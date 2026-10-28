import {
  ABC,
  DEMO,
  MOCKGOV_URL,
  RUN,
  abcId,
  apiJson,
  expect,
  findOpenAbcNotice,
  note,
  noticeToken,
  readNotice,
  test,
  type EnrolmentRow,
  type FlagRow,
  type Paged,
} from "./support";

/**
 * Flow 4b: the second demo student opens the notice from the mock
 * DigiLocker inbox and answers No with a comment. AICTE gets a High
 * Student denied flag; the officer reads the comment, the registrar never
 * sees it.
 */

const comment = `I never joined ABC College. Someone used my APAAR (${RUN}).`;
let flagId = "";

test.describe.configure({ mode: "serial" });

test.describe("A student's No", () => {
  test("a No from the DigiLocker inbox raises a High Student denied flag for ABC College", async ({ pageAs, freshPage, request }) => {
    const admin = await pageAs("admin");
    const institution = await abcId(admin);
    const last4 = DEMO.second.apaarId.slice(-4);
    const candidates = await apiJson<Paged<EnrolmentRow>>(admin, "GET", `/institutions/${institution}/enrolments?academic_year=2026-27&q=${last4}&page_size=25`);
    const second = candidates.items.find((e) => e.student.name === DEMO.second.name);
    expect(second, `${DEMO.second.name} (APAAR ending ${last4}) is enrolled at ABC College`).toBeTruthy();
    let enrolmentId = second!.id;
    let apaarLast4 = last4;

    const page = await freshPage();
    await page.goto(`${MOCKGOV_URL}/digilocker/ui?apaar_id=${DEMO.second.apaarId}`);
    await expect(page.getByRole("heading", { name: `Inbox for APAAR XXXX XXXX ${last4}` })).toBeVisible();
    const respond = page.getByRole("listitem").filter({ hasText: ABC.name }).first().getByRole("link", { name: "Respond" });
    await expect(respond).toBeVisible();
    const token = noticeToken((await respond.getAttribute("href")) ?? "");
    expect(token, "the Respond link carries a notice token").toBeTruthy();

    const { status, notice } = await readNotice(request, token!);
    expect(notice, `the Respond link opens a notice (GET /notices answered ${status})`).not.toBeNull();
    if (notice!.response === null) {
      await respond.click();
      await expect(page).toHaveURL(new RegExp(`/student/notices/${token}$`));
    } else {
      note(`${DEMO.second.name}'s notice was answered by an earlier run (make demo-reset restores it); this run answers No on another unanswered ABC College notice from Mailpit.`);
      const other = await findOpenAbcNotice(admin, request, { skipApaarLast4: [DEMO.ravi.apaarLast4, last4] });
      test.skip(!other, "No unanswered ABC College email notice is left; run make demo-reset.");
      enrolmentId = other!.enrolmentId;
      apaarLast4 = other!.apaarMasked.slice(-4);
      await page.goto(`/student/notices/${other!.token}`);
    }

    await expect(page.getByRole("heading", { name: "Is that right?" })).toBeVisible();
    await expect(page.getByText(`XXXX XXXX ${apaarLast4}`, { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "No, that is not me" }).click();
    const sheet = page.getByRole("dialog", { name: "No, that is not me" });
    await sheet.getByLabel("Anything we should know?").fill(comment);
    await sheet.getByRole("button", { name: "Send", exact: true }).click();
    await expect(page.getByText("Thank you. An AICTE officer will look into this.")).toBeVisible();

    const flags = await apiJson<Paged<FlagRow>>(admin, "GET", `/flags?institution_id=${institution}&type=STUDENT_DENIED&page_size=100`);
    const flag = flags.items.find((f) => f.enrolment_id === enrolmentId);
    expect(flag, "a STUDENT_DENIED flag on the enrolment").toBeTruthy();
    expect(flag!.severity).toBe("HIGH");
    flagId = flag!.id;

    await admin.goto(`/aicte/enrolments/${enrolmentId}`);
    const studentCheck = admin
      .getByRole("table", { name: "Countersign checks" })
      .getByRole("row")
      .filter({ has: admin.getByRole("cell", { name: "Student", exact: true }) });
    await expect(studentCheck.getByRole("img", { name: "Not countersigned" })).toBeVisible();
  });

  test("the regional officer reads the student's comment; the registrar does not", async ({ pageAs }) => {
    expect(flagId, "the No step raised a flag").toBeTruthy();
    const ro = await pageAs("ro");
    await ro.goto(`/ro/cases/${flagId}`);
    await expect(ro.getByRole("heading", { level: 1, name: "Student denied" })).toBeVisible();
    await expect(ro.getByRole("img", { name: "Severity high" })).toBeVisible();
    const officerEvidence = ro.getByRole("article", { name: /^Student denied:/ });
    await expect(officerEvidence).toContainText("Comment from the student");
    await expect(officerEvidence).toContainText(comment);

    const registrar = await pageAs("registrar");
    await registrar.goto(`/college/flags/${flagId}`);
    await expect(registrar.getByRole("heading", { level: 1, name: "Student denied" })).toBeVisible();
    const collegeEvidence = registrar.getByRole("article", { name: /^Student denied:/ });
    await expect(collegeEvidence).toContainText("Channel");
    await expect(registrar.getByText("Comment from the student")).toHaveCount(0);
    await expect(registrar.getByText(comment)).toHaveCount(0);
  });
});
