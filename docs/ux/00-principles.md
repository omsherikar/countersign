# UX principles

Countersign treats a college upload as a claim. Five independent sources (Identity, Admission, Seat, Studying, Student) each countersign a record. An officer sees which check failed and decides. Every screen follows from that sentence.

Terms used in this folder: "officer" means `AICTE_ADMIN` or `RO_OFFICER`; "registrar" means the `INSTITUTION` user; "check" means one of the five countersign checks; "flag" means a row in `flags`; "case" means a flag an officer is working.

## 1. Product principles

### P1. Claim, then countersign
- Every enrolment is shown first as what the college said, then as what each source said about it.
- The five checks are always shown in the same order: Identity, Admission, Seat, Studying, Student.
- A page never says an enrolment "is valid" or "is fraud". It says which sources agreed.

### P2. Evidence first
- A flag is never shown without its evidence. The evidence summary line sits in the flag row itself, not behind a click.
- Evidence reads as "what was claimed, what the source holds, the difference", with the rule it comes from (`rule_source`, e.g. "APH 2024-27 cl. 2.8(b)").
- Numbers in evidence carry their unit and their period ("120 approved seats, 2026-27").

### P3. Nothing is auto-rejected
- The system opens flags; only a person clears, requests documents, escalates or confirms.
- No screen shows a flag as "rejected", "blocked" or "fraud". Status words are exactly: Open, Documents requested, Cleared, Escalated, Confirmed.
- Confirm always requires a written note. Clear always requires a written note. The note is shown in the case history.
- A student's "No" opens a case; it does not change the enrolment.

### P4. Privacy is visible, not assumed
- Every student identifier on screen is masked in the standard shape: `XXXX XXXX 4417` for APAAR, `XXXXXX4521` for mobile. The full value never exists in the browser.
- When a student has no APAAR, the provisional id (`PRV-XXXXXXXX`) is shown with the label "Provisional id", never a blank.
- Pages that show student rows say so in a small line: "Viewing student records is logged." This is true (every read is audited) and the officer should know it.
- Students see exactly what the system holds on them and who looked, in plain words.

### P5. Score is "n of m", never a percentage
- Per-enrolment countersign is displayed as "4 of 5" with the five-segment strip beside it.
- `NA` checks are left out of the count and shown as a grey "n/a" segment with a reason on hover.
- `PENDING` counts in the denominator and is shown hollow, never red: "3 of 5, 1 pending". The Student check, pending for every enrolment until student notices start, is left out of that pending count.
- Aggregates (dashboard tiles) may say "share of enrolments fully countersigned" with a percentage, because that is a share of a population, not a score. The word "score" is never followed by "%".
- Integrity Index (Week 4) is a 0 to 100 number with its breakdown one click away ("why this score"). It is never coloured red or green on its own; it is ranked.

### P6. Neutral "no reply"
- A student notice has three states: Confirmed, Denied, No reply. "No reply" is neutral grey, phrased as "No reply yet", and never counts against the enrolment or the college.
- The Student check is `PENDING` until a reply; it never becomes `FAIL` from silence.

### P7. Source unavailable means Pending, not Fail
- When a government source times out or is down, the check is `PENDING` with the label "Awaiting source" and the source name. The row never turns red.
- The dashboard shows source health ("APAAR registry: unavailable since 09:30") so an officer knows why many rows are pending.
- A pending check runs again when its row is uploaded again, or when an officer or the registrar presses "Recheck pending checks" (rate-limited, API_CONTRACT §A2.12 and §A2.13). The button appears only when a check other than Student is pending, and a source still down leaves the check pending, never failed.

### P8. Officers rank, they do not scroll
- Officer landing pages open on the ranked list (by open flags, then severity, then enrolments), not on a blank search.
- Every list carries a count ("37 open flags in 9 institutions"), so the officer can say a defensible number out loud.
- Default sort is explained in the column header tooltip.

### P9. No map
- Geography is a state grid or table. There is never an outline of India on any screen, including loading placeholders, icons, favicons and empty states (decision D8).

### P10. Honest demo surfaces
- Demo-only affordances (prefilled credentials, chaos toggles, reset) are labelled "Demo" and live on the login page and `/admin/system` only.
- Nothing fakes a real government API: the Sources panel says "mockgov" when that is the adapter.

### P11. Dense for officers, spacious for students
- Officer and registrar tables: 36 px rows, tabular numerals, right-aligned numbers, sticky header, no card-per-row layouts.
- Student, verifier and notice pages: one task per screen, large tap targets (44 px), one primary button.

### P12. Everything keyboard reachable
- Every row with a drill-down is a link, not a click handler on a `div`.
- Tables support `Tab` into rows, `Enter` to open, `Esc` to close any panel.
- Focus order follows reading order; focus is never trapped except in a modal.

## 2. Copy voice

### Spelling and words
- Indian English: enrolment, programme, counselling, colour, organisation, cancelled, licence (noun). Never "enrollment", "program".
- "Academic year 2026-27", never "AY26" in user-facing text.
- Institutions are "institutions" in officer views and "your college" in the registrar view. Students see "ABC College of Engineering says..." with the full name.
- "Approved intake" for the AICTE number, "admitted" for what the college uploaded, "seated" for enrolments with a seat, "unseated" for enrolments without one. Never "overbooked", "illegal", "fake".
- "Countersigned" for a check that passed; "not countersigned" for one that failed; for pending, the reason when it is known ("awaiting source", "needs review", "notice not sent yet", "awaiting next results"), else "pending"; "n/a" for not applicable.
- Government source names: APAAR registry, Counselling allotment list, Seat ledger, ABC (Academic Bank of Credits), Student reply, DigiLocker, Study in India.

### Tone
- Plain sentences, present tense, second person for instructions ("Upload the admission file"), third person for facts ("The source did not respond").
- No exclamation marks. No "Oops". No jargon in headings (no "SD-JWT" in a student heading; say "your enrolment proof").
- Numbers use Indian grouping with `en-IN` formatting: 1,20,000. Dates as `14 Jul 2026`. Times as `09:30 IST`.
- Buttons are verbs: "Request documents", "Clear flag", "Confirm it is me", "Share proof".
- Destructive or irreversible actions name the consequence in the confirmation: "Confirming opens a formal case against ABC College. Add a note first."

### How to word a flag
Pattern: `<what the college claimed> against <what the source holds> <in scope> (<period>)`, then facts as label and value pairs, then the rule.

- Good: "132 admitted against 120 approved seats in CSE (2026-27)."
- Good: "Name on upload differs from the APAAR registry (similarity 71 of 100)."
- Bad: "Illegal excess admission detected." (accusatory, no numbers)
- Bad: "Fraud ring suspected." (no evidence, loaded word)

Severity words are only `Low`, `Medium`, `High`. Never "critical", "alert".

### How to word a notice to a student
Pattern: `<institution> says you joined <programme> (<academic year>). Is that right?` followed by exactly two choices and a line on what happens next.

- Primary: "Yes, that is right"
- Secondary: "No, that is not me"
- Next-step line: "If you say no, an AICTE officer will look into it. Nothing changes for you until then."
- Never: "Verify your enrolment immediately", "Action required", deadlines in bold red.

### Error messages
- Say what happened, then what to do, in that order. "The APAAR registry did not respond. This check will retry on its own."
- Never show an error code alone; show the message and keep the code in small text for support: "Ref: SOURCE_UNAVAILABLE".
- 403 is phrased as a role statement, not a scolding: "This page is for AICTE officers. You are signed in as a registrar."

### Empty states
- State what would be here and the one action that fills it. "No flags open. Flags appear here after the first upload is checked."
- Week 1 nulls (`integrity_index`, `countersigned_pct`, `score`) read "Not yet computed", never "0" and never "N/A".
