"use client";

import * as React from "react";
import { toast } from "sonner";
import { ApiError } from "@/lib/api";
import { t, tk, type CopyId } from "@/lib/copy";
import { formatCardDate } from "@/lib/format";
import { useCaseAction } from "@/lib/queries-cases";
import type { CaseActionResult, DocsKind, EscalateReason, FlagDetail, OfficerAction } from "@/lib/types";
import { errorMessage } from "@/components/common/query-state";
import { useMe } from "@/components/providers/root-provider";
import { AssigneeCombobox, type AssigneePick } from "@/components/cases/assignee-combobox";
import { ACTION_WORD, DOCS_KINDS, noteLabel, reasonWord, reasonsFor } from "@/components/cases/case-words";
import { ChangesList, CaseSheetShell, FieldSelect, NoteField, SheetButtons } from "@/components/cases/sheet-shell";

/** The sheets of the actions that are not decisions (W3-8 with the W4-5 words). */
export type RecordAction = Exclude<OfficerAction, "UPHOLD" | "CORRECT" | "WITHDRAW">;

const SUBMIT: Record<RecordAction, CopyId> = {
  REQUEST_DOCS: "case.request_docs_send",
  ESCALATE: "case.escalate",
  NOTE: "case.note",
  ASSIGN: "case.assign",
  REOPEN: "case.reopen",
};

/** The question each sheet asks above its note, where the deck has one. */
const PROMPT: Partial<Record<RecordAction, CopyId>> = {
  REQUEST_DOCS: "case.request_docs_prompt",
  ESCALATE: "case.escalate_prompt",
  REOPEN: "case.reopen_prompt",
};

/** Today in IST as YYYY-MM-DD, the earliest reply date an officer may set. */
function todayIst(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}

function plusDays(date: string, n: number): string {
  const d = new Date(`${date}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

function toastFor(action: RecordAction, flag: FlagDetail): string {
  switch (action) {
    case "REQUEST_DOCS":
      return t("case.docs_toast");
    case "ESCALATE":
      return t("case.escalated_toast");
    case "REOPEN":
      return t("case.reopened_toast");
    case "NOTE":
      return t("case.note_toast");
    case "ASSIGN":
      return flag.assignee ? t("case.assigned_toast", { name: flag.assignee.name }) : t("case.unassigned_toast");
  }
}

type FieldErrors = Partial<Record<"note" | "due_date" | "assignee_id" | "docs_kind" | "reason", string>>;

/**
 * Request documents, Escalate, Add note, Assign and Reopen, each as a modal
 * sheet labelled by its title: focus on the first field, Tab kept inside,
 * Esc and Cancel close it and the caller puts focus back on the button that
 * opened it. Request documents and Escalate say what will change before the
 * officer sends; an empty field is caught here and nothing is sent.
 */
export function CaseSheet({
  flag,
  action,
  onClose,
  onDone,
  returnFocus,
}: {
  flag: FlagDetail;
  action: RecordAction | null;
  onClose: () => void;
  /** Runs after a successful action; the caller closes the sheet. */
  onDone: (flag: CaseActionResult) => void;
  /** Puts focus back on the opening button, or somewhere sensible when the action removed it. */
  returnFocus: () => void;
}) {
  const mutation = useCaseAction(flag.id);
  const { user } = useMe();
  const [note, setNote] = React.useState("");
  const [due, setDue] = React.useState("");
  const [kind, setKind] = React.useState<DocsKind | "">("");
  const [reason, setReason] = React.useState<EscalateReason | "">("");
  const [pick, setPick] = React.useState<AssigneePick | undefined>(undefined);
  const [errors, setErrors] = React.useState<FieldErrors>({});
  const [formError, setFormError] = React.useState<string | null>(null);
  const noteRef = React.useRef<HTMLTextAreaElement>(null);
  const dueRef = React.useRef<HTMLInputElement>(null);
  const kindRef = React.useRef<HTMLSelectElement>(null);
  const reasonRef = React.useRef<HTMLSelectElement>(null);
  const comboRef = React.useRef<HTMLInputElement>(null);
  const ids = React.useId();

  const [shown, setShown] = React.useState<RecordAction | null>(action);
  if (action !== shown) {
    // A new sheet starts empty.
    setShown(action);
    if (action) {
      setNote("");
      setDue("");
      setKind("");
      setReason("");
      setPick(undefined);
      setErrors({});
      setFormError(null);
    }
  }

  const today = todayIst();
  const latest = plusDays(today, 90);

  function focusFirst(fields: FieldErrors) {
    if (fields.docs_kind) kindRef.current?.focus();
    else if (fields.reason) reasonRef.current?.focus();
    else if (fields.note) noteRef.current?.focus();
    else if (fields.due_date) dueRef.current?.focus();
    else if (fields.assignee_id) comboRef.current?.focus();
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!action || mutation.isPending) return;
    const local: FieldErrors = {};
    if (action === "REQUEST_DOCS" && !kind) local.docs_kind = t("case.docs_kind_required");
    if (action === "ESCALATE" && !reason) local.reason = t("case.reason_required");
    if (action !== "ASSIGN" && !note.trim()) local.note = t("case.note_required");
    if (action === "REQUEST_DOCS" && due) {
      if (due < today) local.due_date = t("case.due_date_past");
      else if (due > latest) local.due_date = t("case.due_date_far");
    }
    setErrors(local);
    setFormError(null);
    if (Object.keys(local).length > 0) {
      focusFirst(local);
      return;
    }
    if (action === "ASSIGN" && pick === undefined) return;
    mutation.mutate(
      {
        action,
        note: action === "ASSIGN" ? undefined : note.trim(),
        due_date: action === "REQUEST_DOCS" ? due || null : undefined,
        docs_kind: action === "REQUEST_DOCS" ? (kind as DocsKind) : undefined,
        reason_code: action === "ESCALATE" ? (reason as EscalateReason) : undefined,
        assignee_id: action === "ASSIGN" ? (pick?.id ?? null) : undefined,
      },
      {
        onSuccess: (updated) => {
          toast(toastFor(action, updated));
          onDone(updated);
        },
        onError: (err) => {
          if (err instanceof ApiError && err.code === "VALIDATION_ERROR" && err.fields.length > 0) {
            const fields: FieldErrors = {};
            for (const f of err.fields) {
              if (f.field === "note" || f.field === "due_date" || f.field === "assignee_id" || f.field === "docs_kind") fields[f.field] = f.message;
              if (f.field === "reason_code") fields.reason = f.message;
            }
            if (Object.keys(fields).length > 0) {
              setErrors(fields);
              focusFirst(fields);
              return;
            }
          }
          if (err instanceof ApiError && err.code === "REASON_REQUIRED") {
            setFormError(t("err.REASON_REQUIRED"));
            return;
          }
          setFormError(err instanceof ApiError && err.code === "FLAG_TRANSITION_INVALID" ? t("err.FLAG_TRANSITION_INVALID") : errorMessage(err, user?.role, "flag"));
        },
      },
    );
  }

  const prompt = action ? PROMPT[action] : undefined;
  const formId = `${ids}-form`;
  const busy = mutation.isPending;

  let changes: string[] = [];
  if (action === "ESCALATE") changes = [t("case.escalate_change")];
  if (action === "REQUEST_DOCS") {
    const words = kind ? tk(`docs_kind.${kind}.words`) : tk("docs_kind.OTHER.words");
    changes = [due ? t("case.request_docs_change", { docs_words: words, due_date: formatCardDate(due) }) : t("case.request_docs_change_no_date", { docs_words: words })];
  }

  const lead =
    action === "REQUEST_DOCS"
      ? t("case.request_docs_email", { institution_name: flag.institution.name })
      : action === "ESCALATE"
        ? t("case.escalate_note")
        : undefined;

  return (
    <CaseSheetShell
      open={action !== null}
      onOpenChange={(o) => !o && onClose()}
      title={action ? t(ACTION_WORD[action]) : ""}
      lead={lead}
      initialFocus={() => (action === "ASSIGN" ? comboRef.current : action === "REQUEST_DOCS" ? kindRef.current : action === "ESCALATE" ? reasonRef.current : noteRef.current)}
      returnFocus={returnFocus}
      busy={busy}
      footer={
        action ? (
          <SheetButtons form={formId} busy={busy} disabled={action === "ASSIGN" && pick === undefined} submitLabel={t(SUBMIT[action])} onCancel={onClose} />
        ) : null
      }
    >
      {action && (
        <form id={formId} onSubmit={submit} noValidate className="flex min-w-0 flex-col gap-5">
          {action === "REQUEST_DOCS" && (
            <FieldSelect
              ref={kindRef}
              id={`${ids}-kind`}
              label={t("case.docs_kind_label")}
              value={kind}
              onChange={(v) => {
                setKind(v as DocsKind);
                setErrors((x) => ({ ...x, docs_kind: undefined }));
              }}
              placeholder={t("case.docs_kind_placeholder")}
              options={DOCS_KINDS.map((k) => ({ value: k, label: tk(`docs_kind.${k}`) }))}
              error={errors.docs_kind}
              disabled={busy}
            />
          )}
          {action === "ESCALATE" && (
            <FieldSelect
              ref={reasonRef}
              id={`${ids}-reason`}
              label={t("case.reason_label")}
              value={reason}
              onChange={(v) => {
                setReason(v as EscalateReason);
                setErrors((x) => ({ ...x, reason: undefined }));
              }}
              placeholder={t("case.reason_placeholder")}
              options={reasonsFor("ESCALATE", flag.type).map((code) => ({ value: code, label: reasonWord("ESCALATE", code) }))}
              error={errors.reason}
              disabled={busy}
            />
          )}

          {action === "ASSIGN" ? (
            <AssigneeCombobox ref={comboRef} flagId={flag.id} value={pick} onChange={setPick} error={errors.assignee_id} />
          ) : (
            <NoteField
              ref={noteRef}
              id={`${ids}-note`}
              label={noteLabel(action)}
              prompt={prompt ? t(prompt) : undefined}
              value={note}
              onChange={(v) => {
                setNote(v);
                if (errors.note && v.trim()) setErrors({ ...errors, note: undefined });
              }}
              error={errors.note}
              disabled={busy}
            />
          )}

          {action === "REQUEST_DOCS" && (
            <div className="flex flex-col gap-1.5">
              <label htmlFor={`${ids}-due`} className="text-sm font-medium">
                {t("case.due_date")}
              </label>
              <p id={`${ids}-due-hint`} className="text-sm text-ink-muted">
                {t("case.due_date_hint")}
              </p>
              <input
                ref={dueRef}
                id={`${ids}-due`}
                type="date"
                min={today}
                max={latest}
                value={due}
                onChange={(e) => setDue(e.target.value)}
                aria-invalid={errors.due_date ? true : undefined}
                aria-describedby={[`${ids}-due-hint`, errors.due_date ? `${ids}-due-error` : null].filter(Boolean).join(" ")}
                disabled={busy}
                className="h-11 w-full max-w-56 rounded-md border border-line bg-paper px-2.5 text-md aria-invalid:border-check-fail md:h-9 md:text-sm"
              />
              {errors.due_date && (
                <p id={`${ids}-due-error`} className="text-sm text-check-fail-ink">
                  {errors.due_date}
                </p>
              )}
            </div>
          )}

          {changes.length > 0 && <ChangesList lines={changes} loading={false} failed={false} />}

          <div aria-live="polite">
            {formError && (
              <p role="alert" className="rounded-md border border-check-fail/30 bg-paper px-3 py-2 text-sm text-ink">
                {formError}
              </p>
            )}
          </div>
        </form>
      )}
    </CaseSheetShell>
  );
}
