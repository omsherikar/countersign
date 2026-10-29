"use client";

import * as React from "react";
import { XIcon } from "lucide-react";
import { Dialog as DialogPrimitive } from "radix-ui";
import { t } from "@/lib/copy";
import { cn } from "@/lib/utils";

/**
 * The frame of every case sheet (W4-5): a modal dialog labelled by its
 * heading from 640 px, and a full-height sheet on phones with the form
 * scrolling and the buttons pinned to the foot. Radix keeps Tab inside and
 * closes on Esc; the caller decides where focus lands when it opens and
 * where it returns when it closes.
 */
export function CaseSheetShell({
  open,
  onOpenChange,
  title,
  lead,
  children,
  footer,
  initialFocus,
  returnFocus,
  busy,
  wide = false,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: React.ReactNode;
  lead?: React.ReactNode;
  children: React.ReactNode;
  footer: React.ReactNode;
  initialFocus?: () => HTMLElement | null | undefined;
  returnFocus: () => void;
  /** While sending, Esc and the close button do nothing. */
  busy?: boolean;
  wide?: boolean;
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={(next) => !busy && onOpenChange(next)}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <DialogPrimitive.Content
          onOpenAutoFocus={(e) => {
            const el = initialFocus?.();
            if (el) {
              e.preventDefault();
              el.focus();
            }
          }}
          onCloseAutoFocus={(e) => {
            e.preventDefault();
            returnFocus();
          }}
          className={cn(
            "fixed z-50 flex flex-col bg-paper-raised text-md text-ink shadow-lg outline-none md:text-sm",
            "inset-0 h-dvh w-full",
            "sm:inset-auto sm:top-1/2 sm:left-1/2 sm:h-auto sm:max-h-[88dvh] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-lg sm:border sm:border-line",
            wide ? "sm:w-[min(720px,calc(100vw-2rem))]" : "sm:w-[min(600px,calc(100vw-2rem))]",
          )}
        >
          <div className="flex items-start gap-3 border-b border-rule px-4 pt-4 pb-3 sm:px-6">
            <div className="min-w-0 flex-1">
              <DialogPrimitive.Title className="font-display text-xl leading-snug font-semibold">{title}</DialogPrimitive.Title>
              {lead ? <DialogPrimitive.Description className="mt-1.5 text-md text-ink md:text-sm">{lead}</DialogPrimitive.Description> : <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>}
            </div>
            <DialogPrimitive.Close
              disabled={busy}
              className="-mt-1 -mr-2 inline-flex size-11 shrink-0 items-center justify-center rounded-md text-ink-muted hover:bg-paper-sunken disabled:opacity-50"
            >
              <XIcon className="size-5" aria-hidden="true" />
              <span className="sr-only">{t("case.cancel")}</span>
            </DialogPrimitive.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-6">{children}</div>
          <div className="border-t border-rule px-4 pt-3 pb-[max(1rem,env(safe-area-inset-bottom))] sm:px-6">{footer}</div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

/** A labelled native select, 44 px tall on phones, with its error under it. */
export const FieldSelect = React.forwardRef<
  HTMLSelectElement,
  {
    id: string;
    label: string;
    value: string;
    onChange: (value: string) => void;
    options: { value: string; label: string }[];
    placeholder?: string;
    error?: string;
    hint?: string;
    disabled?: boolean;
    required?: boolean;
    className?: string;
  }
>(function FieldSelect({ id, label, value, onChange, options, placeholder, error, hint, disabled, required = true, className }, ref) {
  const describedBy = [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      {hint && (
        <p id={`${id}-hint`} className="text-sm text-ink-muted">
          {hint}
        </p>
      )}
      <select
        ref={ref}
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-required={required || undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        disabled={disabled}
        className="h-11 w-full min-w-0 rounded-md border border-line bg-paper px-2.5 text-md aria-invalid:border-check-fail md:h-9 md:text-sm"
      >
        {placeholder !== undefined && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {error && (
        <p id={`${id}-error`} className="text-sm text-check-fail-ink">
          {error}
        </p>
      )}
    </div>
  );
});

/** The note every case action asks for, with its own error line. */
export const NoteField = React.forwardRef<
  HTMLTextAreaElement,
  { id: string; label: string; prompt?: string; value: string; onChange: (v: string) => void; error?: string; disabled?: boolean }
>(function NoteField({ id, label, prompt, value, onChange, error, disabled }, ref) {
  const describedBy = [prompt ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      {prompt && (
        <p id={`${id}-hint`} className="text-sm text-ink-muted">
          {prompt}
        </p>
      )}
      <textarea
        ref={ref}
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={3}
        maxLength={2000}
        aria-required="true"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        disabled={disabled}
        className="min-h-20 w-full rounded-md border border-line bg-paper px-2.5 py-2 text-md leading-snug aria-invalid:border-check-fail md:text-sm"
      />
      {error && (
        <p id={`${id}-error`} className="text-sm text-check-fail-ink">
          {error}
        </p>
      )}
    </div>
  );
});

/**
 * "What will change": one full sentence per consequence, as a list. While
 * the preview loads the lines are skeletons; when it fails, the list says so
 * and the caller keeps the submit disabled.
 */
export function ChangesList({
  lines,
  loading,
  failed,
  empty,
  after,
}: {
  lines: React.ReactNode[];
  loading: boolean;
  failed: boolean;
  /** Shown instead of the list when there is nothing to preview yet. */
  empty?: string | null;
  after?: React.ReactNode;
}) {
  const id = React.useId();
  return (
    <section aria-labelledby={id} className="border-l-2 border-rule-margin bg-paper px-3 py-3">
      <h3 id={id} className="font-sans text-sm font-semibold">
        {t("case.changes_heading")}
      </h3>
      <div aria-live="polite" aria-busy={loading || undefined}>
        {loading ? (
          <div className="mt-2 flex flex-col gap-2" aria-hidden="true">
            <span className="block h-3.5 w-11/12 animate-pulse rounded bg-paper-sunken" />
            <span className="block h-3.5 w-9/12 animate-pulse rounded bg-paper-sunken" />
            <span className="block h-3.5 w-10/12 animate-pulse rounded bg-paper-sunken" />
            <span className="sr-only">{t("case.changes_loading")}</span>
          </div>
        ) : failed ? (
          <p className="mt-2 text-sm text-check-fail-ink">{t("err.tile_failed")}</p>
        ) : empty ? (
          <p className="mt-2 text-sm text-ink-muted">{empty}</p>
        ) : (
          <ul className="mt-2 flex list-disc flex-col gap-1.5 pl-5 text-sm leading-snug">
            {lines.map((line, i) => (
              <li key={i} className="[overflow-wrap:anywhere]">
                {line}
              </li>
            ))}
          </ul>
        )}
      </div>
      {after}
    </section>
  );
}

/** The two buttons at the foot of a sheet: submit first on phones (full width), Cancel beside it from 640 px. */
export function SheetButtons({
  submitLabel,
  busyLabel,
  busy,
  disabled,
  onCancel,
  form,
}: {
  submitLabel: string;
  busyLabel?: string;
  busy: boolean;
  disabled?: boolean;
  onCancel: () => void;
  form: string;
}) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row-reverse sm:justify-start">
      <button
        type="submit"
        form={form}
        aria-busy={busy || undefined}
        aria-disabled={disabled || busy || undefined}
        className={cn(
          "inline-flex h-12 w-full items-center justify-center gap-2 rounded-md bg-ink-blue px-4 text-md font-medium text-on-ink-blue hover:bg-ink-blue-hover sm:h-9 sm:w-auto sm:text-sm",
          (disabled || busy) && "cursor-not-allowed opacity-60 hover:bg-ink-blue",
        )}
      >
        {busy ? (busyLabel ?? t("case.sending")) : submitLabel}
      </button>
      <button
        type="button"
        onClick={onCancel}
        disabled={busy}
        className="inline-flex h-12 w-full items-center justify-center rounded-md border border-line bg-paper-raised px-4 text-md font-medium hover:bg-paper-sunken disabled:opacity-60 sm:h-9 sm:w-auto sm:text-sm"
      >
        {t("case.cancel")}
      </button>
    </div>
  );
}
