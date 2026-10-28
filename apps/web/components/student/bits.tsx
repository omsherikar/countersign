"use client";

import * as React from "react";
import { ChevronRight, XIcon } from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

/* ---- Status words -------------------------------------------------------- */

export type Tone = "ok" | "alert" | "caution" | "neutral" | "blue";

const TONE: Record<Tone, string> = {
  ok: "bg-check-pass-soft text-check-pass-ink border-check-pass/40",
  alert: "bg-check-fail-soft text-check-fail-ink border-check-fail/40",
  caution: "bg-check-pending-soft text-check-pending-ink border-check-pending/40 border-dashed",
  neutral: "bg-check-na-soft text-check-na-ink border-check-na/40",
  blue: "bg-flag-open-soft text-flag-open-ink border-flag-open/40",
};

/**
 * A status as a word with its icon on the tint of its hue family (DESIGN
 * section 3.2). Never colour alone: the word is always there, and pending
 * states are dashed so they survive greyscale print.
 */
export function StatusWord({
  tone,
  icon: Icon,
  children,
  className,
  size = "sm",
}: {
  tone: Tone;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
  className?: string;
  size?: "sm" | "md";
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-chip border font-medium whitespace-nowrap",
        size === "sm" ? "h-5 px-1.5 text-xs" : "h-7 px-2 text-sm",
        TONE[tone],
        className,
      )}
    >
      <Icon className={cn("shrink-0", size === "sm" ? "size-3" : "size-4")} aria-hidden="true" />
      <span>{children}</span>
    </span>
  );
}

/* ---- Dialog that is a bottom sheet on phones ----------------------------- */

/**
 * A modal dialog from 768 px and a bottom sheet below it (W3-2). Radix keeps
 * focus inside, closes on Esc and returns focus to the control that opened
 * it. The body scrolls inside itself; `footer` stays pinned to the foot.
 */
export function SheetDialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  onOpenAutoFocus,
  closeLabel = "Close",
  className,
  lang,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: React.ReactNode;
  description?: React.ReactNode;
  children?: React.ReactNode;
  footer?: React.ReactNode;
  onOpenAutoFocus?: (e: Event) => void;
  closeLabel?: string;
  className?: string;
  lang?: string;
}) {
  // Opened from state rather than a Radix trigger, so remember the opener and hand focus back to it on close.
  const opener = React.useRef<HTMLElement | null>(null);
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <DialogPrimitive.Content
          lang={lang}
          onOpenAutoFocus={(e) => {
            opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
            onOpenAutoFocus?.(e);
          }}
          onCloseAutoFocus={(e) => {
            if (opener.current?.isConnected) {
              e.preventDefault();
              opener.current.focus();
            }
          }}
          className={cn(
            "fixed z-50 flex flex-col bg-paper-raised text-md text-ink shadow-lg outline-none",
            "inset-x-0 bottom-0 max-h-[92dvh] rounded-t-lg border-t border-line",
            "md:inset-x-auto md:top-1/2 md:bottom-auto md:left-1/2 md:max-h-[86dvh] md:w-[560px] md:-translate-x-1/2 md:-translate-y-1/2 md:rounded-lg md:border",
            className,
          )}
        >
          <div className="flex items-start gap-3 border-b border-rule px-4 pt-4 pb-3 md:px-6">
            <div className="min-w-0 flex-1">
              <DialogPrimitive.Title className="font-display text-xl leading-snug font-semibold">{title}</DialogPrimitive.Title>
              {description ? (
                <DialogPrimitive.Description className="mt-1.5 text-md text-ink-muted">{description}</DialogPrimitive.Description>
              ) : null}
            </div>
            <DialogPrimitive.Close className="-mt-1 -mr-2 inline-flex size-11 shrink-0 items-center justify-center rounded-md text-ink-muted hover:bg-paper-sunken">
              <XIcon className="size-5" aria-hidden="true" />
              <span className="sr-only">{closeLabel}</span>
            </DialogPrimitive.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 md:px-6">{children}</div>
          {footer ? <div className="border-t border-rule px-4 pt-3 pb-[max(1rem,env(safe-area-inset-bottom))] md:px-6">{footer}</div> : null}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

/* ---- Countdown ----------------------------------------------------------- */

const noSubscribe = () => () => {};
function subscribeClock(onTick: () => void) {
  const id = setInterval(onTick, 1000);
  return () => clearInterval(id);
}
const clockNow = () => Math.floor(Date.now() / 1000);
const serverClock = () => 0;

/** Seconds left until `until` (epoch ms), ticking once a second; null when there is no deadline. */
export function useSecondsLeft(until: number | null): number | null {
  const now = React.useSyncExternalStore(until === null ? noSubscribe : subscribeClock, clockNow, serverClock);
  if (until === null) return null;
  return Math.max(0, Math.ceil(until / 1000 - now));
}

/** The time in epoch ms, read without making render impure; `live` ticks it once a second. 0 on the server. */
export function useNow(live = false): number {
  return React.useSyncExternalStore(live ? subscribeClock : noSubscribe, clockNow, serverClock) * 1000;
}

/**
 * When a 429 lets the caller try again: `retry_after` counted from when the
 * answer came back (a query's `errorUpdatedAt`, a mutation's `submittedAt`).
 */
export function retryDeadline(err: unknown, at: number): number | null {
  if (!(err instanceof ApiError) || err.code !== "RATE_LIMITED" || !at) return null;
  return at + (err.retryAfter ?? 30) * 1000;
}

/* ---- Buttons sized for phones -------------------------------------------- */

/** Full width and 48 px tall below 768 px (W3 phone rules); `quiet` is the outlined twin of equal weight. */
export const bigButton = cn(
  "inline-flex h-12 w-full items-center justify-center gap-2 rounded-md px-4 text-md font-medium",
  "disabled:cursor-not-allowed disabled:opacity-60 aria-disabled:cursor-not-allowed aria-disabled:opacity-60",
);
export const primaryButton = cn(bigButton, "bg-ink-blue text-on-ink-blue hover:bg-ink-blue-hover");
export const outlineButton = cn(bigButton, "border-[1.5px] border-ink-blue bg-paper-raised text-ink-blue hover:bg-flag-open-soft");

/* ---- Native disclosure --------------------------------------------------- */

/** A native <details> with a visible chevron; keyboard and screen readers get the built-in behaviour. */
export function Disclosure({
  summary,
  children,
  className,
  summaryClassName,
  open,
  onToggle,
}: {
  summary: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  summaryClassName?: string;
  open?: boolean;
  onToggle?: (open: boolean) => void;
}) {
  return (
    <details className={cn("group", className)} open={open} onToggle={onToggle ? (e) => onToggle(e.currentTarget.open) : undefined}>
      <summary
        className={cn(
          "flex min-h-11 w-fit cursor-pointer list-none items-center gap-2 font-medium text-ink-blue [&::-webkit-details-marker]:hidden",
          summaryClassName,
        )}
      >
        <ChevronRight className="size-4 shrink-0 group-open:rotate-90" aria-hidden="true" />
        {summary}
      </summary>
      {children}
    </details>
  );
}
