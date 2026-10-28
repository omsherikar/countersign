import type { Metadata } from "next";
import { t } from "@/lib/copy";
import { Crumbs, PageHeader } from "@/components/common/page-header";

export const metadata: Metadata = { title: "Upload" };

/** Upload file layout from API_CONTRACT.md section E; the upload itself lands in Week 2. */
const COLUMNS: { name: string; notes: string }[] = [
  { name: "apaar_id", notes: "12-digit APAAR id. Leave blank when consent is Refused, Pending or International." },
  { name: "name", notes: "Full name as in the admission register." },
  { name: "dob", notes: t("rowerr.DOB_FORMAT") + "." },
  { name: "gender", notes: "As recorded at admission." },
  { name: "mobile", notes: "Student's mobile number. Stored hashed; officers see the last four digits only." },
  { name: "email", notes: "Student's email. Shown only to the student." },
  { name: "address", notes: "Postal address. Stored hashed, never shown." },
  { name: "nationality", notes: "Two-letter country code, e.g. IN." },
  { name: "passport_no", notes: t("rowerr.PASSPORT_REQUIRED") + "." },
  { name: "programme_code", notes: "An approved programme of your college, e.g. CSE." },
  { name: "academic_year", notes: "e.g. 2026-27." },
  { name: "year_of_study", notes: t("rowerr.YEAR_INVALID") + "." },
  { name: "admission_route", notes: t("rowerr.ROUTE_INVALID") + "." },
  { name: "counselling_ref", notes: "Allotment reference for counselling admissions, e.g. MHCET-2026-R1-004512." },
  { name: "category", notes: "General, EWS, OBC, SC, ST or Other." },
  { name: "consent_status", notes: t("rowerr.CONSENT_INVALID") + "." },
];

export default function CollegeUploadPage() {
  return (
    <>
      <Crumbs items={[{ label: t("nav.ledger"), href: "/college" }, { label: t("nav.upload") }]} />
      <PageHeader title={t("upload.heading")} description={t("app.upload.lead")} />
      <p className="mb-3 text-sm text-ink-muted">{`CSV or XLSX. ${t("upload.max")}.`}</p>
      <h2 className="mb-3 text-xl">{t("upload.columns")}</h2>
      <div className="overflow-x-auto border-l-2 border-rule-margin bg-paper-raised">
        <table className="ledger-table">
          <caption className="sr-only">{t("upload.columns")}</caption>
          <thead>
            <tr>
              <th scope="col" className="num w-10">
                #
              </th>
              <th scope="col" className="code">
                {t("app.upload.col.column")}
              </th>
              <th scope="col">{t("app.upload.col.notes")}</th>
            </tr>
          </thead>
          <tbody>
            {COLUMNS.map((c, i) => (
              <tr key={c.name}>
                <td className="num text-ink-muted">{i + 1}</td>
                <td className="code font-medium">{c.name}</td>
                <td className="wrap">{c.notes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-4 max-w-[68ch] text-sm text-ink-muted">{t("upload.declaration")}</p>
    </>
  );
}
