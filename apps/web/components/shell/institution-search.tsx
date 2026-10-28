"use client";

import * as React from "react";
import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { t } from "@/lib/copy";
import { formatCount } from "@/lib/format";
import { useInstitutions } from "@/lib/queries";
import { cn } from "@/lib/utils";

/**
 * Global search for officers and the university: institutions only, by name
 * or permanent id (IA section 4). `/` or Ctrl+K focuses it, Esc clears it,
 * arrows move through at most 8 results.
 */
export function InstitutionSearch({ basePath }: { basePath: string }) {
  const router = useRouter();
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [text, setText] = React.useState("");
  const [q, setQ] = React.useState("");
  const [open, setOpen] = React.useState(false);
  const [cursor, setCursor] = React.useState(0);
  const listId = React.useId();

  React.useEffect(() => {
    const id = setTimeout(() => setQ(text.trim()), 250);
    return () => clearTimeout(id);
  }, [text]);

  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      const typing = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
      if ((e.key === "/" && !typing) || (e.key.toLowerCase() === "k" && (e.ctrlKey || e.metaKey))) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const results = useInstitutions({ q, page_size: 8, sort: "enrolments", order: "desc" }, q.length > 0);
  const items = q.length > 0 ? (results.data?.items ?? []) : [];
  const show = open && q.length > 0;

  function go(id: string) {
    setOpen(false);
    setText("");
    router.push(`${basePath}/institutions/${id}`);
  }

  return (
    <div className="relative w-full max-w-sm">
      <label htmlFor={`${listId}-input`} className="sr-only">
        {t("search.placeholder")}
      </label>
      <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-ink-faint" aria-hidden="true" />
      <input
        ref={inputRef}
        id={`${listId}-input`}
        type="search"
        role="combobox"
        aria-expanded={show}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={show && items[cursor] ? `${listId}-${cursor}` : undefined}
        autoComplete="off"
        placeholder={t("search.placeholder")}
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setCursor(0);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            setText("");
            setOpen(false);
          } else if (e.key === "ArrowDown") {
            e.preventDefault();
            setCursor((c) => Math.min(c + 1, Math.max(items.length - 1, 0)));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setCursor((c) => Math.max(c - 1, 0));
          } else if (e.key === "Enter" && items[cursor]) {
            e.preventDefault();
            go(items[cursor].id);
          }
        }}
        className="h-9 w-full rounded-md border border-line bg-paper pr-12 pl-8 text-sm placeholder:text-ink-faint focus-visible:bg-paper-raised"
      />
      <kbd className="pointer-events-none absolute top-1/2 right-2 hidden -translate-y-1/2 rounded-chip border border-line px-1.5 font-mono text-2xs text-ink-faint sm:inline">
        /
      </kbd>
      {show && (
        <div
          id={listId}
          role="listbox"
          className="absolute top-full right-0 left-0 z-50 mt-1 overflow-hidden rounded-md border border-line bg-popover shadow-popover"
        >
          {results.isFetching && items.length === 0 && <p className="px-3 py-2.5 text-sm text-ink-muted">Searching</p>}
          {!results.isFetching && items.length === 0 && (
            <p className="px-3 py-2.5 text-sm text-ink-muted">{t("search.empty", { q })}</p>
          )}
          {items.map((row, i) => (
            <div
              key={row.id}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === cursor}
              onMouseDown={(e) => {
                e.preventDefault();
                go(row.id);
              }}
              onMouseEnter={() => setCursor(i)}
              className={cn(
                "flex cursor-pointer items-baseline gap-3 px-3 py-2 text-sm",
                i === cursor && "bg-[var(--hue-blue-soft)]",
              )}
            >
              <span className="min-w-0 flex-1 truncate font-medium">{row.name}</span>
              <span className="code shrink-0 text-xs text-ink-muted">{row.aicte_permanent_id}</span>
              <span className="w-6 shrink-0 text-xs text-ink-muted">{row.state_code}</span>
              <span className="num w-14 shrink-0 text-right text-xs text-ink-muted" title="Open flags">
                {formatCount(row.flags_open)} flags
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
