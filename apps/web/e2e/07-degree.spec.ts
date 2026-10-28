import { expect, test } from "./support";

/**
 * Flow 6: the university issues a degree proof for a graduate, prints the
 * insert with the masked APAAR and the QR, downloads the PDF insert, and the
 * QR's address verifies on a phone with no account.
 */

interface DegreePrint {
  student: { name: string; id_kind: "APAAR" | "PROVISIONAL"; id_masked: string };
  university: { name: string };
  degree: { short_id: string; status: string; verify_url: string } | null;
}

test("the university issues a degree proof, prints the insert, and its QR verifies", async ({ pageAs, freshPage }) => {
  const page = await pageAs("university");
  await page.goto("/university/degrees");
  const graduates = page.getByRole("table", { name: "Degree print" });
  // A graduate with a linked APAAR and no degree proof yet: each run takes the next one.
  const graduate = graduates
    .getByRole("row")
    .filter({ has: page.getByRole("button", { name: "Issue degree proof" }) })
    .filter({ hasText: /XXXX XXXX \d{4}/ })
    .first();
  await expect(graduate).toBeVisible();
  const name = (await graduate.getByRole("cell").first().innerText()).trim();

  await graduate.getByRole("button", { name: "Issue degree proof" }).click();
  const dialog = page.getByRole("dialog", { name: `Issue a degree proof for ${name}?` });
  const issuing = page.waitForResponse((r) => /^\/api\/university\/degrees\/[^/]+\/issue$/.test(new URL(r.url()).pathname) && r.request().method() === "POST");
  await dialog.getByRole("button", { name: "Issue proof" }).click();
  const issued = await issuing;
  expect(issued.status()).toBe(201);
  const enrolmentId = new URL(issued.url()).pathname.split("/")[4];
  await expect(dialog).toBeHidden();
  const printLink = graduates.locator(`a[href="/university/degrees/${enrolmentId}/print"]`);
  await expect(printLink).toHaveText("Print degree insert");

  // The print view, loaded fresh so its data comes from the api.
  const printData = page.waitForResponse((r) => new URL(r.url()).pathname === `/api/university/degrees/${enrolmentId}` && r.request().method() === "GET");
  await page.goto(`/university/degrees/${enrolmentId}/print`);
  const print = (await (await printData).json()) as DegreePrint;
  expect(print.degree?.status).toBe("ACTIVE");
  expect(print.student.id_kind).toBe("APAAR");
  expect(print.student.id_masked).toMatch(/^XXXX XXXX \d{4}$/);

  const insert = page.getByRole("article");
  await expect(insert.getByRole("heading", { level: 1 })).toHaveText(print.university.name);
  await expect(insert.getByText(name, { exact: true })).toBeVisible();
  await expect(insert.getByText(print.student.id_masked, { exact: true })).toBeVisible();
  await expect(insert.getByRole("img", { name: /^QR code to verify this degree proof/ })).toBeVisible();
  await expect(insert.getByText(`Proof id ${print.degree!.short_id}`)).toBeVisible();
  expect(await insert.innerText(), "no full APAAR on the insert").not.toMatch(/\d{12}/);
  await expect(page.getByRole("button", { name: "Print", exact: true })).toBeVisible();

  const pdf = await page.request.get(`/api/university/degrees/${enrolmentId}/insert.pdf`);
  expect(pdf.status()).toBe(200);
  expect(pdf.headers()["content-type"]).toContain("application/pdf");
  expect((await pdf.body()).subarray(0, 5).toString("latin1")).toBe("%PDF-");

  // The QR encodes the verify address; a phone opens it with no account.
  const qr = new URL(print.degree!.verify_url);
  expect(qr.pathname).toMatch(/^\/verify\/d\/[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/);
  const phone = await freshPage();
  await phone.goto(qr.pathname);
  const result = phone.getByRole("region", { name: "Valid degree proof" });
  await expect(result.getByRole("heading", { level: 1 })).toHaveText("Valid degree proof");
  await expect(result).toContainText(name);
  await expect(result).toContainText(print.degree!.short_id);
  await expect(result).toContainText(print.student.id_masked);
});
