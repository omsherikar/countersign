"use client";

import * as React from "react";
import { FileText, ImageIcon, Loader2, Paperclip, X } from "lucide-react";
import { toast } from "sonner";
import { FlagStatusBadge } from "@/components/brand/FlagStatusBadge";
import { ApiError } from "@/lib/api";
import { t, tk } from "@/lib/copy";
import { formatBytes, formatDate } from "@/lib/format";
import { useCollegeResponse } from "@/lib/queries-cases";
import type { FlagDetail } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { errorMessage } from "@/components/common/query-state";
import { useMe } from "@/components/providers/root-provider";
import { lastOf, roleWordOf } from "@/components/cases/case-words";

const MAX_FILES = 3;
const MAX_BYTES = 5 * 1024 * 1024;
const EXTENSIONS = ["pdf", "png", "jpg", "jpeg"];
const TYPES = ["application/pdf", "image/png", "image/jpeg"];

/** Checked in the browser first; the api checks the first bytes again (415 ATTACHMENT_TYPE). */
function allowedType(file: File): boolean {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  return EXTENSIONS.includes(ext) && (!file.type || TYPES.includes(file.type));
}

/**
 * Respond to a document request (page spec W3-7): what the officer asked,
 * then a reply and up to three PDF, PNG or JPEG files of 5 MB each. The
 * status stays at Documents requested; the officer decides afterwards.
 */
export function CollegeRespond({ flag }: { flag: FlagDetail }) {
  const respond = useCollegeResponse(flag.id);
  const { user } = useMe();
  const request = lastOf(flag.history, "REQUEST_DOCS");
  const response = lastOf(flag.history, "COLLEGE_RESPONSE");
  const answered = Boolean(response && (!request || response.seq > request.seq));

  const [expanded, setExpanded] = React.useState(!answered);
  const [note, setNote] = React.useState("");
  const [files, setFiles] = React.useState<File[]>([]);
  const [noteError, setNoteError] = React.useState<string | null>(null);
  const [fileErrors, setFileErrors] = React.useState<string[]>([]);
  const [serverError, setServerError] = React.useState<string | null>(null);
  const [progress, setProgress] = React.useState(0);
  const [sent, setSent] = React.useState(false);
  const noteRef = React.useRef<HTMLTextAreaElement>(null);
  const fileRef = React.useRef<HTMLInputElement>(null);
  const addRef = React.useRef<HTMLButtonElement>(null);
  const moreRef = React.useRef<HTMLButtonElement>(null);
  const ids = React.useId();

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = Array.from(e.target.files ?? []);
    e.target.value = "";
    const errs: string[] = [];
    const next = [...files];
    for (const file of picked) {
      if (!allowedType(file)) errs.push(t("college.respond_file_type", { filename: file.name }));
      else if (file.size > MAX_BYTES) errs.push(t("college.respond_file_size", { filename: file.name }));
      else if (next.length >= MAX_FILES) {
        const msg = t("college.respond_too_many");
        if (!errs.includes(msg)) errs.push(msg);
      } else next.push(file);
    }
    setFiles(next);
    setFileErrors(errs);
    setServerError(null);
  }

  function remove(i: number) {
    setFiles(files.filter((_, n) => n !== i));
    setFileErrors([]);
    addRef.current?.focus();
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (respond.isPending) return;
    setServerError(null);
    if (!note.trim()) {
      setNoteError(t("college.respond_note_required"));
      noteRef.current?.focus();
      return;
    }
    setNoteError(null);
    setProgress(0);
    respond.mutate(
      { note: note.trim(), files, onProgress: setProgress },
      {
        onSuccess: () => {
          setSent(true);
          setNote("");
          setFiles([]);
          setFileErrors([]);
          setExpanded(false);
          requestAnimationFrame(() => moreRef.current?.focus());
        },
        onError: (err) => {
          if (err instanceof ApiError) {
            if (err.code === "ATTACHMENT_TOO_LARGE") return setServerError(t("err.ATTACHMENT_TOO_LARGE"));
            if (err.code === "ATTACHMENT_TYPE") return setServerError(t("err.ATTACHMENT_TYPE"));
            if (err.code === "FLAG_TRANSITION_INVALID") {
              // The officer decided meanwhile; the panel goes away as the flag refetches.
              toast.error(t("err.FLAG_TRANSITION_INVALID"));
              return;
            }
            const field = err.fields.find((f) => f.field === "note");
            if (field) {
              setNoteError(field.message);
              noteRef.current?.focus();
              return;
            }
          }
          setServerError(errorMessage(err, user?.role, "flag"));
        },
      },
    );
  }

  const noteHint = `${ids}-note-hint`;
  const noteErr = `${ids}-note-error`;
  const filesHint = `${ids}-files-label`;
  const countId = `${ids}-count`;
  const busy = respond.isPending;

  return (
    <section aria-label={t("college.respond_heading")} className="mb-10 max-w-3xl rounded-md border border-line border-l-[3px] border-l-flag-docs bg-paper-raised p-4 md:p-5">
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
        <FlagStatusBadge status={flag.status} />
        {flag.docs_due_on && <span className="font-medium">{t("college.due_line", { due_date: formatDate(flag.docs_due_on) })}</span>}
      </p>
      {request && (
        <div className="mt-3 text-sm">
          <p className="text-ink-muted">
            {t("college.request_line", {
              role_word: request.actor ? roleWordOf(request.actor.role, request.actor.role === "RO_OFFICER" ? flag.institution.region : null) : t("case.history.system"),
              requested_date: formatDate(request.at),
            })}
          </p>
          {request.docs_kind && <p className="mt-1 font-medium">{t("college.request_kind_line", { docs_kind_word: tk(`docs_kind.${request.docs_kind}`) })}</p>}
          {request.note && <p className="mt-1 max-w-[68ch] text-md [overflow-wrap:anywhere]">&ldquo;{request.note}&rdquo;</p>}
        </div>
      )}

      <div aria-live="polite">{sent && <p className="mt-4 font-medium">{t("college.respond_sent")}</p>}</div>

      {!expanded && response && (
        <div className="mt-3 flex flex-col items-start gap-3">
          <p className="max-w-[68ch] text-sm text-ink-muted">{t("college.respond_waiting", { date: formatDate(response.at) })}</p>
          <Button ref={moreRef} type="button" variant="outline" className="h-11 w-full sm:w-auto md:h-9" onClick={() => setExpanded(true)}>
            <Paperclip className="size-4" aria-hidden="true" />
            {t("college.respond_more")}
          </Button>
        </div>
      )}

      {expanded && (
        <form onSubmit={submit} noValidate className="mt-5 flex flex-col gap-5 border-t border-rule pt-4">
          <h2 className="text-lg">
            {t("college.respond_heading")}
          </h2>
          <div className="flex flex-col gap-1.5">
            <label htmlFor={`${ids}-note`} className="text-sm font-medium">
              {t("college.respond_note")}
            </label>
            <textarea
              ref={noteRef}
              id={`${ids}-note`}
              value={note}
              onChange={(e) => {
                setNote(e.target.value);
                if (noteError && e.target.value.trim()) setNoteError(null);
              }}
              rows={4}
              maxLength={2000}
              aria-required="true"
              aria-invalid={noteError ? true : undefined}
              aria-describedby={[noteHint, noteError ? noteErr : null].filter(Boolean).join(" ")}
              disabled={busy}
              className="min-h-28 w-full rounded-md border border-line bg-paper px-2.5 py-2 text-md leading-snug aria-invalid:border-check-fail md:text-sm"
            />
            <p id={noteHint} className="text-sm text-ink-muted">
              {t("college.respond_note_hint")}
            </p>
            {noteError && (
              <p id={noteErr} className="text-sm text-check-fail-ink">
                {noteError}
              </p>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <label id={filesHint} htmlFor={`${ids}-files`} className="text-sm font-medium">
              {t("college.respond_files")}
            </label>
            <input
              ref={fileRef}
              id={`${ids}-files`}
              type="file"
              multiple
              accept=".pdf,.png,.jpg,.jpeg"
              tabIndex={-1}
              className="sr-only"
              onChange={onPick}
              disabled={busy}
            />
            <div>
              <Button
                ref={addRef}
                type="button"
                variant="outline"
                className="h-11 md:h-9"
                aria-describedby={`${filesHint} ${countId}`}
                disabled={busy}
                onClick={() => fileRef.current?.click()}
              >
                <Paperclip className="size-4" aria-hidden="true" />
                {t("college.respond_add_file")}
              </Button>
            </div>
            {files.length > 0 && (
              <ul className="flex flex-col divide-y divide-rule rounded-md border border-line">
                {files.map((file, i) => {
                  const Icon = file.type.startsWith("image/") ? ImageIcon : FileText;
                  return (
                    <li key={`${file.name}-${i}`} className="flex items-center justify-between gap-3 px-3 py-1.5 text-sm">
                      <span className="flex min-w-0 items-center gap-2">
                        <Icon className="size-4 shrink-0 text-ink-muted" aria-hidden="true" />
                        <span className="min-w-0 [overflow-wrap:anywhere]">{t("case.attachment", { filename: file.name, size: formatBytes(file.size) })}</span>
                      </span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="size-11 shrink-0 md:size-8"
                        aria-label={t("college.respond_remove_file", { filename: file.name })}
                        disabled={busy}
                        onClick={() => remove(i)}
                      >
                        <X className="size-4" aria-hidden="true" />
                      </Button>
                    </li>
                  );
                })}
              </ul>
            )}
            <p id={countId} className="text-xs text-ink-muted tabular-nums" aria-live="polite">
              {t("college.respond_file_count", { n: files.length })}
            </p>
            <div aria-live="polite">
              {fileErrors.map((m) => (
                <p key={m} className="text-sm text-check-fail-ink">
                  {m}
                </p>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-3">
            <div aria-live="polite">
              {serverError && (
                <p role="alert" className="rounded-md border border-check-fail/30 bg-paper px-3 py-2 text-sm">
                  {serverError}
                </p>
              )}
            </div>
            <div>
              <Button type="submit" className="h-12 w-full sm:w-auto md:h-9" aria-busy={busy} disabled={busy}>
                {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
                {busy ? (progress > 0 && progress < 100 ? t("college.respond_progress", { pct: progress }) : t("college.respond_sending")) : t("college.respond_submit")}
              </Button>
            </div>
          </div>
        </form>
      )}
    </section>
  );
}
