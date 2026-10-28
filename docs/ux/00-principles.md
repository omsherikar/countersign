# UX principles

Countersign treats a college upload as a claim. Each fact on it is matched to a source, labelled with who supplied it and when, and judged Confirmed, Contradicted, Pending, Not yet due, Not applicable or Source unavailable. A record is Countersigned only when the evidence for its route and stage is complete and nothing is unresolved. A student who never joined says so after signing in with DigiLocker, and an officer decides. Every screen follows from that.

Terms used in this folder: "officer" means `AICTE_ADMIN` or `RO_OFFICER`; "registrar" means the `INSTITUTION` user; "row" (or "check") means one of the five evidence rows of a record; "case" is what people read for a row in `flags`; "attestation" is what people read for a row in `credentials`; "signal" is an officer-only pattern in `signals`.

## 1. Product principles

### P1. Claim, then countersign
- Every enrolment is shown first as what the college said, then as what each source said about it.
- The five rows are always shown in the deck's order: Identity, Seat, Joining record, Credits, Student.
- Every fact shows who supplied it and when, and whether it is independent of the college.
- A page never says an enrolment "is valid" or "is fraud". It says which sources confirm or contradict the claim, and the record's one status.

### P2. Evidence first
- A case is never shown without its evidence. The evidence summary line sits in the case row itself, not behind a click.
- Evidence reads as "what was claimed, what the source holds, the difference", with the rule it comes from (`rule_source`, e.g. "APH 2024-27 cl. 2.8(b)").
- Numbers in evidence carry their unit and their period ("120 approved seats, 2026-27").

### P3. Nothing is auto-rejected
- The system opens cases; only an officer decides: claim upheld, corrected, withdrawn or escalated, each with a reason and a note shown in the case history.
- No screen shows a case as "rejected", "blocked" or "fraud". Case status words are exactly: Open, Documents requested, Escalated, Claim upheld, Claim corrected, Claim withdrawn.
- A decision sheet names every consequence before the officer submits: the record's status, the seat, the attestation, who sees it.
- A decision is not evidence: an upheld claim still needs independent evidence to be Countersigned.
- A student's "No, I never joined" opens a priority dispute; it does not change the enrolment. Only a decision does.

### P4. Privacy is visible, not assumed
- Every student identifier on screen is masked in the standard shape: `XXXX XXXX 4417` for APAAR, `XXXXXX4521` for mobile. The full value never exists in the browser.
- Signals are for officers only. No college, university, student or verifier page shows or requests one.
- A student answers for themselves only after signing in with DigiLocker; an email only points there.
- When a student has no APAAR, the provisional id (`PRV-XXXXXXXX`) is shown with the label "Provisional id", never a blank.
- Pages that show student rows say so in a small line: "Viewing student records is logged." This is true (every read is audited) and the officer should know it.
- Students see exactly what the system holds on them and who looked, in plain words.

### P5. One status, never a score
- A record has exactly one status: Awaiting evidence, Countersigned, Under review or Disputed, always a word with its icon.
- One contradiction outranks any number of confirmations. There is no score that four positives can win: no "n of 5", no strip of segments, no percentage for one record.
- Aggregates (dashboard tiles, reports) may show the share of records Countersigned or the completeness of a college's uploads as a percentage, because those are shares of a population.
- The Integrity Index is dropped.

### P6. Neutral "no answer"
- A student who has not answered leaves the Student row Pending, phrased "no answer yet", in neutral grey. Silence never counts against the record or the college.
- Only a No after DigiLocker sign-in makes the Student row Contradicted.

### P7. Source unavailable is its own state, never a contradiction
- When a government source times out or is down, its rows read Source unavailable with the source name. They are never red and never Contradicted.
- The dashboard shows source health so an officer knows why many rows wait.
- Recheck evidence asks the sources again (rate-limited). A source still down leaves its rows Source unavailable.

### P8. Officers rank, they do not scroll
- Officer landing pages open on records by status and the ranked list (by open cases, then Disputed, then Under review), not on a blank search.
- Every list carries a count ("37 open cases in 9 institutions"), so the officer can say a defensible number out loud.
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
- Rows say Confirmed, Contradicted, Pending, Not yet due, Not applicable or Source unavailable; only a record says Countersigned.
- "Case", never "flag"; "attestation", never "proof" or "credential"; "dispute" for a student's "I never joined". Countersign issues enrolment and completion attestations, never degrees.
- Source words follow the deck: APAAR verification, AICTE approval vN (Seat Ledger, derived), State admission authority, ABC with the issuing body named, Student sign-in via DigiLocker, Study in India.

### Tone
- Plain sentences, present tense, second person for instructions ("Upload the admission file"), third person for facts ("The source did not respond").
- No exclamation marks. No "Oops". No jargon in headings (no "SD-JWT" in a student heading; say "your enrolment attestation").
- Numbers use Indian grouping with `en-IN` formatting: 1,20,000. Dates as `14 Jul 2026`. Times as `09:30 IST`.
- Buttons are verbs: "Request documents", "Uphold claim", "Withdraw claim", "Sign in with DigiLocker", "Share attestation".
- Decisions name every consequence before they are made: "The record is withdrawn. Seat CSE-R-014 is released. Enrolment attestation K7PQ3M2X is revoked. Nothing is deleted."

### How to word a case
Pattern: `<what the college claimed> against <what the source holds> <in scope> (<period>)`, then facts as label and value pairs, then the rule.

- Good: "132 admitted against 120 approved seats in CSE (2026-27)."
- Good: "Name on upload differs from the APAAR registry (similarity 71 of 100)."
- Bad: "Illegal excess admission detected." (accusatory, no numbers)
- Bad: "Fraud ring suspected." (no evidence, loaded word)

Severity words are only `Low`, `Medium`, `High`. Never "critical", "alert".

### How to word a notice to a student
Pattern: `<institution> says you joined <programme> (<academic year>).` then, after DigiLocker sign-in, exactly two choices and a line on what happens next. The email only points to the sign-in.

- Primary: "Yes, I joined"
- Secondary: "No, I never joined"
- Next-step line: "If you say no, a priority dispute opens and an AICTE officer looks into it first. Nothing changes for you until they decide."
- Never: "Verify your enrolment immediately", "Action required", deadlines in bold red.

### Error messages
- Say what happened, then what to do, in that order. "The APAAR registry did not respond. This check stays pending until a recheck or the next upload."
- Never show an error code alone; show the message and keep the code in small text for support: "Ref: SOURCE_UNAVAILABLE".
- 403 is phrased as a role statement, not a scolding: "This page is for AICTE officers. You are signed in as a registrar."

### Empty states
- State what would be here and the one action that fills it. "No open cases. Cases appear here after the first upload is checked."
- Week 1 nulls (`integrity_index`, `countersigned_pct`, `score`) read "Not yet computed", never "0" and never "N/A".
