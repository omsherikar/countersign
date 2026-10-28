# Copy deck

Every user-facing string, keyed by id. Placeholders are `{snake_case}` and map to API fields. Indian-English spelling throughout. No exclamation marks. Hindi strings are marked "for review" and must be checked by a native speaker before the panel.

Suggested implementation: `apps/web/lib/copy.ts` exporting a flat object keyed by these ids, so the review checklist can grep for them.

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
| kpi.enrolments | Enrolments |
| kpi.flags_open | Open flags |
| kpi.countersigned | Countersigned |
| kpi.countersigned_value | {pct}% of enrolments fully countersigned |
| kpi.not_computed | Not yet computed |
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
| col.enrolments | Enrolments |
| col.flags_open | Open flags |
| col.integrity | Integrity Index |
| col.code | Code |
| col.programme | Programme |
| col.level | Level |
| col.shift | Shift |
| col.approved | Approved |
| col.approved_tip | Approved intake for {academic_year} |
| col.admitted | Admitted |
| col.admitted_tip | Active enrolments uploaded by the college |
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
| strip.score_pending | {passes} of {applicable}, {pending} awaiting source |
| strip.aria | Countersigned {passes} of {applicable}. Identity {s1}, Admission {s2}, Seat {s3}, Studying {s4}, Student {s5}. |
| check.IDENTITY | Identity |
| check.ADMISSION | Admission |
| check.SEAT | Seat |
| check.STUDYING | Studying |
| check.STUDENT | Student |
| check.status.PASS | Countersigned |
| check.status.FAIL | Not countersigned |
| check.status.PENDING | Awaiting source |
| check.status.NA | n/a |
| check.na_reason.STUDYING | Not applicable before first results |
| check.na_reason.ADMISSION | No counselling list for this route |
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
| source.will_retry | Will retry |

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
| provisional.label | Provisional id |

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
| flag.STUDENT_DENIED.summary | not raised before Week 3 | | Student replied "not me" to the notice sent on {sent_date}. |
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
| | Capacity | {capacity} | rules.yaml |
| | Admitted via route | {admitted} ({route_words}) | College uploads |
| | Unseated | {unseated} | Seat ledger |
| | Rule percentage | {share}% of approved intake {approved} | rules.yaml |
| LATE_REFILL | Seat | {seat_code} | Seat ledger |
| | Released on | {released_date} | Seat ledger |
| | Assigned on | {assigned_date} | College upload {filename}, row {row_no} |
| | Last admission date | {cutoff_date} | rules.yaml cutoff_dates |
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
| STUDENT_DENIED | Notice sent; Replied on; Student comment | | Student reply |
| GHOST_RING | Shared mobiles; Shared emails; Shared addresses; Institutions | | Contact graph analysis |
| ANOMALY | Metric; Value; Usual range; Compared with | | Anomaly model |

Words: `{match_words}` is "Same APAAR", "Same passport" or "Name ({name_score} of 100), date of birth and mobile", joined with "and" when more than one matched. `{mode_a_word}` and `{mode_b_word}` are "physical", "open and distance learning" or "online". `{route_words}` lists the routes that map to the pool (NRI; TFW; Lateral; International). Institution A is always the flag's own institution and B the other one. The registrar never sees B's name: the api drops the officer facts and keeps the registrar ones.

Rule sources (`evidence.rule_source`, shown after "Rule:")

| id | text |
|---|---|
| flag.EXCESS_ADMISSION.rule | {rule_source}, the Regular pool's, e.g. "Approval record (approved_intake); minus NRI carve-out (APH 2024-27 cl. 2.8(b))" |
| flag.QUOTA_BREACH.rule | {rule_source}, the breached pool's, e.g. "APH 2024-27 cl. 2.8(b)" for NRI |
| flag.LATE_REFILL.rule | Last admission date for {cohort_year} (rules.yaml cutoff_dates) |
| flag.INVALID_APAAR.rule | APAAR verification |
| flag.NAME_MISMATCH.rule | APAAR verification |
| flag.DUPLICATE_CROSS_INSTITUTION.rule | One active full-time enrolment per student |
| flag.DUPLICATE_WITHIN_UPLOAD.rule | Upload validation |
| flag.DUAL_ENROLMENT_ALLOWED.rule | UGC dual-degree guidelines 2022 |
| flag.NO_ACADEMIC_ACTIVITY.rule | ABC credit record |
| flag.STUDENT_DENIED.rule | Student reply |
| flag.GHOST_RING.rule | Contact graph analysis |
| flag.ANOMALY.rule | Anomaly model, Week 4 |

QUOTA_BREACH counts `{admitted}` (enrolments by route), because assigned seats can never exceed a pool's capacity. LATE_REFILL cites the last admission date in `rules.yaml` `cutoff_dates`, not APH cl. 6.13(f), which is the lateral-entry vacancy clause.

Rules for every template: no verdict words (never "fraud", "fake", "illegal"); claimed figure first, source figure second; the period in brackets; one sentence.

## 6. Case actions

| id | text |
|---|---|
| case.clear | Clear flag |
| case.request_docs | Request documents |
| case.escalate | Escalate |
| case.confirm | Confirm |
| case.note | Add note |
| case.note_label | Note (shown to the college) |
| case.note_required | Add a note before you continue. |
| case.clear_confirm | Clear this flag? Your note is shown to the college and kept in the case history. |
| case.request_docs_prompt | What should the college send? Be specific, e.g. "Admission register extract for CSE, 2026-27". |
| case.due_date | Reply by (optional) |
| case.escalate_prompt | Why does this need a senior officer? |
| case.confirm_confirm | Confirming records this flag as a confirmed irregularity against {institution_name}. Nothing is deleted; the enrolment keeps its status. Your note becomes part of the formal record. |
| case.cleared_toast | Flag cleared. {institution_name} can see your note. |
| case.docs_toast | Request sent to the registrar. |
| case.escalated_toast | Escalated. |
| case.confirmed_toast | Recorded as confirmed. |
| case.back | Back to queue |
| case.history.opened | Flag opened |
| case.history.response | Response from the college |
| college.respond | Respond |
| college.respond_note | Your reply to the officer |
| college.respond_files | Attach documents (PDF, JPG, PNG, up to 10 MB each) |
| college.respond_sent | Sent to the officer. You will see their decision here. |
| college.other_institution | another institution in {state_name} |

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
| col.level | Level |
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
| notice.expired | This link has expired. Ask your college to resend the notice. |
| notice.invalid | This link is not valid. Check the link in your message or ask your college to resend it. |
| notice.lang_hi | हिन्दी |
| notice.lang_en | English |

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
| notice.expired.hi | यह लिंक समाप्त हो गया है। अपने कॉलेज से सूचना दोबारा भेजने को कहें। |

Wallet

| id | text |
|---|---|
| wallet.heading | My proofs |
| wallet.kind.ENROLMENT | Enrolment proof |
| wallet.kind.DEGREE | Degree |
| wallet.issued_by | Issued by Countersign for {institution_name} |
| wallet.issued_on | Issued {issued_date} |
| wallet.status.active | Active |
| wallet.status.revoked | Revoked |
| wallet.share | Share proof |
| wallet.details | Show details |
| wallet.fields_heading | Choose what to share |
| wallet.field.name | Name |
| wallet.field.institution | Institution (always shared) |
| wallet.field.programme | Programme (always shared) |
| wallet.field.academic_year | Academic year |
| wallet.field.year_of_study | Year of study |
| wallet.field.dob | Date of birth |
| wallet.field.apaar_masked | APAAR (masked) |
| wallet.create_qr | Create QR |
| wallet.shares | Shares {n} of {m} fields |
| wallet.valid_for | Valid for 10 minutes |
| wallet.copy_link | Copy link |
| wallet.copied | Link copied |
| wallet.history_item | Shared with a verifier at {time} |
| student.heading | My enrolment |
| student.card_lead | {institution_name} says you joined {programme_name} |
| student.strip_caption | {passes} of {applicable} sources agree |
| privacy.student_line | Only you can see your email and mobile here. Officers see masked ids only. |
| privacy.how_link | How my data is used |

## 9. Consent texts (DPDP)

Each text is stored verbatim in `consents.notice_text` when the consent is recorded.

| id | purpose | text |
|---|---|---|
| consent.apaar_link | APAAR_LINK | I allow AICTE to use my APAAR id to check that my enrolment at {institution_name} is genuine. AICTE will look up my id with the APAAR registry, the counselling allotment list and the Academic Bank of Credits. Only the last four digits of my id are shown to officers. I can withdraw this consent from my Privacy page; checks already made stay on record. |
| consent.notice | NOTICE | By replying, you let AICTE record your answer with today's date against this enrolment. Your answer is shown to AICTE officers and to {institution_name} as "Confirmed" or "Denied", with no other personal detail. |
| consent.credential_share | CREDENTIAL_SHARE | I am creating a proof that shows only the fields I ticked. Whoever scans it sees those fields, the issuer and the date, and nothing else. The proof expires in 10 minutes. AICTE records that a proof was created, not who scanned it. |
| consent.withdraw | any | Withdraw this consent? Checks already made stay on record. New checks will use your provisional id instead of your APAAR. |
| consent.upload_declaration | APAAR_LINK via college | (identical to upload.declaration) |

## 10. Verifier

| id | text |
|---|---|
| verify.heading | Verify an enrolment or degree proof |
| verify.lead | Scan the QR on the document, or paste the code printed under it. |
| verify.scan | Scan with camera |
| verify.code_label | Code |
| verify.placeholder | e.g. K7PQ-3M2X-9ZAB |
| verify.check | Check |
| verify.coming | Verification opens in Week 3. Until then no code can be checked here. |
| verify.what | What you will see: whether the proof is valid, who issued it, and only the fields the student chose to share. Never a full APAAR number. |
| verify.valid | Valid proof |
| verify.valid_sub | Issued by Countersign for {institution_name} on {issued_date}. |
| verify.revocation | Revocation list checked just now. |
| verify.revoked | This proof has been revoked. |
| verify.revoked_sub | The student or the issuer withdrew it on {revoked_date}. Ask for a fresh proof. |
| verify.expired | This proof has expired. |
| verify.expired_sub | Proofs are valid for 10 minutes after they are created. Ask for a fresh one. |
| verify.invalid | This code is not a Countersign proof. |
| verify.invalid_sub | Check the code and try again. |
| verify.about_link | What is Countersign? |

## 11. University

| id | text |
|---|---|
| university.heading | Affiliated institutions |
| university.degree_teaser | Degree print opens in Week 3. You will pick a graduating student and print a degree insert with masked APAAR and a QR. |
| degree.heading | Degree print |
| degree.print | Print |
| degree.issue | Issue degree proof |
| degree.issue_note | The student can see this proof in their wallet and control what they share from it. |
| degree.scan_line | Scan to verify at {verify_url} |
| degree.apaar_line | APAAR {apaar_masked} |

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
| audit.col.seq | Seq |
| audit.col.at | Time |
| audit.col.actor | Actor |
| audit.col.action | Action |
| audit.col.entity | Entity |
| audit.col.hash | Hash |
| score.heading | Integrity Index |
| score.value | {index} of 100 |
| score.rank | Rank {rank} of {of} nationally · computed {computed_date} |
| score.start | Start at 100, minus: |
| score.raise | What would raise it: {hint} |
| psi.heading | Private matching |
| psi.compute | Compute overlap |
| psi.result | Overlap: {n} records. Neither side learned the other's members. |
| psi.explain | Both sides encrypt their lists, swap the encrypted versions and count the matches. The lists themselves never leave their owner. |

## 13. Errors (by API error code)

| id | text |
|---|---|
| err.UNAUTHENTICATED | Your session has ended. Sign in again. |
| err.INVALID_CREDENTIALS | Email or password is incorrect. |
| err.FORBIDDEN | This page is for {required_roles_words}. You are signed in as {role_word}. |
| err.FORBIDDEN_redirect | That page is for {required_roles_words}. You are signed in as {role_word}. |
| err.NOT_FOUND_institution | This institution is not in your scope or does not exist. |
| err.NOT_FOUND_upload | This upload is not in your scope or does not exist. |
| err.NOT_FOUND_generic | We could not find that. |
| err.VALIDATION_ERROR | Check the highlighted fields. |
| err.RATE_LIMITED | Too many attempts. Try again in {seconds} s. |
| err.SOURCE_UNAVAILABLE | {source} did not respond. This check will retry on its own. |
| err.FILE_TOO_LARGE | The file is larger than 20 MB. Split it by programme and upload each part. |
| err.TOO_MANY_ROWS | The file has more than 50,000 rows. Split it and upload each part. |
| err.UNSUPPORTED_FILE_TYPE | Only .csv and .xlsx files can be uploaded. |
| err.UPLOAD_HEADER_INVALID | The file is missing required columns: {columns}. |
| err.UPLOAD_HEADER_DUPLICATE | The column {column} appears more than once. |
| err.UPLOAD_EMPTY | The file has a header but no rows. |
| err.UPLOAD_IN_PROGRESS | An upload for this college and year is still being processed. |
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
| empty.seats | No seats in this pool. |
| empty.uploads | No uploads yet. |
| empty.notices_student | You have no notices yet. |
| empty.credentials_student | Proofs you can share arrive in Week 3. |
| empty.enrolments_student | No college has reported an enrolment for you. |
| empty.affiliates | No institutions are affiliated to your university in this academic year. |
| empty.audit | No audit entries. |
| empty.graduates | No graduating students found. |
