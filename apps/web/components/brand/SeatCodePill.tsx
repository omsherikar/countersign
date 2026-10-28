import * as React from "react";
import { cn } from "@/lib/utils";

/** Mirrors `SeatStatus` and `SeatType` in lib/types.ts. */
export type SeatStatus = "FREE" | "ASSIGNED" | "RELEASED";
export type SeatType = "REGULAR" | "NRI" | "TFW" | "LATERAL" | "INTERNATIONAL";

export const SEAT_STATUS_LABEL: Record<SeatStatus, string> = {
  FREE: "Free",
  ASSIGNED: "Assigned",
  RELEASED: "Released",
};

/** Seat code letter to pool, from ARCHITECTURE.md section 9. */
export const SEAT_TYPE_FROM_LETTER: Record<string, SeatType> = {
  R: "REGULAR",
  N: "NRI",
  T: "TFW",
  L: "LATERAL",
  I: "INTERNATIONAL",
};

const STYLE: Record<SeatStatus, string> = {
  FREE: "bg-seat-free-soft text-seat-free-ink border-seat-free/50 border-dashed",
  ASSIGNED: "bg-seat-assigned-soft text-seat-assigned-ink border-seat-assigned/40",
  RELEASED: "bg-seat-released-soft text-seat-released-ink border-seat-released/40",
};

export interface SeatCodePillProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** `<PROGRAMME>-<R|N|T|L|I>-<NNN>`, e.g. "CSE-R-087". */
  seatCode: string;
  status?: SeatStatus;
  /** Show the status word after the code (default: status is in the title only). */
  showStatus?: boolean;
}

/**
 * A seat code in the mono face, segmented so the pool letter stands out.
 * A free seat is drawn with a dashed border: an empty line in the ledger.
 */
export function SeatCodePill({ seatCode, status, showStatus = false, className, ...rest }: SeatCodePillProps) {
  const parts = seatCode.split("-");
  const pool = parts.length === 3 ? SEAT_TYPE_FROM_LETTER[parts[1]] : undefined;
  const title = [seatCode, pool, status ? SEAT_STATUS_LABEL[status] : undefined].filter(Boolean).join(", ");
  return (
    <span
      title={title}
      className={cn(
        "inline-flex h-5 items-center gap-1 whitespace-nowrap rounded-chip border px-1.5 font-mono text-xs leading-none tracking-wide",
        status ? STYLE[status] : "bg-paper-raised text-ink border-line",
        className,
      )}
      {...rest}
    >
      {parts.length === 3 ? (
        <span>
          {parts[0]}
          <span className="opacity-50">-</span>
          <span className="font-medium">{parts[1]}</span>
          <span className="opacity-50">-</span>
          {parts[2]}
        </span>
      ) : (
        <span>{seatCode}</span>
      )}
      {showStatus && status && <span className="font-sans font-medium opacity-80">{SEAT_STATUS_LABEL[status]}</span>}
      {!showStatus && status && <span className="sr-only">{SEAT_STATUS_LABEL[status]}</span>}
    </span>
  );
}
