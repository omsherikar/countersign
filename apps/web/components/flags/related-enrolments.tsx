"use client";

import Link from "next/link";
import { MaskedApaar } from "@/components/brand/MaskedApaar";
import { SeatCodePill } from "@/components/brand/SeatCodePill";
import { t, tk } from "@/lib/copy";
import type { RelatedEnrolmentRow } from "@/lib/types";
import { CountersignStrip, UnseatedChip } from "@/components/common/ledger-bits";
import { FlagChips } from "@/components/flags/flag-chip";

/** Enrolment rows with an Institution column, for flag detail (W2-8). */
export function RelatedEnrolmentsTable({
  rows,
  caption,
  enrolmentHref,
  flagHref,
}: {
  rows: RelatedEnrolmentRow[];
  caption: string;
  enrolmentHref: (id: string) => string;
  flagHref?: (id: string) => string;
}) {
  return (
    <div className="relative overflow-x-auto border-l-2 border-rule-margin bg-paper-raised">
      <table className="ledger-table">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">{t("col.student")}</th>
            <th scope="col" className="code">
              {t("col.apaar")}
            </th>
            <th scope="col">{t("col.institution")}</th>
            <th scope="col" className="code">
              {t("col.programme")}
            </th>
            <th scope="col" className="num">
              {t("col.year")}
            </th>
            <th scope="col">{t("col.route")}</th>
            <th scope="col" className="code">
              {t("col.seat")}
            </th>
            <th scope="col">{t("col.countersign")}</th>
            <th scope="col">{t("col.flags")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((e) => (
            <tr key={e.id}>
              <td className="font-medium">
                <Link href={enrolmentHref(e.id)}>{e.student.name}</Link>
              </td>
              <td className="code">
                <MaskedApaar apaarMasked={e.student.apaar_masked} provisionalId={e.student.provisional_id} />
              </td>
              <td className="wrap max-w-[16rem] min-w-[10rem] text-ink-muted">{e.institution.name}</td>
              <td className="code">{e.programme_code}</td>
              <td className="num">{e.year_of_study}</td>
              <td>{tk(`route.${e.admission_route}`)}</td>
              <td className="code">{e.seat_code ? <SeatCodePill seatCode={e.seat_code} status="ASSIGNED" /> : <UnseatedChip />}</td>
              <td>
                <CountersignStrip countersign={e.countersign} />
              </td>
              <td>
                <FlagChips flags={e.flags} hrefFor={flagHref} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
