"use client";

import * as React from "react";
import { ChevronsUp, CircleCheck, FileQuestion, Info, MessageSquarePlus, PencilLine, RotateCcw, Stamp, UserRoundPlus, type LucideIcon } from "lucide-react";
import { t } from "@/lib/copy";
import { formatDate } from "@/lib/format";
import type { FlagDetail, OfficerAction, Role } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { CaseSheet } from "@/components/cases/case-sheet";
import { ACTION_WORD, lastOf } from "@/components/cases/case-words";
import { ResponseBadge } from "@/components/cases/response-badge";

const ICON: Record<OfficerAction, LucideIcon> = {
  UPHOLD: CircleCheck,
  REQUEST_DOCS: FileQuestion,
  ESCALATE: ChevronsUp,
  WITHDRAW: Stamp,
  NOTE: MessageSquarePlus,
  ASSIGN: UserRoundPlus,
  REOPEN: RotateCcw,
  CORRECT: PencilLine,
};

/** Decisions sit on the left, record-keeping on the right (W3-8). */
const DECIDE: OfficerAction[] = ["UPHOLD", "REQUEST_DOCS", "ESCALATE", "WITHDRAW", "REOPEN"];
const RECORD: OfficerAction[] = ["NOTE", "ASSIGN"];

/** Today in IST as YYYY-MM-DD. */
function todayIst(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}

/**
 * Under the flag header: Response received (with the date on hover and
 * focus), the reply date while documents are requested (plain text, never
 * red, even once passed), and who holds the case.
 */
export function CaseStatusLine({ flag, showAssignee }: { flag: FlagDetail; showAssignee: boolean }) {
  const responded = lastOf(flag.history, "COLLEGE_RESPONSE");
  const waiting = flag.status === "DOCS_REQUESTED" && flag.docs_due_on;
  const passed = waiting && flag.docs_due_on! < todayIst();
  if (!flag.response_received && !waiting && !showAssignee) return null;
  return (
    <p className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
      {flag.response_received && (
        <Tooltip>
          <TooltipTrigger asChild>
            <span tabIndex={0} className="rounded-chip">
              <ResponseBadge />
            </span>
          </TooltipTrigger>
          <TooltipContent className="max-w-72">{t("case.response_badge_tip", { date: formatDate(responded?.at ?? flag.last_action_at) })}</TooltipContent>
        </Tooltip>
      )}
      {waiting && (
        <span className="text-ink">
          {passed ? t("case.due_passed", { due_date: formatDate(flag.docs_due_on) }) : t("case.due_line", { due_date: formatDate(flag.docs_due_on) })}
        </span>
      )}
      {showAssignee && <span className="text-ink-muted">{t("case.assignee_line", { name: flag.assignee?.name ?? t("case.assignee_none") })}</span>}
    </p>
  );
}

/**
 * The officer action bar: exactly the actions `allowed_actions` names, in
 * the contract's order, each opening its sheet. A refused action is not
 * shown at all. The line under it says why the bar is short, when it is.
 */
export function CaseActionBar({
  flag,
  role,
  fallbackFocus,
  onActed,
}: {
  flag: FlagDetail;
  role: Role;
  /** Receives focus when the action removed the button that opened the sheet. */
  fallbackFocus: React.RefObject<HTMLElement | null>;
  onActed: (flag: FlagDetail) => void;
}) {
  const [open, setOpen] = React.useState<OfficerAction | null>(null);
  const opener = React.useRef<HTMLButtonElement | null>(null);
  const allowed = flag.allowed_actions;
  const decide = DECIDE.filter((a) => allowed.includes(a));
  const record = RECORD.filter((a) => allowed.includes(a));
  const closed = flag.status === "UPHELD" || flag.status === "WITHDRAWN" || flag.status === "CORRECTED";
  const line =
    role === "RO_OFFICER" && flag.status === "ESCALATED"
      ? t("case.escalated_ro")
      : closed
        ? role === "AICTE_ADMIN"
          ? t("case.closed_admin")
          : t("case.closed_line")
        : null;

  const button = (a: OfficerAction) => {
    const Icon = ICON[a];
    return (
      <Button
        key={a}
        type="button"
        variant="outline"
        className="h-11 md:h-9"
        data-action={a}
        onClick={(e) => {
          opener.current = e.currentTarget;
          setOpen(a);
        }}
      >
        <Icon className="size-4" aria-hidden="true" />
        {t(ACTION_WORD[a])}
      </Button>
    );
  };

  function returnFocus() {
    const el = opener.current;
    if (el && el.isConnected) el.focus();
    else fallbackFocus.current?.focus();
  }

  if (allowed.length === 0 && !line) return null;
  return (
    <div className="mt-5">
      {allowed.length > 0 && (
        <div role="group" aria-label={t("section.actions")} className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-y border-rule py-3">
          <div className="flex flex-wrap gap-2">{decide.map(button)}</div>
          {record.length > 0 && <div className="flex flex-wrap gap-2">{record.map(button)}</div>}
        </div>
      )}
      {line && (
        <p className="mt-3 flex max-w-[68ch] items-start gap-2 text-sm text-ink-muted">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          {line}
        </p>
      )}
      <CaseSheet
        flag={flag}
        action={open}
        onClose={() => setOpen(null)}
        onDone={(updated) => {
          setOpen(null);
          onActed(updated);
        }}
        returnFocus={returnFocus}
      />
    </div>
  );
}
