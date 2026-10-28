"use client";

import * as React from "react";
import { Check } from "lucide-react";
import { t } from "@/lib/copy";
import { useOfficers } from "@/lib/queries-cases";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBlock } from "@/components/common/query-state";
import { useMe } from "@/components/providers/root-provider";
import { roleWordOf } from "@/components/cases/case-words";

export interface AssigneePick {
  id: string | null;
  name: string | null;
}

interface Option extends AssigneePick {
  key: string;
  label: string;
}

/**
 * "Assign to": a text box that filters the officers who may hold this flag
 * (GET /users with flag_id), with Assign to me first and Remove assignee
 * last. Arrow keys move, Enter chooses; the list stays open inside the sheet.
 */
export const AssigneeCombobox = React.forwardRef<
  HTMLInputElement,
  { flagId: string; value: AssigneePick | undefined; onChange: (pick: AssigneePick) => void; error?: string | null }
>(function AssigneeCombobox({ flagId, value, onChange, error }, ref) {
  const officers = useOfficers(flagId);
  const { user } = useMe();
  const [q, setQ] = React.useState("");
  const [active, setActive] = React.useState(0);
  // "Assign to me" and my own row name the same officer; only the one chosen is marked.
  const [chosenKey, setChosenKey] = React.useState<string | null>(null);
  const id = React.useId();
  const listId = `${id}-list`;
  const errorId = `${id}-error`;

  const text = q.trim().toLowerCase();
  const all = officers.data ?? [];
  const me = user ? all.find((o) => o.id === user.id) : undefined;
  const matches = all.filter((o) => !text || o.name.toLowerCase().includes(text));
  const options: Option[] = [
    ...(me ? [{ key: "me", id: me.id, name: me.name, label: t("case.assign_me") }] : []),
    ...matches.map((o) => ({ key: o.id, id: o.id, name: o.name, label: t("case.assign_option", { name: o.name, role_word: roleWordOf(o.role, o.region) }) })),
    { key: "none", id: null, name: null, label: t("case.assign_none") },
  ];
  const at = Math.min(active, options.length - 1);
  const optionId = (i: number) => `${id}-opt-${i}`;

  function choose(o: Option) {
    setChosenKey(o.key);
    onChange({ id: o.id, name: o.name });
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      setActive(Math.min(options.length - 1, at + 1));
      e.preventDefault();
    } else if (e.key === "ArrowUp") {
      setActive(Math.max(0, at - 1));
      e.preventDefault();
    } else if (e.key === "Home") {
      setActive(0);
      e.preventDefault();
    } else if (e.key === "End") {
      setActive(options.length - 1);
      e.preventDefault();
    } else if (e.key === "Enter") {
      const o = options[at];
      // Enter on a new choice picks it; Enter on the current choice submits the sheet.
      if (o && !(value && chosenKey === o.key)) {
        choose(o);
        e.preventDefault();
      }
    }
  }

  React.useEffect(() => {
    document.getElementById(optionId(at))?.scrollIntoView({ block: "nearest" });
    // optionId only depends on the stable id.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [at]);

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={`${id}-input`} className="text-sm font-medium">
        {t("case.assign_label")}
      </label>
      <input
        ref={ref}
        id={`${id}-input`}
        type="text"
        role="combobox"
        aria-expanded="true"
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={options.length ? optionId(at) : undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        autoComplete="off"
        placeholder={t("case.assign_search")}
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setActive(0);
        }}
        onKeyDown={onKeyDown}
        className="h-10 w-full rounded-md border border-line bg-paper-raised px-2.5 text-md placeholder:text-ink-faint md:text-sm"
      />
      {officers.isLoading ? (
        <div className="flex flex-col gap-2 py-2" aria-hidden="true">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-4 w-64" />
          <Skeleton className="h-4 w-40" />
        </div>
      ) : officers.isError ? (
        <ErrorBlock error={officers.error} onRetry={() => officers.refetch()} compact />
      ) : (
        <ul id={listId} role="listbox" aria-label={t("case.assign_label")} className="max-h-60 overflow-y-auto rounded-md border border-line bg-paper-raised py-1">
          {options.map((o, i) => {
            const selected = value !== undefined && chosenKey === o.key;
            return (
              <li
                key={o.key}
                id={optionId(i)}
                role="option"
                aria-selected={selected}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  setActive(i);
                  choose(o);
                }}
                className={cn(
                  "flex min-h-10 cursor-pointer items-center gap-2 px-2.5 text-sm",
                  i === at && "bg-flag-open-soft",
                  o.key === "none" && "border-t border-rule text-ink-muted",
                )}
              >
                <Check className={cn("size-4 shrink-0 text-ink-blue", !selected && "invisible")} aria-hidden="true" />
                <span className="min-w-0 truncate">{o.label}</span>
              </li>
            );
          })}
          {text && matches.length === 0 && (
            <li role="presentation" className="px-2.5 py-2 text-sm text-ink-muted">
              {t("case.assign_empty", { q: q.trim() })}
            </li>
          )}
        </ul>
      )}
      {error && (
        <p id={errorId} className="text-sm text-check-fail-ink">
          {error}
        </p>
      )}
    </div>
  );
});
