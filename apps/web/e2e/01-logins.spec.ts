import { API_URL, DEMO, DEMO_OTP, DEMO_PASSWORD, ROLES, accountRadio, backOnCountersign, expect, test, type Role } from "./support";

/**
 * Flow 1: officers, the registrars and the university sign in from their
 * card with the demo password; the student signs in only through the Demo
 * DigiLocker from the Student card; a signed-out visit goes to /login.
 */
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

  test("a student account has no password: its email and the demo password are refused like a wrong password", async ({ request }) => {
    // Ravi's seeded account (A4.12): students sign in only through DigiLocker.
    const res = await request.post(`${API_URL}/auth/login`, { data: { email: "student@demo", password: DEMO_PASSWORD } });
    expect(res.status()).toBe(401);
    expect(((await res.json()) as { error: { code: string } }).error.code).toBe("INVALID_CREDENTIALS");
  });

  test("the student card signs Ravi in through the Demo DigiLocker and lands on /student", async ({ page }) => {
    await page.goto("/login");
    const card = page.getByRole("link", { name: /^Student .*Sign in with DigiLocker/ });
    await expect(card).toBeVisible();
    // No password exists for a student: the card is a link to DigiLocker sign-in, not a prefill.
    await expect(card).toHaveAttribute("href", "/api/auth/digilocker/start?next=%2Fstudent");
    await card.click();

    await expect(page.getByRole("heading", { level: 1, name: /^Demo DigiLocker\./ })).toBeVisible();
    const accounts = page.getByRole("radio");
    await expect(accounts.first()).toHaveAccessibleName(/^Ravi Kumar Sharma /);
    await accountRadio(page, DEMO.ravi).check();
    await page.getByLabel("One-time password").fill(DEMO_OTP);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();

    await backOnCountersign(page, "/student");
    await expect(page.getByRole("heading", { level: 1, name: "My enrolment" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Ravi", exact: true })).toBeVisible();
    await expect(page.getByText(DEMO.ravi.name, { exact: true }).first()).toBeVisible();
  });
});
