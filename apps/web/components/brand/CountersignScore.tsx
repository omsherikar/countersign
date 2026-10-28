import * as React from "react";
import { scoreText, stripAria } from "@/lib/checks";
import { t } from "@/lib/copy";
import { cn } from "@/lib/utils";

import type { CheckStatus, CheckType, Countersign } from "@/lib/types";

export type { CheckStatus, CheckType, Countersign };

/** Display order is fixed by ARCHITECTURE.md section 9. */
export const CHECK_ORDER: CheckType[] = ["IDENTITY", "ADMISSION", "SEAT", "STUDYING", "STUDENT"];


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
        <span className="countersign-score__empty">{t("strip.not_checked")}</span>
      </span>
    );
  }

  const aria = stripAria(countersign);

  return (
    <span className={cn("countersign-score", sizeClass, className)} role="img" aria-label={aria} title={scoreText(countersign)} {...rest}>
      <span className="countersign-score__value">
        {score.passes}
        <span className="countersign-score__of">of</span>
        {score.applicable}
      </span>
      {!numberOnly && (
        <span className="countersign-score__checks" aria-hidden="true">
          {CHECK_ORDER.map((type) => {
            const c = byType.get(type);
            return <span key={type} className="countersign-score__check" data-status={c?.status ?? "PENDING"} />;
          })}
        </span>
      )}
    </span>
  );
}
