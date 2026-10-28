import * as React from "react";
import { cn } from "@/lib/utils";

/** Mirrors `Check`, `CheckStatus`, `CheckType` and `Countersign` in lib/types.ts. */
export type CheckType = "IDENTITY" | "ADMISSION" | "SEAT" | "STUDYING" | "STUDENT";
export type CheckStatus = "PASS" | "FAIL" | "PENDING" | "NA";
export interface Check {
  type: CheckType;
  status: CheckStatus;
  source: string;
  checked_at: string | null;
  detail: Record<string, unknown>;
}
export interface Countersign {
  score: { passes: number; applicable: number } | null;
  checks: Check[];
}

/** Display order is fixed by ARCHITECTURE.md section 9. */
export const CHECK_ORDER: CheckType[] = ["IDENTITY", "ADMISSION", "SEAT", "STUDYING", "STUDENT"];

const TYPE_LABEL: Record<CheckType, string> = {
  IDENTITY: "Identity",
  ADMISSION: "Admission",
  SEAT: "Seat",
  STUDYING: "Studying",
  STUDENT: "Student",
};
const STATUS_LABEL: Record<CheckStatus, string> = {
  PASS: "pass",
  FAIL: "fail",
  PENDING: "pending",
  NA: "not applicable",
};

export interface CountersignScoreProps extends React.HTMLAttributes<HTMLSpanElement> {
  countersign: Countersign;
  /** sm for table rows, md for lists and cards, lg for the detail page header. */
  size?: "sm" | "md" | "lg";
  /** Hide the five glyphs and show only "4 of 5". */
  numberOnly?: boolean;
}

/**
 * "4 of 5" with five small glyphs, one per countersignature, in display
 * order. Styling lives in globals.css (.countersign-score) so the same look
 * is available outside React. A null score renders "Not yet countersigned"
 * rather than a misleading zero.
 */
export function CountersignScore({ countersign, size = "md", numberOnly = false, className, ...rest }: CountersignScoreProps) {
  const { score, checks } = countersign;
  const byType = new Map(checks.map((c) => [c.type, c]));
  const sizeClass = size === "sm" ? "countersign-score--sm" : size === "lg" ? "countersign-score--lg" : undefined;

  if (!score) {
    return (
      <span className={cn("countersign-score", sizeClass, className)} {...rest}>
        <span className="countersign-score__empty">{size === "sm" ? "Not yet" : "Not yet countersigned"}</span>
      </span>
    );
  }

  const summary = CHECK_ORDER.map((t) => {
    const c = byType.get(t);
    return `${TYPE_LABEL[t]} ${c ? STATUS_LABEL[c.status] : "pending"}`;
  }).join(", ");

  return (
    <span
      className={cn("countersign-score", sizeClass, className)}
      role="img"
      aria-label={`Countersigned ${score.passes} of ${score.applicable}. ${summary}.`}
      title={summary}
      {...rest}
    >
      <span className="countersign-score__value">
        {score.passes}
        <span className="countersign-score__of">of</span>
        {score.applicable}
      </span>
      {!numberOnly && (
        <span className="countersign-score__checks" aria-hidden="true">
          {CHECK_ORDER.map((t) => {
            const c = byType.get(t);
            return <span key={t} className="countersign-score__check" data-status={c?.status ?? "PENDING"} />;
          })}
        </span>
      )}
    </span>
  );
}
