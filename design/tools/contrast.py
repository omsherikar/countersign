#!/usr/bin/env python3
"""Compute WCAG 2 contrast ratios for the Countersign token palette.

Parses design/tokens.css (the :root and .dark blocks), resolves var()
aliases, and checks every foreground/background pair the design system
relies on. Text pairs must reach 4.5:1, marks and large text 3:1, and the
Integrity Index ramp must step monotonically in luminance.

    python3 design/tools/contrast.py            # table + exit 1 on failure
    python3 design/tools/contrast.py --md       # markdown for DESIGN.md
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

TOKENS = Path(__file__).resolve().parents[1] / "tokens.css"

HUES = ["ok", "alert", "caution", "neutral", "blue", "seal", "teal"]

# (label, foreground, background, minimum ratio)
PAIRS: list[tuple[str, str, str, float]] = [
    ("Body text on page", "ink", "paper", 4.5),
    ("Body text on card", "ink", "paper-raised", 4.5),
    ("Body text on sunken", "ink", "paper-sunken", 4.5),
    ("Muted text on page", "ink-muted", "paper", 4.5),
    ("Muted text on card", "ink-muted", "paper-raised", 4.5),
    ("Muted text on sunken", "ink-muted", "paper-sunken", 4.5),
    ("Faint text on card (large only)", "ink-faint", "paper-raised", 3.0),
    ("Link / primary text on page", "ink-blue", "paper", 4.5),
    ("Link / primary text on card", "ink-blue", "paper-raised", 4.5),
    ("Primary button label", "on-ink-blue", "ink-blue", 4.5),
    ("Seal (stamp) text on page", "seal", "paper", 4.5),
    ("Seal (stamp) text on card", "seal", "paper-raised", 4.5),
    ("Label on solid seal", "on-seal", "seal", 4.5),
    ("Destructive button label", "destructive-foreground", "destructive", 4.5),
    ("Accent foreground on accent", "accent-foreground", "accent", 4.5),
    ("Sidebar text", "sidebar-foreground", "sidebar", 4.5),
    ("Feint rule on page (decorative)", "rule", "paper", 0.0),
    ("Margin rule on page (decorative)", "rule-margin", "paper", 0.0),
    ("Border on card (decorative)", "line", "paper-raised", 0.0),
]
for h in HUES:
    PAIRS += [
        (f"{h}: ink on soft tint", f"hue-{h}-ink", f"hue-{h}-soft", 4.5),
        (f"{h}: ink on page", f"hue-{h}-ink", "paper", 4.5),
        (f"{h}: ink on card", f"hue-{h}-ink", "paper-raised", 4.5),
        (f"{h}: mark on page", f"hue-{h}", "paper", 3.0),
        (f"{h}: mark on card", f"hue-{h}", "paper-raised", 3.0),
        (f"{h}: mark on soft tint", f"hue-{h}", f"hue-{h}-soft", 3.0),
    ]
for i in range(1, 7):
    PAIRS.append((f"chart-{i} on card", f"chart-{i}", "paper-raised", 3.0))
PAIRS += [
    ("index-7 on card", "index-7", "paper-raised", 3.0),
    ("Text on index-1 (ink)", "ink", "index-1", 4.5),
    ("Text on index-7 (paper)", "paper-raised", "index-7", 4.5),
]


def parse_blocks(css: str) -> dict[str, dict[str, str]]:
    blocks: dict[str, dict[str, str]] = {}
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for sel in (":root", ".dark"):
        m = re.search(re.escape(sel) + r"\s*\{(.*?)\n\}", css, flags=re.S)
        if not m:
            raise SystemExit(f"block {sel} not found in {TOKENS}")
        props: dict[str, str] = {}
        for name, value in re.findall(r"--([\w-]+)\s*:\s*([^;]+);", m.group(1)):
            props[name] = value.strip()
        blocks[sel] = props
    return blocks


def resolve(name: str, props: dict[str, str], depth: int = 0) -> str:
    if depth > 10:
        raise SystemExit(f"alias loop at --{name}")
    value = props.get(name)
    if value is None:
        raise SystemExit(f"--{name} is not defined")
    m = re.fullmatch(r"var\(--([\w-]+)\)", value)
    if m:
        return resolve(m.group(1), props, depth + 1)
    return value


def hex_to_rgb(value: str) -> tuple[float, float, float]:
    v = value.strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", v):
        raise SystemExit(f"not a 6-digit hex colour: {value!r}")
    return tuple(int(v[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def luminance(value: str) -> float:
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in hex_to_rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: str, bg: str) -> float:
    l1, l2 = luminance(fg), luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def main() -> int:
    md = "--md" in sys.argv
    blocks = parse_blocks(TOKENS.read_text())
    light = blocks[":root"]
    dark = {**light, **blocks[".dark"]}
    failures: list[str] = []

    if md:
        print("| Pair | Light | ratio | Dark | ratio | min |")
        print("|---|---|---|---|---|---|")
    else:
        print(f"{'pair':38} {'light':>18} {'ratio':>6}  {'dark':>18} {'ratio':>6}  min")
    for label, fg, bg, minimum in PAIRS:
        row = []
        for mode, props in (("light", light), ("dark", dark)):
            f, b = resolve(fg, props), resolve(bg, props)
            ratio = contrast(f, b)
            ok = ratio >= minimum
            if not ok:
                failures.append(f"{mode}: {label} {f} on {b} = {ratio:.2f} < {minimum}")
            row.append((f, b, ratio, ok))
        (lf, lb, lr, lok), (df, db, dr, dok) = row
        if md:
            mark = "" if (lok and dok) else " FAIL"
            print(f"| {label} | `{lf}` on `{lb}` | {lr:.2f} | `{df}` on `{db}` | {dr:.2f} | {minimum:g}{mark} |")
        else:
            flag = "" if (lok and dok) else "   <-- FAIL"
            print(f"{label:38} {lf + ' on ' + lb:>18} {lr:6.2f}  {df + ' on ' + db:>18} {dr:6.2f}  {minimum:g}{flag}")

    # Integrity ramp: luminance must be monotonic in both modes.
    for mode, props, direction in (("light", light, -1), ("dark", dark, 1)):
        lums = [luminance(resolve(f"index-{i}", props)) for i in range(1, 8)]
        steps = [b - a for a, b in zip(lums, lums[1:])]
        if not all((s * direction) > 0 for s in steps):
            failures.append(f"{mode}: integrity ramp is not monotonic: {[round(l, 3) for l in lums]}")
        if not md:
            print(f"\nindex ramp ({mode}) luminance: " + " ".join(f"{l:.3f}" for l in lums))

    if failures:
        print("\nFAILED:", file=sys.stderr)
        for f in failures:
            print("  " + f, file=sys.stderr)
        return 1
    if not md:
        print("\nall pairs pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
