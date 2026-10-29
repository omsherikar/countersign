import { expect, test } from "./support";

/** D29: after everything the earlier tests wrote and read, the AICTE officer verifies the audit chain. */
test("the audit page verifies the chain as intact", async ({ pageAs }) => {
  test.setTimeout(240_000);
  const page = await pageAs("admin");
  await page.goto("/admin/audit");
  await expect(page.getByRole("heading", { level: 1, name: "Audit" })).toBeVisible();
  const verify = page.getByRole("region", { name: "Verify chain" });
  await verify.getByRole("button", { name: "Verify chain" }).click();
  await expect(verify.getByText(/^Chain intact, [\d,]+ entries$/)).toBeVisible({ timeout: 180_000 });
  await expect(verify.getByText(/^Chain broken/)).toHaveCount(0);
});
