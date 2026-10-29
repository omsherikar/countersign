import fs from "node:fs";
import type { Page } from "@playwright/test";
import {
  DEMO,
  ROLES,
  RUN,
  STATUS_WORD,
  abcEnrolmentOf,
  abcId,
  apiJson,
  cardStatusLine,
  cellIn,
  expect,
  mailText,
  minimalPdf,
  note,
  numberIn,
  recordCard,
  ruleStatus,
  searchMail,
  test,
  type EnrolmentDetail,
  type FlagRow,
  type Paged,
} from "./support";

/**
 * Flow 2 and Flow 0 at 3:20 to 4:20 (D43): on the student's dispute the
 * regional officer asks ABC College for admission documents with a reply
 * date, and the record's next step says so; the registrar answers with a
 * PDF. The AICTE officer then withdraws the claim with a reason, and in one
 * step the record reads withdrawn, its seat is released in the Seat Ledger,
 * no attestation stays live, and the history holds the decision. On another
 * case the officer upholds the claim with a reason; the case is decided and
 * the record's status is worked out again by the evidence rule.
 */

/** Today plus `days` in India, as the date input wants it (yyyy-mm-dd) and as the pages print it ("5 Nov"). */
function istDate(days: number): { iso: string; short: string } {
  const at = new Date(Date.now() + days * 86_400_000);
  const iso = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(at);
  const short = new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", day: "numeric", month: "short" }).format(at);
  return { iso, short };
}

/** The Admitted, Seated and Unseated counts of one programme in the institution's Programmes table. */
async function ledgerCounts(page: Page, institutionId: string, code: string): Promise<{ admitted: number; seated: number; unseated: number }> {
  await page.goto(`/aicte/institutions/${institutionId}`);
  await page.getByRole("tab", { name: "Programmes", exact: true }).click();
  const programmes = page.getByRole("table", { name: "Programmes" });
  const row = programmes.getByRole("row").filter({ has: page.getByRole("button", { name: new RegExp(`^${code} (Show|Hide) seat pools$`) }) });
  await expect(row).toHaveCount(1);
  return {
    admitted: await numberIn(await cellIn(programmes, row, "Admitted")),
    seated: await numberIn(await cellIn(programmes, row, "Seated")),
    unseated: await numberIn(await cellIn(programmes, row, "Unseated")),
  };
}

let dispute: FlagRow | null = null;

test.describe.configure({ mode: "serial" });

test.describe("Officer decisions", () => {
  test("the regional officer asks for admission documents on the dispute, and the registrar answers with a PDF", async ({ pageAs, request }) => {
    const ro = await pageAs("ro");
    const institution = await abcId(ro);
    const sample = await abcEnrolmentOf(ro, DEMO.sample.name, DEMO.sample.apaarLast4);
    // The newest undecided dispute at ABC College is the one the dispute test opened; the sample record's stays for the demo.
    const open = await apiJson<Paged<FlagRow & { created_at: string }>>(ro, "GET", `/flags?institution_id=${institution}&type=STUDENT_DENIED&status=UNRESOLVED&page_size=100`);
    const newest = open.items.filter((f) => f.enrolment_id !== sample.id).sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
    test.skip(!newest, "No undecided Student dispute at ABC College besides the sample record's; the dispute test opens one.");
    dispute = newest;

    const due = istDate(7);
    const requestNote = `Send the admission register extract and the fee receipt for this student (${RUN}).`;
    const replyNote = `Admission register extract attached (${RUN}).`;
    const fileName = "admission-register-extract.pdf";
    const pdf = minimalPdf(`Admission register extract ${RUN}`);

    await ro.goto(`/ro/cases/${dispute.id}`);
    await expect(ro.getByRole("heading", { level: 1, name: "Student dispute" })).toBeVisible();
    await ro.getByRole("group", { name: "Actions" }).getByRole("button", { name: "Request documents" }).click();
    const sheet = ro.getByRole("dialog", { name: "Request documents" });
    await sheet.getByLabel("What to send").selectOption({ label: "Admission documents" });
    await sheet.getByLabel("Note (shown to the college)").fill(requestNote);
    await sheet.getByLabel("Reply by (optional)").fill(due.iso);
    // The sheet says what the record's next step will read (case.request_docs_change).
    await expect(sheet.getByRole("region", { name: "What will change" })).toContainText(/The record's next step reads "College asked for admission documents by .+\." Nothing else changes\./);
    await sheet.getByRole("button", { name: "Send request" }).click();
    await expect(sheet).toBeHidden();
    await expect(ro.getByRole("img", { name: "Documents requested" }).first()).toBeVisible();

    // The record's next step now follows the request, as the deck's card reads it.
    await ro.goto(`/ro/enrolments/${dispute.enrolment_id}`);
    await expect(cardStatusLine(recordCard(ro))).toHaveText(`Status: Disputed (priority). Next step: College asked for admission documents by ${due.short}.`);

    // Every registrar of the college gets the request by email.
    await expect
      .poll(
        async () => {
          const { messages } = await searchMail(request, `to:"${ROLES.registrar.email}"`, 0, 10);
          for (const m of messages) if ((await mailText(request, m.ID)).includes(requestNote)) return true;
          return false;
        },
        { timeout: 60_000, message: "the document request email reaches the registrar" },
      )
      .toBe(true);

    // The registrar reads the request and answers with a PDF.
    const college = await pageAs("registrar");
    await college.goto(`/college/cases/${dispute.id}`);
    const respond = college.getByRole("region", { name: "Respond to the document request" });
    await expect(respond).toContainText(requestNote);
    await respond.getByLabel("Your reply to the officer").fill(replyNote);
    const choosing = college.waitForEvent("filechooser");
    await respond.getByRole("button", { name: "Add file" }).click();
    await (await choosing).setFiles({ name: fileName, mimeType: "application/pdf", buffer: pdf });
    await expect(respond.getByText("1 of 3 files")).toBeVisible();
    await respond.getByRole("button", { name: "Send to the officer" }).click();
    await expect(respond.getByText("Sent to the officer. You will see their decision here.")).toBeVisible();

    // The officer finds the reply and downloads the very file the registrar sent.
    await ro.goto(`/ro/cases/${dispute.id}`);
    const responded = ro.getByRole("table", { name: "History" }).getByRole("row").filter({ hasText: "Responded" });
    await expect(responded).toContainText(replyNote);
    const downloading = ro.waitForEvent("download");
    await responded.getByRole("button", { name: new RegExp(`^Download ${fileName.replace(/\./g, "\\.")}`) }).click();
    const download = await downloading;
    expect(download.suggestedFilename()).toBe(fileName);
    expect(fs.readFileSync(await download.path()).equals(pdf), "the downloaded file is the one the registrar sent").toBe(true);
  });

  test("the Request documents sheet quotes the next step as the record then shows it", async ({ pageAs }) => {
    expect(dispute, "the documents step found the dispute").not.toBeNull();
    const due = istDate(7);
    const ro = await pageAs("ro");
    await ro.goto(`/ro/cases/${dispute!.id}`);
    await ro.getByRole("group", { name: "Actions" }).getByRole("button", { name: "Request documents" }).click();
    const sheet = ro.getByRole("dialog", { name: "Request documents" });
    await sheet.getByLabel("What to send").selectOption({ label: "Admission documents" });
    await sheet.getByLabel("Reply by (optional)").fill(due.iso);
    await expect(sheet.getByRole("region", { name: "What will change" })).toContainText(`The record's next step reads "College asked for admission documents by ${due.short}."`);
    await sheet.getByRole("button", { name: "Cancel" }).last().click();
  });

  test("the AICTE officer withdraws the disputed claim: in one step the record is withdrawn, its seat released and no attestation stays live", async ({ pageAs }) => {
    expect(dispute, "the documents step found the dispute").not.toBeNull();
    const admin = await pageAs("admin");
    const institution = await abcId(admin);
    const before = await apiJson<EnrolmentDetail>(admin, "GET", `/enrolments/${dispute!.enrolment_id}`);
    expect(before.seat, "the disputed record holds a seat").not.toBeNull();
    const seatCode = before.seat!.seat_code;
    const ledgerBefore = await ledgerCounts(admin, institution, before.programme.code);
    const reasonNote = `The college's documents do not show the student joining; the dispute stands (${RUN}).`;

    await admin.goto(`/aicte/cases/${dispute!.id}`);
    await expect(admin.getByRole("heading", { level: 1, name: "Student dispute" })).toBeVisible();
    await admin.getByRole("group", { name: "Decide" }).getByRole("button", { name: "Withdraw claim" }).click();
    const sheet = admin.getByRole("dialog", { name: "Withdraw the claim?" });
    await sheet.getByLabel("Reason").selectOption({ label: "The student never joined" });
    await sheet.getByLabel("Note (shown to the college)").fill(reasonNote);
    const changes = sheet.getByRole("region", { name: "What will change" });
    await expect(changes).toContainText(`Seat ${seatCode} is released.`);
    await expect(changes).toContainText("Nothing is deleted.");
    await expect(changes).toContainText("The case closes as Claim withdrawn.");
    await sheet.getByRole("checkbox", { name: "I have read what will change." }).check();
    await sheet.getByRole("button", { name: "Withdraw claim" }).click();
    await expect(sheet).toBeHidden();
    await expect(admin.getByRole("img", { name: "Claim withdrawn" }).first()).toBeVisible();

    // The history lists the decision with its reason and note.
    const history = admin.getByRole("table", { name: "History" });
    await expect(history.getByRole("row").filter({ hasText: reasonNote })).toContainText("The student never joined");

    // The record reads withdrawn, and keeps everything it had.
    await admin.goto(`/aicte/enrolments/${dispute!.enrolment_id}`);
    await expect(admin.getByText(/^This record was withdrawn by an officer's decision on /)).toBeVisible();
    const after = await apiJson<EnrolmentDetail>(admin, "GET", `/enrolments/${dispute!.enrolment_id}`);
    expect(after.status).toBe("WITHDRAWN");
    expect(after.seat, "the withdrawn record no longer holds its seat").toBeNull();
    expect(after.credentials.filter((c) => c.status === "ACTIVE"), "no live attestation on a withdrawn record").toHaveLength(0);
    for (const c of before.credentials) expect(after.credentials.find((x) => x.id === c.id)?.status).toBe("REVOKED");

    // The Seat Ledger counts one admission fewer; the freed seat goes to the backlog when there is one.
    const ledgerAfter = await ledgerCounts(admin, institution, before.programme.code);
    expect(ledgerAfter.admitted).toBe(ledgerBefore.admitted - 1);
    expect(ledgerAfter.seated + ledgerAfter.unseated).toBe(ledgerAfter.admitted);
    if (ledgerBefore.unseated > 0) expect(ledgerAfter.unseated).toBe(ledgerBefore.unseated - 1);
    else expect(ledgerAfter.seated).toBe(ledgerBefore.seated - 1);
  });

  test("the AICTE officer upholds another case with a reason; the case is decided and the record's status follows the rule", async ({ pageAs }) => {
    const admin = await pageAs("admin");
    const institution = await abcId(admin);
    // Cases whose decision touches one record and leaves the demo's own cases alone, in the order this walk takes them.
    const take = ["NO_ACADEMIC_ACTIVITY", "NAME_MISMATCH", "LATE_REFILL", "DUAL_ENROLMENT_ALLOWED", "DUPLICATE_CROSS_INSTITUTION", "INVALID_APAAR"];
    const open = await apiJson<Paged<FlagRow>>(admin, "GET", `/flags?institution_id=${institution}&status=OPEN&page_size=100`);
    const pick = take.map((type) => open.items.find((f) => f.type === type && f.enrolment_id)).find((f) => f !== undefined);
    if (!pick) note("No open ABC College case is left for the uphold walk; make demo-reset restores them.");
    test.skip(!pick, "No open ABC College case is left for the uphold walk; run make demo-reset.");
    const reasonNote = `The college's documents support the record (${RUN}).`;

    await admin.goto(`/aicte/cases/${pick!.id}`);
    await admin.getByRole("group", { name: "Decide" }).getByRole("button", { name: "Uphold claim" }).click();
    const sheet = admin.getByRole("dialog", { name: "Uphold the college's claim?" });
    await sheet.getByLabel("Reason").selectOption({ label: "Documents support the college's record" });
    await sheet.getByLabel("Note (shown to the college)").fill(reasonNote);
    await expect(sheet.getByRole("region", { name: "What will change" }).getByRole("listitem").first()).toBeVisible();
    await sheet.getByRole("button", { name: "Uphold claim" }).click();
    await expect(sheet).toBeHidden();
    await expect(admin.getByRole("img", { name: "Claim upheld" }).first()).toBeVisible();
    await expect(admin.getByRole("table", { name: "History" }).getByRole("row").filter({ hasText: reasonNote })).toContainText("Documents support the college's record");

    const decided = await apiJson<FlagRow>(admin, "GET", `/flags/${pick!.id}`);
    expect(decided.status).toBe("UPHELD");

    // The record's status is the evidence rule's answer for its rows and the cases still naming it.
    const record = await apiJson<EnrolmentDetail>(admin, "GET", `/enrolments/${pick!.enrolment_id}`);
    const expected = ruleStatus(record);
    expect(record.record_status).toBe(expected);
    if (pick!.covers) {
      const covered = record.checks.find((c) => c.type === pick!.covers);
      if (covered?.state === "CONTRADICTED") expect(covered.resolved?.outcome, "the upheld row stays Contradicted, marked as upheld").toBe("UPHELD");
    }
    await admin.goto(`/aicte/enrolments/${pick!.enrolment_id}`);
    await expect(cardStatusLine(recordCard(admin))).toHaveText(new RegExp(`^Status:\\s*${STATUS_WORD[expected]}\\.`));
  });
});
