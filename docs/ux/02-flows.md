# Flows

Each flow lists steps, the state after each step, and the exact copy where it matters. Copy ids in brackets refer to `05-copy-deck.md`. Endpoints refer to `docs/API_CONTRACT.md`; endpoints marked (W2), (W3), (W4) are not in the contract yet and are proposed there as gaps.

## Flow 0. The 10-minute panel demo

Fixed cast: `admin@aicte.demo`, `ro.west@aicte.demo`, `registrar@abc.edu.demo`, `student@demo`, `coe@univ.demo`, plus a phone for the verifier. Planted scenarios come from datagen `ground_truth.json`: ABC College CSE 132 admitted vs 120 approved; "Ravi Kumar Sharma" vs "R. K. Sharma"; a 40-student ring across 3 colleges; a second-year with 0 credits; a student who answers "No"; a legal dual enrolment.

Timing is for the full Week 4 build. Week 1 rehearsal uses steps 1, 2, 3, 8 and 10 only.

| Min | Role | Screen | Planted scenario | What the judge sees |
|---|---|---|---|---|
| 0:00 | none | `/login` | none | Six role cards, credentials prefilled, "Demo" tag. Narrator: "A college upload is a claim. Five sources countersign it." |
| 0:30 | AICTE_ADMIN | `/aicte` | national seed | KPI tiles (institutions, programmes, approved seats, enrolments, open flags). State grid, no map. Institutions ranked by open flags; ABC College on top. Sources panel all green. |
| 1:30 | AICTE_ADMIN | `/aicte/institutions/[abc]` | 132 vs 120 in CSE | Programme row CSE: approved 120, admitted 132, unseated 12, pools 114/6/6/12/18. Flag row "132 admitted against 120 approved seats in CSE (2026-27)", severity High, status Open. Narrator: "Nothing was rejected. A person decides." |
| 2:30 | RO_OFFICER | `/ro/cases` | region WEST queue | Only Western institutions. Queue sorted by severity then age. Narrator points at the count "37 open flags in 9 institutions". |
| 3:00 | RO_OFFICER | `/ro/cases/[nameMismatch]` | Ravi Kumar Sharma vs R. K. Sharma | Evidence panel: claimed name, registry similarity 71 of 100, date of birth matches, same mobile last four. Officer clicks "Request documents", writes "Send admission form and ID copy", submits. Status becomes Documents requested. |
| 4:00 | INSTITUTION | `/college/flags/[same]` | same | Registrar sees the request, uploads a PDF, writes "Student's full name per 10th certificate is Ravi Kumar Sharma", submits. Timeline shows both entries. |
| 4:30 | INSTITUTION | `/college/upload` | update file with 2 bad rows | Drag CSV, validation finds row 17 (APAAR not 12 digits, a warning: the row is kept without its APAAR) and row 41 (duplicate in file, an error: the row is not saved). Registrar downloads the error sheet, fixes row 41, uploads it again. Batch goes Queued, Validating, Processing, Done. |
| 5:30 | INSTITUTION | `/college` | ledger reaction | CSE row: admitted 133, seated 120, unseated 13, same day. Narrator: "The ledger has a row per approved seat, so excess shows the day it is uploaded." |
| 6:00 | STUDENT | Mailpit tab, then `/student/notices/[token]` | Ravi, LINKED | Email "ABC College of Engineering says you joined B.Tech CSE (2026-27). Is that right?" Click link, page shows the claim and two buttons. Click "Yes, that is right". Confirmation screen. Student check becomes Pass. |
| 6:45 | STUDENT | second token (the "No" student) | not-me scenario | Click "No, that is not me". Page: "Thank you. An AICTE officer will look into this." Officer queue gains a `STUDENT_DENIED` flag, High. |
| 7:15 | STUDENT | `/student/wallet` | Ravi credential | "Enrolment proof" card. Click "Share proof", untick date of birth, keep institution, programme, year. QR appears with "Shares 3 of 5 fields". |
| 7:45 | VERIFIER | phone camera -> `/verify/[code]` | same | "Valid. Issued by Countersign for ABC College of Engineering." Shows only the 3 shared fields, APAAR masked. "Checked against the revocation list just now." |
| 8:15 | UNIVERSITY | `/university/degrees/[id]/print` | graduating demo student | Print preview: name, programme, year, "APAAR XXXX XXXX 4417", QR. Narrator: "The degree carries the masked id and a scannable proof." |
| 8:45 | AICTE_ADMIN | `/admin/system` | chaos: APAAR down | Toggle "APAAR registry: down". Ping shows Unavailable. In the registrar's tab, upload a small file during the outage; as the officer, open one of its enrolments: Identity check is "Awaiting source", hollow, not red. Narrator: "A source outage never fails a student." Reset chaos, press "Recheck pending checks" on the institution: the check turns Countersigned. |
| 9:15 | AICTE_ADMIN | `/aicte/institutions/[abc]/score` | Integrity Index | "Why this score": penalties listed per component with counts and weights, rule sources cited. Audit "Verify chain" button returns "Chain intact, 1,842 entries". |
| 9:45 | AICTE_ADMIN | `/admin/psi` | PSI | Two sets, intersection size without revealing members. Close on the tagline. |

Hard rules for the demo: no map anywhere; no unmasked id anywhere; no status word other than the five flag statuses; `/admin/system` reset button is pressed before the panel enters.

## Flow 1. Login, per role

Steps
1. Visitor opens `/login`. State: six role cards (AICTE officer, Regional officer West, Registrar ABC College, Registrar XYZ Institute, Student, University) plus a collapsed "Sign in with email" form. Cards show email and a masked password with "Demo credentials" tag [login.demo_tag].
2. Click a card. State: form expands prefilled with that card's email and password; focus moves to "Sign in".
3. Submit. `POST /auth/login`. Button shows "Signing in" with spinner; form disabled.
4a. 200. Read `user.role`, `router.replace` to landing route: AICTE_ADMIN `/aicte`, RO_OFFICER `/ro`, INSTITUTION `/college`, STUDENT `/student`, UNIVERSITY `/university`.
4b. 401 `INVALID_CREDENTIALS`. Inline error under the form [err.INVALID_CREDENTIALS], password cleared, focus to password.
4c. 429 `RATE_LIMITED`. Banner [err.RATE_LIMITED]; "Sign in" disabled for 30 s with a countdown.
4d. 422 `VALIDATION_ERROR`. Field errors from `details.fields` under each field.
4e. Network error. Banner [err.NETWORK].
5. If a signed-in user opens `/login`, redirect to their landing route.

Session expiry: any 401 from the proxy during use shows a full-page notice "Your session has ended. Sign in again." [err.UNAUTHENTICATED] with a button to `/login?next=<path>`; after login, honour `next` only if it is a same-origin path.

Sign out: user menu > "Sign out" -> `POST /auth/logout` -> `/login`, toast "Signed out".

## Flow 2. Officer triage

Actor: AICTE_ADMIN or RO_OFFICER. Week 1 covers steps 1 to 3 (no flags yet, the institution list is still ranked by `enrolments` desc then `name`). Week 2 adds flags; Week 3 adds actions.

1. Land on `/aicte` or `/ro`. `GET /dashboard/summary`, `GET /institutions?sort=flags_open&order=desc` (W2; Week 1 uses `sort=enrolments`). State: KPI tiles, state grid, ranked table.
2. Pick the top institution. Link to `/aicte/institutions/[id]`. `GET /institutions/{id}`. State: header with name, permanent id, type, state, region, university; programme table; flags list (W2, `GET /flags?institution_id=` ).
3. Read a programme row: approved intake, admitted, seated, unseated, pools. Unseated > 0 is the visual cue (amber count, never red).
4. Open the flag. `/aicte/cases/[flagId]` (W2, `GET /flags/{id}`). State: evidence card first (summary, facts, rule source), then related enrolments table (masked), then case history, then the action bar.
5. Read the evidence. Each fact is label and value. Related enrolments show the five-segment strip and "n of m".
6. Choose an action (W3, `POST /flags/{id}/actions {action, note, attachments?}`):
   - Clear: note required. Confirmation sheet [case.clear_confirm]. Status -> Cleared. Toast "Flag cleared. ABC College can see your note."
   - Request documents: note required (what to send), optional due date. Status -> Documents requested. Toast "Request sent to the registrar."
   - Escalate: note required, assignee optional (RO -> AICTE). Status -> Escalated.
   - Confirm: note required, the sheet names the consequence [case.confirm_confirm]. Status -> Confirmed. Nothing is deleted or rejected; the enrolment keeps its status.
   - Add note: free text, no status change.
7. After any action, the history gains an entry: actor, action, note, time. Attachments listed by name and size.
8. "Back to queue" returns with the queue scrolled to the next open item.

Keyboard: `j`/`k` move through queue rows, `Enter` opens, `Esc` back. Actions have no single-key shortcuts (a mis-key must not confirm a case).

## Flow 3. College upload

Actor: INSTITUTION. All Week 2 except step 10 which is visible in Week 1 as the seeded state.

1. `/college/upload`. State: drop zone, "Choose file" button, template download link (CSV and XLSX), the column list, and the declaration checkbox [upload.declaration].
2. Drop a file. Client checks extension (`.csv`, `.xlsx`) and size (<= 20 MB). Errors inline [upload.err_type], [upload.err_size].
3. Tick the declaration. "Upload" enables.
4. Submit. `POST /uploads` multipart (`file`, `academic_year`, `declaration`; API_CONTRACT §A2.4). Response 202 `{batch}` with status QUEUED. Navigate to `/college/uploads/[batchId]`.
5. Batch page polls `GET /uploads/{id}` every 2 s. Status rail: Queued -> Validating -> Processing -> Done, or Failed, with the current stage under it ("Step 6 of 8: Checking with sources"). Progress bar from `progress_pct`. Counts: rows, accepted, with errors, with warnings.
6. Once Validating is over: the row problems table from `GET /uploads/{id}/errors`: row, level (Error: row not saved; Warning: row saved with a note), column, problem, value as uploaded (masked). Button "Download errors as CSV".
7. Registrar fixes the rows offline, returns to `/college/upload` and uploads them again, alone or in the whole file (a file changes only the rows in it; the server marks it an update). The previous batch stays listed with its counts.
8. Processing assigns seats and runs the five checks. Page shows "Checking against sources" with one line per source and its checks. If a source is unavailable, that line reads [upload.source_waiting] and the batch still reaches Done; those checks stay pending until a recheck or the next upload of those rows.
9. Done. Summary card: rows accepted, seats assigned, unseated, flags opened, then new, updated, withdrawn and transferred counts, and [upload.done_note]. Links to the seat ledger, enrolments and flags.
10. `/college` seat ledger. The CSE row now reads approved 120, admitted 132, seated 120, unseated 12, the same day. The row has a muted amber "12 unseated" chip with a tooltip "Enrolments beyond approved intake. An officer will review the flag." No red, no "excess" word in the chip; the flag row below uses the full evidence sentence.
11. `/college/flags` lists the new flags with evidence summaries and status Open.

Error cases: 413 [err.FILE_TOO_LARGE] or [err.TOO_MANY_ROWS]; 415 [err.UNSUPPORTED_FILE_TYPE]; 422 [err.UPLOAD_HEADER_INVALID], [err.UPLOAD_EMPTY], or `VALIDATION_ERROR` on the declaration or the academic year; 409 [err.UPLOAD_IN_PROGRESS]; an unavailable source never fails the batch.

## Flow 4. Student notice

Actor: STUDENT, starting from email (Mailpit in demo) or DigiLocker inbox (mockgov). Week 3.

1. System sends the notice after an enrolment passes Identity (or immediately when there is no APAAR, by email). Message [notice.email_body]. Link `/student/notices/[token]`.
2. Student opens the link (no login needed; the token is the auth). `GET /notices/{token}` (W3). State: the claim card: institution, programme, academic year, year of study, masked APAAR or provisional id, the date the college uploaded it.
3. Two buttons [notice.yes], [notice.no], the next-step line [notice.next_step], and a "What is this?" expander [notice.what_is_this].
4a. Yes. `POST /notices/{token}/respond {response: "YES"}`. State: confirmation [notice.yes_done]. Student check -> PASS. Optional "See what is held about you" link to `/student` (requires login).
4b. No. Confirmation sheet [notice.no_confirm] with one optional free-text "Anything we should know?" then submit `{response: "NO", comment?}`. State: [notice.no_done]. Student check -> FAIL. Flag `STUDENT_DENIED` High opens for the institution. The enrolment is NOT changed.
4c. Expired token: [notice.expired] with "Ask your college to resend" and no form.
4d. Already answered: shows the earlier answer and time, with "Change my answer" allowed once within 7 days.
5. No reply: nothing happens. The officer view shows "No reply yet" in grey. After `expires_at` it reads "No reply (expired)" still grey.
6. The student's `/student/notices` lists every notice with reply and time.

## Flow 5. Credential share

Actor: STUDENT, then a VERIFIER. Week 3.

1. `/student/wallet`. `GET /credentials` (W3). State: one card per credential: kind (Enrolment proof, Degree), issuer, issued date, status (Active, Revoked).
2. "Share proof" on a card. Sheet lists the disclosable fields as checkboxes: name, institution, programme, academic year, year of study, date of birth, masked APAAR. Institution and programme are ticked and locked (a proof without them means nothing); the rest are unticked by default.
3. Consent text [consent.credential_share] with "I agree" checkbox. "Create QR" enables.
4. `POST /credentials/{id}/present {fields: [...]}` (W3). State: QR, a 6-group code under it, "Shares 3 of 7 fields", "Valid for 10 minutes", "Copy link".
5. Verifier scans. Lands on `/verify/[code]`. `GET /verify/{code}` (W3, public, rate limited).
6a. Valid: [verify.valid] heading, issuer, issue date, the shared fields only, "Revocation checked just now". Nothing else is on the page.
6b. Revoked: [verify.revoked]. 6c. Expired presentation: [verify.expired]. 6d. Malformed: [verify.invalid].
7. The student's wallet shows "Shared with a verifier at 10:42" in its history.

## Flow 6. University degree print

Actor: UNIVERSITY. Week 3.

1. `/university/degrees`. `GET /university/graduates?q=` (W3). Table: name, institution, programme, year, masked APAAR, credential status.
2. Pick a row. "Print degree insert". `/university/degrees/[enrolmentId]/print`.
3. Print view (A4 portrait, no nav): university name, student name, programme, institution, year, "APAAR XXXX XXXX 4417" (or provisional id), QR for the DEGREE credential, "Scan to verify at countersign.../verify".
4. `window.print()` on "Print". Browser dialog. The page has `@media print` styles; no colour backgrounds.
5. If the DEGREE credential does not exist yet: "Issue degree proof" button first (`POST /university/degrees/{enrolmentId}/issue`), with consent note that the student can revoke sharing from their wallet.

## Flow 7. Demo reset

Actor: AICTE_ADMIN on `/admin/system`. CLI equivalent `make demo-reset`.

1. Section "Demo controls" (labelled Demo). Buttons: "Reset chaos" (`POST mockgov /admin/chaos/reset`), "Reset demo data" (proposed `POST /admin/demo/reset`, see gaps), "Re-seed" (same endpoint).
2. "Reset demo data" opens a sheet: "This drops and re-seeds the demo database. Takes about 30 seconds." Buttons "Reset" and "Cancel".
3. During reset the page shows a progress line and disables all other controls.
4. After reset: toast "Demo data reset. Audit chain starts fresh." and the adapter ping re-runs.
5. Reset never signs anyone out; the seeded users and passwords are unchanged.

## Flow 8. Role mismatch and out-of-scope

1. Registrar opens `/aicte`. Layout `getMe()` sees role INSTITUTION, redirects to `/college`, toast [err.FORBIDDEN_redirect].
2. RO West opens `/ro/institutions/[southId]`. API 404. Page shows [err.NOT_FOUND_institution] with a "Back to overview" link. The page never says the institution exists elsewhere.
3. Student opens any officer route: redirect to `/student`.
