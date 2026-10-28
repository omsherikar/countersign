# Flows

Each flow lists steps, the state after each step, and the exact copy where it matters. Copy ids in brackets refer to `05-copy-deck.md`. Endpoints refer to `docs/API_CONTRACT.md`; those marked (pending) are named for Addendum 4, which is being written alongside, and the contract wins where it differs.

The model every flow follows (the frozen SIH deck): a college upload is a claim. Each fact on it is matched to a source, labelled with who supplied it and when, and judged Confirmed, Contradicted, Pending, Not yet due, Not applicable or Source unavailable. A record is Countersigned only when the evidence for its route and stage is complete and nothing is unresolved. A student who never joined says so after signing in with DigiLocker, which opens a priority dispute. Officers decide (claim upheld, corrected, withdrawn or escalated), and the record, the seat count and the attestation update together.

## Flow 0. The panel demo and the 60-second path

Fixed cast: `admin@aicte.demo`, `ro.west@aicte.demo`, `registrar@abc.edu.demo`, `registrar@xyz.edu.demo`, the demo students signed in through the Demo DigiLocker (Ravi Kumar Sharma first), `coe@univ.demo`, and a phone for the verifier. Planted scenarios come from datagen `ground_truth.json`: the deck's sample record (ABC College CSE, Identity Confirmed, Seat fits approval v2, Joining record not found, Credits not yet due, Student "I never joined"); a clean record with an independent joining record; a record with only self-issued credits; a refused-consent student with a provisional ID; a college that left students out; the 40-student ring across 3 colleges and the planted anomalies; a legal dual enrolment.

The 60-second path (D49, and the Playwright end-to-end path):
1. `/login` as the AICTE officer. `/aicte` shows Records by status: Awaiting evidence, Countersigned, Under review, Disputed, with counts. Narrator: "Every enrolment is a claim. We show the evidence behind it."
2. Open the sample record from the Disputed tile. The deck's card: Identity Confirmed (APAAR verification · 12 Aug), Seat "Confirmed: fits approved intake" (AICTE approval v2, 2026-27, Seat Ledger, derived), Joining record "Contradicted: not found" (State admission authority · 20 Aug), Credits Not yet due (First semester not complete), Student "Contradicted: "I never joined"" (Student sign-in via DigiLocker · 22 Aug). Footer: "Status: Disputed (priority). Next step: College asked for admission documents by 29 Aug." Narrator: "Identity is confirmed and the record is still disputed. There is no score that four positives can win."
3. Open its Student dispute case. The college's response is in the history. Decide: Withdraw claim. The sheet names every consequence: record withdrawn, seat CSE-R-014 released, attestation revoked, nothing deleted. Confirm.
4. Back on the record: the withdrawn banner; the Seat Ledger's CSE seated count is one lower; the attestation reads Revoked at `/verify`; `/admin/audit` shows the decision entries and Verify chain reads intact. Narrator: "Colleges make claims, evidence backs or contradicts them, students can say not me, and officers decide."

The full panel demo (about 10 minutes):

| Min | Role | Screen | What the judge sees |
|---|---|---|---|
| 0:00 | none | `/login` | Role cards with "Demo credentials"; the Student card reads "Student / Sign in with DigiLocker", no password. |
| 0:30 | AICTE_ADMIN | `/aicte` | Records by status tiles with the evidence rule under them; completeness and deadlines; open cases by type; the officers-only signals panel. No map, no score. |
| 1:15 | AICTE_ADMIN | the sample record | The deck's card, exactly. The status badge is the largest mark; one contradiction outranks four confirmations. |
| 2:00 | STUDENT | Mailpit, then `/student/notices/[token]` | The email only points to DigiLocker sign-in. The notice page shows the claim and "Sign in with DigiLocker to answer". The Demo DigiLocker (labelled "Demo DigiLocker, synthetic data") picks the seeded "No" student, OTP 123456, Allow. Back on the notice: "No, I never joined", the No sheet says it opens a priority dispute. The record turns Disputed (priority). |
| 3:00 | STUDENT | the same link, another account | Signed in as someone else: "This notice is for someone else. Nothing was recorded." |
| 3:20 | RO_OFFICER | `/ro/cases/[dispute]` | Request documents: "Admission documents", reply by 29 Aug. The record's next step reads "College asked for admission documents by 29 Aug." |
| 3:50 | INSTITUTION | `/college/cases/[same]` | The registrar responds with a PDF and a note. |
| 4:20 | AICTE_ADMIN | `/aicte/cases/[same]` | Withdraw claim: the consequences listed, the acknowledgement ticked, confirm. Record withdrawn, seat released, attestation revoked, in one step. |
| 5:00 | AICTE_ADMIN | two records | A clean record Countersigned with no student answer (independent joining record). A record with only self-issued credits stays Awaiting evidence, its Credits row marked "From the college itself". |
| 5:40 | STUDENT | `/student/claim` | The refused-consent student signs in with DigiLocker, claims the record with the provisional ID; Identity reads Confirmed (Student sign-in via DigiLocker) and the record becomes Countersigned. |
| 6:20 | AICTE_ADMIN | `/aicte/institutions/[xyz]/completeness` | "92% of joined students uploaded, 14 missing", deadline Late, the Missing from upload case. |
| 6:50 | AICTE_ADMIN | `/aicte/signals/[ring]` | 40 students across 3 colleges, the rule line, members masked. Open case for one college; the dialog says its records read Under review until decided. No record changed before that. |
| 7:30 | RO_OFFICER | `/ro/reports` | Region-scoped reports, the synthetic data line; one CSV and the one-page PDF download. |
| 8:00 | STUDENT, VERIFIER | `/student/wallet`, then `/verify/[code]` | Ravi shares 3 fields of his enrolment attestation; the phone reads "Valid attestation" with only those fields. |
| 8:30 | UNIVERSITY | `/university/certificates` | "Countersign does not issue degrees." Issue a completion attestation, print the certificate block; its QR verifies. |
| 9:00 | AICTE_ADMIN | `/admin/system`, a record | Chaos APAAR down; a new upload's Identity rows read Source unavailable, never Contradicted; reset and Recheck evidence: Confirmed. |
| 9:30 | AICTE_ADMIN | `/admin/evaluation` or `eval_report.md` | Synthetic numbers with targets; close on the tagline. |

Hard rules for the demo: no map anywhere; no unmasked id anywhere; no score or "n of 5"; record statuses only the four words; case statuses only Open, Documents requested, Escalated, Claim upheld, Claim corrected, Claim withdrawn; the Demo DigiLocker is always labelled; `/admin/system` reset is pressed before the panel enters.

## Flow 1. Sign-in, per role

Officers, registrars and the university sign in with email and password; students sign in only with DigiLocker (D37).

Email and password (unchanged from Week 1):
1. Visitor opens `/login`. Role cards (AICTE officer, Regional officer West, Registrar ABC College, Registrar XYZ Institute, University) with "Demo credentials" [login.demo_tag], and a collapsed "Sign in with email" form.
2. Click a card: the form expands prefilled; focus moves to "Sign in".
3. Submit `POST /auth/login`; "Signing in", form disabled.
4a. 200: `router.replace` to the landing route: AICTE_ADMIN `/aicte`, RO_OFFICER `/ro`, INSTITUTION `/college`, UNIVERSITY `/university`.
4b. 401 [err.INVALID_CREDENTIALS]; 4c. 429 [err.RATE_LIMITED] with a countdown; 4d. 422 field errors; 4e. [err.NETWORK].

Student, through DigiLocker:
1. The Student card [login.card.student] with [login.digilocker_hint] is a link to `GET /auth/digilocker/start?next=/student` (pending). No password field exists for a student.
2. The api redirects to mockgov `GET /digilocker/oauth/authorize`. The Demo DigiLocker page [dldemo.title] shows [dldemo.banner] and the account picker; Ravi Kumar Sharma is first. Continue.
3. OTP step [dldemo.otp_heading]: 123456. A wrong OTP shows [dldemo.otp_wrong].
4. Consent step [dldemo.consent_heading]: Allow returns to `GET /auth/digilocker/callback`; Deny returns as cancelled.
5. The callback signs the STUDENT in (the account is created on first sign-in and bound by APAAR, or later by provisional ID) and redirects to `/auth/digilocker/return?next=`, which shows [signin.returning] and goes to `next` (same-origin paths only).
6. Errors on return: cancelled [err.DIGILOCKER_CANCELLED]; failed [err.DIGILOCKER_FAILED]; stale or cross-browser state [err.DIGILOCKER_STATE_INVALID]; each with [signin.try_again]. Nothing is recorded by a failed sign-in.

Session expiry: any 401 during use shows [err.UNAUTHENTICATED] with a button to `/login?next=<path>`; a student goes back through DigiLocker. Sign out: user menu, `POST /auth/logout`, `/login`, toast "Signed out".

## Flow 2. Officer triage and decisions

Actor: AICTE_ADMIN or RO_OFFICER.

1. Land on `/aicte` or `/ro`. `GET /dashboard/summary` with `by_status`, completeness, deadlines, cases by type and the signals panel (pending fields). State: Records by status tiles in legend order, the evidence rule, completeness and deadlines, open cases by type, signals (officers only), institutions ranked by open cases.
2. Pick an institution or a status tile. Institution detail: programmes with approval versions, the Enrolments tab with the Status column (sorted Needs attention first), the Cases tab, the Completeness tab.
3. Open a record. The record card (W4-1): five rows with evidence state, finding, source and date, independence marker; the footer's status and next step; Why. The officer reads which row decides the status.
4. Open the case from the record's Cases list or the queue (`/aicte/cases`, `/ro/cases`, `GET /flags`). Case detail: evidence (summary, facts, rule), related records with their status, history, the action bar.
5. Gather more if needed. Request documents: choose What to send ([case.docs_kind_label]) and a reply date; the sheet says the record's next step will read "College asked for admission documents by 29 Aug." ([case.request_docs_change]). Status Documents requested; every registrar account gets [email.docs_request.*]. The college responds (W3-7); the case shows [case.response_badge].
6. Decide (D43), each with a reason and a note; each sheet lists exactly what will change, from the dry run (pending):
   - Uphold claim: the case closes as Claim upheld; the contradicted row stays, marked [evidence.resolved.UPHELD]; the status is worked out again and becomes Countersigned only with independent evidence, else Awaiting evidence ([case.uphold_change.not_evidence]); no seat changes; a dispute-revoked attestation is reissued once Countersigned. On a programme-level case Uphold needs an approval version that covers the admissions.
   - Correct record: choose fields and values; stored as version n with the officer and reason; every row re-run; a seat released and reassigned when programme, year, route or eligibility changes; the case closes as Claim corrected.
   - Withdraw claim: pick the records (all for a one-record case); each becomes Withdrawn ("withdrawn by decision"), its seat released, its attestation revoked, nothing deleted; the acknowledgement must be ticked; the case closes as Claim withdrawn.
   - Escalate (RO to AICTE): reason and note; nothing about the record changes; only AICTE can decide it.
7. After a decision: the toast names the result ([case.withdrawn_toast] and the others, with singular nouns when a count is 1), the history gains the row with its reason, the related records refetch with their new status, the Seat Ledger counts change the same moment, and the audit log holds every change. The registrar reads [college.decision_line]; on a Student dispute the student reads `student.decision.*`.
8. Back to queue returns with the queue scrolled to the next open case. An AICTE officer can Reopen a decided case with a note; reopening does not undo what the decision changed ([case.reopen_prompt]).

Keyboard: `j`/`k` move through the queue, `Enter` opens, `Esc` back. Decisions have no single-key shortcuts.

## Flow 3. College upload

Actor: INSTITUTION.

1. `/college/upload`, step 1 [upload.steps.choose]: drop zone, templates, the column list, academic year.
2. Choose a file. The browser checks type and size ([upload.err_type], [upload.err_size]); `POST /uploads/headers` (pending) reads the header row.
3. If every header matches the template or the saved mapping, skip to step 5. Otherwise step 2 [upload.steps.map]: Flow 11.
4. (Flow 11 returns here with the mapping saved.)
5. Step 3 [upload.steps.declare]: tick [upload.declaration]; Upload. `POST /uploads` (multipart `file`, `academic_year`, `declaration`); 202 navigates to `/college/uploads/[batchId]`.
6. The batch page polls `GET /uploads/{id}`: Queued, Validating, Processing, Done. [mapping.batch_line] names the mapping used. Row problems as W2-2.
7. Processing matches each row to an existing person and enrolment by stable keys (internal ids, APAAR as an attribute; D42); a changed field becomes a new version with the batch as its source, shown later in the record's History ("Programme changed from B.Tech ME to B.Tech CSE by upload on 14 Aug."). Then seats from the current approval version, the eligibility checks, and evidence from each source: APAAR verification, the state admission authority's joining record, ABC credits with their issuer. A source that does not answer leaves its rows Source unavailable ([upload.source_waiting]); the batch still reaches Done.
8. Done: [upload.done_summary], [upload.done_changes], then [upload.done_status] (the batch's records by status) and, when students are still missing, [upload.done_completeness] linking to `/college/completeness`; [upload.done_note]. Links to the Seat Ledger, enrolments and cases.
9. `/college`: Records by status, the Seat Ledger, completeness and the deadline word. An excess admission shows on the Seat row as "Contradicted: beyond approved intake" with its case, the same day; nothing is rejected.

Error cases: 413 [err.FILE_TOO_LARGE] or [err.TOO_MANY_ROWS]; 415 [err.UNSUPPORTED_FILE_TYPE]; 422 [err.UPLOAD_HEADER_INVALID], [err.UPLOAD_EMPTY], [err.MAPPING_INCOMPLETE], [err.MAPPING_DUPLICATE]; 409 [err.UPLOAD_IN_PROGRESS]. An unavailable source never fails the batch and never contradicts a row.

## Flow 4. Student notice, through DigiLocker sign-in

Actor: STUDENT, starting from an email (Mailpit in the demo) or the DigiLocker inbox (mockgov).

1. When a batch is Done, every active record in it gets a notice: by email when the college gave an address, and to the DigiLocker inbox when the student has a linked APAAR (D23). The email is a pointer only ([notice.email_subject], [notice.email_body], with the Hindi text under it): it shows no buttons and nothing in it can record an answer.
2. The student opens the link `/student/notices/[token]`. `GET /notices/{token}`. State: the claim card (institution, programme, academic year, year of study, upload date, masked APAAR or provisional ID), then [notice.signin_lead] and [notice.signin_button]. No Yes or No yet.
3. Sign in with DigiLocker (Flow 1, student part) with `next` = the notice. Back on the notice, `GET /notices/{token}` returns `viewer.match` (pending):
4a. MATCH (the DigiLocker identity holds the record's APAAR, or has claimed its provisional ID): [notice.signed_in_as], [notice.signout], then [notice.yes] "Yes, I joined" and [notice.no] "No, I never joined", with [notice.next_step] and [consent.notice].
4b. SOMEONE_ELSE: [notice.someone_else_heading] with its three lines and Sign out. Nothing is recorded. A later `POST /notices/{token}/respond` from this session returns 403 `NOTICE_IDENTITY_MISMATCH`.
4c. CLAIM_NEEDED (the record has no APAAR and this sign-in has not claimed it): [notice.claim_needed] and [notice.claim_button] to `/student/claim?next=`. Claiming (step 7) returns here as MATCH.
5. Yes: `POST /notices/{token}/respond {response: "YES"}` with the student session. [notice.yes_done] and [notice.yes_next]. The Student row reads Confirmed "I joined", Student sign-in via DigiLocker · date, Independent of the college. The record becomes Countersigned if identity and seat are Confirmed and nothing is unresolved.
6. No: the sheet [notice.no_confirm] with the optional comment, then `{response: "NO", comment?}`. [notice.no_done]. The Student row reads Contradicted "I never joined"; a Student dispute case opens (High, priority); the record reads Disputed (priority) and any attestation is revoked (R6). The enrolment itself is not changed: only an officer's decision changes it.
7. Claim by provisional ID (`/student/claim`): the student types PRV-XXXXXXXX; `POST /students/me/claim` (pending) matches DigiLocker's name and date of birth with the record (name matching supports, the sign-in decides). Match: [claim.done]; Identity reads Confirmed (Student sign-in via DigiLocker); the record may become Countersigned. Otherwise [err.CLAIM_NO_MATCH] (one answer for an unknown ID and a mismatch), [err.CLAIM_ALREADY_CLAIMED] or [err.CLAIM_NOT_NEEDED]; five failures pause claiming ([claim.locked]).
8. No answer: nothing happens. The Student row stays Pending ("no answer yet", then "no answer" after expiry) and never counts against the record or the college.
9. After an officer decides the dispute, `/student` and `/student/notices` show `student.decision.*` in place of [notices.denied_line].
10. Expired, invalid, already answered and change-once states as W3-1; a change from No to Yes keeps the case open with a System row.

## Flow 5. Attestation share

Actor: STUDENT, then a VERIFIER.

1. `/student/wallet` ([nav.wallet] "My attestations"). `GET /credentials`. One card per attestation: Enrolment attestation or Completion attestation, issuer, dates, status.
2. An enrolment attestation exists only for a Countersigned record (D44). Otherwise the card reads [wallet.not_issued_heading] with the line for the record's status ([wallet.not_issued.AWAITING_EVIDENCE], [wallet.not_issued.UNDER_REVIEW] or [wallet.not_issued.DISPUTED]); it never names a case or a row.
3. Share attestation: the sheet lists the 8 fields, Institution and Programme locked; the Countersigned field shares "Countersigned, as of <date>", never rows or a count. [consent.credential_share] (text version 2) with "I agree".
4. `POST /credentials/{id}/present`; QR, the 6-group code, "Shares n of 8 fields", "Valid for 10 minutes".
5. The verifier scans; `/verify/[code]`: [verify.valid] "Valid attestation", the issuer, only the shared fields, "Revocation checked just now".
6. Revoked (an officer's Withdraw claim, a dispute, an officer's revoke, or the college reporting the student withdrawn): [verify.revoked] with no reason; the wallet card shows Revoked with the `wallet.revoked_reason.*` sentence. Expired and invalid as before.
7. The wallet's history shows "Shared with a verifier at 10:42".

## Flow 6. Certificate integration (university)

Actor: UNIVERSITY. Countersign does not issue degrees (D44).

1. `/university/certificates` ([nav.certificates]). [cert.lead] and the how-it-works disclosure. `GET /university/graduates?q=` lists graduates of affiliates with their completion attestation status.
2. A graduate whose record is not Countersigned shows [cert.status.not_eligible] and no action.
3. For a Countersigned record: [cert.issue] opens the sheet ([cert.issue_body]: it is not a degree; the certificate remains the degree). `POST /university/certificates/{enrolment_id}/issue` (pending path). [cert.issued_toast]; the attestation is in the graduate's wallet.
4. [cert.print_block] opens `/university/certificates/[enrolmentId]/print`: name, programme, institution, year of completion, "APAAR XXXX XXXX 4417" (or the provisional ID), the QR with "Attestation id" and "Scan to verify at ..." as text, and [cert.print.signed]. `window.print()`; no colour backgrounds. [cert.pdf] gives the block as a PDF for the university's certificate template.
5. The university's own system can fetch the same data (`GET /university/certificates/{enrolment_id}`, [cert.api_line]) and print it on its certificate.
6. A scanned QR opens `/verify/d/[jws]`: [verify.completion_valid] with [verify.completion_sub] ("This is not a degree; the degree is the certificate it is printed on."). If the record is later withdrawn, the attestation is revoked and the QR reads Revoked.

## Flow 7. Demo reset

Actor: AICTE_ADMIN on `/admin/system`. CLI equivalent `make demo-reset`.

1. Section "Demo controls" (labelled Demo). Buttons: "Reset chaos" (`POST mockgov /admin/chaos/reset`), "Reset demo data" (proposed `POST /admin/demo/reset`, see gaps), "Re-seed" (same endpoint).
2. "Reset demo data" opens a sheet with [admin.reset_confirm]: every upload, case, decision and answer since the last seed is removed. Buttons "Reset" and "Cancel".
3. During reset the page shows a progress line and disables all other controls.
4. After reset: toast [admin.reset_done] and the adapter ping re-runs. The seed's planned student answers are recorded as DigiLocker-authenticated answers (D37), so the sample record reads Disputed (priority) again.
5. Reset never signs anyone out; the seeded users and passwords, and the Demo DigiLocker accounts, are unchanged.

## Flow 8. Role mismatch and out-of-scope

1. Registrar opens `/aicte`. Layout `getMe()` sees role INSTITUTION, redirects to `/college`, toast [err.FORBIDDEN_redirect].
2. RO West opens `/ro/institutions/[southId]`. API 404. Page shows [err.NOT_FOUND_institution] with a "Back to overview" link. The page never says the institution exists elsewhere.
3. Student opens any officer route: redirect to `/student`.
4. Registrar, university or student opens `/aicte/signals` or `/ro/signals`: redirect to their landing route with the toast; the api answers 403 to any `/signals` request from those roles, and no page of theirs ever requests one.
5. A student signed in with DigiLocker opens another student's notice link: [notice.someone_else_heading]; nothing is recorded (Flow 4, 4b).

## Flow 9. Completeness review

Actor: AICTE_ADMIN or RO_OFFICER, then the INSTITUTION. D40.

1. `/aicte` (or `/ro`): the Completeness and deadlines panel lists colleges by missing count, each with [completeness.line] and its deadline word (On time, Late, Overdue, or Due by date) with an icon.
2. Pick a college. Its Completeness tab: [completeness.line], the deadline word with [deadline.tip.*] as visible text, Joined (authority), Uploaded and joined, Missing; [missing.case_line] linking to the Missing from upload case (Medium, one per college and year).
3. Read the missing list: masked ids only, programme, joined date, admission round. Download it as CSV if needed.
4. Open the case. Its evidence lists the counts, the deadline and the missing students by masked id, with the rule [flag.MISSING_FROM_UPLOAD.rule]. Request documents if needed ("What to send": Other documents, or the joining report), with a reply date.
5. The registrar sees the same numbers on `/college` and `/college/completeness` with [missing.lead_college], and uploads the missing rows (Flow 3). Each upload refreshes the reconciliation; the case gains [case.system_note.missing_updated] and the completeness line rises.
6. When nothing is missing, or the officer finds the authority's list was wrong, the officer decides Uphold claim with the reason "The missing students are now uploaded" or "The source's record was wrong or late". Correct and Withdraw are not offered: the case names no record.
7. Deadlines are reported, never enforced: a Late or Overdue college is shown so, and nothing it uploads is refused.

## Flow 10. Signal to case

Actor: AICTE_ADMIN or RO_OFFICER. D45, R5.

1. The dashboard's Signals panel shows [signal.count] and the newest summaries, with [signal.never_status]. Or open `/aicte/signals`.
2. Open a signal. Read the summary, the facts table, the rule line ([signal.rule.GHOST_RING] or [signal.rule.ANOMALY]), the members (masked) and, for a ring, the drawing beside the facts. Nothing on any record has changed: the members' records keep their status, and no college, university or student can see the signal.
3a. Open case: the dialog [signal.open_case_heading] says what the case is, lists the colleges to open it for, and names the consequence [signal.open_case_change]: the records the case names read Under review until an officer decides. A note is required. `POST /signals/{id}/open-case` (pending). One case per chosen college, each citing the signal ([case.from_signal], [case.history.opened_from_signal]); the signal reads Case opened with [signal.case_link].
3b. Dismiss: the dialog [signal.dismiss_heading] with a required note (officers only). The signal reads Dismissed with [signal.dismissed_line]. No record or case changes.
4. From here the case is like any other (Flow 2): the college can respond with documents, and an officer decides Uphold claim, Correct record or Withdraw claim per named record, with every consequence named.
5. If another officer acted first, [err.SIGNAL_ALREADY_HANDLED] and the page refetches.

## Flow 11. Column mapping

Actor: INSTITUTION. D42.

1. In Flow 3, the chosen file's headers are read (`POST /uploads/headers`, pending). Every header matches the template or the saved mapping: the step is skipped and the batch later shows [mapping.batch_line].
2. Otherwise step 2 [mapping.step]: [mapping.lead] (or [mapping.lead_saved] with the counts), then one row per column of the file: its name as uploaded and a select of Countersign columns, prefilled from the saved mapping and from exact name matches, with Not used for the rest.
3. The registrar maps each column. [mapping.required_missing] and [mapping.duplicate] update as they choose; no student value from the file is shown.
4. [mapping.continue] with [mapping.saved_for_next_time] ticked: `PUT /institutions/{id}/column-mapping`; [mapping.saved]. Unticked: the mapping is used for this file only. Problems move focus to the first one and nothing is sent ([err.MAPPING_INCOMPLETE], [err.MAPPING_DUPLICATE]).
5. Step 3 of Flow 3 (declare and upload). The next file with the same headers maps itself.
6. `/college/column-mapping` shows the saved mapping; Change mapping edits it, Clear saved mapping removes it after [mapping.reset_confirm].
