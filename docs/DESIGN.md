# Countersign design system

Every enrolment, countersigned. This document is the contract between the UI agent and the frontend: what the system looks like, why, and exactly how to drop it into `apps/web`.

Source files live in `design/`:

| Path | What it is |
|---|---|
| `design/tokens.css` | Tailwind v4 `@theme` tokens, shadcn variables, light and dark palettes |
| `design/globals.css` | Drop-in `apps/web/app/globals.css`: base styles, focus ring, `.ledger-table`, `.stamp`, `.countersign-score`, `.kpi-strip` |
| `design/brand/` | `logo.svg`, `mark.svg`, `favicon.svg`, `og.svg` (1200 x 630), all pure SVG with outlined text |
| `design/components/` | Eleven reference components for `apps/web/components/brand/` |
| `design/preview.html` | Static preview of every element in light and dark; open it in a browser |
| `design/tools/contrast.py` | Computes every contrast ratio in this document from `tokens.css` |

## 1. Principles

1. **Evidence before adjectives.** A status is never a colour alone: every badge has a glyph and a word, and pending and not-applicable states also differ by border style (dashed, dotted) so they survive greyscale print. Every flag shows its evidence in the officer's own language.
2. **The page is the ledger.** Tables are not framed in cards; the table is the page. Feint blue rules separate rows, a heavier rule lands every fifth row so the eye can count, and a pink margin rule frames a block the way ruled paper does. Cards appear only for things that are not rows: a state in the grid, a flag's evidence.
3. **One stamp per page.** The countersign score ("4 of 5") is the one bold element on any view. Everything around it is quiet: hairlines, muted labels, no shadows worth noticing.
4. **Numbers are set to be compared.** Tabular lining figures in every column, right-aligned, Indian digit grouping (18,960 and 1,89,600). Large standalone numbers use proportional figures.
5. **Nothing here says "reject".** The vocabulary is pass, fail, pending, not applicable; open, documents requested, cleared, escalated, confirmed. The system presents countersignatures and the officer decides.
6. **Indian-government-adjacent, not imitation.** No emblem, no tricolour, no saffron accents. The vernacular is the countersigned document: writing ink, a violet seal, ruled paper, serif headings.

## 2. Type

Three faces from Google Fonts. The `@import` line is the first line of `globals.css`; use `next/font` instead in production (see Integration).

| Role | Face | Where |
|---|---|---|
| Display | **Source Serif 4** (400, 600, 400 italic, optical size axis) | h1 to h3, the countersign score, KPI values, state codes, `.stamp` |
| Interface | **IBM Plex Sans** (400, 500, 600, 400 italic) | everything else; true tabular figures |
| Code | **IBM Plex Mono** (400, 500) | seat codes, masked APAAR ids, provisional ids, hashes, audit sequences |

Scale (px, line-height): 11/16 `text-2xs`, 12/16 `text-xs`, 13/20 `text-sm`, 14/22 `text-base`, 16/24 `text-md`, 18/26 `text-lg`, 22/28 `text-xl`, 28/34 `text-2xl`, 36/42 `text-3xl`, 44/50 `text-4xl`.

- Body is 14px. Tables run at 13px. Badges and table heads at 12px. Nothing below 11px, and 11px only for chart axis labels and swatch captions.
- Headings: h1 36, h2 28, h3 22 in Source Serif 4 semibold, tracking -0.01em, line-height 1.15. h4 is Plex Sans 16 semibold (a serif at 16px loses its shape).
- Paragraph measure 68ch maximum (`p { max-width: 68ch }` in globals).
- No all-caps labels anywhere except inside `.stamp`, where uppercase is the stamp's own convention. No eyebrow labels above headings. No middle dots between metadata; use commas.
- Numbers: `.num` (tabular, right-aligned) on every numeric cell. KPI values and the score use `proportional-nums`.

## 3. Colour

All values live in `tokens.css` as plain CSS variables and as Tailwind utilities (`bg-paper`, `text-ink-muted`, `border-rule`, `bg-check-pass-soft`, `text-flag-open-ink`, `bg-index-4` and so on). Dark mode is the `.dark` class on `<html>`.

### 3.1 Paper and ink

| Token | Light | Dark | Use |
|---|---|---|---|
| `paper` | `#f3f3ef` | `#121419` | page background (stone white, deliberately not cream) |
| `paper-raised` | `#fcfcfa` | `#1a1d25` | cards, table bodies, inputs, popovers |
| `paper-sunken` | `#e9e9e4` | `#0d0f13` | sidebar, secondary buttons, muted blocks |
| `ink` | `#171b26` | `#eceae2` | text |
| `ink-muted` | `#5a6072` | `#a6abb8` | secondary text, labels, table heads |
| `ink-faint` | `#7b8194` | `#8a8f9c` | placeholders, masked digits, disabled; large text only (3.78:1 light) |
| `ink-blue` | `#24407d` | `#8ea8e6` | primary action, links, selection, focus ring |
| `seal` | `#5b3f8c` | `#b39be5` | the countersign mark, `.stamp` default, escalated |
| `line` | `#d6d7d0` | `#2c3038` | neutral borders (shadcn `--border`) |
| `rule` | `#c7d2e6` | `#2a3449` | feint blue ledger rule between rows |
| `rule-strong` | `#9fb0d0` | `#3d4b6b` | table head rule, every fifth row, section rules |
| `rule-margin` | `#e0a9ae` | `#5a3a42` | pink margin rule; at most one per block |

### 3.2 Semantic colours and what they mean

Every semantic state has three tokens: `-soft` (tint background), `-ink` (text on the tint and on paper, at least 4.5:1) and the bare name (the mark: glyphs, borders, chart marks, at least 3:1). They alias seven hue families so that the same meaning always has the same hue:

| Hue | Means | Used by |
|---|---|---|
| ok (green) | a source agreed | check PASS, flag CLEARED, consent LINKED |
| alert (red) | a source disagreed, or an officer confirmed a problem | check FAIL, severity HIGH, flag CONFIRMED |
| caution (ochre) | waiting on someone | check PENDING, severity MEDIUM, flag DOCS_REQUESTED, consent PENDING, seat RELEASED |
| neutral (grey) | nothing to say, by design | check NA, consent REFUSED, seat FREE |
| blue (ink) | in progress, assigned, ours | severity LOW, flag OPEN, seat ASSIGNED, chart slot 1, the Integrity ramp |
| seal (violet) | sent up a level; the brand's stamp | flag ESCALATED, `.stamp`, the mark |
| teal | a different legal regime, not a problem | consent INTERNATIONAL |

Rules that must not be broken:

- **REFUSED is grey, never red.** Refusing APAAR is lawful (Supreme Court order, DPDP Act) and never blocks admission. A red refusal would read as a mark against the student.
- **NA is grey and dotted, never red or ochre.** Not applicable is not a failure and not a wait.
- **Severity is urgency, not guilt.** HIGH shares the alert hue with FAIL and CONFIRMED because all three mean "look now", but a HIGH flag that is OPEN says nothing about fault. Never colour a row red because of severity alone; colour the badge.
- **Red text is reserved.** `check-fail-ink` on a number means an open-flag count greater than zero (KPI tile, state card) and nothing else. Zero is muted, not green.
- **Green never decorates.** No green buttons, no green success banners for routine saves. Green means a countersignature passed.
- **Ink blue is the only interactive colour.** Links, primary buttons, selection, focus. Do not use `seal` for buttons; it belongs to the mark and to escalation.
- **Chart colours never mean status, status colours never mean series.** A chart of pass/fail counts uses the status tokens; a chart of routes uses `chart-1` to `chart-6`, assigned in order, never cycled, never reordered when a filter removes a series.
- **Text never wears a chart colour.** Labels and legends stay in `ink` or `ink-muted` with a swatch beside them.
- **The pink margin rule is decoration with a job** (framing the facts in an evidence card, the left edge of a ledger table). It is never a status and never appears twice in one block.

### 3.3 Charts

Categorical (Recharts `fill="var(--chart-1)"`): blue `#3a5ba8`, orange `#c86a1e`, teal-green `#1f8f74`, gold `#a88718`, violet `#8a5fc2`, rose `#c4467a` (light); `#5b7fd1 #c9712f #2e9c80 #ae8d22 #9a7bd6 #d6557c` (dark). Validated with the dataviz checker in both modes: lightness band pass, chroma pass, worst adjacent colour-vision-deficiency distance 10.1 light / 10.5 dark (target 8), worst normal-vision 15.1 / 15.5 (floor 15), all six at or above 3:1 on the card surface (gold is 3.33:1 light). The first three slots also pass the stricter all-pairs test for scatter and small multiples; past three series in those forms, fold to "Other".

Sequential, for the Integrity Index (0 to 100): seven steps of ink blue, `index-1` (lightest, near zero) to `index-7`. In dark mode the anchor flips so step 1 recedes toward the dark surface. Luminance is strictly monotonic in both modes. A single-series bar chart uses `chart-1` for every bar; one series needs no legend.

Chart chrome: `chart-grid` hairline, `chart-axis` baseline, labels in `ink-muted`, bars at most 24px thick with 4px rounded data-ends, 2px lines, no dual axes.

### 3.4 Contrast (computed, not guessed)

`python3 design/tools/contrast.py` parses `tokens.css` and checks 90 pairs; `--md` prints the full table. Headline ratios (WCAG 2, light / dark):

| Pair | Light | Dark |
|---|---|---|
| ink on paper | 15.46 | 15.30 |
| ink on paper-raised | 16.74 | 13.99 |
| ink-muted on paper | 5.63 | 8.02 |
| ink-blue (links) on paper | 8.97 | 7.80 |
| primary button label | 9.71 | 7.80 |
| seal on paper | 7.45 | 7.66 |
| ok ink on ok soft | 6.82 | 8.46 |
| alert ink on alert soft | 7.07 | 7.51 |
| caution ink on caution soft | 6.72 | 8.39 |
| neutral ink on neutral soft | 6.92 | 8.50 |
| blue ink on blue soft | 8.13 | 7.99 |
| seal ink on seal soft | 8.21 | 8.13 |
| teal ink on teal soft | 6.37 | 8.32 |
| ok mark on paper | 4.77 | 8.03 |
| alert mark on paper | 5.55 | 6.23 |
| caution mark on paper | 4.26 | 8.12 |
| neutral mark on paper | 4.21 | 6.37 |
| blue mark on paper | 5.82 | 6.70 |
| seal mark on paper | 5.67 | 6.54 |
| teal mark on paper | 4.25 | 8.19 |
| chart-1 to chart-6 on card (lowest) | 3.33 | 4.33 |
| index-7 on card | 9.71 | 9.32 |

Every `-ink` token is at least 4.5:1 on its tint, on the page and on the card. Every mark is at least 3:1. `ink-faint` is 3.78:1 light and is restricted to large text, placeholders and the masked X groups (which carry no information).

## 4. Layout

Twelve-column grid, 24px gutters, 16px side padding on phones, content max-width 1440px. Spacing is a 4px grid (`--spacing: 0.25rem`).

**Dashboard** (`/aicte`, `/ro`, `/college`, `/university`)

```
+-----------------------------------------------------------------------+
| mark  Countersign          All India, 2026-27            admin  menu  |  56px bar, rule-strong below
+-----------------------------------------------------------------------+
| h1 Enrolment integrity, 2026-27                       [year] [export] |
+-----------------------------------------------------------------------+
| Institutions | Programmes | Approved | Enrolments | Open flags | C/S |  .kpi-strip, one ruled strip
|     50       |    212     |  18,960  |   10,342   |     37     | not |
+-----------------------------------------------------------------------+
| h2 By state                                   grid | table toggle     |
| [MH] [TN] [KA] [GJ] ...   StateGridCard, 4 per row at 1280, 2 on tablet, 1 on phone
+-----------------------------------------------------------------------+
| h2 By region   .ledger-table, 10 rows                                 |
+-----------------------------------------------------------------------+
```

**Table pages** (institutions, enrolments, seats, flags, audit): h1, one row of filters (search, selects) above the table, the table full width, pagination in the table footer. Sidebar 240px on the left for AICTE and RO roles; institutions and students get a top bar only.

**Detail pages** (institution, enrolment, flag): two columns, 8/4 at 1024 and up, stacked below. Left: the claim (what the college uploaded) and the countersign block (`CountersignScore` size `lg`, then one `CheckBadge` per check with its source and time). Right: flags as `EvidenceCard`s, then an audit trail list. The score is the first thing in the left column, directly under the h1.

Density: dashboard sections are separated by 32px; inside a section, 16px. Cards have 12px padding. Nothing floats, nothing is centred except the empty state.

## 5. Iconography

Lucide only, `size-3` (12px) inside badges, `size-4` in buttons and table cells, `size-5` for empty states. Stroke width stays at Lucide's default 2. Icons never appear without a word except in `compact` badges, where the word moves to `aria-label` and `title`.

Fixed mapping (used by the reference components):

| State | Icon |
|---|---|
| PASS / FAIL / PENDING / NA | `Check` / `X` / `Clock` / `Minus` |
| OPEN / DOCS_REQUESTED / CLEARED / ESCALATED / CONFIRMED | `CircleDot` / `FileQuestion` / `CircleCheck` / `ChevronsUp` / `Stamp` |
| LINKED / REFUSED / PENDING / INTERNATIONAL | `Link2` / `Link2Off` / `Clock` / `Globe` |
| Severity | no icon; a one, two or three bar meter drawn in CSS |

The brand mark (`mark.svg`) is never used as an icon inside the interface; it appears once, in the top bar, and on documents.

## 6. Tables

Officers scan thousands of rows. `.ledger-table` encodes the rules:

- Row height 36px (`--row-default`), or 32px with `.ledger-table--dense` for the audit log and seat lists. Never taller than 44px.
- 13px text, 12px head, head sticky, head labels in `ink-muted` medium weight, sentence case.
- Feint rule between rows, heavier rule every fifth row, heavier rule above the head and the footer.
- Numbers right-aligned with `.num`; codes in `.code`; names and free text left; `white-space: nowrap` by default, `.wrap` on the one column allowed to wrap.
- Hover is a 40% wash of `blue-soft`; selection is `blue-soft`. No zebra striping (the rules do that job).
- Badges inside cells are 20px tall and never stack vertically; two badges sit side by side, more than two collapse to the first plus a count.
- Column order on enrolment tables: student, APAAR, consent, route, seat, year, countersign, flags. Countersign and flags are the last two because they are what the officer acts on.
- Pagination default 25, max 200 (API contract). Show "1 to 25 of 571" in tabular figures.

## 7. Motion

Near none. No page-load animations, no fade-ins, no hover transitions on cards. What remains:

- Native disclosure (accordion, popover, dialog) may use shadcn's defaults if `tw-animate-css` is installed; the system does not depend on it.
- A row that changes state after an action (cleared, escalated) may flash its `-soft` tint for 600ms once, so the officer sees what changed.
- `prefers-reduced-motion: reduce` removes all of the above (globals.css).

## 8. Accessibility

- WCAG 2.1 AA throughout; ratios above are computed from the tokens and re-checked on every change.
- One focus ring everywhere: 2px `ink-blue` outline, 2px offset, never removed (`:focus-visible` in globals.css).
- Colour never carries meaning alone: glyph + word on every badge, border style on pending and not-applicable, bar count on severity, a number next to every Integrity tint.
- Every badge is `role="img"` with an `aria-label` that reads as a sentence ("Identity: Pass (APAAR)", "Severity high").
- The score reads as "Countersigned 4 of 5. Identity pass, Admission pass, Seat fail, Studying pass, Student pass."
- Masked ids expose only "APAAR ending 4417" to assistive technology; the X groups are `aria-hidden`.
- Minimum target size 32px for buttons and row actions; badges are not targets.
- Both themes set `color-scheme`, so native controls and scrollbars match.
- `.stamp` is uppercase visually but its text is written in sentence case so screen readers do not spell it out.

## 9. Integration (for the frontend agent)

All paths are relative to the repo root. Nothing here touches files outside the UI agent's ownership (`app/globals.css`, `components/ui/**`, `components/brand/**`) except where noted.

1. **Stylesheets.** Copy `design/globals.css` to `apps/web/app/globals.css` and `design/tokens.css` to `apps/web/app/tokens.css`. Delete the shadcn-generated `:root` / `.dark` / `@theme inline` blocks from the old `globals.css` (tokens.css replaces them). Keep exactly one `@custom-variant dark (&:is(.dark *));` (globals.css has it). If your scaffold imports `tw-animate-css`, keep that line after `@import "tailwindcss";`; the system works without it.
2. **Fonts.** For development the Google Fonts `@import` at the top of `globals.css` is enough. For production, in `app/layout.tsx`:

   ```tsx
   import { Source_Serif_4, IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
   const serif = Source_Serif_4({ subsets: ["latin"], weight: ["400", "600"], style: ["normal", "italic"], variable: "--font-source-serif" });
   const sans = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "500", "600"], style: ["normal", "italic"], variable: "--font-plex-sans" });
   const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-plex-mono" });
   <html lang="en" className={`${serif.variable} ${sans.variable} ${mono.variable}`}>
   ```

   then delete the `@import url(...)` line from `globals.css`. `tokens.css` already reads these three variables with a fallback to the Google names.
3. **Dark mode.** Toggle the `dark` class on `<html>` (next-themes with `attribute="class"`, or a cookie). Nothing else is needed; `color-scheme` follows.
4. **shadcn.** `components.json` must have `"cssVariables": true`. Every shadcn primitive picks up the theme through `--background`, `--primary`, `--ring` and the rest. `--radius` is 6px, so `rounded-lg` is 6, `rounded-md` 4, `rounded-sm` 2. Do not re-run `shadcn init`; add primitives with `shadcn add <name>` as usual. Recharts: pass `fill="var(--chart-1)"`, `stroke="var(--chart-axis)"`.
5. **Brand.** Copy `design/brand/` to `apps/web/public/brand/`. Favicon: copy `favicon.svg` to `apps/web/app/icon.svg` (Next.js file-based metadata). The top bar uses `<img src="/brand/logo.svg" alt="Countersign" height={32} />`; both SVGs re-ink themselves under `prefers-color-scheme: dark`. Open Graph: crawlers need a raster, so render `og.svg` to PNG once (`npx sharp-cli -i design/brand/og.svg -o apps/web/app/opengraph-image.png`, or any SVG to PNG tool) rather than linking the SVG.
6. **Components.** Copy `design/components/*.tsx` to `apps/web/components/brand/`. They import only `lucide-react` and `@/lib/utils` (`cn`). Each file declares the types it needs, copied verbatim from `API_CONTRACT.md` section D; once `lib/types.ts` exists you may replace those local declarations with imports, or leave them. Nothing else changes.
7. **Utilities in markup.** Use `.ledger-table` on every data table (`<table className="ledger-table">`, `.num` on numeric cells, `.code` on code cells), `.kpi-strip` around `KpiTile`s, `.stamp` for stamped labels, `.countersign-score` only through `CountersignScore`.
8. **Verify.** Open `design/preview.html` in a browser (light panel, then dark; `#light` or `#dark` in the URL shows one). After editing any colour run `python3 design/tools/contrast.py`; it exits 1 if a pair falls below AA.

## 10. Reference components

| Component | Props (required in bold) | Notes |
|---|---|---|
| `CountersignScore` | **countersign**, size `sm/md/lg`, numberOnly | null score renders "Not yet countersigned" |
| `CheckBadge` | **status**, type, source, compact | "Identity: Pass" when `type` is given |
| `SeverityBadge` | **severity**, compact | one to three bars plus the word |
| `FlagStatusBadge` | **status**, compact | CONFIRMED uses the `Stamp` icon |
| `ConsentBadge` | **status**, compact | REFUSED is neutral |
| `SeatCodePill` | **seatCode**, status, showStatus | splits `CSE-R-087` so the pool letter stands out; FREE is dashed |
| `MaskedApaar` | **apaarMasked**, provisionalId | X groups dimmed, last four emphasised; `PRV-` fallback |
| `KpiTile` | **label**, **value**, unit, hint, tone, format | Indian grouping by default; put tiles in `.kpi-strip` |
| `StateGridCard` | **row**, integrityIndex, selected, onSelect | becomes a button when `onSelect` is given; left rule from the Integrity ramp |
| `EvidenceCard` | **type**, **severity**, **evidence**, source, checkedAt, badges, actions | left rule carries severity; facts framed by the margin rule |
| `EmptyState` | **title**, description, icon, action, variant | one action at most; "coming in Week N" wording for absent routes |

All eleven typecheck under `strict` against React 19, lucide-react and a `cn` built from clsx + tailwind-merge.
