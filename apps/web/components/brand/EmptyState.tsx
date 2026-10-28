import * as React from "react";
import { cn } from "@/lib/utils";

export interface EmptyStateProps extends React.HTMLAttributes<HTMLDivElement> {
  /** What is absent, as a plain statement: "No flags open". */
  title: string;
  /** Why, or what would change it: "Flags appear after the first upload is checked." */
  description?: string;
  /** A lucide icon element, e.g. <Inbox className="size-5" />. */
  icon?: React.ReactNode;
  /** One action at most: a shadcn <Button>. */
  action?: React.ReactNode;
  /** "page" for a whole empty view, "inline" for an empty table body or panel. */
  variant?: "page" | "inline";
}

/**
 * An empty ledger page: a short ruled block, a plain statement of what is
 * absent, and at most one thing to do about it. No illustrations, no mood.
 * Use "coming in Week N" wording for routes whose endpoints are absent.
 */
export function EmptyState({ title, description, icon, action, variant = "inline", className, ...rest }: EmptyStateProps) {
  return (
    <div
      role="status"
      className={cn(
        "flex flex-col items-center justify-center text-center",
        variant === "page" ? "min-h-[40vh] gap-3 px-6 py-12" : "gap-2 px-4 py-10",
        className,
      )}
      {...rest}
    >
      {icon && <span className="text-ink-faint" aria-hidden="true">{icon}</span>}
      <p className={cn("font-display font-semibold text-ink", variant === "page" ? "text-xl" : "text-md")}>{title}</p>
      {description && <p className="max-w-[48ch] text-sm text-ink-muted">{description}</p>}
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}
