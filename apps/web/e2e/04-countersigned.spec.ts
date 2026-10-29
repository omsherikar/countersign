import {
  ABC,
  abcEnrolments,
  cardRow,
  cardStatusLine,
  expect,
  expectValidShare,
  recordCard,
  shareThreeFields,
  test,
  type EnrolmentRow,
  type RowBrief,
  type RowType,
} from "./support";

/**
 * Flow 0 at 5:00 and the evidence rule (D35, D44): a clean record whose
 * joining record comes from the state admission authority is Countersigned
 * without any answer from the student. Its student, once signed in through
 * DigiLocker, already holds an enrolment attestation, shares three fields,
 * and a verifier with no account sees exactly those.
 */

const DAY = String.raw`\d{1,2} [A-Z][a-z]{2}`;

const rowsOf = (row: EnrolmentRow) => Object.fromEntries(row.checks.map((c) => [c.type, c])) as Record<RowType, RowBrief>;

let record: EnrolmentRow | null = null;

test.describe.configure({ mode: "serial" });

test.describe("A record countersigned without a student reply", () => {
  test("an independent joining record countersigns the record while the Student row has no answer", async ({ pageAs }) => {
    const page = await pageAs("admin");
    // The joining record is the only independent evidence: no credits yet, no answer from the student, no case.
    const candidates = await abcEnrolments(page, "status=ACTIVE&record_status=COUNTERSIGNED");
    record =
      candidates.find((e) => {
        const rows = rowsOf(e);
        return (
          e.student.apaar_masked !== null &&
          e.flags.length === 0 &&
          rows.ADMISSION?.state === "CONFIRMED" &&
          rows.ADMISSION.independent &&
          rows.STUDYING?.state === "NOT_YET_DUE" &&
          rows.STUDENT?.state === "PENDING"
        );
      }) ?? null;
    expect(record, `a Countersigned ${ABC.name} record whose only independent evidence is its joining record`).not.toBeNull();

    await page.goto(`/aicte/enrolments/${record!.id}`);
    await expect(page.getByRole("heading", { level: 1, name: record!.student.name })).toBeVisible();
    const card = recordCard(page);
    await expect(cardStatusLine(card)).toHaveText(/^Status:\s*Countersigned\. Next step: None\. The evidence is complete\.$/);
    await expect(card.getByText("Why: Identity, seat and the joining record confirm the record, and nothing is unresolved.", { exact: true })).toBeVisible();

    const joining = cardRow(card, "Joining record");
    await expect(joining.state).toHaveText(new RegExp(`^Confirmed: joined ${DAY}$`));
    await expect(joining.source).toHaveText(new RegExp(`^State admission authority · ${DAY}\\s*Independent of the college$`));

    const student = cardRow(card, "Student");
    await expect(student.state).toHaveText(/^Pending: no answer yet$/);
    await expect(student.state).not.toHaveText(/Confirmed/);

    // A countersigned record carries its live enrolment attestation (D44).
    await expect(page.getByRole("region", { name: "Attestations" }).getByText(/^Enrolment attestation [0-9A-Z]{8}, issued /)).toBeVisible();
  });

  test("its student holds an enrolment attestation after DigiLocker sign-in, and three shared fields verify as Valid", async ({ studentAs, freshPage }) => {
    expect(record, "the first test found the record").not.toBeNull();
    const student = { name: record!.student.name, apaarLast4: record!.student.apaar_masked!.slice(-4) };
    const wallet = await studentAs(student, "/student/wallet");
    await expect(wallet.getByRole("heading", { level: 1, name: "My attestations" })).toBeVisible();
    const { code } = await shareThreeFields(wallet);

    const verifier = await freshPage();
    await expectValidShare(
      verifier,
      code,
      [
        ["Institution", `${ABC.name} (${ABC.permanentId})`],
        ["Programme", /^B\.Tech .+ \(UG\)$|^.+ \((UG|PG)\)$/],
        ["Academic year", "2026-27"],
      ],
      [student.name, `XXXX XXXX ${student.apaarLast4}`],
    );
  });
});
