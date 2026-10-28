"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { formatRange } from "@/lib/format";
import { Button } from "@/components/ui/button";

/** "1 to 25 of 571" with previous and next; sits in the table footer. */
export function Pager({
  page,
  pageSize,
  total,
  onPage,
  busy = false,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
  busy?: boolean;
}) {
  const last = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex items-center gap-2">
      <span className="num text-xs text-ink-muted" aria-live="polite">
        {formatRange(page, pageSize, total)}
      </span>
      <Button
        variant="outline"
        size="icon"
        className="size-8"
        aria-label="Previous page"
        disabled={page <= 1 || busy}
        onClick={() => onPage(page - 1)}
      >
        <ChevronLeft className="size-4" aria-hidden="true" />
      </Button>
      <span className="num text-xs text-ink-muted">
        Page {page} of {last}
      </span>
      <Button
        variant="outline"
        size="icon"
        className="size-8"
        aria-label="Next page"
        disabled={page >= last || busy}
        onClick={() => onPage(page + 1)}
      >
        <ChevronRight className="size-4" aria-hidden="true" />
      </Button>
    </div>
  );
}
