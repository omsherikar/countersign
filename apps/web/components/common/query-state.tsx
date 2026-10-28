"use client";

import * as React from "react";
import Link from "next/link";
import { RefreshCw, TriangleAlert } from "lucide-react";
import { ApiError } from "@/lib/api";
import { t } from "@/lib/copy";
import { joinWords } from "@/lib/format";
import { ROLE_PLURAL, ROLE_SINGULAR } from "@/lib/roles";
import type { Role } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useMe } from "@/components/providers/root-provider";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

/** "Still loading" under a skeleton once a request runs past 3 s. */
export function SlowHint({ className }: { className?: string }) {
  const [slow, setSlow] = React.useState(false);
  React.useEffect(() => {
    const id = setTimeout(() => setSlow(true), 3000);
    return () => clearTimeout(id);
  }, []);
  if (!slow) return null;
  return (
    <p className={cn("mt-2 text-xs text-ink-muted", className)} role="status">
      {t("shell.loading_slow")}
    </p>
  );
}

/** Message for an ApiError, using the deck wording per code and the envelope message otherwise. */
export type ErrorEntity = "institution" | "enrolment" | "flag" | "upload";

export function errorMessage(err: unknown, role?: Role | null, entity?: ErrorEntity): string {
  if (!(err instanceof ApiError)) return t("err.INTERNAL");
  switch (err.code) {
    case "NETWORK":
      return t("err.NETWORK");
    case "UNAUTHENTICATED":
      return t("err.UNAUTHENTICATED");
    case "FORBIDDEN": {
      const required = Array.isArray(err.details.required_roles) ? (err.details.required_roles as Role[]) : [];
      if (required.length && role) {
        return t("err.FORBIDDEN", {
          required_roles_words: joinWords(required.map((r) => ROLE_PLURAL[r] ?? r)),
          role_word: ROLE_SINGULAR[role],
        });
      }
      return err.message;
    }
    case "NOT_FOUND":
      return entity ? t(`err.NOT_FOUND_${entity}`) : err.message || t("err.NOT_FOUND_generic");
    case "RATE_LIMITED":
      return err.retryAfter !== null ? t("err.RATE_LIMITED", { seconds: err.retryAfter }) : err.message;
    case "INTERNAL":
      return t("err.INTERNAL");
    default:
      return err.message || t("err.INTERNAL");
  }
}

function errorCode(err: unknown): string {
  return err instanceof ApiError ? err.code : "INTERNAL";
}

/**
 * Inline error card: the envelope message, "Try again" and the error code
 * as a reference. 404 and 403 offer a way back instead of a retry.
 */
export function ErrorBlock({
  error,
  onRetry,
  entity,
  backHref,
  backLabel,
  className,
  compact = false,
}: {
  error: unknown;
  onRetry?: () => void;
  entity?: ErrorEntity;
  backHref?: string;
  /** Words on the way-back button; defaults to "Back to overview". */
  backLabel?: string;
  className?: string;
  compact?: boolean;
}) {
  const { user } = useMe();
  const code = errorCode(error);
  const message = errorMessage(error, user?.role, entity);
  const final = code === "NOT_FOUND" || code === "FORBIDDEN";
  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-3 rounded-md border border-check-fail/30 bg-paper-raised text-sm",
        compact ? "px-3 py-2.5" : "px-4 py-4",
        className,
      )}
    >
      <TriangleAlert className="mt-0.5 size-4 shrink-0 text-check-fail" aria-hidden="true" />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <p className="text-ink">{message}</p>
        <div className="flex flex-wrap items-center gap-3">
          {final && backHref ? (
            <Button asChild variant="outline" size="sm">
              <Link href={backHref}>{code === "FORBIDDEN" ? t("err.go_home") : (backLabel ?? t("err.back_overview"))}</Link>
            </Button>
          ) : (
            onRetry && (
              <Button variant="outline" size="sm" onClick={onRetry}>
                <RefreshCw className="size-3.5" aria-hidden="true" />
                {t("err.retry")}
              </Button>
            )
          )}
          <span className="code text-xs text-ink-muted">{t("err.ref", { code })}</span>
        </div>
      </div>
    </div>
  );
}

/** Skeleton rows for a ledger table body, sized like the real rows. */
export function SkeletonRows({ rows = 8, cols }: { rows?: number; cols: number }) {
  return (
    <>
      {Array.from({ length: rows }, (_, r) => (
        <tr key={r} aria-hidden="true">
          {Array.from({ length: cols }, (_, c) => (
            <td key={c}>
              <Skeleton className={cn("h-3.5", c === 0 ? "w-40" : "w-12", c > 0 && "ml-auto")} />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

/** Table body placeholder for empty and error states, spanning every column. */
export function TableMessage({ cols, children }: { cols: number; children: React.ReactNode }) {
  return (
    <tr>
      <td colSpan={cols} className="!h-auto !whitespace-normal !p-0">
        {children}
      </td>
    </tr>
  );
}
