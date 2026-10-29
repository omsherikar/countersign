"use client";

import * as React from "react";
import { Check } from "lucide-react";
import { copy, t, type CopyId, type CopyVars } from "@/lib/copy";
import { cn } from "@/lib/utils";
import { Logo } from "@/components/shell/logo";

export type Lang = "en" | "hi";
const LANG_KEY = "cs_notice_lang";

/** English or the `.hi` row of the deck; a string without one falls back to English (deck sections 8 and 23). */
export function makeTr(lang: Lang) {
  return (id: CopyId, vars?: CopyVars): string => {
    const hi = `${id}.hi`;
    if (lang === "hi" && hi in copy) return t(hi as CopyId, vars);
    return t(id, vars);
  };
}
export type Tr = ReturnType<typeof makeTr>;

const langListeners = new Set<() => void>();
function readLang(): Lang {
  try {
    return sessionStorage.getItem(LANG_KEY) === "hi" ? "hi" : "en";
  } catch {
    return "en";
  }
}
function subscribeLang(onChange: () => void) {
  langListeners.add(onChange);
  return () => langListeners.delete(onChange);
}

/**
 * The language choice lasts for the visit (W3-1): kept in sessionStorage,
 * English on the server, and carried from the notice page into the
 * DigiLocker return page and the claim page (W4-8).
 */
export function useLang(): [Lang, (l: Lang) => void] {
  const lang = React.useSyncExternalStore(subscribeLang, readLang, () => "en" as Lang);
  const set = React.useCallback((l: Lang) => {
    try {
      sessionStorage.setItem(LANG_KEY, l);
    } catch {
      // Storage refused: the choice cannot be kept, so the page stays in English.
    }
    langListeners.forEach((fn) => fn());
  }, []);
  return [lang, set];
}

/** The public pages' header: the mark and the English / Hindi toggle. */
export function PublicHeader({ lang, setLang, tr }: { lang: Lang; setLang: (l: Lang) => void; tr: Tr }) {
  return (
    <header className="border-b border-rule-strong bg-paper-raised">
      <div className="mx-auto flex h-14 max-w-[480px] items-center justify-between gap-3 px-4">
        <Logo className="h-7" />
        <div role="group" aria-label={tr("notice.lang_label")} className="flex rounded-md border border-line p-0.5">
          {(["en", "hi"] as const).map((l) => (
            <button
              key={l}
              type="button"
              lang={l === "hi" ? "hi" : "en"}
              aria-pressed={lang === l}
              onClick={() => setLang(l)}
              className={cn(
                "inline-flex h-10 min-w-11 items-center justify-center gap-1 rounded-[3px] px-3 text-sm font-medium",
                lang === l ? "bg-ink-blue text-on-ink-blue" : "text-ink-blue hover:bg-flag-open-soft",
              )}
            >
              {lang === l && <Check className="size-3.5" aria-hidden="true" />}
              {t(l === "hi" ? "notice.lang_hi" : "notice.lang_en")}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}
