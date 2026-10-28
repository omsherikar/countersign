"use client";

import * as React from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface Option {
  value: string;
  label: string;
}

/** A labelled native select: keyboard, screen readers and phones all work without extra code. */
export function FilterSelect({
  label,
  value,
  options,
  onChange,
  allLabel = "All",
  className,
}: {
  label: string;
  value: string;
  options: Option[];
  onChange: (value: string) => void;
  allLabel?: string | null;
  className?: string;
}) {
  const id = React.useId();
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <label htmlFor={id} className="text-xs font-medium whitespace-nowrap text-ink-muted">
        {label}
      </label>
      <div className="relative">
        <select
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="h-8 max-w-48 appearance-none rounded-md border border-line bg-paper-raised py-0 pr-7 pl-2.5 text-sm text-ink"
        >
          {allLabel !== null && <option value="">{allLabel}</option>}
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute top-1/2 right-2 size-3.5 -translate-y-1/2 text-ink-muted" aria-hidden="true" />
      </div>
    </div>
  );
}

/** Search input with a 300 ms debounce; Esc clears it. */
export function SearchInput({
  label,
  placeholder,
  value,
  onChange,
  delay = 300,
  className,
}: {
  label: string;
  placeholder?: string;
  value: string;
  onChange: (value: string) => void;
  delay?: number;
  className?: string;
}) {
  const id = React.useId();
  const [text, setText] = React.useState(value);
  const [synced, setSynced] = React.useState(value);
  if (value !== synced) {
    // The URL changed underneath us (e.g. "Clear filters"); follow it.
    setSynced(value);
    setText(value);
  }
  React.useEffect(() => {
    if (text === value) return;
    const timer = setTimeout(() => onChange(text.trim()), delay);
    return () => clearTimeout(timer);
  }, [text, value, delay, onChange]);
  return (
    <div className={cn("flex min-w-0 flex-col", className)}>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <input
        id={id}
        type="search"
        value={text}
        placeholder={placeholder ?? label}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            setText("");
            onChange("");
          }
        }}
        className="h-8 w-full min-w-56 rounded-md border border-line bg-paper-raised px-2.5 text-sm placeholder:text-ink-faint"
      />
    </div>
  );
}
