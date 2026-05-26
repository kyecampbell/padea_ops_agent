# Data Observations — Padea Operations Agent



## NOTE; we are edditing this as the data observations data, you ahve the data and the initial data observations sheet to edit. note any of my annotations and make changes as neccesary. in the new data observations note all assumptions we can make from the data at the bottom of the sheet in its own section. assunmptions should not be woven into this document its purely for observations. 


**Purpose:** What the source data actually contains. Factual observations from the resource files, recorded so that downstream design work has a grounded reference for what's true about the data. Interpretations, design choices, and operational rules live in `assumptions.md` and `decision_register.md`.

**Compiled:** 25 May 2026
**Source files:** `data/source/caterers.xlsx`, `data/source/sessions.xlsx`, `data/source/students.xlsx`, `data/source/caterer-contacts.pdf`, `data/source/caterer-menus.pdf`, `data/source/exclusions.pdf`, `data/source/absences.pdf`
**Companion documents:** `assumptions.md`, `decision_register.md`, `schema.md`.

---

## How to read this document

This document is an inventory of what's in the data. Each section reports what the files contain, what patterns appear across files, and what anomalies or ambiguities are present. Where an observation has implications, the implications are stated in the document that handles them (assumptions, decisions, or schema).

---

## Headline numbers

The source data describes 6 schools, 4 caterers, 11 sessions per week spanning Monday through Thursday, 320 unique enrolled students, 6 named caterer contacts, approximately 40 menu items across the four caterers (10 per caterer), and 7 distinct named session managers drawn from the broader tutor population. There are no Friday sessions in the dataset.
## Note: redo are we sure about the 320 figure, there are no double ups or anything. i thought it was something else, take the original data and confirm this. We should proabaly assume any double names at the same school in the original data are the same student as there is no other way to distinguish, let me know if im wrong. lots of assumptions to be made about studetns attending various sessions and various schools etc. 
---


## Schools and sessions

The 6 schools and their session days:

| School | Region | Session days |
|---|---|---|
| Moreton Bay Boys' College (MBBC) | Redlands | Tuesday |
| John Paul College (JPC) | South Brisbane | Tuesday, Wednesday |
| MacGregor State High School (MSHS) | South Brisbane | Thursday |
| Indooroopilly State High School (ISHS) | West Brisbane | Monday, Tuesday, Thursday |
| Loreto College (LC) | Central Brisbane | Monday, Tuesday |
| Cannon Hill Anglican College (CHAC) | Central Brisbane | Monday, Wednesday |

Across the four operational days, each (caterer, date) pair appears at most once — no caterer is scheduled to deliver to multiple schools on the same date in the dataset.

Session start times vary by school. MBBC starts at 4:00pm. JPC starts at 4:30pm. MSHS starts at 3:15pm. The remaining schools start at 3:30pm. Dinner times within sessions vary correspondingly, ranging from 4:45pm to 6:00pm. Building and room values are populated per session.
## NOTE; can we make an observation about session duration and meal length etc. be specific. 

Year levels carried vary by school. MBBC and CHAC carry Years 10–12. Loreto carries Years 10–12. ISHS and JPC carry Years 9–12.

No school has more than one session on the same day in the dataset.
## NOTE; we can assume this is constant for all future sessions 

---

## Students

Students distributed per session:

| Session | Students |
|---|---:|
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
| **Total enrolment rows** | **331** |

The total enrolment rows count to 331; the unique student count is 320. The 11-student difference is accounted for by students who appear in multiple sheets, having enrolment at more than one session.
## NOTE; worth just observing the names of these students. theres only 11, are their any double names, what can we observe about these students


### Dietary information

Of 320 students, 67 carry one or more values in the dietary column of the source data. The remaining 253 students have no value in that column.
## NOTE; if it is simply no value in that collulmn are we not assuming they have no dietry reqs which is assuming as well that this info was filled out properly. probably can be put into one umbrella assumption that the initial given data was accurate etc. 


The distinct values that appear in the dietary column, with their counts across the 320 students:

| Value as written | Count |
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

Three patterns appear in these values that are worth recording. First, `No Pork` appears as a value distinct from `Halal`. Second, `Opted out of Catering` is mixed into the dietary column, appearing both alone and combined with other values. Third, several values combine multiple comma-separated items in a single cell.

Seven students have a value containing `Opted out of Catering`. Six have it alone; one (Lei Li at ISHS Tuesday) has it combined with `Nut Free, No Shellfish`.

The distinct dietary concepts present across the source data, regardless of comma-grouping: halal, vegetarian, gluten free, dairy free, nut free, no beef, no pork, no red meat, no fish, no seafood, no shellfish. The opt-out marker (`Opted out of Catering`) is a thirteenth value with a different operational meaning from the others.

---

## Caterers

The four caterers, their pricing, and their delivery fee structure as recorded in `caterers.xlsx` and `caterer-menus.pdf`:

| Caterer | Price per item | Delivery |
|---|---:|---|
| Lakehouse Victoria Point | $35.00 (excl GST) | $0 |
| Terrific Noodles | $20.50 (excl GST) | $30 per school per trip |
| Kenko Sushi House | $5.50 (incl GST) | $10 per school per trip |
| Guzman y Gomez | $15.00 (incl GST) | $50 per trip |

Two pricing values are notable. Kenko at $5.50 inclusive of GST is markedly below the typical range for sushi catering, which usually sits at $10–18 per box. Lakehouse at $35.00 exclusive of GST is at the high end for school catering. GST treatment also varies: two caterers quote inclusive of GST, two exclusive. Delivery fee structures differ in kind, not just amount — some flat-per-trip, some per-school-per-trip, one zero.
## NOTE;this ties back into our assumption data is accurate, no point arguing it, not our fault if it was a typo etc. we are to take it as true. not worth any mroe time for a demo competition. 


### Minimum order quantity rules

MOQ values from `caterers.xlsx`, expressed as the minimum weekly total order quantity required for a given number of menu items in the order:

| Caterer | 4 items | 5 items | 6 items |
|---|---:|---:|---:|
| Lakehouse | 15 | 20 | 25 |
| Terrific | 10 | 20 | 30 |
| Kenko | 35 | 40 | 45 |
| GyG | 20 | 25 | 30 |

The MOQ note in the source data clarifies that order quantity is measured as the total number of ordered meals for the week across all schools served by that caterer, and that MOQ scales with menu variety — ordering 4 menu items requires a lower minimum weekly total than ordering 6.

Comparing each caterer's MOQ at 6 items against current weekly volume (summed from student counts on the sessions each caterer currently serves):

| Caterer | Sessions served | Weekly volume | MOQ at 6 items | Margin |
|---|---|---:|---:|---:|
| Lakehouse | MBBC Tuesday | 18 | 25 | –7 |
| Terrific | JPC Tuesday, JPC Wednesday, MSHS Thursday | 75 | 30 | +45 |
| Kenko | ISHS Monday, Tuesday, Thursday | 123 | 45 | +78 |
| GyG | LC Monday, Tuesday, CHAC Monday, Wednesday | 115 | 30 | +85 |

Lakehouse's current weekly volume of 18 falls below their MOQ of 25 at 6 items. At 4 items, Lakehouse's MOQ is 15, which the current volume meets. The other three caterers exceed their 6-item MOQ comfortably under current volumes.

### Caterer capability and current assignments

From `caterer-contacts.pdf`, each caterer is recorded as both serving a specific set of schools currently and being able to serve a (possibly broader) set:

| Caterer | Currently serves | Also able to serve |
|---|---|---|
| Lakehouse | MBBC | CHAC |
| Terrific | JPC, MSHS | Loreto |
| Kenko | ISHS | (no additional) |
| GyG | Loreto, CHAC | MSHS |

Three of the four caterers have at least one school they could serve but currently don't. Kenko has no expansion capability beyond ISHS. The overlap pattern means that for any school except ISHS, at least two caterers are eligible to serve.
# are we making an assumption about their capabilities. caterer y being able to serve school x currently does not gurantee they can serve school x if the day or time changes as its the session that matters. think about this one and proccess it as an assumption. 

### Caterer contacts

Six named contacts across the four caterers, with the following email-to-name pairings as written in `caterer-contacts.pdf`:

| Caterer | Name | Stated role | Email |
|---|---|---|---|
| Lakehouse | Carmen Gabrielle | order taker | carmen@padea.com.au |
| Terrific | Dylan Chern | order taker | cherndylan@gmail.com |
| Terrific | James Chern | chef, not cc'd | dylanchern808@gmail.com |
| Kenko | Big Mom | order taker and chef | hellopadea@gmail.com |
| GyG | Big Chicken | order taker | carmengabrielleee@gmail.com |
| GyG | Medium Giraffe | chef, cc'd on orders | dylan@padea.com.au |

Several patterns are present. Names include obvious placeholders (Big Mom, Big Chicken, Medium Giraffe). Email addresses include several routed to Padea-controlled inboxes (`carmen@padea.com.au`, `hellopadea@gmail.com`, `dylan@padea.com.au`). Some name-to-email pairings appear inverted relative to ownership conventions (Carmen Gabrielle's email is `carmen@padea.com.au`; another contact's name is also Dylan, sharing identity with the company owner).

Four distinct combinations of role flags appear across the contacts (order-taker / chef / primary-contact / cc-on-orders), with both single-role and multi-role contacts represented.
## NOTE; make an assumption about the place holder emails, obviously they are for the sake of the competition. trememver this section is specifically for obvs only. so make it a literal obv only and put the assump at the bottom. 

---

## Menus

Each of the four caterers offers 10 menu items, totalling 40 distinct items across the dataset. Each menu item is annotated in `caterer-menus.pdf` using a dietary legend: `GF` (gluten free), `DF` (dairy free), `NF` (nut free), `VO` (vegetarian option). The menus also state explicitly: *"Assume all non-pork meals are halal."*

The `VO` annotation describes a caterer capability to substitute a vegetarian variant on request rather than a property of the item as listed — items annotated `VO` are not themselves vegetarian.

Pork appears explicitly in 4 of the 40 menu items: Lakehouse's `Chicken, Bacon, Avo Wrap`; Terrific's `Grilled Pork Vermicelli Salad`; Terrific's `Bacon Carbonara`; GyG's `Pulled pork burrito bowl`. The remaining 36 items contain no pork by inspection of item names.

Beef appears in 2–3 items per caterer based on item names. Several items have names with ambiguous protein source (for example, `Spaghetti meatballs` does not specify whether the meatballs are beef or pork).

---

## Absences

The `absences.pdf` file lists 10 absences across the week dated 1–4 May 2026:

| Date | School | Student | Match in students.xlsx |
|---|---|---|---|
| 01/05 | Loreto | Holly Hill | ✓ |
| 01/05 | Loreto | Imogen Evans | ✓ |
| 02/05 | MBBC | Noah Baker | ✓ |
| 02/05 | JPC | Christina Hu | ✓ |
| 02/05 | JPC | Nathan Smith | ✓ |
| 02/05 | ISHS | Charlie Morris | ✓ |
| 02/05 | ISHS | Jack Carter | ✓ |
| 02/05 | ISHS | Charlie Mitchell | ✓ |
| 03/05 | CHAC | Henry Cook | ✓ |
| 04/05 | MSHS | Rose Smith | ✓ |

All 10 absentees cross-reference to enrolled students at the school named. The absences file provides names and dates only; it does not include parent contact, source, or timestamp information.

Each absence date corresponds to a session that runs on that day in `sessions.xlsx`.

---

## Exclusions

The `exclusions.pdf` file lists three exclusions:

| # | Date | School | Scope | Reason |
|---|---|---|---|---|
| 1 | 04/05 | ISHS | Whole session, all year levels | Open Day |
| 2 | 02/05 | Loreto | Whole session, all year levels | Parent-Teacher Interviews |
| 3 | 03/05 | CHAC | Years 12 and 10 only (Year 11 still attends) | School Camp |

Two exclusions cancel the entire session. The CHAC exclusion is partial — specific year levels are excluded while one (Year 11) continues to attend.

The exclusions file provides text content only — no source, no timestamp, no notification trail. Each exclusion date corresponds to a session that would otherwise run on that day in `sessions.xlsx`.

---

## Cross-file consistency

The data files are internally consistent at the cross-reference level. Every absence references a student who is enrolled at the named school. Every exclusion references a session that exists in `sessions.xlsx`. Every session has a corresponding student sheet in `students.xlsx`, and every student sheet matches a session. Every caterer in `caterers.xlsx` has a corresponding entry in `caterer-contacts.pdf` and a menu in `caterer-menus.pdf`.

No orphan references appear between files. The data is messy in formatting (dietary tags as free text with mixed concerns, placeholder emails, ambiguous protein names in menu items) but coherent in identity.

---

## Open questions

These questions about the source data cannot be answered from the files alone and would benefit from clarification:

1. Whether Kenko's $5.50-per-item price is intended as written, given it is substantially below typical sushi-catering pricing.
2. Whether the placeholder email routing (e.g. `dylan@padea.com.au` listed as a caterer contact) is meant to be used at face value by the system during competition assessment, or whether outbound email should be redirected to a controlled outbox.
3. How the current operation handles Lakehouse's MBBC volume sitting below their 6-item MOQ — whether the caterer softens the rule in practice, whether Padea pays a shortfall, or whether the order is constrained to fewer menu items.
4. Whether the dataset week (1–4 May 2026) is a single sample for the demo or whether ongoing weekly operation should be simulated.


## NOTE; the data at least to me indicates that for question 3 we are constrained to less options. however check this thouroughly are you sure we are below the MOQ we could be but worth triple checking.  