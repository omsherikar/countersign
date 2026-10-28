import fs from "node:fs";
import {
  RUN,
  abcId,
  apiJson,
  expect,
  mailText,
  searchMail,
  test,
  minimalPdf,
  ROLES,
  type FlagRow,
  type Paged,
} from "./support";

/**
 * Flows 2 and W3-7/W3-8: the regional officer requests documents on an open
 * ABC College flag and keeps an internal note, the registrar answers with a
 * PDF, the officer downloads it and clears the flag. The history lists every
 * step; the registrar reads the officer's request and decision, never the
 * internal note.
 */

/** Flags this walk may take, in order; the excess, duplicate and denied flags belong to the other tests and the live demo. */
const TAKE = ["LATE_REFILL", "NO_ACADEMIC_ACTIVITY", "DUAL_ENROLMENT_ALLOWED", "QUOTA_BREACH", "INVALID_APAAR", "DUPLICATE_CROSS_INSTITUTION", "NAME_MISMATCH"];
const NAME: Record<string, string> = {
  LATE_REFILL: "Late refill",
  NO_ACADEMIC_ACTIVITY: "No academic activity",
  DUAL_ENROLMENT_ALLOWED: "Dual enrolment (allowed)",
  QUOTA_BREACH: "Quota breach",
  INVALID_APAAR: "APAAR not verified",
  DUPLICATE_CROSS_INSTITUTION: "Duplicate across institutions",
  NAME_MISMATCH: "Name or date of birth mismatch",
};

test("an officer requests documents, the registrar answers with a PDF, the officer downloads it and clears the flag", async ({ pageAs, request }) => {
  const ro = await pageAs("ro");
  const institution = await abcId(ro);
  const open = await apiJson<Paged<FlagRow>>(ro, "GET", `/flags?institution_id=${institution}&status=OPEN&page_size=100`);
  const flag = TAKE.map((type) => open.items.find((f) => f.type === type)).find((f) => f !== undefined);
  test.skip(!flag, "No open ABC College flag is left for the case walk; run make demo-reset.");

  const requestNote = `Send the admission register extract for this case (${RUN}).`;
  const internalNote = `Internal: the counselling cell confirmed by phone, waiting for the extract (${RUN}).`;
  const replyNote = `Admission register extract attached (${RUN}).`;
  const clearNote = `The extract matches the upload, so the flag is cleared (${RUN}).`;
  const fileName = "admission-register-extract.pdf";
  const pdf = minimalPdf(`Admission register extract ${RUN}`);

  // The officer asks for documents, then keeps a note for officers only.
  await ro.goto(`/ro/cases/${flag!.id}`);
  await expect(ro.getByRole("heading", { level: 1, name: NAME[flag!.type] })).toBeVisible();
  const actions = ro.getByRole("group", { name: "Actions" });
  await actions.getByRole("button", { name: "Request documents" }).click();
  let sheet = ro.getByRole("dialog", { name: "Request documents" });
  await sheet.getByLabel("Note (shown to the college)").fill(requestNote);
  await sheet.getByRole("button", { name: "Send request" }).click();
  await expect(sheet).toBeHidden();
  await expect(ro.getByRole("img", { name: "Documents requested" }).first()).toBeVisible();

  await actions.getByRole("button", { name: "Add note" }).click();
  sheet = ro.getByRole("dialog", { name: "Add note" });
  await sheet.getByLabel("Note (officers only)").fill(internalNote);
  await sheet.getByRole("button", { name: "Add note" }).click();
  await expect(sheet).toBeHidden();
  const history = ro.getByRole("table", { name: "History" });
  await expect(history).toContainText(internalNote);

  // Every registrar of the institution gets the request by email.
  await expect
    .poll(
      async () => {
        const { messages } = await searchMail(request, `to:"${ROLES.registrar.email}"`, 0, 10);
        for (const m of messages) if ((await mailText(request, m.ID)).includes(requestNote)) return true;
        return false;
      },
      { timeout: 30_000, message: "the document request email reaches the registrar" },
    )
    .toBe(true);

  // The registrar reads the request, not the internal note, and answers with a PDF.
  const college = await pageAs("registrar");
  await college.goto(`/college/flags/${flag!.id}`);
  const respond = college.getByRole("region", { name: "Respond to the document request" });
  await expect(respond).toContainText(requestNote);
  await expect(college.getByText(internalNote)).toHaveCount(0);
  await respond.getByLabel("Your reply to the officer").fill(replyNote);
  const choosing = college.waitForEvent("filechooser");
  await respond.getByRole("button", { name: "Add file" }).click();
  await (await choosing).setFiles({ name: fileName, mimeType: "application/pdf", buffer: pdf });
  await expect(respond.getByText("1 of 3 files")).toBeVisible();
  await respond.getByRole("button", { name: "Send to the officer" }).click();
  await expect(respond.getByText("Sent to the officer. You will see their decision here.")).toBeVisible();

  // The officer downloads the file the registrar sent, byte for byte, and clears the flag.
  await ro.reload();
  const responded = history.getByRole("row").filter({ hasText: "Responded" });
  await expect(responded).toContainText(replyNote);
  const downloading = ro.waitForEvent("download");
  await responded.getByRole("button", { name: new RegExp(`^Download ${fileName.replace(/\./g, "\\.")}`) }).click();
  const download = await downloading;
  expect(download.suggestedFilename()).toBe(fileName);
  expect(fs.readFileSync(await download.path()).equals(pdf), "the downloaded file is the one the registrar sent").toBe(true);

  await actions.getByRole("button", { name: "Clear flag" }).click();
  sheet = ro.getByRole("dialog", { name: "Clear flag" });
  await sheet.getByLabel("Note (shown to the college)").fill(clearNote);
  await sheet.getByRole("button", { name: "Clear flag" }).click();
  await expect(sheet).toBeHidden();
  await expect(ro.getByRole("img", { name: "Cleared" }).first()).toBeVisible();

  // The history lists each step in order.
  await expect(history).toContainText("Cleared the flag");
  const rows = (await history.locator("tbody tr").allInnerTexts()).map((r) => r.replace(/\s+/g, " "));
  const steps = [
    ["Flag opened"],
    ["Requested documents", "Open to Documents requested", requestNote],
    ["Added a note", internalNote],
    ["Responded", replyNote, fileName],
    ["Cleared the flag", "Documents requested to Cleared", clearNote],
  ];
  let at = -1;
  for (const words of steps) {
    const next = rows.findIndex((r, i) => i > at && words.every((w) => r.includes(w)));
    expect(next, `history row with ${words.join(" / ")} after row ${at}:\n${rows.join("\n")}`).toBeGreaterThan(at);
    at = next;
  }

  // The registrar sees the decision and its note; the internal note never reaches the college.
  await college.reload();
  const collegeHistory = college.getByRole("table", { name: "History" });
  await expect(collegeHistory).toContainText("Cleared the flag");
  await expect(collegeHistory).toContainText(clearNote);
  await expect(collegeHistory).toContainText(requestNote);
  await expect(collegeHistory).toContainText("Added a note");
  await expect(college.getByText(internalNote)).toHaveCount(0);
});
