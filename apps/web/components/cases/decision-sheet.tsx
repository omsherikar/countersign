"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError } from "@/lib/api";
import { statusWord } from "@/lib/checks";
import { t, tk } from "@/lib/copy";
import { formatDate } from "@/lib/format";
import { keys } from "@/lib/queries";
import { useCaseAction, useDecisionPreview } from "@/lib/queries-cases";
import type {
  AdmissionRoute,
  CaseActionRequest,
  CaseActionResult,
  Category,
  CorrectableField,
  DecisionEffects,
  EnrolmentDetail,
  FlagDetail,
  ReasonCode,
  RecordStatus,
  RelatedEnrolmentRow,
  SeatType,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { errorMessage } from "@/components/common/query-state";
import { useMe } from "@/components/providers/root-provider";
import { RecordStatusBadge } from "@/components/records/record-status-badge";
import {
  CORRECTABLE,
  ELIGIBILITY_FIELDS,
  SEAT_FIELDS,
  fieldWord,
  reasonWord,
  reasonsFor,
  seatCodes,
  valueWord,
  type Decision,
} from "@/components/cases/case-words";
import { ChangesList, CaseSheetShell, FieldSelect, NoteField, SheetButtons } from "@/components/cases/sheet-shell";

const ROUTES: AdmissionRoute[] = ["COUNSELLING", "MANAGEMENT", "NRI", "SPOT", "LATERAL", "INTERNATIONAL", "TFW"];
const CATEGORIES: Category[] = ["GENERAL", "EWS", "OBC", "SC", "ST", "OTHER"];
const POOL_OF: Record<AdmissionRoute, SeatType> = {
  COUNSELLING: "REGULAR",
  MANAGEMENT: "REGULAR",
  SPOT: "REGULAR",
  NRI: "NRI",
  TFW: "TFW",
  LATERAL: "LATERAL",
  INTERNATIONAL: "INTERNATIONAL",
};

const HEADING: Record<Decision, "case.uphold_heading" | "case.correct_heading" | "case.withdraw_heading"> = {
  UPHOLD: "case.uphold_heading",
  CORRECT: "case.correct_heading",
  WITHDRAW: "case.withdraw_heading",
};

/** "1 records" to "1 record" in the toasts and lines the deck counts. */
function one(text: string): string {
  return text.replace(/(^|[^\d,.])1 (records|seats|attestations|enrolment attestations)\b/g, (_m, pre: string, noun: string) => `${pre}1 ${noun.replace(/s$/, "")}`);
}

function todayIst(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}

/** The value as the API wants it: numbers for the year, booleans or null for the eligibility markers. */
function parseValue(field: CorrectableField, raw: string): string | number | boolean | null {
  if (field === "year_of_study") return Number(raw);
  if (ELIGIBILITY_FIELDS.includes(field)) return raw === "true" ? true : raw === "false" ? false : null;
  return raw.trim();
}

function nowValue(d: EnrolmentDetail | undefined, field: CorrectableField): unknown {
  if (!d) return undefined;
  switch (field) {
    case "name":
      return d.student.name;
    case "dob":
      return d.student.dob;
    case "tfw_income_certified":
    case "nri_sponsored":
    case "ciwg":
      return d.eligibility[field];
    default:
      return d[field];
  }
}

function sameValue(field: CorrectableField, a: unknown, b: unknown): boolean {
  if (ELIGIBILITY_FIELDS.includes(field)) return (a ?? null) === (b ?? null);
  return String(a ?? "").trim().toLowerCase() === String(b ?? "").trim().toLowerCase();
}

/** Keeps a value steady until it has stopped changing for `ms` (the preview waits 300 ms, W4-5). */
function useSettled<T>(value: T, ms: number): T {
  const key = JSON.stringify(value);
  const latest = React.useRef(value);
  React.useEffect(() => {
    latest.current = value;
  });
  const [settled, setSettled] = React.useState<{ key: string; value: T }>({ key, value });
  React.useEffect(() => {
    if (key === settled.key) return;
    const id = setTimeout(() => setSettled({ key, value: latest.current }), ms);
    return () => clearTimeout(id);
  }, [key, ms, settled.key]);
  return settled.value;
}

type FieldRow = { field: CorrectableField | ""; value: string };
type Errors = Partial<Record<"reason" | "note" | "ack" | "picked" | "fields" | "record", string>> & { fieldAt?: Record<number, string> };

/**
 * The three decisions (page spec W4-5): Uphold claim, Correct record and
 * Withdraw claim. Each asks for a reason and a note, then lists every
 * consequence with its real values from the api's dry run before the
 * officer can submit. A programme-level case adds the record picker
 * (Withdraw), the record select (Correct) or the approval version (Uphold).
 */
export function DecisionSheet({
  flag,
  action,
  onClose,
  onDone,
  returnFocus,
}: {
  flag: FlagDetail;
  action: Decision | null;
  onClose: () => void;
  onDone: (result: CaseActionResult) => void;
  returnFocus: () => void;
}) {
  const ids = React.useId();
  const { user } = useMe();
  const mutation = useCaseAction(flag.id);
  const reasonRef = React.useRef<HTMLSelectElement>(null);
  const noteRef = React.useRef<HTMLTextAreaElement>(null);
  const ackRef = React.useRef<HTMLInputElement>(null);
  const pickRef = React.useRef<HTMLFieldSetElement>(null);
  const fieldsRef = React.useRef<HTMLDivElement>(null);

  const [reason, setReason] = React.useState<ReasonCode | "">("");
  const [note, setNote] = React.useState("");
  const [ack, setAck] = React.useState(false);
  const [picked, setPicked] = React.useState<string[]>([]);
  const [record, setRecord] = React.useState("");
  const [rows, setRows] = React.useState<FieldRow[]>([{ field: "", value: "" }]);
  const [errors, setErrors] = React.useState<Errors>({});
  const [formError, setFormError] = React.useState<string | null>(null);

  const [shown, setShown] = React.useState<Decision | null>(action);
  if (action !== shown) {
    // Each opening starts with an empty form.
    setShown(action);
    if (action) {
      setReason("");
      setNote("");
      setAck(false);
      setPicked([]);
      setRecord("");
      setRows([{ field: "", value: "" }]);
      setErrors({});
      setFormError(null);
    }
  }

  // A multi-record case names several records; a record case without its own record (a duplicate) names one of its related records.
  const multi = flag.scope === "MULTI_RECORD" || (flag.scope === "RECORD" && !flag.enrolment_id);
  const all = React.useMemo(() => {
    const list = [flag.enrolment, ...flag.related_enrolments].filter((r): r is RelatedEnrolmentRow => Boolean(r));
    return list.filter((r, i) => list.findIndex((x) => x.id === r.id) === i);
  }, [flag.enrolment, flag.related_enrolments]);
  const named =
    flag.scope === "MULTI_RECORD"
      ? all.filter((r) => flag.outstanding_enrolment_ids.includes(r.id))
      : flag.enrolment_id
        ? all.filter((r) => r.id === flag.enrolment_id)
        : all.filter((r) => r.institution.id === flag.institution.id && r.status === "ACTIVE");
  const seatCase = flag.type === "EXCESS_ADMISSION" || flag.type === "QUOTA_BREACH";
  const versionMissing = action === "UPHOLD" && seatCase && !flag.approval?.covers;
  const target = action === "CORRECT" ? (multi ? record : (flag.enrolment_id ?? "")) : "";

  const detail = useQuery({
    queryKey: keys.enrolment(target),
    queryFn: () => api.get<EnrolmentDetail>(`/enrolments/${target}`),
    enabled: action === "CORRECT" && Boolean(target),
  });

  const changes = React.useMemo(() => {
    const out: Partial<Record<CorrectableField, string | number | boolean | null>> = {};
    for (const r of rows) {
      if (!r.field || r.value === "") continue;
      if (sameValue(r.field, nowValue(detail.data, r.field), parseValue(r.field, r.value))) continue;
      out[r.field] = parseValue(r.field, r.value);
    }
    return out;
  }, [rows, detail.data]);

  /** The body the officer would send, with stand-ins for the reason and note so the dry run can answer before they are written. */
  const draft = React.useMemo((): CaseActionRequest | null => {
    if (!action) return null;
    const base = { action, reason_code: (reason || undefined) as ReasonCode, note: note.trim() };
    if (action === "UPHOLD") {
      if (versionMissing) return null;
      return seatCase && flag.approval ? { ...base, approval_version: flag.approval.current_version } : base;
    }
    if (action === "WITHDRAW") {
      const chosen = multi ? picked : flag.enrolment_id ? [flag.enrolment_id] : [];
      if (chosen.length === 0) return null;
      return { ...base, withdrawn_enrolment_ids: chosen };
    }
    if (!target || Object.keys(changes).length === 0) return null;
    return { ...base, correction: { enrolment_id: target, fields: changes } };
  }, [action, reason, note, flag, versionMissing, seatCase, multi, picked, target, changes]);

  /** The consequences never depend on the reason or the note, so the preview sends stand-ins for them and waits only on the rest. */
  const shape = draft ? { ...draft, reason_code: undefined, note: undefined } : null;
  const settled = useSettled(shape, 300);
  const placeholder: ReasonCode = flag.type === "MISSING_FROM_UPLOAD" ? "MISSING_NOW_UPLOADED" : "OTHER";
  const previewBody = React.useMemo(() => (settled ? ({ ...settled, reason_code: placeholder, note: "-" } as CaseActionRequest) : null), [settled, placeholder]);
  const preview = useDecisionPreview(flag.id, previewBody);
  const waiting = draft !== null && (JSON.stringify(shape) !== JSON.stringify(settled) || preview.isFetching);
  const previewFailed = draft !== null && !waiting && preview.isError;
  const effects = draft !== null && !waiting ? preview.data : undefined;

  if (!action) return <CaseSheetShell open={false} onOpenChange={() => onClose()} title="" footer={null} returnFocus={returnFocus}>{null}</CaseSheetShell>;

  const reasons = reasonsFor(action, flag.type);
  const institution = flag.institution.name;
  const dispute = flag.type === "STUDENT_DENIED";

  /* ---- What will change --------------------------------------------------- */
  let lines: React.ReactNode[] = [];
  let empty: string | null = null;
  if (versionMissing) empty = t("case.uphold_version_none");
  else if (action === "WITHDRAW" && multi && picked.length === 0) empty = t("err.WITHDRAW_NONE_SELECTED");
  else if (action === "CORRECT" && (!target || Object.keys(changes).length === 0)) empty = t("err.CORRECTION_EMPTY");
  if (effects) lines = linesFor(action, effects, flag, detail.data, changes);

  /* ---- Submit -------------------------------------------------------------- */
  const pickedCount = multi ? picked.length : 1;
  const submitLabel =
    action === "UPHOLD"
      ? t("case.uphold_submit")
      : action === "CORRECT"
        ? t("case.correct_submit")
        : multi && pickedCount > 1
          ? t("case.withdraw_submit_many", { n: pickedCount })
          : t("case.withdraw_submit");
  const blocked = versionMissing || (draft !== null && (waiting || previewFailed || !effects));

  function focusFirst(e: Errors) {
    if (e.record) document.getElementById(`${ids}-record`)?.focus();
    else if (e.reason) reasonRef.current?.focus();
    else if (e.note) noteRef.current?.focus();
    else if (e.picked) pickRef.current?.querySelector<HTMLInputElement>("input")?.focus();
    else if (e.fields || e.fieldAt) fieldsRef.current?.querySelector<HTMLElement>("select, input")?.focus();
    else if (e.ack) ackRef.current?.focus();
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!action || mutation.isPending || blocked) return;
    const local: Errors = {};
    if (action === "CORRECT" && multi && !record) local.record = t("case.correct_record_required");
    if (!reason) local.reason = t("case.reason_required");
    if (!note.trim()) local.note = t("case.note_required");
    if (action === "WITHDRAW" && multi && picked.length === 0) local.picked = t("err.WITHDRAW_NONE_SELECTED");
    if (action === "CORRECT" && Object.keys(changes).length === 0) local.fields = t("err.CORRECTION_EMPTY");
    if (action === "WITHDRAW" && !ack) local.ack = t("case.withdraw_ack_required");
    setErrors(local);
    setFormError(null);
    if (Object.keys(local).length > 0) {
      focusFirst(local);
      return;
    }
    const body: CaseActionRequest = { ...draft!, reason_code: reason as ReasonCode, note: note.trim() };
    mutation.mutate(body, {
      onSuccess: (result) => {
        toast(toastFor(action, result));
        onDone(result);
      },
      onError: (err) => {
        if (!(err instanceof ApiError)) {
          setFormError(t("err.INTERNAL"));
          return;
        }
        const next: Errors = {};
        switch (err.code) {
          case "REASON_REQUIRED":
            if (!reason) next.reason = t("case.reason_required");
            if (!note.trim()) next.note = t("case.note_required");
            setFormError(t("err.REASON_REQUIRED"));
            break;
          case "CORRECTION_EMPTY":
            next.fields = t("err.CORRECTION_EMPTY");
            break;
          case "CORRECTION_INVALID": {
            const field = String(err.details.field ?? "");
            const at = rows.findIndex((r) => r.field === field);
            if (at >= 0) next.fieldAt = { [at]: err.message };
            else next.fields = err.message;
            break;
          }
          case "WITHDRAW_NONE_SELECTED":
            next.picked = t("err.WITHDRAW_NONE_SELECTED");
            break;
          case "WITHDRAW_NOT_NAMED":
            setPicked([]);
            next.picked = one(t("err.WITHDRAW_NOT_NAMED", { n: Number(err.details.n ?? 1) }));
            break;
          case "UPHOLD_NEEDS_VERSION":
            setFormError(t("err.UPHOLD_NEEDS_VERSION"));
            break;
          case "DECISION_NOT_AVAILABLE":
            setFormError(t("err.DECISION_NOT_AVAILABLE", { case_name: tk(`flag.${flag.type}.name`) }));
            break;
          case "FLAG_TRANSITION_INVALID":
            setFormError(t("err.FLAG_TRANSITION_INVALID"));
            break;
          case "VALIDATION_ERROR":
            for (const f of err.fields) {
              if (f.field === "note") next.note = f.message;
              else if (f.field === "reason_code") next.reason = f.message;
            }
            if (Object.keys(next).length === 0) setFormError(err.message);
            break;
          default:
            setFormError(errorMessage(err, user?.role, "flag"));
        }
        setErrors(next);
        focusFirst(next);
      },
    });
  }

  const formId = `${ids}-form`;
  const busy = mutation.isPending;
  return (
    <CaseSheetShell
      open
      onOpenChange={(o) => !o && onClose()}
      title={t(HEADING[action])}
      lead={action === "WITHDRAW" && flag.scope === "MULTI_RECORD" ? t("case.withdraw_lead_programme") : t(action === "UPHOLD" ? "case.uphold_lead" : action === "CORRECT" ? "case.correct_lead" : "case.withdraw_lead")}
      initialFocus={() => (action === "CORRECT" && multi ? document.getElementById(`${ids}-record`) : reasonRef.current)}
      returnFocus={returnFocus}
      busy={busy}
      wide={action === "CORRECT" || (action === "WITHDRAW" && multi)}
      footer={
        <SheetButtons
          form={formId}
          busy={busy}
          disabled={blocked}
          submitLabel={draft !== null && waiting ? t("case.changes_loading") : submitLabel}
          onCancel={onClose}
        />
      }
    >
      <form id={formId} onSubmit={submit} noValidate className="flex min-w-0 flex-col gap-5">
        {action === "CORRECT" && multi && (
          <FieldSelect
            id={`${ids}-record`}
            label={t("case.correct_record_label")}
            value={record}
            onChange={(v) => {
              setRecord(v);
              setRows([{ field: "", value: "" }]);
              setErrors((x) => ({ ...x, record: undefined }));
            }}
            placeholder={t("case.correct_record_placeholder")}
            options={named.map((r) => ({ value: r.id, label: `${r.student.name}, ${r.student.apaar_masked ?? r.student.provisional_id ?? ""}` }))}
            error={errors.record}
            disabled={busy}
          />
        )}

        {action === "WITHDRAW" && multi && (
          <RecordPicker
            ref={pickRef}
            records={named}
            picked={picked}
            onChange={(next) => {
              setPicked(next);
              setErrors((x) => ({ ...x, picked: undefined }));
            }}
            error={errors.picked}
            disabled={busy}
          />
        )}

        {action === "UPHOLD" && seatCase && (
          versionMissing ? null : flag.approval ? (
            <FieldSelect
              id={`${ids}-version`}
              label={t("case.uphold_version_label")}
              value={String(flag.approval.current_version)}
              onChange={() => {}}
              options={[{ value: String(flag.approval.current_version), label: t("case.uphold_version_option", { version: flag.approval.current_version, intake: flag.approval.approved_intake }) }]}
              disabled={busy}
            />
          ) : null
        )}

        {action === "CORRECT" && (
          <CorrectFields
            ref={fieldsRef}
            idBase={ids}
            rows={rows}
            setRows={(next) => {
              setRows(next);
              setErrors((x) => ({ ...x, fields: undefined, fieldAt: undefined }));
            }}
            detail={detail.data}
            loading={Boolean(target) && detail.isLoading}
            disabled={busy || !target}
            error={errors.fields}
            errorAt={errors.fieldAt}
          />
        )}

        <FieldSelect
          ref={reasonRef}
          id={`${ids}-reason`}
          label={t("case.reason_label")}
          value={reason}
          onChange={(v) => {
            setReason(v as ReasonCode);
            setErrors((x) => ({ ...x, reason: undefined }));
          }}
          placeholder={t("case.reason_placeholder")}
          options={reasons.map((code) => ({ value: code, label: reasonWord(action, code) }))}
          error={errors.reason}
          disabled={busy}
        />
        <NoteField
          ref={noteRef}
          id={`${ids}-note`}
          label={t("case.note_label")}
          value={note}
          onChange={(v) => {
            setNote(v);
            if (v.trim()) setErrors((x) => ({ ...x, note: undefined }));
          }}
          error={errors.note}
          disabled={busy}
        />

        <ChangesList lines={lines} loading={draft !== null && waiting} failed={previewFailed} empty={empty} />

        <div className="flex flex-col gap-1 text-sm text-ink-muted">
          <p>{t("case.who_sees", { institution_name: institution })}</p>
          {dispute && <p>{t("case.who_sees_student")}</p>}
        </div>

        {action === "WITHDRAW" && (
          <div className="flex flex-col gap-1">
            <label className="flex min-h-11 items-start gap-3 text-md md:min-h-0 md:text-sm">
              <input
                ref={ackRef}
                type="checkbox"
                checked={ack}
                onChange={(e) => {
                  setAck(e.target.checked);
                  if (e.target.checked) setErrors((x) => ({ ...x, ack: undefined }));
                }}
                aria-invalid={errors.ack ? true : undefined}
                aria-describedby={errors.ack ? `${ids}-ack-error` : undefined}
                disabled={busy}
                className="mt-0.5 size-5 shrink-0 accent-[var(--ink-blue)] md:size-4"
              />
              <span>{t("case.withdraw_ack")}</span>
            </label>
            {errors.ack && (
              <p id={`${ids}-ack-error`} className="text-sm text-check-fail-ink">
                {errors.ack}
              </p>
            )}
          </div>
        )}

        <div aria-live="polite">
          {formError && (
            <p role="alert" className="rounded-md border border-check-fail/30 bg-paper px-3 py-2 text-sm text-ink">
              {formError}
            </p>
          )}
        </div>
      </form>
    </CaseSheetShell>
  );
}

/* ---- The consequences, one sentence each ---------------------------------- */

function linesFor(
  action: Decision,
  effects: DecisionEffects,
  flag: FlagDetail,
  detail: EnrolmentDetail | undefined,
  changes: Partial<Record<CorrectableField, unknown>>,
): React.ReactNode[] {
  const lines: React.ReactNode[] = [];
  if (action === "UPHOLD") {
    if (effects.case_status === "UPHELD") lines.push(t("case.uphold_change.case"));
    if (effects.rows_resolved > 0) lines.push(t("case.uphold_change.row", { today: formatDate(todayIst()) }));
    lines.push(t("case.uphold_change.status"));
    lines.push(t("case.uphold_change.not_evidence"));
    if (effects.approval) {
      lines.push(
        t("case.uphold_change.version", {
          version: effects.approval.version,
          programme_code: effects.approval.programme_code,
          cohort_year: effects.approval.cohort_year,
          intake: effects.approval.approved_intake,
        }),
      );
    } else {
      lines.push(t("case.uphold_change.seat"));
    }
    if (effects.attestations_issued.length > 0 && flag.type === "STUDENT_DENIED") lines.push(t("case.uphold_change.attestation"));
    return lines;
  }
  if (action === "CORRECT") {
    const changed = effects.changes.length > 0 ? effects.changes : Object.entries(changes).map(([field, after]) => ({ field, before: null, after }));
    lines.push(
      <>
        {t("case.correct_change.version", { version: effects.version ?? "" })}
        <ul className="mt-1 flex list-[circle] flex-col gap-0.5 pl-5">
          {changed.map((c) => (
            <li key={c.field}>{t("case.correct_change.line", { field_word: fieldWord(c.field), before: valueWord(c.field, c.before), after: valueWord(c.field, c.after) })}</li>
          ))}
        </ul>
      </>,
    );
    lines.push(t("case.correct_change.rerun"));
    const movesSeat = changed.some((c) => SEAT_FIELDS.includes(c.field));
    const released = effects.seats_released[0];
    const assigned = effects.seats_assigned[0];
    if (movesSeat || released || assigned) {
      const route = (changes.admission_route as AdmissionRoute | undefined) ?? detail?.admission_route ?? null;
      const programme = detail?.programme.code ?? flag.programme?.code ?? "";
      if (released) {
        lines.push(
          t("case.correct_change.seat", {
            seat_code: released.seat_code,
            seat_type_word: route ? tk(`seat_type.${POOL_OF[route]}`) : "",
            programme_code: programme,
          }),
        );
      } else if (assigned) {
        lines.push(t("case.correct_change.seat_assigned", { seat_code: assigned.seat_code }));
      }
    }
    if (effects.case_status === "CORRECTED") lines.push(t("case.correct_change.case"));
    lines.push(t("case.correct_change.status"));
    return lines;
  }
  const withdrawn = effects.records.filter((r) => r.status === "WITHDRAWN").length || 1;
  lines.push(withdrawn === 1 ? t("case.withdraw_change.status") : t("case.withdraw_change.status_many", { n: withdrawn }));
  const seats = effects.seats_released.map((s) => s.seat_code);
  if (seats.length === 0) lines.push(t("case.withdraw_change.no_seat"));
  else if (seats.length === 1) lines.push(t("case.withdraw_change.seat", { seat_code: seats[0] }));
  else lines.push(t("case.withdraw_change.seats", { n: seats.length, seat_codes: seatCodes(seats) }));
  const revoked = effects.attestations_revoked;
  if (revoked.length === 0) lines.push(t("case.withdraw_change.no_attestation"));
  else if (revoked.length === 1) lines.push(t("case.withdraw_change.attestation", { short_id: revoked[0].short_id }));
  else lines.push(t("case.withdraw_change.attestations", { n: revoked.length }));
  lines.push(t("case.withdraw_change.kept"));
  if (effects.case_status === "WITHDRAWN") lines.push(t("case.withdraw_change.case"));
  if (flag.type === "STUDENT_DENIED") lines.push(t("case.withdraw_change.student"));
  return lines;
}

function recordWord(status: RecordStatus | null | undefined): string {
  return status ? statusWord(status) : t("enrol_status.WITHDRAWN");
}

function toastFor(action: Decision, result: CaseActionResult): string {
  const e = result.effects;
  const after = e.records.find((r) => r.enrolment_id === result.enrolment_id)?.record_status ?? result.enrolment?.record_status ?? null;
  if (action === "UPHOLD") {
    if (e.approval) return one(t("case.upheld_toast_programme", { version: e.approval.version, seated: e.seats_assigned.length }));
    return t("case.upheld_toast", { status_word: recordWord(after) });
  }
  if (action === "CORRECT") {
    const corrected = e.records[0]?.record_status ?? after;
    return t("case.corrected_toast", { version: e.version ?? "", status_word: recordWord(corrected) });
  }
  return one(
    t("case.withdrawn_toast", {
      records: e.records.filter((r) => r.status === "WITHDRAWN").length,
      seats: e.seats_released.length,
      attestations: e.attestations_revoked.length,
    }),
  );
}

/* ---- Withdraw: the record picker ------------------------------------------ */

const RecordPicker = React.forwardRef<
  HTMLFieldSetElement,
  { records: RelatedEnrolmentRow[]; picked: string[]; onChange: (ids: string[]) => void; error?: string; disabled?: boolean }
>(function RecordPicker({ records, picked, onChange, error, disabled }, ref) {
  const id = React.useId();
  const allOn = records.length > 0 && picked.length === records.length;
  const toggle = (rid: string, on: boolean) => onChange(on ? [...picked, rid] : picked.filter((x) => x !== rid));
  return (
    <fieldset ref={ref} className="min-w-0" aria-describedby={[`${id}-hint`, error ? `${id}-error` : null].filter(Boolean).join(" ")}>
      <legend className="text-sm font-medium">{t("case.withdraw_pick_label")}</legend>
      <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
        <p id={`${id}-hint`} className="text-sm text-ink-muted">
          {t("case.withdraw_pick_hint")}
        </p>
        <p className="text-sm text-ink-muted" aria-live="polite">
          {t("case.withdraw_pick_count", { n: picked.length, total: records.length })}
        </p>
      </div>
      <label className="mt-2 flex min-h-11 items-center gap-3 border-b border-rule pb-2 text-md font-medium md:min-h-9 md:text-sm">
        <input
          type="checkbox"
          checked={allOn}
          ref={(el) => {
            if (el) el.indeterminate = picked.length > 0 && !allOn;
          }}
          onChange={(e) => onChange(e.target.checked ? records.map((r) => r.id) : [])}
          disabled={disabled || records.length === 0}
          className="size-5 shrink-0 accent-[var(--ink-blue)] md:size-4"
        />
        {t("case.withdraw_pick_all", { n: records.length })}
      </label>
      <ul className="max-h-72 divide-y divide-rule overflow-y-auto">
        {records.map((r) => {
          const on = picked.includes(r.id);
          const masked = r.student.apaar_masked ?? r.student.provisional_id ?? "";
          return (
            <li key={r.id}>
              <label className={cn("flex min-h-14 items-center gap-3 py-2 md:min-h-11", on && "bg-flag-open-soft/40")}>
                <input
                  type="checkbox"
                  checked={on}
                  onChange={(e) => toggle(r.id, e.target.checked)}
                  disabled={disabled}
                  className="size-5 shrink-0 accent-[var(--ink-blue)] md:size-4"
                />
                <span className="flex min-w-0 flex-1 flex-col gap-0.5 sm:flex-row sm:items-center sm:gap-3">
                  <span className="min-w-0 truncate font-medium">{r.student.name}</span>
                  <span className="code text-xs text-ink-muted sm:w-32">{masked}</span>
                  <span className="code text-xs text-ink-muted sm:w-28">{r.seat_code ?? t("seat.unseated")}</span>
                </span>
                <RecordStatusBadge status={r.record_status} className="shrink-0" />
              </label>
            </li>
          );
        })}
      </ul>
      {error && (
        <p id={`${id}-error`} className="mt-1 text-sm text-check-fail-ink">
          {error}
        </p>
      )}
    </fieldset>
  );
});

/* ---- Correct: field, now, correct value ----------------------------------- */

const CorrectFields = React.forwardRef<
  HTMLDivElement,
  {
    idBase: string;
    rows: FieldRow[];
    setRows: (rows: FieldRow[]) => void;
    detail: EnrolmentDetail | undefined;
    loading: boolean;
    disabled: boolean;
    error?: string;
    errorAt?: Record<number, string>;
  }
>(function CorrectFields({ idBase, rows, setRows, detail, loading, disabled, error, errorAt }, ref) {
  const used = rows.map((r) => r.field).filter(Boolean);
  const duration = detail?.programme.duration_years ?? 5;
  const update = (i: number, patch: Partial<FieldRow>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  return (
    <div ref={ref} className="flex min-w-0 flex-col gap-3">
      {rows.map((row, i) => {
        const fid = `${idBase}-field-${i}`;
        const vid = `${idBase}-value-${i}`;
        const now = row.field ? nowValue(detail, row.field) : undefined;
        const equal = row.field && row.value !== "" && sameValue(row.field, now, parseValue(row.field, row.value));
        const rowError = errorAt?.[i] ?? (equal ? t("err.CORRECTION_EMPTY") : undefined);
        return (
          <div key={i} className="grid min-w-0 grid-cols-1 gap-2 border-b border-rule pb-3 sm:grid-cols-[minmax(0,10rem)_minmax(0,1fr)_minmax(0,12rem)] sm:items-end sm:gap-3">
            <FieldSelect
              id={fid}
              label={t("case.correct_field_label")}
              value={row.field}
              onChange={(v) => update(i, { field: v as CorrectableField, value: "" })}
              placeholder={t("case.correct_field_placeholder")}
              options={CORRECTABLE.filter((f) => f === row.field || !used.includes(f)).map((f) => ({ value: f, label: fieldWord(f) }))}
              disabled={disabled}
            />
            <div className="flex min-w-0 flex-col gap-1.5">
              <span className="text-sm font-medium">{t("case.correct_now")}</span>
              <span className="flex min-h-9 items-center text-md md:text-sm [overflow-wrap:anywhere]">
                {!row.field ? "" : loading ? <span className="h-3.5 w-24 animate-pulse rounded bg-paper-sunken" aria-hidden="true" /> : valueWord(row.field, now)}
              </span>
            </div>
            <div className="flex min-w-0 flex-col gap-1.5">
              <label htmlFor={vid} className="text-sm font-medium">
                {t("case.correct_new")}
              </label>
              <ValueInput
                id={vid}
                field={row.field}
                value={row.value}
                onChange={(v) => update(i, { value: v })}
                duration={duration}
                disabled={disabled || !row.field}
                invalid={Boolean(rowError)}
                describedBy={rowError ? `${vid}-error` : undefined}
              />
            </div>
            {rowError && (
              <p id={`${vid}-error`} className="text-sm text-check-fail-ink sm:col-span-3">
                {rowError}
              </p>
            )}
            {rows.length > 1 && (
              <button
                type="button"
                onClick={() => setRows(rows.filter((_, j) => j !== i))}
                disabled={disabled}
                className="inline-flex min-h-11 w-fit items-center text-sm text-ink-blue underline-offset-2 hover:underline sm:col-span-3 md:min-h-8"
              >
                {t("case.correct_remove", { field_word: row.field ? fieldWord(row.field) : t("case.correct_field_label") })}
              </button>
            )}
          </div>
        );
      })}
      {used.length < CORRECTABLE.length && (
        <button
          type="button"
          onClick={() => setRows([...rows, { field: "", value: "" }])}
          disabled={disabled}
          className="inline-flex min-h-11 w-fit items-center rounded-md border border-line px-3 text-sm font-medium hover:bg-paper-sunken disabled:opacity-60 md:min-h-9"
        >
          {t("case.correct_add")}
        </button>
      )}
      <p className="text-sm text-ink-muted">{t("case.correct_not_here")}</p>
      {error && <p className="text-sm text-check-fail-ink">{error}</p>}
    </div>
  );
});

function ValueInput({
  id,
  field,
  value,
  onChange,
  duration,
  disabled,
  invalid,
  describedBy,
}: {
  id: string;
  field: CorrectableField | "";
  value: string;
  onChange: (v: string) => void;
  duration: number;
  disabled: boolean;
  invalid: boolean;
  describedBy?: string;
}) {
  const cls = "h-11 w-full min-w-0 rounded-md border border-line bg-paper px-2.5 text-md aria-invalid:border-check-fail md:h-9 md:text-sm";
  const common = { id, disabled, "aria-invalid": invalid || undefined, "aria-describedby": describedBy, className: cls };
  const select = (options: { value: string; label: string }[]) => (
    <select {...common} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="" disabled>
        {t("case.correct_value_placeholder")}
      </option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
  if (field === "admission_route") return select(ROUTES.map((r) => ({ value: r, label: tk(`route.${r}`) })));
  if (field === "category") return select(CATEGORIES.map((c) => ({ value: c, label: tk(`category.${c}`) })));
  if (field === "year_of_study") return select(Array.from({ length: duration }, (_, i) => ({ value: String(i + 1), label: String(i + 1) })));
  if (field && ELIGIBILITY_FIELDS.includes(field)) {
    return select([
      { value: "true", label: t("case.correct_value.yes") },
      { value: "false", label: t("case.correct_value.no") },
      { value: "null", label: t("case.correct_value.unreported") },
    ]);
  }
  if (field === "dob" || field === "admission_date") {
    return <input {...common} type="date" max={field === "admission_date" ? todayIst() : undefined} value={value} onChange={(e) => onChange(e.target.value)} />;
  }
  return <input {...common} type="text" maxLength={field === "name" ? 120 : 40} value={value} onChange={(e) => onChange(e.target.value)} autoComplete="off" />;
}
