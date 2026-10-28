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
| login.demo_footer | Demo passwords are shared and reset nightly. Not for real data. |
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
| upload_status.CHECKING | Checking |
| upload_status.DONE | Done |
| upload_status.FAILED | Failed |
| notice_reply.YES | Confirmed |
| notice_reply.NO | Denied |
| notice_reply.NONE | No reply yet |
| notice_reply.EXPIRED | No reply (expired) |
| provisional.label | Provisional id |

## 5. Flag names and evidence templates

`flag.<TYPE>.name` is the human name shown in tables. `flag.<TYPE>.summary` is the evidence sentence the api should produce in `evidence.summary` (the web renders `summary` verbatim and never rebuilds it). `facts` lists the label and value pairs expected in `evidence.facts`. `rule` is the expected `rule_source`.

| type | name | summary template | facts | rule |
|---|---|---|---|---|
| EXCESS_ADMISSION | Excess admission | {admitted} admitted against {approved} approved seats in {programme_code} ({academic_year}). | Approved intake; Admitted (active); Seated; Unseated | APH 2024-27 cl. 2.8(b) |
| QUOTA_BREACH | Quota breach | {assigned} {seat_type} admissions against {capacity} {seat_type} seats in {programme_code} ({academic_year}). | Pool; Capacity; Admitted via route; Rule percentage | APH 2024-27 cl. {clause} |
| LATE_REFILL | Late refill | Seat {seat_code} assigned on {assigned_date}, after the last admission date {cutoff_date}. | Seat; Released on; Assigned on; Last admission date | APH 2024-27 cl. 6.13(f) |
| INVALID_APAAR | APAAR not found | APAAR ending {apaar_last4} is not in the APAAR registry. | APAAR (masked); Registry reply; Checked at | APAAR verification |
| NAME_MISMATCH | Name mismatch | Name on upload differs from the APAAR registry (similarity {name_score} of 100). | Name on upload; Similarity; Date of birth match; Checked at | APAAR verification |
| DUPLICATE_CROSS_INSTITUTION | Duplicate across institutions | The same student appears as active at {institution_a} and {institution_b} ({academic_year}). | Match on; Institution A programme; Institution B programme; Uploaded on | One active full-time enrolment per student |
| DUPLICATE_WITHIN_UPLOAD | Duplicate in upload | Rows {row_a} and {row_b} of {filename} describe the same student. | Match on; Row A; Row B; Names as uploaded | Upload validation |
| DUAL_ENROLMENT_ALLOWED | Dual enrolment (allowed) | The student holds two enrolments; one is distance or online, which is permitted. | Enrolment A mode; Enrolment B mode; UGC notification | UGC dual-degree guidelines 2022 |
| NO_ACADEMIC_ACTIVITY | No academic activity | No credits recorded in ABC for {semesters} semesters while enrolled in year {year_of_study}. | Semesters checked; Credits found; Last ABC entry | ABC credit record |
| STUDENT_DENIED | Student denied | Student replied "not me" to the notice sent on {sent_date}. | Notice sent; Replied on; Student comment | Student reply |
| GHOST_RING | Shared contact ring | {students} students across {institutions} institutions share {contacts} contact details. | Shared mobiles; Shared emails; Shared addresses; Institutions | Contact graph analysis |
| ANOMALY | Unusual pattern | {metric} for {programme_code} is {value}, outside the usual range ({low} to {high}) for similar programmes. | Metric; Value; Usual range; Compared with | Anomaly model, Week 4 |

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

| id | text |
|---|---|
| upload.heading | Upload admissions file |
| upload.drop | Drop a CSV or XLSX here, or choose a file |
| upload.choose | Choose file |
| upload.template | Template |
| upload.max | Max 20 MB |
| upload.columns | Columns expected |
| upload.kind.INITIAL | Initial upload for this year |
| upload.kind.UPDATE | Update to an earlier upload |
| upload.declaration | I declare that every student in this file has consented to their APAAR being used to verify this enrolment, and that the file is true to the college's admission register. |
| upload.submit | Upload |
| upload.err_type | Only .csv and .xlsx files can be uploaded. |
| upload.err_size | The file is larger than 20 MB. Split it by programme and upload each part. |
| upload.err_declaration | Tick the declaration to upload. |
| upload.previous | Previous uploads |
| upload.rows | Rows {total} · Accepted {ok} · Errors {error} |
| upload.checking | Checking against sources |
| upload.source_waiting | {source}: awaiting source, will retry |
| upload.failed | This upload could not be processed: {reason}. Accepted rows from earlier uploads are unchanged. |
| upload.errors_heading | Row errors ({n}) |
| upload.errors_download | Download errors as CSV |
| upload.errors_none | No row errors |
| upload.errors_next | Fix the rows in your file and upload it again as an update. Accepted rows are already in the seat ledger. |
| upload.done_summary | {ok} rows accepted · {seated} seats assigned · {unseated} unseated · {flags} flags opened |
| upload.done_note | Flags are for review by an officer. Nothing has been rejected. |
| upload.view_ledger | View seat ledger |
| college.no_upload_yet | Last upload: none yet. Upload opens in Week 2. |
| rowerr.APAAR_FORMAT | APAAR must be 12 digits |
| rowerr.DUPLICATE_IN_FILE | Same APAAR appears on row {other_row} |
| rowerr.UNKNOWN_PROGRAMME | Programme code {value} is not approved for your college |
| rowerr.DOB_FORMAT | Date of birth must be YYYY-MM-DD |
| rowerr.MISSING_REQUIRED | {field} is required |
| rowerr.ROUTE_INVALID | Admission route must be one of Counselling, Management, NRI, Spot, Lateral, International, TFW |
| rowerr.YEAR_INVALID | Year of study must be between 1 and 6 |
| rowerr.CONSENT_INVALID | Consent status must be Linked, Refused, Pending or International |
| rowerr.PASSPORT_REQUIRED | International students need a passport number |

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
| err.NOT_FOUND_generic | We could not find that. |
| err.VALIDATION_ERROR | Check the highlighted fields. |
| err.RATE_LIMITED | Too many attempts. Try again in {seconds} s. |
| err.SOURCE_UNAVAILABLE | {source} did not respond. This check will retry on its own. |
| err.INTERNAL | Something went wrong on our side. Try again. |
| err.NETWORK | Could not reach Countersign. Check your connection and try again. |
| err.ref | Ref: {code} |
| err.retry | Try again |
| err.back_overview | Back to overview |
| err.go_home | Go to my overview |
| err.tile_failed | Could not load |
| err.signin | Sign in |

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
