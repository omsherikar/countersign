import { MailCheck } from "lucide-react";
import { t } from "@/lib/copy";
import { cn } from "@/lib/utils";

/** "Response received": the college answered a document request. A word and a glyph, never colour alone. */
export function ResponseBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center gap-1 rounded-chip border border-flag-open/40 bg-flag-open-soft px-1.5 text-xs leading-none font-medium whitespace-nowrap text-flag-open-ink",
        className,
      )}
    >
      <MailCheck className="size-3 shrink-0" aria-hidden="true" />
      {t("case.response_badge")}
    </span>
  );
}
