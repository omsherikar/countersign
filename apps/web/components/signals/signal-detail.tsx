"use client";

import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";
import { ApiError } from "@/lib/api";
import { t, tk } from "@/lib/copy";
import { formatCount, formatDate } from "@/lib/format";
import { useDismissSignal, useOpenSignalCase, useSignal } from "@/lib/queries-signals";
import type { SignalDetail as Detail, SignalFeature } from "@/lib/types";
import { MaskedApaar } from "@/components/brand/MaskedApaar";
import { FlagStatusBadge } from "@/components/brand/FlagStatusBadge";
import { ReadLoggedNote } from "@/components/common/ledger-bits";
import { Crumbs, SectionHeader } from "@/components/common/page-header";
import { ErrorBlock, SlowHint } from "@/components/common/query-state";
import { useMe } from "@/components/providers/root-provider";
import { RecordStatusBadge } from "@/components/records/record-status-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ChangesList, CaseSheetShell, NoteField, SheetButtons } from "@/components/cases/sheet-shell";
import { RingDrawing } from "@/components/signals/ring-drawing";
import { NeverStatusLine, SignalStatusBadge, SignalTypeWord } from "@/components/signals/signal-bits";

const pct = (v: number) => `${Math.round(v * 100)}%`;

function featureLine(f: SignalFeature): string {
  return t("signal.feature_line", { feature_word: tk(`signal.feature.${f.name}`), value: pct(f.value), low: pct(f.peer_low), high: pct(f.peer_high) });
}

/**
 * One signal (W4-6): the summary as the api wrote it, the facts and the
 * rule or model line every time, the members (masked ids) or the feature
 * lines, then Open case and Dismiss. Signals never change a record; the
 * case an officer opens is the only way they can.
 */
export function SignalDetailPage({ id, variant }: { id: string; variant: "aicte" | "ro" }) {
  const q = useSignal(id);
  const { user } = useMe();
  const d = q.data;
  const heading = React.useRef<HTMLHeadingElement>(null);
  const [sheet, setSheet] = React.useState<"open" | "dismiss" | null>(null);
  const opener = React.useRef<HTMLButtonElement | null>(null);
  const base = `/${variant}`;
  const crumbs = [
    { label: t("nav.overview"), href: base },
    { label: t("signal.heading"), href: `${base}/signals` },
    { label: d ? tk(`signal.type.${d.type}`) : "…" },
  ];

  if (q.isError && !d) {
    return (
      <>
        <Crumbs items={crumbs} />
        <h1 className="sr-only">{t("signal.heading")}</h1>
        <ErrorBlock
          error={q.error}
          entity="signal"
          backHref={`${base}/signals`}
          backLabel={t("signal.panel_more")}
          onRetry={() => q.refetch()}
          className="mt-4"
        />
      </>
    );
  }
  if (!d) {
    return (
      <>
        <Crumbs items={crumbs} />
        <div className="flex flex-col gap-3" aria-hidden="true">
          <Skeleton className="h-9 w-72" />
          <Skeleton className="h-5 w-full max-w-2xl" />
          <Skeleton className="mt-6 h-64 max-w-4xl" />
          <SlowHint />
        </div>
      </>
    );
  }

  const openCases = new Set(d.cases.map((c) => c.institution_id));
  const canOpen = d.status !== "DISMISSED" && d.institutions.some((i) => !openCases.has(i.id));
  const canDismiss = d.status === "NEW";
  const drawingLabel = t("signal.drawing_alt", { members: formatCount(d.members.length), contacts: formatCount(d.shared.length) });

  return (
    <>
      <Crumbs items={crumbs} />
      <header className="mb-6">
        <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
          <h1 ref={heading} tabIndex={-1} className="text-2xl outline-none md:text-3xl">
            <SignalTypeWord type={d.type} />
          </h1>
          <p className="flex flex-wrap items-center gap-2 text-sm text-ink-muted">
            <SignalStatusBadge status={d.status} />
            <span>{t("signal.found_on", { date: formatDate(d.created_at) })}</span>
          </p>
        </div>
        <p className="mt-3 max-w-[68ch] font-display text-lg leading-snug">{d.summary}</p>
      </header>

      <section aria-labelledby="facts-heading" className="mb-8 max-w-5xl">
        <SectionHeader id="facts-heading" title={t("section.evidence")} />
        <div className="grid grid-cols-1 gap-6 md:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
          {d.type === "GHOST_RING" && d.members.length > 0 && (
            <div className="hidden md:block">
              <RingDrawing signal={d} label={drawingLabel} />
              <p className="mt-2 text-xs text-ink-muted">{t("signal.drawing_note")}</p>
            </div>
          )}
          <div className={d.type === "GHOST_RING" && d.members.length > 0 ? "min-w-0" : "min-w-0 md:col-span-2"}>
            <div className="relative overflow-x-auto border-l-2 border-rule-margin bg-paper-raised">
              <table className="ledger-table">
                <caption className="sr-only">{t("section.evidence")}</caption>
                <thead>
                  <tr>
                    <th scope="col">{t("flag.facts.label")}</th>
                    <th scope="col">{t("flag.facts.value")}</th>
                    <th scope="col">{t("flag.facts.source")}</th>
                  </tr>
                </thead>
                <tbody>
                  {d.facts.map((f) => (
                    <tr key={f.label}>
                      <th scope="row" className="wrap !h-auto min-w-36 py-2 text-left align-top font-medium">
                        {f.label}
                      </th>
                      <td className="wrap !h-auto min-w-48 py-2 align-top leading-snug">{f.value}</td>
                      <td className="wrap !h-auto py-2 align-top text-ink-muted">{f.source}</td>
                    </tr>
                  ))}
                  {d.shared.map((s, i) => (
                    <tr key={`shared-${i}`}>
                      <th scope="row" className="wrap !h-auto min-w-36 py-2 text-left align-top font-medium">
                        {t(s.kind === "MOBILE" ? "signal.fact.mobile_one" : s.kind === "EMAIL" ? "signal.fact.email_one" : "signal.fact.address_one")}
                      </th>
                      <td className="wrap !h-auto py-2 align-top">
                        <span className="code">{s.masked}</span> · {t("signal.shared_by", { n: formatCount(s.students) })}
                      </td>
                      <td className="wrap !h-auto py-2 align-top text-ink-muted">{t("signal.shared_source")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {d.features.length > 0 && (
              <ul className="mt-4 flex flex-col gap-1.5 text-md md:text-sm">
                {d.features.map((f) => (
                  <li key={f.name} className={f.stands_out ? "font-medium" : "text-ink-muted"}>
                    {featureLine(f)}
                    {f.stands_out && <span className="ml-2 rounded-chip border border-line px-1 text-2xs font-normal text-ink-muted">{t("signal.stands_out")}</span>}
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-4 max-w-[68ch] text-sm text-ink">{d.rule}</p>
          </div>
        </div>
      </section>

      {d.type === "GHOST_RING" && (
        <section aria-labelledby="members-heading" className="mb-8">
          <SectionHeader id="members-heading" title={t("signal.members_heading", { n: formatCount(d.member_count) })} />
          <MembersTable signal={d} base={base} />
          {d.members_hidden > 0 && <p className="mt-2 text-sm text-ink-muted">{t("signal.members_hidden", { n: formatCount(d.members_hidden) })}</p>}
        </section>
      )}

      {d.cases.length > 0 && (
        <section aria-labelledby="cases-heading" className="mb-8">
          <SectionHeader id="cases-heading" title={t("signal.cases_heading")} />
          <ul className="flex flex-col gap-2">
            {d.cases.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span>{d.institutions.find((i) => i.id === c.institution_id)?.name}</span>
                <FlagStatusBadge status={c.status} />
                <Link href={`${base}/cases/${c.id}`} className="inline-flex min-h-11 items-center md:min-h-0">
                  {t("signal.case_link")}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {d.dismissal && (
        <p className="mb-6 max-w-[68ch] border-l-2 border-rule-strong bg-paper-raised px-3 py-2 text-sm">
          {t("signal.dismissed_line", { name: d.dismissal.by.name, date: formatDate(d.dismissal.at), note: d.dismissal.note })}
        </p>
      )}

      {(canOpen || canDismiss) && (
        <div className="mb-6 flex flex-col gap-2 border-y border-rule py-3 sm:flex-row">
          {canOpen && (
            <button type="button" aria-haspopup="dialog" onClick={(e) => {
                opener.current = e.currentTarget;
                setSheet("open");
              }} className="inline-flex h-12 w-full items-center justify-center rounded-md bg-ink-blue px-4 text-md font-medium text-on-ink-blue hover:bg-ink-blue-hover sm:h-9 sm:w-auto sm:text-sm">
              {t("signal.open_case")}
            </button>
          )}
          {canDismiss && (
            <button type="button" aria-haspopup="dialog" onClick={(e) => {
                opener.current = e.currentTarget;
                setSheet("dismiss");
              }} className="inline-flex h-12 w-full items-center justify-center rounded-md border border-line bg-paper-raised px-4 text-md font-medium hover:bg-paper-sunken sm:h-9 sm:w-auto sm:text-sm">
              {t("signal.dismiss")}
            </button>
          )}
        </div>
      )}

      <NeverStatusLine className="mb-3" />
      <ReadLoggedNote />

      <OpenCaseSheet
        open={sheet === "open"}
        signal={d}
        canAct={user?.role === "AICTE_ADMIN" || user?.role === "RO_OFFICER"}
        onClose={() => setSheet(null)}
        returnFocus={() => (opener.current?.isConnected ? opener.current.focus() : heading.current?.focus())}
      />
      <DismissSheet
        open={sheet === "dismiss"}
        signal={d}
        onClose={() => setSheet(null)}
        returnFocus={() => (opener.current?.isConnected ? opener.current.focus() : heading.current?.focus())}
      />
    </>
  );
}

function MembersTable({ signal, base }: { signal: Detail; base: string }) {
  if (signal.members.length === 0) return null;
  return (
    <>
      <ul className="flex flex-col divide-y divide-rule border-l-2 border-rule-margin bg-paper-raised md:hidden">
        {signal.members.map((m) => (
          <li key={m.enrolment_id} className="px-3 py-2.5">
            <Link href={`${base}/enrolments/${m.enrolment_id}`} className="font-medium">
              {m.student.name}
            </Link>
            <p className="code text-sm text-ink-muted">
              <MaskedApaar apaarMasked={m.student.apaar_masked} provisionalId={m.student.provisional_id} />
            </p>
            <p className="flex flex-wrap items-center gap-2 text-sm text-ink-muted">
              <span>
                {m.institution.name} · {m.programme_code}
              </span>
              <RecordStatusBadge status={m.record_status} />
            </p>
          </li>
        ))}
      </ul>
      <div className="relative hidden max-h-[28rem] overflow-auto border-l-2 border-rule-margin bg-paper-raised md:block">
        <table className="ledger-table">
          <caption className="sr-only">{t("signal.fact.members")}</caption>
          <thead className="sticky top-0 z-10 bg-paper-raised">
            <tr>
              <th scope="col">{t("col.student")}</th>
              <th scope="col" className="code">
                {t("col.apaar")}
              </th>
              <th scope="col">{t("col.institution")}</th>
              <th scope="col" className="code">
                {t("col.programme")}
              </th>
              <th scope="col">{t("col.record_status")}</th>
            </tr>
          </thead>
          <tbody>
            {signal.members.map((m) => (
              <tr key={m.enrolment_id}>
                <td className="font-medium">
                  <Link href={`${base}/enrolments/${m.enrolment_id}`}>{m.student.name}</Link>
                </td>
                <td className="code">
                  <MaskedApaar apaarMasked={m.student.apaar_masked} provisionalId={m.student.provisional_id} />
                </td>
                <td className="max-w-[16rem] truncate text-ink-muted" title={m.institution.name}>
                  {m.institution.name}
                </td>
                <td className="code">{m.programme_code}</td>
                <td>
                  <RecordStatusBadge status={m.record_status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

/** "Open a case from this signal?": one case per college chosen, citing the signal; the records it names read Under review. */
function OpenCaseSheet({ open, signal, canAct, onClose, returnFocus }: { open: boolean; signal: Detail; canAct: boolean; onClose: () => void; returnFocus: () => void }) {
  const ids = React.useId();
  const mutation = useOpenSignalCase(signal.id);
  const choices = signal.institutions.filter((i) => !signal.cases.some((c) => c.institution_id === i.id));
  const [picked, setPicked] = React.useState<string[]>([]);
  const [note, setNote] = React.useState("");
  const [errors, setErrors] = React.useState<{ picked?: string; note?: string }>({});
  const [formError, setFormError] = React.useState<string | null>(null);
  const noteRef = React.useRef<HTMLTextAreaElement>(null);
  const firstBox = React.useRef<HTMLInputElement>(null);
  const [shown, setShown] = React.useState(open);
  if (open !== shown) {
    setShown(open);
    if (open) {
      setPicked(choices.length === 1 ? [choices[0].id] : []);
      setNote("");
      setErrors({});
      setFormError(null);
    }
  }
  const caseName = tk(`flag.${signal.type}.name`);
  const named = signal.type === "GHOST_RING" ? signal.members.filter((m) => picked.includes(m.institution.id)).length : 0;
  const lines = [
    signal.type === "GHOST_RING" ? t("signal.open_case_change", { n: formatCount(named) }).replace(/^The 1 records/, "The 1 record") : t("signal.open_case_change_none"),
  ];
  const n = picked.length;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (mutation.isPending || !canAct) return;
    const local: typeof errors = {};
    if (n === 0) local.picked = t("signal.open_case_pick_required");
    if (!note.trim()) local.note = t("case.note_required");
    setErrors(local);
    setFormError(null);
    if (local.picked) return firstBox.current?.focus();
    if (local.note) return noteRef.current?.focus();
    mutation.mutate(
      { institution_ids: picked, note: note.trim() },
      {
        onSuccess: (res) => {
          toast(res.cases.length === 1 ? t("signal.case_opened_toast") : t("signal.cases_opened_toast", { n: res.cases.length }));
          onClose();
        },
        onError: (err) => {
          if (err instanceof ApiError && err.code === "SIGNAL_ALREADY_HANDLED") setFormError(t("err.SIGNAL_ALREADY_HANDLED"));
          else if (err instanceof ApiError && err.code === "VALIDATION_ERROR" && err.fields.length) setFormError(err.fields[0].message);
          else setFormError(err instanceof ApiError ? err.message : t("err.INTERNAL"));
        },
      },
    );
  }

  return (
    <CaseSheetShell
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title={t("signal.open_case_heading")}
      lead={t("signal.open_case_body", { case_name: caseName })}
      initialFocus={() => (choices.length > 1 ? firstBox.current : noteRef.current)}
      returnFocus={returnFocus}
      busy={mutation.isPending}
      footer={
        <SheetButtons
          form={`${ids}-form`}
          busy={mutation.isPending}
          submitLabel={n > 1 ? t("signal.open_case_submit_many", { n }) : t("signal.open_case_submit")}
          onCancel={onClose}
        />
      }
    >
      <form id={`${ids}-form`} onSubmit={submit} noValidate className="flex flex-col gap-5">
        <fieldset aria-describedby={errors.picked ? `${ids}-picked` : undefined}>
          <legend className="text-sm font-medium">{t("signal.open_case_colleges")}</legend>
          <ul className="mt-2 flex flex-col">
            {choices.map((c, i) => {
              const count = signal.members.filter((m) => m.institution.id === c.id).length;
              return (
                <li key={c.id}>
                  <label className="flex min-h-11 items-center gap-3 text-md md:min-h-9 md:text-sm">
                    <input
                      ref={i === 0 ? firstBox : undefined}
                      type="checkbox"
                      checked={picked.includes(c.id)}
                      onChange={(e) => {
                        setPicked(e.target.checked ? [...picked, c.id] : picked.filter((x) => x !== c.id));
                        setErrors((x) => ({ ...x, picked: undefined }));
                      }}
                      disabled={mutation.isPending}
                      className="size-5 shrink-0 accent-[var(--ink-blue)] md:size-4"
                    />
                    <span>
                      {c.name}
                      {signal.type === "GHOST_RING" && <span className="text-ink-muted"> ({formatCount(count)})</span>}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
          {errors.picked && (
            <p id={`${ids}-picked`} className="mt-1 text-sm text-check-fail-ink">
              {errors.picked}
            </p>
          )}
        </fieldset>
        <NoteField
          ref={noteRef}
          id={`${ids}-note`}
          label={t("case.note_label_internal")}
          value={note}
          onChange={(v) => {
            setNote(v);
            if (v.trim()) setErrors((x) => ({ ...x, note: undefined }));
          }}
          error={errors.note}
          disabled={mutation.isPending}
        />
        <ChangesList lines={lines} loading={false} failed={false} />
        <div aria-live="polite">
          {formError && (
            <p role="alert" className="rounded-md border border-check-fail/30 bg-paper px-3 py-2 text-sm">
              {formError}
            </p>
          )}
        </div>
      </form>
    </CaseSheetShell>
  );
}

/** "Dismiss this signal?" with a required note; no record or case changes. */
function DismissSheet({ open, signal, onClose, returnFocus }: { open: boolean; signal: Detail; onClose: () => void; returnFocus: () => void }) {
  const ids = React.useId();
  const mutation = useDismissSignal(signal.id);
  const [note, setNote] = React.useState("");
  const [error, setError] = React.useState<string | undefined>();
  const [formError, setFormError] = React.useState<string | null>(null);
  const noteRef = React.useRef<HTMLTextAreaElement>(null);
  const [shown, setShown] = React.useState(open);
  if (open !== shown) {
    setShown(open);
    if (open) {
      setNote("");
      setError(undefined);
      setFormError(null);
    }
  }
  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (mutation.isPending) return;
    if (!note.trim()) {
      setError(t("case.note_required"));
      noteRef.current?.focus();
      return;
    }
    mutation.mutate(
      { note: note.trim() },
      {
        onSuccess: () => {
          toast(t("signal.dismissed_toast"));
          onClose();
        },
        onError: (err) => setFormError(err instanceof ApiError && err.code === "SIGNAL_ALREADY_HANDLED" ? t("err.SIGNAL_ALREADY_HANDLED") : err instanceof ApiError ? err.message : t("err.INTERNAL")),
      },
    );
  }
  return (
    <CaseSheetShell
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title={t("signal.dismiss_heading")}
      lead={t("signal.dismiss_body")}
      initialFocus={() => noteRef.current}
      returnFocus={returnFocus}
      busy={mutation.isPending}
      footer={<SheetButtons form={`${ids}-form`} busy={mutation.isPending} submitLabel={t("signal.dismiss_submit")} onCancel={onClose} />}
    >
      <form id={`${ids}-form`} onSubmit={submit} noValidate className="flex flex-col gap-4">
        <NoteField
          ref={noteRef}
          id={`${ids}-note`}
          label={t("signal.dismiss_note_label")}
          value={note}
          onChange={(v) => {
            setNote(v);
            if (v.trim()) setError(undefined);
          }}
          error={error}
          disabled={mutation.isPending}
        />
        <div aria-live="polite">
          {formError && (
            <p role="alert" className="rounded-md border border-check-fail/30 bg-paper px-3 py-2 text-sm">
              {formError}
            </p>
          )}
        </div>
      </form>
    </CaseSheetShell>
  );
}
