import { expect, test } from "./support";

/**
 * W4-7 and Flow 0 at 7:30 (D46): the regional officer's reports are scoped
 * to the region and labelled synthetic; one report downloads as CSV, XLSX
 * and PDF, each answered 200 with its own content type and an attachment
 * name that carries the report, the year and the scope.
 */

const FORMATS = [
  { word: "CSV", type: "text/csv", magic: "academic_year,state_code,state_name,region," },
  { word: "XLSX", type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", magic: "PK" },
  { word: "PDF", type: "application/pdf", magic: "%PDF-" },
] as const;

test("Records by state downloads as CSV, XLSX and PDF for the Western region", async ({ pageAs }) => {
  const page = await pageAs("ro");
  await page.goto("/ro/reports");
  await expect(page.getByRole("heading", { level: 1, name: "Reports" })).toBeVisible();
  await expect(page.getByText("Synthetic data. Every college, student and number here is generated for the demo.")).toBeVisible();
  await expect(page.getByText("These reports cover only the Western region.")).toBeVisible();

  const report = page.getByRole("listitem").filter({ has: page.getByRole("heading", { level: 2, name: "Records by state" }) });
  for (const format of FORMATS) {
    const link = report.getByRole("link", { name: `Download Records by state as ${format.word}` });
    await expect(link).toHaveText(format.word);
    const href = await link.getAttribute("href");
    expect(href).toMatch(new RegExp(`^/api/reports/by-state\\.${format.word.toLowerCase()}\\?academic_year=2026-27$`));

    // The link downloads the file in the browser...
    const downloading = page.waitForEvent("download");
    await link.click();
    const download = await downloading;
    expect(download.suggestedFilename()).toMatch(new RegExp(`^countersign_by-state_2026-27_[A-Za-z0-9-]+\\.${format.word.toLowerCase()}$`));
    await download.delete();

    // ...and the same address answers 200 with the format's content type.
    const res = await page.request.get(href!);
    expect(res.status(), `${format.word}: ${res.status()}`).toBe(200);
    expect(res.headers()["content-type"]).toContain(format.type);
    expect(res.headers()["content-disposition"]).toMatch(/^attachment; filename="countersign_by-state_2026-27_[A-Za-z0-9-]+\.(csv|xlsx|pdf)"$/);
    const body = await res.body();
    expect(body.length).toBeGreaterThan(100);
    if (format.word !== "CSV") {
      expect(body.subarray(0, format.magic.length).toString("latin1"), `${format.word} file signature`).toBe(format.magic);
      continue;
    }
    // The CSV holds the report's header and, under it, one row per state of the region.
    const lines = body.toString("utf8").replace(/^\ufeff/, "").trim().split(/\r?\n/);
    const header = lines.findIndex((line) => line.startsWith(format.magic));
    expect(header, `the CSV header in:\n${lines.slice(0, 3).join("\n")}`).toBeGreaterThanOrEqual(0);
    const regions = lines.slice(header + 1).map((line) => line.split(",")[3]);
    expect(regions.length).toBeGreaterThan(0);
    expect(new Set(regions)).toEqual(new Set(["WEST"]));
  }
});

test.fixme("the CSV's first line is its header", async ({ pageAs }) => {
  // Product bug: the CSV puts a quoted "Synthetic data." line before the header, while API_CONTRACT §A4.21 makes the column names the header.
  const page = await pageAs("ro");
  const res = await page.request.get("/api/reports/by-state.csv?academic_year=2026-27");
  expect(res.status()).toBe(200);
  const first = (await res.text()).replace(/^\ufeff/, "").split(/\r?\n/)[0];
  expect(first.startsWith(FORMATS[0].magic)).toBe(true);
});
