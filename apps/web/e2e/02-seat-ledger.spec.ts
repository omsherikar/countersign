import { ABC, cellIn, expect, test } from "./support";

/** Flow 0 at 1:30: the planted 132 admitted against 120 approved in ABC College CSE, and the flag it raised. */
test("ABC College CSE 2026-27 shows 120 approved, 132 admitted and an Excess admission flag", async ({ pageAs }) => {
  const page = await pageAs("admin");
  await page.goto("/aicte");
  await page.getByRole("link", { name: ABC.name, exact: true }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: ABC.name })).toBeVisible();

  await expect(page.getByText("Academic year 2026-27", { exact: true })).toBeVisible();
  const programmes = page.getByRole("table", { name: "Programmes" });
  const cse = programmes.getByRole("row").filter({ has: page.getByRole("button", { name: /^CSE (Show|Hide) seat pools$/ }) });
  await expect(cse).toHaveCount(1);
  await expect(await cellIn(programmes, cse, "Approved")).toHaveText("120");
  await expect(await cellIn(programmes, cse, "Admitted")).toHaveText("132");

  await page.getByRole("tab", { name: /^Flags/ }).click();
  const flags = page.getByRole("table", { name: "Flags" });
  const excess = flags.getByRole("row").filter({ hasText: "Excess admission" }).filter({ hasText: "132 admitted against 120 approved" });
  await expect(excess).toHaveCount(1);
  await expect(excess.getByRole("cell").first()).toHaveText("High");

  await excess.getByRole("link", { name: /132 admitted against 120 approved/ }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Excess admission" })).toBeVisible();
  await expect(page.getByText("132 admitted against 120 approved seats in CSE (2026-27)").first()).toBeVisible();
});
