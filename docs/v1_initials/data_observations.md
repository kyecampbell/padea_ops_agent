# Data Observations — Padea Operations Agent

**Purpose:** What the source data actually contains. Factual observations from the resource files, recorded so that downstream design work has a grounded reference for what's true about the data. Interpretations, design choices, and operational rules live in `assumptions.md` and `decision_register.md`. A short list of candidate assumptions appears at the bottom of this document for processing into `assumptions.md` — they are not part of the observation set.

**Compiled:** 25 May 2026
**Source files:** `data/source/caterers.xlsx`, `data/source/sessions.xlsx`, `data/source/students.xlsx`, `data/source/caterer-contacts.pdf`, `data/source/caterer-menus.pdf`, `data/source/exclusions.pdf`, `data/source/absences.pdf`
**Companion documents:** `assumptions.md`, `decision_register.md`, `schema.md`.

---

## How to read this document

This document is a literal inventory of what's in the data — what the files contain, what patterns appear across files, and what anomalies or ambiguities are present. Where an observation has implications, the implications are recorded as candidate assumptions at the bottom of this document and resolved in `assumptions.md`.

---

## Observation period

The source data describes the week of **Monday 1 May 2026 to Thursday 4 May 2026**. All dated records (sessions, absences, exclusions) fall within this Mon–Thu window. The dataset contains no records for Friday 5 May, Saturday 6 May, Sunday 7 May, or for any other week.

The dataset does not include any non-dated records that would describe ongoing operation outside this window (e.g. a tutor roster, a parent contact registry, an order ledger, a communications archive). Where the data references entities that would have a longer history in a live operation — students, caterers, schools, sessions — those entities appear as static records without dated history.

---

## Headline numbers

The source data describes 6 schools, 4 caterers, 11 sessions across the week (Monday through Thursday), **320 enrolment rows** across all session sheets, 6 named caterer contacts, **40 menu items total (10 per caterer)**, and 7 distinct named session managers. There are no Friday sessions in the dataset.

Of the 320 enrolment rows, **13 names appear at two schools each**, giving 307 distinct names overall. Whether each cross-school name match is one student enrolled at two schools or two different students sharing a name is not determinable from the files; this is recorded as a candidate assumption at the bottom of this document.

---

## Schools and sessions

The 6 schools and their session days in this dataset:

| School | Region | Session days |
|---|---|---|
| Moreton Bay Boys' College (MBBC) | Redlands | Tuesday |
| John Paul College (JPC) | South Brisbane | Tuesday, Wednesday |
| MacGregor State High School (MSHS) | South Brisbane | Thursday |
| Indooroopilly State High School (ISHS) | West Brisbane | Monday, Tuesday, Thursday |
| Loreto College (LC) | Central Brisbane | Monday, Tuesday |
| Cannon Hill Anglican College (CHAC) | Central Brisbane | Monday, Wednesday |

In this dataset, no school has more than one session on the same day.

### Session timing

Each session in the dataset runs for exactly **3 hours (180 minutes)**, and the dinner time is recorded at exactly the **midpoint** of each session — 90 minutes after start, 90 minutes before end. This holds for all 11 sessions without exception.

| School | Start | End | Length | Dinner |
|---|---|---|---|---|
| MBBC | 4:00pm | 7:00pm | 3h | 5:30pm |
| JPC (Tue & Wed) | 4:30pm | 7:30pm | 3h | 6:00pm |
| MSHS | 3:15pm | 6:15pm | 3h | 4:45pm |
| ISHS (Mon, Tue, Thu) | 3:30pm | 6:30pm | 3h | 5:00pm |
| LC (Mon & Tue) | 3:30pm | 6:30pm | 3h | 5:00pm |
| CHAC (Mon & Wed) | 3:30pm | 6:30pm | 3h | 5:00pm |

The source data records only a single timestamp for dinner — there is no `dinner-end-time` or `dinner-duration` column. The 30-minute dinner length referenced in the project context pack is not present in the session data itself.

Session times in the dataset are recorded as strings (e.g. 4:00pm), not as parsed timestamps. Conversion happens at ingest.

### Building, year levels, and concurrent sessions

Each session has a single `Building` value populated; there is **no `Room` column** in the sessions data. Building values are constant per school (MBBC: Library; JPC: G Centre; MSHS: Library; ISHS: X Block; LC: Ella Building; CHAC: E Centre).

Year levels carried per school:

| School | Years carried (per sessions.xlsx) |
|---|---|
| MBBC | 11, 12 |
| JPC | 9, 10, 11, 12 |
| MSHS | 9, 10, 11, 12 |
| ISHS | 9, 10, 11, 12 |
| LC | 10, 11, 12 |
| CHAC | 10, 11, 12 |

**Same-caterer concurrent delivery:** Guzman y Gomez is scheduled to deliver to **two schools simultaneously** on Monday 1 May 2026 — Loreto College and Cannon Hill Anglican College, both with a 5:00pm dinner time. No other caterer has multiple deliveries on the same date in the dataset.

### Session managers

There are **7 distinct named session managers** across the 11 sessions: Triet, Jessie, Liam, Lucian, Ethan, Claire, Camilo. Workload distribution:

| Manager | Sessions | Detail |
|---|---|---|
| Triet | 1 | MBBC Tue |
| Liam | 1 | JPC Wed |
| Camilo | 1 | CHAC Wed |
| Jessie | 2 | JPC Tue + MSHS Thu |
| Lucian | 2 | ISHS Mon + ISHS Tue |
| Ethan | 2 | ISHS Thu + CHAC Mon |
| Claire | 2 | LC Mon + LC Tue |

Each manager who covers 2 sessions covers them on different days. No manager is scheduled for two concurrent sessions on the same day in the dataset.

---

## Students

### Per-session enrolment counts

| Session | Students |
|---|---:|
| MBBC Tuesday | 17 |
| JPC Tuesday | 28 |
| JPC Wednesday | 36 |
| MSHS Thursday | 8 |
| ISHS Monday | 36 |
| ISHS Tuesday | 45 |
| ISHS Thursday | 39 |
| LC Monday | 35 |
| LC Tuesday | 21 |
| CHAC Monday | 16 |
| CHAC Wednesday | 39 |
| **Total enrolment rows** | **320** |

Each sheet in `students.xlsx` has the structure: row 1 = school+day title, row 2 = blank, row 3 = column headers (`Student`, `Year Level`, `Subjects`, `Dietary`, `Student Email`, `Parent`, `Parent Email`, `Parent Mobile`), rows 4+ = data.

### Year-level breakdown per session

| Session | Y9 | Y10 | Y11 | Y12 | Total |
|---|---:|---:|---:|---:|---:|
| MBBC Tuesday | — | — | 5 | 12 | 17 |
| JPC Tuesday | 5 | 6 | 8 | 9 | 28 |
| JPC Wednesday | 5 | 8 | 8 | 15 | 36 |
| MSHS Thursday | 2 | 2 | 2 | 2 | 8 |
| ISHS Monday | 16 | 10 | 5 | 5 | 36 |
| ISHS Tuesday | 2 | 7 | 14 | 22 | 45 |
| ISHS Thursday | 3 | 11 | 10 | 15 | 39 |
| LC Monday | — | 8 | 8 | 19 | 35 |
| LC Tuesday | — | 2 | 6 | 13 | 21 |
| CHAC Monday | — | 11 | 2 | 3 | 16 |
| CHAC Wednesday | — | 4 | 22 | 13 | 39 |

### Duplicate names across sheets

13 student names appear in more than one session sheet. **All 13 cases are cross-school** — no name appears more than once within a single school's combined sheets. Two distinct patterns:

**Year level matches across the two appearances (6 names) — plausibly the same student:**

| Name | Sheets | Year | Dietary discrepancy |
|---|---|---:|---|
| Bailey Roberts | JPC Tue, ISHS Tue | 12 | none |
| Benjamin Wilson | JPC Tue, ISHS Tue | 12 | JPC: `No Beef`; ISHS: blank |
| Imogen Evans | ISHS Tue, LC Mon | 12 | none |
| Matilda Evans | ISHS Thu, LC Mon | 11 | none |
| Noah Hall | ISHS Thu, CHAC Mon | 10 | none |
| Riley Turner | MBBC, ISHS Tue | 12 | none |

**Year levels differ across the two appearances (7 names) — likely different students sharing a name:**

| Name | Sheets | Years | Dietary |
|---|---|---|---|
| Georgia Adams | MSHS, CHAC Wed | 11 / 10 | MSHS: `Halal`; CHAC: blank |
| Grace Thompson | ISHS Mon, CHAC Wed | 12 / 10 | none |
| Harper Harris | ISHS Mon, CHAC Wed | 12 / 11 | none |
| Phoebe Jones | ISHS Thu, LC Tue | 10 / 11 | none |
| Samuel Martin | JPC Tue, ISHS Tue | 10 / 12 | none |
| Sophia Turner | JPC Wed, ISHS Tue | 11 / 12 | none |
| Zachary Anderson | MBBC, CHAC Wed | 12 / 11 | MBBC: `No Fish`; CHAC: blank |

In two of the same-year cases (Benjamin Wilson, Zachary Anderson) the dietary field is populated at one school and blank at the other.

Of the 320 enrolled students, 13 names appear across two school sheets each. Of those 13, 7 have differing year levels across the two sheets (likely different individuals with the same name); 6 have matching year levels (cannot be distinguished without further identifiers).

### Dietary information

Of 320 enrolment rows, **59 carry a value** in the `Dietary` column. The remaining **261 are blank**.

Distinct values in the dietary column, with counts:

| Value as written | Count |
|---|---:|
| Halal | 16 |
| No Beef | 8 |
| Vegetarian | 8 |
| Nut Free | 6 |
| Opted out of Catering | 6 |
| No Beef, No Pork | 2 |
| Gluten Free, Dairy Free | 2 |
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
| Nut Free, No Shellfish, Opted out of Catering | 1 |

Three structural patterns in the column:

1. `No Pork` appears as a value distinct from `Halal`.
2. `Opted out of Catering` is recorded in the same column as dietary requirements — 6 students have it alone and 1 (Lei Li at ISHS Tuesday) has it combined with other tags.
3. Several rows combine multiple comma-separated items in a single cell.

Distinct dietary concepts referenced across the column, ignoring comma-grouping: halal, vegetarian, gluten free, dairy free, nut free, no beef, no pork, no red meat, no fish, no seafood, no shellfish. The `Opted out of Catering` marker is a thirteenth value with a different operational meaning from the others.

---

## Caterers

The four caterers and their pricing as recorded in `caterer-menus.pdf`:

| Caterer | Price per item | Delivery |
|---|---:|---|
| Lakehouse Victoria Point | $35.00 (excl GST) | $0 |
| Terrific Noodles | $20.50 (excl GST) | $30 per school per trip |
| Kenko Sushi House | $5.50 (incl GST) | $10 per school per trip |
| Guzman y Gomez | $15.00 (incl GST) | $50 per trip |

Two pricing characteristics are notable on inspection. Kenko at $5.50 inclusive of GST is markedly below the typical commercial range for sushi catering (which usually sits at $10–18 per box). Lakehouse at $35.00 exclusive of GST is at the high end for school catering. GST treatment varies: two caterers quote inclusive of GST, two exclusive. Delivery fee structures differ in kind, not just amount — flat-per-trip, per-school-per-trip, or zero.

### Minimum order quantity (MOQ)

MOQ values from `caterers.xlsx`, expressed as the minimum weekly total order quantity required for a given number of menu items in the order:

| Caterer | 4 items | 5 items | 6 items |
|---|---:|---:|---:|
| Lakehouse | 15 | 20 | 25 |
| Terrific | 10 | 20 | 30 |
| Kenko | 35 | 40 | 45 |
| GyG | 20 | 25 | 30 |

The footnote in `caterers.xlsx` clarifies: *"order quantity means total number of ordered meals for the week across all schools"*. MOQ scales with menu variety — ordering more menu items requires a higher weekly minimum.

Comparing each caterer's MOQ at each menu-size tier against current weekly enrolment volume (summed across the sessions each caterer currently serves, before factoring in absences or exclusions):

| Caterer | Sessions served | Weekly enrolment | MOQ 4 / 5 / 6 items | Status |
|---|---|---:|---|---|
| Lakehouse | MBBC Tue | 17 | 15 / 20 / 25 | Meets 4-item MOQ by margin of 2; below 5-item by 3; below 6-item by 8 |
| Terrific | JPC Tue, JPC Wed, MSHS Thu | 72 | 10 / 20 / 30 | Exceeds 6-item MOQ by 42 |
| Kenko | ISHS Mon, Tue, Thu | 120 | 35 / 40 / 45 | Exceeds 6-item MOQ by 75 |
| GyG | LC Mon, LC Tue, CHAC Mon, CHAC Wed | 111 | 20 / 25 / 30 | Exceeds 6-item MOQ by 81 |

Lakehouse is the only caterer whose current enrolment volume sits below the 6-item or 5-item MOQ; at 4 items they meet MOQ with a margin of 2. The other three caterers exceed their 6-item MOQ comfortably under current enrolment volumes.

### Caterer capability and current assignments

From `caterer-contacts.pdf`, each caterer is recorded as both serving a specific set of schools currently and being able to serve a (possibly broader) set:

| Caterer | Currently serves | Also able to serve |
|---|---|---|
| Lakehouse | MBBC | CHAC |
| Terrific | JPC, MSHS | Loreto |
| Kenko | ISHS | (no additional) |
| GyG | Loreto, CHAC | MSHS |

The capability statements in `caterer-contacts.pdf` are expressed at the school level, not the session level — i.e. "able to serve Loreto College" rather than "able to serve Loreto College Monday 3:30pm sessions". Three of the four caterers have at least one school they could serve but currently don't. Kenko has no expansion capability recorded beyond ISHS. The overlap pattern means that for any school except ISHS, at least two caterers have a recorded capability to serve it.

### Caterer contacts

Six named contacts across the four caterers, as written in `caterer-contacts.pdf`:

| Caterer | Name | Stated role | Email |
|---|---|---|---|
| Lakehouse | Carmen Gabrielle | order taker | carmen@padea.com.au |
| Terrific | Dylan Chern | order taker | cherndylan@gmail.com |
| Terrific | James Chern | chef, not cc'd | dylanchern808@gmail.com |
| Kenko | Big Mom | order taker and chef | hellopadea@gmail.com |
| GyG | Big Chicken | order taker | carmengabrielleee@gmail.com |
| GyG | Medium Giraffe | chef, cc'd on orders | dylan@padea.com.au |

Literal observations about this table:

- Three of the six names are non-realistic placeholders (`Big Mom`, `Big Chicken`, `Medium Giraffe`).
- Three of the six email addresses are routed to `padea.com.au` or `hellopadea@gmail.com` rather than to the caterer's own domain.
- Two contacts share a first name with `Dylan` (the company owner, per project context).
- The name-to-email pairings show several inversions relative to typical ownership conventions — e.g. Carmen Gabrielle's email is `carmen@padea.com.au`; the GyG order-taker `Big Chicken` is at `carmengabrielleee@gmail.com`; the GyG chef `Medium Giraffe` is at `dylan@padea.com.au`.
- Four distinct combinations of role flags appear across the contacts (order-taker / chef / primary-contact / cc-on-orders), with both single-role and multi-role contacts represented.

---

## Menus

Each of the four caterers offers 10 menu items in `caterer-menus.pdf`, totalling **40 distinct items** across the dataset. Items are annotated with a dietary legend defined on page 1:

- `GF` = gluten free
- `DF` = dairy free
- `NF` = nut free
- `VO` = vegetarian option

The legend page also states explicitly: *"Assume all non-pork meals are halal."*

The `VO` annotation describes a caterer capability to substitute a vegetarian variant on request rather than a property of the item as listed — items annotated `VO` are not themselves vegetarian.

**Pork** appears explicitly by name in 4 of the 40 items: Lakehouse's `Chicken, Bacon, Avo Wrap`; Terrific's `Grilled Pork Vermicelli Salad`; Terrific's `Bacon Carbonara`; GyG's `Pulled pork burrito bowl`. The remaining 36 items contain no pork reference in the item name.

**Beef** appears by name in 2–3 items per caterer based on item names. Several item names have ambiguous protein source — e.g. Terrific's `Spaghetti meatballs` does not specify the meatball protein. Per the legend's halal rule, the halal status of any ambiguously-named item depends on whether the actual recipe contains pork.

---

## Absences

`absences.pdf` lists 10 absences across the week of 1–4 May 2026:

| Date | School | Student | Session running that date | Enrolled at that session? |
|---|---|---|---|---|
| 01/05 | Loreto | Holly Hill | LC Monday | ✓ |
| 01/05 | Loreto | Imogen Evans | LC Monday | ✓ |
| 02/05 | MBBC | Noah Baker | MBBC Tuesday | ✓ |
| 02/05 | JPC | Christina Hu | JPC Tuesday | ✓ |
| 02/05 | JPC | Nathan Smith | JPC Tuesday | ✓ |
| 02/05 | ISHS | Charlie Morris | ISHS Tuesday | ✓ |
| 02/05 | ISHS | Jack Carter | ISHS Tuesday | ✓ |
| 02/05 | ISHS | Charlie Mitchell | ISHS Tuesday | ✓ |
| 03/05 | CHAC | Henry Cook | CHAC Wednesday | ✓ |
| 04/05 | MSHS | Rose Smith | MSHS Thursday | ✓ |

All 10 absentees are enrolled in the specific session running on the absence date. The file provides student name and date only — no time-of-day, no notification source (parent / school / student), no timestamp, no communication channel, no reason, no notes.

Imogen Evans is one of the cross-school duplicate-name cases. The absence at Loreto on 01/05 is recorded against her LC Monday enrolment; her ISHS Tuesday enrolment is unaffected by this entry.

---

## Exclusions

`exclusions.pdf` lists three exclusions:

| # | Date | School | Scope | Reason |
|---|---|---|---|---|
| 1 | 04/05 | ISHS | Whole session, all year levels | Open Day |
| 2 | 02/05 | Loreto | Whole session, all year levels | Parent-Teacher Interviews |
| 3 | 03/05 | CHAC | Years 10 and 12 only (Year 11 still attends) | School Camp |

Exclusions 1 and 2 cancel the entire session. Exclusion 3 is partial.

Applied to enrolment counts: exclusion 1 removes the entire ISHS Thursday session (39 students); exclusion 2 removes the entire Loreto Tuesday session (21 students); exclusion 3 removes 17 students from CHAC Wednesday (4 Year 10 + 13 Year 12), leaving 22 Year 11 students attending.

The file provides text content only — no source, no submission timestamp, no notification trail, no contact for the exclusion. Each exclusion date corresponds to a session that would otherwise run on that day per `sessions.xlsx`.

---

## Cross-file consistency

The data files are internally consistent at the cross-reference level. Every absence references a student enrolled in the specific session running on the absence date. Every exclusion references a session that exists in `sessions.xlsx`. Every session has a corresponding student sheet in `students.xlsx`, and every student sheet maps to a session. Every caterer in `caterers.xlsx` has a corresponding entry in `caterer-contacts.pdf` and a menu in `caterer-menus.pdf`.

No orphan references appear between files. The data is messy in formatting (dietary tags as free-text mixed with the catering-opt-out flag, placeholder caterer-contact names, ambiguous protein names in menu items, an Excel-stored header row that would be miscounted as a data row by a naive `nrows`-based read) but coherent in identity.

---

## Data expected but not present

Categories of information that would plausibly exist in a live operation but are absent from the source files:

- **Tutor roster.** Sessions reference a single `manager` per session, not the full tutor team. No file in the dataset enumerates tutors, their subject specialties, their school assignments, or their contact details.
- **Communication history.** Absences and exclusions are recorded as outcomes only — no sender, timestamp, channel, message body, or thread.
- **Parent contact for absence reports.** `absences.pdf` does not record who reported the absence or how. Parent contact details exist in `students.xlsx` but are not linked to the absence records.
- **Order history.** No file records past or pending catering orders, invoices, payments, or order confirmations.
- **Dinner duration.** `sessions.xlsx` records a single `dinner-time` per session; there is no field for dinner end time or dinner duration.
- **Room.** Sessions record a `Building` value but no room within the building.
- **Allergy severity.** Dietary tags such as `Nut Free` do not distinguish preference from anaphylaxis-level allergy.
- **Caterer ABNs, payment terms, or invoicing details.** Only price-per-item, delivery, and MOQ are present.
- **Per-session capacity limits.** No field records a maximum or target student count per session.
- **Tutor-to-student or tutor-to-subject assignments.** No file records which tutor teaches which student or which subject.

