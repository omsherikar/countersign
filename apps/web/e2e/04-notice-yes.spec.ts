import {
  ABC,
  DEMO,
  RUN,
  apiJson,
  expect,
  findOpenAbcNotice,
  mailText,
  note,
  noticeToken,
  readNotice,
  searchMail,
  test,
} from "./support";

/**
 * Flows 4 and 5: Ravi's notice, opened from the email in Mailpit, answered
 * Yes; his Enrolment proof appears; he shares three fields and a verifier
 * with no account sees exactly those; once AICTE revokes the proof the same
 * code says Revoked.
 */

interface StudentMe {
  email: string;
  enrolments: { id: string; institution_name: string; programme_code: string; academic_year: string; countersign: { checks: { type: string; status: string }[] } }[];
}

/** Six groups of four Crockford base32 characters (A3.15). */
const SHARE_CODE = /^[0-9A-HJKMNP-TV-Z]{4}(?:-[0-9A-HJKMNP-TV-Z]{4}){5}$/;

let raviEnrolment = "";
let credentialId = "";
let shareCode = "";

test.describe.configure({ mode: "serial" });

test.describe("A student's Yes", () => {
  test("Ravi's notice from Mailpit opens without sign-in, and Yes makes his Student check pass", async ({ pageAs, freshPage, request }) => {
    const student = await pageAs("student");
    const me = await apiJson<StudentMe>(student, "GET", "/students/me");
    const enrolment = me.enrolments.find((e) => e.institution_name === ABC.name && e.programme_code === "CSE" && e.academic_year === "2026-27");
    expect(enrolment, "Ravi's ABC College CSE 2026-27 enrolment").toBeTruthy();
    raviEnrolment = enrolment!.id;

    // The link exists only in the message, so the test reads it from Mailpit's API.
    let token: string | null = null;
    let answered = false;
    const { messages } = await searchMail(request, `to:"${me.email}"`);
    for (const m of messages) {
      const found = noticeToken(await mailText(request, m.ID));
      if (!found) continue;
      const { notice } = await readNotice(request, found);
      // The "R. K. Sharma" row shares Ravi's email; its notice carries a provisional id, his carries his APAAR.
      const his = notice && notice.institution_name === ABC.name && notice.programme_code === "CSE" && notice.id_kind === "APAAR" && notice.id_masked.endsWith(DEMO.ravi.apaarLast4);
      if (!his) continue;
      if (notice.response === null) {
        token = found;
        break;
      }
      answered = true;
    }

    let enrolmentId = raviEnrolment;
    let apaarLast4 = DEMO.ravi.apaarLast4;
    if (!token) {
      expect(answered, `Ravi's notice email (to ${me.email}) is in Mailpit`).toBe(true);
      note("Ravi's notice was answered by an earlier run (make demo-reset restores it); this run answers another unanswered ABC College notice.");
      const admin = await pageAs("admin");
      const other = await findOpenAbcNotice(admin, request, { skipApaarLast4: [DEMO.ravi.apaarLast4, DEMO.second.apaarId.slice(-4)] });
      test.skip(!other, "No unanswered ABC College email notice is left; run make demo-reset.");
      token = other!.token;
      enrolmentId = other!.enrolmentId;
      apaarLast4 = other!.apaarMasked.slice(-4);
    }

    const page = await freshPage();
    await page.goto(`/student/notices/${token}`);
    await expect(page.getByText(`${ABC.name} says`, { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Is that right?" })).toBeVisible();
    await expect(page.getByText(`XXXX XXXX ${apaarLast4}`, { exact: true })).toBeVisible();
    await expect(page.getByText(DEMO.ravi.name)).toHaveCount(0);
    await page.getByRole("button", { name: "Yes, that is right" }).click();
    await expect(page.getByText(`Thank you. Your enrolment at ${ABC.name} is now countersigned by you.`)).toBeVisible();

    const admin = await pageAs("admin");
    await admin.goto(`/aicte/enrolments/${enrolmentId}`);
    const checks = admin.getByRole("table", { name: "Countersign checks" });
    const studentCheck = checks.getByRole("row").filter({ has: admin.getByRole("cell", { name: "Student", exact: true }) });
    await expect(studentCheck.getByRole("img", { name: "Countersigned" })).toBeVisible();
    await expect(studentCheck).toContainText("Confirmed by the student on");
  });

  test("his wallet holds an Enrolment proof, and three shared fields verify as Valid with nothing else", async ({ pageAs, freshPage }) => {
    const page = await pageAs("student");
    await page.goto("/student/wallet");
    await expect(page.getByRole("heading", { level: 1, name: "My proofs" })).toBeVisible();
    const proofs = page.getByRole("region", { name: "Enrolment proof" });
    await expect(proofs.first()).toBeVisible();
    let shareable = proofs.filter({ has: page.getByRole("button", { name: "Share proof" }) });

    if ((await shareable.count()) === 0) {
      // An earlier run revoked the proof. Eligibility is looked at again after a recheck (D26),
      // and a revoked proof does not count, so the officer's recheck issues a new one.
      note("Ravi's proof was revoked by an earlier run; an officer's recheck issues a new one.");
      const admin = await pageAs("admin");
      await apiJson(admin, "POST", `/enrolments/${raviEnrolment}/recheck`);
      await page.reload();
      shareable = page.getByRole("region", { name: "Enrolment proof" }).filter({ has: page.getByRole("button", { name: "Share proof" }) });
    }
    await expect(shareable).toHaveCount(1);
    await expect(shareable).toContainText(ABC.name);
    await expect(shareable.getByText("Active", { exact: true })).toBeVisible();

    await shareable.getByRole("button", { name: "Share proof" }).click();
    const sheet = page.getByRole("dialog", { name: "Share this proof" });
    await expect(sheet.getByRole("checkbox", { name: "Institution (always shared)" })).toBeChecked();
    await expect(sheet.getByRole("checkbox", { name: "Programme (always shared)" })).toBeChecked();
    await expect(sheet.getByText("Shares 2 of 8 fields")).toBeVisible();
    await sheet.getByRole("checkbox", { name: "Academic year", exact: true }).check();
    await expect(sheet.getByText("Shares 3 of 8 fields")).toBeVisible();
    await sheet.getByRole("checkbox", { name: "I agree" }).check();

    const created = page.waitForResponse((r) => /^\/api\/credentials\/[^/]+\/present$/.test(new URL(r.url()).pathname) && r.request().method() === "POST");
    await sheet.getByRole("button", { name: "Create QR" }).click();
    const response = await created;
    expect(response.status()).toBe(201);
    credentialId = new URL(response.url()).pathname.split("/")[3];
    const body = (await response.json()) as { code: string; disclosed: string[] };
    expect(body.disclosed).toEqual(["institution", "programme", "academic_year"]);

    await expect(sheet.getByRole("img", { name: /^QR code for your proof/ })).toBeVisible();
    const code = sheet.getByText(SHARE_CODE).first();
    await expect(code).toBeVisible();
    shareCode = (await code.innerText()).trim();
    expect(shareCode).toBe(body.code);
    await expect(sheet.getByText("Shares 3 of 8 fields")).toBeVisible();

    const verifier = await freshPage();
    await verifier.goto(`/verify/${shareCode}`);
    const result = verifier.getByRole("region", { name: "Valid proof" });
    await expect(result.getByRole("heading", { level: 1 })).toHaveText("Valid proof");
    await expect(result.getByRole("term")).toHaveText(["Institution", "Programme", "Academic year"]);
    await expect(result.getByRole("definition")).toHaveText([`${ABC.name} (${ABC.permanentId})`, "B.Tech Computer Science and Engineering (UG)", "2026-27"]);
    await expect(verifier.getByText(DEMO.ravi.name)).toHaveCount(0);
    await expect(verifier.getByText(DEMO.ravi.apaarLast4)).toHaveCount(0);
  });

  test("after AICTE revokes the proof, the same code shows Revoked", async ({ pageAs, freshPage }) => {
    expect(credentialId && shareCode, "the share step ran").toBeTruthy();
    const admin = await pageAs("admin");
    // The enrolment page has no Revoke button yet (A3.7), so the officer's revocation goes through the api.
    const revoked = await apiJson<{ status: string }>(admin, "POST", `/credentials/${credentialId}/revoke`, {
      reason: `Withdrawn by the end-to-end test (${RUN}).`,
    });
    expect(revoked.status).toBe("REVOKED");

    const verifier = await freshPage();
    // The status list is rebuilt at once in the process that revoked, and within 60 s elsewhere (A3.15).
    await expect(async () => {
      await verifier.goto(`/verify/${shareCode}`);
      await expect(verifier.getByRole("heading", { level: 1 })).toHaveText("This proof has been revoked.", { timeout: 5_000 });
    }).toPass({ timeout: 90_000, intervals: [2_000, 5_000, 10_000] });
    await expect(verifier.getByText("Revoked", { exact: true })).toBeVisible();
    await expect(verifier.getByRole("term")).toHaveCount(0);
  });
});
