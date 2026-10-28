"use client";

import * as React from "react";
import { Flag } from "lucide-react";
import { EmptyState } from "@/components/brand/EmptyState";
import { t } from "@/lib/copy";
import { institutionAdmitted } from "@/lib/counts";
import { formatCount } from "@/lib/format";
import { useInstitution } from "@/lib/queries";
import { REGION_NAME } from "@/lib/roles";
import type { InstitutionDetail as Detail } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ErrorBlock, SlowHint } from "@/components/common/query-state";
import { Crumbs, SectionHeader } from "@/components/common/page-header";
import { TypeChip } from "@/components/common/ledger-bits";
import { EnrolmentsTable } from "@/components/institution/enrolments-table";
import { ProgrammesTable } from "@/components/institution/programmes-table";
import { SeatsTable } from "@/components/institution/seats-table";

const TABS = ["programmes", "enrolments", "seats", "flags"] as const;
type Tab = (typeof TABS)[number];

function subscribeHash(cb: () => void) {
  window.addEventListener("hashchange", cb);
  return () => window.removeEventListener("hashchange", cb);
}

/** Tab state lives in the URL hash (#enrolments) so a refresh keeps it. */
function useHashTab(allowed: readonly Tab[]): [Tab, (t: Tab) => void] {
  const hash = React.useSyncExternalStore(
    subscribeHash,
    () => window.location.hash.replace(/^#/, ""),
    () => "",
  );
  const tab = (allowed as readonly string[]).includes(hash) ? (hash as Tab) : "programmes";
  const setTab = React.useCallback((next: Tab) => {
    const url = `${window.location.pathname}${window.location.search}${next === "programmes" ? "" : `#${next}`}`;
    window.history.replaceState(window.history.state, "", url);
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  }, []);
  return [tab, setTab];
}

/**
 * Seats and admissions as one comparable pair (A2.18): approved seats and
 * admitted are the same intake; students on roll covers every year and is
 * labelled so nobody divides it by seats.
 */
function HeaderFigures({ d, academicYear }: { d: Detail; academicYear: string }) {
  const admitted = institutionAdmitted(d);
  const approved = d.programmes.reduce((a, p) => a + p.approval.approved_intake, 0) || d.approved_seats;
  const intake = t("app.hint.intake", { academic_year: academicYear });
  const cells: { label: string; value: string; hint?: string; tone?: string }[] = [
    { label: t("kpi.approved_seats"), value: formatCount(approved), hint: intake },
    { label: t("kpi.admitted"), value: formatCount(admitted), hint: intake },
    { label: t("kpi.enrolments"), value: formatCount(d.enrolments), hint: t("app.hint.all_years") },
    { label: t("kpi.flags_open"), value: formatCount(d.flags_open), tone: d.flags_open > 0 ? undefined : "text-ink-muted" },
  ];
  return (
    <dl className="mt-4 grid grid-cols-2 border-y border-rule bg-paper-raised sm:grid-cols-4" style={{ fontVariantNumeric: "lining-nums proportional-nums" }}>
      {cells.map((c, i) => (
        <div key={c.label} className={`flex min-w-0 flex-col gap-0.5 px-3 py-2 ${i > 0 ? "sm:border-l sm:border-rule" : ""} ${i % 2 === 1 ? "border-l border-rule" : ""} ${i >= 2 ? "border-t border-rule sm:border-t-0" : ""}`}>
          <dt className="truncate text-xs font-medium text-ink-muted">{c.label}</dt>
          <dd className={`font-display text-xl leading-tight font-semibold ${c.tone ?? ""}`}>{c.value}</dd>
          {c.hint && <dd className="truncate text-xs text-ink-muted">{c.hint}</dd>}
        </div>
      ))}
    </dl>
  );
}

function DetailHeader({ d, academicYear }: { d: Detail; academicYear: string }) {
  const place = [d.address_city, d.state_code].filter(Boolean).join(", ");
  const second = [
    t("app.detail.region", { region_name: REGION_NAME[d.region] }),
    d.university_name,
    d.established_year ? t("app.detail.est", { year: d.established_year }) : null,
  ].filter(Boolean);
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
      <div className="min-w-0">
        <h1 className="text-2xl md:text-3xl">{d.name}</h1>
        <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink-muted">
          <span className="code text-ink">{d.aicte_permanent_id}</span>
          <TypeChip type={d.type} />
          {place && <span>{place}</span>}
        </p>
        <p className="mt-1 text-sm text-ink-muted">{second.join(", ")}</p>
        <HeaderFigures d={d} academicYear={academicYear} />
      </div>
      <dl className="flex min-w-44 flex-col gap-1 border-l-2 border-rule-margin pl-4">
        <dt className="text-xs font-medium text-ink-muted">{t("index.label")}</dt>
        <dd>
          {d.integrity_index === null ? (
            <span className="font-display text-lg text-ink-muted italic">{t("kpi.not_computed")}</span>
          ) : (
            <span className="font-display text-3xl font-semibold">{Math.round(d.integrity_index)}</span>
          )}
        </dd>
      </dl>
    </div>
  );
}

function HeaderSkeleton() {
  return (
    <div className="mb-6 flex flex-col gap-3" aria-hidden="true">
      <Skeleton className="h-9 w-96 max-w-full" />
      <Skeleton className="h-4 w-80 max-w-full" />
      <Skeleton className="h-4 w-64 max-w-full" />
    </div>
  );
}

/**
 * One institution: header, then Programmes, Enrolments, Seats and Flags
 * tabs. Shared by /aicte, /ro and /university (read-only, no Flags tab).
 */
export function InstitutionDetail({
  id,
  crumbRoot,
  showFlags = true,
}: {
  id: string;
  crumbRoot: { label: string; href: string };
  showFlags?: boolean;
}) {
  const detail = useInstitution(id);
  const allowed = showFlags ? TABS : TABS.filter((x) => x !== "flags");
  const [tab, setTab] = useHashTab(allowed);
  const d = detail.data;

  if (detail.isError && !d) {
    return (
      <>
        <Crumbs items={[crumbRoot, { label: "Institution" }]} />
        <h1 className="sr-only">{t("err.NOT_FOUND_generic")}</h1>
        <ErrorBlock error={detail.error} entity="institution" backHref={crumbRoot.href} onRetry={() => detail.refetch()} className="mt-4" />
      </>
    );
  }

  // Every active enrolment in the year, matching the enrolments list below; programme
  // rows count only their own intake.
  const enrolmentCount = d ? d.enrolments : null;
  const academicYear = d?.programmes[0]?.approval.academic_year ?? "2026-27";

  return (
    <>
      <Crumbs items={[crumbRoot, { label: d?.name ?? "…" }]} />
      {d ? <DetailHeader d={d} academicYear={academicYear} /> : <HeaderSkeleton />}
      {detail.isLoading && <SlowHint className="-mt-4 mb-4" />}

      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
        <TabsList className="mb-4">
          <TabsTrigger value="programmes">{t("tab.programmes")}</TabsTrigger>
          <TabsTrigger value="enrolments">
            {t("tab.enrolments")}
            {enrolmentCount !== null && <span className="num ml-1.5 text-xs text-ink-muted">{formatCount(enrolmentCount)}</span>}
          </TabsTrigger>
          <TabsTrigger value="seats">{t("tab.seats")}</TabsTrigger>
          {showFlags && (
            <TabsTrigger value="flags">
              {t("tab.flags")}
              {d && <span className="num ml-1.5 text-xs text-ink-muted">{formatCount(d.flags_open)}</span>}
            </TabsTrigger>
          )}
        </TabsList>

        <TabsContent value="programmes">
          <SectionHeader
            title={
              <>
                {t("section.programmes")} {d && <span className="num text-ink-muted">({d.programmes.length})</span>}
              </>
            }
            aside={<span>{`${t("app.academic_year")} ${academicYear}`}</span>}
          />
          {d ? (
            <ProgrammesTable programmes={d.programmes} academicYear={academicYear} />
          ) : (
            <div className="flex flex-col gap-2" aria-hidden="true">
              {Array.from({ length: 4 }, (_, i) => (
                <Skeleton key={i} className="h-9" />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="enrolments">
          {d && (
            <EnrolmentsTable
              institutionId={d.id}
              programmes={d.programmes}
              academicYear={academicYear}
              enrolmentHref={(eid) => `${crumbRoot.href}/enrolments/${eid}`}
              flagHref={showFlags ? (fid) => `${crumbRoot.href}/cases/${fid}` : undefined}
            />
          )}
        </TabsContent>

        <TabsContent value="seats">{d && <SeatsTable institutionId={d.id} programmes={d.programmes} />}</TabsContent>

        {showFlags && (
          <TabsContent value="flags">
            <SectionHeader title={`${t("section.flags")} (${d ? formatCount(d.flags_open) : 0})`} />
            <div className="border-l-2 border-rule-margin bg-paper-raised">
              <EmptyState icon={<Flag className="size-5" />} title={t("empty.flags_institution")} />
            </div>
          </TabsContent>
        )}
      </Tabs>
    </>
  );
}

