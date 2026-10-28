import { CircleCheck, CircleDashed, CircleX, LoaderCircle } from "lucide-react";
import { tk } from "@/lib/copy";
import type { UploadStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Upload status as an icon and the deck word; colour is never the only signal. */
export function UploadStatusWord({ status, className }: { status: UploadStatus; className?: string }) {
  const Icon = status === "DONE" ? CircleCheck : status === "FAILED" ? CircleX : status === "QUEUED" ? CircleDashed : LoaderCircle;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-xs font-medium",
        status === "DONE" && "text-ink",
        status === "FAILED" && "text-check-fail-ink",
        (status === "VALIDATING" || status === "PROCESSING") && "text-ink-blue",
        status === "QUEUED" && "text-ink-muted",
        className,
      )}
    >
      <Icon className={cn("size-3.5", (status === "VALIDATING" || status === "PROCESSING") && "animate-spin motion-reduce:animate-none")} aria-hidden="true" />
      {tk(`upload_status.${status}`)}
    </span>
  );
}
