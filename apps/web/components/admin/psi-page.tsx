"use client";

import { t } from "@/lib/copy";
import { formatClock, formatCount } from "@/lib/format";
import { useComputePsi } from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { KpiTile } from "@/components/brand/KpiTile";
import { ErrorBlock } from "@/components/common/query-state";
import { Crumbs, PageHeader } from "@/components/common/page-header";

const STEPS = ["psi.step.1", "psi.step.2", "psi.step.3", "psi.step.4"] as const;

/**
 * /admin/psi (W4-14, D48): Countersign and a mock partner regulator learn how many
 * APAAR-linked students they both hold by private set intersection. Counts only.
 * AICTE_ADMIN only.
 */
export function PsiPage() {
  const run = useComputePsi();
  const r = run.data;
  return (
    <>
      <Crumbs items={[{ label: t("nav.overview"), href: "/aicte" }, { label: t("psi.heading") }]} />
      <PageHeader title={t("psi.heading")} description={t("psi.lead")} actions={<span className="stamp">{t("psi.demo_tag")}</span>} />

      <section aria-label={t("psi.counts_note")} className="mb-2 grid gap-4 sm:grid-cols-2">
        <div className="border-l-2 border-rule-margin bg-paper-raised">
          <KpiTile label={t("psi.ours")} value={r ? r.countersign_count : null} hint={t("psi.ours_hint")} />
        </div>
        <div className="border-l-2 border-rule-margin bg-paper-raised">
          <KpiTile label={t("psi.theirs")} value={r ? r.partner_count : null} hint={t("psi.theirs_hint")} />
        </div>
      </section>
      <p className="mb-6 text-xs text-ink-muted">{t("psi.counts_note")}</p>

      <div className="mb-4">
        <Button onClick={() => run.mutate()} disabled={run.isPending}>
          {t("psi.compute")}
        </Button>
      </div>

      <section className="mb-8 border-l-2 border-rule-margin bg-paper-raised px-4 py-3 text-sm" aria-live="polite">
        {run.isPending && <span className="text-ink-muted">{t("psi.computing")}</span>}
        {!run.isPending && run.isError && <ErrorBlock error={run.error} onRetry={() => run.mutate()} compact />}
        {!run.isPending && !run.isError && !r && <span className="text-ink-muted">{t("psi.idle")}</span>}
        {!run.isPending && r && (
          <div className="flex flex-col gap-2">
            <p className="text-md font-medium text-ink">{t("psi.result", { n: formatCount(r.overlap) })}</p>
            <p className="text-ink-muted">{t("psi.explain")}</p>
            <p className="text-xs text-ink-muted">{t("psi.computed_at", { time: formatClock(r.computed_at), method: r.method })}</p>
          </div>
        )}
      </section>

      <details className="group max-w-prose text-sm">
        <summary className="cursor-pointer text-ink-blue hover:underline">{t("psi.show_how")}</summary>
        <ol className="mt-3 list-decimal space-y-2 pl-5 text-ink">
          {STEPS.map((id) => (
            <li key={id}>{t(id)}</li>
          ))}
        </ol>
      </details>
    </>
  );
}
