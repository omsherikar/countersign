"use client";

import * as React from "react";
import { Popover } from "radix-ui";
import { CHECK_ORDER, ordered, pendingCount, scoreText, segmentTip, stripAria, statusWord } from "@/lib/checks";
import { t, tk } from "@/lib/copy";
import type { Check, CheckBrief, Countersign } from "@/lib/types";
import { cn } from "@/lib/utils";

const SIZE = { sm: "countersign-score--sm", md: undefined, lg: "countersign-score--lg" } as const;

/**
 * The countersign strip (page spec W2-3): five segments in check order and
 * "3 of 4". It is one focusable control; hover, focus or a tap opens a small
 * list of the five checks with their status words. Lists pass the compact
 * countersign; enrolment detail also passes the full checks, so each line
 * carries the source and the time it was checked.
 */
export function CountersignStrip({
  countersign,
  checks,
  size = "sm",
  className,
}: {
  countersign: Countersign;
  checks?: Check[];
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const [open, setOpen] = React.useState(false);
  const closing = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const contentId = React.useId();
  const score = countersign.score;

  if (!score) {
    return (
      <span className={cn("countersign-score", SIZE[size], className)} role="img" aria-label={t("strip.not_checked")}>
        <span className="countersign-score__checks" aria-hidden="true">
          {CHECK_ORDER.map((c) => (
            <span key={c} className="countersign-score__check" data-status="UNCHECKED" />
          ))}
        </span>
        <span className="countersign-score__empty">{t("strip.not_checked")}</span>
      </span>
    );
  }

  const list: (CheckBrief | Check)[] = ordered<CheckBrief | Check>(checks && checks.length ? checks : countersign.checks);
  const pending = pendingCount(countersign);
  const scoreOnly = t("strip.score", { passes: score.passes, applicable: score.applicable });
  const suffix = pending > 0 ? scoreText(countersign).slice(scoreOnly.length) : "";

  const cancelClose = () => {
    if (closing.current) clearTimeout(closing.current);
    closing.current = null;
  };
  const closeSoon = () => {
    cancelClose();
    closing.current = setTimeout(() => setOpen(false), 120);
  };

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Anchor asChild>
        <button
          type="button"
          aria-label={stripAria(countersign, checks)}
          aria-describedby={open ? contentId : undefined}
          aria-expanded={open}
          onClick={() => setOpen(true)}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onPointerEnter={(e) => {
            if (e.pointerType !== "mouse") return;
            cancelClose();
            setOpen(true);
          }}
          onPointerLeave={(e) => {
            if (e.pointerType === "mouse") closeSoon();
          }}
          onKeyDown={(e) => {
            if (e.key === "Escape") setOpen(false);
          }}
          className={cn(
            "countersign-score -mx-1 cursor-default rounded-md px-1 py-0.5 hover:bg-flag-open-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-blue",
            SIZE[size],
            className,
          )}
        >
          <span className="countersign-score__checks" aria-hidden="true">
            {CHECK_ORDER.map((type) => {
              const c = list.find((x) => x.type === type);
              return <span key={type} className="countersign-score__check" data-status={c?.status ?? "UNCHECKED"} />;
            })}
          </span>
          <span className="countersign-score__value" aria-hidden="true">
            {score.passes}
            <span className="countersign-score__of">of</span>
            {score.applicable}
          </span>
          {suffix && (
            <span className="font-sans text-xs text-ink-muted" aria-hidden="true">
              {suffix.replace(/^,\s*/, "")}
            </span>
          )}
        </button>
      </Popover.Anchor>
      <Popover.Portal>
        <Popover.Content
          id={contentId}
          side="top"
          align="start"
          sideOffset={6}
          collisionPadding={8}
          onOpenAutoFocus={(e) => e.preventDefault()}
          onCloseAutoFocus={(e) => e.preventDefault()}
          onPointerEnter={cancelClose}
          onPointerLeave={closeSoon}
          className="z-50 max-w-[min(26rem,calc(100vw-2rem))] rounded-md border border-line bg-paper-raised px-3 py-2 text-xs text-ink shadow-md"
        >
          <p className="mb-1.5 font-medium">{t("enrolment.score_label")} {scoreText(countersign)}</p>
          <ul className="flex flex-col gap-1">
            {list.map((c) => (
              <li key={c.type} className="flex items-center gap-2">
                <span className="countersign-score countersign-score--sm" aria-hidden="true">
                  <span className="countersign-score__check" data-status={c.status} />
                </span>
                <span>
                  <span className="sr-only">{`${tk(`check.${c.type}`)}: ${statusWord(c)}. `}</span>
                  <span aria-hidden="true">{segmentTip(c)}</span>
                </span>
              </li>
            ))}
          </ul>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
