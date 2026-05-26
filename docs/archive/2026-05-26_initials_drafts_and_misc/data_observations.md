# Data Observations — PADEA Operations Agent

**Purpose:** What the competition resource files actually contain, with attention to anomalies, ambiguities, and gaps that affect schema and agent design.

**Compiled:** 25 May 2026
**Source files:** `data/source/caterers.xlsx`, `data/source/sessions.xlsx`, `data/source/students.xlsx`, `data/source/caterer-contacts.pdf`, `data/source/caterer-menus.pdf`, `data/source/exclusions.pdf`, `data/source/absences.pdf`
**Companion documents:** `docs/decisions/decision_register.md`, `docs/current/assumptions.md`, `docs/cuts/deletions_ledger.md`

---

## How to read this document

This document is the inventory of what's in the data, written after opening the resource files for the first time on 22 May. It's structured as observations, not interpretations — interpretations live in `assumptions.md` and `decision_register.md`. Where an observation has driven a downstream decision, that decision is linked.

Some observations confirm prior assumptions; some surprised us; some surface a real ambiguity that needs a decision. All three are noted.

---

## Headline numbers

- **6 schools** across 4 regions (Redlands, South Brisbane, West Brisbane, Central Brisbane).
- **11 sessions** per week, spanning Monday through Thursday. No Friday sessions in the dataset.
- **320 students** enrolled across all sessions.
- **4 caterers** with pre-defined "able to serve" sets and current "currently serves" assignments.
- **6 caterer contacts** with four distinct role combinations.
- **~40 menu items** across caterers (~10 per caterer).
- **7 distinct session managers**, drawn from the tutor pool.

The 320 figure differs from earlier estimates in our planning docs (~290). The schema doesn't need to change but the student count is now grounded.

---

## Schools and sessions

### Schools and their session days

| School | Region | Session days |
|---|---|---|
| Moreton Bay Boys' College (MBBC) | Redlands | Tuesday |
| John Paul College (JPC) | South Brisbane | Tuesday, Wednesday |
| MacGregor State High School (MSHS) | South Brisbane | Thursday |
| Indooroopilly State High School (ISHS) | West Brisbane | Monday, Tuesday, Thursday |
| Loreto College (LC) | Central Brisbane | Monday, Tuesday |
| Cannon Hill Anglican College (CHAC) | Central Brisbane | Monday, Wednesday |

### Observations

- **No two sessions overlap in caterer + date.** Each (caterer × date) pair appears at most once, which means the assumption *"one caterer serves at most one school per day"* (Assumption 9) holds across the current dataset.
- **Session times vary by school.** MBBC starts 4:00pm; JPC starts 4:30pm; MSHS starts 3:15pm; the rest start 3:30pm. Dinner times similarly vary (4:45pm to 6:00pm). The schema correctly puts these on the session row, not the school row.
- **Year levels vary by school.** MBBC and CHAC carry Year 10–12. Loreto carries 10–12. ISHS and JPC carry Year 9–12. Year-level exclusions affect different cohort sizes at each school.
- **No two-session-per-day school.** No school has both a Monday-AM and Monday-PM session, for instance. The schema's day-of-week granularity is sufficient.

---

## Students

### Distribution per session

| Session | Students |
|---|---|
| MBBC Tuesday | 18 |
| JPC Tuesday | 29 |
| JPC Wednesday | 37 |
| MSHS Thursday | 9 |
| ISHS Monday | 37 |
| ISHS Tuesday | 46 |
| ISHS Thursday | 40 |
| LC Monday | 36 |
| LC Tuesday | 22 |
| CHAC Monday | 17 |
| CHAC Wednesday | 40 |
| **Total** | **331 (320 unique)** |

The discrepancy between rows-counted (331) and unique students (320) is because some students attend multiple sessions and appear in multiple sheets. The schema handles this correctly through `enrolments` — a student can have multiple enrolment rows pointing at different sessions.

### Dietary requirements — actual distribution

Of 320 students, 67 (21%) carry one or more dietary tags in the source data. The distribution:

| Tag value (as written) | Count |
|---|---:|
| Halal | 16 |
| No Beef | 8 |
| Vegetarian | 8 |
| Nut Free | 6 |
| Opted out of Catering | 6 |
| No Beef, No Pork | 2 |
| Gluten Free, Dairy Free | 2 |
| Nut Free, No Shellfish, Opted out of Catering | 1 |
| Halal, Vegetarian | 1 |
| Dairy Free | 1 |
| Gluten Free | 1 |
| No Fish | 1 |
| No Pork | 1 |
| No Pork, No Shellfish | 1 |
| No Red Meat | 1 |
| No Seafood | 1 |
| No Shellfish | 1 |
| Nut Free, No Seafood | 1 |

The remaining 253 students (79%) have no dietary tag.

### What this means for the dietary vocabulary

Our current `dietary_tags` vocabulary covered most of this, but a few observations:

1. **`No Pork` appears as an explicit tag, distinct from `Halal`.** The schema's "halal = absence of pork" rule (Assumption 5) handles menu-side matching correctly. On the student side, we'll have students tagged `halal` *and* students tagged `no_pork`. Functionally these select the same set of allowable menu items, but they're semantically different — keep both in the vocabulary and don't collapse them at ingest.

2. **`Opted out of Catering` is mixed into the dietary column.** It's not a dietary requirement, it's an enrolment-level fact. Confirms the schema's decision to handle opt-out as a boolean on `enrolments` (DR-11), not as a dietary tag. Ingest must recognise this string and *split* it: the dietary part goes to `student_dietary_tags`, the opt-out part flips `enrolments.opted_out = TRUE`. Example: `Nut Free, No Shellfish, Opted out of Catering` becomes two tags (`nut_free`, `no_shellfish`) plus an opt-out boolean.

3. **7 students opt out of catering.** Six with no other restrictions; one (Lei Li at ISHS Tuesday) with `Nut Free, No Shellfish`. The fact that an opted-out student has dietary tags preserved is correct — they could un-opt-out next term and the data is ready.

### Vocabulary needed (final list for v1)

Based on the actual data, the controlled vocabulary needs:

- `halal`, `vegetarian`, `gluten_free`, `dairy_free`, `nut_free`, `contains_pork` (item-only tag, derived at ingest)
- `no_beef`, `no_pork`, `no_red_meat`, `no_fish`, `no_seafood`, `no_shellfish`

That's 12 tags. The `Opted out of Catering` string is *not* a tag — it's parsed and routed to the enrolment row at ingest.

---

## Caterers

### The pricing anomaly

| Caterer | Price per item | Delivery |
|---|---:|---|
| Lakehouse Victoria Point | $35.00 (excl GST) | $0 |
| Terrific Noodles | $20.50 (excl GST) | $30 per school per trip |
| Kenko Sushi House | **$5.50 (incl GST)** | $10 per school per trip |
| Guzman y Gomez | $15.00 (incl GST) | $50 per trip |

Two anomalies in this table:

1. **Kenko's $5.50 per item is markedly low for sushi.** Real-world catering for sushi typically sits at $10–18 per box. $5.50 incl GST is below plausible cost-of-goods. Could be a data typo, a strategic loss-leader, a different meal-size tier, or an unstated assumption about the dataset.

2. **Lakehouse's $35.00 per item is on the high end** for school catering but within plausible range for premium restaurant-style boxed meals.

**Decision:** Treat all four prices as accurate at ingest. Do not normalise, correct, or warn at ingest. The system should not silently overwrite source data on the basis of plausibility heuristics. A note will appear in the memo flagging the observation. *(See `docs/cuts/deletions_ledger.md` for the deliberate non-correction.)*

### MOQ (minimum order quantity) reality check

The MOQ table in `caterers.xlsx`:

| Caterer | 4 items | 5 items | 6 items |
|---|---:|---:|---:|
| Lakehouse | 15 | 20 | 25 |
| Terrific | 10 | 20 | 30 |
| Kenko | 35 | 40 | 45 |
| GyG | 20 | 25 | 30 |

Comparing each caterer's MOQ at 6 items against their current weekly volume (sum of student counts on the sessions they currently serve):

| Caterer | Sessions served | Current weekly volume | MOQ at 6 items | Margin |
|---|---|---:|---:|---:|
| Lakehouse | MBBC Tue | 18 | 25 | **–7 (under MOQ)** |
| Terrific | JPC Tue + JPC Wed + MSHS Thu | 75 | 30 | +45 |
| Kenko | ISHS Mon + Tue + Thu | 123 | 45 | +78 |
| GyG | LC Mon + Tue + CHAC Mon + Wed | 115 | 30 | +85 |

**Lakehouse is below MOQ at the current 6-item variety.** At 4 items, the MOQ is 15 and Lakehouse meets it. At 5 items, MOQ is 20 and Lakehouse is just over. This means the operationally-feasible variety for Lakehouse is constrained by their MOQ-vs-volume reality — they probably get ordered with 4 items, not 6.

**Implication for the agent:** when generating Lakehouse's order, menu variety has to be sized to keep the order at or above MOQ. This is a real escalation trigger — *not* a hypothetical one. Demo opportunity.

Conversely, Kenko, Terrific, and GyG are well above MOQ even at maximum variety. The MOQ shortfall escalation will not fire for them in normal operation. It would only fire under heavy partial-exclusion scenarios.

### "Able to serve" vs "currently serves"

From `caterer-contacts.pdf`:

| Caterer | Currently serves | Able to serve (overlap) |
|---|---|---|
| Lakehouse | MBBC | MBBC, **CHAC** |
| Terrific | JPC, MSHS | JPC, MSHS, **Loreto** |
| Kenko | ISHS | ISHS (no expansion) |
| GyG | Loreto, CHAC | Loreto, CHAC, **MSHS** |

Each caterer except Kenko has at least one "able but not currently serving" school. These are the rotation candidates:

- Lakehouse could take CHAC (currently GyG).
- Terrific could take Loreto (currently GyG).
- GyG could take MSHS (currently Terrific).

These overlaps drive the rotation mechanic. A rotation decision is *operationally feasible* only because at least one school has two caterers eligible to serve it. Kenko's lack of overlap means ISHS rotation is not an option in v1 — no fallback caterer.

**This is the leverage the satisfaction loop has.** If GyG's rating drops at CHAC, the agent can draft a swap to Lakehouse. If Terrific's rating drops at MSHS, the agent can draft a swap to GyG. Without these overlaps the rotation has no teeth.

### Caterer contacts — placeholder routing

From `caterer-contacts.pdf`, the email addresses are **deliberately routed to Padea-controlled inboxes** during competition assessment:

- Carmen Gabrielle (Lakehouse order taker) → `carmen@padea.com.au`
- Dylan Chern (Terrific order taker) → `cherndylan@gmail.com`
- James Chern (Terrific chef, no-cc) → `dylanchern808@gmail.com`
- Big Mom (Kenko, both roles) → `hellopadea@gmail.com`
- Big Chicken (GyG order taker) → `carmengabrielleee@gmail.com`
- Medium Giraffe (GyG chef, cc-on-orders) → `dylan@padea.com.au`

The names are obvious placeholders ("Big Mom", "Big Chicken", "Medium Giraffe") — these are not real caterer staff. The email-to-name pairings appear inverted in places (Carmen's address goes to a different person; Dylan Chern shares his name with the company owner). All confirmed as intentional fixtures, not data quality issues (Assumption 17).

**For the agent:** when ingesting contacts, preserve the email/name pairings exactly as given. Do not try to repair the apparent inversions. They are part of the test setup.

---

## Menus

Four menus, ~10 items each, with dietary annotations in legend form (`GF`, `DF`, `NF`, `VO`) plus the rule "non-pork meals are halal."

### Menu observations

- **All four caterers offer 10 items each.** Variety is symmetric. No caterer is starved for options.
- **VO is a swap capability, not a property** (Assumption 6 confirmed by the menu data — e.g. Lakehouse's `Chicken, Bacon, Avo Wrap VO` is not vegetarian; the caterer offers a vegetarian variant on request).
- **Pork-containing items are limited.** A scan of all four menus shows pork explicitly in: Lakehouse's `Chicken, Bacon, Avo Wrap`; Terrific's `Grilled Pork Vermicelli Salad` and `Bacon Carbonara`; GyG's `Pulled pork burrito bowl`. That's 4 items across 40 (10%). The rest are halal-eligible by the "non-pork = halal" rule.
- **Beef-containing items are common.** Most caterers have 2-3 beef items. For the 10 students tagged `No Beef` (including the 2 with `No Beef, No Pork`), matching needs to identify beef in item names — same keyword-based ingest as pork.
- **Several items have ambiguous dietary keywords.** Items like `Spaghetti meatballs` need keyword inference (meatballs → likely beef? or could be pork?). For v1, conservatism is safer — if the keyword scan is uncertain, flag for review at ingest rather than auto-tagging.

### Items per caterer (for MOQ variety planning)

If the agent orders the same 4–6 items per session for a given caterer × week, the question is: which 4–6? The dataset doesn't tell us — that's a system decision. v1 logic should pick items that:

1. Cover all dietary tags represented in the student cohort for that week.
2. Stay within MOQ for the caterer.
3. Vary week-to-week to avoid the "same Korean Beef Bulgogi every week" complaint that the brief implies is driving dissatisfaction.

---

## Absences

`absences.pdf` lists 10 absences across a single week, dated 1–4 May 2026:

| Date | School | Student | Present in students.xlsx? |
|---|---|---|---|
| 02/05 | MBBC | Noah Baker | ✓ |
| 02/05 | JPC | Christina Hu | ✓ |
| 02/05 | JPC | Nathan Smith | ✓ |
| 04/05 | MSHS | Rose Smith | ✓ |
| 02/05 | ISHS | Charlie Morris | ✓ |
| 02/05 | ISHS | Jack Carter | ✓ |
| 02/05 | ISHS | Charlie Mitchell | ✓ |
| 01/05 | LC | Holly Hill | ✓ |
| 01/05 | LC | Imogen Evans | ✓ |
| 03/05 | CHAC | Henry Cook | ✓ |

**All 10 absentees cross-reference cleanly to enrolled students.** No orphans, no unknown students. This is a sanity check for the schema's `absences → students` foreign key — every absence will find a parent student row.

The absences PDF gives names only — no parent contact, no email source, no timestamp. For the simulated email workflow, the agent ingest layer needs to *fabricate plausible parent emails* that produce the same 10 absence rows. That's a build-time concern, not a schema concern.

Three Indooroopilly absences arrive on 02/05 (Tuesday). The Tuesday session was actually held that day (date matches sessions.xlsx — the data is internally consistent). The other dates also match real session occurrences.

---

## Exclusions

`exclusions.pdf` lists three exclusions:

| # | Date | School | Scope | Reason |
|---|---|---|---|---|
| 1 | 04/05 | ISHS | Whole session | Open Day |
| 2 | 02/05 | Loreto | Whole session | Parent-Teacher Interviews |
| 3 | 03/05 | CHAC | Years 12 and 10 (Year 11 still attends) | School Camp |

### Observations

- **Two whole-session exclusions and one partial.** The partial case (CHAC) is the operationally interesting one — it tests the agent's ability to size an order to the *remaining* cohort. Year 11 students still attend; Years 10 and 12 don't.
- **No exclusion has a source-email simulation.** Like absences, these arrive as text content the agent will need to ingest as emails for the demo to feel real.
- **The CHAC partial case lines up with our 10% attendance buffer rule.** At CHAC Wednesday the typical cohort is 40 students. Year 11 is one of three year levels (10, 11, 12) so roughly 13 students would normally attend in the Year 11 group. With Years 10 and 12 excluded but social-reality walk-ups expected, the buffer rule says +10% of the excluded cohort (rounded up). Roughly 13 students excluded per year level × 2 year levels = 26 excluded students, of which 10% = 3 buffer meals. Total order: ~13 + 3 = ~16 meals. This is a concrete number for the demo.

### Exclusions that aren't in the data but were anticipated

The decision register (DR-29 area) anticipates: subject-specific exclusions (e.g. "all Physics students at camp"), one-off student lists from schools, exclusion walk-backs. None of these appear in the provided dataset. The schema supports them through the existing patterns; the build doesn't need to implement them in v1.

---

## Cross-referencing — what hangs together

The data is internally consistent. Specifically:

- Every absence references a real student at the right school.
- Every exclusion references a real session on a date that matches `sessions.xlsx`.
- Every session has a corresponding student sheet in `students.xlsx`.
- Every student sheet maps cleanly to one session.
- Every caterer in `caterers.xlsx` appears in `caterer-contacts.pdf` and has a menu in `caterer-menus.pdf`.

No orphan rows, no missing references, no contradictions across files. The "messy" part of the data is in *formats and interpretations* (dietary tags as free text, opt-out mixed in, placeholder emails), not in cross-table integrity.

---

## Observations that change v1 design

Summary of things to update from this review:

1. **Student count is 320, not ~290** — update everywhere that estimate appeared.
2. **Lakehouse is structurally below MOQ at 6 items** — this is a *real* escalation trigger for the demo, not just an architectural one. Plan the demo around it.
3. **Dietary vocabulary needs 12 tags** as listed in the "Vocabulary needed" subsection. `No Pork` joins as a distinct tag from `Halal`.
4. **`Opted out of Catering` is parsed at ingest** into the enrolment boolean — not added to the dietary vocabulary.
5. **Pricing anomaly** (Kenko $5.50, Lakehouse $35) is documented and *not corrected*. Memo note.
6. **Caterer contact email/name placeholder routing** is intentional — preserve exact pairings at ingest.
7. **The CHAC partial-exclusion case** is the cleanest demo opportunity for the year-level exclusion mechanic. Build the demo around it.
8. **No source emails for absences or exclusions** — these need to be fabricated as simulated incoming emails to make the demo end-to-end.

---

## Open questions for Dylan (Wednesday meeting)

1. **The Kenko pricing.** Is $5.50 incl GST per item correct? If so, is it a strategic loss-leader or a different meal size to the others?
2. **The placeholder emails.** Should the agent send to the placeholder addresses during the demo (e.g. `dylan@padea.com.au`), or to a simulated outbox only? Clarifying because some addresses route to Dylan.
3. **The Lakehouse MOQ situation.** Is MBBC's 18-student size really under MOQ in practice today? If yes, how is it currently handled — does Lakehouse soften the rule, or does Padea pay the shortfall as a contract minimum?
4. **The dataset week.** All absences and exclusions are dated 1–4 May 2026. Is this a single representative week for the demo, or do we need to simulate the rolling weekly cadence?

---

*End of data observations. Update this file when new observations emerge from operational use. Do not delete observations — strike through and date if superseded.*
