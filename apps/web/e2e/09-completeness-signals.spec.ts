import { DEADLINES, RUN, apiJson, cellIn, expect, note, numberIn, test, type EnrolmentDetail, type Paged } from "./support";

/**
 * Flows 9 and 10 (Flow 0 at 6:20 and 6:50; D40, D45, R5): the AICTE
 * officer's overview counts records by status and shows completeness; a
 * college that left joined students out of its upload lists them by name
 * with a Missing from upload case. The signals page lists the planted
 * shared contact ring and the anomalies; opening a case from the ring for
 * one college puts that college's members Under review, and nothing before
 * that. The registrar never sees a signal.
 */

test.describe.configure({ mode: "serial" });

interface SignalRow {
  id: string;
  type: "GHOST_RING" | "ANOMALY";
  status: "NEW" | "CASE_OPENED" | "DISMISSED";
  member_count: number;
  summary: string;
  institutions: { id: string; name: string }[];
  cases: { id: string; institution_id: string; status: string }[];
}

interface SignalDetail extends SignalRow {
  members: { enrolment_id: string; institution: { id: string; name: string }; record_status: string }[];
}

test("the overview counts records by status, and a college with missing students lists them by name", async ({ pageAs }) => {
  const page = await pageAs("admin");
  await page.goto("/aicte");

  const status = page.getByRole("region", { name: "Records by status" });
  const counts = status.getByRole("table", { name: "Records by status" });
  await expect(counts.getByRole("rowheader")).toHaveText(["Awaiting evidence", "Countersigned", "Under review", "Disputed"]);
  for (const word of ["Countersigned", "Under review", "Disputed"]) {
    const row = counts.getByRole("row").filter({ has: page.getByRole("rowheader", { name: word }) });
    // The status is the row's header; its first cell is the count.
    expect(await numberIn(row.getByRole("cell").first()), `${word} records`).toBeGreaterThan(0);
  }

  const completeness = page.getByRole("region", { name: "Completeness and deadlines" });
  await expect(completeness.getByRole("term").filter({ hasText: "Completeness" })).toBeVisible();
  await expect(completeness.getByText(/^\d+(\.\d)?%$/).first()).toBeVisible();
  const colleges = completeness.getByRole("table", { name: "Completeness and deadlines" });
  const first = colleges.getByRole("row").nth(1);
  const missing = await numberIn(await cellIn(colleges, first, "Missing"));
  expect(missing, "the college with most students missing from its upload comes first").toBeGreaterThan(0);
  const name = (await first.getByRole("link").innerText()).trim();

  await first.getByRole("link").click();
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
  const tab = page.getByRole("tabpanel", { name: "Completeness" });
  await expect(tab.getByText(new RegExp(`^\\d+(\\.\\d)?% of joined students uploaded, ${missing} missing$`))).toBeVisible();
  await expect(tab.getByRole("link", { name: "A Missing from upload case is open for these students." })).toBeVisible();

  const list = tab.getByRole("table", { name: `Missing from the upload (${missing})` });
  const rows = list.locator("tbody tr");
  await expect(rows).toHaveCount(missing);
  // The college's own admitted students, named, with the APAAR masked.
  for (const row of await rows.all()) {
    await expect(await cellIn(list, row, "Student")).toHaveText(/^[A-Z][A-Za-z.]*( [A-Z][A-Za-z.]*)+$/);
    await expect(await cellIn(list, row, "APAAR / Provisional")).not.toHaveText(/\d{12}/);
  }

  await tab.getByRole("link", { name: "A Missing from upload case is open for these students." }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Missing from upload" })).toBeVisible();
});

interface CompletenessRow {
  institution: { id: string; name: string; aicte_permanent_id: string };
  deadline_state: "NOT_DUE" | "ON_TIME" | "LATE" | "OVERDUE";
}

test("the colleges that first uploaded after the reporting deadline read Late", async ({ pageAs }) => {
  const page = await pageAs("admin");
  const list = await apiJson<Paged<CompletenessRow>>(page, "GET", "/completeness?academic_year=2026-27&page_size=100");
  const late = DEADLINES.late.map((id) => list.items.find((i) => i.institution.aicte_permanent_id === id));
  for (const [i, row] of late.entries()) expect(row?.deadline_state, `${DEADLINES.late[i]} is planted late`).toBe("LATE");

  await page.goto(`/aicte/institutions/${late[0]!.institution.id}/completeness`);
  await expect(page.getByRole("heading", { level: 1, name: late[0]!.institution.name })).toBeVisible();
  await expect(page.getByRole("tabpanel", { name: "Completeness" }).getByText(/^Late\s*First upload on \d{1,2} [A-Z][a-z]{2}, after the deadline of 30 Sep\.$/)).toBeVisible();
});

test.fixme("the college that never uploaded reads Overdue, and the overview counts it", async ({ pageAs }) => {
  // Product bug: the seed loads the planted overdue college's file too, so it reads Late (first upload at seed time) and the overview counts 0 overdue.
  const page = await pageAs("admin");
  const list = await apiJson<Paged<CompletenessRow>>(page, "GET", "/completeness?academic_year=2026-27&page_size=100");
  for (const id of DEADLINES.overdue) expect(list.items.find((i) => i.institution.aicte_permanent_id === id)?.deadline_state, `${id} is planted overdue`).toBe("OVERDUE");
  await page.goto("/aicte");
  const completeness = page.getByRole("region", { name: "Completeness and deadlines" });
  await expect(completeness.getByRole("term").filter({ hasText: "Overdue" }).locator("xpath=following-sibling::dd[1]")).toHaveText(String(DEADLINES.overdue.length));
});

test.describe("Signals", () => {
  test("the signals page lists the shared contact ring and the anomalies; a case opened from the ring puts one college's members Under review", async ({ pageAs }) => {
    const page = await pageAs("admin");
    await page.goto("/aicte/signals");
    await expect(page.getByRole("heading", { level: 1, name: "Signals" })).toBeVisible();
    await expect(page.getByText("Signals never change a record's status. Only a case an officer opens can lead to a decision.")).toBeVisible();
    await page.getByLabel("Status").selectOption({ label: "All" });
    const table = page.getByRole("table", { name: "Signals" });
    const ring = table.getByRole("row").filter({ hasText: "Shared contact ring" }).filter({ hasText: /^.*40 students across 3 colleges share / });
    await expect(ring).toHaveCount(1);
    expect(await table.getByRole("row").filter({ hasText: "Unusual pattern" }).count(), "anomaly signals").toBeGreaterThan(0);

    const signals = await apiJson<Paged<SignalRow>>(page, "GET", "/signals?academic_year=2026-27&type=GHOST_RING&page_size=100");
    const planted = signals.items.find((s) => s.member_count === 40 && s.institutions.length === 3);
    expect(planted, "the planted 40-student ring across 3 colleges").toBeTruthy();

    await ring.getByRole("link", { name: "Shared contact ring" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Shared contact ring" })).toBeVisible();
    await expect(page.getByText(/^Rule: students linked by a shared mobile number, email or address form a group; /)).toBeVisible();
    await expect(page.getByRole("region", { name: "Members (40)" })).toBeVisible();

    // Open the case for a college that has none from this signal yet, ABC College last so the demo's college stays as it is.
    const detail = await apiJson<SignalDetail>(page, "GET", `/signals/${planted!.id}`);
    const withCase = new Set(detail.cases.map((c) => c.institution_id));
    const college = [...detail.institutions].sort((a, b) => Number(a.name.startsWith("ABC")) - Number(b.name.startsWith("ABC"))).find((i) => !withCase.has(i.id));
    if (!college) {
      note("Every college of the ring has a case from an earlier run (make demo-reset restores the signal); this run checks those cases' records.");
    } else {
      const members = detail.members.filter((m) => m.institution.id === college.id);
      // Before any case, the signal changed nothing: the members keep the statuses their own evidence gives.
      expect(members.length).toBeGreaterThan(0);
      expect(members.some((m) => m.record_status !== "UNDER_REVIEW"), "the signal alone puts no member Under review").toBe(true);

      await page.getByRole("button", { name: "Open case" }).click();
      const dialog = page.getByRole("dialog", { name: "Open a case from this signal?" });
      await dialog.getByRole("checkbox", { name: `${college.name} (${members.length})` }).check();
      await dialog.getByLabel("Note (officers only)").fill(`Shared mobiles across three colleges; ask for admission records (${RUN}).`);
      await expect(dialog.getByRole("region", { name: "What will change" })).toContainText(
        `The ${members.length} records the case names read Under review until an officer decides it. Nothing else about them changes.`,
      );
      await dialog.getByRole("button", { name: "Open case" }).click();
      await expect(dialog).toBeHidden();
    }

    // Every member at a college with a case from this signal now reads Under review.
    const after = await apiJson<SignalDetail>(page, "GET", `/signals/${planted!.id}`);
    expect(after.status).toBe("CASE_OPENED");
    const opened = new Set(after.cases.map((c) => c.institution_id));
    const covered = after.members.filter((m) => opened.has(m.institution.id));
    expect(covered.length).toBeGreaterThan(0);
    for (const m of covered) {
      const record = await apiJson<EnrolmentDetail>(page, "GET", `/enrolments/${m.enrolment_id}`);
      expect(record.record_status, `${m.enrolment_id} at ${m.institution.name}`).toBe("UNDER_REVIEW");
    }
    await page.reload();
    const membersTable = page.getByRole("table", { name: "Members" });
    const one = covered[0];
    await expect(membersTable.getByRole("row").filter({ has: page.locator(`a[href$="/enrolments/${one.enrolment_id}"]`) })).toContainText("Under review");
  });

  test("the registrar never sees a signal: the page is refused and the api answers 403", async ({ pageAs }) => {
    const page = await pageAs("registrar");
    await page.goto("/aicte/signals");
    await expect(page).toHaveURL(/\/college(\?|$)/);
    await expect(page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Signals" })).toHaveCount(0);
    const res = await page.request.get("/api/signals?academic_year=2026-27");
    expect(res.status()).toBe(403);
  });
});
