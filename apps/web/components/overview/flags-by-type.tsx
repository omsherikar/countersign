"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { YAxisTickContentProps } from "recharts/types/util/types";
import { EmptyState } from "@/components/brand/EmptyState";
import { t, tk } from "@/lib/copy";
import { formatCount, singular } from "@/lib/format";
import type { DashboardSummary, FlagType } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

const ROW = 30;

interface Row {
  type: FlagType;
  name: string;
  open: number;
  href: string;
}

/** A y-axis label that is also a link to the case queue for that type; keyboard and pointer both work. */
function TypeTick({ x, y, payload, rows, onOpen }: { x: number | string; y: number | string; payload: { value: unknown }; rows: Row[]; onOpen: (href: string) => void }) {
  const row = rows.find((r) => r.name === payload?.value);
  if (!row) return null;
  return (
    <a
      href={row.href}
      aria-label={t("flags_by_type.link", { type_name: row.name })}
      onClick={(e) => {
        e.preventDefault();
        onOpen(row.href);
      }}
      className="cursor-pointer [&:focus-visible]:outline-2 [&:focus-visible]:outline-ink-blue [&:hover_text]:underline"
    >
      <text x={Number(x) - 8} y={Number(y)} dy="0.32em" textAnchor="end" fill="var(--ink)" fontSize={13}>
        {row.name}
      </text>
    </a>
  );
}

function TipBox({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded-md border border-line bg-paper-raised px-3 py-2 text-xs text-ink shadow-md">
      <p className="font-medium">{row.name}</p>
      <p className="num text-ink-muted">{singular(t("flags_by_type.total", { total: formatCount(row.open) }))}</p>
    </div>
  );
}

/**
 * Open flags by type (page spec W2-9): one series, so one colour (chart-1)
 * and no legend. Types with no open flag are left out; every bar and every
 * label opens the case queue filtered to that type. Counts are printed in
 * ink at the end of each bar, so the chart reads without hovering.
 */
export function FlagsByType({ summary, loading, casesHref }: { summary: DashboardSummary | undefined; loading: boolean; casesHref: string }) {
  const router = useRouter();
  if (loading) return <Skeleton className="h-56 max-w-3xl" />;
  if (!summary) return null;
  const rows: Row[] = (summary.flags_by_type ?? [])
    .filter((r) => r.open > 0)
    .map((r) => ({ type: r.type, name: tk(`flag.${r.type}.name`), open: r.open, href: `${casesHref}?f_type=${r.type}` }));
  if (rows.length === 0) {
    return (
      <div className="border-l-2 border-rule-margin bg-paper-raised">
        <EmptyState title={t("empty.flags_by_type", { academic_year: summary.academic_year })} />
      </div>
    );
  }
  const total = rows.reduce((a, r) => a + r.open, 0);
  const open = (href: string) => router.push(href);
  const label = `${t("section.flags_by_type")}: ${rows.map((r) => `${r.name} ${r.open}`).join(", ")}`;
  return (
    <figure className="max-w-3xl border-l-2 border-rule-margin bg-paper-raised py-3 pr-4">
      <div role="img" aria-label={label} style={{ height: rows.length * ROW + 36 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 40, bottom: 4, left: 8 }} barCategoryGap={8}>
            <CartesianGrid horizontal={false} stroke="var(--chart-grid)" strokeDasharray="0" />
            <XAxis type="number" allowDecimals={false} tick={{ fill: "var(--ink-muted)", fontSize: 11 }} axisLine={{ stroke: "var(--chart-axis)" }} tickLine={false} />
            <YAxis
              type="category"
              dataKey="name"
              width={230}
              axisLine={{ stroke: "var(--chart-axis)" }}
              tickLine={false}
              interval={0}
              tick={(props: YAxisTickContentProps) => <TypeTick x={props.x} y={props.y} payload={props.payload} rows={rows} onOpen={open} />}
            />
            <Tooltip cursor={{ fill: "var(--chart-grid)", opacity: 0.4 }} content={<TipBox />} />
            <Bar dataKey="open" fill="var(--chart-1)" barSize={16} radius={[0, 4, 4, 0]} isAnimationActive={false} onClick={(d: { payload?: Row }) => d.payload && open(d.payload.href)} className="cursor-pointer">
              <LabelList dataKey="open" position="right" offset={8} fill="var(--ink)" fontSize={12} fontWeight={600} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 pl-4 text-xs text-ink-muted">{singular(t("flags_by_type.total", { total: formatCount(total) }))}</figcaption>
    </figure>
  );
}
