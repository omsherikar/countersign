import {
  ABC,
  DEMO,
  abcEnrolmentOf,
  abcNoticeEmail,
  apiJson,
  backOnCountersign,
  cardRow,
  cardStatusLine,
  digiLockerSignIn,
  expect,
  expectValidShare,
  findOpenAbcNotice,
  note,
  readNotice,
  recordCard,
  shareThreeFields,
  test,
  type EnrolmentDetail,
  type OpenNotice,
} from "./support";

/**
 * Flows 4 and 5 (Flow 0 at 2:00, 3:00 and 8:00): Ravi opens his notice from
 * the email in Mailpit. Anyone with the link sees the claim, but only after
 * DigiLocker sign-in as the student it is about can it be answered. Ravi
 * says Yes; his Student row is confirmed through DigiLocker. With his
 * record Countersigned, his wallet holds an enrolment attestation; he
 * shares three fields and a verifier sees exactly those. Another student
 * signed in with DigiLocker gets "This notice is for someone else" and can
 * record nothing.
 */

const DAY = String.raw`\d{1,2} [A-Z][a-z]{2}`;

let answered: OpenNotice | null = null;

test.describe.configure({ mode: "serial" });

test.describe("A student's Yes", () => {
  test("the notice from Mailpit asks for DigiLocker sign-in, and Yes after it confirms the Student row", async ({ pageAs, studentAs, freshPage, request }) => {
    const admin = await pageAs("admin");
    const ravi = await abcEnrolmentOf(admin, DEMO.ravi.name, DEMO.ravi.apaarLast4);

    // The link exists only in the message; Ravi's address is on his own home page.
    const found = await abcNoticeEmail(await studentAs(DEMO.ravi), request, DEMO.ravi.apaarLast4);
    if (found.token) {
      answered = { token: found.token, enrolmentId: ravi.id, programmeCode: ravi.programme_code, student: DEMO.ravi };
      // The email is a pointer only: nothing in it can record an answer.
      expect(found.text).toContain("sign in with DigiLocker");
      expect(found.text).toContain("nothing in this email can record it");
    } else {
      expect(found.answered, `Ravi's notice email (to ${found.email}) is in Mailpit`).toBe(true);
      note("Ravi's notice was answered by an earlier run (make demo-reset restores it); this run answers another unanswered ABC College notice.");
      answered = await findOpenAbcNotice(admin, request, (who) => studentAs(who), { skipApaarLast4: [] });
      test.skip(!answered, "No unanswered ABC College email notice is left; run make demo-reset.");
    }
    const { token, student } = answered!;

    // Signed out, the link shows the claim and the way to sign in, never the question.
    const page = await freshPage();
    await page.goto(`/student/notices/${token}`);
    await expect(page.getByText(`${ABC.name} says`, { exact: true })).toBeVisible();
    await expect(page.getByText(new RegExp(`for APAAR XXXX XXXX ${student.apaarLast4}\\.$`))).toBeVisible();
    await expect(page.getByText(student.name)).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Yes, I joined" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "No, I never joined" })).toHaveCount(0);
    const signIn = page.getByRole("link", { name: "Sign in with DigiLocker to answer" });
    await expect(signIn).toBeVisible();

    await signIn.click();
    await digiLockerSignIn(page, student);
    await backOnCountersign(page, `/student/notices/${token}`);
    await expect(page.getByText(`Signed in with DigiLocker as ${student.name}.`, { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Is that right?" })).toBeVisible();
    await page.getByRole("button", { name: "Yes, I joined" }).click();
    await expect(page.getByText(`Thank you. Your answer is recorded: you joined ${ABC.name}.`)).toBeVisible();

    // The officer reads the answer as independent evidence from DigiLocker sign-in.
    await admin.goto(`/aicte/enrolments/${answered!.enrolmentId}`);
    const row = cardRow(recordCard(admin), "Student");
    await expect(row.state).toHaveText('Confirmed: "I joined"');
    await expect(row.source).toHaveText(new RegExp(`^Student sign-in via DigiLocker · ${DAY}\\s*Independent of the college$`));
  });

  test("the record is Countersigned and the wallet's enrolment attestation shares three fields that verify as Valid", async ({ pageAs, studentAs, freshPage }) => {
    expect(answered, "the Yes step ran").not.toBeNull();
    const admin = await pageAs("admin");
    const record = await apiJson<EnrolmentDetail>(admin, "GET", `/enrolments/${answered!.enrolmentId}`);
    test.fixme(
      answered!.student.name === DEMO.ravi.name && record.record_status === "UNDER_REVIEW",
      "Product bug: the open R. K. Sharma duplicate case keeps Ravi's record Under review, so no enrolment attestation exists for the 8:00 share step.",
    );

    await admin.goto(`/aicte/enrolments/${answered!.enrolmentId}`);
    await expect(cardStatusLine(recordCard(admin))).toHaveText(/^Status:\s*Countersigned\./);

    const wallet = await studentAs(answered!.student, "/student/wallet");
    await expect(wallet.getByRole("heading", { level: 1, name: "My attestations" })).toBeVisible();
    const { code } = await shareThreeFields(wallet);

    const verifier = await freshPage();
    await expectValidShare(
      verifier,
      code,
      [
        ["Institution", `${ABC.name} (${ABC.permanentId})`],
        ["Programme", /\((UG|PG)\)$/],
        ["Academic year", "2026-27"],
      ],
      [answered!.student.name, `XXXX XXXX ${answered!.student.apaarLast4}`],
    );
  });

  test("another student signed in with DigiLocker is told the notice is for someone else, and nothing is recorded", async ({ studentAs, request }) => {
    expect(answered, "the Yes step ran").not.toBeNull();
    const { token } = answered!;
    const before = (await readNotice(request, token)).notice?.response;

    const page = await studentAs(DEMO.someoneElse, `/student/notices/${token}`);
    await expect(page.getByRole("heading", { level: 2, name: "This notice is for someone else" })).toBeVisible();
    await expect(page.getByText(`You are signed in with DigiLocker as ${DEMO.someoneElse.name}, but this notice is about a different person's record. Nothing was recorded.`)).toBeVisible();
    await expect(page.getByText(answered!.student.name)).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Yes, I joined" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "No, I never joined" })).toHaveCount(0);

    // An answer sent from this session anyway is refused, and the notice keeps its answer.
    const res = await page.request.post(`/api/notices/${token}/respond`, { data: { response: "NO" } });
    expect(res.status()).toBe(403);
    expect(((await res.json()) as { error: { code: string } }).error.code).toBe("NOTICE_IDENTITY_MISMATCH");
    expect((await readNotice(request, token)).notice?.response).toBe(before);
  });
});
