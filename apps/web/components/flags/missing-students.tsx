import { t, tk } from "@/lib/copy";
import { formatDate } from "@/lib/format";
import type { MissingStudent } from "@/lib/types";
import { EmptyState } from "@/components/brand/EmptyState";

/** The masked APAAR, or the authority's roll number cut to its last four, never a full id (D40). */
function maskedId(m: MissingStudent): string {
  if (m.apaar_masked) return m.apaar_masked;
  if (m.roll_no) return `Roll XXXX${m.roll_no.slice(-4)}`;
  return "";
}

/**
 * Students the state admission authority lists as joined but the college's
 * uploads leave out, as a Missing from upload case names them (A4.11).
 * Phones get a list; from 640 px a table scrolling inside its container.
 */
export function MissingStudentsTable({ rows }: { rows: MissingStudent[] }) {
  if (rows.length === 0) {
    return (
      <div className="border-l-2 border-rule-margin bg-paper-raised">
        <EmptyState title={t("missing.none")} />
      </div>
    );
  }
  return (
    <>
      <ul className="flex flex-col divide-y divide-rule border-l-2 border-rule-margin bg-paper-raised text-md sm:hidden">
        {rows.map((m, i) => (
          <li key={`${m.name}-${i}`} className="px-3 py-2.5">
            <p className="font-medium">{m.name}</p>
            <p className="code text-sm text-ink-muted">{maskedId(m)}</p>
            <p className="text-sm text-ink-muted">
              {m.programme_code} · {formatDate(m.joined_on)}
              {m.round !== null ? ` · ${m.round}` : ""}
            </p>
          </li>
        ))}
      </ul>
      <div className="relative hidden overflow-x-auto border-l-2 border-rule-margin bg-paper-raised sm:block">
        <table className="ledger-table">
          <caption className="sr-only">{t("missing.heading", { n: rows.length })}</caption>
          <thead>
            <tr>
              <th scope="col">{t("missing.col.student")}</th>
              <th scope="col" className="code">
                {t("col.apaar")}
              </th>
              <th scope="col" className="code">
                {t("missing.col.programme")}
              </th>
              <th scope="col">{t("missing.col.joined_on")}</th>
              <th scope="col" className="num">
                {t("missing.col.round")}
              </th>
              <th scope="col">{t("col.route")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((m, i) => (
              <tr key={`${m.name}-${i}`}>
                <td className="font-medium">{m.name}</td>
                <td className="code">{maskedId(m)}</td>
                <td className="code">{m.programme_code}</td>
                <td>{formatDate(m.joined_on)}</td>
                <td className="num">{m.round ?? ""}</td>
                <td>{tk(`route.${m.route}`)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
