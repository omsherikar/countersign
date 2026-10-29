import { expect, test } from "./support";

/**
 * Flow 6 and Flow 0 at 8:30 (D44, W4-12): Countersign does not issue
 * degrees. The university issues a completion attestation for a graduate,
 * prints the certificate block with the masked APAAR and the QR, and a phone
 * with no account opens the QR's address and reads a valid completion
 * attestation.
 */

interface CertificatePrint {
  student: { name: string; id_kind: "APAAR" | "PROVISIONAL"; id_masked: string };
  university: { name: string };
  attestation: { short_id: string; status: string; verify_url: string } | null;
}

test("the university issues a completion attestation, prints the certificate block, and its QR verifies", async ({ pageAs, freshPage }) => {
  const page = await pageAs("university");
  await page.goto("/university/certificates");
  await expect(page.getByRole("heading", { level: 1, name: "Certificate integration" })).toBeVisible();
  await expect(page.getByText(/^Countersign does not issue degrees\./)).toBeVisible();

  const graduates = page.getByRole("table", { name: "Certificate integration" });
  await expect(graduates.getByRole("row").nth(1)).toBeVisible();
  // A graduate with a linked APAAR and no completion attestation yet: each run takes the next one.
  const graduate = graduates
    .getByRole("row")
    .filter({ has: page.getByRole("button", { name: "Issue completion attestation" }) })
    .filter({ has: page.getByRole("cell", { name: /^APAAR ending \d{4}$/ }) })
    .first();
  test.skip((await graduate.count()) === 0, "Every graduate with an APAAR already holds a completion attestation; run make demo-reset.");
  const name = (await graduate.getByRole("cell").first().innerText()).trim();

  await graduate.getByRole("button", { name: "Issue completion attestation" }).click();
  const dialog = page.getByRole("dialog", { name: `Issue a completion attestation for ${name}?` });
  await expect(dialog).toContainText("It is not a degree: your certificate remains the degree.");
  const issuing = page.waitForResponse((r) => /^\/api\/university\/certificates\/[^/]+\/issue$/.test(new URL(r.url()).pathname) && r.request().method() === "POST");
  await dialog.getByRole("button", { name: "Issue attestation" }).click();
  const issued = await issuing;
  expect(issued.status()).toBe(201);
  const enrolmentId = new URL(issued.url()).pathname.split("/")[4];
  await expect(dialog).toBeHidden();
  await expect(graduates.locator(`a[href="/university/certificates/${enrolmentId}/print"]`)).toHaveText("Print certificate block");

  // The print view, loaded fresh so its data comes from the api.
  const printData = page.waitForResponse((r) => new URL(r.url()).pathname === `/api/university/certificates/${enrolmentId}` && r.request().method() === "GET");
  await page.goto(`/university/certificates/${enrolmentId}/print`);
  const print = (await (await printData).json()) as CertificatePrint;
  expect(print.attestation?.status).toBe("ACTIVE");
  expect(print.student.id_kind).toBe("APAAR");
  expect(print.student.id_masked).toMatch(/^XXXX XXXX \d{4}$/);

  const block = page.getByRole("article");
  await expect(block).toContainText(`For the certificate awarded by ${print.university.name} to`);
  await expect(block.getByText(name, { exact: true })).toBeVisible();
  await expect(block.getByText(print.student.id_masked, { exact: true })).toBeVisible();
  await expect(block.getByRole("img", { name: /^QR code to verify this completion attestation/ })).toBeVisible();
  await expect(block.getByText(`Attestation id ${print.attestation!.short_id}`)).toBeVisible();
  await expect(block).toContainText("This block is not a degree");
  expect(await block.innerText(), "no full APAAR on the block").not.toMatch(/\d{12}/);
  await expect(page.getByRole("button", { name: "Print", exact: true })).toBeVisible();

  const pdf = await page.request.get(`/api/university/certificates/${enrolmentId}/block.pdf`);
  expect(pdf.status()).toBe(200);
  expect(pdf.headers()["content-type"]).toContain("application/pdf");
  expect((await pdf.body()).subarray(0, 5).toString("latin1")).toBe("%PDF-");

  // The QR encodes the verify address; a phone opens it with no account.
  const qr = new URL(print.attestation!.verify_url);
  expect(qr.pathname).toMatch(/^\/verify\/d\/[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/);
  const phone = await freshPage();
  await phone.goto(qr.pathname);
  const result = phone.getByRole("region", { name: "Valid completion attestation" });
  await expect(result.getByRole("heading", { level: 1 })).toHaveText("Valid completion attestation");
  await expect(result).toContainText("This is not a degree; the degree is the certificate it is printed on.");
  await expect(result).toContainText(name);
  await expect(result).toContainText(print.attestation!.short_id);
  await expect(result).toContainText(print.student.id_masked);
});
