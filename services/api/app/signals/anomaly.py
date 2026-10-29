"""Institutions that stand out from their peers (D45, ENGINES §17.11).

An Isolation Forest per academic year over five features of each institution's ACTIVE
records. The model only points: each outlier carries every feature with its value, the
peers' quartiles and median and a robust z-score, and the features that made it stand out.
`score` is pure apart from scikit-learn and deterministic for a given `random_state`.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from sklearn.ensemble import IsolationForest
from sqlalchemy import and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import AdmissionRoute, CheckStatus, EnrolmentStatus
from app.models.student import Enrolment
from app.models.verification import Check
from app.signals.rings import Member, load_members, sharing_students

FEATURES = (
    "admission_growth",
    "nri_share",
    "management_share",
    "contradiction_rate",
    "contact_sharing_rate",
)
# copy deck signal.feature.*
FEATURE_WORDS = {
    "admission_growth": "Admission growth on last year",
    "nri_share": "NRI share of admissions",
    "management_share": "Management share of admissions",
    "contradiction_rate": "Records with a contradicted row",
    "contact_sharing_rate": "Students sharing a contact",
}
STANDS_OUT_Z = 2.0
MAD_SCALE = 1.4826  # makes the median absolute deviation comparable to a standard deviation
MEAN_AD_SCALE = 1.2533  # the same for the mean absolute deviation, when the MAD is 0
# copy deck signal.rule.ANOMALY
RULE = (
    "Model: Isolation Forest, contamination {contamination}, trained on this year's {n} colleges."
)
MODEL_NAME = "IsolationForest"


@dataclass(frozen=True, slots=True)
class AnomalySettings:
    """rules.yaml `signals.anomaly` (API_CONTRACT §A4.1); these defaults when it is absent."""

    contamination: float = 0.05
    n_estimators: int = 200
    random_state: int = 0
    min_records: int = 20


@lru_cache
def _settings_from(path: str) -> AnomalySettings:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    block = (raw.get("signals") or {}).get("anomaly") or {}
    defaults = AnomalySettings()
    return AnomalySettings(
        contamination=float(block.get("contamination", defaults.contamination)),
        n_estimators=int(block.get("n_estimators", defaults.n_estimators)),
        random_state=int(block.get("random_state", defaults.random_state)),
        min_records=int(block.get("min_records", defaults.min_records)),
    )


def settings(path: str | Path | None = None) -> AnomalySettings:
    return _settings_from(str(path or get_settings().resolved_rules_path()))


@dataclass(frozen=True, slots=True)
class InstitutionFeatures:
    institution_id: uuid.UUID
    values: Mapping[str, float | None]  # None: the feature cannot be measured here
    records: int


@dataclass(frozen=True, slots=True)
class Outlier:
    institution_id: uuid.UUID
    score: float  # IsolationForest.score_samples (lower is more unusual)
    features: tuple[dict[str, Any], ...]  # name, value, peer_low, peer_high, peer_median,
    # robust_z, stands_out

    @property
    def standing_out(self) -> list[str]:
        return [f["name"] for f in self.features if f["stands_out"]]


# ------------------------------------------------------------------------ model


def _matrix(rows: Sequence[InstitutionFeatures]) -> np.ndarray:
    """One row per institution; a feature that cannot be measured takes the peers' median."""
    x = np.array(
        [
            [np.nan if r.values.get(f) is None else float(r.values[f]) for f in FEATURES]
            for r in rows
        ],
        dtype=float,
    )
    for j in range(x.shape[1]):
        column = x[:, j]
        missing = np.isnan(column)
        if missing.any():
            column[missing] = float(np.median(column[~missing])) if (~missing).any() else 0.0
    return x


def _spread(values: np.ndarray, median: float) -> float:
    deviations = np.abs(values - median)
    scale = MAD_SCALE * float(np.median(deviations))
    if scale == 0.0:
        scale = MEAN_AD_SCALE * float(np.mean(deviations))
    return scale


def explain(x: np.ndarray, i: int) -> tuple[dict[str, Any], ...]:
    """Each feature of row i against the other rows: quartiles, median and robust z-score.
    A feature stands out at |z| >= 2; when none does, the one furthest out still does."""
    others = np.delete(x, i, axis=0)
    out: list[dict[str, Any]] = []
    for j, name in enumerate(FEATURES):
        peers = others[:, j]
        median = float(np.median(peers))
        scale = _spread(peers, median)
        value = float(x[i, j])
        z = 0.0 if scale == 0.0 else (value - median) / scale
        out.append(
            {
                "name": name,
                "value": round(value, 3),
                "peer_low": round(float(np.percentile(peers, 25)), 3),
                "peer_high": round(float(np.percentile(peers, 75)), 3),
                "peer_median": round(median, 3),
                "robust_z": round(z, 1),
                "stands_out": abs(z) >= STANDS_OUT_Z,
                "_z": abs(z),
            }
        )
    if not any(f["stands_out"] for f in out):
        max(out, key=lambda f: f["_z"])["stands_out"] = True
    for f in out:
        del f["_z"]
    return tuple(out)


def score(
    rows: Sequence[InstitutionFeatures],
    *,
    contamination: float,
    n_estimators: int,
    random_state: int,
) -> list[Outlier]:
    """The rows the forest predicts as outliers (-1), most unusual first."""
    rows = sorted(rows, key=lambda r: str(r.institution_id))
    if len(rows) < 2:
        return []
    x = _matrix(rows)
    model = IsolationForest(
        n_estimators=n_estimators, contamination=contamination, random_state=random_state
    )
    predicted = model.fit_predict(x)
    scores = model.score_samples(x)
    outliers = [
        Outlier(
            institution_id=rows[i].institution_id,
            score=round(float(scores[i]), 4),
            features=explain(x, i),
        )
        for i in range(len(rows))
        if predicted[i] == -1
    ]
    outliers.sort(key=lambda o: (o.score, str(o.institution_id)))
    return outliers


# ---------------------------------------------------------------------- features


async def load_features(
    session: AsyncSession,
    academic_year: str,
    *,
    min_records: int,
    members: Sequence[Member] | None = None,
) -> list[InstitutionFeatures]:
    """The five features of every institution with `min_records` or more ACTIVE records."""
    y1 = Enrolment.year_of_study == 1
    route = Enrolment.admission_route
    active = and_(
        Enrolment.academic_year == academic_year, Enrolment.status == EnrolmentStatus.ACTIVE
    )
    per_programme = (
        await session.execute(
            select(
                Enrolment.institution_id,
                func.count(),
                func.count().filter(y1),
                func.count().filter(Enrolment.year_of_study == 2, route != AdmissionRoute.LATERAL),
                func.count().filter(y1, route == AdmissionRoute.NRI),
                func.count().filter(
                    y1, route.in_([AdmissionRoute.MANAGEMENT, AdmissionRoute.SPOT])
                ),
            )
            .where(active)
            .group_by(Enrolment.institution_id, Enrolment.programme_id)
        )
    ).all()
    contradicted = dict(
        (
            await session.execute(
                select(Enrolment.institution_id, func.count())
                .where(
                    active,
                    exists().where(
                        Check.enrolment_id == Enrolment.id,
                        Check.status == CheckStatus.CONTRADICTED,
                        Check.resolved.is_(None),
                    ),
                )
                .group_by(Enrolment.institution_id)
            )
        ).all()
    )
    if members is None:
        members = await load_members(session, academic_year)
    sharing = sharing_students(members)
    students: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for member in members:
        students[member.institution_id].add(member.student_id)

    totals: dict[uuid.UUID, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for institution_id, records, first, second, nri, management in per_programme:
        t = totals[institution_id]
        t["records"] += records
        t["first"] += first
        t["nri"] += nri
        t["management"] += management
        if second:  # like for like: programmes with a previous cohort on the roll
            t["growth_first"] += first
            t["growth_second"] += second

    out: list[InstitutionFeatures] = []
    for institution_id, t in totals.items():
        if t["records"] < min_records:
            continue
        own = students.get(institution_id, set())
        out.append(
            InstitutionFeatures(
                institution_id=institution_id,
                records=t["records"],
                values={
                    "admission_growth": t["growth_first"] / t["growth_second"]
                    if t["growth_second"]
                    else None,
                    "nri_share": t["nri"] / t["first"] if t["first"] else 0.0,
                    "management_share": t["management"] / t["first"] if t["first"] else 0.0,
                    "contradiction_rate": contradicted.get(institution_id, 0) / t["records"],
                    "contact_sharing_rate": len(own & sharing) / len(own) if own else 0.0,
                },
            )
        )
    out.sort(key=lambda r: str(r.institution_id))
    return out


# ------------------------------------------------------------------- sentences


def percent(value: float) -> str:
    """0.05 -> `5%`, 0.025 -> `2.5%`."""
    text = f"{100 * value:.1f}".removesuffix(".0")
    return f"{text}%"


def feature_value(name: str, value: float) -> str:
    """Shares and rates as percentages; growth as a ratio of this year's first-years to the
    previous cohort."""
    if name == "admission_growth":
        return f"{value:.2f}"
    return percent(value)


def feature_word(name: str, *, lower: bool = False) -> str:
    word = FEATURE_WORDS[name]
    if lower and not word[:2].isupper():
        return word[:1].lower() + word[1:]
    return word


def feature_words(names: Sequence[str]) -> str:
    """`NRI share of admissions and management share of admissions`."""
    words = [feature_word(n, lower=True) for n in names]
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


def feature_fact(feature: Mapping[str, Any], source: str) -> dict[str, Any]:
    """copy deck signal.feature_line as a fact: the label is the feature word."""
    name = feature["name"]
    low = feature_value(name, feature["peer_low"])
    high = feature_value(name, feature["peer_high"])
    return {
        "label": feature_word(name),
        "value": f"{feature_value(name, feature['value'])} (similar colleges {low} to {high})",
        "source": source,
    }


def summary(institution_name: str, peers: int, academic_year: str, names: Sequence[str]) -> str:
    """copy deck signal.summary.ANOMALY."""
    return (
        f"{institution_name} stands out from {peers} similar colleges in {academic_year} "
        f"on {feature_words(names)}."
    )


def rule(contamination: float, n: int) -> str:
    return RULE.format(contamination=percent(contamination), n=n)
