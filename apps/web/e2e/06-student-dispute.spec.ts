import {
  ABC,
  DEMO,
  MOCKGOV_URL,
  RUN,
  abcEnrolmentOf,
  abcId,
  apiJson,
  backOnCountersign,
  cardRow,
  cardStatusLine,
  digiLockerSignIn,
  expect,
  findOpenAbcNotice,
  note,
  noticeToken,
  readNotice,
  recordCard,
  test,
  type EnrolmentDetail,
  type FlagRow,
  type OpenNotice,
  type Paged,
} from "./support";

/**
 * Flow 4, the No (Flow 0 at 2:00 and the deck's hero feature): Xavier Paul
 * opens his notice from the Demo DigiLocker inbox, signs in with DigiLocker
 * and says he never joined. The record turns Disputed (priority), a High
 * Student dispute case opens, and the attestation his record held is
 * revoked. Officers read his comment; the registrar never does.
 */

const DAY = String.raw`\d{1,2} [A-Z][a-z]{2}`;
const comment = `I never joined ABC College. Someone used my APAAR (${RUN}).`;

let disputed: OpenNotice | null = null;
let caseId = "";

test.describe.configure({ mode: "serial" });

test.describe("A student's dispute", () => {
  test("a No after DigiLocker sign-in disputes the record, opens a Student dispute case and revokes the attestation", async ({ pageAs, freshPage, studentAs, request }) => {
    const admin = await pageAs("admin");
    const xavier = await abcEnrolmentOf(admin, DEMO.xavier.name, DEMO.xavier.apaarLast4);

    const page = await freshPage();
    await page.goto(`${MOCKGOV_URL}/digilocker/ui?apaar_id=${DEMO.xavier.apaarId}`);
    await expect(page.getByRole("heading", { name: `Inbox for APAAR XXXX XXXX ${DEMO.xavier.apaarLast4}` })).toBeVisible();
    const message = page.getByRole("listitem").filter({ hasText: ABC.name }).first();
    await expect(message).toContainText("Sign in to Countersign with DigiLocker to answer.");
    const respond = message.getByRole("link", { name: "Respond" });
    const token = noticeToken((await respond.getAttribute("href")) ?? "");
    expect(token, "the Respond link carries a notice token").toBeTruthy();

    const { status, notice } = await readNotice(request, token!);
    expect(notice, `the Respond link opens a notice (GET /notices answered ${status})`).not.toBeNull();
    if (notice!.response === null) {
      disputed = { token: token!, enrolmentId: xavier.id, programmeCode: xavier.programme_code, student: DEMO.xavier };
      await respond.click();
      await expect(page).toHaveURL(new RegExp(`/student/notices/${token}$`));
    } else {
      note(`${DEMO.xavier.name}'s notice was answered by an earlier run (make demo-reset restores it); this run disputes another unanswered ABC College notice from Mailpit.`);
      disputed = await findOpenAbcNotice(admin, request, (who) => studentAs(who), { skipApaarLast4: [] });
      test.skip(!disputed, "No unanswered ABC College email notice is left; run make demo-reset.");
      await page.goto(`/student/notices/${disputed!.token}`);
    }
    const { student, enrolmentId } = disputed!;
    const before = await apiJson<EnrolmentDetail>(admin, "GET", `/enrolments/${enrolmentId}`);
    const live = before.credentials.filter((c) => c.kind === "ENROLMENT" && c.status === "ACTIVE");

    // The question appears only after signing in as the student the notice is about.
    await expect(page.getByRole("button", { name: "No, I never joined" })).toHaveCount(0);
    await page.getByRole("link", { name: "Sign in with DigiLocker to answer" }).click();
    await digiLockerSignIn(page, student);
    await backOnCountersign(page, `/student/notices/${disputed!.token}`);
    await expect(page.getByText(`Signed in with DigiLocker as ${student.name}.`, { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "No, I never joined" }).click();
    const sheet = page.getByRole("dialog");
    await expect(sheet).toContainText(`You are telling AICTE that you never joined ${ABC.name}. This opens a priority dispute`);
    await sheet.getByLabel("Anything we should know?").fill(comment);
    await sheet.getByRole("button", { name: "Send", exact: true }).click();
    await expect(page.getByText("Thank you. Your dispute is recorded and an AICTE officer will look into it first.", { exact: false })).toBeVisible();

    // A High Student dispute case names the record.
    const institution = await abcId(admin);
    const cases = await apiJson<Paged<FlagRow>>(admin, "GET", `/flags?institution_id=${institution}&type=STUDENT_DENIED&page_size=100`);
    const dispute = cases.items.find((f) => f.enrolment_id === enrolmentId);
    expect(dispute, "a Student dispute case on the record").toBeTruthy();
    expect(dispute!.severity).toBe("HIGH");
    caseId = dispute!.id;

    // The record reads Disputed (priority), whatever confirmed it before.
    await admin.goto(`/aicte/enrolments/${enrolmentId}`);
    const card = recordCard(admin);
    await expect(cardStatusLine(card)).toHaveText(/^Status:\s*Disputed \(priority\)\. Next step: /);
    const row = cardRow(card, "Student");
    await expect(row.state).toHaveText('Contradicted: "I never joined"');
    await expect(row.source).toHaveText(new RegExp(`^Student sign-in via DigiLocker · ${DAY}\\s*Independent of the college$`));
    await expect(admin.getByRole("region", { name: "Cases about this record" }).getByRole("link", { name: "Student dispute" })).toBeVisible();

    // The attestation the record held is revoked by the dispute (R6).
    const after = await apiJson<EnrolmentDetail>(admin, "GET", `/enrolments/${enrolmentId}`);
    expect(after.credentials.filter((c) => c.kind === "ENROLMENT" && c.status === "ACTIVE"), "no live enrolment attestation on a disputed record").toHaveLength(0);
    if (live.length === 0) {
      note(`${student.name}'s record held no live attestation before the dispute, so there was none to revoke.`);
    } else {
      for (const c of live) expect(after.credentials.find((x) => x.id === c.id)?.revoked_reason_code).toBe("STUDENT_DISPUTE");
      const attestations = admin.getByRole("region", { name: "Attestations" });
      await expect(attestations.getByText(new RegExp(`^Enrolment attestation ${live[0].short_id}, issued `))).toBeVisible();
      await expect(attestations.getByText("You told us you never joined, so this attestation was revoked while an officer reviews it.").first()).toBeVisible();
    }
  });

  test("the regional officer reads the student's comment; the registrar does not", async ({ pageAs }) => {
    expect(caseId, "the No step opened a case").toBeTruthy();
    const ro = await pageAs("ro");
    await ro.goto(`/ro/cases/${caseId}`);
    await expect(ro.getByRole("heading", { level: 1, name: "Student dispute" })).toBeVisible();
    await expect(ro.getByRole("img", { name: "Severity high" }).first()).toBeVisible();
    const officerEvidence = ro.getByRole("article", { name: /^Student dispute:/ });
    await expect(officerEvidence).toContainText("Comment from the student");
    await expect(officerEvidence).toContainText(comment);

    const registrar = await pageAs("registrar");
    await registrar.goto(`/college/cases/${caseId}`);
    await expect(registrar.getByRole("heading", { level: 1, name: "Student dispute" })).toBeVisible();
    await expect(registrar.getByRole("article", { name: /^Student dispute:/ })).toContainText("Signed in with");
    await expect(registrar.getByText("Comment from the student")).toHaveCount(0);
    await expect(registrar.getByText(comment)).toHaveCount(0);
  });
});
