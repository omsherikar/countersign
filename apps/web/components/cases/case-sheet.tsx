"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { ApiError } from "@/lib/api";
import { t, type CopyId } from "@/lib/copy";
import { useCaseAction } from "@/lib/queries-cases";
import type { FlagDetail, OfficerAction } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { errorMessage } from "@/components/common/query-state";
import { useMe } from "@/components/providers/root-provider";
import { AssigneeCombobox, type AssigneePick } from "@/components/cases/assignee-combobox";
import { ACTION_WORD, noteLabel } from "@/components/cases/case-words";

const SUBMIT: Record<OfficerAction, CopyId> = { ...ACTION_WORD, REQUEST_DOCS: "case.request_docs_send" };

/** The question each sheet asks above its note, where the deck has one. */
const PROMPT: Partial<Record<OfficerAction, CopyId>> = {
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

function toastFor(action: OfficerAction, flag: FlagDetail): string {
  switch (action) {
    case "CLEAR":
      return t("case.cleared_toast", { institution_name: flag.institution.name });
    case "REQUEST_DOCS":
      return t("case.docs_toast");
    case "ESCALATE":
      return t("case.escalated_toast");
    case "CONFIRM":
      return t("case.confirmed_toast");
    case "REOPEN":
      return t("case.reopened_toast");
    case "NOTE":
      return t("case.note_toast");
    case "ASSIGN":
      return flag.assignee ? t("case.assigned_toast", { name: flag.assignee.name }) : t("case.unassigned_toast");
  }
}

type FieldErrors = Partial<Record<"note" | "due_date" | "assignee_id", string>>;

/**
 * One officer action as a modal sheet (page spec W3-8): labelled by its
 * title, focus on the note (or the officer list for Assign), Tab kept
 * inside, Esc and Cancel close it and the caller puts focus back on the
 * button that opened it. An empty note is caught here and nothing is sent.
 */
export function CaseSheet({
  flag,
  action,
  onClose,
  onDone,
  returnFocus,
}: {
  flag: FlagDetail;
  action: OfficerAction | null;
  onClose: () => void;
  /** Runs after a successful action; the caller closes the sheet. */
  onDone: (flag: FlagDetail) => void;
  /** Puts focus back on the opening button, or somewhere sensible when the action removed it. */
  returnFocus: () => void;
}) {
  const mutation = useCaseAction(flag.id);
  const { user } = useMe();
  const [note, setNote] = React.useState("");
  const [due, setDue] = React.useState("");
  const [pick, setPick] = React.useState<AssigneePick | undefined>(undefined);
  const [errors, setErrors] = React.useState<FieldErrors>({});
  const [formError, setFormError] = React.useState<string | null>(null);
  const noteRef = React.useRef<HTMLTextAreaElement>(null);
  const dueRef = React.useRef<HTMLInputElement>(null);
  const comboRef = React.useRef<HTMLInputElement>(null);
  const ids = React.useId();

  const [shown, setShown] = React.useState<OfficerAction | null>(action);
  if (action !== shown) {
    // A new sheet starts empty.
    setShown(action);
    if (action) {
      setNote("");
      setDue("");
      setPick(undefined);
      setErrors({});
      setFormError(null);
    }
  }

  const today = todayIst();
  const latest = plusDays(today, 90);

  function focusFirst(fields: FieldErrors) {
    if (fields.note) noteRef.current?.focus();
    else if (fields.due_date) dueRef.current?.focus();
    else if (fields.assignee_id) comboRef.current?.focus();
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!action || mutation.isPending) return;
    const local: FieldErrors = {};
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
            for (const f of err.fields) if (f.field === "note" || f.field === "due_date" || f.field === "assignee_id") fields[f.field] = f.message;
            if (Object.keys(fields).length > 0) {
              setErrors(fields);
              focusFirst(fields);
              return;
            }
          }
          setFormError(err instanceof ApiError && err.code === "FLAG_TRANSITION_INVALID" ? t("err.FLAG_TRANSITION_INVALID") : errorMessage(err, user?.role, "flag"));
        },
      },
    );
  }

  const open = action !== null;
  const prompt = action ? PROMPT[action] : undefined;
  const noteHint = `${ids}-note-hint`;
  const noteError = `${ids}-note-error`;
  const dueHint = `${ids}-due-hint`;
  const dueError = `${ids}-due-error`;

  return (
    <Dialog open={open} onOpenChange={(next) => !next && !mutation.isPending && onClose()}>
      <DialogContent
        className="max-h-[calc(100dvh-2rem)] gap-5 overflow-y-auto bg-paper-raised sm:max-w-lg"
        onOpenAutoFocus={(e) => {
          e.preventDefault();
          (action === "ASSIGN" ? comboRef.current : noteRef.current)?.focus();
        }}
        onCloseAutoFocus={(e) => {
          e.preventDefault();
          returnFocus();
        }}
      >
        {action && (
          <form onSubmit={submit} noValidate className="flex flex-col gap-5">
            <div className="flex flex-col gap-2 pr-6">
              <DialogTitle className="font-display text-xl font-semibold">{t(ACTION_WORD[action])}</DialogTitle>
              <DialogDescription asChild>
                <div className="flex flex-col gap-2 text-sm text-ink">
                  {action === "CLEAR" && <p>{t("case.clear_confirm")}</p>}
                  {action === "REQUEST_DOCS" && <p>{t("case.request_docs_email", { institution_name: flag.institution.name })}</p>}
                  {action === "ESCALATE" && <p>{t("case.escalate_note")}</p>}
                  {action === "CONFIRM" && (
                    <>
                      <p>{t("case.confirm_confirm", { institution_name: flag.institution.name })}</p>
                      {flag.enrolment_id && <p className="border-l-2 border-rule-margin pl-3">{t("case.confirm_revokes")}</p>}
                    </>
                  )}
                  {(action === "NOTE" || action === "ASSIGN" || action === "REOPEN") && <p className="sr-only">{t(ACTION_WORD[action])}</p>}
                </div>
              </DialogDescription>
            </div>

            {action === "ASSIGN" ? (
              <AssigneeCombobox ref={comboRef} flagId={flag.id} value={pick} onChange={setPick} error={errors.assignee_id} />
            ) : (
              <div className="flex flex-col gap-1.5">
                <label htmlFor={`${ids}-note`} className="text-sm font-medium">
                  {noteLabel(action)}
                </label>
                {prompt && (
                  <p id={noteHint} className="text-sm text-ink-muted">
                    {t(prompt)}
                  </p>
                )}
                <textarea
                  ref={noteRef}
                  id={`${ids}-note`}
                  value={note}
                  onChange={(e) => {
                    setNote(e.target.value);
                    if (errors.note && e.target.value.trim()) setErrors({ ...errors, note: undefined });
                  }}
                  rows={4}
                  maxLength={2000}
                  aria-required="true"
                  aria-invalid={errors.note ? true : undefined}
                  aria-describedby={[prompt ? noteHint : null, errors.note ? noteError : null].filter(Boolean).join(" ") || undefined}
                  disabled={mutation.isPending}
                  className="min-h-24 w-full rounded-md border border-line bg-paper px-2.5 py-2 text-base leading-snug aria-invalid:border-check-fail md:text-sm"
                />
                {errors.note && (
                  <p id={noteError} className="text-sm text-check-fail-ink">
                    {errors.note}
                  </p>
                )}
              </div>
            )}

            {action === "REQUEST_DOCS" && (
              <div className="flex flex-col gap-1.5">
                <label htmlFor={`${ids}-due`} className="text-sm font-medium">
                  {t("case.due_date")}
                </label>
                <p id={dueHint} className="text-sm text-ink-muted">
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
                  aria-describedby={[dueHint, errors.due_date ? dueError : null].filter(Boolean).join(" ")}
                  disabled={mutation.isPending}
                  className="h-10 w-full max-w-56 rounded-md border border-line bg-paper px-2.5 text-sm aria-invalid:border-check-fail"
                />
                {errors.due_date && (
                  <p id={dueError} className="text-sm text-check-fail-ink">
                    {errors.due_date}
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

            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button type="button" variant="outline" className="h-11 sm:h-9" onClick={onClose} disabled={mutation.isPending}>
                {t("case.cancel")}
              </Button>
              <Button type="submit" className="h-11 sm:h-9" aria-busy={mutation.isPending} disabled={mutation.isPending || (action === "ASSIGN" && pick === undefined)}>
                {mutation.isPending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
                {mutation.isPending ? t("case.sending") : t(SUBMIT[action])}
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
