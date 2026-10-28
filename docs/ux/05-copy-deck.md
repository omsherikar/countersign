# Copy deck

Every user-facing string, keyed by id. Placeholders are `{snake_case}` and map to API fields. Indian-English spelling throughout. No exclamation marks. Hindi strings are marked "for review" and must be checked by a native speaker before the panel.

Suggested implementation: `apps/web/lib/copy.ts` exporting a flat object keyed by these ids, so the review checklist can grep for them.

Counts: when a number is 1, use the singular noun ("1 flag opened", "1 row"). Sentences the api writes (flag `summary`, evidence facts, check `detail.summary`, row problem `message`, a failed batch's `error`) are printed verbatim; the deck mirrors them for review and the browser never rebuilds them.

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
| brand.tagline | Every enrolment, countersigned. |
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
| nav.ledger | Seat ledger |
| nav.upload | Upload |
| nav.enrolments | Enrolments |
| nav.flags | Flags |
| nav.score | Why this score |
| nav.my_enrolment | My enrolment |
| nav.notices | Notices |
| nav.wallet | My proofs |
| nav.privacy | Privacy |
| nav.affiliated | Affiliated institutions |
| nav.degree_print | Degree print |
| nav.data_requests | Data requests |

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
| login.card.student | Student / Ravi Kumar Sharma |
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
| kpi.flags_open | Open flags |
| kpi.flags_open_tip | Flags that are open, waiting for documents or escalated, for {academic_year}. |
| kpi.countersigned | Countersigned |
| kpi.countersigned_value | {pct}% of enrolments fully countersigned |
| kpi.countersigned_tip | Share of checked enrolments where every check that applies is countersigned, the student's own reply included. Waiting for a reply keeps an enrolment out of this share; it never counts against the college. |
| kpi.clear | No source disagrees |
| kpi.clear_value | {pct}% of enrolments |
| kpi.clear_tip | Share of checked enrolments where no source disagrees with the college's upload. A check that is still pending does not count against an enrolment. |
| kpi.not_computed | Not yet computed |
| app.hint.intake | {academic_year} intake |
| app.hint.all_years | All years of study |
| app.all_years_line | {n} students on roll across all years of study |
| section.institutions_ranked | Institutions ranked |
| section.by_state | By state |
| section.by_region | By region |
| section.sources | Sources |
| section.programmes | Programmes |
| section.flags | Flags |
| section.evidence | Evidence |
| section.related | Related enrolments |
| section.history | History |
| section.actions | Actions |
| table.sort_tip | Ranked by open flags, then enrolments |
| table.count.institutions | {total} institutions |
| table.count.enrolments | {total} enrolments |
| table.count.seats | {total} seats |
| table.count.flags | {total} open flags in {institutions} institutions |
| col.name | Name |
| col.permanent_id | Permanent id |
| col.state | State |
| col.region | Region |
| col.type | Type |
| col.programmes | Programmes |
| col.approved_seats | Approved seats |
| col.enrolments | On roll |
| col.enrolments_tip | Every active student on the {academic_year} roll, all years of study. Not comparable with approved seats, which are one year's intake. |
| col.flags_open | Open flags |
| col.integrity | Integrity Index |
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
| col.countersign | Countersign |
| col.flags | Flags |
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
| tab.flags | Flags |
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
| index.label | Integrity Index |
| index.why | Why this score |
| strip.not_checked | Not yet checked |
| strip.score | {passes} of {applicable} |
| strip.score_pending | {passes} of {applicable}, {pending} pending |
| strip.aria | Countersigned {passes} of {applicable}. Identity {s1}, Admission {s2}, Seat {s3}, Studying {s4}, Student {s5}. |
| strip.segment_tip | {check}: {status_word} |
| strip.segment_tip_full | {check}: {status_word} ({source_name}, {checked_at}) |
| check.IDENTITY | Identity |
| check.ADMISSION | Admission |
| check.SEAT | Seat |
| check.STUDYING | Studying |
| check.STUDENT | Student |
| check.status.PASS | Countersigned |
| check.status.FAIL | Not countersigned |
| check.status.PENDING | Pending |
| check.status.NA | n/a |
| check.pending.student | No reply yet |
| check.pending.student_not_sent | Notice not sent yet |
| check.pending.student_expired | No reply (expired) |
| check.pending.unavailable | Awaiting source |
| check.pending.review | Needs review |
| check.pending.results | Awaiting next results |
| check.na_reason.IDENTITY | No APAAR to check: not linked, or an international student |
| check.na_reason.STUDYING | No credits to check: first year, or no APAAR or ABC record |
| check.attempts | The source did not respond on {n} attempts. |
| check.never | Not checked yet |
| source.APAAR | APAAR registry |
| source.COUNSELLING | Counselling list |
| source.SEAT_LEDGER | Seat ledger |
| source.ABC | ABC credits |
| source.STUDENT_NOTICE | Student reply |
| source.DIGILOCKER | DigiLocker |
| source.SII | Study in India |
| source.status.OK | OK |
| source.status.UNAVAILABLE | Unavailable |
| source.status.DISABLED | Disabled |
| source.disabled_detail | Real adapter disabled |
| source.checked | Checked {relative} |
| source.failed | Sources: could not check |
| source.will_retry | Checks against it stay pending, not failed |

Seats against admissions (API_CONTRACT §A2.18). Approved seats are one year's intake. Wherever they appear, `admitted` for the same year ([kpi.admitted], [col.admitted], hinted [app.hint.intake]) appears directly after them, and no ratio, bar, "against" sentence or difference uses any other figure. `enrolments` is every student on roll in every year of study: it is labelled [kpi.enrolments] or [col.enrolments], always carries [app.hint.all_years] or [col.enrolments_tip], comes after Admitted (never between Approved seats and Admitted), and is never divided by, subtracted from or set against approved seats. No screen shows a fill percentage; seats are compared as counts (Approved, Admitted, Seated, Unseated). On `/college`, where the tiles are about one intake, the roll appears only as the line [app.all_years_line].

Percentages. `countersigned_pct` and `clear_pct` arrive rounded to one decimal; print them as sent, dropping a trailing ".0" (0.0 prints "0%", 91.4 prints "91.4%"). Null prints [kpi.not_computed]. The two tiles always appear together, Countersigned first.

Pending words. A PENDING check shows the first word that applies. Student check: on enrolment detail the word follows `detail.notice_state`: [check.pending.student_not_sent] for `NOT_SENT`, [check.pending.student] for `SENT`, [check.pending.student_expired] for `EXPIRED`; wherever there is no `detail`, [check.pending.student]. Other checks: [check.pending.unavailable] when `detail.source_unavailable`; [check.pending.review] when `detail.needs_review`; [check.pending.results] when `detail.awaiting_semester`; otherwise [check.status.PENDING]. Enrolment lists and `/students/me` carry no `detail` (API_CONTRACT §A2.10), so there a pending Student check reads "No reply yet" and any other pending check reads "Pending". PENDING is hollow and never red, whatever its word. The Student check is never n/a, and silence never fails it: with no reply it stays pending (D24).

In `strip.score_pending`, `{pending}` counts pending checks other than Student; when that is 0 the strip shows `strip.score` alone. (A pending Student check waits on the student, not on a source, and is neutral; counting it would print the same words on most rows.) `strip.aria`, `strip.segment_tip` and `strip.segment_tip_full` use the same status words. `strip.segment_tip` is for lists (type and status only); `strip.segment_tip_full` is for enrolment detail. `check.na_reason.*` is the n/a tooltip in lists; on enrolment detail the check's `detail.summary` replaces it.

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
| severity.LOW | Low |
| severity.MEDIUM | Medium |
| severity.HIGH | High |
| flag_status.OPEN | Open |
| flag_status.DOCS_REQUESTED | Documents requested |
| flag_status.CLEARED | Cleared |
| flag_status.ESCALATED | Escalated |
| flag_status.CONFIRMED | Confirmed |
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
| upload_stage.FLAGS | Raising flags |
| upload_stage.DONE | Done |
| upload_source.FILE | File upload |
| upload_source.API | College system |
| upload_source.SEED | Demo seed |
| notice_reply.YES | Confirmed |
| notice_reply.NO | Denied |
| notice_reply.NONE | No reply yet |
| notice_reply.EXPIRED | No reply (expired) |
| notice_channel.EMAIL | Email |
| notice_channel.DIGILOCKER | DigiLocker |
| notice_delivery.QUEUED | Waiting to send |
| notice_delivery.SENT | Sent |
| notice_delivery.FAILED | Not delivered |
| consent_purpose.APAAR_LINK | Using your APAAR to check your enrolment |
| consent_purpose.NOTICE | Notices asking you to confirm an enrolment |
| consent_purpose.CREDENTIAL_SHARE | Sharing your proofs with verifiers |
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

## 5. Flag names and evidence templates

`flag.<TYPE>.name` is the human name shown in tables, filters, chips and the dashboard. Everything else in this section is a reference copy of API_CONTRACT §A2.17: the engines write `summary`, `facts` and `rule_source` into the flag and the web prints them verbatim, in the order sent. The web never rebuilds a summary from these templates.

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
| flag.STUDENT_DENIED.name | Student denied |
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
| flag.STUDENT_DENIED.summary | High | the student replies No on any channel; a No beats a Yes | Student replied "not me" to the notice sent on {sent_date}. |
| flag.STUDENT_DENIED.summary_changed | High; the flag keeps its status | the student changed the reply from No to Yes within 7 days | Student replied "not me" to the notice sent on {sent_date}, then changed the reply to Yes on {changed_date}. |
| flag.GHOST_RING.summary | not raised before Week 3 | | {students} students across {institutions} institutions share {contacts} contact details. |
| flag.ANOMALY.summary | not raised before Week 4 | | {metric} for {programme_code} is {value}, outside the usual range ({low} to {high}) for similar programmes. |

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
| STUDENT_DENIED | Channel | {channel_name} | Student reply |
| | Notice sent | {sent_date} | Student reply |
| | Replied on | {reply_date} | Student reply |
| | Reply changed (only after a change) | Yes on {changed_date} | Student reply |
| | Comment from the student (officers only) | {comment}, or None | Student reply |
| GHOST_RING | Shared mobiles; Shared emails; Shared addresses; Institutions | | Contact graph analysis |
| ANOMALY | Metric; Value; Usual range; Compared with | | Anomaly model |

STUDENT_DENIED: `{channel_name}` is the `notice_channel.*` word of the channel that carried the No. The comment fact carries `audience: "OFFICER"`, so a registrar never receives it (D24). When the student changes a No to a Yes, the flag keeps its status (only an officer resolves it), its evidence is refreshed with `summary_changed` and the Reply changed fact, and the case history gains a System row (§6).

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
| flag.STUDENT_DENIED.rule | Student reply |
| flag.GHOST_RING.rule | Contact graph analysis |
| flag.ANOMALY.rule | Anomaly model, Week 4 |

QUOTA_BREACH counts `{admitted}` (enrolments by route), because assigned seats can never exceed a pool's capacity. LATE_REFILL cites the last admission date from the AICTE admission schedule (kept in `rules.yaml` `cutoff_dates`; evidence never names the file), not APH cl. 6.13(f), which is the lateral-entry vacancy clause.

Rules for every template: no verdict words (never "fraud", "fake", "illegal"); claimed figure first, source figure second; the period in brackets; one sentence.

## 6. Case actions

Officer flag detail (`/aicte/cases/[flagId]`, `/ro/cases/[flagId]`) and the registrar's flag detail (`/college/flags/[flagId]`), from `POST /flags/{id}/actions {action, note, due_date?, assignee_id?}`, `POST /flags/{id}/response` and the `history` of `GET /flags/{id}` (D25).

Actions and sheets

| id | text |
|---|---|
| case.clear | Clear flag |
| case.request_docs | Request documents |
| case.escalate | Escalate |
| case.confirm | Confirm |
| case.reopen | Reopen |
| case.note | Add note |
| case.assign | Assign |
| case.cancel | Cancel |
| case.note_label | Note (shown to the college) |
| case.note_required | Add a note before you continue. |
| case.clear_confirm | Clear this flag? Your note is shown to the college and kept in the case history. |
| case.request_docs_prompt | What should the college send? Be specific, e.g. "Admission register extract for CSE, 2026-27". |
| case.request_docs_email | Every registrar account of {institution_name} gets an email with your request. |
| case.request_docs_send | Send request |
| case.due_date | Reply by (optional) |
| case.due_date_hint | Shown to the college with your request. |
| case.escalate_prompt | Why does this need a senior officer? |
| case.escalate_note | After escalation only an AICTE officer can clear it, confirm it or request documents. Regional officers can still add notes. |
| case.confirm_confirm | Confirming records this flag as a confirmed irregularity against {institution_name}. Nothing is deleted; the enrolment keeps its status. Your note becomes part of the formal record. |
| case.confirm_revokes | Any enrolment proof AICTE issued for this enrolment is revoked now. A verifier who checks it will see Revoked. |
| case.reopen_prompt | Why reopen this case? It goes back to Open, and the earlier decision stays in the history. |
| case.assign_label | Assign to |
| case.assign_search | Search officers by name |
| case.assign_me | Assign to me |
| case.assign_none | Remove assignee |
| case.assign_option | {name}, {role_word} |
| case.assign_empty | No officer matches "{q}". |
| case.assignee_none | Unassigned |
| case.cleared_toast | Flag cleared. {institution_name} can see your note. |
| case.docs_toast | Request sent to the registrar. |
| case.escalated_toast | Escalated. |
| case.confirmed_toast | Recorded as confirmed. |
| case.reopened_toast | Reopened. The flag is Open again. |
| case.note_toast | Note added. |
| case.assigned_toast | Assigned to {name}. |
| case.unassigned_toast | Assignee removed. |
| case.back | Back to queue |

Case status lines

| id | text |
|---|---|
| case.response_badge | Response received |
| case.response_badge_tip | The college responded on {date}. The flag stays at Documents requested until an officer decides. |
| case.due_line | Reply due by {due_date} |
| case.due_passed | Reply date {due_date} has passed |
| case.escalated_ro | Only AICTE can act on an escalated flag. You can still add a note. |
| case.closed_line | This case is closed. Only an AICTE officer can reopen it. |
| case.closed_admin | This case is closed. Reopen it to act on it again. |
| case.attachment | {filename}, {size} |
| case.attachment_download | Download {filename} |
| case.attachments_logged | Each download is logged. |

History (one row per `history[]` entry, oldest first, after [case.history.opened])

| id | text |
|---|---|
| case.history.opened | Flag opened |
| case.history.col.when | When |
| case.history.col.who | Who |
| case.history.col.what | What |
| case.history.who | {actor_name}, {role_word} |
| case.history.system | System |
| case.history.REQUEST_DOCS | Requested documents |
| case.history.COLLEGE_RESPONSE | Responded |
| case.history.ESCALATE | Escalated |
| case.history.CLEAR | Cleared the flag |
| case.history.CONFIRM | Confirmed the flag |
| case.history.NOTE | Added a note |
| case.history.ASSIGN | Assigned to {assignee_name} |
| case.history.ASSIGN_none | Removed the assignee |
| case.history.REOPEN | Reopened the flag |
| case.history.SYSTEM_NOTE | Evidence updated after the decision |
| case.history.status_change | {from_word} to {to_word} |
| case.history.due | Reply by {due_date} |
| case.system_note.reply_changed | The student changed the reply from No to Yes on {changed_date}. The flag keeps its status until an officer decides. |

A history row reads When (`at`, `14 Jul 2026, 09:31 IST`), Who (`case.history.who` with `{role_word}` from `shell.role.*`, or `case.history.system` when the actor is null), What (the `case.history.<ACTION>` words, then `case.history.status_change` in small text when `from_status` and `to_status` differ, then `case.history.due` when `due_date` is set), and under it the note in quotes and one `case.attachment` link per file. A SYSTEM_NOTE row prints its `note` verbatim when the api sends one other than `case.history.SYSTEM_NOTE`; the deck mirrors the one other note the engines write, `case.system_note.reply_changed`. Status words come from `flag_status.*`.

Which actions show (D25). AICTE officer: on Open and Documents requested, Clear flag, Request documents, Escalate, Confirm, Add note, Assign; on Escalated, the same without Escalate; on Cleared and Confirmed, Reopen, Add note, Assign, with `case.closed_admin`. Regional officer, for its region: on Open and Documents requested, the same as the AICTE officer; on Escalated, only Add note, with `case.escalated_ro`; on Cleared and Confirmed, Add note and Assign, with `case.closed_line`. Registrar: only Respond, and only while the flag is Documents requested. University: none. Every sheet needs a note except Assign; `case.note_required` shows under the empty field. The Confirm sheet shows `case.confirm_confirm`, then `case.confirm_revokes` when the flag names an enrolment (D25: confirming revokes any active proof for that enrolment and changes nothing else). A 409 `FLAG_TRANSITION_INVALID` shows [err.FLAG_TRANSITION_INVALID] in the sheet and refetches the flag.

College response

| id | text |
|---|---|
| college.respond | Respond |
| college.respond_heading | Respond to the document request |
| college.request_line | {role_word} asked on {requested_date}: |
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
| college.respond_sent | Sent to the officer. You will see their decision here. |
| college.respond_waiting | You responded on {date}. The flag stays at Documents requested until the officer decides. |
| college.respond_more | Send more documents |
| college.other_institution | another institution in {state_name} |

`college.respond_file_type` and `college.respond_file_size` are checked in the browser before anything is sent; the server answers the same cases with 415 [err.ATTACHMENT_TYPE] and 413 [err.ATTACHMENT_TOO_LARGE]. `{size}` in `case.attachment` reads like `412 KB` or `1.8 MB`.

Email to the registrar when documents are requested (sent to every registrar account of the college, D25)

| id | text |
|---|---|
| email.docs_request.subject | Documents requested by AICTE: {flag_name}, {where} |
| email.docs_request.body | {role_word} has asked {institution_name} for documents about a flag. Flag: {flag_name}, {where}. Evidence: {summary} Request: "{note}" {due_sentence}Sign in to Countersign and open the flag to respond: {link}. Attach PDF, PNG or JPEG files, up to 3, 5 MB each. Nothing about your college or its students has changed; an officer decides after reading your response. This email went to every registrar account of your college. |
| email.docs_request.due | Please reply by {due_date}. |

`{where}` is `{programme_code}, {academic_year}`, or `{academic_year}` alone for a flag without a programme. `{summary}` is the summary the registrar sees (the redacted one for a cross-institution duplicate). `{due_sentence}` is `email.docs_request.due` followed by a space, or nothing when no date was set. `{link}` is `{WEB_ORIGIN}/college/flags/{flag_id}`. The email names no student and no officer.

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
| upload.source_waiting | {source_name} did not respond for {n} checks. Those checks stay pending, not failed, and run again at the next recheck or the next upload of those rows. |
| upload.same_file | This file was already uploaded on {uploaded_date}. Uploading it again changes nothing. |
| upload.ignored_columns | Columns not recognised and ignored: {columns} |
| upload.done_heading | Upload processed |
| upload.done_summary | {ok} rows accepted · {seated} seats assigned · {unseated} unseated · {flags} flags opened |
| upload.done_changes | {created} new · {updated} updated · {unchanged} unchanged · {withdrawn} withdrawn · {transferred} transferred · {released} seats released |
| upload.done_note | Flags are for review by an officer. A flag does not remove or change any enrolment. |
| upload.failed | This upload could not be finished. |
| upload.failed_earlier | Earlier uploads are unchanged. |
| upload.upload_again | Upload a file |
| upload.view_ledger | View seat ledger |
| upload.view_enrolments | View enrolments |
| upload.view_flags | View flags |
| college.no_upload_yet | Last upload: none yet. |
| last_upload.line | Last upload {uploaded_date}: {rows} rows, {errors} with errors · {status_word} |

`upload.done_summary` takes `{ok}` = `counts.accepted`, `{seated}`, `{unseated}` and `{flags}` = `counts.flags_raised`. `upload.done_changes` takes the `counts` keys of the same names. `upload.failed` is followed by the batch `error` sentence verbatim, then `upload.failed_earlier`. `upload.same_file` shows when `same_file_as` is set, with its `uploaded_at` as the date. `last_upload.line` reads the institution's `last_upload` (`rows`, `errors`, `status`).

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
| notice.email_subject | {institution_name} says you joined {programme_short}. Is that right? |
| notice.email_body | {institution_name} has told AICTE that you joined {programme_name} for {academic_year}. Please confirm whether this is right. It takes one tap: {link}. If this is not you, tell us and an AICTE officer will look into it. This link works until {expires_date}. You will not be asked for a password or any payment. |
| notice.digilocker | {institution_name} says you joined {programme_short} ({academic_year}). Is that right? |
| notice.headline | {institution_name} says |
| notice.claim | you joined {programme_name} |
| notice.meta | Academic year {academic_year} · Year {year_of_study} |
| notice.uploaded_line | They uploaded this on {uploaded_date} for {id_label} {id_masked}. |
| notice.question | Is that right? |
| notice.yes | Yes, that is right |
| notice.no | No, that is not me |
| notice.next_step | If you say no, an AICTE officer will look into it. Nothing changes for you until then. |
| notice.what_is_this_link | What is this? |
| notice.what_is_this | Countersign is AICTE's way of checking that colleges report only students who really joined. Your college uploaded your enrolment; we are asking you to countersign it. Your answer is recorded with the date. Only the masked id you see here is stored with it. |
| notice.yes_done | Thank you. Your enrolment at {institution_name} is now countersigned by you. |
| notice.no_confirm | You are telling AICTE that you did not join {institution_name}. An officer will look into it. Anything we should know? (optional) |
| notice.no_comment_label | Anything we should know? |
| notice.no_submit | Send |
| notice.no_done | Thank you. An AICTE officer will look into this. Nothing changes for you until they do. |
| notice.answered | You replied "{reply}" on {responded_date}. |
| notice.change | Change my answer |
| notice.expired | This link has expired. No reply was recorded, and that does not count against you. To reply now, ask your college or AICTE to send a new notice. |
| notice.invalid | This link is not valid. Check that you opened the whole link from your message, or ask your college to send a new notice. |
| notice.page_title | Notice from {institution_name} |
| notice.lang_label | Language |
| notice.sending | Sending |
| notice.no_comment_hint | Only AICTE officers read this. Your college does not see it. |
| notice.no_cancel | Go back |
| notice.yes_next | If the other checks agree too, an enrolment proof you can share appears in My proofs. |
| notice.see_proofs | See my proofs |
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

`{reply}` takes `notice.reply.*`. `{id_label}` is "APAAR" or [provisional.label]. `{change_until_date}` is 7 days after the first reply. Page states and the error codes behind them: 404 `NOTICE_NOT_FOUND` (same body for an invalid and an unknown token) shows `notice.invalid`; 410 `NOTICE_EXPIRED` shows `notice.expired`; 409 `NOTICE_ALREADY_CHANGED` shows `notice.change_used`; 429 shows `notice.rate_limited`.

Hindi (for review by a native speaker before the panel)

| id | text |
|---|---|
| notice.digilocker.hi | {institution_name} का कहना है कि आपने {programme_short} ({academic_year}) में प्रवेश लिया है। क्या यह सही है? |
| notice.headline.hi | {institution_name} का कहना है |
| notice.claim.hi | कि आपने {programme_name} में प्रवेश लिया है |
| notice.meta.hi | शैक्षणिक वर्ष {academic_year} · वर्ष {year_of_study} |
| notice.question.hi | क्या यह सही है? |
| notice.yes.hi | हाँ, यह सही है |
| notice.no.hi | नहीं, यह मैं नहीं हूँ |
| notice.next_step.hi | अगर आप "नहीं" चुनते हैं, तो AICTE का एक अधिकारी इसकी जाँच करेगा। तब तक आपके लिए कुछ नहीं बदलता। |
| notice.yes_done.hi | धन्यवाद। {institution_name} में आपका नामांकन अब आपके द्वारा प्रमाणित है। |
| notice.no_done.hi | धन्यवाद। AICTE का एक अधिकारी इसकी जाँच करेगा। तब तक आपके लिए कुछ नहीं बदलता। |
| notice.expired.hi | यह लिंक समाप्त हो गया है। कोई उत्तर दर्ज नहीं हुआ, और इसे आपके विरुद्ध नहीं गिना जाता। अभी उत्तर देने के लिए अपने कॉलेज या AICTE से नई सूचना भेजने को कहें। |
| notice.page_title.hi | {institution_name} की सूचना |
| notice.lang_label.hi | भाषा |
| notice.uploaded_line.hi | कॉलेज ने यह जानकारी {uploaded_date} को {id_label} {id_masked} के साथ अपलोड की। |
| provisional.label.hi | अस्थायी आईडी |
| notice.what_is_this_link.hi | यह क्या है? |
| notice.what_is_this.hi | Countersign से AICTE यह जाँचता है कि कॉलेज केवल उन्हीं विद्यार्थियों की जानकारी भेजें जिन्होंने सच में प्रवेश लिया है। आपके कॉलेज ने आपका नामांकन अपलोड किया है, और हम आपसे इसकी पुष्टि करने को कह रहे हैं। आपका उत्तर तारीख के साथ दर्ज होता है। उसके साथ केवल वही छिपी हुई आईडी रखी जाती है जो आप यहाँ देख रहे हैं। |
| notice.sending.hi | भेजा जा रहा है |
| notice.no_confirm.hi | आप AICTE को बता रहे हैं कि आपने {institution_name} में प्रवेश नहीं लिया। एक अधिकारी इसकी जाँच करेगा। क्या आप कुछ और बताना चाहेंगे? (वैकल्पिक) |
| notice.no_comment_label.hi | क्या आप कुछ और बताना चाहेंगे? |
| notice.no_comment_hint.hi | इसे केवल AICTE के अधिकारी पढ़ते हैं। आपका कॉलेज इसे नहीं देखता। |
| notice.no_submit.hi | भेजें |
| notice.no_cancel.hi | वापस जाएँ |
| notice.yes_next.hi | अगर बाकी जाँचें भी सहमत हैं, तो एक नामांकन प्रमाण, जिसे आप साझा कर सकते हैं, "मेरे प्रमाण" (My proofs) में दिखेगा। |
| notice.see_proofs.hi | मेरे प्रमाण देखें |
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
| consent.notice.hi | उत्तर देकर आप AICTE को इस नामांकन के साथ आज की तारीख में अपना उत्तर दर्ज करने की अनुमति देते हैं। आपका उत्तर AICTE के अधिकारियों और {institution_name} को केवल "पुष्टि की" या "अस्वीकार किया" के रूप में दिखता है, किसी और व्यक्तिगत जानकारी के बिना। अगर आप टिप्पणी लिखते हैं, तो उसे केवल AICTE के अधिकारी देखते हैं। |
| err.NETWORK.hi | Countersign से संपर्क नहीं हो सका। अपना इंटरनेट कनेक्शन जाँचें और फिर कोशिश करें। |
| err.INTERNAL.hi | हमारी ओर से कुछ गड़बड़ हुई। फिर कोशिश करें। |
| err.retry.hi | फिर कोशिश करें |

With Hindi on, every string on the notice page uses its `.hi` row, states and errors included; a string without one falls back to English. Institution and programme names print as sent. `{reply}` takes `notice.reply.*.hi`; `{id_label}` is "APAAR" or [provisional.label.hi]. Dates keep the `14 Jul 2026` form. "Privacy" and "My proofs" stay in English inside the Hindi strings because the student portal shows them in English.

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
| notices.reply_hint | To reply, open the link we sent you by email or in DigiLocker. It works until {expires_date}. |
| notices.denied_line | An AICTE officer is looking into this. Nothing changes for you until they decide. |
| notices.consent_off | You turned off new notices on {withdrawn_date}. Notices already sent can still be answered. |

`{channel_words}` is "email", "DigiLocker" or "email and DigiLocker". The list cannot open a notice: only a hash of each link is stored (D23), so an unanswered notice shows `notices.reply_hint` instead of a link. `notices.denied_line` sits under a No reply and is the only place a student learns that a case exists.

Student home (`/student`)

| id | text |
|---|---|
| student.check_student_sent | The last check is your own reply. We sent you a notice on {sent_date}. Open it from your email or DigiLocker to reply. |
| student.check_student_expired | Your notice expired without a reply. That does not count against you. |
| student.check_student_denied | You told us this is not you. An AICTE officer is looking into it. Nothing changes for you until they decide. |
| student.consent_change | {tip}. To change it, go to your Privacy page. |

Under the strip the home page shows one line by the enrolment's newest notice: none sent, [student.check_student_pending]; sent and unanswered, `student.check_student_sent`; expired, `student.check_student_expired`; answered No, `student.check_student_denied`; answered Yes, nothing. `student.consent_change` replaces the consent tooltip line the web kept outside the deck.

Wallet

| id | text |
|---|---|
| wallet.heading | My proofs |
| wallet.lead | Proofs you can show an employer or anyone else who needs to check your enrolment. You choose what they see. |
| wallet.kind.ENROLMENT | Enrolment proof |
| wallet.kind.DEGREE | Degree proof |
| wallet.issued_by | Issued by Countersign for {institution_name} |
| wallet.issued_by_degree | Issued by Countersign for {university_name} |
| wallet.issued_on | Issued {issued_date} |
| wallet.valid_until | Valid until {expires_date} |
| wallet.status.active | Active |
| wallet.status.revoked | Revoked |
| wallet.status.expired | Expired |
| wallet.share | Share proof |
| wallet.details | Show details |
| wallet.hide_details | Hide details |
| wallet.details_heading | What this proof holds |
| wallet.proof_id | Proof id {short_id} |
| wallet.not_issued_heading | No enrolment proof yet |
| wallet.not_issued.reply | Your proof is issued after you reply Yes to the notice we sent you and the other checks agree. |
| wallet.not_issued.checks | You confirmed your enrolment. Your proof is issued once no source disagrees and any review of this enrolment is finished. You do not need to do anything. |
| wallet.not_issued.denied | You told us you did not join {institution_name}, so no proof is issued for this enrolment. |
| wallet.revoked_line | Withdrawn on {revoked_date}. Anyone who checks this proof now sees Revoked. |
| wallet.revoked_reason.ENROLMENT_WITHDRAWN | Your college reported that you left this programme. |
| wallet.revoked_reason.ENROLMENT_TRANSFERRED | Your college reported that you moved to another institution. |
| wallet.revoked_reason.FLAG_CONFIRMED | AICTE reviewed this enrolment and withdrew the proof. |
| wallet.revoked_reason.ADMIN | AICTE withdrew this proof. |
| wallet.revoked_help | If you think this is wrong, ask for a correction from your Privacy page. |
| wallet.expired_line | This proof ended on {expires_date}. If you are still enrolled, a proof for your next academic year is issued once its checks agree. |
| wallet.share_heading | Share this proof |
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
| wallet.field.countersigned | Checks that agree (countersigned) |
| wallet.field.countersigned_hint | Which of the five checks agree with your college's record, and the date. |
| wallet.field.university | University |
| wallet.field.year_of_award | Year of award |
| wallet.countersigned_value | {checks}, as of {date} |
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
| wallet.qr_alt | QR code for your proof. The same code is written under it. |
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
| wallet.history_empty | You have not shared this proof yet. |
| wallet.history_note | AICTE records when your proof is checked, but not who checked it. |
| student.heading | My enrolment |
| student.card_lead | {institution_name} says you joined {programme_name} |
| student.strip_caption | {passes} of {applicable} sources agree |
| student.check_student_pending | The last check is your own reply. AICTE sends you a notice by email or DigiLocker to confirm this enrolment. |
| privacy.student_line | Only you can see your email and mobile here. Officers see masked ids only. |
| privacy.how_link | How my data is used |

Share sheet fields (D26): an enrolment proof lists 8 fields in this order: name, institution, programme, academic year, year of study, date of birth, APAAR (masked), countersigned. Institution and programme are ticked and locked; the other six start unticked. `{m}` in `wallet.shares` is the response's `total` (8 for an enrolment proof) and `{n}` counts the ticked fields, locked ones included, so the fewest a share can show is "Shares 2 of 8 fields". A degree proof lists the fields its `disclosable` claims name, using the `wallet.field.*` words. Each row shows the value that would be shared; the countersigned value is `wallet.countersigned_value`, with `{checks}` the `check.*` words joined with commas and a final "and" ("Identity, Admission, Seat and Student, as of 28 Oct 2026").

The code under the QR is 6 groups of 4 letters and digits, printed as sent (`K7PQ-3M2X-9ZAB-4TNE-W8RC-6HDF`). `{verify_url}` is the host and path of the verify page without the code ("localhost:3000/verify"). The countdown counts down from `expires_at`; `wallet.expires_in_sr` is announced at 5 minutes and at 1 minute only. In the history, a share's first row is `wallet.history.created`; each check of it prints `wallet.history_item` (D27), with `wallet.history_item_date` when it was not today, or `wallet.history_item_more` once `verify_count` is above 1; a share that expired unchecked prints `wallet.history.unused`.

No proof yet: for an active enrolment with no enrolment proof, the card reads `wallet.not_issued_heading` and one line by the Student check: pending, `wallet.not_issued.reply`; countersigned, `wallet.not_issued.checks`; not countersigned, `wallet.not_issued.denied`. It never names a flag or a failed check. A revoked proof prints `wallet.revoked_line`, then the `wallet.revoked_reason.*` sentence for its `revoked_reason` (a reason the deck does not list prints `wallet.revoked_reason.ADMIN`), then `wallet.revoked_help`; it has no Share button.

## 9. Consent texts (DPDP)

Each text is stored verbatim in `consents.notice_text` when the consent is recorded.

| id | purpose | text |
|---|---|---|
| consent.apaar_link | APAAR_LINK | I allow AICTE to use my APAAR id to check that my enrolment at {institution_name} is genuine. AICTE will look up my id with the APAAR registry, the counselling allotment list and the Academic Bank of Credits. Only the last four digits of my id are shown to officers. To unlink my APAAR later, I can ask from my Privacy page; my college then uploads my enrolment again without it. Checks already made stay on record, and my admission is not affected. |
| consent.notice | NOTICE | By replying, you let AICTE record your answer with today's date against this enrolment. Your answer is shown to AICTE officers and to {institution_name} as "Confirmed" or "Denied", with no other personal detail. If you add a comment, only AICTE officers see it. |
| consent.credential_share | CREDENTIAL_SHARE | I am creating a proof that shows only the fields I ticked. Whoever scans it sees those fields, who issued the proof and when, and nothing else. The proof works for 10 minutes. AICTE records when it is created and when it is checked, but not who checks it. |
| consent.withdraw.NOTICE | NOTICE | Stop new notices? You will get no new notices about your enrolments. Notices already sent can still be answered, and replies you gave stay on record. |
| consent.withdraw.CREDENTIAL_SHARE | CREDENTIAL_SHARE | Stop sharing? Every QR or link you created that still works stops working now. Your proofs stay in your wallet, and sharing again asks for your consent again. |
| consent.unlink_apaar | APAAR_LINK | Unlinking your APAAR is a correction request, because your college must upload your enrolment again without it. Your admission is not affected, and checks already made stay on record. |
| consent.upload_declaration | APAAR_LINK via college | (identical to upload.declaration) |

`consent.withdraw.*` and `consent.unlink_apaar` are confirmations on the Privacy page, not stored texts. Only NOTICE and CREDENTIAL_SHARE can be withdrawn there (`POST /students/me/consents/{purpose}/withdraw`, D30). APAAR_LINK has no Withdraw button: `consent.unlink_apaar` explains why and offers [privacy.unlink_apaar], which opens a Correction request with [privacy.request.unlink_prefill]. Each stored text is kept with its `notice_version`; the Privacy page shows the exact text the student agreed to, not today's version.

## 10. Verifier

Public pages, no sign-in, rate limited (D27, D32). They never offer search and never show a field the student did not share.

Entry page (`/verify`)

| id | text |
|---|---|
| verify.bar | Verify a proof |
| verify.heading | Verify an enrolment or degree proof |
| verify.lead | Scan the QR on the document, or type the code printed under it. |
| verify.scan | Scan with camera |
| verify.scan_stop | Stop camera |
| verify.scan_hint | Hold the QR inside the frame. |
| verify.scan_unsupported | This browser cannot scan QR codes. Type the code instead. |
| verify.camera_denied | The camera is not allowed for this page. Type the code instead, or allow the camera in your browser settings. |
| verify.code_label | Code |
| verify.placeholder | e.g. K7PQ-3M2X-9ZAB-4TNE-W8RC-6HDF |
| verify.code_hint | 24 letters and digits. Dashes and spaces are optional. |
| verify.code_format | A code has 24 letters and digits, in 6 groups of 4. Check it and try again. |
| verify.check | Check |
| verify.checking | Checking |
| verify.paste_link | Have the proof text instead of a code? |
| verify.paste_label | Proof text |
| verify.paste_hint | Paste the full text you were given. It is long and starts with eyJ. |
| verify.paste_check | Check proof text |
| verify.what | What you will see: whether the proof is valid, who issued it, and only the fields the student chose to share. Never a full APAAR number, and no search: only a proof a student shares can be checked. |
| verify.about_link | What is Countersign? |
| verify.about | Countersign is AICTE's way of checking that every enrolment a college reports is backed by independent sources: the APAAR registry, the counselling allotment list, the seat ledger, the Academic Bank of Credits and the student's own reply. A proof shows that check, and only the fields the student chose to share. |
| verify.rate_limited | Too many checks from this network in a minute. Try again in {seconds} s. |

Result page (`/verify/[code]`, and pasted proof text)

| id | text |
|---|---|
| verify.result_title | Proof check |
| verify.state.VALID | Valid |
| verify.state.REVOKED | Revoked |
| verify.state.EXPIRED | Expired |
| verify.state.INVALID | Not valid |
| verify.kind.ENROLMENT | Enrolment proof |
| verify.kind.DEGREE | Degree proof |
| verify.valid | Valid proof |
| verify.valid_sub | Issued by Countersign for {institution_name} on {issued_date}. |
| verify.signature | Signature checked against Countersign's published keys. |
| verify.revocation | Revocation checked just now. |
| verify.revocation_at | Revocation checked at {time}. |
| verify.holder_bound | The student shared this proof for this check, from their own wallet. |
| verify.pasted_note | Checked from pasted text, so Countersign cannot tell whether it was made for you. Ask the student for a fresh code if that matters. |
| verify.shared_heading | Shared by the student |
| verify.not_shared | Nothing else is shown. The student chose what to share. |
| verify.revoked | This proof has been revoked. |
| verify.revoked_sub | AICTE withdrew it, for example because the student left the programme. It no longer confirms anything. Ask the student about it. |
| verify.expired | This proof has expired. |
| verify.expired_sub | A shared code works for 10 minutes, and every proof has an end date. Ask the student for a new one. |
| verify.invalid | This is not a valid Countersign proof. |
| verify.invalid_sub | The code may be mistyped, or the proof was changed after it was issued. Check the code and try again; if it still fails, do not rely on it. |
| verify.check_another | Check another proof |

Degree QR result (`/verify/d/[jws]`)

| id | text |
|---|---|
| verify.degree_valid | Valid degree proof |
| verify.degree_sub | Signed by Countersign for {university_name}. |
| verify.degree_heading | On the degree |
| verify.degree_printed | Printed proofs are not tied to a phone. Compare the name with the person's photo ID. |
| verify.degree_wallet | This QR carries a short signed summary of the degree. The graduate's wallet holds the full proof. |
| verify.degree_revoked_sub | AICTE withdrew this degree proof. It no longer confirms anything. Ask the graduate about it. |

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
| verify.field.countersigned | Checks that agree |
| verify.field.university | University |
| verify.field.year_of_award | Year of award |
| verify.field.proof_id | Proof id |

Result states (D27): the heading, a badge with icon and `verify.state.*` word, and the sub line. VALID shows `verify.kind.*`, `verify.valid_sub`, `verify.signature`, `verify.revocation` (or `verify.revocation_at` when `status_checked_at` is more than a minute old), `verify.holder_bound` when `holder_bound` is true, then `verify.shared_heading` with the `disclosed` fields as label and value pairs in the order sent, then `verify.not_shared`. REVOKED, EXPIRED and INVALID show the heading, the sub line and `verify.check_another`, and no fields. A pasted proof (`POST /verify`) adds `verify.pasted_note` to a VALID result, because its share code is reported, not enforced. A degree QR shows `verify.degree_valid`, `verify.degree_sub`, `verify.signature`, `verify.revocation`, `verify.degree_heading` with its fields, `verify.degree_printed` and `verify.degree_wallet`; revoked uses `verify.revoked` with `verify.degree_revoked_sub`. A 404 `PRESENTATION_NOT_FOUND` shows [err.PRESENTATION_NOT_FOUND]; a 429 shows `verify.rate_limited` with a countdown. Values print as sent: the APAAR is always `XXXX XXXX 4417`, never more.

## 11. University

| id | text |
|---|---|
| university.heading | Affiliated institutions |
| degree.heading | Degree print |
| degree.lead | Graduates of your affiliated institutions. Issue a degree proof, then print the insert with the masked APAAR and a QR anyone can scan. |
| degree.search | Search by name or the last four digits of APAAR |
| degree.count | {total} graduates |
| degree.col.student | Graduate |
| degree.col.year_of_award | Year of award |
| degree.col.proof | Degree proof |
| degree.status.none | Not issued |
| degree.status.active | Issued {issued_date} |
| degree.status.revoked | Revoked |
| degree.issue | Issue degree proof |
| degree.issue_heading | Issue a degree proof for {student_name}? |
| degree.issue_body | Countersign signs a degree proof for {programme_name} ({year_of_award}) and puts it in the graduate's wallet. You can then print the insert. |
| degree.issue_note | The graduate can see this proof in their wallet and choose what they share from it. |
| degree.issue_revocation_note | If the degree is withdrawn later, AICTE revokes the proof and anyone who scans the printed QR sees Revoked. |
| degree.issue_confirm | Issue proof |
| degree.issue_cancel | Cancel |
| degree.issuing | Issuing |
| degree.issued_toast | Degree proof issued. It is in {student_name}'s wallet. |
| degree.print_insert | Print degree insert |
| degree.pdf | Download PDF |
| degree.pdf_note | A sample A4 insert with the same QR, for filing or sending. |
| degree.provisional_note | This graduate has no APAAR, so the insert prints the provisional id. |
| degree.print_title | Degree insert, {student_name} |
| degree.print_hint | Print on A4, portrait. Navigation and colours are left out of the printout. |
| degree.print | Print |
| degree.print_back | Back to graduates |
| degree.print.accompanies | This insert accompanies the degree awarded to |
| degree.print.name | Name |
| degree.print.programme | Programme |
| degree.print.institution | Institution |
| degree.print.year | Year of award |
| degree.print.apaar | APAAR |
| degree.print.provisional | Provisional id |
| degree.apaar_line | APAAR {apaar_masked} |
| degree.scan_line | Scan to verify at {verify_url} |
| degree.print.proof_id | Proof id {short_id} |
| degree.print.issued | Proof issued {issued_date} |
| degree.print.signed | Signed by Countersign for {university_name}. A changed insert does not verify. |

`/university/degrees` lists `GET /university/graduates?q&page` (D28): Graduate (name, linked to nothing), [col.apaar] (masked APAAR or provisional id), [col.institution], [col.programme], `degree.col.year_of_award`, `degree.col.proof` (`degree.status.*` word with an icon). Row action: `degree.issue` when there is no active degree proof (also after a revoked one), else `degree.print_insert` and `degree.pdf`. The issue sheet shows `degree.issue_heading`, `degree.issue_body`, `degree.issue_note`, `degree.issue_revocation_note` (and `degree.provisional_note` for a graduate without APAAR), then `degree.issue_confirm` and `degree.issue_cancel`. 409 `CREDENTIAL_NOT_ELIGIBLE` shows [err.CREDENTIAL_NOT_ELIGIBLE]; 409 `CREDENTIAL_REVOKED` on print shows [err.CREDENTIAL_REVOKED].

Print view text under the QR: `degree.print.proof_id` and `degree.scan_line`, with `{verify_url}` the verify page's host and path ("localhost:3000/verify"). The QR's own link (`/verify/d/{jws}`, about 350 characters) is never printed as text.

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
| admin.reset_confirm | Reset the demo data? Every upload, flag and reply since the last seed is removed. Seeded users and passwords stay the same. |
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
| score.heading | Integrity Index |
| score.value | {index} of 100 |
| score.rank | Rank {rank} of {of} nationally · computed {computed_date} |
| score.start | Start at 100, minus: |
| score.raise | What would raise it: {hint} |
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
| admin.requests.filter.status | Status |
| admin.requests.filter.kind | Request |
| admin.requests.col.received | Received |
| admin.requests.col.kind | Request |
| admin.requests.col.student | Student |
| admin.requests.col.details | Details |
| admin.requests.col.status | Status |
| admin.requests.col.resolved | Resolved |
| admin.requests.resolve | Resolve |
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
| admin.requests.erasure_retention | Enrolment records, their checks, flags and the audit log are kept for the period the law requires, so they cannot be erased on request. Contact details and anything not needed for that record can be removed. |
| admin.requests.erasure_reply | We cannot erase your enrolment record, its checks or its history, because AICTE must keep them for the period the law requires. Everything shown to officers stays masked, and you can see who views your record on your Privacy page. We have removed: |
| admin.requests.submit | Send reply |
| admin.requests.sending | Sending |
| admin.requests.resolved_toast | Request resolved. The student can see your reply. |
| admin.requests.empty | No open data requests. |
| admin.requests.empty_filtered | No requests match these filters. |

The queue lists Correction and Erasure requests (an Access request is fulfilled at once and never waits here), Open first, oldest first. The Student cell is the name with the masked APAAR or provisional id under it; Details prints the student's text verbatim, wrapped. `{kind_word}` is `data_request_kind.*` in lower case. The resolve sheet shows `admin.requests.correction_hint` for a correction (plus `admin.requests.unlink_hint` when the text asks to unlink an APAAR), and for an erasure shows `admin.requests.erasure_retention` and prefills the reply with `admin.requests.erasure_reply`, which the officer completes. Outcome words map to `status`: Done is `DONE`, Decline is `REJECTED`; the student then sees `data_request_status.*`.

## 13. Errors (by API error code)

| id | text |
|---|---|
| err.UNAUTHENTICATED | Your session has ended. Sign in again. |
| err.INVALID_CREDENTIALS | Email or password is incorrect. |
| err.FORBIDDEN | This page is for {required_roles_words}. You are signed in as {role_word}. |
| err.FORBIDDEN_redirect | That page is for {required_roles_words}. You are signed in as {role_word}. |
| err.NOT_FOUND_institution | This institution is not in your scope or does not exist. |
| err.NOT_FOUND_upload | This upload is not in your scope or does not exist. |
| err.NOT_FOUND_enrolment | This enrolment is not in your scope or does not exist. |
| err.NOT_FOUND_flag | This flag is not in your scope or does not exist. |
| err.NOT_FOUND_generic | We could not find that. |
| err.VALIDATION_ERROR | Check the highlighted fields. |
| err.RATE_LIMITED | Too many attempts. Try again in {seconds} s. |
| err.SOURCE_UNAVAILABLE | {source_name} did not respond. This check stays pending until a recheck or the next upload. |
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
| err.CREDENTIAL_NOT_ELIGIBLE | A proof cannot be issued for this record yet. Refresh the page to see its current status. |
| err.CREDENTIAL_REVOKED | This proof has been withdrawn, so it cannot be shared or printed. |
| err.PRESENTATION_NOT_FOUND | No proof matches this code. Check each group of four and try again. |
| err.FLAG_TRANSITION_INVALID | This action is not possible from the flag's current status. The page now shows the latest status. |
| err.ATTACHMENT_TOO_LARGE | A file is larger than 5 MB. Attach a smaller copy, for example a scan at a lower resolution. |
| err.ATTACHMENT_TYPE | Only PDF, PNG and JPEG files can be attached. |
| err.INTERNAL | Something went wrong on our side. Try again. |
| err.NETWORK | Could not reach Countersign. Check your connection and try again. |
| err.ref | Ref: {code} |
| err.retry | Try again |
| err.back_overview | Back to overview |
| err.go_home | Go to my overview |
| err.tile_failed | Could not load |
| err.signin | Sign in |

`err.UPLOAD_HEADER_INVALID` takes `{columns}` from `details.missing_columns` joined with ", "; `err.UPLOAD_HEADER_DUPLICATE` is shown once per entry in `details.duplicate_columns`; both are followed by [upload.header_help]. `err.UPLOAD_IN_PROGRESS` is followed by a link [upload.in_progress_link] to `details.batch_id`. A 422 `VALIDATION_ERROR` on `declaration` or `academic_year` shows the api's field message under that field.

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
| empty.flags_institution | No flags open. Flags appear here after the first upload is checked. |
| empty.flags_college | No flags. Flags appear after your upload is checked. Nothing is rejected automatically; an officer reviews every flag. |
| empty.cases | No open flags. Flags appear here after uploads are checked. |
| empty.cases_filtered | No flags match these filters. |
| empty.clear_filters | Clear filters |
| empty.flags_by_type | No open flags for {academic_year}. |
| empty.flags_enrolment | No flags name this enrolment. |
| empty.related | No related enrolments you can see. |
| empty.checks | Not yet checked. Checks run when the upload is processed. |
| empty.enrolments_filtered | No enrolments match these filters. |
| empty.seats | No seats in this pool. |
| empty.uploads | No uploads yet. |
| empty.notices_student | You have no notices yet. When a college reports your enrolment, AICTE sends you a notice by email or DigiLocker. |
| empty.credentials_student | No proofs yet. An enrolment proof appears here after you confirm your enrolment and the other checks agree. |
| empty.enrolments_student | No college has reported an enrolment for you. |
| empty.affiliates | No institutions are affiliated to your university in this academic year. |
| empty.audit | No audit entries. |
| empty.audit_filtered | No entries match these filters. |
| empty.graduates | No graduates found for your affiliated institutions. |
| empty.graduates_search | No graduate matches "{q}". Search by name or the last four digits of APAAR. |

## 15. Check detail sentences

Reference copy of API_CONTRACT §A2.14. The engines write one of these into each check's `detail.summary`; enrolment detail prints it verbatim in the Detail column. The web never rebuilds them. Placeholders: `{source_name}` from `source.*`, `{route_word}` from `route.*`, `{seat_type_word}` from `seat_type.*`, `{flag_name}` from `flag.<TYPE>.name`, `{cohort_start}` the start year of the cohort (`2026`), `{cohort_year}` the approval year (`2026-27`).

| id | check | result | when | text |
|---|---|---|---|---|
| check.detail.unavailable | any | Pending | the source did not answer | {source_name} did not respond. This check stays pending until a recheck or the next upload. |
| check.detail.IDENTITY.na_no_apaar | Identity | n/a | no APAAR (consent Refused or Pending) | APAAR not linked; admission is not blocked. |
| check.detail.IDENTITY.na_international | Identity | n/a | international student | International student; identity is checked through the passport, not APAAR. |
| check.detail.IDENTITY.fail_malformed | Identity | Not countersigned | malformed APAAR on upload | APAAR as uploaded {problem}; the enrolment was kept without it. |
| check.detail.IDENTITY.fail_not_found | Identity | Not countersigned | the registry has no such id | APAAR ending {apaar_last4} is not in the APAAR registry. |
| check.detail.IDENTITY.fail_dob | Identity | Not countersigned | the date of birth differs | Date of birth on upload does not match the APAAR registry. |
| check.detail.IDENTITY.fail_name | Identity | Not countersigned | similarity below 75 | Name on upload differs from the APAAR registry (similarity {name_score} of 100). |
| check.detail.IDENTITY.pending_review | Identity | Needs review | similarity 75 to 89 | Name on upload is close to the APAAR registry but not a clear match (similarity {name_score} of 100); an officer should review. |
| check.detail.IDENTITY.pass | Identity | Countersigned | similarity 90 or more | Name and date of birth match the APAAR registry (similarity {name_score} of 100). |
| check.detail.ADMISSION.pass_counselling | Admission | Countersigned | in the counselling list | Found in the {state_name} counselling allotments for {programme_code} ({cohort_start}), round {round}. |
| check.detail.ADMISSION.pass_ref_differs | Admission | Countersigned | found, reference differs | Found in the {state_name} counselling allotments for {programme_code} ({cohort_start}), round {round}, as {allotment_ref}; the upload says {counselling_ref}. |
| check.detail.ADMISSION.fail_counselling | Admission | Not countersigned | not in the counselling list | Not found in the {state_name} counselling allotments for {programme_code} ({cohort_start}). |
| check.detail.ADMISSION.pass_route | Admission | Countersigned | management, spot or NRI with a seat in the route's pool | {route_word} admission is allowed for {programme_code} and holds a {seat_type_word} seat. |
| check.detail.ADMISSION.fail_no_pool | Admission | Not countersigned | the approval has no seats of the route's type | {route_word} admission is not allowed for {programme_code}: the {cohort_year} approval has no {seat_type_word} seats. |
| check.detail.ADMISSION.fail_no_seat | Admission | Not countersigned | no seat of the route's type | {route_word} admission has no {seat_type_word} seat in {programme_code} ({cohort_year}). |
| check.detail.ADMISSION.pass_sii | Admission | Countersigned | Study in India confirms | Study in India confirms this admission to {programme_code} ({cohort_year}). |
| check.detail.ADMISSION.fail_sii | Admission | Not countersigned | Study in India does not | Study in India has no matching admission for this passport at this institution. |
| check.detail.SEAT.pass | Seat | Countersigned | holds a seat of its cohort approval | Holds seat {seat_code} ({seat_type_word}, {cohort_year} approval). |
| check.detail.SEAT.fail | Seat | Not countersigned | no seat | No {seat_type_word} seat is free in {programme_code} ({cohort_year}); see the {flag_name} flag. |
| check.detail.STUDYING.na_first_year | Studying | n/a | first year | First year, no result yet. |
| check.detail.STUDYING.na_no_apaar | Studying | n/a | no APAAR | APAAR not linked; ABC credits cannot be checked. |
| check.detail.STUDYING.na_abc_unknown | Studying | n/a | ABC does not know the APAAR | ABC has no record of this APAAR; see the Identity check. |
| check.detail.STUDYING.pass | Studying | Countersigned | credits in every expected semester | Credits recorded in ABC for all {expected} semesters since admission. |
| check.detail.STUDYING.pending_one_missing | Studying | Awaiting next results | one semester missing | No credits recorded in ABC for semester {sem} ({academic_year}); waiting for the next upload. |
| check.detail.STUDYING.fail | Studying | Not countersigned | two or more semesters missing | No credits recorded in ABC for {missing} of {expected} semesters since admission. |
| check.detail.STUDENT.pending | Student | Notice not sent yet | no notice for this enrolment yet | Notice not sent yet. |
| check.detail.STUDENT.pending_sent | Student | No reply yet | a notice was sent and has no reply | Notice sent on {sent_date}; no reply yet. |
| check.detail.STUDENT.pending_expired | Student | No reply (expired) | every notice expired without a reply | No reply (expired). |
| check.detail.STUDENT.pass | Student | Countersigned | a Yes on any channel and no No | Confirmed by the student on {reply_date} ({channel_word}). |
| check.detail.STUDENT.fail | Student | Not countersigned | a No on any channel; a No beats a Yes | Denied by the student on {reply_date} ({channel_word}). |

`{problem}` is, for example, "has 11 digits, expected 12" or "contains characters other than digits". The result column gives the word the web shows beside the sentence (`check.status.*` or `check.pending.*`).

Student check (D24): the source is `STUDENT_NOTICE` ([source.STUDENT_NOTICE]) and the result comes only from the enrolment's notices, never from an adapter. A No beats a Yes, because the college supplies the email address while DigiLocker reaches the APAAR holder. `{channel_word}` is "email" or "DigiLocker". After the one allowed change of answer, the sentence follows the new answer and its date. The FAIL sentence is the deck's wording; D24 names the result but not the sentence.

## 16. Enrolment detail

Routes `/aicte/enrolments/[id]`, `/ro/enrolments/[id]`, `/college/enrolments/[id]`, `/university/enrolments/[id]`, from `GET /enrolments/{id}` (API_CONTRACT §A2.11).

| id | text |
|---|---|
| enrolment.crumb | Enrolment |
| enrolment.title | {student_name}, {programme_code} |
| enrolment.section.student | Student |
| enrolment.section.enrolment | Enrolment |
| enrolment.section.checks | Countersign checks |
| enrolment.section.seat | Seat |
| enrolment.section.flags | Flags on this enrolment |
| enrolment.field.institution | Institution |
| enrolment.field.programme | Programme |
| enrolment.field.mode | Mode |
| enrolment.field.intake | Intake |
| enrolment.intake_value | {cohort_year} approval |
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
| enrolment.score_label | Countersigned |
| enrolment.seat_value | {seat_code} · {seat_type_word} · {academic_year} approval · assigned {assigned_date} |
| enrolment.unseated | No seat held. |
| enrolment.unseated_flag | See the {flag_name} flag. |
| col.check | Check |
| col.result | Result |
| col.source | Source |
| col.checked_at | Checked |
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
| resend.button | Resend notice |
| resend.tip | Sends a new notice when the last one expired or was not delivered. Up to 3 times for this enrolment in an academic year. |
| resend.live_tip | The student can still answer the notice sent on {sent_date}, until {expires_date}. |
| resend.confirm_heading | Send a new notice? |
| resend.confirm | {student_name} gets a new link by email, and in DigiLocker when they have an APAAR. Notices can be resent up to 3 times for this enrolment in {academic_year}. |
| resend.send | Send notice |
| resend.cancel | Cancel |
| resend.sending | Sending |
| resend.sent | Notice sent. The new link works until {expires_date}. |

One `enrolment.notice.channel_line` per notification, newest notice first, with `{channel_name}` from `notice_channel.*` and `{delivery_word}` from `notice_delivery.*`; a FAILED line adds `enrolment.notice.failed_reason` with the api's `last_error` verbatim (for a missing DigiLocker account the api writes "no DigiLocker account"). `{reply_word}` is `notice_reply.*` (Confirmed, Denied). `enrolment.notice.comment` and the comment under it appear for officers only; the api never sends the comment to a registrar or a university (D24). Resend notice shows for an AICTE officer, a regional officer and the registrar of the student's own college, never for the university: enabled when every notice is expired or not delivered; disabled with `resend.live_tip` while a notice is live; replaced by `enrolment.notice.consent_off` when the student withdrew notice consent. A 429 `RESEND_LIMIT` shows [err.RESEND_LIMIT] and disables the button; a 409 `NOTICE_LIVE` shows [err.NOTICE_LIVE] and refetches.

The Result cell uses `check.status.*`, or for PENDING the pending word from §3. The Detail cell prints `detail.summary` verbatim; when `attempts` is above 0, [check.attempts] follows in small text. A null `checked_at` prints [check.never]. Mobile prints `mobile_masked` exactly as sent; a null value leaves the line out. `enrolment.unseated_flag` takes the SEAT check's `detail.flag_type` and links to that flag in `flags` when it is there. The footer carries [privacy.read_logged].

## 17. Recheck

`POST /enrolments/{id}/recheck` (AICTE officer, regional officer, the registrar for their own college) and `POST /institutions/{id}/recheck` (AICTE officer, regional officer), API_CONTRACT §A2.12 and §A2.13.

| id | text |
|---|---|
| recheck.enrolment | Recheck pending checks |
| recheck.enrolment_tip | Asks the sources again for this enrolment's pending checks. The student check waits for the student's reply and is not rechecked. |
| recheck.institution | Recheck pending checks |
| recheck.institution_tip | Asks the sources again for every pending check of this institution's active enrolments in {academic_year}. Use it after a source comes back. The student check is not rechecked. |
| recheck.running | Rechecking |
| recheck.result_heading | Recheck finished |
| recheck.result_line | {check}: {before_word} to {after_word} |
| recheck.still_pending | {check}: still pending |
| recheck.none | Nothing to recheck. No check other than the student's reply is pending. |
| recheck.flags_raised | {n} new flags raised. |
| recheck.institution_result | {rechecked} pending checks asked again in {seconds} s: {now_pass} now countersigned, {now_fail} not countersigned, {now_na} n/a, {still_pending} still pending. |

The enrolment button shows only when a check other than Student is PENDING. Each item of `results` prints `recheck.result_line` with `check.status.*` words, or `recheck.still_pending` when `after` is PENDING; `rechecked: 0` prints `recheck.none`; `flags_raised` above 0 adds `recheck.flags_raised`. `{seconds}` is `duration_ms` / 1000 with one decimal. A 429 shows [err.RATE_LIMITED] and counts down `details.retry_after` on the button.

## 18. Flag list and detail

Case queue `/aicte/cases` and `/ro/cases`, the institution Flags tab, `/college/flags`, and flag detail, from `GET /flags` and `GET /flags/{id}` (API_CONTRACT §A2.15, §A2.16). Officers act from flag detail and the registrar responds there (§6).

| id | text |
|---|---|
| flags.heading_college | Flags against your college |
| flags.see_all | See all flags |
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
| table.count.flags_any | {total} flags in {institutions} institutions |
| table.count.flags_one | {total} open flags |
| table.count.flags_one_any | {total} flags |
| tab.flags_count | Flags ({n}) |
| flags.more | +{n} |
| enrolments.filter.check | Check |
| enrolments.filter.result | Result |
| enrolments.filter.any | Any |
| enrolments.filter.flagged | Flags |
| enrolments.filter.flagged_yes | With open flags |
| enrolments.filter.flagged_no | No open flags |
| enrolments.filter.seated | Seat |
| enrolments.filter.seated_yes | Holds a seat |
| enrolments.filter.seated_no | Unseated |
| col.severity | Severity |
| col.flag_type | Type |
| col.institution | Institution |
| col.evidence | Evidence |
| col.related | Related |
| col.related_tip | Enrolments this flag names that you can see |
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
| flag.enrolment_heading | Enrolment this flag is about |
| flag.related_heading | Related enrolments ({n}) |
| flag.related_hidden | {n} related enrolments at another institution are not shown to your college. |
| flag.readonly_college | An officer reviews every flag. If they ask for documents, you can respond here. |

Count line: with the status filter on Open use [table.count.flags]; with any other status filter use `table.count.flags_any`; on one institution's Flags tab and on `/college/flags` use `table.count.flags_one`, or `table.count.flags_one_any` when the status filter is not Open. `{institutions}` is the response's `institutions`. The Evidence cell prints `summary` verbatim on one line, truncated, with the full sentence on focus and hover. Opened prints the `created_at` date. The Assignee column shows on the officers' case queue; a null assignee reads [case.assignee_none]. The Assignee filter sends `assignee=me`, `none` or an officer's id; the Response filter sends `response_received=true`. A row with `response_received` carries the [case.response_badge] chip beside its status. History starts with [case.history.opened] at the `created_at` time, then the rows of §6. `flag.readonly_college` shows to the registrar when the flag is not Documents requested. `flag.related_hidden` shows when `related_hidden` is above 0. `flag.chip` is the accessible name of a flag chip in an enrolment row; after two chips the rest collapse into `flags.more`. The enrolments table's Result filter uses `check.status.*` words and its Check filter `check.*` words.

## 19. Dashboard flags

| id | text |
|---|---|
| section.flags_by_type | Open flags by type |
| flags_by_type.link | Show {type_name} cases |
| flags_by_type.total | {total} open flags |

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
| privacy.consent_via.CREDENTIAL_SHARE | Given each time you share a proof |
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
| privacy.access.verifier | A verifier you shared a proof with |
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
| privacy.request.sent | Request sent. An AICTE officer replies here. |
| privacy.request.row | {kind_word}, sent {date} |
| privacy.request.waiting | Waiting for a reply from AICTE |
| privacy.request.reply | Reply from AICTE, {date} |
| privacy.request.none | You have not made any requests. |
| privacy.export_ready | Your copy is ready. |
| privacy.export_download | Download my data (JSON file) |
| privacy.export_note | The file lists everything Countersign holds about you. Your APAAR is masked in it too. Keep the file somewhere safe. |
| privacy.export_preparing | Preparing your file |

Consents: one row per purpose in the order APAAR_LINK, NOTICE, CREDENTIAL_SHARE, each with the `consent_purpose.*` words, the `consent_state.*` word in `privacy.consent_status`, the `privacy.consent_via.*` line and the exact stored text behind `privacy.consent_text_show`. CREDENTIAL_SHARE is recorded once per share; its row shows the newest with `privacy.consent_last`. Withdraw shows on NOTICE and CREDENTIAL_SHARE while they are Given and opens `consent.withdraw.<PURPOSE>` with `privacy.withdraw_confirm` and `privacy.withdraw_cancel`; the APAAR_LINK row shows `consent.unlink_apaar` and `privacy.unlink_apaar` instead.

Access log (D30): READ entries about the student and their enrolments, newest first, Date and Who only. Who is `privacy.access.<ROLE>` by the reader's role; an entry with no actor reads `privacy.access.notice_link` when it came from a notice link and `privacy.access.verifier` when it came from a verifier check. Never a name, an email, a college other than the student's own, or an IP.

Requests: Access is fulfilled at once: after sending, the form is replaced by `privacy.export_ready` and `privacy.export_download` (a link to `/api/students/me/export.json`) with `privacy.export_note`. Correction and Erasure need details (`privacy.request.details_required` under an empty field) and appear in the list with `privacy.request.row`, the `data_request_status.*` word with an icon, `privacy.request.waiting` while Open, and the officer's reply under `privacy.request.reply` once resolved.
