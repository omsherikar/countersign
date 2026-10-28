# Copy deck

Every user-facing string, keyed by id. Words follow the frozen scope (the SIH deck): a college upload is a claim, each fact carries an evidence state and its source, and a record carries one status. Placeholders are `{snake_case}` and map to API fields. Indian-English spelling throughout. No exclamation marks. Hindi strings are marked "for review" and must be checked by a native speaker before the panel.

Suggested implementation: `apps/web/lib/copy.ts` exporting a flat object keyed by these ids, so the review checklist can grep for them.

Counts: when a number is 1, use the singular noun ("1 flag opened", "1 row"). Sentences the api writes (flag `summary`, evidence facts, check `detail.summary`, row problem `message`, a failed batch's `error`) are printed verbatim; the deck mirrors them for review and the browser never rebuilds them.

## Changes 2026-10-29: evidence states, record statuses and the record card

Reconciled with the frozen scope (the SIH deck) and DECISIONS D34 to D49, R1 to R6. API_CONTRACT Addendum 4 is being written alongside; every field, endpoint and error code below that the contract does not name yet is marked "pending contract confirmation". Update `apps/web/lib/copy.ts`, `copy-student.ts`, `copy-cases.ts` and every caller.

Words, everywhere a person reads them:
- A college upload is a claim. Each record has five rows, in the deck's order Identity, Seat, Joining record, Credits, Student, each with one evidence state (Confirmed, Contradicted, Pending, Not yet due, Not applicable, Source unavailable) and a source and date. Each record has one status: Awaiting evidence, Countersigned, Under review or Disputed (§21).
- Rows say Confirmed; only a record says Countersigned. No score, no "n of 5", no percentage per record.
- "Case" replaces "flag", "attestation" replaces "proof" and "credential", "dispute" names a student's "I never joined". Wire names (`flags`, `credentials`, `STUDENT_DENIED`) and id prefixes (`flag.*`, `flags.*`, `wallet.*`) stay.
- Countersign does not issue degrees: the university page is certificate integration (§11), and the degree proof is a completion attestation.
- A student answers only after signing in with DigiLocker; email only points there (§23).
- Signals are for officers only and never set a status (§27).

Renamed ids

| old id | new id |
|---|---|
| wallet.kind.DEGREE | wallet.kind.COMPLETION |
| wallet.issued_by_degree | wallet.issued_by_completion |
| wallet.not_issued.reply | wallet.not_issued.AWAITING_EVIDENCE |
| wallet.not_issued.checks | wallet.not_issued.UNDER_REVIEW |
| wallet.not_issued.denied | wallet.not_issued.DISPUTED |
| wallet.revoked_reason.FLAG_CONFIRMED | wallet.revoked_reason.CLAIM_WITHDRAWN |
| verify.kind.DEGREE | verify.kind.COMPLETION |
| verify.code_hint_degree | verify.code_hint_certificate |
| verify.degree_valid, verify.degree_sub, verify.degree_heading, verify.degree_printed, verify.degree_wallet, verify.degree_revoked_sub | verify.completion_valid, verify.completion_sub, verify.completion_heading, verify.completion_printed, verify.completion_wallet, verify.completion_revoked_sub |
| verify.field.proof_id | verify.field.attestation_id |
| nav.degree_print | nav.certificates |
| degree.heading, degree.lead, degree.search, degree.count | cert.heading, cert.lead, cert.search, cert.count |
| degree.col.student, degree.col.year_of_award, degree.col.proof | cert.col.graduate, cert.col.year, cert.col.attestation |
| degree.status.none, degree.status.active, degree.status.revoked | cert.status.none, cert.status.active, cert.status.revoked |
| degree.issue, degree.issue_heading, degree.issue_body, degree.issue_note, degree.issue_revocation_note, degree.issue_confirm, degree.issue_cancel, degree.issuing, degree.issued_toast | cert.issue, cert.issue_heading, cert.issue_body, cert.issue_note, cert.issue_revocation_note, cert.issue_confirm, cert.issue_cancel, cert.issuing, cert.issued_toast |
| degree.print_insert, degree.pdf, degree.pdf_note, degree.provisional_note | cert.print_block, cert.pdf, cert.pdf_note, cert.provisional_note |
| degree.print_title, degree.print_hint, degree.print, degree.print_back | cert.print_title, cert.print_hint, cert.print, cert.print_back |
| degree.print.accompanies, degree.print.name, degree.print.programme, degree.print.institution, degree.print.year, degree.print.apaar, degree.print.provisional | cert.print.lead, cert.print.name, cert.print.programme, cert.print.institution, cert.print.year, cert.print.apaar, cert.print.provisional |
| degree.apaar_line, degree.scan_line, degree.print.proof_id, degree.qr_alt, degree.print.issued, degree.print.signed | cert.apaar_line, cert.scan_line, cert.print.attestation_id, cert.qr_alt, cert.print.issued, cert.print.signed |
| check.detail.IDENTITY.pass, .fail_not_found, .fail_malformed, .fail_name, .fail_dob, .pending_review, .na_no_apaar | check.detail.IDENTITY.confirmed, .contradicted_not_found, .contradicted_malformed, .contradicted_name, .contradicted_dob, .pending_review, .na_no_apaar |
| check.detail.IDENTITY.na_international | check.detail.IDENTITY.confirmed_sii |
| check.detail.SEAT.pass, check.detail.SEAT.fail | check.detail.SEAT.confirmed, check.detail.SEAT.contradicted_no_seat |
| check.detail.ADMISSION.fail_no_pool | check.detail.SEAT.contradicted_no_pool |
| check.detail.ADMISSION.pass_sii, check.detail.ADMISSION.fail_sii | check.detail.ADMISSION.confirmed_sii, check.detail.ADMISSION.contradicted_sii |
| check.detail.STUDYING.pass, .fail, .pending_one_missing, .na_first_year, .na_no_apaar, .na_abc_unknown | check.detail.STUDYING.confirmed, .contradicted, .pending, .not_yet_due, .na_no_apaar, .na_abc_unknown |
| check.detail.STUDENT.pass, .fail, .pending, .pending_sent, .pending_expired | check.detail.STUDENT.confirmed, .contradicted, .pending_not_sent, .pending_sent, .pending_expired |
| enrolment.proofs.* (web-only, copy-cases.ts) | enrolment.attestations.* (§22) |
| enrolment.section.proofs (web-only) | enrolment.section.attestations |
| recheck.still_pending | recheck.no_change |
| flag_status.CLEARED, flag_status.CONFIRMED | flag_status.UPHELD, flag_status.WITHDRAWN (wire renames in migration 0004) |
| case.history.CLEAR, case.history.CONFIRM | case.history.UPHOLD, case.history.WITHDRAW |

Retired ids
- The per-record score and the countersign strip: `strip.not_checked`, `strip.score`, `strip.score_pending`, `strip.aria`, `strip.segment_tip`, `strip.segment_tip_full`, `student.strip_caption`, `enrolment.score_label`, `col.countersign`. The "n of 5" words go with them: no screen prints "{passes} of {applicable}", "n pending" or "sources agree".
- The check-level score words: `check.status.PASS` (Countersigned), `check.status.FAIL` (Not countersigned), `check.status.PENDING`, `check.status.NA` (n/a), `check.pending.student`, `check.pending.student_not_sent`, `check.pending.student_expired`, `check.pending.unavailable`, `check.pending.review`, `check.pending.results`, `check.na_reason.IDENTITY`, `check.na_reason.STUDYING`. They give way to `evidence.state.*` and the findings of §15.
- The Integrity Index (dropped from the scope): `score.heading`, `score.value`, `score.rank`, `score.start`, `score.raise`, `index.label`, `index.why`, `nav.score`, `col.integrity`.
- `kpi.clear`, `kpi.clear_value`, `kpi.clear_tip` (the status tiles replace "No source disagrees").
- Clear and Confirm: `case.clear`, `case.confirm`, `case.clear_confirm`, `case.confirm_confirm`, `case.confirm_revokes`, `case.cleared_toast`, `case.confirmed_toast`.
- The counselling-list sentences: `check.detail.ADMISSION.pass_counselling`, `.pass_ref_differs`, `.fail_counselling`, `.pass_route`, `.fail_no_seat` (the Joining record row checks the admission authority's joining record; route and pool checks belong to the Seat row).
- `col.result` and `col.checked_at` on enrolment detail (the record card's columns are `record.col.*`).

Same id, new text: `brand.tagline` (the deck's tagline), `nav.ledger`, `nav.flags`, `nav.wallet`, `login.card.student`, `kpi.flags_open`, `kpi.flags_open_tip`, `kpi.countersigned_value`, `kpi.countersigned_tip`, `section.flags`, `table.sort_tip`, `table.count.flags`, `col.flags_open`, `col.flags`, `tab.flags`, `check.ADMISSION` (Joining record), `check.STUDYING` (Credits), `source.COUNSELLING`, `source.SEAT_LEDGER`, `source.STUDENT_NOTICE`, `source.will_retry`, `upload_stage.FLAGS`, `consent_purpose.CREDENTIAL_SHARE`, `notice_reply.YES`, `notice_reply.NO`, `flag.STUDENT_DENIED.name` (Student dispute), `flag.STUDENT_DENIED.summary`, `flag.STUDENT_DENIED.summary_changed`, `flag.STUDENT_DENIED.rule`, `flag.GHOST_RING.rule`, `flag.ANOMALY.rule`, every §6 row that said flag, `email.docs_request.body`, `upload.source_waiting`, `upload.done_summary`, `upload.done_note`, `upload.view_flags`, the notice rows in §8 and §23 with their `.hi` rows, `notices.reply_hint`, `notices.denied_line`, `student.check_student_*`, the wallet rows that said proof, `consent.apaar_link`, `consent.notice` and `consent.notice.hi`, `consent.credential_share`, `consent.withdraw.CREDENTIAL_SHARE` (the three stored texts become text version 2), the verifier rows that said proof or degree, `admin.reset_confirm`, `admin.requests.erasure_retention`, `admin.requests.erasure_reply`, `err.SOURCE_UNAVAILABLE`, `err.NOT_FOUND_enrolment`, `err.NOT_FOUND_flag`, `err.CREDENTIAL_NOT_ELIGIBLE`, `err.CREDENTIAL_REVOKED`, `err.PRESENTATION_NOT_FOUND`, `err.FLAG_TRANSITION_INVALID`, the empty states that said flag or proof, `enrolment.section.checks` (Evidence), `enrolment.section.flags`, `enrolment.intake_value`, `enrolment.seat_value`, `enrolment.unseated_flag`, every §17 row, the §18 and §19 rows that said flag, `privacy.consent_via.CREDENTIAL_SHARE`, `privacy.access.verifier`, and `privacy_notice.*` (notice version v2).

New ids, by prefix: `evidence.*`, `check.label_tip.*`, `check.*.hi`, `record_status.*`, `status_reason.*`, `next_step.*` (§21); `record.*`, `history.*`, `enrolment.section.attestations`, `enrolment.attestations.*` (§22); `login.digilocker*`, `signin.*`, `dldemo.*`, `claim.*`, the new `notice.*` rows and their `.hi` rows, `student.decision.*` (§23); `completeness.*`, `deadline.*`, `missing.*` (§24); `approval.*`, `eligibility.*` (§25); `mapping.*` (§26); `signal.*` (§27); `report.*` (§28); `eval.*` (§29); `case.uphold*`, `case.correct*`, `case.withdraw*`, `case.decide_heading`, `case.reason_*`, `case.changes_heading`, `case.who_sees*`, `case.docs_kind_label`, `case.request_docs_change*`, `case.escalate_change`, `case.from_signal`, `case.history.UPHOLD`, `case.history.CORRECT`, `case.history.WITHDRAW`, `case.history.reason`, `case.history.correction_line`, `case.history.withdrawn_line`, `case.history.opened_from_signal`, `case.system_note.missing_updated`, `docs_kind.*`, `reason.*`, `college.request_kind_line`, `college.decision_line` (§6); `flag_status.UPHELD`, `flag_status.CORRECTED`, `flag_status.WITHDRAWN`, `enrol_status.withdrawn_by_decision` (§4); `flag.NOT_IN_JOINING_RECORD.*`, `flag.ELIGIBILITY_BREACH.*`, `flag.MISSING_FROM_UPLOAD.*` (§5); `field.tfw_income_certified`, `field.nri_sponsored`, `field.ciwg` and their `rowerr.BAD_ENUM.*` rows (§7); `wallet.kind.COMPLETION`, `wallet.revoked_reason.STUDENT_DISPUTE` (§8); `cert.*`, `nav.certificates` (§11); `source_line.*`, `check.finding.*` (§15); `recheck.no_change`, `recheck.status_line` (§17); `col.record_status`, `enrolments.filter.status`, `nav.signals`, `nav.evaluation`, `nav.completeness` (§1, §3, §18); and the error codes below.

Error codes the contract will add (all pending contract confirmation): `err.SIGNIN_REQUIRED`, `err.DIGILOCKER_CANCELLED`, `err.DIGILOCKER_FAILED`, `err.DIGILOCKER_STATE_INVALID`, `err.NOTICE_IDENTITY_MISMATCH`, `err.CLAIM_NO_MATCH`, `err.CLAIM_ALREADY_CLAIMED`, `err.CLAIM_NOT_NEEDED`, `err.REASON_REQUIRED`, `err.CORRECTION_EMPTY`, `err.CORRECTION_INVALID`, `err.WITHDRAW_NONE_SELECTED`, `err.WITHDRAW_NOT_NAMED`, `err.UPHOLD_NEEDS_VERSION`, `err.APPROVAL_BELOW_ASSIGNED`, `err.MAPPING_INCOMPLETE`, `err.MAPPING_DUPLICATE`, `err.SIGNAL_ALREADY_HANDLED`, `err.NOT_FOUND_signal`, `err.REPORT_FAILED` (§13).

Fields the deck reads that the contract must carry (pending contract confirmation): on each row, `finding` and `source_line` as sentences the api writes (§15), besides `supplied_by`, `observed_at`, `independent` and `resolved`; on each record, `record_status`, `status_reason`, `next_step`, `record_status_at`, the approval `version` its seat cites, and `versions[]` for History; on the notice page, the signed-in DigiLocker name and one of `MATCH`, `SOMEONE_ELSE`, `CLAIM_NEEDED`; on a case action, `docs_kind` and `approval_version`, plus a `dry_run` preview of a decision's consequences; on a revoked attestation, the reason codes `CLAIM_WITHDRAWN` and `STUDENT_DISPUTE`; on each college, `completeness_pct`, `joined`, `missing` and `deadline_state`.

## Changes 2026-10-29: strings the pages print

Reconciled with the pages as built and API_CONTRACT "Addendum 3 errata". New ids, with the text the web already prints: `case.note_label_internal`, `case.due_date_past`, `case.due_date_far`, `case.sending`, `case.assignee_line`, `college.respond_progress` (§6); `verify.code_hint_degree`, `verify.method_lookup` (§10); `degree.qr_alt` (§11); `admin.requests.count_any`, `admin.requests.resolve_for` (§12); `enrolment.notice.consent_off_undated` (§16); `privacy.consent_state_none`, `privacy.access.SYSTEM`, `privacy.request.cancel`, and the privacy notice sections `privacy_notice.*` (§20, mirrored from the api). Same id, new text: `verify.field.countersigned` (Countersigned by, the label the api sends and the verifier prints). §6: Assign no longer shows on Cleared and Confirmed flags, and the action bar shows exactly the flag's `allowed_actions`; `{role_word}` in the documents email is defined. Update `verify.field.countersigned` in `apps/web/lib/copy-student.ts`.

## Changes 2026-10-28: notices, cases, proofs and privacy

Reconciled with DECISIONS D23 to D33 (student notices, the Student check, case actions, student-held proofs, the verifier, the degree QR, the audit page, consent and data requests, error codes). Update `apps/web/lib/copy.ts` and every caller.

Renamed ids

| old id | new id |
|---|---|
| case.history.response | case.history.COLLEGE_RESPONSE |
| consent.withdraw | consent.withdraw.NOTICE, consent.withdraw.CREDENTIAL_SHARE and consent.unlink_apaar |

Retired ids: `verify.coming` (the verifier is live), `university.degree_teaser` (Degree print is live), `flag.readonly_officer` (officers act from flag detail).

Same id, new placeholders

| id | change |
|---|---|
| verify.revoked_sub | `{revoked_date}` removed; the verifier result carries no revocation date |

Same id, new text: `check.pending.student` (No reply yet; "Notice not sent yet" moves to `check.pending.student_not_sent`), `kpi.countersigned_tip`, `student.check_student_pending`, `notice.expired`, `notice.expired.hi`, `notice.invalid`, `wallet.kind.DEGREE` (Degree proof), `consent.apaar_link`, `consent.notice`, `consent.credential_share`, `verify.lead`, `verify.placeholder` (6 groups of 4), `verify.what`, `verify.revocation` (Revocation checked just now), `verify.expired_sub`, `verify.invalid`, `verify.invalid_sub`, `degree.issue_note`, `college.respond_files` (up to 3 files, 5 MB each, PDF, PNG or JPEG), `flag.readonly_college`, `flag.STUDENT_DENIED.summary` (now raised, High; its facts gain Channel, Reply changed and the officers-only comment), `audit.col.seq` (Entry), `empty.notices_student`, `empty.credentials_student`, `empty.graduates`.

New ids, by prefix: `check.pending.student_not_sent`, `check.pending.student_expired`, `check.detail.STUDENT.*` (§15); `notice_channel.*`, `notice_delivery.*`, `consent_purpose.*`, `consent_state.*`, `data_request_kind.*`, `data_request_status.*`, `audit_action.*` (§4); `flag.STUDENT_DENIED.summary_changed`; the new `notice.*` rows and their `.hi` rows, `provisional.label.hi`, `consent.notice.hi`, `err.NETWORK.hi`, `err.INTERNAL.hi`, `err.retry.hi`; `notices.*`; `student.check_student_sent`, `student.check_student_expired`, `student.check_student_denied`, `student.consent_change`; the new `wallet.*` rows; `verify.*` for the entry page, the result states, the degree QR and the field labels; `degree.*` for the graduates table, the issue sheet and the print view; `case.*` for Reopen, Assign, the status lines and the history rows (`case.history.*`, `case.system_note.*`); the new `college.respond_*` rows; `email.docs_request.*`; `enrolment.section.notice`, `enrolment.notice.*`, `resend.*`; `flags.filter.assignee*`, `flags.filter.response*`; `audit.*` for filters and chain results; `admin.requests.*`; `privacy.*` (§20); `nav.data_requests`; `empty.graduates_search`, `empty.audit_filtered`; `err.NOTICE_NOT_FOUND`, `err.NOTICE_EXPIRED`, `err.NOTICE_ALREADY_CHANGED`, `err.FLAG_TRANSITION_INVALID`, `err.ATTACHMENT_TOO_LARGE`, `err.ATTACHMENT_TYPE`, `err.CREDENTIAL_NOT_ELIGIBLE`, `err.CREDENTIAL_REVOKED`, `err.PRESENTATION_NOT_FOUND`, `err.RESEND_LIMIT`, `err.NOTICE_LIVE`.

Strings the web kept outside the deck and now has ids for: `app.student.consent_change` becomes `student.consent_change`; `app.verify.what_is` becomes `verify.about`; `app.verify.bar` becomes `verify.bar`.

Fields the deck reads that the contract must carry: `detail.notice_state` (`NOT_SENT`, `SENT`, `EXPIRED`) on the Student check, `revoked_reason` codes on a proof (`ENROLMENT_WITHDRAWN`, `ENROLMENT_TRANSFERRED`, `FLAG_CONFIRMED`, else the admin's text), and the student's own data requests with their replies.

## Changes 2026-10-28

Reconciled with API_CONTRACT Addendum 2, ENGINES.md and DECISIONS D14 to D22. Update `apps/web/lib/copy.ts` and every caller.

Renamed ids

| old id | new id |
|---|---|
| rowerr.ROUTE_INVALID | rowerr.BAD_ENUM.admission_route |
| rowerr.CONSENT_INVALID | rowerr.BAD_ENUM.consent_status |
| rowerr.YEAR_INVALID | rowerr.YEAR_OF_STUDY_INVALID |
| upload_status.CHECKING | upload_status.PROCESSING |

Retired ids: `check.na_reason.ADMISSION` (the Admission check is never n/a; management, spot and NRI admissions are checked against the seat ledger).

Same id, new placeholders

| id | change |
|---|---|
| flag.EXCESS_ADMISSION.summary | `{academic_year}` becomes `{cohort_year}`; ends "; {unseated} without a seat." |
| flag.QUOTA_BREACH.summary | `{assigned}` becomes `{admitted}`, `{seat_type}` becomes `{seat_type_word}`, `{academic_year}` becomes `{cohort_year}` |
| flag.NO_ACADEMIC_ACTIVITY.summary | `{semesters}` becomes `{missing}` |
| flag.EXCESS_ADMISSION.rule, flag.QUOTA_BREACH.rule | the pool's `{rule_source}` |
| rowerr.MISSING_REQUIRED | `{field}` becomes `{field_word}` |
| err.SOURCE_UNAVAILABLE | `{source}` becomes `{source_name}` |
| upload.source_waiting | `{source}` becomes `{source_name}`; adds `{n}` |
| upload.rows | `{total}`, `{ok}`, `{error}` become `{rows}`, `{accepted}`, `{errors}`, `{warnings}` |
| upload.failed | `{reason}` removed; the batch `error` sentence follows it verbatim |

Same id, new text: `check.status.PENDING` (Pending), `check.na_reason.STUDYING`, `strip.score_pending` (pending, Student left out of the count), `source.will_retry`, `kpi.enrolments` (Students on roll), `col.enrolments` (On roll), `col.admitted_tip`, `flag.INVALID_APAAR.name` (APAAR not verified), `flag.NAME_MISMATCH.name` (Name or date of birth mismatch), `flag.DUPLICATE_WITHIN_UPLOAD.name` (Duplicate within institution), `flag.LATE_REFILL.rule`, `upload.kind.INITIAL` and `upload.kind.UPDATE` (display words; the server sets the kind), `upload.max`, `upload.declaration`, `upload.errors_heading`, `upload.errors_none`, `upload.errors_next`, `upload.done_note`, `college.no_upload_yet`.

New ids: `kpi.admitted`, `kpi.flags_open_tip`, `kpi.countersigned_tip`, `kpi.clear`, `kpi.clear_value`, `kpi.clear_tip`, `app.hint.intake`, `app.hint.all_years`, `app.all_years_line`, `col.enrolments_tip`, `col.mode`, `mode.*`, `gender.*`, `strip.segment_tip`, `strip.segment_tip_full`, `check.pending.*`, `check.na_reason.IDENTITY`, `check.attempts`, `check.never`, `check.detail.*` (§15, reference), `upload_stage.*`, `upload_source.*`, the new `upload.*`, `field.*` and `rowerr.*` rows (§7), `last_upload.line`, `col.file`, `col.uploaded_by`, `col.kind`, `col.upload_source`, `col.rows`, `col.accepted`, `col.with_errors`, `col.with_warnings`, `col.row`, `col.row_level`, `col.column`, `col.problem`, `col.value`, the flag summary variants in §5, `err.FILE_TOO_LARGE`, `err.TOO_MANY_ROWS`, `err.UNSUPPORTED_FILE_TYPE`, `err.UPLOAD_HEADER_INVALID`, `err.UPLOAD_HEADER_DUPLICATE`, `err.UPLOAD_EMPTY`, `err.UPLOAD_IN_PROGRESS`, `err.NOT_FOUND_upload`, `err.NOT_FOUND_enrolment`, `err.NOT_FOUND_flag`, `empty.cases_filtered`, `empty.clear_filters`, `enrolments.filter.*`, `table.count.flags_one_any`, `tab.flags_count`, `flags.more`, `empty.flags_by_type`, `empty.flags_enrolment`, `empty.related`, `empty.checks`, `empty.enrolments_filtered`, `student.check_student_pending`, and every id in §16 to §19 (`enrolment.*`, `recheck.*`, `flags.*`, `flag.*`, `flags_by_type.*`, `section.flags_by_type`, `table.count.flags_any`, `table.count.flags_one` and their `col.*`).

## 1. Brand and shell

| id | text |
|---|---|
| brand.name | Countersign |
| brand.tagline | Every enrolment is a claim. We show the evidence behind it. |
| shell.signout | Sign out |
| shell.role.AICTE_ADMIN | AICTE officer |
| shell.role.RO_OFFICER | Regional officer, {region_name} |
| shell.role.INSTITUTION | Registrar |
| shell.role.STUDENT | Student |
| shell.role.UNIVERSITY | University controller |
| shell.coming | Coming in Week {n} |
| shell.loading_slow | Still loading |
| search.placeholder | Search institutions by name or permanent id |
| search.empty | No institution matches "{q}". Try the permanent id, e.g. 1-ABC-0001. |
| nav.overview | Overview |
| nav.cases | Cases |
| nav.reports | Reports |
| nav.system | System |
| nav.audit | Audit |
| nav.psi | Private matching |
| nav.ledger | Seat Ledger |
| nav.upload | Upload |
| nav.enrolments | Enrolments |
| nav.flags | Cases |
| nav.my_enrolment | My enrolment |
| nav.notices | Notices |
| nav.wallet | My attestations |
| nav.privacy | Privacy |
| nav.affiliated | Affiliated institutions |
| nav.certificates | Certificate integration |
| nav.data_requests | Data requests |
| nav.signals | Signals |
| nav.completeness | Completeness |
| nav.evaluation | Evaluation |

## 2. Login

| id | text |
|---|---|
| login.heading | Sign in |
| login.sub | Pick a demo role or use your email. |
| login.demo_tag | Demo credentials |
| login.email | Email |
| login.password | Password |
| login.show | Show |
| login.hide | Hide |
| login.submit | Sign in |
| login.submitting | Signing in |
| login.demo_footer | Shared demo passwords. Synthetic data only, never real students. |
| login.card.admin | AICTE officer / National |
| login.card.ro_west | Regional officer / Western (Mumbai) |
| login.card.abc | Registrar / ABC College of Engineering |
| login.card.xyz | Registrar / XYZ Institute of Technology |
| login.card.student | Student / Sign in with DigiLocker |
| login.card.university | University controller / Maharashtra State Technical University |
| login.signed_out | Signed out |

## 3. Officer pages

| id | text |
|---|---|
| aicte.heading | Overview |
| ro.heading | {region_name} region overview |
| ro.office_line | Regional office: {hq_city} |
| kpi.institutions | Institutions |
| kpi.programmes | Programmes |
| kpi.approved_seats | Approved seats |
| kpi.admitted | Admitted |
| kpi.enrolments | Students on roll |
| kpi.flags_open | Open cases |
| kpi.flags_open_tip | Cases that are open, waiting for documents or escalated, for {academic_year}. |
| kpi.countersigned | Countersigned |
| kpi.countersigned_value | {pct}% of active records |
| kpi.countersigned_tip | Share of active records whose evidence is complete for their admission route and stage, with nothing unresolved. Records still awaiting evidence are not counted against the college. |
| kpi.not_computed | Not yet computed |
| kpi.status_heading | Records by status |
| kpi.status_value | {n} records · {pct}% |
| kpi.status_tip | Active records for {academic_year}, each counted once under its one status. |
| kpi.completeness | Completeness |
| kpi.completeness_value | {pct}% of joined students uploaded |
| kpi.signals_new | New signals |
| app.hint.intake | {academic_year} intake |
| app.hint.all_years | All years of study |
| app.all_years_line | {n} students on roll across all years of study |
| section.institutions_ranked | Institutions ranked |
| section.by_state | By state |
| section.by_region | By region |
| section.sources | Sources |
| section.programmes | Programmes |
| section.flags | Cases |
| section.evidence | Evidence |
| section.related | Related enrolments |
| section.history | History |
| section.actions | Actions |
| table.sort_tip | Ranked by open cases, then enrolments |
| table.count.institutions | {total} institutions |
| table.count.enrolments | {total} enrolments |
| table.count.seats | {total} seats |
| table.count.flags | {total} open cases in {institutions} institutions |
| col.name | Name |
| col.permanent_id | Permanent id |
| col.state | State |
| col.region | Region |
| col.type | Type |
| col.programmes | Programmes |
| col.approved_seats | Approved seats |
| col.enrolments | On roll |
| col.enrolments_tip | Every active student on the {academic_year} roll, all years of study. Not comparable with approved seats, which are one year's intake. |
| col.flags_open | Open cases |
| col.code | Code |
| col.programme | Programme |
| col.level | Level |
| col.shift | Shift |
| col.mode | Mode |
| col.approved | Approved |
| col.approved_tip | Approved intake for {academic_year} |
| col.admitted | Admitted |
| col.admitted_tip | Active students admitted against the {academic_year} intake, every admission route. Lateral entrants count with the batch they join. |
| col.seated | Seated |
| col.unseated | Unseated |
| col.student | Student |
| col.apaar | APAAR / Provisional |
| col.consent | Consent |
| col.year | Year |
| col.route | Route |
| col.category | Category |
| col.seat | Seat |
| col.record_status | Status |
| col.flags | Cases |
| col.uploaded | Uploaded |
| col.seat_code | Seat code |
| col.seat_type | Type |
| col.reserved_for | Reserved for |
| col.status | Status |
| col.holder | Holder |
| col.assigned | Assigned |
| tab.programmes | Programmes |
| tab.enrolments | Enrolments |
| tab.seats | Seats |
| tab.flags | Cases |
| tab.completeness | Completeness |
| tab.approvals | Approval versions |
| pools.show | Show seat pools |
| pools.hide | Hide seat pools |
| pools.line | {type} {assigned} of {capacity} |
| pools.supernumerary | (supernumerary) |
| pools.ciwg | ({n} reserved for CIWG) |
| ledger.pools_source | Pool sizes follow AICTE APH 2024-27. |
| ledger.pools_help_link | What are pools? |
| ledger.pools_help | Approved intake is split into seat pools. Regular seats include a 5% NRI carve-out. TFW (5%), lateral entry (10%) and international (15% or 25% by programme) are supernumerary: extra seats on top of the intake. Every seat is a row in the ledger, so an enrolment beyond the pool shows as unseated the day it is uploaded. |
| ledger.unseated_chip | {n} unseated |
| ledger.unseated_tip | Enrolments beyond the approved intake or not yet given a seat. An officer reviews these; nothing is rejected automatically. |
| seat.unseated | Unseated |
| privacy.read_logged | Viewing student records is logged. |
| check.IDENTITY | Identity |
| check.SEAT | Seat |
| check.ADMISSION | Joining record |
| check.STUDYING | Credits |
| check.STUDENT | Student |
| check.attempts | The source did not respond on {n} attempts. |
| check.never | Not checked yet |
| source.APAAR | APAAR registry |
| source.COUNSELLING | State admission authority |
| source.SEAT_LEDGER | Seat Ledger |
| source.ABC | ABC credits |
| source.STUDENT_NOTICE | Student sign-in via DigiLocker |
| source.DIGILOCKER | DigiLocker |
| source.SII | Study in India |
| source.status.OK | OK |
| source.status.UNAVAILABLE | Unavailable |
| source.status.DISABLED | Disabled |
| source.disabled_detail | Real adapter disabled |
| source.checked | Checked {relative} |
| source.failed | Sources: could not check |
| source.will_retry | Rows that depend on it show Source unavailable, never Contradicted |

Seats against admissions (API_CONTRACT §A2.18). Approved seats are one year's intake. Wherever they appear, `admitted` for the same year ([kpi.admitted], [col.admitted], hinted [app.hint.intake]) appears directly after them, and no ratio, bar, "against" sentence or difference uses any other figure. `enrolments` is every student on roll in every year of study: it is labelled [kpi.enrolments] or [col.enrolments], always carries [app.hint.all_years] or [col.enrolments_tip], comes after Admitted (never between Approved seats and Admitted), and is never divided by, subtracted from or set against approved seats. No screen shows a fill percentage; seats are compared as counts (Approved, Admitted, Seated, Unseated). On `/college`, where the tiles are about one intake, the roll appears only as the line [app.all_years_line].

Percentages. `countersigned_pct` (the Countersigned share of active records) and `completeness_pct` arrive rounded to one decimal; print them as sent, dropping a trailing ".0" (0.0 prints "0%", 91.4 prints "91.4%"). Null prints [kpi.not_computed]. They are shares of a population, never a score of one record. The status tiles (`kpi.status_heading`) show the four statuses in the legend's order, each with its count and share (`kpi.status_value`), with the status word and icon; they replace "No source disagrees".

Evidence words. A row prints its `evidence.state.*` word with its icon, then its finding after a colon when the api sends one (§15, §21). Rows say Confirmed; only a record says Countersigned. Lists that carry no row detail print the state word alone. The source names above (`source.*`) label the Sources panel and the upload's source lines; the record card's "Source and date" cell prints the row's `source_line` (§15). A source that does not answer leaves its rows Source unavailable, never Contradicted.

No score. The five-segment strip, "n of m", "n pending" and "sources agree" are retired (Changes 2026-10-29): a record has one status (§21) and lists show it as a word with its icon in the Status column (`col.record_status`).

## 4. Enum words

| id | text |
|---|---|
| type.GOVERNMENT | Government |
| type.GOVERNMENT_AIDED | Government aided |
| type.PRIVATE_SELF_FINANCED | Private self-financed |
| type.UNIVERSITY_DEPARTMENT | University department |
| type.DEEMED | Deemed |
| level.DIPLOMA | Diploma |
| level.UG | UG |
| level.PG | PG |
| level.POST_DIPLOMA | Post diploma |
| shift.FIRST | First |
| shift.SECOND | Second |
| mode.PHYSICAL | Physical |
| mode.ODL | Open and distance learning |
| mode.ONLINE | Online |
| consent.LINKED | Linked |
| consent.REFUSED | Refused |
| consent.PENDING | Pending |
| consent.INTERNATIONAL | International |
| consent.tip_LINKED | APAAR linked with the student's consent |
| consent.tip_REFUSED | Student declined to share APAAR; a provisional id is used |
| consent.tip_PENDING | Consent not recorded yet; a provisional id is used |
| consent.tip_INTERNATIONAL | International student; passport-based, no APAAR |
| route.COUNSELLING | Counselling |
| route.MANAGEMENT | Management |
| route.NRI | NRI |
| route.SPOT | Spot |
| route.LATERAL | Lateral |
| route.INTERNATIONAL | International |
| route.TFW | TFW |
| category.GENERAL | General |
| category.EWS | EWS |
| category.OBC | OBC |
| category.SC | SC |
| category.ST | ST |
| category.OTHER | Other |
| seat_type.REGULAR | Regular |
| seat_type.NRI | NRI |
| seat_type.TFW | TFW |
| seat_type.LATERAL | Lateral |
| seat_type.INTERNATIONAL | International |
| seat_status.FREE | Free |
| seat_status.ASSIGNED | Assigned |
| seat_status.RELEASED | Released |
| enrol_status.ACTIVE | Active |
| enrol_status.WITHDRAWN | Withdrawn |
| enrol_status.TRANSFERRED | Transferred |
| enrol_status.GRADUATED | Graduated |
| enrol_status.withdrawn_by_decision | Withdrawn by decision |
| severity.LOW | Low |
| severity.MEDIUM | Medium |
| severity.HIGH | High |
| flag_status.OPEN | Open |
| flag_status.DOCS_REQUESTED | Documents requested |
| flag_status.ESCALATED | Escalated |
| flag_status.UPHELD | Claim upheld |
| flag_status.CORRECTED | Claim corrected |
| flag_status.WITHDRAWN | Claim withdrawn |
| upload_status.QUEUED | Queued |
| upload_status.VALIDATING | Validating |
| upload_status.PROCESSING | Processing |
| upload_status.DONE | Done |
| upload_status.FAILED | Failed |
| upload_stage.PARSE | Reading the file |
| upload_stage.VALIDATE | Checking rows |
| upload_stage.FILE_DUPLICATES | Looking for repeated rows |
| upload_stage.UPSERT | Saving students and enrolments |
| upload_stage.LEDGER | Assigning seats |
| upload_stage.CHECKS | Checking with sources |
| upload_stage.DUPLICATES | Looking for duplicates |
| upload_stage.FLAGS | Opening cases |
| upload_stage.DONE | Done |
| upload_source.FILE | File upload |
| upload_source.API | College system |
| upload_source.SEED | Demo seed |
| notice_reply.YES | Joined |
| notice_reply.NO | Never joined |
| notice_reply.NONE | No reply yet |
| notice_reply.EXPIRED | No reply (expired) |
| notice_channel.EMAIL | Email |
| notice_channel.DIGILOCKER | DigiLocker |
| notice_delivery.QUEUED | Waiting to send |
| notice_delivery.SENT | Sent |
| notice_delivery.FAILED | Not delivered |
| consent_purpose.APAAR_LINK | Using your APAAR to check your enrolment |
| consent_purpose.NOTICE | Notices asking you to confirm an enrolment |
| consent_purpose.CREDENTIAL_SHARE | Sharing your attestations with verifiers |
| consent_state.GIVEN | Given |
| consent_state.WITHDRAWN | Withdrawn |
| consent_state.REFUSED | Refused |
| data_request_kind.ACCESS | Copy of my data |
| data_request_kind.CORRECTION | Correction |
| data_request_kind.ERASURE | Erasure |
| data_request_status.OPEN | Open |
| data_request_status.DONE | Done |
| data_request_status.REJECTED | Declined |
| audit_action.CREATE | Created |
| audit_action.UPDATE | Updated |
| audit_action.DELETE | Deleted |
| audit_action.READ | Viewed |
| audit_action.LOGIN | Signed in |
| audit_action.LOGOUT | Signed out |
| audit_action.SEED | Seeded |
| provisional.label | Provisional id |
| gender.M | Male |
| gender.F | Female |
| gender.O | Other |
| gender.U | Not stated |

## 5. Case names and evidence templates

`flag.<TYPE>.name` is the case's name shown in tables, filters, chips and the dashboard (the wire keeps `flag`; people read "case"). Everything else in this section is a reference copy of API_CONTRACT §A2.17: the engines write `summary`, `facts` and `rule_source` into the flag and the web prints them verbatim, in the order sent. The web never rebuilds a summary from these templates.

Placeholders are the contract's. `{cohort_year}` is the approval year (`2026-27`); `{academic_year}` is the roll year, used only by flags that are not about seats. Dates inside sentences and fact values read `5 Oct 2026`.

Names, in dashboard order (ARCHITECTURE §9)

| id | text |
|---|---|
| flag.EXCESS_ADMISSION.name | Excess admission |
| flag.QUOTA_BREACH.name | Quota breach |
| flag.LATE_REFILL.name | Late refill |
| flag.INVALID_APAAR.name | APAAR not verified |
| flag.NAME_MISMATCH.name | Name or date of birth mismatch |
| flag.DUPLICATE_CROSS_INSTITUTION.name | Duplicate across institutions |
| flag.DUPLICATE_WITHIN_UPLOAD.name | Duplicate within institution |
| flag.DUAL_ENROLMENT_ALLOWED.name | Dual enrolment (allowed) |
| flag.NO_ACADEMIC_ACTIVITY.name | No academic activity |
| flag.NOT_IN_JOINING_RECORD.name | Not in joining record |
| flag.ELIGIBILITY_BREACH.name | Seat category not eligible |
| flag.MISSING_FROM_UPLOAD.name | Missing from upload |
| flag.STUDENT_DENIED.name | Student dispute |
| flag.GHOST_RING.name | Shared contact ring |
| flag.ANOMALY.name | Unusual pattern |

Summaries (`evidence.summary`, one sentence, never a student name or a full id)

| id | severity | when | text |
|---|---|---|---|
| flag.EXCESS_ADMISSION.summary | High | admissions on Regular and NRI routes exceed the seats inside the intake | {admitted} admitted against {approved} approved seats in {programme_code} ({cohort_year}); {unseated} without a seat. |
| flag.QUOTA_BREACH.summary | Medium; High when the NRI or International pool is more than 2 over | any other pool has admissions without a seat | {admitted} {seat_type_word} admissions against {capacity} {seat_type_word} seats in {programme_code} ({cohort_year}). |
| flag.LATE_REFILL.summary | Medium | a released seat goes to an admission dated after the last admission date | Seat {seat_code} assigned on {assigned_date}, after the last admission date {cutoff_date}. |
| flag.INVALID_APAAR.summary | High | a well-formed APAAR is not in the registry | APAAR ending {apaar_last4} is not in the APAAR registry. |
| flag.INVALID_APAAR.summary_malformed | Medium | the APAAR as uploaded is not 12 digits | APAAR as uploaded {problem}, so it could not be checked. |
| flag.NAME_MISMATCH.summary | Medium below 75; Low from 75 to 89 | the name differs from the registry | Name on upload differs from the APAAR registry (similarity {name_score} of 100). |
| flag.NAME_MISMATCH.summary_dob | Medium | the date of birth differs from the registry | Date of birth on upload differs from the APAAR registry. |
| flag.DUPLICATE_CROSS_INSTITUTION.summary | High with a shared APAAR or passport; Medium by name, date of birth and mobile | officers | The same student appears as active at {institution_a} and {institution_b} ({academic_year}). |
| flag.DUPLICATE_CROSS_INSTITUTION.summary_institution | as above | the registrar (`summary_for_institution`) | The same student appears as active here and at another institution in {state_b} ({academic_year}). |
| flag.DUPLICATE_WITHIN_UPLOAD.summary | Medium | both rows in one file | Rows {row_a} and {row_b} of {filename} describe the same student. |
| flag.DUPLICATE_WITHIN_UPLOAD.summary_two_files | Medium | the rows are in two files | Row {row_b} of {filename_b} describes the same student as row {row_a} of {filename_a}. |
| flag.DUAL_ENROLMENT_ALLOWED.summary | Low | one physical programme plus one open and distance learning or online programme | The student holds two enrolments; one is distance or online, which is permitted. |
| flag.NO_ACADEMIC_ACTIVITY.summary | Medium | two or more expected semesters have no credits | No credits recorded in ABC for {missing} semesters while enrolled in year {year_of_study}. |
| flag.STUDENT_DENIED.summary | High, priority; the record reads Disputed | the student answers No after DigiLocker sign-in; a No beats a Yes | The student said they never joined, after signing in with DigiLocker on {reply_date}. |
| flag.STUDENT_DENIED.summary_changed | High; the case keeps its status | the student changed the answer from No to Yes within 7 days | The student said they never joined on {reply_date}, then changed the answer to Yes on {changed_date}. |
| flag.NOT_IN_JOINING_RECORD.summary | Medium | the Joining record row is Contradicted after the reporting deadline | Not found in the {state_name} admission authority's joining record for {programme_code} ({academic_year}) after the reporting deadline of {deadline_date}. |
| flag.ELIGIBILITY_BREACH.summary | Medium; High for an International or CIWG seat | a seat's category does not allow the student as reported (D41) | {seat_type_word} seat in {programme_code} ({cohort_year}) held by a student reported as {reported_word}. |
| flag.MISSING_FROM_UPLOAD.summary | Medium; one per college and year | students the admission authority lists as joined are not in the uploads (D40) | {missing} students the {state_name} admission authority lists as joined at {institution_name} in {academic_year} are not in the college's uploads. |
| flag.GHOST_RING.summary | set by the officer | opened only from a signal (§27) | {students} students across {institutions} institutions share {contacts} contact details. |
| flag.ANOMALY.summary | set by the officer | opened only from a signal (§27) | {institution_name} stands out from similar colleges on {feature_words} ({academic_year}). |

Facts (`evidence.facts`, label: value, source, in this order)

| type | label | value | source |
|---|---|---|---|
| EXCESS_ADMISSION | Approved intake | {approved} | AICTE approval {cohort_year} |
| | Admitted (active) | {admitted} | College uploads, Regular and NRI routes |
| | Seated | {seated} | Seat ledger |
| | Unseated | {unseated} | Seat ledger |
| | Most unseated at once (only when higher than Unseated) | {peak_unseated} | Seat ledger |
| QUOTA_BREACH | Pool | {seat_type_word} | Seat ledger |
| | Capacity | {capacity} | AICTE approval rules |
| | Admitted via route | {admitted} ({route_words}) | College uploads |
| | Unseated | {unseated} | Seat ledger |
| | Rule percentage | {share}% of approved intake {approved} | AICTE approval rules |
| LATE_REFILL | Seat | {seat_code} | Seat ledger |
| | Released on | {released_date} | Seat ledger |
| | Assigned on | {assigned_date} | College upload {filename}, row {row_no} |
| | Last admission date | {cutoff_date} | AICTE admission schedule |
| INVALID_APAAR, not in registry | APAAR (masked) | XXXX XXXX {apaar_last4} | College upload |
| | Registry reply | Not found | APAAR registry |
| | Checked at | {checked_date} | APAAR registry |
| INVALID_APAAR, malformed | APAAR (masked) | <{n} characters> | College upload |
| | Registry reply | Not checked | APAAR registry |
| | Checked at | {checked_date} | Countersign |
| NAME_MISMATCH | Name on upload | {name} | College upload |
| | Similarity | {name_score} of 100 | APAAR registry |
| | Date of birth match | Yes (name variant) or No (date of birth variant) | APAAR registry |
| | Checked at | {checked_date} | APAAR registry |
| DUPLICATE_WITHIN_UPLOAD | Match on | {match_words} | Duplicate detection |
| | Row A | {filename_a}, row {row_a} | College upload |
| | Row B | {filename_b}, row {row_b} | College upload |
| | Names as uploaded | {name_a} / {name_b} | College upload |
| DUPLICATE_CROSS_INSTITUTION | Match on | {match_words} | Duplicate detection |
| | Institution A programme | {institution_a}: {programme_a} | College upload {uploaded_a} |
| | Institution B programme (officers) | {institution_b}: {programme_b} | College upload {uploaded_b} |
| | Institution B programme (registrar) | Another institution in {state_b}: {programme_b} | |
| | Uploaded on | {uploaded_a} and {uploaded_b} | College uploads |
| DUAL_ENROLMENT_ALLOWED | Enrolment A mode | {institution_a}: {programme_a}, {mode_a_word} | College upload |
| | Enrolment B mode (officers) | {institution_b}: {programme_b}, {mode_b_word} | College upload |
| | Enrolment B mode (registrar) | Another institution in {state_b}: {programme_b}, {mode_b_word} | College upload |
| | UGC notification | Pursuing two academic programmes simultaneously, 2022 | UGC |
| NO_ACADEMIC_ACTIVITY | Semesters checked | {expected} ({first_academic_year} to {last_academic_year}) | ABC |
| | Credits found | Sem 1: 0, Sem 2: 0 (one entry per semester) | ABC |
| | Last ABC entry | {last_entry_date}, or None | ABC |
| STUDENT_DENIED | Signed in with | DigiLocker | Student sign-in via DigiLocker |
| | Notice sent | {sent_date} | Countersign |
| | Answered on | {reply_date} | Student sign-in via DigiLocker |
| | Answer changed (only after a change) | Yes on {changed_date} | Student sign-in via DigiLocker |
| | Comment from the student (officers only) | {comment}, or None | Student sign-in via DigiLocker |
| NOT_IN_JOINING_RECORD | Programme and year | {programme_code} ({academic_year}) | College upload |
| | Joining record | Not found | State admission authority |
| | Checked on | {checked_date} | State admission authority |
| | Reporting deadline | {deadline_date} | AICTE reporting schedule |
| ELIGIBILITY_BREACH | Seat | {seat_code} ({seat_type_word}) | Seat Ledger |
| | Reported as | {reported_word} | College upload |
| | Allowed for this seat | {allowed_words} | AICTE approval rules |
| MISSING_FROM_UPLOAD | Joined (authority) | {joined} | State admission authority |
| | Uploaded and joined | {matched} | Reconciliation |
| | Missing | {missing} | Reconciliation |
| | Completeness | {pct}% | Reconciliation |
| | Reporting deadline | {deadline_date} | AICTE reporting schedule |
| | Missing students | {masked_ids} | State admission authority |
| GHOST_RING | the signal's facts (§27) | | Signal, contact graph |
| ANOMALY | the signal's feature lines (§27) | | Signal, Isolation Forest |

STUDENT_DENIED (shown as Student dispute): the answer counts only after DigiLocker sign-in (D37), whichever channel carried the notice. The comment fact carries `audience: "OFFICER"`, so a registrar never receives it (D24). When the student changes a No to a Yes, the case keeps its status (only an officer decides it), its evidence is refreshed with `summary_changed` and the Answer changed fact, and the case history gains a System row (§6). MISSING_FROM_UPLOAD lists missing students by masked id only (D40). GHOST_RING and ANOMALY cases exist only when an officer opens one from a signal; the case cites the signal and copies its facts and rule.

Words: `{match_words}` is "Same APAAR", "Same passport" or "Name ({name_score} of 100), date of birth and mobile", joined with "and" when more than one matched. `{mode_a_word}` and `{mode_b_word}` are "physical", "open and distance learning" or "online". `{route_words}` lists the routes that map to the pool (NRI; TFW; Lateral; International). Institution A is always the flag's own institution and B the other one. The registrar never sees B's name: the api drops the officer facts and keeps the registrar ones.

Rule sources (`evidence.rule_source`, shown after "Rule:")

| id | text |
|---|---|
| flag.EXCESS_ADMISSION.rule | {rule_source}, the Regular pool's, e.g. "AICTE approved intake; minus NRI carve-out (APH 2024-27 cl. 2.8(b))" |
| flag.QUOTA_BREACH.rule | {rule_source}, the breached pool's, e.g. "APH 2024-27 cl. 2.8(b)" for NRI |
| flag.LATE_REFILL.rule | Last admission date for {cohort_year} (AICTE admission schedule) |
| flag.INVALID_APAAR.rule | APAAR verification |
| flag.NAME_MISMATCH.rule | APAAR verification |
| flag.DUPLICATE_CROSS_INSTITUTION.rule | One active full-time enrolment per student |
| flag.DUPLICATE_WITHIN_UPLOAD.rule | Upload validation |
| flag.DUAL_ENROLMENT_ALLOWED.rule | UGC dual-degree guidelines 2022 |
| flag.NO_ACADEMIC_ACTIVITY.rule | ABC credit record |
| flag.NOT_IN_JOINING_RECORD.rule | {state_name} admission authority joining record, after the reporting deadline |
| flag.ELIGIBILITY_BREACH.rule | {clause}, e.g. "APH 2026-27 cl. 2.8(b)" for an NRI seat |
| flag.MISSING_FROM_UPLOAD.rule | Reconciliation with the {state_name} admission authority's joinings list |
| flag.STUDENT_DENIED.rule | Student's answer after DigiLocker sign-in |
| flag.GHOST_RING.rule | The signal's rule: contact graph, groups of 3 or more across 2 or more colleges, or 5 or more in one college |
| flag.ANOMALY.rule | The signal's model: Isolation Forest, contamination 5%, trained on this year's colleges |

QUOTA_BREACH counts `{admitted}` (enrolments by route), because assigned seats can never exceed a pool's capacity. LATE_REFILL cites the last admission date from the AICTE admission schedule (kept in `rules.yaml` `cutoff_dates`; evidence never names the file), not APH cl. 6.13(f), which is the lateral-entry vacancy clause.

Rules for every template: no verdict words (never "fraud", "fake", "illegal"); claimed figure first, source figure second; the period in brackets; one sentence.

## 6. Case actions and officer decisions

Officer case detail (`/aicte/cases/[caseId]`, `/ro/cases/[caseId]`) and the registrar's case detail (`/college/cases/[caseId]`), from `POST /flags/{id}/actions {action, reason_code, note, due_date?, docs_kind?, assignee_id?, correction?, withdrawn_enrolment_ids?, approval_version?}`, `POST /flags/{id}/response` and the `history` of `GET /flags/{id}` (D25, D43). The wire keeps the name `flags`; every visible word says case. `reason_code`, `correction` and `withdrawn_enrolment_ids` are in migration 0004; `docs_kind` and `approval_version` are pending contract confirmation.

A decision is an officer's, always with a reason and a note, and the record, the seat count, the attestation and the audit trail change together. A decision is never evidence (R2).

Actions

| id | text |
|---|---|
| case.decide_heading | Decide |
| case.uphold | Uphold claim |
| case.correct | Correct record |
| case.withdraw | Withdraw claim |
| case.request_docs | Request documents |
| case.escalate | Escalate |
| case.reopen | Reopen |
| case.note | Add note |
| case.assign | Assign |
| case.cancel | Cancel |
| case.sending | Sending |
| case.note_label | Note (shown to the college) |
| case.note_label_internal | Note (officers only) |
| case.note_required | Add a note before you continue. |
| case.reason_label | Reason |
| case.reason_placeholder | Choose a reason |
| case.reason_required | Choose a reason before you continue. |
| case.changes_heading | What will change |
| case.who_sees | {institution_name} sees your decision, its reason and your note. |
| case.who_sees_student | The student sees the outcome in plain words, never your note or your name. |

Uphold claim (the college's claim stands; UPHELD)

| id | text |
|---|---|
| case.uphold_heading | Uphold the college's claim? |
| case.uphold_lead | The college's record stands as uploaded. |
| case.uphold_change.case | The case closes as Claim upheld. |
| case.uphold_change.row | The contradicted row stays on the record, marked "Claim upheld by an officer on {today}". |
| case.uphold_change.status | The record's status is worked out again. It becomes Countersigned only if a source independent of the college confirms it; otherwise it reads Awaiting evidence. |
| case.uphold_change.not_evidence | Your decision settles the contradiction. It is not evidence and does not confirm the record. |
| case.uphold_change.seat | No seat changes. |
| case.uphold_change.attestation | The attestation revoked when the student disputed the record is issued again once the record is Countersigned. |
| case.uphold_change.version | Approval v{version} for {programme_code} ({cohort_year}), intake {intake}, covers these admissions. The Seat Ledger seats them from the backlog. |
| case.uphold_version_label | Approval version that covers these admissions |
| case.uphold_version_none | No approval version covers these admissions yet. Withdraw or correct the records, or wait for a new approval version. |
| case.uphold_submit | Uphold claim |
| case.upheld_toast | Claim upheld. The record now reads {status_word}. |
| case.upheld_toast_programme | Claim upheld under approval v{version}. {seated} records seated. |

Correct record (CORRECTED)

| id | text |
|---|---|
| case.correct_heading | Correct the record |
| case.correct_lead | Choose the fields that are wrong and enter the right values. Only the fields you change are stored, as a new version of the record. |
| case.correct_record_label | Record to correct |
| case.correct_field_label | Field |
| case.correct_now | Now |
| case.correct_new | Correct value |
| case.correct_add | Add another field |
| case.correct_remove | Remove {field_word} |
| case.correct_not_here | APAAR and status are not corrected here. An APAAR change needs the student's consent through the college's upload, and a withdrawal is its own decision. |
| case.correct_change.version | These fields change, saved as version {version} of the record with your name and reason: |
| case.correct_change.line | {field_word}: {before} to {after} |
| case.correct_change.rerun | Countersign checks every row of the record again against its sources and the Seat Ledger. |
| case.correct_change.seat | Seat {seat_code} is released, and a {seat_type_word} seat in {programme_code} is assigned if one is free. If none is free, the record is unseated and a case opens. |
| case.correct_change.case | The case closes as Claim corrected. |
| case.correct_change.status | The record's status is worked out again from the new evidence. |
| case.correct_submit | Correct record |
| case.corrected_toast | Record corrected. Version {version} saved and the evidence checked again; the record now reads {status_word}. |

Withdraw claim (WITHDRAWN)

| id | text |
|---|---|
| case.withdraw_heading | Withdraw the claim? |
| case.withdraw_lead | The college's claim that this student joined does not stand. |
| case.withdraw_lead_programme | Choose the records whose claim does not stand. The others stay as they are. |
| case.withdraw_pick_label | Records to withdraw |
| case.withdraw_pick_hint | Only records this case names are listed. |
| case.withdraw_pick_all | Select all {n} |
| case.withdraw_pick_count | {n} of {total} selected |
| case.withdraw_change.status | The record is withdrawn: its status becomes Withdrawn, with the reason "withdrawn by decision", and it leaves the college's active counts. |
| case.withdraw_change.status_many | {n} records are withdrawn: each status becomes Withdrawn, with the reason "withdrawn by decision", and they leave the college's active counts. |
| case.withdraw_change.seat | Seat {seat_code} is released. |
| case.withdraw_change.seats | {n} seats are released: {seat_codes}. |
| case.withdraw_change.no_seat | No seat to release. |
| case.withdraw_change.attestation | Enrolment attestation {short_id} is revoked. Anyone who checks it sees Revoked. |
| case.withdraw_change.attestations | {n} enrolment attestations are revoked. Anyone who checks them sees Revoked. |
| case.withdraw_change.no_attestation | No attestation to revoke. |
| case.withdraw_change.kept | Nothing is deleted. Each record and its history stay, marked withdrawn. |
| case.withdraw_change.case | The case closes as Claim withdrawn. |
| case.withdraw_change.student | The student sees that the college's claim was withdrawn. |
| case.withdraw_ack | I have read what will change. |
| case.withdraw_ack_required | Tick the box to confirm you have read what will change. |
| case.withdraw_submit | Withdraw claim |
| case.withdraw_submit_many | Withdraw {n} records |
| case.withdrawn_toast | Claim withdrawn: {records} records withdrawn, {seats} seats released, {attestations} attestations revoked. |

Request documents, Escalate, Reopen, Add note, Assign

| id | text |
|---|---|
| case.request_docs_prompt | What should the college send? Be specific, e.g. "Admission register extract for CSE, 2026-27". |
| case.docs_kind_label | What to send |
| case.request_docs_email | Every registrar account of {institution_name} gets an email with your request. |
| case.request_docs_change | The record's next step reads "College asked for {docs_words} by {due_date}." Nothing else changes. |
| case.request_docs_change_no_date | The record's next step reads "College asked for {docs_words}; no reply date set." Nothing else changes. |
| case.request_docs_send | Send request |
| case.due_date | Reply by (optional) |
| case.due_date_hint | Shown to the college with your request. |
| case.due_date_past | Choose today or a later date. |
| case.due_date_far | Choose a date within 90 days of today. |
| case.escalate_prompt | Why does this need a senior officer? |
| case.escalate_note | After escalation only an AICTE officer can decide the case or request documents. Regional officers can still add notes. |
| case.escalate_change | The case goes to AICTE. Only an AICTE officer can decide it. Nothing about the record changes. |
| case.reopen_prompt | Why reopen this case? It goes back to Open and the earlier decision stays in the history. Reopening does not undo what the decision changed; a new decision does. |
| case.assign_label | Assign to |
| case.assign_search | Search officers by name |
| case.assign_me | Assign to me |
| case.assign_none | Remove assignee |
| case.assign_option | {name}, {role_word} |
| case.assign_empty | No officer matches "{q}". |
| case.assignee_none | Unassigned |
| case.assignee_line | Assignee: {name} |
| case.docs_toast | Request sent to the registrar. |
| case.escalated_toast | Escalated to AICTE. |
| case.reopened_toast | Reopened. The case is Open again. |
| case.note_toast | Note added. |
| case.assigned_toast | Assigned to {name}. |
| case.unassigned_toast | Assignee removed. |
| case.back | Back to queue |

What the college is asked to send (`docs_kind`, pending contract confirmation; `.words` is the form used inside `next_step` and the email)

| id | text |
|---|---|
| docs_kind.ADMISSION | Admission documents |
| docs_kind.ADMISSION.words | admission documents |
| docs_kind.JOINING | Joining report |
| docs_kind.JOINING.words | the joining report |
| docs_kind.IDENTITY | Identity documents |
| docs_kind.IDENTITY.words | identity documents |
| docs_kind.ELIGIBILITY | Eligibility certificates |
| docs_kind.ELIGIBILITY.words | eligibility certificates |
| docs_kind.CREDITS | Semester results |
| docs_kind.CREDITS.words | semester results |
| docs_kind.OTHER | Other documents |
| docs_kind.OTHER.words | documents |

Reasons (`reason_code` with its outcome; pending contract confirmation of the codes)

| id | text |
|---|---|
| reason.UPHOLD.DOCUMENTS_SUPPORT_CLAIM | Documents support the college's record |
| reason.UPHOLD.SOURCE_RECORD_WRONG | The source's record was wrong or late |
| reason.UPHOLD.NAME_VARIANT | Same person; the name is spelt differently |
| reason.UPHOLD.PERMITTED_DUAL_PROGRAMME | Permitted to study two programmes at once |
| reason.UPHOLD.APPROVAL_VERSION_COVERS | A new approval version covers these admissions |
| reason.UPHOLD.STUDENT_ANSWER_MISTAKEN | The student's answer was a mistake, confirmed with the student |
| reason.UPHOLD.MISSING_NOW_UPLOADED | The missing students are now uploaded |
| reason.UPHOLD.OTHER | Other (explain in the note) |
| reason.CORRECT.UPLOAD_ERROR | Data entry error in the college's upload |
| reason.CORRECT.DOCUMENTS_SHOW_OTHER_VALUE | Documents show a different value |
| reason.CORRECT.WRONG_SEAT_CATEGORY | Reported in the wrong seat category |
| reason.CORRECT.OTHER | Other (explain in the note) |
| reason.WITHDRAW.STUDENT_NEVER_JOINED | The student never joined |
| reason.WITHDRAW.NO_JOINING_EVIDENCE | No joining record and no documents |
| reason.WITHDRAW.BEYOND_APPROVED_INTAKE | Admitted beyond the approved intake |
| reason.WITHDRAW.NOT_ELIGIBLE_FOR_SEAT | Not eligible for the seat category |
| reason.WITHDRAW.DUPLICATE_RECORD | Duplicate of another record |
| reason.WITHDRAW.NO_RESPONSE | No response from the college by the reply date |
| reason.WITHDRAW.OTHER | Other (explain in the note) |
| reason.ESCALATE.NEEDS_AICTE_DECISION | Needs a decision at AICTE level |
| reason.ESCALATE.POLICY_QUESTION | Raises a policy question |
| reason.ESCALATE.SPANS_REGIONS | Involves colleges in more than one region |
| reason.ESCALATE.REPEATED_PATTERN | Part of a repeated pattern at this college |
| reason.ESCALATE.OTHER | Other (explain in the note) |

Case status lines

| id | text |
|---|---|
| case.response_badge | Response received |
| case.response_badge_tip | The college responded on {date}. The case stays at Documents requested until an officer decides. |
| case.due_line | Reply due by {due_date} |
| case.due_passed | Reply date {due_date} has passed |
| case.escalated_ro | Only AICTE can decide an escalated case. You can still add a note. |
| case.closed_line | This case is decided. Only an AICTE officer can reopen it. |
| case.closed_admin | This case is decided. Reopen it to act on it again. |
| case.from_signal | Opened from a signal: {signal_summary} |
| case.attachment | {filename}, {size} |
| case.attachment_download | Download {filename} |
| case.attachments_logged | Each download is logged. |

History (one row per `history[]` entry, oldest first, after [case.history.opened])

| id | text |
|---|---|
| case.history.opened | Case opened |
| case.history.opened_from_signal | Case opened from a signal |
| case.history.col.when | When |
| case.history.col.who | Who |
| case.history.col.what | What |
| case.history.who | {actor_name}, {role_word} |
| case.history.system | System |
| case.history.REQUEST_DOCS | Requested documents |
| case.history.COLLEGE_RESPONSE | Responded |
| case.history.ESCALATE | Escalated |
| case.history.UPHOLD | Upheld the claim |
| case.history.CORRECT | Corrected the record |
| case.history.WITHDRAW | Withdrew the claim |
| case.history.NOTE | Added a note |
| case.history.ASSIGN | Assigned to {assignee_name} |
| case.history.ASSIGN_none | Removed the assignee |
| case.history.REOPEN | Reopened the case |
| case.history.SYSTEM_NOTE | Evidence updated after the decision |
| case.history.status_change | {from_word} to {to_word} |
| case.history.due | Reply by {due_date} |
| case.history.reason | Reason: {reason_word} |
| case.history.correction_line | {field_word}: {before} to {after} |
| case.history.withdrawn_line | {records} records withdrawn, {seats} seats released, {attestations} attestations revoked |
| case.system_note.reply_changed | The student changed the answer from No to Yes on {changed_date}. The case keeps its status until an officer decides. |
| case.system_note.missing_updated | The college uploaded {n} of the missing students on {date}; {remaining} still missing. |

A history row reads When (`at`, `14 Jul 2026, 09:31 IST`), Who (`case.history.who` with `{role_word}` from `shell.role.*`, or `case.history.system` when the actor is null; the registrar sees the role only), What (the `case.history.<ACTION>` words, then `case.history.status_change` in small text when `from_status` and `to_status` differ, `case.history.due` when `due_date` is set, and `case.history.reason` for a decision), and under it the note in quotes, one `case.history.correction_line` per corrected field, `case.history.withdrawn_line` for a withdrawal, and one `case.attachment` link per file. A SYSTEM_NOTE row prints its `note` verbatim when the api sends one other than `case.history.SYSTEM_NOTE`; the deck mirrors the notes the engines write, `case.system_note.*`. Status words come from `flag_status.*`.

Which actions show (D25, D43). The action bar shows exactly the case's `allowed_actions`, in the order the api sends them, with the three decisions grouped under `case.decide_heading`; a refused action is not shown. AICTE officer: on Open and Documents requested, Uphold claim, Correct record, Withdraw claim, Request documents, Escalate, Add note, Assign; on Escalated, the same without Escalate; on Claim upheld, Claim corrected and Claim withdrawn, Add note and Reopen, with `case.closed_admin`. Regional officer, for its region: on Open and Documents requested, the same as the AICTE officer; on Escalated, only Add note, with `case.escalated_ro`; on a decided case, only Add note, with `case.closed_line`. Registrar: only Respond, and only while the case is Documents requested. University: none. Nobody can assign a decided case.

Which decisions fit which case. A case about one record offers all three decisions. A programme-level case (Excess admission, Quota breach) offers Uphold claim only with an approval version that covers the admissions (`case.uphold_version_label`, or `case.uphold_version_none` and the button disabled when none does), Correct record for one named record at a time (`case.correct_record_label`), and Withdraw claim with the record picker. A Missing from upload case names no record, so it offers Uphold claim (reasons Missing now uploaded, Source record wrong) and not Correct or Withdraw. A Student dispute offers all three; the student reads `student.decision.*` (§23).

Every decision sheet. A modal dialog labelled by its heading: the lead, the reason select (`case.reason_label`, `reason.<ACTION>.*`, required), the note (`case.note_label`, required), then `case.changes_heading` with one line per consequence, then `case.who_sees` (and `case.who_sees_student` on a Student dispute), then the submit button, which repeats the decision's verb and is never red. The "What will change" lines name every consequence with its real values (seat codes, attestation ids, the version number), from the api's preview of the decision (`POST /flags/{id}/actions` with `dry_run: true`, pending contract confirmation); until the preview exists the web builds them from the case's related records and says no more than it knows. Uphold lists `case.uphold_change.case`, `.row` (when a row is Contradicted), `.status`, `.not_evidence`, `.seat` or `.version`, and `.attestation` only when a dispute revoked one. Correct lists `case.correct_change.version` with its lines, `.rerun`, `.seat` only when the programme, the year of study, the admission route or an eligibility marker changes, `.case` and `.status`. Withdraw lists `case.withdraw_change.status` (or `.status_many`), `.seat`, `.seats` or `.no_seat`, `.attestation`, `.attestations` or `.no_attestation`, `.kept`, `.case`, and `.student` when the case is a Student dispute; it also needs `case.withdraw_ack` ticked. Escalate lists `case.escalate_change`; Request documents lists `case.request_docs_change` (or `_no_date`). `{seat_codes}` lists up to five codes, then "and {more} more". An empty reason shows `case.reason_required`, an empty note `case.note_required`, an unticked acknowledgement `case.withdraw_ack_required`, each under its field, with focus moved there; nothing is sent. A 409 `FLAG_TRANSITION_INVALID` shows [err.FLAG_TRANSITION_INVALID] in the sheet and refetches the case. The note field is `case.note_label` on Request documents and the three decisions, whose notes the college reads, and `case.note_label_internal` on Escalate, Add note and Reopen. A due date before today shows `case.due_date_past`, one more than 90 days ahead `case.due_date_far`.

After a decision: the toast (`case.upheld_toast`, `case.corrected_toast`, `case.withdrawn_toast`, `case.escalated_toast`) in an `aria-live` region names the result, the history gains the row, the case's related records refresh with their new status, and the record card of each shows the change.

College response

| id | text |
|---|---|
| college.respond | Respond |
| college.respond_heading | Respond to the document request |
| college.request_line | {role_word} asked on {requested_date}: |
| college.request_kind_line | What to send: {docs_kind_word} |
| college.due_line | Reply by {due_date} |
| college.respond_note | Your reply to the officer |
| college.respond_note_hint | Required. Say what you are sending and how it answers the request. |
| college.respond_note_required | Write a reply before you send. |
| college.respond_files | Attach documents (PDF, PNG or JPEG, up to 3 files, 5 MB each) |
| college.respond_add_file | Add file |
| college.respond_remove_file | Remove {filename} |
| college.respond_file_count | {n} of 3 files |
| college.respond_too_many | You can attach up to 3 files. Remove one to add another. |
| college.respond_file_type | {filename} is not a PDF, PNG or JPEG file. |
| college.respond_file_size | {filename} is larger than 5 MB. Attach a smaller copy. |
| college.respond_submit | Send to the officer |
| college.respond_sending | Sending |
| college.respond_progress | Sending, {pct}% |
| college.respond_sent | Sent to the officer. You will see their decision here. |
| college.respond_waiting | You responded on {date}. The case stays at Documents requested until the officer decides. |
| college.respond_more | Send more documents |
| college.other_institution | another institution in {state_name} |
| college.decision_line | {status_word} by {role_word} on {date}. Reason: {reason_word}. |

While the files upload, the submit button reads `college.respond_progress` with the percentage sent, and `college.respond_sending` before and after. `college.respond_file_type` and `college.respond_file_size` are checked in the browser before anything is sent; the server answers the same cases with 415 [err.ATTACHMENT_TYPE] and 413 [err.ATTACHMENT_TOO_LARGE]. `{size}` in `case.attachment` reads like `412 KB` or `1.8 MB`. On a decided case the registrar reads `college.decision_line` above the evidence, with the officer's role, never the name, and the note in quotes under it.

Email to the registrar when documents are requested (sent to every registrar account of the college, D25)

| id | text |
|---|---|
| email.docs_request.subject | Documents requested by AICTE: {flag_name}, {where} |
| email.docs_request.body | {role_word} has asked {institution_name} for {docs_words} about a case. Case: {flag_name}, {where}. Evidence: {summary} Request: "{note}" {due_sentence}Sign in to Countersign and open the case to respond: {link}. Attach PDF, PNG or JPEG files, up to 3, 5 MB each. Nothing about your college or its students has changed; an officer decides after reading your response. This email went to every registrar account of your college. |
| email.docs_request.due | Please reply by {due_date}. |

`{role_word}` is "An AICTE officer" when an AICTE officer asks, and "The {region_name} regional office" when a regional officer asks ("The Western regional office"). `{where}` is `{programme_code}, {academic_year}`, or `{academic_year}` alone for a case without a programme. `{docs_words}` is `docs_kind.*.words`. `{summary}` is the summary the registrar sees (the redacted one for a cross-institution duplicate). `{due_sentence}` is `email.docs_request.due` followed by a space, or nothing when no date was set. `{link}` is `{WEB_ORIGIN}/college/cases/{flag_id}`. The email names no student and no officer.

## 7. Upload

Screens: `/college/upload` (the form) and `/college/uploads/[batchId]` (status and row problems), API_CONTRACT §A2.2 to §A2.9. The api writes each row problem's `message` and a failed batch's `error`; the web prints both verbatim. The `rowerr.*` rows mirror §A2.3 so a reviewer can check them; the browser never rebuilds them.

Status and stage move together (§A2.7): the rail shows the five `upload_status.*` words; the line under it shows the current `upload_stage.*` word. Validating covers Reading the file, Checking rows and Looking for repeated rows; Processing covers the next five stages.

Form

| id | text |
|---|---|
| upload.heading | Upload admissions file |
| upload.lead | One file covers one academic year of your college. It changes only the students in it; students you leave out stay as they are. |
| upload.year | Academic year |
| upload.drop | Drop a CSV or XLSX here, or choose a file |
| upload.choose | Choose file |
| upload.chosen | {filename}, {size} |
| upload.remove | Remove file |
| upload.template | Template |
| upload.template_csv | Download CSV template |
| upload.template_xlsx | Download XLSX template |
| upload.max | Up to 20 MB and 50,000 rows |
| upload.columns | Columns expected |
| upload.columns_required | Required |
| upload.columns_optional | Optional |
| upload.columns_note | Column names are matched ignoring case, spaces and hyphens. Columns Countersign does not use are listed after the upload and ignored. |
| upload.changes_note | To report a withdrawal or a transfer, upload that student's row again with status Withdrawn or Transferred and the status date. Leave status blank for a new admission. |
| upload.declaration | I declare that this file is true to the college's admission register, and that each APAAR in it is shared with that student's consent as recorded in the consent column. |
| upload.submit | Upload |
| upload.sending | Sending file, {pct}% |
| upload.err_type | Only .csv and .xlsx files can be uploaded. |
| upload.err_size | The file is larger than 20 MB. Split it by programme and upload each part. |
| upload.err_declaration | Tick the declaration to upload. |
| upload.header_help | Download a template to see the column names Countersign expects. |
| upload.in_progress_link | See the upload in progress |
| upload.kind.INITIAL | Initial |
| upload.kind.UPDATE | Update |
| upload.kind_tip | The first completed upload of a year is the initial upload and later ones are updates. Countersign sets this; you do not choose it. |
| upload.previous | Previous uploads |
| col.file | File |
| col.uploaded_by | By |
| col.kind | Kind |
| col.upload_source | Source |
| col.rows | Rows |
| col.accepted | Accepted |
| col.with_errors | With errors |
| col.with_warnings | With warnings |

Batch page

| id | text |
|---|---|
| upload.batch_meta | {kind_word} · {source_word} · uploaded {uploaded_at} by {uploaded_by} |
| upload.rail_label | Upload status |
| upload.queued_note | Waiting to start. Uploads are processed one at a time. |
| upload.step | Step {n} of 8: {stage_word} |
| upload.progress_label | Progress |
| upload.rows | Rows {rows} · Accepted {accepted} · With errors {errors} · With warnings {warnings} |
| upload.checking | Checking against sources |
| upload.source_line | {source_name}: {calls} checked |
| upload.source_waiting | {source_name} did not respond for {n} rows. Those rows show Source unavailable, never Contradicted, and are asked again at the next recheck or the next upload of those rows. |
| upload.same_file | This file was already uploaded on {uploaded_date}. Uploading it again changes nothing. |
| upload.ignored_columns | Columns not recognised and ignored: {columns} |
| upload.done_heading | Upload processed |
| upload.done_summary | {ok} rows accepted · {seated} seats assigned · {unseated} unseated · {flags} cases opened |
| upload.done_changes | {created} new · {updated} updated · {unchanged} unchanged · {withdrawn} withdrawn · {transferred} transferred · {released} seats released |
| upload.done_status | {countersigned} Countersigned · {awaiting} Awaiting evidence · {under_review} Under review · {disputed} Disputed |
| upload.done_completeness | Completeness now {pct}%: {missing} joined students still missing from your uploads. |
| upload.done_note | Cases are for review by an officer. A case does not remove or change any record; only an officer's decision can. |
| upload.failed | This upload could not be finished. |
| upload.failed_earlier | Earlier uploads are unchanged. |
| upload.upload_again | Upload a file |
| upload.view_ledger | View seat ledger |
| upload.view_enrolments | View enrolments |
| upload.view_flags | View cases |
| college.no_upload_yet | Last upload: none yet. |
| last_upload.line | Last upload {uploaded_date}: {rows} rows, {errors} with errors · {status_word} |

`upload.done_status` counts the batch's active records by status and `upload.done_completeness` follows when the college's `missing` is above 0 (both pending contract confirmation). `upload.done_summary` takes `{ok}` = `counts.accepted`, `{seated}`, `{unseated}` and `{flags}` = `counts.flags_raised`. `upload.done_changes` takes the `counts` keys of the same names. `upload.failed` is followed by the batch `error` sentence verbatim, then `upload.failed_earlier`. `upload.same_file` shows when `same_file_as` is set, with its `uploaded_at` as the date. `last_upload.line` reads the institution's `last_upload` (`rows`, `errors`, `status`).

Row errors and warnings

| id | text |
|---|---|
| upload.errors_heading | Row errors and warnings ({n}) |
| upload.errors_filter.all | All |
| upload.errors_filter.ERROR | Errors |
| upload.errors_filter.WARNING | Warnings |
| upload.level.ERROR | Error |
| upload.level.WARNING | Warning |
| upload.level_tip.ERROR | This row was not saved. Fix it and upload the row again. |
| upload.level_tip.WARNING | This row was saved. The value shown was not used, or was recorded as the message says. |
| col.row | Row |
| col.row_level | Level |
| col.column | Column |
| col.problem | Problem |
| col.value | Value as uploaded |
| upload.value_blank | blank |
| upload.errors_download | Download errors as CSV |
| upload.errors_none | No row errors or warnings |
| upload.errors_next | Fix the rows marked Error and upload them again, on their own or in the whole file. Rows already accepted do not change when you upload them again. |

`{n}` in `upload.errors_heading` is the errors endpoint `total` (entries; a row can have several). The Column cell prints the column name as in the template (`apaar_id`, monospace), with the `field.*` word as its tooltip. The Value cell prints `value_masked` exactly as sent; null prints [upload.value_blank].

Column words (`{field_word}` and column tooltips)

| id | text |
|---|---|
| field.apaar_id | APAAR |
| field.name | Name |
| field.dob | Date of birth |
| field.gender | Gender |
| field.mobile | Mobile |
| field.email | Email |
| field.address | Address |
| field.nationality | Nationality |
| field.passport_no | Passport number |
| field.programme_code | Programme code |
| field.academic_year | Academic year |
| field.year_of_study | Year of study |
| field.admission_route | Admission route |
| field.counselling_ref | Counselling reference |
| field.category | Category |
| field.consent_status | Consent status |
| field.status | Status |
| field.status_date | Status date |
| field.admission_date | Admission date |
| field.tfw_income_certified | TFW income certificate |
| field.nri_sponsored | NRI sponsored |
| field.ciwg | CIWG |

Row problem messages (mirror of API_CONTRACT §A2.3, written by the api)

| id | level | column | text |
|---|---|---|---|
| rowerr.MISSING_REQUIRED | Error | the column | {field_word} is required |
| rowerr.APAAR_FORMAT | Warning | `apaar_id` | APAAR must be 12 digits |
| rowerr.DUPLICATE_IN_FILE | Error | `apaar_id` | Same APAAR appears on row {other_row} |
| rowerr.DUPLICATE_IN_FILE.passport_no | Error | `passport_no` | Same passport number appears on row {other_row} |
| rowerr.DUPLICATE_IN_FILE.name | Error | `name` | Same student (name, date of birth and mobile) appears on row {other_row} |
| rowerr.UNKNOWN_PROGRAMME | Error | `programme_code` | Programme code {value} is not approved for your college |
| rowerr.NO_APPROVAL_FOR_COHORT | Error | `year_of_study` | {programme_code} has no approval for {cohort_year}, the intake of a year {year_of_study} student in {academic_year} |
| rowerr.DOB_FORMAT | Error | `dob` | Date of birth must be YYYY-MM-DD |
| rowerr.DOB_IMPLAUSIBLE | Error | `dob` | Date of birth {value} gives an age of {age} at admission; expected 14 to 60 |
| rowerr.BAD_ENUM.admission_route | Error | `admission_route` | Admission route must be one of Counselling, Management, NRI, Spot, Lateral, International, TFW |
| rowerr.BAD_ENUM.category | Error | `category` | Category must be one of General, EWS, OBC, SC, ST, Other |
| rowerr.BAD_ENUM.consent_status | Error | `consent_status` | Consent status must be Linked, Refused, Pending or International |
| rowerr.BAD_ENUM.status | Error | `status` | Status must be Active, Withdrawn or Transferred |
| rowerr.BAD_ENUM.gender | Warning | `gender` | Gender must be M, F, O or U; recorded as U |
| rowerr.BAD_ENUM.tfw_income_certified | Error | `tfw_income_certified` | TFW income certificate must be Yes or No |
| rowerr.BAD_ENUM.nri_sponsored | Error | `nri_sponsored` | NRI sponsored must be Yes or No |
| rowerr.BAD_ENUM.ciwg | Error | `ciwg` | CIWG must be Yes or No |
| rowerr.YEAR_OF_STUDY_INVALID | Error | `year_of_study` | Year of study must be a whole number between 1 and {max} |
| rowerr.YEAR_MISMATCH | Error | `academic_year` | Academic year {value} does not match this upload's academic year {academic_year} |
| rowerr.PASSPORT_REQUIRED | Error | `passport_no` | International students need a passport number |
| rowerr.NATIONALITY_FORMAT | Error | `nationality` | Nationality must be a two-letter country code, e.g. IN |
| rowerr.DATE_FORMAT.status_date | Error | `status_date` | Status date must be YYYY-MM-DD |
| rowerr.DATE_FORMAT.admission_date | Error | `admission_date` | Admission date must be YYYY-MM-DD |
| rowerr.DATE_IN_FUTURE.status_date | Error | `status_date` | Status date {value} is after the upload date |
| rowerr.DATE_IN_FUTURE.admission_date | Error | `admission_date` | Admission date {value} is after the upload date |
| rowerr.MOBILE_FORMAT | Warning | `mobile` | Mobile must be 10 digits; the value was not used |
| rowerr.EMAIL_FORMAT | Warning | `email` | Email address is not valid; the value was not used |
| rowerr.CONSENT_CONFLICT.apaar_unused | Warning | `consent_status` | APAAR given but consent is {consent_word}; the APAAR was not used |
| rowerr.CONSENT_CONFLICT.no_apaar | Warning | `consent_status` | Consent is Linked but no APAAR was given; recorded as Pending |
| rowerr.NOT_PREVIOUSLY_ENROLLED | Warning | `status` | No earlier enrolment matches this student; recorded as {status_word} with no seat |

`{field_word}` is the `field.*` word of the column (the api uses the same six words for the required columns). `{max}` is the programme's duration, 6 when the programme is unknown. `{consent_word}` is `consent.*`; `{status_word}` is `enrol_status.*`.

## 8. Student notice and wallet

English

| id | text |
|---|---|
| notice.email_subject | {institution_name} has reported an enrolment in your name |
| notice.email_body | {institution_name} has told AICTE that you joined {programme_name} in {academic_year}. To see what they reported and to answer, open {link} and sign in with DigiLocker. Your answer is recorded only after you sign in with DigiLocker; nothing in this email can record it. The link works until {expires_date}. Never share your DigiLocker OTP with anyone, including AICTE or your college. |
| notice.digilocker | {institution_name} has reported that you joined {programme_short} ({academic_year}). Sign in to Countersign with DigiLocker to answer. |
| notice.headline | {institution_name} says |
| notice.claim | you joined {programme_name} |
| notice.meta | Academic year {academic_year} · Year {year_of_study} |
| notice.uploaded_line | They uploaded this on {uploaded_date} for {id_label} {id_masked}. |
| notice.question | Is that right? |
| notice.yes | Yes, I joined |
| notice.no | No, I never joined |
| notice.next_step | If you say no, a priority dispute opens and an AICTE officer looks into it first. Nothing changes for you until they decide. |
| notice.what_is_this_link | What is this? |
| notice.what_is_this | Countersign is AICTE's way of checking that colleges report only students who really joined. A college's upload is a claim, and your answer is one piece of evidence about it. You answer after signing in with DigiLocker, so only you can answer for yourself. Your answer is recorded with the date. |
| notice.yes_done | Thank you. Your answer is recorded: you joined {institution_name}. |
| notice.no_confirm | You are telling AICTE that you never joined {institution_name}. This opens a priority dispute: the college can respond with documents, and an officer decides. Anything we should know? (optional) |
| notice.no_comment_label | Anything we should know? |
| notice.no_submit | Send |
| notice.no_done | Thank you. Your dispute is recorded and an AICTE officer will look into it first. Nothing changes for you until they decide. |
| notice.answered | You replied "{reply}" on {responded_date}. |
| notice.change | Change my answer |
| notice.expired | This link has expired. No reply was recorded, and that does not count against you. To reply now, ask your college or AICTE to send a new notice. |
| notice.invalid | This link is not valid. Check that you opened the whole link from your message, or ask your college to send a new notice. |
| notice.page_title | Notice from {institution_name} |
| notice.lang_label | Language |
| notice.sending | Sending |
| notice.no_comment_hint | Only AICTE officers read this. Your college does not see it. |
| notice.no_cancel | Go back |
| notice.yes_next | When the rest of the evidence is in, an enrolment attestation you can share appears in My attestations. |
| notice.see_proofs | See my attestations |
| notice.reply.YES | Yes |
| notice.reply.NO | No |
| notice.change_window | You can change your answer once, until {change_until_date}. |
| notice.change_heading | Change your answer |
| notice.change_once | You can change your answer only once. After that it is final. |
| notice.current_answer | Your answer now |
| notice.change_submit | Save my new answer |
| notice.changed_done | Your answer is now "{reply}". It cannot be changed again. |
| notice.change_used | You changed your answer on {changed_date}. Your answer "{reply}" is final. |
| notice.change_closed | The 7 days to change your answer are over. If it needs correcting, ask from your Privacy page. |
| notice.rate_limited | Too many tries from this network. Try again in {seconds} s. |
| notice.lang_hi | हिन्दी |
| notice.lang_en | English |

Yes and No show only after DigiLocker sign-in; before it, and when the signed-in person is someone else or has not claimed a record without APAAR, the page shows the §23 states instead. The Hindi rows of `notice.email_subject` and `notice.email_body` are in §23; the email is sent in English with the Hindi text under it. `{reply}` takes `notice.reply.*`. `{id_label}` is "APAAR" or [provisional.label]. `{change_until_date}` is 7 days after the first reply. Page states and the error codes behind them: 404 `NOTICE_NOT_FOUND` (same body for an invalid and an unknown token) shows `notice.invalid`; 410 `NOTICE_EXPIRED` shows `notice.expired`; 409 `NOTICE_ALREADY_CHANGED` shows `notice.change_used`; 429 shows `notice.rate_limited`.

Hindi (for review by a native speaker before the panel)

| id | text |
|---|---|
| notice.digilocker.hi | {institution_name} का कहना है कि आपने {programme_short} ({academic_year}) में प्रवेश लिया है। उत्तर देने के लिए DigiLocker से Countersign में साइन इन करें। |
| notice.headline.hi | {institution_name} का कहना है |
| notice.claim.hi | कि आपने {programme_name} में प्रवेश लिया है |
| notice.meta.hi | शैक्षणिक वर्ष {academic_year} · वर्ष {year_of_study} |
| notice.question.hi | क्या यह सही है? |
| notice.yes.hi | हाँ, मैंने प्रवेश लिया है |
| notice.no.hi | नहीं, मैंने कभी प्रवेश नहीं लिया |
| notice.next_step.hi | अगर आप "नहीं" चुनते हैं, तो एक प्राथमिकता विवाद खुलता है और AICTE का एक अधिकारी सबसे पहले इसकी जाँच करता है। उनके निर्णय तक आपके लिए कुछ नहीं बदलता। |
| notice.yes_done.hi | धन्यवाद। आपका उत्तर दर्ज हो गया है: आपने {institution_name} में प्रवेश लिया है। |
| notice.no_done.hi | धन्यवाद। आपका विवाद दर्ज हो गया है और AICTE का एक अधिकारी सबसे पहले इसकी जाँच करेगा। उनके निर्णय तक आपके लिए कुछ नहीं बदलता। |
| notice.expired.hi | यह लिंक समाप्त हो गया है। कोई उत्तर दर्ज नहीं हुआ, और इसे आपके विरुद्ध नहीं गिना जाता। अभी उत्तर देने के लिए अपने कॉलेज या AICTE से नई सूचना भेजने को कहें। |
| notice.page_title.hi | {institution_name} की सूचना |
| notice.lang_label.hi | भाषा |
| notice.uploaded_line.hi | कॉलेज ने यह जानकारी {uploaded_date} को {id_label} {id_masked} के साथ अपलोड की। |
| provisional.label.hi | अस्थायी आईडी |
| notice.what_is_this_link.hi | यह क्या है? |
| notice.what_is_this.hi | Countersign से AICTE यह जाँचता है कि कॉलेज केवल उन्हीं विद्यार्थियों की जानकारी भेजें जिन्होंने सच में प्रवेश लिया है। कॉलेज का अपलोड एक दावा है, और आपका उत्तर उसके बारे में एक साक्ष्य है। आप DigiLocker से साइन इन करने के बाद उत्तर देते हैं, ताकि आपके लिए केवल आप ही उत्तर दे सकें। आपका उत्तर तारीख के साथ दर्ज होता है। |
| notice.sending.hi | भेजा जा रहा है |
| notice.no_confirm.hi | आप AICTE को बता रहे हैं कि आपने {institution_name} में कभी प्रवेश नहीं लिया। इससे एक प्राथमिकता विवाद खुलता है: कॉलेज दस्तावेज़ों के साथ जवाब दे सकता है, और एक अधिकारी निर्णय लेता है। क्या आप कुछ और बताना चाहेंगे? (वैकल्पिक) |
| notice.no_comment_label.hi | क्या आप कुछ और बताना चाहेंगे? |
| notice.no_comment_hint.hi | इसे केवल AICTE के अधिकारी पढ़ते हैं। आपका कॉलेज इसे नहीं देखता। |
| notice.no_submit.hi | भेजें |
| notice.no_cancel.hi | वापस जाएँ |
| notice.yes_next.hi | जब बाकी साक्ष्य भी आ जाएँगे, तो एक नामांकन अनुप्रमाणन, जिसे आप साझा कर सकते हैं, "My attestations" में दिखेगा। |
| notice.see_proofs.hi | मेरे अनुप्रमाणन देखें |
| notice.answered.hi | आपने {responded_date} को "{reply}" उत्तर दिया। |
| notice.reply.YES.hi | हाँ |
| notice.reply.NO.hi | नहीं |
| notice.change.hi | मेरा उत्तर बदलें |
| notice.change_window.hi | आप अपना उत्तर केवल एक बार, {change_until_date} तक, बदल सकते हैं। |
| notice.change_heading.hi | अपना उत्तर बदलें |
| notice.change_once.hi | आप अपना उत्तर केवल एक बार बदल सकते हैं। उसके बाद वह अंतिम होगा। |
| notice.current_answer.hi | आपका अभी का उत्तर |
| notice.change_submit.hi | नया उत्तर सहेजें |
| notice.changed_done.hi | आपका उत्तर अब "{reply}" है। इसे फिर से नहीं बदला जा सकता। |
| notice.change_used.hi | आपने {changed_date} को अपना उत्तर बदला था। आपका उत्तर "{reply}" अंतिम है। |
| notice.change_closed.hi | उत्तर बदलने के 7 दिन पूरे हो चुके हैं। अगर इसमें सुधार चाहिए, तो अपने Privacy पेज से अनुरोध करें। |
| notice.invalid.hi | यह लिंक मान्य नहीं है। जाँचें कि आपने संदेश का पूरा लिंक खोला है, या अपने कॉलेज से नई सूचना भेजने को कहें। |
| notice.rate_limited.hi | इस नेटवर्क से बहुत अधिक प्रयास हुए हैं। {seconds} सेकंड बाद फिर कोशिश करें। |
| consent.notice.hi | उत्तर देकर आप AICTE को इस नामांकन के साथ अपना उत्तर, तारीख और आपका DigiLocker साइन-इन दर्ज करने की अनुमति देते हैं। आपका उत्तर AICTE के अधिकारियों और {institution_name} को केवल "प्रवेश लिया" या "कभी प्रवेश नहीं लिया" के रूप में दिखता है, किसी और व्यक्तिगत जानकारी के बिना। अगर आप टिप्पणी लिखते हैं, तो उसे केवल AICTE के अधिकारी देखते हैं। |
| err.NETWORK.hi | Countersign से संपर्क नहीं हो सका। अपना इंटरनेट कनेक्शन जाँचें और फिर कोशिश करें। |
| err.INTERNAL.hi | हमारी ओर से कुछ गड़बड़ हुई। फिर कोशिश करें। |
| err.retry.hi | फिर कोशिश करें |

With Hindi on, every string on the notice page uses its `.hi` row, states and errors included; a string without one falls back to English. Institution and programme names print as sent. `{reply}` takes `notice.reply.*.hi`; `{id_label}` is "APAAR" or [provisional.label.hi]. Dates keep the `14 Jul 2026` form. "Privacy" and "My attestations" stay in English inside the Hindi strings because the student portal shows them in English.

Notices list (`/student/notices`)

| id | text |
|---|---|
| notices.heading | Notices |
| notices.lead | Messages asking you to confirm what a college told AICTE about you. |
| notices.col.sent | Sent |
| notices.col.from | From |
| notices.col.claim | What they said |
| notices.col.reply | Your reply |
| notices.claim | You joined {programme_short} ({academic_year}) |
| notices.channels | By {channel_words} |
| notices.reply.YES | Yes, on {responded_date} |
| notices.reply.NO | No, on {responded_date} |
| notices.reply.NONE | No reply yet |
| notices.reply.EXPIRED | No reply (expired) |
| notices.changed | Changed once, on {changed_date} |
| notices.reply_hint | To answer, open the link we sent you by email or in DigiLocker, then sign in with DigiLocker. It works until {expires_date}. |
| notices.denied_line | Your dispute is open. An AICTE officer is looking into it first. Nothing changes for you until they decide. |
| notices.consent_off | You turned off new notices on {withdrawn_date}. Notices already sent can still be answered. |

`{channel_words}` is "email", "DigiLocker" or "email and DigiLocker". The list cannot open a notice: only a hash of each link is stored (D23), so an unanswered notice shows `notices.reply_hint` instead of a link. `notices.denied_line` sits under a No while the dispute is undecided and is the only place a student learns that a case exists; once an officer decides, the matching `student.decision.*` line (§23) takes its place.

Student home (`/student`)

| id | text |
|---|---|
| student.check_student_sent | You can answer for yourself. We sent you a notice on {sent_date}; open it from your email or DigiLocker and sign in with DigiLocker to answer. |
| student.check_student_expired | Your notice expired without an answer. That does not count against you. |
| student.check_student_denied | You told us you never joined. An AICTE officer is looking into it first. Nothing changes for you until they decide. |
| student.consent_change | {tip}. To change it, go to your Privacy page. |

Under the record card the home page shows the status line `record_status.student.*` (§21), then one line by the enrolment's newest notice: none sent, [student.check_student_pending]; sent and unanswered, `student.check_student_sent`; expired, `student.check_student_expired`; answered No, `student.check_student_denied` until an officer decides, then `student.decision.*`; answered Yes, nothing. `student.consent_change` replaces the consent tooltip line the web kept outside the deck.

Wallet

| id | text |
|---|---|
| wallet.heading | My attestations |
| wallet.lead | Attestations you can show an employer or anyone else who needs to check your enrolment. You choose what they see. |
| wallet.kind.ENROLMENT | Enrolment attestation |
| wallet.kind.COMPLETION | Completion attestation |
| wallet.issued_by | Issued by Countersign for {institution_name} |
| wallet.issued_by_completion | Issued by Countersign for {university_name} |
| wallet.issued_on | Issued {issued_date} |
| wallet.valid_until | Valid until {expires_date} |
| wallet.status.active | Active |
| wallet.status.revoked | Revoked |
| wallet.status.expired | Expired |
| wallet.share | Share attestation |
| wallet.details | Show details |
| wallet.hide_details | Hide details |
| wallet.details_heading | What this attestation holds |
| wallet.proof_id | Attestation id {short_id} |
| wallet.not_issued_heading | No enrolment attestation yet |
| wallet.not_issued.AWAITING_EVIDENCE | Your attestation is issued once your record is Countersigned. Countersign is waiting for evidence from sources other than your college; you do not need to do anything. Answering your notice can help, because your answer is evidence independent of the college. |
| wallet.not_issued.UNDER_REVIEW | Your attestation is issued once an officer finishes reviewing your record and it is Countersigned. You do not need to do anything. |
| wallet.not_issued.DISPUTED | You told us you never joined {institution_name}, so no attestation is issued for this enrolment. |
| wallet.revoked_line | Revoked on {revoked_date}. Anyone who checks this attestation now sees Revoked. |
| wallet.revoked_reason.ENROLMENT_WITHDRAWN | Your college reported that you left this programme. |
| wallet.revoked_reason.ENROLMENT_TRANSFERRED | Your college reported that you moved to another institution. |
| wallet.revoked_reason.CLAIM_WITHDRAWN | An AICTE officer decided that the college's claim does not stand, so this attestation was revoked. |
| wallet.revoked_reason.STUDENT_DISPUTE | You told us you never joined, so this attestation was revoked while an officer reviews it. |
| wallet.revoked_reason.ADMIN | AICTE revoked this attestation. |
| wallet.revoked_help | If you think this is wrong, ask for a correction from your Privacy page. |
| wallet.expired_line | This attestation ended on {expires_date}. If you are still enrolled, an attestation for your next academic year is issued once that record is Countersigned. |
| wallet.share_heading | Share this attestation |
| wallet.fields_heading | Choose what to share |
| wallet.fields_hint | Institution and programme are always shared. Tick anything else the verifier needs. |
| wallet.always_shared | Always shared |
| wallet.field.name | Name |
| wallet.field.institution | Institution (always shared) |
| wallet.field.programme | Programme (always shared) |
| wallet.field.academic_year | Academic year |
| wallet.field.year_of_study | Year of study |
| wallet.field.dob | Date of birth |
| wallet.field.apaar_masked | APAAR (masked) |
| wallet.field.countersigned | Countersigned |
| wallet.field.countersigned_hint | That your record is Countersigned: its evidence is complete and nothing is unresolved, as of the date shown. |
| wallet.field.university | University |
| wallet.field.year_of_award | Year of completion |
| wallet.countersigned_value | Countersigned, as of {date} |
| wallet.consent_label | I agree |
| wallet.consent_required | Tick "I agree" to create the QR. |
| wallet.create_qr | Create QR |
| wallet.creating | Creating |
| wallet.shares | Shares {n} of {m} fields |
| wallet.shared_fields | Shared: {fields} |
| wallet.valid_for | Valid for 10 minutes |
| wallet.expires_in | Expires in {mm}:{ss} |
| wallet.expires_in_sr | The QR expires in {minutes} minutes. |
| wallet.expired_share | This QR has expired. Create a new one if you still need to share. |
| wallet.new_qr | Create a new QR |
| wallet.qr_alt | QR code for your attestation. The same code is written under it. |
| wallet.code_label | Code |
| wallet.code_hint | The verifier can type this code at {verify_url} instead of scanning. |
| wallet.copy_code | Copy code |
| wallet.code_copied | Code copied |
| wallet.copy_link | Copy link |
| wallet.copied | Link copied |
| wallet.done | Done |
| wallet.history_heading | Sharing history |
| wallet.history.created | {date}, {time}: QR created, shares {n} of {m} fields |
| wallet.history_item | Shared with a verifier at {time} |
| wallet.history_item_date | Shared with a verifier on {date} at {time} |
| wallet.history_item_more | Checked {n} times, last at {time} |
| wallet.history.unused | Not checked by anyone before it expired |
| wallet.history.stopped | Stopped on {date}, when you withdrew consent to share |
| wallet.history_empty | You have not shared this attestation yet. |
| wallet.history_note | AICTE records when your attestation is checked, but not who checked it. |
| student.heading | My enrolment |
| student.card_lead | {institution_name} says you joined {programme_name} |
| student.check_student_pending | You can answer for yourself. AICTE sends you a notice by email or DigiLocker, and you answer after signing in with DigiLocker. |
| privacy.student_line | Only you can see your email and mobile here. Officers see masked ids only. |
| privacy.how_link | How my data is used |

Share sheet fields (D26): an enrolment attestation lists 8 fields. Institution and programme come first, ticked and locked; then name, academic year, year of study, date of birth, APAAR (masked) and countersigned, all unticked to start. `{m}` in `wallet.shares` is the response's `total` (8 for an enrolment attestation) and `{n}` counts the ticked fields, locked ones included, so the fewest a share can show is "Shares 2 of 8 fields". A completion attestation lists the fields its `disclosable` claims name, using the `wallet.field.*` words. Each row shows the value that would be shared; the countersigned value is `wallet.countersigned_value` with the date the record became Countersigned ("Countersigned, as of 28 Oct 2026"). It never lists rows or a count.

The code under the QR is 6 groups of 4 letters and digits, printed as sent (`K7PQ-3M2X-9ZAB-4TNE-W8RC-6HDF`). `{verify_url}` is the host and path of the verify page without the code ("localhost:3000/verify"). The countdown counts down from `expires_at`; `wallet.expires_in_sr` is announced at 5 minutes and at 1 minute only. In the history, a share's first row is `wallet.history.created`; each check of it prints `wallet.history_item` (D27), with `wallet.history_item_date` when it was not today, or `wallet.history_item_more` once `verify_count` is above 1; a share that expired unchecked prints `wallet.history.unused`.

No attestation yet: for an active enrolment with no enrolment attestation, the card reads `wallet.not_issued_heading` and one line by the record's status: Awaiting evidence, `wallet.not_issued.AWAITING_EVIDENCE`; Under review, `wallet.not_issued.UNDER_REVIEW`; Disputed, `wallet.not_issued.DISPUTED`. It never names a case or a contradicted row. A revoked attestation prints `wallet.revoked_line`, then the `wallet.revoked_reason.*` sentence for its `revoked_reason_code` (a code the deck does not list prints `wallet.revoked_reason.ADMIN`), then `wallet.revoked_help`; it has no Share button. Reason codes `CLAIM_WITHDRAWN` (an officer's Withdraw claim decision, D43) and `STUDENT_DISPUTE` (the record became Disputed, R6) are pending contract confirmation; `FLAG_CONFIRMED` is retired with the Confirm action.

## 9. Consent texts (DPDP)

Each text is stored verbatim in `consents.notice_text` when the consent is recorded.

| id | purpose | text |
|---|---|---|
| consent.apaar_link | APAAR_LINK | I allow AICTE to use my APAAR id to check that my enrolment at {institution_name} is genuine. AICTE will look up my id with the APAAR registry and the Academic Bank of Credits, and I can confirm or dispute the enrolment myself by signing in with DigiLocker. Only the last four digits of my id are shown to officers. To unlink my APAAR later, I can ask from my Privacy page; my college then uploads my enrolment again without it. Evidence already gathered stays on record, and my admission is not affected. |
| consent.notice | NOTICE | By answering, you let AICTE record your answer, the date and your DigiLocker sign-in against this enrolment. Your answer is shown to AICTE officers and to {institution_name} as "Joined" or "Never joined", with no other personal detail. If you add a comment, only AICTE officers see it. |
| consent.credential_share | CREDENTIAL_SHARE | I am sharing an attestation that shows only the fields I ticked. Whoever scans it sees those fields, who issued the attestation and when, and nothing else. The share works for 10 minutes. AICTE records when it is created and when it is checked, but not who checks it. |
| consent.withdraw.NOTICE | NOTICE | Stop new notices? You will get no new notices about your enrolments. Notices already sent can still be answered, and replies you gave stay on record. |
| consent.withdraw.CREDENTIAL_SHARE | CREDENTIAL_SHARE | Stop sharing? Every QR or link you created that still works stops working now. Your attestations stay in your wallet, and sharing again asks for your consent again. |
| consent.unlink_apaar | APAAR_LINK | Unlinking your APAAR is a correction request, because your college must upload your enrolment again without it. Your admission is not affected, and checks already made stay on record. |
| consent.upload_declaration | APAAR_LINK via college | (identical to upload.declaration) |

`consent.withdraw.*` and `consent.unlink_apaar` are confirmations on the Privacy page, not stored texts. Only NOTICE and CREDENTIAL_SHARE can be withdrawn there (`POST /students/me/consents/{purpose}/withdraw`, D30). APAAR_LINK has no Withdraw button: `consent.unlink_apaar` explains why and offers [privacy.unlink_apaar], which opens a Correction request with [privacy.request.unlink_prefill]. Each stored text is kept with its `notice_version`; the Privacy page shows the exact text the student agreed to, not today's version. The new wording of `consent.apaar_link`, `consent.notice` and `consent.credential_share` is text version 2; consents already given keep version 1.

## 10. Verifier

Public pages, no sign-in, rate limited (D27, D32). They never offer search and never show a field the student did not share.

Entry page (`/verify`)

| id | text |
|---|---|
| verify.bar | Verify an attestation |
| verify.heading | Verify an enrolment or completion attestation |
| verify.lead | Scan the QR on the document, or type the code printed under it. |
| verify.scan | Scan with camera |
| verify.scan_stop | Stop camera |
| verify.scan_hint | Hold the QR inside the frame. |
| verify.scan_unsupported | This browser cannot scan QR codes. Type the code instead. |
| verify.camera_denied | The camera is not allowed for this page. Type the code instead, or allow the camera in your browser settings. |
| verify.code_label | Code |
| verify.placeholder | e.g. K7PQ-3M2X-9ZAB-4TNE-W8RC-6HDF |
| verify.code_hint | 24 letters and digits. Dashes and spaces are optional. |
| verify.code_hint_certificate | For a printed certificate, type the 8-character attestation id under its QR. |
| verify.code_format | A code has 24 letters and digits, in 6 groups of 4. Check it and try again. |
| verify.check | Check |
| verify.checking | Checking |
| verify.paste_link | Have the attestation text instead of a code? |
| verify.paste_label | Attestation text |
| verify.paste_hint | Paste the full text you were given. It is long and starts with eyJ. |
| verify.paste_check | Check attestation text |
| verify.what | What you will see: whether the attestation is valid, who issued it, and only the fields the student chose to share. Never a full APAAR number, and no search: only an attestation a student shares can be checked. |
| verify.about_link | What is Countersign? |
| verify.about | Countersign is AICTE's way of checking that every enrolment a college reports is backed by evidence: the APAAR registry, the AICTE approval, the state admission authority's joining record, the Academic Bank of Credits and the student's own answer after signing in with DigiLocker. An enrolment attestation says the record is Countersigned, and shows only the fields the student chose to share. |
| verify.rate_limited | Too many checks from this network in a minute. Try again in {seconds} s. |

Result page (`/verify/[code]`, and pasted attestation text)

| id | text |
|---|---|
| verify.result_title | Attestation check |
| verify.state.VALID | Valid |
| verify.state.REVOKED | Revoked |
| verify.state.EXPIRED | Expired |
| verify.state.INVALID | Not valid |
| verify.kind.ENROLMENT | Enrolment attestation |
| verify.kind.COMPLETION | Completion attestation |
| verify.valid | Valid attestation |
| verify.valid_sub | Issued by Countersign for {institution_name} on {issued_date}. |
| verify.signature | Signature checked against Countersign's published keys. |
| verify.method_lookup | Checked against AICTE's register of issued completion attestations. |
| verify.revocation | Revocation checked just now. |
| verify.revocation_at | Revocation checked at {time}. |
| verify.holder_bound | The student shared this attestation for this check, from their own wallet. |
| verify.pasted_note | Checked from pasted text, so Countersign cannot tell whether it was made for you. Ask the student for a fresh code if that matters. |
| verify.shared_heading | Shared by the student |
| verify.not_shared | Nothing else is shown. The student chose what to share. |
| verify.revoked | This attestation has been revoked. |
| verify.revoked_sub | AICTE revoked it, for example because the record was withdrawn. It no longer confirms anything. Ask the student about it. |
| verify.expired | This attestation has expired. |
| verify.expired_sub | A shared code works for 10 minutes, and every attestation has an end date. Ask the student for a new one. |
| verify.invalid | This is not a valid Countersign attestation. |
| verify.invalid_sub | The code may be mistyped, or the attestation was changed after it was issued. Check the code and try again; if it still fails, do not rely on it. |
| verify.check_another | Check another attestation |

Completion attestation QR result (`/verify/d/[jws]`, the QR printed on a university's certificate)

| id | text |
|---|---|
| verify.completion_valid | Valid completion attestation |
| verify.completion_sub | Signed by Countersign for {university_name}. This is not a degree; the degree is the certificate it is printed on. |
| verify.completion_heading | On the attestation |
| verify.completion_printed | Printed attestations are not tied to a phone. Compare the name with the person's photo ID. |
| verify.completion_wallet | This QR carries a short signed summary of the completion attestation. The graduate's wallet holds the full attestation. |
| verify.completion_revoked_sub | AICTE revoked this completion attestation. It no longer confirms anything. Ask the graduate about it. |

Field labels (the api sends `label` with every disclosed field; these rows mirror them)

| id | text |
|---|---|
| verify.field.name | Name |
| verify.field.institution | Institution |
| verify.field.programme | Programme |
| verify.field.academic_year | Academic year |
| verify.field.year_of_study | Year of study |
| verify.field.dob | Date of birth |
| verify.field.apaar_masked | APAAR (masked) |
| verify.field.countersigned | Countersigned |
| verify.field.university | University |
| verify.field.year_of_award | Year of completion |
| verify.field.attestation_id | Attestation id |

Result states (D27): the heading, a badge with icon and `verify.state.*` word, and the sub line. VALID shows `verify.kind.*`, `verify.valid_sub`, `verify.signature`, `verify.revocation` (or `verify.revocation_at` when `status_checked_at` is more than a minute old), `verify.holder_bound` when `holder_bound` is true, then `verify.shared_heading` with the `disclosed` fields as label and value pairs in the order sent, then `verify.not_shared`. REVOKED, EXPIRED and INVALID show the heading, the sub line and `verify.check_another`, and no fields. Pasted attestation text (`POST /verify`) adds `verify.pasted_note` to a VALID result, because its share code is reported, not enforced. A completion attestation QR shows `verify.completion_valid`, `verify.completion_sub`, `verify.signature`, `verify.revocation`, `verify.completion_heading` with its fields, `verify.completion_printed` and `verify.completion_wallet`; revoked uses `verify.revoked` with `verify.completion_revoked_sub`. A typed attestation id (`method` `register_lookup`) shows `verify.method_lookup` in place of `verify.signature`. Field labels print the api's `label` as sent, so the countersigned field reads "Countersigned" with its date here and in the wallet's claim list; the share sheet uses `wallet.field.*`. The entry page prints `verify.code_hint` and `verify.code_hint_certificate` on one line under the code field. The verifier never says why an attestation was revoked. A 404 `PRESENTATION_NOT_FOUND` shows [err.PRESENTATION_NOT_FOUND]; a 429 shows `verify.rate_limited` with a countdown. Values print as sent: the APAAR is always `XXXX XXXX 4417`, never more.

## 11. University: certificate integration

DECISIONS D44. Countersign does not issue degrees. The university awards the degree and prints its own certificate; Countersign supplies the masked APAAR and a QR to the graduate's completion attestation for it to print. Routes `/university/certificates` and `/university/certificates/[enrolmentId]/print`, from `GET /university/graduates?q&page`, `POST /university/certificates/{enrolment_id}/issue`, `GET /university/certificates/{enrolment_id}` and `GET /university/certificates/{enrolment_id}/block.pdf` (the D28 endpoints renamed; pending contract confirmation of the paths).

| id | text |
|---|---|
| university.heading | Affiliated institutions |
| cert.heading | Certificate integration |
| cert.lead | Countersign does not issue degrees. Your university awards the degree and prints its own certificate. Countersign gives you two things to print on it: the graduate's masked APAAR, and a QR to their completion attestation. |
| cert.how_heading | How it works |
| cert.how_issue | Countersign issues a completion attestation for a graduate of an affiliated college whose enrolment record is Countersigned. |
| cert.how_print | Your certificate system fetches the masked APAAR and the QR through the API, or you print them from here as a block for the certificate. |
| cert.how_verify | Anyone who scans the QR sees whether the attestation is valid, and the fields on it. |
| cert.api_heading | For your certificate system |
| cert.api_line | GET {api_url}/university/certificates/{enrolment_id} returns the masked APAAR, the attestation id and the QR as SVG for one graduate. |
| cert.search | Search by name or the last four digits of APAAR |
| cert.count | {total} graduates |
| cert.col.graduate | Graduate |
| cert.col.year | Year of completion |
| cert.col.attestation | Completion attestation |
| cert.status.none | Not issued |
| cert.status.active | Issued {issued_date} |
| cert.status.revoked | Revoked |
| cert.status.not_eligible | Record not Countersigned |
| cert.not_eligible_tip | A completion attestation is issued only when the graduate's enrolment record is Countersigned. This record reads {status_word}. |
| cert.issue | Issue completion attestation |
| cert.issue_heading | Issue a completion attestation for {student_name}? |
| cert.issue_body | Countersign signs an attestation that {student_name} completed {programme_name} ({year}) at {institution_name}, and puts it in the graduate's wallet. It is not a degree: your certificate remains the degree. |
| cert.issue_note | The graduate can see this attestation in their wallet and choose what they share from it. |
| cert.issue_revocation_note | If the record is withdrawn later, AICTE revokes the attestation and anyone who scans the printed QR sees Revoked. |
| cert.issue_confirm | Issue attestation |
| cert.issue_cancel | Cancel |
| cert.issuing | Issuing |
| cert.issued_toast | Completion attestation issued. It is in {student_name}'s wallet. |
| cert.print_block | Print certificate block |
| cert.pdf | Download PDF |
| cert.pdf_note | The block as a PDF, to place on your certificate template. |
| cert.provisional_note | This graduate has no APAAR, so the block prints the provisional ID. |
| cert.print_title | Certificate block, {student_name} |
| cert.print_hint | Print on A4, portrait, or place the PDF on your certificate. Navigation and colours are left out of the printout. |
| cert.print | Print |
| cert.print_back | Back to graduates |
| cert.print.lead | For the certificate awarded by {university_name} to |
| cert.print.name | Name |
| cert.print.programme | Programme |
| cert.print.institution | Institution |
| cert.print.year | Year of completion |
| cert.print.apaar | APAAR |
| cert.print.provisional | Provisional ID |
| cert.apaar_line | APAAR {apaar_masked} |
| cert.scan_line | Scan to verify at {verify_url} |
| cert.print.attestation_id | Attestation id {short_id} |
| cert.qr_alt | QR code to verify this completion attestation. The attestation id is written under it. |
| cert.print.issued | Completion attestation issued {issued_date} |
| cert.print.signed | Signed by Countersign for {university_name}. This block is not a degree, and a changed block does not verify. |

`/university/certificates` lists the graduates of the university's affiliates: Graduate (name, linked to nothing), [col.apaar] (masked APAAR or provisional ID), [col.institution], [col.programme], `cert.col.year`, `cert.col.attestation` (`cert.status.*` word with an icon; `cert.status.not_eligible` carries `cert.not_eligible_tip`). Row action: `cert.issue` when the record is Countersigned and there is no active completion attestation (also after a revoked one); `cert.print_block` and `cert.pdf` when there is one; nothing when the record is not Countersigned. The issue sheet shows `cert.issue_heading`, `cert.issue_body`, `cert.issue_note`, `cert.issue_revocation_note` (and `cert.provisional_note` for a graduate without APAAR), then `cert.issue_confirm` and `cert.issue_cancel`. 409 `CREDENTIAL_NOT_ELIGIBLE` shows [err.CREDENTIAL_NOT_ELIGIBLE]; 409 `CREDENTIAL_REVOKED` on print shows [err.CREDENTIAL_REVOKED]. The how-it-works panel (`cert.how_heading` with its three lines and `cert.api_line` under `cert.api_heading`) sits above the table and can be collapsed.

Print view text under the QR: `cert.print.attestation_id` and `cert.scan_line`, with `{verify_url}` the verify page's host and path ("localhost:3000/verify"). The QR's own link (`/verify/d/{jws}`) is never printed as text; the QR's text alternative is `cert.qr_alt`. The block never uses the word "degree" except to say it is not one.

## 12. Admin and system

| id | text |
|---|---|
| admin.heading | System |
| admin.sources | Government sources |
| admin.adapter | adapter: {adapter} |
| admin.ping | Ping |
| admin.pinging | Pinging |
| admin.audit | Audit chain |
| admin.verify | Verify chain |
| admin.verify_idle | Not checked yet. Press Verify chain. |
| admin.chain_ok | {length} entries · Chain intact · Checked {time} |
| admin.chain_broken | {length} entries · Chain broken at entry {seq} · Checked {time} |
| admin.health | Service health |
| admin.health_line | API {status} · Database {db} · Redis {redis} · version {version} |
| admin.demo | Demo controls |
| admin.demo_tag | Demo |
| admin.chaos | Chaos (mockgov) |
| admin.chaos_source | Source |
| admin.chaos_latency | Latency (ms) |
| admin.chaos_fail | Fail rate |
| admin.chaos_down | Down |
| admin.chaos_apply | Apply |
| admin.chaos_reset | Reset chaos |
| admin.chaos_applied | Chaos applied to {source}: {summary} |
| admin.chaos_cli | Chaos controls are not proxied yet. Use curl localhost:8001/admin/chaos for now. |
| admin.reset | Reset demo data |
| admin.reset_note | Drops and re-seeds the demo database. About 30 seconds. |
| admin.reset_confirm | Reset the demo data? Every upload, case, decision and answer since the last seed is removed. Seeded users and passwords stay the same. |
| admin.reset_running | Resetting |
| admin.reset_done | Demo data reset. Audit chain starts fresh. |
| admin.reset_cli | Reset is not available from the browser yet. Run make demo-reset. |
| audit.heading | Audit |
| audit.lead | Every change, and every view of student records, in order. Each entry carries the hash of the one before, so a changed entry shows up when the chain is verified. |
| audit.col.seq | Entry |
| audit.col.at | Time |
| audit.col.actor | Actor |
| audit.col.action | Action |
| audit.col.entity | Entity |
| audit.col.entity_id | Entity id |
| audit.col.hash | Hash |
| audit.filter.entity_type | Entity |
| audit.filter.action | Action |
| audit.filter.actor | Actor |
| audit.filter.entity_id | Entity id |
| audit.filter.seq_from | From entry |
| audit.filter.all | All |
| audit.count | {total} entries |
| audit.actor_system | System |
| audit.via.notice_link | Public, notice link |
| audit.via.verifier | Public, verifier |
| audit.via.demo_seed | Demo seed |
| audit.hash_tip | Full hash {hash} |
| audit.verify | Verify chain |
| audit.verifying | Verifying |
| audit.chain_ok | Chain intact, {n} entries |
| audit.chain_broken | Chain broken at entry {seq} |
| audit.chain_broken_detail | Entry {seq} no longer matches its recorded hash, so it was changed after it was written. Entries before it are intact. |
| audit.chain_checked | Checked {time} |
| audit.show_entry | Show entry {seq} |
| audit.break_marker | Chain breaks here |
| audit.read_note | Views of student records are logged as Viewed entries. |

`/admin/audit` (D29) reads `GET /admin/audit` with `entity_type`, `action`, `actor_id`, `entity_id`, `seq_from` and `page`, and `GET /admin/audit/verify`. Actor prints `actor_email`; a null actor prints `audit.actor_system`, or the `audit.via.*` words when the entry records how a public page reached it. Action prints `audit_action.*`. Entity id and Hash print their first 8 characters in monospace, the full value on focus and hover (`audit.hash_tip`). `{n}` in `audit.chain_ok` is `length` in `en-IN` grouping ("Chain intact, 1,842 entries"); `{seq}` in `audit.chain_broken` is `first_broken_seq`. `admin.chain_ok` and `admin.chain_broken` stay on `/admin/system`.

| id | text |
|---|---|
| psi.heading | Private matching |
| psi.compute | Compute overlap |
| psi.result | Overlap: {n} records. Neither side learned the other's members. |
| psi.explain | Both sides encrypt their lists, swap the encrypted versions and count the matches. The lists themselves never leave their owner. |

Data requests queue (`/admin/data-requests`, `GET /data-requests` and `POST /data-requests/{id}/resolve {status, response}`, AICTE officer only, D30)

| id | text |
|---|---|
| admin.requests.heading | Data requests |
| admin.requests.lead | Students' requests to correct or erase their data. Each one gets a written reply the student reads on their Privacy page. |
| admin.requests.count | {total} open requests |
| admin.requests.count_any | {total} requests |
| admin.requests.filter.status | Status |
| admin.requests.filter.kind | Request |
| admin.requests.col.received | Received |
| admin.requests.col.kind | Request |
| admin.requests.col.student | Student |
| admin.requests.col.details | Details |
| admin.requests.col.status | Status |
| admin.requests.col.resolved | Resolved |
| admin.requests.resolve | Resolve |
| admin.requests.resolve_for | Resolve the request from {student_name} |
| admin.requests.resolve_heading | Resolve this request |
| admin.requests.request_line | {student_name} asked for {kind_word} on {date}: |
| admin.requests.outcome | Outcome |
| admin.requests.outcome.DONE | Done |
| admin.requests.outcome.REJECTED | Decline |
| admin.requests.response_label | Reply to the student |
| admin.requests.response_hint | The student reads this on their Privacy page. Say what was done, or why not. |
| admin.requests.response_required | Write a reply before you resolve the request. |
| admin.requests.correction_hint | A correction usually needs the college to upload the student's row again. Tell the student what will change and who does it. |
| admin.requests.unlink_hint | To unlink an APAAR, the college uploads the row again with consent Refused. Admission is not affected. |
| admin.requests.erasure_retention | Enrolment records, their evidence, cases and the audit log are kept for the period the law requires, so they cannot be erased on request. Contact details and anything not needed for that record can be removed. |
| admin.requests.erasure_reply | We cannot erase your enrolment record, its evidence or its history, because AICTE must keep them for the period the law requires. Everything shown to officers stays masked, and you can see who views your record on your Privacy page. We have removed: |
| admin.requests.submit | Send reply |
| admin.requests.sending | Sending |
| admin.requests.resolved_toast | Request resolved. The student can see your reply. |
| admin.requests.empty | No open data requests. |
| admin.requests.empty_filtered | No requests match these filters. |

The queue lists Correction and Erasure requests (an Access request is fulfilled at once and never waits here), Open first, oldest first. The Student cell is the name with the masked APAAR or provisional id under it; Details prints the student's text verbatim, wrapped. `{kind_word}` is `data_request_kind.*` in lower case. The count line is `admin.requests.count` with the status filter on Open and `admin.requests.count_any` otherwise. Each row's Resolve button has the accessible name `admin.requests.resolve_for`. The resolve sheet shows `admin.requests.correction_hint` for a correction (plus `admin.requests.unlink_hint` when the text asks to unlink an APAAR), and for an erasure shows `admin.requests.erasure_retention` and prefills the reply with `admin.requests.erasure_reply`, which the officer completes. Outcome words map to `status`: Done is `DONE`, Decline is `REJECTED`; the student then sees `data_request_status.*`.

## 13. Errors (by API error code)

| id | text |
|---|---|
| err.UNAUTHENTICATED | Your session has ended. Sign in again. |
| err.INVALID_CREDENTIALS | Email or password is incorrect. |
| err.FORBIDDEN | This page is for {required_roles_words}. You are signed in as {role_word}. |
| err.FORBIDDEN_redirect | That page is for {required_roles_words}. You are signed in as {role_word}. |
| err.NOT_FOUND_institution | This institution is not in your scope or does not exist. |
| err.NOT_FOUND_upload | This upload is not in your scope or does not exist. |
| err.NOT_FOUND_enrolment | This record is not in your scope or does not exist. |
| err.NOT_FOUND_flag | This case is not in your scope or does not exist. |
| err.NOT_FOUND_generic | We could not find that. |
| err.VALIDATION_ERROR | Check the highlighted fields. |
| err.RATE_LIMITED | Too many attempts. Try again in {seconds} s. |
| err.SOURCE_UNAVAILABLE | {source_name} did not respond. The row shows Source unavailable until a recheck or the next upload. |
| err.FILE_TOO_LARGE | The file is larger than 20 MB. Split it by programme and upload each part. |
| err.TOO_MANY_ROWS | The file has more than 50,000 rows. Split it and upload each part. |
| err.UNSUPPORTED_FILE_TYPE | Only .csv and .xlsx files can be uploaded. |
| err.UPLOAD_HEADER_INVALID | The file is missing required columns: {columns}. |
| err.UPLOAD_HEADER_DUPLICATE | The column {column} appears more than once. |
| err.UPLOAD_EMPTY | The file has a header but no rows. |
| err.UPLOAD_IN_PROGRESS | An upload for this college and year is still being processed. |
| err.NOTICE_NOT_FOUND | This link is not valid. Check that you opened the whole link from your message, or ask your college to send a new notice. |
| err.NOTICE_EXPIRED | This link has expired. No reply was recorded, and that does not count against you. To reply now, ask your college or AICTE to send a new notice. |
| err.NOTICE_ALREADY_CHANGED | You have already changed your answer once, so it cannot be changed again. |
| err.RESEND_LIMIT | This enrolment has already had 3 notices resent in this academic year, which is the limit. |
| err.NOTICE_LIVE | The student still has a notice they can answer. You can resend once it expires or is not delivered. |
| err.CREDENTIAL_NOT_ELIGIBLE | An attestation is issued only for a Countersigned record. Refresh the page to see its current status. |
| err.CREDENTIAL_REVOKED | This attestation has been revoked, so it cannot be shared or printed. |
| err.PRESENTATION_NOT_FOUND | No attestation matches this code. Check each group of four and try again. |
| err.FLAG_TRANSITION_INVALID | This action is not possible from the case's current status. The page now shows the latest status. |
| err.ATTACHMENT_TOO_LARGE | A file is larger than 5 MB. Attach a smaller copy, for example a scan at a lower resolution. |
| err.ATTACHMENT_TYPE | Only PDF, PNG and JPEG files can be attached. |
| err.SIGNIN_REQUIRED | Sign in with DigiLocker to answer this notice. |
| err.DIGILOCKER_CANCELLED | You left DigiLocker before signing in. Nothing was recorded. |
| err.DIGILOCKER_FAILED | DigiLocker sign-in did not finish. Nothing was recorded. Try again. |
| err.DIGILOCKER_STATE_INVALID | This sign-in has expired or was started in another browser. Start again from the notice link. |
| err.NOTICE_IDENTITY_MISMATCH | This notice is for someone else. Nothing was recorded. |
| err.CLAIM_NO_MATCH | We could not match this provisional ID to the name and date of birth on your DigiLocker. Check the ID, or ask your college to check the name and date of birth they recorded. |
| err.CLAIM_ALREADY_CLAIMED | This record is already claimed through another DigiLocker sign-in. If that was not you, ask for a correction from your Privacy page. |
| err.CLAIM_NOT_NEEDED | This record has an APAAR, so it links to DigiLocker on its own. Sign in with the DigiLocker account that holds that APAAR. |
| err.REASON_REQUIRED | Choose a reason and write a note before you decide. |
| err.CORRECTION_EMPTY | Change at least one field, or choose another decision. |
| err.CORRECTION_INVALID | {field_word}: {message} |
| err.WITHDRAW_NONE_SELECTED | Select at least one record to withdraw. |
| err.WITHDRAW_NOT_NAMED | {n} of the selected records are not named by this case. The page now shows the records it names; select again. |
| err.UPHOLD_NEEDS_VERSION | This case is about admissions beyond the approval. It can be upheld only when an approval version covers them. |
| err.APPROVAL_BELOW_ASSIGNED | This version lowers the intake to {intake}, below the {assigned} seats already assigned. Release seats first, or record a version that keeps them. |
| err.MAPPING_INCOMPLETE | Map every required column before you continue: {columns}. |
| err.MAPPING_DUPLICATE | Each Countersign column can be chosen once. {column} is chosen more than once. |
| err.SIGNAL_ALREADY_HANDLED | Another officer already acted on this signal. The page now shows its current status. |
| err.NOT_FOUND_signal | This signal is not in your scope or does not exist. |
| err.REPORT_FAILED | The report could not be prepared. Try again; if it fails again, download the CSV instead. |
| err.INTERNAL | Something went wrong on our side. Try again. |
| err.NETWORK | Could not reach Countersign. Check your connection and try again. |
| err.ref | Ref: {code} |
| err.retry | Try again |
| err.back_overview | Back to overview |
| err.go_home | Go to my overview |
| err.tile_failed | Could not load |
| err.signin | Sign in |

`err.UPLOAD_HEADER_INVALID` takes `{columns}` from `details.missing_columns` joined with ", "; `err.UPLOAD_HEADER_DUPLICATE` is shown once per entry in `details.duplicate_columns`; both are followed by [upload.header_help]. `err.UPLOAD_IN_PROGRESS` is followed by a link [upload.in_progress_link] to `details.batch_id`. A 422 `VALIDATION_ERROR` on `declaration` or `academic_year` shows the api's field message under that field.

The codes from `err.SIGNIN_REQUIRED` to `err.REPORT_FAILED` are pending contract confirmation. `err.CLAIM_NO_MATCH` is one answer for an unknown ID and a name or date of birth that does not match, so nobody can learn which provisional IDs exist; `err.CLAIM_ALREADY_CLAIMED` and `err.CLAIM_NOT_NEEDED` are returned only after the name and date of birth match. `err.CORRECTION_INVALID` prints the api's field message verbatim.

Hindi for the student's sign-in, notice and claim errors (for review by a native speaker before the panel)

| id | text |
|---|---|
| err.SIGNIN_REQUIRED.hi | इस सूचना का उत्तर देने के लिए DigiLocker से साइन इन करें। |
| err.DIGILOCKER_CANCELLED.hi | आपने साइन इन पूरा होने से पहले DigiLocker छोड़ दिया। कुछ भी दर्ज नहीं हुआ। |
| err.DIGILOCKER_FAILED.hi | DigiLocker से साइन इन पूरा नहीं हुआ। कुछ भी दर्ज नहीं हुआ। फिर कोशिश करें। |
| err.DIGILOCKER_STATE_INVALID.hi | यह साइन इन समाप्त हो गया है या किसी दूसरे ब्राउज़र में शुरू हुआ था। सूचना के लिंक से फिर से शुरू करें। |
| err.NOTICE_IDENTITY_MISMATCH.hi | यह सूचना किसी और के लिए है। कुछ भी दर्ज नहीं हुआ। |
| err.CLAIM_NO_MATCH.hi | हम इस अस्थायी आईडी को आपके DigiLocker के नाम और जन्म तिथि से नहीं मिला सके। आईडी जाँचें, या अपने कॉलेज से उनके दर्ज किए नाम और जन्म तिथि जाँचने को कहें। |
| err.CLAIM_ALREADY_CLAIMED.hi | इस रिकॉर्ड पर किसी दूसरे DigiLocker साइन-इन से पहले ही दावा किया जा चुका है। अगर वह आप नहीं थे, तो अपने Privacy पेज से सुधार का अनुरोध करें। |
| err.CLAIM_NOT_NEEDED.hi | इस रिकॉर्ड में APAAR है, इसलिए यह अपने आप DigiLocker से जुड़ जाता है। उस DigiLocker खाते से साइन इन करें जिसमें वह APAAR है। |

`required_roles_words` maps `AICTE_ADMIN` -> "AICTE officers", `RO_OFFICER` -> "regional officers", `INSTITUTION` -> "registrars", `STUDENT` -> "students", `UNIVERSITY` -> "university controllers"; join with " and ".

## 14. Empty states

| id | text |
|---|---|
| empty.institutions_filtered | No institutions match these filters. |
| empty.institutions_clear | Clear filters |
| empty.by_state | No data for this academic year yet. |
| empty.programmes | No approved programmes for this academic year. |
| empty.programmes_college | No approved programmes for your college in this academic year. Contact your regional office if this is wrong. |
| empty.enrolments | No enrolments uploaded yet. |
| empty.enrolments_search | No enrolment matches "{q}". Search by name or the last four digits of APAAR. |
| empty.flags_institution | No open cases. Cases appear here after the first upload is checked. |
| empty.flags_college | No cases. Cases appear after your upload is checked. Nothing is rejected automatically; an officer decides every case. |
| empty.cases | No open cases. Cases appear here after uploads are checked. |
| empty.cases_filtered | No cases match these filters. |
| empty.clear_filters | Clear filters |
| empty.flags_by_type | No open cases for {academic_year}. |
| empty.flags_enrolment | No cases name this record. |
| empty.related | No related enrolments you can see. |
| empty.checks | No evidence yet. Evidence is gathered when the upload is processed. |
| empty.enrolments_filtered | No records match these filters. |
| empty.seats | No seats in this pool. |
| empty.uploads | No uploads yet. |
| empty.notices_student | You have no notices yet. When a college reports an enrolment in your name, AICTE sends you a notice by email or DigiLocker. |
| empty.credentials_student | No attestations yet. An enrolment attestation appears here once your record is Countersigned. |
| empty.enrolments_student | No college has reported an enrolment for you. |
| empty.affiliates | No institutions are affiliated to your university in this academic year. |
| empty.audit | No audit entries. |
| empty.audit_filtered | No entries match these filters. |
| empty.graduates | No graduates found for your affiliated institutions. |
| empty.graduates_search | No graduate matches "{q}". Search by name or the last four digits of APAAR. |
| empty.status_filtered | No records with this status. |
| empty.history | No changes since the record was created. |

## 15. Evidence rows: findings, source lines and detail sentences

Reference copy of what the engines write into each row (D34, D38, D39, R4; API Addendum 4, pending): `finding` (a short phrase printed after the state word, or nothing), `source_line` (the "Source and date" cell) and `detail.summary` (one sentence, shown behind [record.details_show]). The web prints all three verbatim and never rebuilds them. Placeholders: `{source_name}` from `source.*`, `{route_word}` from `route.*`, `{seat_type_word}` from `seat_type.*`, `{flag_name}` from `flag.<TYPE>.name`, `{cohort_start}` the start year of the cohort (`2026`), `{cohort_year}` the approval year (`2026-27`), `{date}` the row's `observed_at` (`12 Aug` in the current year, else `12 Aug 2025`).

Source lines (`source_line`; the words follow the deck, whatever `supplied_by` stores)

| id | text |
|---|---|
| source_line.APAAR | APAAR verification · {date} |
| source_line.SEAT_LEDGER | AICTE approval v{version}, {cohort_year} (Seat Ledger, derived) |
| source_line.ADMISSION_AUTHORITY | State admission authority · {date} |
| source_line.ABC | ABC, issued by {issuer_name} · {date} |
| source_line.ABC_self | ABC, issued by {institution_name} itself · {date} |
| source_line.STUDENT_DIGILOCKER | Student sign-in via DigiLocker · {date} |
| source_line.SII | Study in India · {date} |
| source_line.COLLEGE_UPLOAD | College upload · {date} |
| source_line.unavailable | {source_name} did not respond · {date} |
| source_line.not_due.STUDYING | First semester not complete |
| source_line.not_due.STUDYING_lateral | Lateral entry; first semester here not complete |
| source_line.not_due.ADMISSION | Published by {deadline_date} |
| source_line.na.IDENTITY | APAAR not linked; alternative route not used yet |
| source_line.na.STUDYING | APAAR not linked; ABC cannot be checked |
| source_line.na.STUDYING_abc | ABC has no record of this APAAR |
| source_line.STUDENT.not_sent | No notice sent yet |
| source_line.STUDENT.sent | Notice sent {sent_date} |
| source_line.STUDENT.expired | Notice expired {expires_date} |

Rows (`check.detail.<case>` is the sentence and `check.finding.<case>` the finding column; the state is the row's `status`)

| id | row | state | when | finding | source line | text |
|---|---|---|---|---|---|---|
| check.detail.unavailable | any | Source unavailable | the source did not answer | (none) | source_line.unavailable | {source_name} did not respond. This row is asked again at the next recheck or the next upload. |
| check.detail.IDENTITY.confirmed | Identity | Confirmed | similarity 90 or more and the date of birth matches | (none) | source_line.APAAR | Name and date of birth match the APAAR registry (similarity {name_score} of 100). |
| check.detail.IDENTITY.confirmed_digilocker | Identity | Confirmed | no APAAR; the student claimed the record through DigiLocker (D36) | (none) | source_line.STUDENT_DIGILOCKER | The student signed in with DigiLocker on {date} and claimed this record with its provisional ID; name and date of birth match. |
| check.detail.IDENTITY.confirmed_sii | Identity | Confirmed | international student, passport confirmed | (none) | source_line.SII | Study in India confirms the passport holder's identity. |
| check.detail.IDENTITY.pending_review | Identity | Pending | similarity 75 to 89 (`needs_review`) | needs review | source_line.APAAR | Name on upload is close to the APAAR registry but not a clear match (similarity {name_score} of 100); an officer should review. Name matching supports a decision; it never makes one. |
| check.detail.IDENTITY.contradicted_not_found | Identity | Contradicted | the registry has no such id | APAAR not found | source_line.APAAR | APAAR ending {apaar_last4} is not in the APAAR registry. |
| check.detail.IDENTITY.contradicted_malformed | Identity | Contradicted | the APAAR as uploaded is not 12 digits | APAAR not valid | source_line.COLLEGE_UPLOAD | APAAR as uploaded {problem}; the record was kept without it. |
| check.detail.IDENTITY.contradicted_name | Identity | Contradicted | similarity below 75 | name differs | source_line.APAAR | Name on upload differs from the APAAR registry (similarity {name_score} of 100). |
| check.detail.IDENTITY.contradicted_dob | Identity | Contradicted | the date of birth differs | date of birth differs | source_line.APAAR | Date of birth on upload does not match the APAAR registry. |
| check.detail.IDENTITY.na_no_apaar | Identity | Not applicable | no APAAR, record not claimed yet | (none) | source_line.na.IDENTITY | APAAR not linked, and the student has not claimed the record through DigiLocker yet. Admission is not blocked. |
| check.detail.SEAT.confirmed | Seat | Confirmed | holds a seat of the current approval version | fits approved intake | source_line.SEAT_LEDGER | Holds seat {seat_code} ({seat_type_word}, AICTE approval v{version}, {cohort_year}). |
| check.detail.SEAT.contradicted_no_seat | Seat | Contradicted | no free seat of the route's type | beyond approved intake | source_line.SEAT_LEDGER | No {seat_type_word} seat is free in {programme_code} ({cohort_year}); see the {flag_name} case. |
| check.detail.SEAT.contradicted_no_pool | Seat | Contradicted | the approval has no seats of the route's type | no {seat_type_word} seats approved | source_line.SEAT_LEDGER | {route_word} admission is not allowed for {programme_code}: approval v{version} for {cohort_year} has no {seat_type_word} seats. |
| check.detail.SEAT.contradicted_eligibility | Seat | Contradicted | the category is not allowed for the student as reported (D41) | not eligible for this seat | source_line.SEAT_LEDGER | {seat_type_word} seat held by a student reported as {reported_word}; {clause} does not allow it. |
| check.detail.SEAT.pending_tfw | Seat | Pending | TFW without `tfw_income_certified = yes` | TFW income certificate not reported | source_line.SEAT_LEDGER | TFW income certificate not reported; the seat is held until the college reports it. |
| check.detail.ADMISSION.confirmed | Joining record | Confirmed | the authority records the joining | joined {joined_date} | source_line.ADMISSION_AUTHORITY | The {state_name} admission authority records that the student joined {programme_code} at this college on {joined_date} ({round_words}). |
| check.detail.ADMISSION.confirmed_sii | Joining record | Confirmed | Study in India confirms the admission | (none) | source_line.SII | Study in India confirms this admission to {programme_code} ({cohort_year}). |
| check.detail.ADMISSION.pending | Joining record | Pending | not in the record, before the deadline | not in the joining record yet | source_line.ADMISSION_AUTHORITY | Not in the {state_name} admission authority's joining record yet; the reporting deadline is {deadline_date}. |
| check.detail.ADMISSION.not_yet_due | Joining record | Not yet due | before the deadline, nothing published yet (R4) | (none) | source_line.not_due.ADMISSION | The {state_name} admission authority publishes joining records by {deadline_date}. |
| check.detail.ADMISSION.contradicted | Joining record | Contradicted | not found after the deadline | not found | source_line.ADMISSION_AUTHORITY | Not found in the {state_name} admission authority's joining record for {programme_code} ({academic_year}) after the reporting deadline of {deadline_date}. |
| check.detail.ADMISSION.contradicted_sii | Joining record | Contradicted | Study in India has no match | not found | source_line.SII | Study in India has no matching admission for this passport at this institution. |
| check.detail.STUDYING.confirmed | Credits | Confirmed | credits in every expected semester, issued by a body other than the college | credits for {expected} semesters | source_line.ABC | Credits recorded in ABC for all {expected} semesters since admission, issued by {issuer_name}. |
| check.detail.STUDYING.confirmed_self | Credits | Confirmed, from the college itself | the same, issued by the claiming college (D38) | credits for {expected} semesters | source_line.ABC_self | Credits recorded in ABC for all {expected} semesters, issued by the college itself. They do not count as evidence independent of the college. |
| check.detail.STUDYING.not_yet_due | Credits | Not yet due | year 1 before the first semester result | (none) | source_line.not_due.STUDYING | First year; no semester result is due yet. |
| check.detail.STUDYING.not_yet_due_lateral | Credits | Not yet due | a year-2 lateral entrant before the first result here | (none) | source_line.not_due.STUDYING_lateral | Lateral entry into year 2; no semester result here is due yet. |
| check.detail.STUDYING.pending | Credits | Pending | one expected semester missing | waiting for semester {sem} | source_line.ABC | No credits recorded in ABC for semester {sem} ({academic_year}); waiting for the next results. |
| check.detail.STUDYING.contradicted | Credits | Contradicted | two or more expected semesters missing | no credits for {missing} semesters | source_line.ABC | No credits recorded in ABC for {missing} of {expected} semesters since admission. |
| check.detail.STUDYING.na_no_apaar | Credits | Not applicable | no APAAR | (none) | source_line.na.STUDYING | APAAR not linked; ABC credits cannot be checked. |
| check.detail.STUDYING.na_abc_unknown | Credits | Not applicable | ABC does not know the APAAR | (none) | source_line.na.STUDYING_abc | ABC has no record of this APAAR; see the Identity row. |
| check.detail.STUDENT.confirmed | Student | Confirmed | Yes after DigiLocker sign-in | "I joined" | source_line.STUDENT_DIGILOCKER | The student signed in with DigiLocker on {reply_date} and said they joined. |
| check.detail.STUDENT.confirmed_changed | Student | Confirmed | No changed to Yes within 7 days | "I joined" | source_line.STUDENT_DIGILOCKER | The student said they never joined on {reply_date}, then changed the answer to Yes on {changed_date}. |
| check.detail.STUDENT.contradicted | Student | Contradicted | No after DigiLocker sign-in | "I never joined" | source_line.STUDENT_DIGILOCKER | The student signed in with DigiLocker on {reply_date} and said they never joined. |
| check.detail.STUDENT.pending_not_sent | Student | Pending | no notice yet | notice not sent yet | source_line.STUDENT.not_sent | Notice not sent yet. |
| check.detail.STUDENT.pending_sent | Student | Pending | a notice is live with no answer | no answer yet | source_line.STUDENT.sent | Notice sent on {sent_date}; no answer yet. |
| check.detail.STUDENT.pending_expired | Student | Pending | every notice expired unanswered | no answer | source_line.STUDENT.expired | No answer before the notice expired on {expires_date}. Silence never counts against the record. |

`{problem}` is, for example, "has 11 digits, expected 12". `{round_words}` is "round {round}" for a counselling joining and "{route_word} admission approved by the state" for management, NRI and spot joinings (D39). `{reported_word}` is the `eligibility.word.*` the upload reported; `{clause}` the handbook clause, e.g. "APH 2026-27 cl. 2.8(b)". The quotation marks in the Student findings are part of the text, as on the deck's card.

Independence (D38): `independent` is true on Confirmed and Contradicted rows from the APAAR registry, the state admission authority, Study in India, the student's DigiLocker sign-in and ABC credits issued by another body; it is false on `STUDYING.confirmed_self` and `IDENTITY.contradicted_malformed` (the college's own upload). The Seat row is derived by the Seat Ledger from AICTE's approval and is not enrolment evidence; it carries no independence marker. A silent student never fails: the Student row stays Pending until an answer, and only a No after DigiLocker sign-in makes it Contradicted.

## 16. Enrolment detail

Routes `/aicte/enrolments/[id]`, `/ro/enrolments/[id]`, `/college/enrolments/[id]`, `/university/enrolments/[id]`, from `GET /enrolments/{id}` (API_CONTRACT §A2.11, with the Addendum 4 fields). The page's centre is the record card (§22); the blocks below are its details.

| id | text |
|---|---|
| enrolment.crumb | Enrolment |
| enrolment.title | {student_name}, {programme_code} |
| enrolment.section.student | Student |
| enrolment.section.enrolment | Enrolment |
| enrolment.section.checks | Evidence |
| enrolment.section.seat | Seat |
| enrolment.section.flags | Cases about this record |
| enrolment.field.institution | Institution |
| enrolment.field.programme | Programme |
| enrolment.field.mode | Mode |
| enrolment.field.intake | Intake |
| enrolment.intake_value | AICTE approval v{version}, {cohort_year} |
| enrolment.field.year | Year of study |
| enrolment.field.route | Admission route |
| enrolment.field.counselling_ref | Counselling reference |
| enrolment.field.category | Category |
| enrolment.field.status | Status |
| enrolment.status_value | {status_word} since {status_date} |
| enrolment.field.admitted_on | Admitted on |
| enrolment.field.uploaded | Uploaded |
| enrolment.field.source_row | Source row |
| enrolment.source_row | Row {row_no} of {filename} |
| enrolment.source_row_none | Not from an upload |
| enrolment.field.dob | Date of birth |
| enrolment.field.gender | Gender |
| enrolment.field.mobile | Mobile |
| enrolment.field.nationality | Nationality |
| enrolment.field.eligibility | Reported eligibility |
| enrolment.seat_value | {seat_code} · {seat_type_word} · approval v{version}, {cohort_year} · assigned {assigned_date} |
| enrolment.unseated | No seat held. |
| enrolment.unseated_flag | See the {flag_name} case. |
| col.check | Check |
| col.source | Source |
| col.detail | Detail |

Student notice block and Resend notice (`POST /enrolments/{id}/notices/resend`, D23)

| id | text |
|---|---|
| enrolment.section.notice | Student notice |
| enrolment.notice.none | No notice sent yet. |
| enrolment.notice.channel_line | {channel_name}: {delivery_word}, {sent_date} |
| enrolment.notice.failed_reason | ({last_error}) |
| enrolment.notice.expires | The link works until {expires_date}. |
| enrolment.notice.expired | Expired on {expires_date} without a reply. |
| enrolment.notice.reply | Reply: {reply_word}, {responded_date} ({channel_word}) |
| enrolment.notice.changed | Reply changed once, on {changed_date}. |
| enrolment.notice.comment | Comment from the student |
| enrolment.notice.consent_off | The student turned off new notices on {withdrawn_date}, so no new notice can be sent. |
| enrolment.notice.consent_off_undated | The student turned off new notices, so no new notice can be sent. |
| resend.button | Resend notice |
| resend.tip | Sends a new notice when the last one expired or was not delivered. Up to 3 times for this enrolment in an academic year. |
| resend.live_tip | The student can still answer the notice sent on {sent_date}, until {expires_date}. |
| resend.confirm_heading | Send a new notice? |
| resend.confirm | {student_name} gets a new link by email, and in DigiLocker when they have an APAAR. Notices can be resent up to 3 times for this enrolment in {academic_year}. |
| resend.send | Send notice |
| resend.cancel | Cancel |
| resend.sending | Sending |
| resend.sent | Notice sent. The new link works until {expires_date}. |

One `enrolment.notice.channel_line` per notification, newest notice first, with `{channel_name}` from `notice_channel.*` and `{delivery_word}` from `notice_delivery.*`; a FAILED line adds `enrolment.notice.failed_reason` with the api's `last_error` verbatim (for a missing DigiLocker account the api writes "No DigiLocker account."). `{reply_word}` is `notice_reply.*` (Confirmed, Denied). `enrolment.notice.comment` and the comment under it appear for officers only; the comment is read from the officers-only "Comment from the student" fact of the enrolment's STUDENT_DENIED flag, and the api never sends it to a registrar or a university (D24). Resend notice shows for an AICTE officer, a regional officer and the registrar of the student's own college, never for the university: enabled when every notice is expired or not delivered; disabled with `resend.live_tip` while a notice is live; replaced by `enrolment.notice.consent_off_undated` when `resend.blocked_by` is CONSENT_WITHDRAWN (enrolment detail carries no withdrawal date, so `enrolment.notice.consent_off` is not printed there). A 429 `RESEND_LIMIT` shows [err.RESEND_LIMIT] and disables the button; a 409 `NOTICE_LIVE` shows [err.NOTICE_LIVE] and refetches.

The record card (§22) replaces the checks table: Check (`check.*`), Evidence state (`evidence.state.*` with the finding), Source and date (`source_line`), and behind [record.details_show] the row's `detail.summary` verbatim (`col.detail`), with [check.attempts] in small text when `attempts` is above 0. A row never checked prints [check.never] in its Source and date cell. Mobile prints `mobile_masked` exactly as sent; a null value leaves the line out. `enrolment.unseated_flag` takes the SEAT check's `detail.flag_type` and links to that flag in `flags` when it is there. The footer carries [privacy.read_logged].

## 17. Recheck

`POST /enrolments/{id}/recheck` (AICTE officer, regional officer, the registrar for their own college) and `POST /institutions/{id}/recheck` (AICTE officer, regional officer), API_CONTRACT §A2.12 and §A2.13, with the new states.

| id | text |
|---|---|
| recheck.enrolment | Recheck evidence |
| recheck.enrolment_tip | Asks the sources again for this record's rows that are Pending or Source unavailable. The Student row waits for the student and is not rechecked. |
| recheck.institution | Recheck evidence |
| recheck.institution_tip | Asks the sources again for every row that is Pending or Source unavailable on this institution's active records in {academic_year}. Use it after a source comes back. The Student row is not rechecked. |
| recheck.running | Rechecking |
| recheck.result_heading | Recheck finished |
| recheck.result_line | {check}: {before_word} to {after_word} |
| recheck.no_change | {check}: no change ({state_word}) |
| recheck.none | Nothing to recheck. No row other than the student's answer is Pending or Source unavailable. |
| recheck.flags_raised | {n} new cases opened. |
| recheck.status_line | The record now reads {status_word}. |
| recheck.institution_result | {rechecked} rows asked again in {seconds} s: {now_confirmed} confirmed, {now_contradicted} contradicted, {now_other} not yet due or not applicable, {still_waiting} still waiting. |

The enrolment button shows only when a row other than Student is Pending or Source unavailable. Each item of `results` prints `recheck.result_line` with `evidence.state.*` words, or `recheck.no_change` when the state did not change; `rechecked: 0` prints `recheck.none`; `flags_raised` above 0 adds `recheck.flags_raised`; `recheck.status_line` follows when the record's status changed. `{seconds}` is `duration_ms` / 1000 with one decimal. A 429 shows [err.RATE_LIMITED] and counts down `details.retry_after` on the button. The counts in `recheck.institution_result` are pending contract confirmation of their field names.

## 18. Case list and detail

Case queue `/aicte/cases` and `/ro/cases`, the institution Cases tab, `/college/cases`, and case detail, from `GET /flags` and `GET /flags/{id}` (API_CONTRACT §A2.15, §A2.16). Officers decide from case detail and the registrar responds there (§6).

| id | text |
|---|---|
| flags.heading_college | Cases about your college |
| flags.see_all | See all cases |
| flags.filter.status | Status |
| flags.filter.severity | Severity |
| flags.filter.type | Type |
| flags.filter.institution | Institution |
| flags.filter.state | State |
| flags.filter.programme | Programme |
| flags.filter.all | All |
| flags.search | Search evidence, institution or permanent id |
| flags.sort.severity_desc | Most severe first |
| flags.sort.created_desc | Newest first |
| flags.sort_tip | Most severe first, then oldest first |
| flags.filter.assignee | Assignee |
| flags.filter.assignee_me | Assigned to me |
| flags.filter.assignee_none | Unassigned |
| flags.filter.response | Response |
| flags.filter.response_received | Response received |
| table.count.flags_any | {total} cases in {institutions} institutions |
| table.count.flags_one | {total} open cases |
| table.count.flags_one_any | {total} cases |
| tab.flags_count | Cases ({n}) |
| flags.more | +{n} |
| enrolments.filter.check | Row |
| enrolments.filter.result | Evidence state |
| enrolments.filter.any | Any |
| enrolments.filter.status | Status |
| enrolments.filter.status_all | All statuses |
| enrolments.filter.flagged | Cases |
| enrolments.filter.flagged_yes | With open cases |
| enrolments.filter.flagged_no | No open cases |
| enrolments.filter.seated | Seat |
| enrolments.filter.seated_yes | Holds a seat |
| enrolments.filter.seated_no | Unseated |
| col.severity | Severity |
| col.flag_type | Type |
| col.institution | Institution |
| col.evidence | Evidence |
| col.related | Related |
| col.related_tip | Records this case names that you can see |
| col.opened | Opened |
| col.assignee | Assignee |
| flag.chip | {type_name}, {severity_word} |
| flag.meta | {severity_word} · {status_word} · opened {created_date} |
| flag.where | {institution_name} · {programme_code} · {academic_year} |
| flag.where_no_programme | {institution_name} · {academic_year} |
| flag.facts.label | Fact |
| flag.facts.value | Value |
| flag.facts.source | Source |
| flag.rule | Rule: {rule_source} |
| flag.enrolment_heading | Record this case is about |
| flag.related_heading | Related records ({n}) |
| flag.related_hidden | {n} related records at another institution are not shown to your college. |
| flag.readonly_college | An officer decides every case. If they ask for documents, you can respond here. |

Count line: with the status filter on Open use [table.count.flags]; with any other status filter use `table.count.flags_any`; on one institution's Cases tab and on `/college/cases` use `table.count.flags_one`, or `table.count.flags_one_any` when the status filter is not Open. `{institutions}` is the response's `institutions`. The Evidence cell prints `summary` verbatim on one line, truncated, with the full sentence on focus and hover. Opened prints the `created_at` date. The Assignee column shows on the officers' case queue; a null assignee reads [case.assignee_none]. The Assignee filter sends `assignee=me`, `none` or an officer's id; the Response filter sends `response_received=true`. A row with `response_received` carries the [case.response_badge] chip beside its status. History starts with [case.history.opened] at the `created_at` time, then the rows of §6. `flag.readonly_college` shows to the registrar when the case is not Documents requested. `flag.related_hidden` shows when `related_hidden` is above 0. `flag.chip` is the accessible name of a flag chip in an enrolment row; after two chips the rest collapse into `flags.more`. The enrolments table's Status filter uses `record_status.*` words in the legend's order, its Evidence state filter `evidence.state.*` words and its Row filter `check.*` words in the deck's row order.

## 19. Dashboard cases

| id | text |
|---|---|
| section.flags_by_type | Open cases by type |
| flags_by_type.link | Show {type_name} cases |
| flags_by_type.total | {total} open cases |

`flags_by_type` rows with `open: 0` are hidden; when every row is 0 the panel shows [empty.flags_by_type]. Each row names the type with `flag.<TYPE>.name` and links to the case queue filtered by that type with status Open. Counts are ink with weight; severity colour appears only on severity chips, never on a count.

## 20. Student privacy page

`/student/privacy`, from `GET /privacy/notice`, `GET /students/me/consents`, `POST /students/me/consents/{purpose}/withdraw`, `GET /students/me/access-log`, `POST /students/me/data-requests {kind, details}` and `GET /students/me/export.json` (D30).

| id | text |
|---|---|
| privacy.heading | Privacy |
| privacy.lead | What you agreed to, who has viewed your record, and requests about your data. |
| privacy.notice_link | Read the privacy notice |
| privacy.notice_heading | Privacy notice |
| privacy.notice_version | Version {version}, {date} |
| privacy.consents_heading | What you agreed to |
| privacy.consent_status | {state_word} on {date} |
| privacy.consent_last | Last given on {date} |
| privacy.consent_via.APAAR_LINK | Recorded by your college when it uploaded your enrolment |
| privacy.consent_via.NOTICE | Given when you replied Yes to a notice |
| privacy.consent_via.CREDENTIAL_SHARE | Given each time you share an attestation |
| privacy.consent_text_show | Show the exact text |
| privacy.consent_text_hide | Hide the text |
| privacy.consent_version | Text version {version} |
| privacy.withdraw | Withdraw |
| privacy.withdraw_confirm | Yes, withdraw |
| privacy.withdraw_cancel | Keep it |
| privacy.withdrawn_on | Withdrawn on {date} |
| privacy.withdraw_done.NOTICE | New notices are off. You can still answer notices already sent. |
| privacy.withdraw_done.CREDENTIAL_SHARE | Sharing stopped. QR codes and links you created no longer work. |
| privacy.unlink_apaar | Ask to unlink my APAAR |
| privacy.consent_none | No consents recorded yet. |
| privacy.consent_state_none | Not given yet |
| privacy.access_heading | Who viewed your record |
| privacy.access_lead | Every time someone opens your record it is logged. You see their role and the date, never their name. |
| privacy.access.col.date | Date |
| privacy.access.col.who | Who |
| privacy.access.AICTE_ADMIN | An AICTE officer |
| privacy.access.RO_OFFICER | A regional officer |
| privacy.access.INSTITUTION | Your college |
| privacy.access.UNIVERSITY | Your university |
| privacy.access.STUDENT | You |
| privacy.access.notice_link | Someone who opened your notice link |
| privacy.access.verifier | A verifier you shared an attestation with |
| privacy.access.SYSTEM | Countersign itself |
| privacy.access.more | Show older |
| privacy.access_empty | Nobody has viewed your record yet. When someone does, the role and the date appear here. |
| privacy.requests_heading | Requests about your data |
| privacy.requests_lead | Ask for a copy of what Countersign holds about you, a correction, or an erasure. |
| privacy.request.new | Make a request |
| privacy.request.kind_label | What do you want? |
| privacy.request.kind.ACCESS | A copy of my data |
| privacy.request.kind_hint.ACCESS | A file with everything Countersign holds about you, ready at once. Your APAAR stays masked in it. |
| privacy.request.kind.CORRECTION | Correct something |
| privacy.request.kind_hint.CORRECTION | Tell us what is wrong. An AICTE officer replies here; your college may need to upload your record again. |
| privacy.request.kind.ERASURE | Erase my data |
| privacy.request.kind_hint.ERASURE | Tell us what to erase. Some records must be kept by law; the reply says what can be removed. |
| privacy.request.details.ACCESS | Anything to add? (optional) |
| privacy.request.details.CORRECTION | What is wrong, and what should it say? |
| privacy.request.details.ERASURE | What should be erased, and why? |
| privacy.request.details_required | Write a few words so an officer knows what to do. |
| privacy.request.unlink_prefill | Please unlink my APAAR from my enrolment at {institution_name}. |
| privacy.request.submit | Send request |
| privacy.request.sending | Sending |
| privacy.request.cancel | Cancel |
| privacy.request.sent | Request sent. An AICTE officer replies here. |
| privacy.request.row | {kind_word}, sent {date} |
| privacy.request.waiting | Waiting for a reply from AICTE |
| privacy.request.reply | Reply from AICTE, {date} |
| privacy.request.none | You have not made any requests. |
| privacy.export_ready | Your copy is ready. |
| privacy.export_download | Download my data (JSON file) |
| privacy.export_note | The file lists everything Countersign holds about you. Your APAAR is masked in it too. Keep the file somewhere safe. |
| privacy.export_preparing | Preparing your file |

Consents: one row per purpose in the order APAAR_LINK, NOTICE, CREDENTIAL_SHARE, each with the `consent_purpose.*` words, the `consent_state.*` word in `privacy.consent_status` (or `privacy.consent_state_none` when nothing is recorded for the purpose), the `privacy.consent_via.*` line and the exact stored text behind `privacy.consent_text_show`. CREDENTIAL_SHARE is recorded once per share; its row shows the newest with `privacy.consent_last`. Withdraw shows on NOTICE and CREDENTIAL_SHARE while they are Given and opens `consent.withdraw.<PURPOSE>` with `privacy.withdraw_confirm` and `privacy.withdraw_cancel`; the APAAR_LINK row shows `consent.unlink_apaar` and `privacy.unlink_apaar` instead.

Access log (D30): READ entries about the student and their enrolments, newest first, Date and Who only. Who is `privacy.access.<ROLE>` by the reader's role; an entry with no actor reads `privacy.access.notice_link` when it came from a notice link and `privacy.access.verifier` when it came from a verifier check; any other entry without an actor (`role` `SYSTEM`) reads `privacy.access.SYSTEM`. Never a name, an email, a college other than the student's own, or an IP.

Requests: Access is fulfilled at once: after sending, the form is replaced by `privacy.export_ready` and `privacy.export_download` (a link to `/api/students/me/export.json`) with `privacy.export_note`. Correction and Erasure need details (`privacy.request.details_required` under an empty field) and appear in the list with `privacy.request.row`, the `data_request_status.*` word with an icon, `privacy.request.waiting` while Open, and the officer's reply under `privacy.request.reply` once resolved. `privacy.request.cancel` closes the form without sending.

Privacy notice (`GET /privacy/notice`, version `v2`, effective when Addendum 4 ships; v1 of 28 Oct 2026 stays readable for consents given under it). The api serves it from `app/privacy/notice.py`; the page prints `title` as the heading ("How Countersign uses your data", or `privacy.notice_heading` when it is missing), `privacy.notice_version`, then each section's `heading` and `body` in this order. A new wording is a new version, made in the api and mirrored here.

| id | heading | text |
|---|---|---|
| privacy_notice.title | | How Countersign uses your data |
| privacy_notice.what_we_hold | What we hold | Your college uploads your enrolment: your name, date of birth, gender, nationality, email, mobile number and address, your programme, year of study, admission route and category, and your APAAR id when you allowed it to be linked. Your APAAR id and passport number are stored encrypted, your mobile number and address only as keyed fingerprints, and officers see only the last four digits of your APAAR id. Countersign also holds the evidence about your enrolment with the source and date of each fact, any cases about it and their decisions, the notices sent to you and your answers, your DigiLocker sign-in (your name, date of birth, APAAR if linked and DigiLocker id), the attestations in your wallet, and a log of who viewed your record. |
| privacy_notice.why_we_use_it | Why we use it | AICTE uses your data only to check the evidence behind your college's record of your enrolment: that your identity matches the APAAR registry or your DigiLocker sign-in, that the seat was approved, that the state admission authority records your joining, that you are earning credits, and what you yourself say. Nothing is decided automatically. When a source disagrees, an officer reads the evidence and decides, and Countersign never cancels an admission. |
| privacy_notice.where_we_check | Where we check it | With your consent, AICTE looks up your APAAR id with the APAAR registry and the Academic Bank of Credits, and checks your name, date of birth and programme against the state admission authority's joining record. AICTE sends you a notice by email or through DigiLocker, and you answer it after signing in with DigiLocker, so that only you can confirm or dispute the enrolment. International students are checked against Study in India records using their passport. |
| privacy_notice.who_sees_it | Who sees it | AICTE officers, the regional officer for your college's region, your college and, once you graduate, your university see your enrolment with your APAAR masked. Your college sees your answer to a notice only as Joined or Never joined; a comment you add is seen only by AICTE officers. When you share an attestation, whoever checks it sees only the fields you chose. |
| privacy_notice.your_rights | Your rights | On your Privacy page you can read what you agreed to in the exact words you saw, stop new notices, stop sharing your attestations, see who viewed your record by role and date, download a copy of everything Countersign holds about you, and ask for a correction or an erasure. AICTE answers every request in writing on the same page. |
| privacy_notice.how_long | How long we keep it | Enrolment records, their evidence and cases, and the audit log are kept for the period the law requires, so they cannot be erased on request. Contact details and anything not needed for that record can be removed when you ask. |

The ids after `privacy_notice.` are the sections' `id` values on the wire. The consent texts the notice also returns are §9's `consent.apaar_link`, `consent.notice` and `consent.credential_share`, with their placeholders left in.

## 21. Evidence states and record statuses

DECISIONS D34, D35 and R3. Each active record has five rows, always in the deck's order: Identity, Seat, Joining record, Credits, Student (wire names IDENTITY, SEAT, ADMISSION, STUDYING, STUDENT). Each row carries exactly one evidence state and its provenance; each record carries exactly one status.

Rules for every screen:
- Rows say Confirmed; only a record says Countersigned. A row is never "Countersigned" and a record is never "Confirmed".
- There is no score: no "n of 5", no strip of segments, no percentage per record. One contradiction outranks any number of confirmations: Disputed outranks Under review, which outranks Countersigned, which outranks Awaiting evidence.
- A state or a status is always a word with its icon, never colour alone. Where both a row state and a record status appear, the status is the larger mark.
- A decision is not evidence. An upheld contradiction stays visible on its row with the resolved line; it no longer holds the record under review, but it never confirms it.
- Signals (§27) never appear on a record card and never set a status.

Row labels (`check.*`, same ids; the deck's labels)

| id | text |
|---|---|
| check.label_tip.IDENTITY | Is this person who the college says? Checked with the APAAR registry, or by the student's own DigiLocker sign-in when there is no APAAR. |
| check.label_tip.SEAT | Does the enrolment fit an approved seat? Worked out by the Seat Ledger from the AICTE approval version and the category rules. |
| check.label_tip.ADMISSION | Did the student join this college in this programme? Checked with the state admission authority's joining record, or Study in India for international students. |
| check.label_tip.STUDYING | Is the student earning credits? Checked with ABC, which names the body that issued them. |
| check.label_tip.STUDENT | Does the student agree? Answered only after the student signs in with DigiLocker. |

`check.IDENTITY` Identity, `check.SEAT` Seat, `check.ADMISSION` Joining record, `check.STUDYING` Credits and `check.STUDENT` Student are in §3.

Evidence states

| id | text |
|---|---|
| evidence.state.CONFIRMED | Confirmed |
| evidence.state.CONTRADICTED | Contradicted |
| evidence.state.PENDING | Pending |
| evidence.state.NOT_YET_DUE | Not yet due |
| evidence.state.NOT_APPLICABLE | Not applicable |
| evidence.state.SOURCE_UNAVAILABLE | Source unavailable |
| evidence.tip.CONFIRMED | The source holds this fact and it agrees with the college's record. |
| evidence.tip.CONTRADICTED | The source holds something different from the college's record. An officer decides; nothing changes on its own. |
| evidence.tip.PENDING | The source has been asked and has not answered yet, or its answer needs an officer's review. |
| evidence.tip.NOT_YET_DUE | This evidence cannot exist yet, for example credits before the first semester result. It does not count against the record. |
| evidence.tip.NOT_APPLICABLE | This row does not apply to this record, for example APAAR for a student who chose not to link it. It does not count against the record. |
| evidence.tip.SOURCE_UNAVAILABLE | The source did not respond. This never counts against the record, and the source is asked again at the next recheck. |
| evidence.sr.CONFIRMED | confirmed, the source agrees with the college's record |
| evidence.sr.CONTRADICTED | contradicted, the source disagrees with the college's record |
| evidence.sr.PENDING | pending, waiting for an answer or a review |
| evidence.sr.NOT_YET_DUE | not yet due, this evidence cannot exist yet |
| evidence.sr.NOT_APPLICABLE | not applicable to this record |
| evidence.sr.SOURCE_UNAVAILABLE | source unavailable, it did not respond and is asked again later |
| evidence.sr_row | {check}: {state_sr}. {finding} Source and date: {source_line}. {independence_word}. {resolved_line} |
| evidence.with_finding | {state_word}: {finding} |
| evidence.independent | Independent of the college |
| evidence.from_college | From the college itself |
| evidence.independent_tip | {source_name} is not the college that made this claim, so this fact counts as independent evidence. |
| evidence.from_college_tip | This fact comes from {institution_name} itself. It is shown, but it never makes a record Countersigned on its own. |
| evidence.resolved.UPHELD | Claim upheld by an officer on {date} |
| evidence.resolved_tip | An officer decided this contradiction, so it no longer holds the record under review. A decision is not evidence: the record still needs a confirmed source independent of the college to be Countersigned. |
| evidence.rechecked_after_correction | Checked again after an officer's correction on {date} |

Hindi (for review by a native speaker before the panel)

| id | text |
|---|---|
| evidence.state.CONFIRMED.hi | पुष्ट |
| evidence.state.CONTRADICTED.hi | खंडित |
| evidence.state.PENDING.hi | लंबित |
| evidence.state.NOT_YET_DUE.hi | अभी देय नहीं |
| evidence.state.NOT_APPLICABLE.hi | लागू नहीं |
| evidence.state.SOURCE_UNAVAILABLE.hi | स्रोत उपलब्ध नहीं |
| check.IDENTITY.hi | पहचान |
| check.SEAT.hi | सीट |
| check.ADMISSION.hi | प्रवेश रिकॉर्ड |
| check.STUDYING.hi | क्रेडिट |
| check.STUDENT.hi | विद्यार्थी |

Where the words go:
- The state cell prints `evidence.state.*` with its icon, then `evidence.with_finding` when the row has a `finding` (§15). The deck's sample row "Contradicted: "I never joined"" is this pattern; Identity with nothing more to say prints "Confirmed" alone.
- The independence marker prints under the source line on Confirmed and Contradicted rows only (rows that hold a fact): `evidence.independent` when `independent` is true, `evidence.from_college` when it is false, each with its tooltip. Pending, Not yet due, Not applicable and Source unavailable rows hold no fact and carry no marker.
- `evidence.resolved.UPHELD` prints under a Contradicted row whose `resolved.outcome` is UPHELD, with an icon and `evidence.resolved_tip`. It is never shown as the row's state: the state stays Contradicted.
- The tooltip `evidence.tip.*` is on the state word; `check.label_tip.*` is on the row label. Screen readers hear one `evidence.sr_row` per row: `{state_sr}` from `evidence.sr.*`, `{independence_word}` and `{resolved_line}` left out when they do not apply.

Record statuses

| id | text |
|---|---|
| record_status.AWAITING_EVIDENCE | Awaiting evidence |
| record_status.COUNTERSIGNED | Countersigned |
| record_status.UNDER_REVIEW | Under review |
| record_status.DISPUTED | Disputed |
| record_status.DISPUTED_priority | Disputed (priority) |
| record_status.meaning.AWAITING_EVIDENCE | Nothing contradicts the college's record, but the evidence for its admission route and stage is not complete yet. |
| record_status.meaning.COUNTERSIGNED | Identity, seat and at least one source independent of the college confirm the record, and nothing is unresolved. |
| record_status.meaning.UNDER_REVIEW | A source contradicts the record, or a case about it is open. An officer decides. |
| record_status.meaning.DISPUTED | The student said they never joined. This outranks every confirmation until an officer decides. |
| record_status.legend | Awaiting evidence · Countersigned · Under review · Disputed |
| record_status.legend_label | What the statuses mean |
| record_status.sort.attention | Needs attention first |
| record_status.sort_tip | Disputed, then Under review, then Awaiting evidence, then Countersigned; oldest first within each. |
| record_status.rule | Countersigned = identity verified (or the alternative route) + seat fits the approval + at least one piece of enrolment evidence independent of the college + nothing unresolved. |
| record_status.student.AWAITING_EVIDENCE | Countersign is waiting for records from sources other than your college. You do not need to do anything. |
| record_status.student.COUNTERSIGNED | Your enrolment is backed by sources independent of your college. You can share an attestation of it. |
| record_status.student.UNDER_REVIEW | An AICTE officer is reviewing your college's record. You do not need to do anything, and nothing changes for you until they decide. |
| record_status.student.DISPUTED | You told us you never joined. An AICTE officer is looking into it first. Nothing changes for you until they decide. |

Hindi (for review by a native speaker before the panel)

| id | text |
|---|---|
| record_status.AWAITING_EVIDENCE.hi | साक्ष्य की प्रतीक्षा |
| record_status.COUNTERSIGNED.hi | प्रतिहस्ताक्षरित |
| record_status.UNDER_REVIEW.hi | समीक्षा में |
| record_status.DISPUTED.hi | विवादित |
| record_status.student.AWAITING_EVIDENCE.hi | Countersign आपके कॉलेज के अलावा दूसरे स्रोतों से रिकॉर्ड की प्रतीक्षा कर रहा है। आपको कुछ करने की ज़रूरत नहीं है। |
| record_status.student.COUNTERSIGNED.hi | आपका नामांकन आपके कॉलेज से स्वतंत्र स्रोतों से समर्थित है। आप इसका अनुप्रमाणन साझा कर सकते हैं। |
| record_status.student.UNDER_REVIEW.hi | AICTE का एक अधिकारी आपके कॉलेज के रिकॉर्ड की समीक्षा कर रहा है। आपको कुछ करने की ज़रूरत नहीं है, और उनके निर्णय तक आपके लिए कुछ नहीं बदलता। |
| record_status.student.DISPUTED.hi | आपने हमें बताया कि आपने कभी प्रवेश नहीं लिया। AICTE का एक अधिकारी सबसे पहले इसकी जाँच कर रहा है। उनके निर्णय तक आपके लिए कुछ नहीं बदलता। |

Order and placement: wherever the four statuses are listed together (legend, filters, dashboard tiles, report columns) they follow `record_status.legend`, the deck's order. Lists sorted by status use `record_status.sort.attention`. A Disputed record prints `record_status.DISPUTED_priority` in the record card footer and in the record header; elsewhere (chips, tables, legend) the word is Disputed with its icon. Officers and registrars read `record_status.meaning.*` as the status tooltip; students read `record_status.student.*` as a line under the status. `record_status.rule` is the evidence rule, printed once under the legend on the record card and on the dashboard's status panel.

Status reason (`status_reason`, one sentence written by the api, R3; printed verbatim)

| id | status | when | text |
|---|---|---|---|
| status_reason.DISPUTED | Disputed | the student's dispute is unresolved | The student said they never joined, after signing in with DigiLocker on {reply_date}. |
| status_reason.UNDER_REVIEW.row | Under review | a row is Contradicted and not resolved | {check} is contradicted: {finding}. |
| status_reason.UNDER_REVIEW.case | Under review | a case names the record and is not decided | An open {case_name} case names this record. |
| status_reason.COUNTERSIGNED | Countersigned | the evidence rule holds | Identity, seat and {independent_rows} confirm the record, and nothing is unresolved. |
| status_reason.AWAITING_EVIDENCE.identity | Awaiting evidence | Identity is not Confirmed | Identity is not confirmed yet: {finding}. |
| status_reason.AWAITING_EVIDENCE.seat | Awaiting evidence | Seat is not Confirmed | Seat is not confirmed yet: {finding}. |
| status_reason.AWAITING_EVIDENCE.independent | Awaiting evidence | no enrolment row is Confirmed and independent | No enrolment evidence independent of the college yet. |
| status_reason.AWAITING_EVIDENCE.only_self | Awaiting evidence | the only Confirmed enrolment row comes from the college | The only enrolment evidence so far comes from the college itself. |
| status_reason.AWAITING_EVIDENCE.upheld | Awaiting evidence | a contradiction was upheld and nothing independent confirms the record | An officer upheld the claim on {date}, but no evidence independent of the college confirms the record yet. |

`{check}` is the `check.*` label; `{finding}` the row's finding (§15) as sent; `{case_name}` the `flag.<TYPE>.name`; `{independent_rows}` names the Confirmed independent rows in deck order, joined with commas and a final "and": "the joining record", "credits from {issuer_name}", "the student's own answer" ("Identity, seat and the joining record confirm the record, and nothing is unresolved.").

Next step (`next_step`, one sentence written by the api, R3; printed verbatim)

| id | when | text |
|---|---|---|
| next_step.docs_requested | an open case's last action requested documents with a date | College asked for {docs_words} by {due_date}. |
| next_step.docs_requested_no_date | the same, without a date | College asked for {docs_words}; no reply date set. |
| next_step.docs_overdue | the date has passed without a response | College was asked for {docs_words} by {due_date}; no response yet. |
| next_step.responded | the college responded | College responded on {date}; waiting for an officer's decision. |
| next_step.escalated | the case is escalated | Escalated to AICTE on {date}; waiting for a decision. |
| next_step.dispute_open | a student dispute with no action yet | Waiting for an officer to review the student's dispute. |
| next_step.case_open | any other open case with no action yet | Waiting for an officer to review the {case_name} case. |
| next_step.joining_record | the joining record is missing and the deadline has not passed | Waiting for the joining record from the state admission authority. |
| next_step.joining_deadline | the authority has not published yet | Waiting for the joining record; the state admission authority publishes it by {deadline_date}. |
| next_step.identity_claim | Identity Not applicable, no APAAR | Waiting for the student to sign in with DigiLocker and claim this record with its provisional ID. |
| next_step.source_unavailable | the first missing evidence waits on a source that did not respond | Waiting for {source_name}, which did not respond; it is asked again at the next recheck. |
| next_step.seat_tfw | Seat Pending for the TFW income certificate | Waiting for the college to report the TFW income certificate. |
| next_step.credits | Credits are the next evidence due | Waiting for credits from {issuer_name} after the semester {sem} result. |
| next_step.student | only the student's answer could still complete the record | Waiting for evidence independent of the college; the student's notice was sent on {sent_date}. |
| next_step.none | Countersigned | None. The evidence is complete. |
| next_step.withdrawn | the record was withdrawn by decision | None. The record was withdrawn by an officer's decision on {date}. |

`{docs_words}` is the `docs_kind.*.words` of the request (§6): "College asked for admission documents by 29 Aug." Dates inside these sentences print as `29 Aug` within the current year and `29 Aug 2027` otherwise, the same as the record card.

## 22. The record card, its history and attestations

Enrolment detail (`/aicte/enrolments/[id]`, `/ro/enrolments/[id]`, `/college/enrolments/[id]`, `/university/enrolments/[id]`) and the student's `/student` card, from `GET /enrolments/{id}` and `GET /students/me` (API Addendum 4, pending). The card is the deck's slide 2 card.

| id | text |
|---|---|
| record.header | {programme_short} {cohort_start}, {institution_name} · {id_label} {id_masked} |
| record.col.check | Check |
| record.col.state | Evidence state |
| record.col.source | Source and date |
| record.footer_status | Status: {status_word}. |
| record.footer_next | Next step: {next_step} |
| record.reason | Why: {status_reason} |
| record.status_since | Since {date} |
| record.details_show | Show details |
| record.details_hide | Hide details |
| record.withdrawn_banner | This record was withdrawn by an officer's decision on {date}. It no longer counts toward the college's admissions, and nothing about it was deleted. |
| record.withdrawn_upload_banner | The college reported this record as {status_word} on {date}. It no longer counts toward the college's admissions. |
| record.aria_card | Record card for {programme_short}, {institution_name} |

Header, rows, footer, legend, in that order, exactly as the deck draws them:

```
B.Tech CSE 2026, ABC College of Engineering · APAAR XXXX XXXX 4417
Check           Evidence state                       Source and date
Identity        Confirmed                            APAAR verification · 12 Aug
Seat            Confirmed: fits approved intake      AICTE approval v2, 2026-27 (Seat Ledger, derived)
Joining record  Contradicted: not found              State admission authority · 20 Aug
Credits         Not yet due                          First semester not complete
Student         Contradicted: "I never joined"       Student sign-in via DigiLocker · 22 Aug
Status: Disputed (priority). Next step: College asked for admission documents by 29 Aug.
Awaiting evidence · Countersigned · Under review · Disputed
```

The deck's slide shortens the Seat and Joining record cells to their findings; the product always prints the state word first, so the six states read the same on every row. `record.reason` sits under the footer for officers and the registrar (never for the student, who reads `record_status.student.*`). Dates on the card print as `12 Aug` when they fall in the current calendar year and `12 Aug 2025` otherwise. A record that left ACTIVE carries `record.withdrawn_banner` (by decision) or `record.withdrawn_upload_banner` (reported by the college) above the card, and its footer reads the last status it held.

History (`enrolment_versions`, D42; newest first)

| id | text |
|---|---|
| history.heading | History |
| history.col.when | When |
| history.col.what | What changed |
| history.col.by | By |
| history.created.UPLOAD | Record created by upload {filename} on {date}. |
| history.created.API | Record created by the college's system on {date}. |
| history.created.SEED | Record created by the demo seed on {date}. |
| history.change.UPLOAD | {field_word} changed from {before} to {after} by upload on {date}. |
| history.change.API | {field_word} changed from {before} to {after} by the college's system on {date}. |
| history.change.DECISION | {field_word} changed from {before} to {after} by an officer's decision on {date}. |
| history.change.SEED | {field_word} changed from {before} to {after} by the demo seed on {date}. |
| history.withdrawn.DECISION | Record withdrawn by an officer's decision on {date}. Seat {seat_code} released. |
| history.withdrawn.UPLOAD | Record reported as {status_word} by upload on {date}. Seat {seat_code} released. |
| history.no_seat | No seat was held. |
| history.version | Version {version} |
| history.file | Upload {filename} |
| history.case_link | Case: {case_name} |
| history.blank | blank |
| history.by_role | {role_word} |
| history.by_named | {name}, {role_word} |
| history.empty | No changes since the record was created. |

One row per version: When (`at`), What changed (one sentence per changed field, `history.change.<SOURCE>`, then `history.case_link` for a decision, linked for officers and the registrar), By (`history.by_named` for officers; `history.by_role` for the registrar and the university; the student sees neither names nor roles, only the sentences). `{field_word}` is `field.*`; `{before}` and `{after}` print as sent (masked for APAAR and mobile; enum values as their deck words; a null as `history.blank`). Example: "Programme changed from B.Tech ME to B.Tech CSE by upload on 14 Aug."

Attestations block (officers; ids the web kept in copy-cases.ts as `enrolment.proofs.*`, renamed)

| id | text |
|---|---|
| enrolment.section.attestations | Attestations |
| enrolment.attestations.none | No attestation issued. One is issued when the record is Countersigned. |
| enrolment.attestations.line | {kind_word} {short_id}, issued {issued_date} |
| enrolment.attestations.revoked_line | Revoked on {revoked_date}: {reason} |
| enrolment.attestations.held_by_dispute | Revoked when the student disputed the record. Issued again only if an officer upholds the claim and the record is Countersigned. |
| enrolment.attestations.revoke | Revoke |
| enrolment.attestations.revoke_heading | Revoke this attestation? |
| enrolment.attestations.revoke_body | Anyone who checks it will see Revoked, and the student's wallet says AICTE revoked it. The record and its status do not change, and the attestation is not issued again on its own. |
| enrolment.attestations.reason_label | Reason (kept with the attestation, shown to the student) |
| enrolment.attestations.reason_hint | 5 to 300 characters. |
| enrolment.attestations.reason_short | Give a reason of at least 5 characters. |
| enrolment.attestations.revoke_confirm | Revoke attestation |
| enrolment.attestations.revoking | Revoking |
| enrolment.attestations.cancel | Cancel |
| enrolment.attestations.revoked_toast | Attestation revoked. A verifier who checks it now sees Revoked. |

`{reason}` is the `wallet.revoked_reason.*` sentence for the reason code (§8), or the officer's text for ADMIN.

## 23. DigiLocker sign-in, answering a notice and claiming a record

DECISIONS D36 and D37. A student signs in only through DigiLocker; a notice is answered only after that sign-in; email only points to it. The demo uses mockgov's simulated DigiLocker, labelled as such on every screen it draws.

Sign-in (web: the student entry on `/login`, and the gate on the notice page)

| id | text |
|---|---|
| login.digilocker | Sign in with DigiLocker |
| login.digilocker_hint | Students sign in through DigiLocker. Countersign never asks a student for a password. |
| signin.heading | Sign in with DigiLocker |
| signin.lead | Countersign gets your name, date of birth and APAAR, if linked, from DigiLocker, and nothing else. Countersign never asks you for a password. |
| signin.button | Sign in with DigiLocker |
| signin.why | Why DigiLocker? It shows that you are the person in the record, without relying on an email address or phone number your college gave us. |
| signin.redirect_note | You go to DigiLocker to sign in, then come back here. |
| signin.demo_note | Demo: this opens a simulated DigiLocker with synthetic accounts. No real DigiLocker account is used. |
| signin.returning | Signing you in |
| signin.done | Signed in with DigiLocker as {name} |
| signin.not_you | Not you? Sign out and sign in again. |
| signin.signout | Sign out |
| signin.try_again | Try again |

Demo DigiLocker (mockgov `GET /digilocker/oauth/authorize` and its steps; English only, every screen labelled)

| id | text |
|---|---|
| dldemo.title | Demo DigiLocker, synthetic data |
| dldemo.banner | This is a simulated DigiLocker for the Countersign demo. Every account here is synthetic. Never type real details. |
| dldemo.request | Countersign is asking you to sign in. |
| dldemo.pick_heading | Choose a demo account |
| dldemo.search_label | Search by APAAR or DigiLocker id |
| dldemo.account_line | {name} · APAAR {apaar_masked} |
| dldemo.account_line_no_apaar | {name} · No APAAR linked · DigiLocker id {dl_id_masked} |
| dldemo.search_empty | No demo account matches "{q}". |
| dldemo.continue | Continue |
| dldemo.otp_heading | Enter the OTP |
| dldemo.otp_lead | A real DigiLocker sends an OTP to the mobile number linked to the account. In this demo the OTP is always 123456. |
| dldemo.otp_label | OTP |
| dldemo.otp_submit | Verify |
| dldemo.otp_wrong | That OTP is not right. In this demo it is 123456. |
| dldemo.consent_heading | Share with Countersign? |
| dldemo.consent_lead | Countersign will receive your name, your date of birth, your APAAR if linked, and your DigiLocker id. |
| dldemo.allow | Allow |
| dldemo.deny | Deny |
| dldemo.back | Choose another account |
| dldemo.footer | Demo DigiLocker, synthetic data. Run by the Countersign demo's mock services, not by DigiLocker. |

Notice page after the gate (`/student/notices/[token]`; the claim card and §8's answered states stay)

| id | text |
|---|---|
| notice.signin_lead | To answer, sign in with DigiLocker. Only the person this record is about can answer. |
| notice.signin_button | Sign in with DigiLocker to answer |
| notice.signed_in_as | Signed in with DigiLocker as {name}. |
| notice.signout | Not you? Sign out |
| notice.someone_else_heading | This notice is for someone else |
| notice.someone_else_body | You are signed in with DigiLocker as {name}, but this notice is about a different person's record. Nothing was recorded. |
| notice.someone_else_college | If you did join {institution_name}, the college may have recorded a different APAAR for you. Ask the college to check your record. |
| notice.someone_else_other | If you have never had anything to do with {institution_name}, you do not need to do anything. |
| notice.claim_needed_heading | Claim this record first |
| notice.claim_needed | This record has no APAAR, so Countersign cannot tell from DigiLocker that it is yours. Claim it with the provisional ID your college gave you, then answer. |
| notice.claim_button | Claim with provisional ID |

Claim by provisional ID (`/student/claim`, signed in)

| id | text |
|---|---|
| claim.heading | Claim your record |
| claim.lead | Your college recorded your enrolment without an APAAR and gave you a provisional ID. Enter it to link the record to your DigiLocker sign-in. |
| claim.id_label | Provisional ID |
| claim.id_hint | It starts with PRV- and has 8 more letters and digits, for example PRV-7K2M9QXA. |
| claim.match_note | Countersign checks that the name and date of birth on your DigiLocker match the record. A small difference in spelling is allowed; your DigiLocker sign-in decides. |
| claim.submit | Claim record |
| claim.submitting | Checking |
| claim.format | A provisional ID is PRV- followed by 8 letters and digits. Check it and try again. |
| claim.done_heading | Record claimed |
| claim.done | This record at {institution_name} is now linked to your DigiLocker sign-in. Its Identity row reads Confirmed. |
| claim.done_answer | Answer the notice |
| claim.done_home | Go to my enrolment |
| claim.locked | Too many tries. For your safety, claiming is paused for {minutes} minutes. |

Email and DigiLocker inbox notice: a pointer only, and nothing in it can record an answer. The English rows `notice.email_subject`, `notice.email_body` and `notice.digilocker` are in §8; their Hindi rows are below.

After a decision on the student's dispute (`/student`, `/student/notices`; the student sees the outcome, never the officer's note or name)

| id | text |
|---|---|
| student.decision.UPHELD | An AICTE officer reviewed your dispute and decided that {institution_name}'s record stands. Their reason: {reason_word}. If you think this is wrong, ask for a correction from your Privacy page. |
| student.decision.WITHDRAWN | An AICTE officer agreed with you: {institution_name}'s claim that you joined has been withdrawn. |
| student.decision.CORRECTED | An AICTE officer corrected {institution_name}'s record of your enrolment. See what changed under History. |
| student.decision.ESCALATED | Your dispute has been passed to AICTE for a decision. Nothing changes for you until they decide. |

Hindi (for review by a native speaker before the panel)

| id | text |
|---|---|
| signin.heading.hi | DigiLocker से साइन इन करें |
| signin.lead.hi | Countersign को DigiLocker से केवल आपका नाम, जन्म तिथि और APAAR (अगर जुड़ा है) मिलता है। Countersign आपसे कभी पासवर्ड नहीं माँगता। |
| signin.button.hi | DigiLocker से साइन इन करें |
| signin.why.hi | DigiLocker क्यों? इससे पता चलता है कि रिकॉर्ड वाले व्यक्ति आप ही हैं, कॉलेज के दिए किसी ईमेल पते या फ़ोन नंबर पर निर्भर हुए बिना। |
| signin.redirect_note.hi | साइन इन करने के लिए आप DigiLocker पर जाएँगे, फिर यहाँ लौट आएँगे। |
| signin.demo_note.hi | डेमो: यह सिंथेटिक खातों वाला एक सिम्युलेटेड DigiLocker खोलता है। किसी असली DigiLocker खाते का उपयोग नहीं होता। |
| signin.returning.hi | आपको साइन इन किया जा रहा है |
| signin.done.hi | आप DigiLocker से {name} के रूप में साइन इन हैं |
| signin.not_you.hi | आप नहीं हैं? साइन आउट करें और फिर से साइन इन करें। |
| signin.signout.hi | साइन आउट करें |
| signin.try_again.hi | फिर कोशिश करें |
| notice.signin_lead.hi | उत्तर देने के लिए DigiLocker से साइन इन करें। जिस व्यक्ति के बारे में यह रिकॉर्ड है, केवल वही उत्तर दे सकता है। |
| notice.signin_button.hi | उत्तर देने के लिए DigiLocker से साइन इन करें |
| notice.signed_in_as.hi | आप DigiLocker से {name} के रूप में साइन इन हैं। |
| notice.signout.hi | आप नहीं हैं? साइन आउट करें |
| notice.someone_else_heading.hi | यह सूचना किसी और के लिए है |
| notice.someone_else_body.hi | आप DigiLocker से {name} के रूप में साइन इन हैं, लेकिन यह सूचना किसी दूसरे व्यक्ति के रिकॉर्ड के बारे में है। कुछ भी दर्ज नहीं हुआ। |
| notice.someone_else_college.hi | अगर आपने {institution_name} में प्रवेश लिया है, तो हो सकता है कॉलेज ने आपके लिए कोई दूसरा APAAR दर्ज किया हो। कॉलेज से अपना रिकॉर्ड जाँचने को कहें। |
| notice.someone_else_other.hi | अगर {institution_name} से आपका कभी कोई संबंध नहीं रहा, तो आपको कुछ करने की ज़रूरत नहीं है। |
| notice.claim_needed_heading.hi | पहले इस रिकॉर्ड पर दावा करें |
| notice.claim_needed.hi | इस रिकॉर्ड में APAAR नहीं है, इसलिए Countersign DigiLocker से यह नहीं जान सकता कि यह आपका है। अपने कॉलेज से मिली अस्थायी आईडी से इस पर दावा करें, फिर उत्तर दें। |
| notice.claim_button.hi | अस्थायी आईडी से दावा करें |
| claim.heading.hi | अपने रिकॉर्ड पर दावा करें |
| claim.lead.hi | आपके कॉलेज ने आपका नामांकन बिना APAAR के दर्ज किया है और आपको एक अस्थायी आईडी दी है। रिकॉर्ड को अपने DigiLocker साइन-इन से जोड़ने के लिए उसे यहाँ लिखें। |
| claim.id_label.hi | अस्थायी आईडी |
| claim.id_hint.hi | यह PRV- से शुरू होती है और उसके बाद 8 अक्षर और अंक होते हैं, जैसे PRV-7K2M9QXA। |
| claim.match_note.hi | Countersign जाँचता है कि आपके DigiLocker पर नाम और जन्म तिथि इस रिकॉर्ड से मेल खाते हैं। वर्तनी में थोड़ा अंतर चल जाता है; निर्णय आपके DigiLocker साइन-इन से होता है। |
| claim.submit.hi | रिकॉर्ड पर दावा करें |
| claim.submitting.hi | जाँच हो रही है |
| claim.format.hi | अस्थायी आईडी में PRV- के बाद 8 अक्षर और अंक होते हैं। इसे जाँचें और फिर कोशिश करें। |
| claim.done_heading.hi | रिकॉर्ड आपसे जुड़ गया |
| claim.done.hi | {institution_name} का यह रिकॉर्ड अब आपके DigiLocker साइन-इन से जुड़ गया है। इसकी पहचान पंक्ति अब "पुष्ट" दिखाती है। |
| claim.done_answer.hi | सूचना का उत्तर दें |
| claim.done_home.hi | मेरा नामांकन देखें |
| claim.locked.hi | बहुत अधिक प्रयास हुए हैं। आपकी सुरक्षा के लिए दावा करना {minutes} मिनट के लिए रोक दिया गया है। |
| notice.email_subject.hi | {institution_name} ने आपके नाम से एक नामांकन की जानकारी दी है |
| notice.email_body.hi | {institution_name} ने AICTE को बताया है कि आपने {academic_year} में {programme_name} में प्रवेश लिया है। उन्होंने क्या बताया है यह देखने और उत्तर देने के लिए {link} खोलें और DigiLocker से साइन इन करें। आपका उत्तर DigiLocker से साइन इन करने के बाद ही दर्ज होता है; इस ईमेल से कुछ भी दर्ज नहीं हो सकता। यह लिंक {expires_date} तक काम करेगा। अपना DigiLocker OTP किसी के साथ साझा न करें, AICTE या अपने कॉलेज के साथ भी नहीं। |
| student.decision.UPHELD.hi | AICTE के एक अधिकारी ने आपके विवाद की समीक्षा की और निर्णय लिया कि {institution_name} का रिकॉर्ड बना रहेगा। उनका कारण: {reason_word}। अगर आपको लगता है कि यह गलत है, तो अपने Privacy पेज से सुधार का अनुरोध करें। |
| student.decision.WITHDRAWN.hi | AICTE के एक अधिकारी ने आपकी बात मानी: {institution_name} का यह दावा कि आपने प्रवेश लिया था, वापस ले लिया गया है। |
| student.decision.CORRECTED.hi | AICTE के एक अधिकारी ने आपके नामांकन के बारे में {institution_name} के रिकॉर्ड में सुधार किया है। क्या बदला, यह "History" में देखें। |
| student.decision.ESCALATED.hi | आपका विवाद निर्णय के लिए AICTE को भेजा गया है। उनके निर्णय तक आपके लिए कुछ नहीं बदलता। |

Which state shows (D37): the notice page shows the claim card to whoever holds the link, as before, but Yes and No are replaced by `notice.signin_lead` and `notice.signin_button` until the student is signed in. After sign-in, one of four things happens. The signed-in DigiLocker identity matches the record's APAAR: the claim card shows `notice.signed_in_as` with `notice.signout`, then Yes and No as in §8. The record has an APAAR that does not match: `notice.someone_else_heading`, `notice.someone_else_body`, `notice.someone_else_college`, `notice.someone_else_other` and `notice.signout`; no buttons; nothing recorded. The record has no APAAR and is not claimed: `notice.claim_needed_heading`, `notice.claim_needed` and `notice.claim_button` (to `/student/claim?next=` the notice). The record is claimed by this sign-in: as the match. `{name}` is the name DigiLocker returned, never the record's name. `{reason_word}` in `student.decision.UPHELD` is the `reason.UPHOLD.*` word and stays in English inside the Hindi row. The demo login page's student card opens the same DigiLocker sign-in; the demo account list shows Ravi Kumar Sharma first.

## 24. Completeness and reporting deadlines

DECISIONS D40. Reconciliation of each college's uploads against the state admission authority's joinings list, per academic year.

| id | text |
|---|---|
| completeness.heading | Completeness |
| completeness.line | {pct}% of joined students uploaded, {missing} missing |
| completeness.line_full | All {joined} joined students uploaded |
| completeness.line_none | No joinings published yet by the state admission authority |
| completeness.tip | Students the state admission authority lists as joined at this college in {academic_year}, against the students in the college's uploads. We can only check data we receive, and we say so. |
| completeness.col | Completeness |
| completeness.col_missing | Missing |
| completeness.col_joined | Joined (authority) |
| completeness.col_uploaded | Uploaded and joined |
| deadline.col | Reporting deadline |
| deadline.ON_TIME | On time |
| deadline.LATE | Late |
| deadline.OVERDUE | Overdue |
| deadline.NOT_DUE | Due {deadline_date} |
| deadline.tip.ON_TIME | First upload on {uploaded_date}, before the deadline of {deadline_date}. |
| deadline.tip.LATE | First upload on {uploaded_date}, after the deadline of {deadline_date}. |
| deadline.tip.OVERDUE | No upload yet. The deadline was {deadline_date}. |
| deadline.tip.NOT_DUE | Reporting deadline {deadline_date}. |
| missing.heading | Missing from the upload ({n}) |
| missing.lead_college | The state admission authority lists these students as joined at your college in {academic_year}, but they are not in your uploads. Upload their rows to complete your record. |
| missing.lead_officer | The state admission authority lists these students as joined at {institution_name} in {academic_year}, but they are not in the college's uploads. |
| missing.col.student | Student |
| missing.col.programme | Programme |
| missing.col.joined_on | Joined on |
| missing.col.round | Admission round |
| missing.none | No missing students. Every student the state admission authority lists as joined is in the uploads. |
| missing.download | Download the list as CSV |
| missing.case_line | A Missing from upload case is open for these students. |

`completeness.line` takes `completeness_pct` as sent (one decimal, a trailing ".0" dropped) and `missing`; when `missing` is 0 it is `completeness.line_full`; a null percentage is `completeness.line_none` when the authority has published nothing, else [kpi.not_computed]. Deadline words come with their icon and tooltip; Overdue is never red text (the hue rule for counts applies). The Student cell of the missing list prints the masked APAAR, or the authority's roll number masked to its last four ("Roll XXXX2231") when there is no APAAR, never a full id (D40).

## 25. Approval versions and category eligibility

DECISIONS D41.

| id | text |
|---|---|
| approval.name | AICTE approval v{version}, {cohort_year} |
| approval.versions_heading | Approval versions |
| approval.col.version | Version |
| approval.col.intake | Approved intake |
| approval.col.effective | Effective from |
| approval.col.source | Source |
| approval.current | Current |
| approval.change_up | v{version} raised the intake from {before} to {after} on {date}: {added} seats added and {reseated} records seated from the backlog. |
| approval.change_down | v{version} lowered the intake from {before} to {after} on {date}. |
| approval.source.SAMPLE | Sample approval data |
| approval.rule_tip | Capacity follows the versioned approval: NRI seats inside the approved intake; FN, OCI and CIWG seats supernumerary under the handbook. |
| eligibility.TFW_UNREPORTED | TFW income certificate not reported |
| eligibility.word.FN | foreign national |
| eligibility.word.OCI | OCI |
| eligibility.word.PIO | PIO |
| eligibility.word.CIWG | child of an Indian worker in the Gulf |
| eligibility.word.NRI | NRI |
| eligibility.word.NRI_SPONSORED | NRI-sponsored |
| eligibility.word.NOT_MARKED | not marked for this category |

## 26. Column mapping

DECISIONS D42. A step in the upload form when the file's headers do not match the template, and a page to see or change the saved mapping (`GET/PUT /institutions/{id}/column-mapping`).

| id | text |
|---|---|
| mapping.step | Map your columns |
| mapping.lead | Some of your file's column names do not match the template. Tell Countersign which column holds what. Your choices are saved for next time. |
| mapping.lead_saved | Your saved mapping matched {matched} of {total} columns. Check the rest. |
| mapping.col.theirs | Column in your file |
| mapping.col.ours | Countersign column |
| mapping.not_used | Not used |
| mapping.required_tag | Required |
| mapping.required_missing | Required columns not mapped yet: {columns} |
| mapping.duplicate | {column} is chosen for more than one of your columns: {their_columns}. Choose it once. |
| mapping.saved_for_next_time | Saved for next time |
| mapping.continue | Save mapping and continue |
| mapping.cancel | Choose another file |
| mapping.saved | Mapping saved. Files with these column names are mapped automatically from now on. |
| mapping.batch_line | Columns read with your saved mapping, last changed {date} by {name}. |
| mapping.view | See the mapping |
| mapping.settings_heading | Column mapping |
| mapping.settings_lead | How Countersign reads your college's column names. Change it if your files change. |
| mapping.edit | Change mapping |
| mapping.save | Save mapping |
| mapping.reset | Clear saved mapping |
| mapping.reset_confirm | Clear the saved mapping? The next file with different column names asks you to map them again. |
| mapping.reset_done | Saved mapping cleared. |
| mapping.empty | No saved mapping. Files that use the template's column names need none. |

The Countersign column list shows each template column with its `field.*` word and the column name in monospace ("Date of birth (dob)"), required ones tagged `mapping.required_tag`; a column already chosen elsewhere is listed but marked with `mapping.duplicate` when picked twice. Column names of the college's file print as uploaded. No student value from the file is shown on this step.

## 27. Signals

DECISIONS D45 and R5. Visible to AICTE and regional officers only; never to a registrar, a university, a student or a verifier, and never on a record card.

| id | text |
|---|---|
| signal.heading | Signals |
| signal.lead | Patterns worth a look, found by a published rule or a model. Only AICTE and regional officers see signals. |
| signal.never_status | Signals never change a record's status. Only a case an officer opens can lead to a decision. |
| signal.panel_heading | Signals (officers only) |
| signal.panel_more | See all signals |
| signal.count | {total} signals, {new} new |
| signal.type.GHOST_RING | Shared contact ring |
| signal.type.ANOMALY | Unusual pattern |
| signal.status.NEW | New |
| signal.status.CASE_OPENED | Case opened |
| signal.status.DISMISSED | Dismissed |
| signal.col.type | Type |
| signal.col.summary | What stands out |
| signal.col.colleges | Colleges |
| signal.col.records | Records |
| signal.col.found | Found |
| signal.col.status | Status |
| signal.rule.GHOST_RING | Rule: students linked by a shared mobile number, email or address form a group; a group of 3 or more across 2 or more colleges, or of 5 or more in one college, is a signal. |
| signal.rule.ANOMALY | Model: Isolation Forest, contamination 5%, trained on this year's {n} colleges. |
| signal.feature.admission_growth | Admission growth on last year |
| signal.feature.nri_share | NRI share of admissions |
| signal.feature.management_share | Management share of admissions |
| signal.feature.contradiction_rate | Records with a contradicted row |
| signal.feature.contact_sharing_rate | Students sharing a contact |
| signal.feature_line | {feature_word}: {value} (similar colleges {low} to {high}) |
| signal.fact.students | Students |
| signal.fact.colleges | Colleges |
| signal.fact.mobiles | Shared mobile numbers |
| signal.fact.emails | Shared email addresses |
| signal.fact.addresses | Shared addresses |
| signal.fact.members | Members |
| signal.drawing_note | The drawing shows how members link. The table beside it is the evidence. |
| signal.open_case | Open case |
| signal.open_case_heading | Open a case from this signal? |
| signal.open_case_body | A {case_name} case opens for each college you choose, citing this signal. It follows the same steps as any case: the college can respond, and an officer decides. Records change only through that decision. |
| signal.open_case_colleges | Colleges to open a case for |
| signal.open_case_submit | Open case |
| signal.open_case_submit_many | Open {n} cases |
| signal.case_opened_toast | Case opened. It cites this signal. |
| signal.cases_opened_toast | {n} cases opened. Each cites this signal. |
| signal.case_link | See the case |
| signal.dismiss | Dismiss |
| signal.dismiss_heading | Dismiss this signal? |
| signal.dismiss_body | The signal is kept with your note and stays listed as Dismissed. No record or case changes. |
| signal.dismiss_note_label | Why dismiss it? (officers only) |
| signal.dismiss_submit | Dismiss signal |
| signal.dismissed_toast | Signal dismissed. |
| signal.dismissed_line | Dismissed by {name} on {date}: "{note}" |
| signal.empty | No signals for {academic_year}. |
| signal.empty_filtered | No signals match these filters. |

Summaries (`summary`, one sentence written by the api; printed verbatim)

| id | type | text |
|---|---|---|
| signal.summary.GHOST_RING | GHOST_RING, across colleges | {students} students across {colleges} colleges share {mobiles} mobile numbers, {emails} email addresses and {addresses} addresses. |
| signal.summary.GHOST_RING_one | GHOST_RING, one college | {students} students at {institution_name} share {mobiles} mobile numbers, {emails} email addresses and {addresses} addresses. |
| signal.summary.ANOMALY | ANOMALY | {institution_name} stands out from {peers} similar colleges in {academic_year} on {feature_words}. |

A count of 0 drops its clause ("share 6 mobile numbers and 2 addresses"). `{feature_words}` names the features that made the college stand out, as `signal.feature.*` words in lower case, joined with commas and a final "and". The facts table follows the summary: for a ring, `signal.fact.*` rows, with Members as masked ids and their colleges; for an anomaly, one `signal.feature_line` per feature. The rule line prints under the facts every time. Members are linked to their record only for officers in scope; a regional officer sees members outside the region as "{n} records in other regions".

## 28. Reports

DECISIONS D46. `/aicte/reports` and `/ro/reports`, scoped by role (`/reports/*`).

| id | text |
|---|---|
| report.heading | Reports |
| report.lead | Summaries for policy, accreditation and monitoring. Each downloads as CSV or XLSX; the summary also as a one-page PDF. |
| report.synthetic | Synthetic data. Every college, student and number here is generated for the demo. |
| report.scope_line | {scope_name} · Academic year {academic_year} · Generated {time} |
| report.ro_scope | These reports cover only the {region_name} region. |
| report.name.by_state | Records by state |
| report.desc.by_state | Active records by status in each state, with approved seats and admitted. |
| report.name.by_institution_type | Records by institution type |
| report.desc.by_institution_type | Active records by status for each type of institution. |
| report.name.cases | Cases by type and outcome |
| report.desc.cases | Cases opened, open and decided, by type, with each outcome and the median days to decide. |
| report.name.coverage | Countersign coverage |
| report.desc.coverage | Share of active records Countersigned, by region, state and college. |
| report.name.completeness | Completeness and deadlines |
| report.desc.completeness | Each college's completeness against the state admission authority, its missing count and its deadline state. |
| report.name.summary | One-page summary |
| report.desc.summary | The headline numbers on one page: records by status, completeness, open cases and decisions. |
| report.format.CSV | CSV |
| report.format.XLSX | XLSX |
| report.format.PDF | PDF |
| report.download | Download {format} |
| report.download_label | Download {report_name} as {format} |
| report.preparing | Preparing {format} |
| report.preview | Preview |
| report.preview_rows | First {n} of {total} rows |
| report.empty | No data for {academic_year} in your scope. |
| report.pdf.title | Countersign summary, {scope_name}, {academic_year} |
| report.pdf.footer | Synthetic data. Generated {time} by {role_word}. Page {n} of {m}. |
| report.col.outcome.UPHELD | Claim upheld |
| report.col.outcome.CORRECTED | Claim corrected |
| report.col.outcome.WITHDRAWN | Claim withdrawn |
| report.col.median_days | Median days to decide |

Column headers in the files use the deck words of the same columns on screen (`record_status.*`, `completeness.*`, `deadline.col`, `flag.<TYPE>.name`), so a downloaded file reads like the page. Every file starts with `report.synthetic` as its first line (CSV), first row (XLSX) or header (PDF). No file holds a student name or an unmasked id.

## 29. Evaluation report

DECISIONS D47. Labels for `eval_report.md` and, if the page is built, `/admin/evaluation` (AICTE officer). Every number is synthetic and says so.

| id | text |
|---|---|
| eval.heading | Evaluation |
| eval.lead | How Countersign performs on the synthetic test bed: generated colleges, students and planted cases. Every number here is synthetic. |
| eval.synthetic | Synthetic data |
| eval.run_line | Run {time} · seed {seed} · {colleges} colleges · {records} records |
| eval.col.measure | Measure |
| eval.col.result | Result |
| eval.col.target | Target |
| eval.col.met | Met |
| eval.metric.detection | Seeded inconsistencies caught |
| eval.value.detection | {pct}% ({caught} of {planted}) |
| eval.target.detection | 95% or more |
| eval.metric.false_alarm | Cases raised on legitimate records |
| eval.value.false_alarm | {pct}% ({wrong} of {clean} known-clean records) |
| eval.target.false_alarm | Under 5% |
| eval.metric.throughput | Time to process 50,000 rows |
| eval.value.seconds | {seconds} s |
| eval.target.throughput | Under 2 minutes |
| eval.metric.per_upload | Processing time per upload (median) |
| eval.metric.review_effort | Officer review effort |
| eval.value.review_effort | {cases} cases per 1,000 records, {rows} evidence rows per case |
| eval.metric.signals | Signals against planted rings and anomalies |
| eval.value.signals | Precision {precision}%, recall {recall}% |
| eval.metric.access | Cross-college access attempts refused |
| eval.value.access | {refused} of {attempts} |
| eval.target.access | All refused |
| eval.met.YES | Met |
| eval.met.NO | Not met |
| eval.by_type_heading | Detection by case type |
| eval.col.type | Case type |
| eval.col.planted | Planted |
| eval.col.caught | Caught |
| eval.col.recall | Recall |
| eval.col.severity_match | Severity as planted |
| eval.limit | We can only check data we receive, and a student who colludes cannot always be caught. These numbers measure the test bed, not the real world. |
| eval.download_md | Download eval_report.md |
| eval.download_json | Download eval.json |
| eval.none | No evaluation run yet. Run make eval, then reload this page. |

Met and Not met are words with an icon, never colour alone; Not met is printed as plainly as Met.
