"use client";

import * as React from "react";
import { Download, FileText, ImageIcon } from "lucide-react";
import { toast } from "sonner";
import { t, tk } from "@/lib/copy";
import { formatBytes, formatDate, formatDateTime } from "@/lib/format";
import { downloadAttachment } from "@/lib/queries-cases";
import type { CaseAttachment, CaseHistoryItem, FlagDetail, Role } from "@/lib/types";
import { errorMessage } from "@/components/common/query-state";
import { useMe } from "@/components/providers/root-provider";
import { fieldWord, historyReasonWord, roleWordOf, valueWord } from "@/components/cases/case-words";

/** The engines' standard system note; any other system note is printed as the api wrote it. */
const STANDARD_SYSTEM_NOTE = t("case.history.SYSTEM_NOTE");
const isStandardNote = (note: string | null) => !note || note.replace(/\.$/, "") === STANDARD_SYSTEM_NOTE;

/** "28 Oct 2026" over "16:05 IST", so the When column stays narrow. */
function When({ at }: { at: string }) {
  const [day, time] = formatDateTime(at).split(", ");
  return (
    <>
      <span className="block whitespace-nowrap">{day}</span>
      {time && <span className="block whitespace-nowrap text-ink-muted">{time}</span>}
    </>
  );
}

function AttachmentLink({ flagId, file }: { flagId: string; file: CaseAttachment }) {
  const { user } = useMe();
  const [busy, setBusy] = React.useState(false);
  const Icon = file.content_type === "application/pdf" ? FileText : ImageIcon;
  const size = formatBytes(file.size_bytes);
  return (
    <button
      type="button"
      disabled={busy}
      aria-busy={busy}
      // The visible "name, size" stays inside the accessible name.
      aria-label={`${t("case.attachment_download", { filename: file.filename })}, ${size}`}
      onClick={async () => {
        setBusy(true);
        try {
          await downloadAttachment(flagId, file);
        } catch (err) {
          toast.error(errorMessage(err, user?.role));
        } finally {
          setBusy(false);
        }
      }}
      className="inline-flex min-h-8 max-w-full items-center gap-1.5 rounded-md text-left text-ink-blue underline-offset-2 hover:underline disabled:opacity-60"
    >
      <Icon className="size-4 shrink-0" aria-hidden="true" />
      <span className="min-w-0 [overflow-wrap:anywhere]">{t("case.attachment", { filename: file.filename, size })}</span>
      <Download className="size-3.5 shrink-0" aria-hidden="true" />
    </button>
  );
}

/**
 * Who acted. A registrar sees the officer's role but never the officer's
 * name (IA: the role only on a document request).
 */
function who(item: CaseHistoryItem, flag: FlagDetail, viewer: Role | undefined): string {
  if (!item.actor) return t("case.history.system");
  const role = roleWordOf(item.actor.role, item.actor.role === "RO_OFFICER" ? flag.institution.region : null);
  if (viewer === "INSTITUTION" && item.actor.role !== "INSTITUTION") return role;
  return t("case.history.who", { actor_name: item.actor.name, role_word: role });
}

function what(item: CaseHistoryItem): string {
  if (item.action === "ASSIGN") return item.assignee ? t("case.history.ASSIGN", { assignee_name: item.assignee.name }) : t("case.history.ASSIGN_none");
  if (item.action === "SYSTEM_NOTE") return isStandardNote(item.note) ? STANDARD_SYSTEM_NOTE : item.note!;
  return tk(`case.history.${item.action}`);
}

/**
 * The What cell: the action, then in small text the status change, the reply
 * date and the reason; under it the note in quotes, the corrected fields,
 * the withdrawal line and the files (deck section 6, history).
 */
function WhatCell({ item, flagId }: { item: CaseHistoryItem; flagId: string }) {
  const changed = item.from_status && item.to_status && item.from_status !== item.to_status;
  const note = item.action === "SYSTEM_NOTE" ? null : item.note;
  const reason = historyReasonWord(item);
  return (
    <>
      <span className="block font-medium">{what(item)}</span>
      {changed && (
        <span className="block text-xs text-ink-muted">
          {t("case.history.status_change", { from_word: tk(`flag_status.${item.from_status}`), to_word: tk(`flag_status.${item.to_status}`) })}
        </span>
      )}
      {item.due_date && <span className="block text-xs text-ink-muted">{t("case.history.due", { due_date: formatDate(item.due_date) })}</span>}
      {item.docs_kind && <span className="block text-xs text-ink-muted">{t("case.history.docs_kind", { docs_kind_word: tk(`docs_kind.${item.docs_kind}`) })}</span>}
      {reason && <span className="block text-xs text-ink-muted">{t("case.history.reason", { reason_word: reason })}</span>}
      {item.approval_version !== null && item.approval_version !== undefined && (
        <span className="block text-xs text-ink-muted">{t("case.history.approval_version", { version: item.approval_version })}</span>
      )}
      {note && <span className="mt-1 block max-w-[68ch] [overflow-wrap:anywhere]">&ldquo;{note}&rdquo;</span>}
      {item.correction && item.correction.changes.length > 0 && (
        <ul className="mt-1 flex flex-col gap-0.5">
          {item.correction.changes.map((c) => (
            <li key={c.field} className="[overflow-wrap:anywhere]">
              {t("case.history.correction_line", { field_word: fieldWord(c.field), before: valueWord(c.field, c.before), after: valueWord(c.field, c.after) })}
            </li>
          ))}
        </ul>
      )}
      {item.action === "WITHDRAW" && item.withdrawn_enrolment_ids.length > 0 && (
        <span className="mt-1 block">{withdrawnLine(item.withdrawn_enrolment_ids.length)}</span>
      )}
      {item.attachments.length > 0 && (
        <ul className="mt-1 flex flex-col gap-0.5">
          {item.attachments.map((file) => (
            <li key={file.id}>
              <AttachmentLink flagId={flagId} file={file} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

/** The history keeps the withdrawn records, not the seats and attestations; those are on each record's own history. */
function withdrawnLine(n: number): string {
  const text = t("case.history.withdrawn_records", { records: n });
  return n === 1 ? text.replace("1 records", "1 record") : text;
}

/**
 * The case history (W3-8, W4-5), oldest first, starting with Case opened: When,
 * Who, What, with the status change and the reply date in small text, the
 * note in quotes and the attachments as downloads. Phones get the same rows
 * as a list, so a note never scrolls sideways.
 */
export function CaseHistory({ flag }: { flag: FlagDetail }) {
  const { user } = useMe();
  const items = [...flag.history].sort((a, b) => a.seq - b.seq);
  const anyFiles = items.some((i) => i.attachments.length > 0);
  const opened = { seq: -1, at: flag.created_at };
  const openedWord = flag.signal_id ? t("case.history.opened_from_signal") : t("case.history.opened");
  return (
    <>
      <ol aria-label={t("section.history")} className="flex flex-col divide-y divide-rule border-l-2 border-rule-margin bg-paper-raised text-sm sm:hidden">
        <li className="px-3 py-2.5">
          <p className="text-xs text-ink-muted">{formatDateTime(opened.at)}</p>
          <p className="text-ink-muted">{t("case.history.system")}</p>
          <p className="mt-1 font-medium">{openedWord}</p>
        </li>
        {items.map((item) => (
          <li key={item.seq} className="px-3 py-2.5">
            <p className="text-xs text-ink-muted">{formatDateTime(item.at)}</p>
            <p className="text-ink-muted">{who(item, flag, user?.role)}</p>
            <div className="mt-1">
              <WhatCell item={item} flagId={flag.id} />
            </div>
          </li>
        ))}
      </ol>
      <div className="relative hidden overflow-x-auto border-l-2 border-rule-margin bg-paper-raised sm:block">
        <table className="ledger-table">
          <caption className="sr-only">{t("section.history")}</caption>
          <thead>
            <tr>
              <th scope="col" className="w-36">
                {t("case.history.col.when")}
              </th>
              <th scope="col" className="w-56">
                {t("case.history.col.who")}
              </th>
              <th scope="col">{t("case.history.col.what")}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="wrap !h-auto py-2 align-top text-xs leading-snug">
                <When at={opened.at} />
              </td>
              <td className="wrap !h-auto py-2 align-top leading-snug">{t("case.history.system")}</td>
              <td className="wrap !h-auto py-2 align-top leading-snug">{openedWord}</td>
            </tr>
            {items.map((item) => (
              <tr key={item.seq}>
                <td className="wrap !h-auto py-2 align-top text-xs leading-snug">
                  <When at={item.at} />
                </td>
                <td className="wrap !h-auto min-w-36 py-2 align-top leading-snug">{who(item, flag, user?.role)}</td>
                <td className="wrap !h-auto min-w-56 py-2 align-top leading-snug">
                  <WhatCell item={item} flagId={flag.id} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {anyFiles && <p className="mt-2 text-xs text-ink-muted">{t("case.attachments_logged")}</p>}
    </>
  );
}
