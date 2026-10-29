import { ABC, DEMO, abcEnrolments, abcId, apiJson, cellIn, expect, note, test, type FlagDetail, type FlagRow, type Paged } from "./support";

/**
 * Flow 0 at 1:30 and 3:00: the planted 132 admitted against 120 approved in
 * ABC College CSE and its Excess admission case; "Ravi Kumar Sharma" and
 * "R. K. Sharma" in one upload are one student, and the case says so.
 */

/** The seeded CSE 2026-27 cohort: 132 admitted against an approved intake of 120 (approval v2). */
const SEEDED = { approved: 120, admitted: 132 };

test("ABC College CSE 2026-27 shows 120 approved, 132 admitted and an Excess admission case", async ({ pageAs }) => {
  const page = await pageAs("admin");

  // A claim withdrawn by an officer's decision leaves the active counts, so a run after the
  // decisions test of an earlier run counts that many fewer (make demo-reset restores 132).
  const withdrawn = (await abcEnrolments(page, "status=WITHDRAWN")).filter(
    (e) => e.programme_code === "CSE" && e.cohort_year === "2026-27" && /withdrawn by an officer's decision/.test(e.next_step ?? ""),
  ).length;
  const admitted = SEEDED.admitted - withdrawn;
  if (withdrawn > 0) note(`${withdrawn} ABC College CSE 2026-27 claim(s) were withdrawn by an earlier run's decision, so CSE shows ${admitted} admitted (make demo-reset restores 132).`);

  await page.goto("/aicte");
  await page.getByRole("link", { name: ABC.name, exact: true }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: ABC.name })).toBeVisible();

  await page.getByRole("tab", { name: "Programmes", exact: true }).click();
  await expect(page.getByRole("tabpanel", { name: "Programmes" }).getByText("Academic year 2026-27", { exact: true })).toBeVisible();
  const programmes = page.getByRole("table", { name: "Programmes" });
  const cse = programmes.getByRole("row").filter({ has: page.getByRole("button", { name: /^CSE (Show|Hide) seat pools$/ }) });
  await expect(cse).toHaveCount(1);
  // The approved intake carries the approval version it comes from (D41).
  await expect(await cellIn(programmes, cse, "Approved")).toHaveText(/^120\s*v2$/);
  await expect(await cellIn(programmes, cse, "Admitted")).toHaveText(String(admitted));
  await expect(await cellIn(programmes, cse, "Seated")).toHaveText(String(SEEDED.approved));
  await expect(await cellIn(programmes, cse, "Unseated")).toHaveText(`${admitted - SEEDED.approved} unseated`);

  const summary = `${admitted} admitted against ${SEEDED.approved} approved`;
  await page.getByRole("tab", { name: /^Cases/ }).click();
  const cases = page.getByRole("table", { name: /^Cases/ });
  const excess = cases.getByRole("row").filter({ hasText: "Excess admission" }).filter({ hasText: summary });
  await expect(excess).toHaveCount(1);
  await expect(excess.getByRole("cell").first()).toHaveText("High");

  await excess.getByRole("link", { name: new RegExp(summary) }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Excess admission" })).toBeVisible();
  await expect(page.getByText(`${summary} seats in CSE (2026-27)`).first()).toBeVisible();
});

test("the R. K. Sharma duplicate case links to Ravi Kumar Sharma", async ({ pageAs }) => {
  const page = await pageAs("ro");
  const institution = await abcId(page);
  const list = await apiJson<Paged<FlagRow>>(page, "GET", `/flags?institution_id=${institution}&type=DUPLICATE_WITHIN_UPLOAD&page_size=100`);
  let caseId: string | null = null;
  for (const row of list.items) {
    const flag = await apiJson<FlagDetail>(page, "GET", `/flags/${row.id}`);
    const names = flag.evidence.facts.find((f) => f.label === "Names as uploaded");
    if (names && String(names.value).includes("R. K. Sharma") && String(names.value).includes(DEMO.ravi.name)) caseId = row.id;
  }
  expect(caseId, "a DUPLICATE_WITHIN_UPLOAD case naming R. K. Sharma at ABC College").not.toBeNull();

  await page.goto(`/ro/cases/${caseId}`);
  await expect(page.getByRole("heading", { level: 1, name: "Duplicate within institution" })).toBeVisible();
  const evidence = page.getByRole("article", { name: /^Duplicate within institution:/ });
  await expect(evidence).toContainText(`${DEMO.ravi.name} / R. K. Sharma`);

  const related = page.getByRole("table", { name: "Related enrolments" });
  const ravi = related.getByRole("link", { name: DEMO.ravi.name, exact: true });
  await expect(ravi).toBeVisible();
  const raviRow = related.getByRole("row").filter({ has: page.getByRole("link", { name: DEMO.ravi.name, exact: true }) });
  await expect(raviRow.getByRole("cell", { name: `APAAR ending ${DEMO.ravi.apaarLast4}` })).toBeVisible();

  await ravi.click();
  await expect(page).toHaveURL(/\/ro\/enrolments\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { level: 1, name: DEMO.ravi.name })).toBeVisible();
  await expect(page.getByText(`XXXX XXXX ${DEMO.ravi.apaarLast4}`).first()).toBeVisible();
});
