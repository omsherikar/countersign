/**
 * Number and date formatting for every page.
 * Counts use Indian digit grouping (1,20,000). Dates read "14 Jul 2026" and
 * timestamps "14 Jul 2026, 09:30 IST", always in India Standard Time so the
 * server render and the browser agree.
 */

const COUNT = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const TZ = "Asia/Kolkata";

const DATE = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: TZ });
const TIME = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: TZ });
const TIME_SECONDS = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
  timeZone: TZ,
});

/** ICU writes September as "Sept" in en-GB and en-IN; the deck and the api sentences say "Sep". */
const fmtDay = (d: Date) => DATE.format(d).replace(/\bSept\b/, "Sep");

export function formatCount(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "";
  return COUNT.format(n);
}

/** Accepts `YYYY-MM-DD` or an ISO timestamp. Plain dates are read as calendar dates, not midnight UTC. */
function toDate(value: string): Date {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return new Date(`${value}T12:00:00+05:30`);
  return new Date(value);
}

/** "14 Jul 2026" */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "";
  const d = toDate(value);
  return Number.isNaN(d.getTime()) ? value : fmtDay(d);
}

/** "14 Jul 2026, 09:30 IST" */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "";
  const d = toDate(value);
  if (Number.isNaN(d.getTime())) return value;
  return `${fmtDay(d)}, ${TIME.format(d)} IST`;
}

/** "09:30:12" in IST, for "Checked" lines on the system page. */
export function formatClock(value: string | null | undefined): string {
  if (!value) return "";
  const d = toDate(value);
  return Number.isNaN(d.getTime()) ? value : TIME_SECONDS.format(d);
}

/** "just now", "2 min ago", "3 h ago"; used only in the Sources panel, with the absolute time on hover. */
export function formatRelative(value: string | null | undefined, now: number): string {
  if (!value) return "";
  const then = toDate(value).getTime();
  if (Number.isNaN(then)) return value;
  const seconds = Math.max(0, Math.round((now - then) / 1000));
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return formatDate(value);
}

/** "1 to 25 of 571" */
export function formatRange(page: number, pageSize: number, total: number): string {
  if (total === 0) return "0 of 0";
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  return `${formatCount(from)} to ${formatCount(to)} of ${formatCount(total)}`;
}

/** "18 ms", "3,004 ms" */
export function formatLatency(ms: number): string {
  return `${formatCount(ms)} ms`;
}

/** Join role words: "AICTE officers and regional officers". */
export function joinWords(words: string[]): string {
  if (words.length <= 1) return words.join("");
  return `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;
}
