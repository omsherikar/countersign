import { DEMO, abcId, apiJson, expect, test, type FlagDetail, type FlagRow, type Paged } from "./support";

/** Flow 0 at 3:00: "Ravi Kumar Sharma" and "R. K. Sharma" in one upload are one student, and the flag says so. */
test("the R. K. Sharma duplicate flag links to Ravi Kumar Sharma", async ({ pageAs }) => {
  const page = await pageAs("ro");
  const institution = await abcId(page);
  const list = await apiJson<Paged<FlagRow>>(page, "GET", `/flags?institution_id=${institution}&type=DUPLICATE_WITHIN_UPLOAD&page_size=100`);
  let flagId: string | null = null;
  for (const row of list.items) {
    const flag = await apiJson<FlagDetail>(page, "GET", `/flags/${row.id}`);
    const names = flag.evidence.facts.find((f) => f.label === "Names as uploaded");
    if (names && String(names.value).includes("R. K. Sharma") && String(names.value).includes(DEMO.ravi.name)) flagId = row.id;
  }
  expect(flagId, "a DUPLICATE_WITHIN_UPLOAD flag naming R. K. Sharma at ABC College").not.toBeNull();

  await page.goto(`/ro/cases/${flagId}`);
  await expect(page.getByRole("heading", { level: 1, name: "Duplicate within institution" })).toBeVisible();
  const evidence = page.getByRole("article", { name: /^Duplicate within institution:/ });
  await expect(evidence).toContainText(`${DEMO.ravi.name} / R. K. Sharma`);

  const related = page.getByRole("table", { name: "Related enrolments" });
  const ravi = related.getByRole("link", { name: DEMO.ravi.name, exact: true });
  await expect(ravi).toBeVisible();
  const raviRow = related.getByRole("row").filter({ has: page.getByRole("link", { name: DEMO.ravi.name, exact: true }) });
  await expect(raviRow).toContainText(`XXXX XXXX ${DEMO.ravi.apaarLast4}`);

  await ravi.click();
  await expect(page).toHaveURL(/\/ro\/enrolments\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { level: 1, name: DEMO.ravi.name })).toBeVisible();
  await expect(page.getByText(`XXXX XXXX ${DEMO.ravi.apaarLast4}`).first()).toBeVisible();
});
