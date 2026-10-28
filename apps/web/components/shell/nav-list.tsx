"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { t } from "@/lib/copy";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { isActive, type NavItem } from "@/components/shell/nav-config";

/**
 * Role navigation. Items not yet available (`available: false` in
 * nav-config) are shown but never navigate: aria-disabled, with "Coming in
 * Week N" in a tooltip and as a visible tag so nothing depends on hover.
 */
export function NavList({
  items,
  orientation = "vertical",
  onNavigate,
}: {
  items: NavItem[];
  orientation?: "vertical" | "horizontal";
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const vertical = orientation === "vertical";
  return (
    <ul className={cn(vertical ? "flex flex-col gap-0.5" : "flex items-center gap-1 overflow-x-auto")}>
      {items.map((item) => {
        const Icon = item.icon;
        const label = t(item.label);
        const base = cn(
          "group flex items-center gap-2.5 rounded-md text-sm whitespace-nowrap",
          vertical ? "h-9 px-2.5" : "h-11 px-3",
        );
        if (!item.available) {
          const coming = t("shell.coming", { n: item.week });
          return (
            <li key={item.href}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    aria-disabled="true"
                    aria-label={`${label}. ${coming}`}
                    onClick={(e) => e.preventDefault()}
                    className={cn(base, "w-full cursor-not-allowed text-ink-faint")}
                  >
                    <Icon className="size-4 shrink-0" aria-hidden="true" />
                    <span className="truncate">{label}</span>
                    <span className="ml-auto shrink-0 text-2xs text-ink-faint">Week {item.week}</span>
                  </button>
                </TooltipTrigger>
                <TooltipContent side={vertical ? "right" : "bottom"}>{coming}</TooltipContent>
              </Tooltip>
            </li>
          );
        }
        const active = isActive(item, pathname);
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              aria-current={active ? "page" : undefined}
              onClick={onNavigate}
              className={cn(
                base,
                "no-underline",
                active
                  ? "bg-paper-raised font-medium text-ink shadow-hairline ring-1 ring-line"
                  : "text-ink-muted hover:bg-paper-raised/70 hover:text-ink",
              )}
            >
              <Icon className={cn("size-4 shrink-0", active ? "text-ink-blue" : "")} aria-hidden="true" />
              <span className="truncate">{label}</span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
