import { ROLES, expect, test, type Role } from "./support";

/** Flow 1: every demo role signs in from its card and lands on its own home; a signed-out visit goes to /login. */
test.describe("Sign in", () => {
  test("a signed-out visit to /aicte goes to the sign-in page", async ({ page }) => {
    await page.goto("/aicte");
    await expect(page).toHaveURL(/\/login\?next=%2Faicte$/);
    await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
  });

  for (const role of Object.keys(ROLES) as Role[]) {
    const { email, home, menu } = ROLES[role];
    test(`${email} lands on ${home}`, async ({ page }) => {
      await page.goto("/login");
      await page.getByRole("button", { name: email }).click();
      await expect(page.getByLabel("Email")).toHaveValue(email);
      await page.getByRole("button", { name: "Sign in", exact: true }).click();

      await expect(page).toHaveURL(new RegExp(`${home}$`));
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
      await expect(page.getByRole("button", { name: menu, exact: true })).toBeVisible();
    });
  }
});
