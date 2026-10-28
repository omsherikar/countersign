import * as React from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";

export interface Crumb {
  label: string;
  href?: string;
}

/** "Overview / ABC College of Engineering"; the last crumb is plain text. */
export function Crumbs({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="mb-2 text-sm text-ink-muted">
      <ol className="flex flex-wrap items-center gap-1.5">
        {items.map((c, i) => (
          <li key={`${c.label}-${i}`} className="flex min-w-0 items-center gap-1.5">
            {i > 0 && (
              <span aria-hidden="true" className="text-ink-faint">
                /
              </span>
            )}
            {c.href && i < items.length - 1 ? (
              <Link href={c.href} className="truncate text-ink-blue hover:underline">
                {c.label}
              </Link>
            ) : (
              <span aria-current={i === items.length - 1 ? "page" : undefined} className="truncate">
                {c.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

/** h1 on the left, page-level controls on the right. */
export function PageHeader({
  title,
  description,
  actions,
  className,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-6 flex flex-wrap items-end justify-between gap-x-6 gap-y-3", className)}>
      <div className="min-w-0">
        <h1 className="text-2xl md:text-3xl">{title}</h1>
        {description && <div className="mt-1.5 text-sm text-ink-muted">{description}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/** h2 with an optional count or control on the right. */
export function SectionHeader({
  id,
  title,
  aside,
  className,
}: {
  id?: string;
  title: React.ReactNode;
  aside?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2", className)}>
      <h2 id={id} className="text-xl">
        {title}
      </h2>
      {aside && <div className="flex flex-wrap items-center gap-2 text-sm text-ink-muted">{aside}</div>}
    </div>
  );
}
