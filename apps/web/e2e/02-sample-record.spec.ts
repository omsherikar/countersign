import { ABC, DEMO, abcEnrolmentOf, cardFooter, cardRow, cardStatusLine, expect, recordCard, test } from "./support";

/**
 * Flow 0, steps 1 and 2 (the deck's slide 2): the AICTE officer's overview
 * counts records by status, and the sample record reads exactly as the
 * deck's card: identity confirmed, the seat fits approval v2, the joining
 * record contradicts the claim, credits are not yet due, and the student
 * said "I never joined" after DigiLocker sign-in. One contradiction
 * outranks every confirmation, so the record is Disputed (priority).
 */

/** "29 Oct": the card prints a source's date as day and month. */
const DAY = String.raw`\d{1,2} [A-Z][a-z]{2}`;

test("the sample record card reads as the deck draws it", async ({ pageAs }) => {
  const page = await pageAs("admin");

  await page.goto("/aicte");
  const tiles = page.getByRole("list", { name: "Records by status" });
  for (const word of ["Awaiting evidence", "Countersigned", "Under review", "Disputed"]) {
    await expect(tiles.getByRole("listitem").filter({ hasText: word })).toHaveCount(1);
  }
  await expect(page.getByText(/^Countersigned = identity verified \(or the alternative route\) \+ seat fits the approval \+ /)).toBeVisible();

  const sample = await abcEnrolmentOf(page, DEMO.sample.name, DEMO.sample.apaarLast4);
  await page.goto(`/aicte/enrolments/${sample.id}`);
  await expect(page.getByRole("heading", { level: 1, name: DEMO.sample.name })).toBeVisible();
  await expect(page.getByText("Disputed (priority)", { exact: true }).first()).toBeVisible();

  const card = recordCard(page);
  await expect(card).toHaveAccessibleName(`Record card for B.Tech CSE, ${ABC.name}`);
  await expect(card.getByText(`B.Tech CSE 2026, ${ABC.name} · APAAR XXXX XXXX ${DEMO.sample.apaarLast4}`, { exact: true })).toBeVisible();

  // The five rows, in the deck's order.
  await expect(card.getByRole("rowheader")).toHaveText([/^Identity: /, /^Seat: /, /^Joining record: /, /^Credits: /, /^Student: /]);

  const identity = cardRow(card, "Identity");
  await expect(identity.state).toHaveText("Confirmed");
  await expect(identity.source).toHaveText(new RegExp(`^APAAR verification · ${DAY}\\s*Independent of the college$`));

  const seat = cardRow(card, "Seat");
  await expect(seat.state).toHaveText("Confirmed: fits approved intake");
  await expect(seat.source).toHaveText("AICTE approval v2, 2026-27 (Seat Ledger, derived)");

  const joining = cardRow(card, "Joining record");
  await expect(joining.state).toHaveText("Contradicted: not found");
  await expect(joining.source).toHaveText(new RegExp(`^State admission authority · ${DAY}\\s*Independent of the college$`));

  const credits = cardRow(card, "Credits");
  await expect(credits.state).toHaveText("Not yet due");
  await expect(credits.source).toHaveText("First semester not complete");

  const student = cardRow(card, "Student");
  await expect(student.state).toHaveText('Contradicted: "I never joined"');
  await expect(student.source).toHaveText(new RegExp(`^Student sign-in via DigiLocker · ${DAY}\\s*Independent of the college$`));

  // The footer: the status with "(priority)" and the next step, then the legend with this record's status marked.
  const footer = cardFooter(card);
  await expect(cardStatusLine(card)).toHaveText(/^Status:\s*Disputed \(priority\)\. Next step: \S.+\.$/);
  const legend = footer.getByLabel("Awaiting evidence · Countersigned · Under review · Disputed");
  await expect(legend).toHaveText(/^Awaiting evidence\s*·\s*Countersigned\s*·\s*Under review\s*·\s*Disputed$/);
  await expect(legend.locator('[aria-current="true"]')).toHaveText("Disputed");
  await expect(footer.getByText("What the statuses mean")).toBeVisible();

  // The dispute is a priority case the officer can open from the record.
  const cases = page.getByRole("region", { name: "Cases about this record" });
  await expect(cases.getByRole("listitem").filter({ has: page.getByRole("link", { name: "Student dispute" }) }).getByRole("img", { name: "Severity high" })).toBeVisible();
});
