import {
  ABC,
  DEMO,
  abcEnrolmentOf,
  apiJson,
  backOnCountersign,
  cardRow,
  cardStatusLine,
  digiLockerSignIn,
  expect,
  note,
  recordCard,
  ruleStatus,
  STATUS_WORD,
  test,
  type EnrolmentDetail,
} from "./support";

/**
 * Flow 4, step 7 and Flow 0 at 5:40 (D36): Priyanka Salunkhe refused APAAR
 * consent, so her college recorded her with a provisional ID. She signs in
 * with the Demo DigiLocker, which knows no APAAR for her, and claims the
 * record with that ID; her Identity row then reads Confirmed through her
 * DigiLocker sign-in, and the record's status follows the evidence rule.
 */

const DAY = String.raw`\d{1,2} [A-Z][a-z]{2}`;

test("a student without APAAR claims her record by provisional ID after DigiLocker sign-in, and Identity reads Confirmed", async ({ pageAs, freshPage }) => {
  const admin = await pageAs("admin");
  const row = await abcEnrolmentOf(admin, DEMO.priyanka.name, null);
  const provisionalId = row.student.provisional_id;
  expect(provisionalId, "her record carries a provisional ID").toMatch(/^PRV-[0-9A-Z]{8}$/);
  const before = await apiJson<EnrolmentDetail>(admin, "GET", `/enrolments/${row.id}`);

  const page = await freshPage();
  await page.goto("/login");
  await page.getByRole("link", { name: /^Student .*Sign in with DigiLocker/ }).click();
  await digiLockerSignIn(page, DEMO.priyanka);

  if (before.claim?.claimed) {
    // The claim binds her DigiLocker account, so a later sign-in goes straight home.
    note(`${DEMO.priyanka.name} claimed her record in an earlier run (make demo-reset restores it); this run checks the claimed record.`);
    await backOnCountersign(page, "/student");
  } else {
    expect(before.checks.find((c) => c.type === "IDENTITY")?.state, "Identity is Not applicable before the claim").toBe("NOT_APPLICABLE");
    await backOnCountersign(page, "/student/claim");
    await expect(page.getByRole("heading", { level: 1, name: "Claim your record" })).toBeVisible();
    await expect(page.getByText(`Signed in with DigiLocker as ${DEMO.priyanka.name}.`, { exact: true })).toBeVisible();
    // The field takes the ID in any case and with spaces, and upper-cases it.
    await page.getByLabel("Provisional ID").fill(provisionalId!.toLowerCase());
    await page.getByRole("button", { name: "Claim record" }).click();
    await expect(page.getByRole("heading", { name: "Record claimed" })).toBeVisible();
    await expect(page.getByText(`This record at ${ABC.name} is now linked to your DigiLocker sign-in. Its Identity row reads Confirmed.`)).toBeVisible();
    await page.goto("/student");
  }

  // Her own home shows the card with Identity confirmed.
  await expect(page.getByRole("heading", { level: 1, name: "My enrolment" })).toBeVisible();
  await expect(cardRow(recordCard(page), "Identity").state).toHaveText("Confirmed");

  // The officer reads the same row, independent of the college, and the status the rule gives.
  const after = await apiJson<EnrolmentDetail>(admin, "GET", `/enrolments/${row.id}`);
  expect(after.claim?.claimed).toBe(true);
  const expected = ruleStatus(after);
  await admin.goto(`/aicte/enrolments/${row.id}`);
  const card = recordCard(admin);
  const identity = cardRow(card, "Identity");
  await expect(identity.state).toHaveText("Confirmed");
  await expect(identity.source).toHaveText(new RegExp(`^Student sign-in via DigiLocker · ${DAY}\\s*Independent of the college$`));
  await expect(cardStatusLine(card)).toHaveText(new RegExp(`^Status:\\s*${STATUS_WORD[expected]}\\.`));
  // With her joining record confirmed by the state admission authority, nothing else is missing.
  const admission = after.checks.find((c) => c.type === "ADMISSION");
  if (admission?.state === "CONFIRMED" && admission.independent && after.flags.length === 0) expect(after.record_status).toBe("COUNTERSIGNED");
});

test.fixme("the student's own record card names the source and date of each row, as the officer's does", async ({ studentAs }) => {
  // Product bug: on /student the card's Source and date column is empty (only the independence marker shows), because GET /students/me carries brief rows without source lines.
  const page = await studentAs(DEMO.priyanka);
  const card = recordCard(page);
  await expect(cardRow(card, "Identity").source).toHaveText(new RegExp(`^Student sign-in via DigiLocker · ${DAY}`));
  await expect(cardRow(card, "Seat").source).toHaveText(/^AICTE approval v\d+, 2026-27 \(Seat Ledger, derived\)$/);
  await expect(cardRow(card, "Joining record").source).toHaveText(new RegExp(`^State admission authority · ${DAY}`));
});
