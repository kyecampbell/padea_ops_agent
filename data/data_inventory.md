# Data Inventory — Phase 2 Ingest Planning

_Last updated: 2026-05-28 (Session 010)_  
_Schema target: V4 (`docs/v4_optimised/Schema/v4_schema.sql`)_  
_Cross-referenced against: `docs/v1_initials/data_observations.md` (compiled 2026-05-25)_

---

## Demo dummy data (fabricated — no real source)

Four seed scripts generate synthetic data needed to demonstrate the agent's
full capability.  All are run as steps 11–14 of `src/ingest/run_all.py`.

| Script | Table(s) | What it creates | Why needed |
|---|---|---|---|
| `seed_term_meal_preferences.py` | `term_meal_preferences`, `term_meal_preference_items` | 3–5 approved menu items per student per caterer (dietary-safe, random selection, `captured_by='parent'`, April 25) | Without preferences, every student falls through to `auto_pick_dietary_meal` — the rotation system is invisible |
| `seed_term_meal_preferences.py` | `caterers.canonical_menu_order` | Most-popular items ranked by preference vote count | Required by `get_next_rotation_meal` to determine rotation order |
| `seed_feedback_history.py` | `orders`, `feedback` | 5 weeks of historical orders (Apr 21–May 22) + 2 feedback rows per session (manager + tutor) | `compute_rolling_mean` needs ≥3 ratings; quality monitoring is invisible without history |
| `seed_upcoming_exclusions.py` | `exclusions` | ISHS Year 10 school camp (Jun 8–11) + Term 2 holidays all schools (Jun 27–Jul 12) | Shows exclusion buffer logic and whole-school closure handling |
| `seed_upcoming_absences.py` | `absences` | ~11 absences across Jun 2–10 | Shows absence handling and dietary-student override rule in upcoming sessions |

### Contact substitution (all seed scripts)

Every email address and phone number in the DB is the demo contact rather than
the real person's details:

| Field | All rows contain |
|---|---|
| `enrolments.parent_email` | `kyec898@gmail.com` |
| `enrolments.parent_phone` | `0458971565` |
| `tutors.email` | `kyec898@gmail.com` |
| `tutors.mobile` | `0458971565` |
| `caterers.contact_email` | `kyec898@gmail.com` |

This means every email the agent sends (order confirmations, parent enrolment
emails, operator notifications) arrives in the one demo inbox.

### Feedback history — engineered caterer trend

Terrific Noodles (caterer 2) is seeded with a clear declining-quality arc to
trigger the `sustained-decline` escalation in the demo:

| Week | Sessions | Terrific manager / tutor | Other caterers |
|---|---|---|---|
| Wk 1 Apr 21–24 | 11 sessions | 5 / 5 | 4–5 |
| Wk 2 Apr 28–May 1 | 11 sessions | 5 / 4 | 4–5 |
| Wk 3 May 5–8 | 11 sessions | 3 / 3 | 4 |
| Wk 4 May 12–15 | 11 sessions | 2 / 2 | 3–4 |
| Wk 5 May 19–22 | 11 sessions | 1 / 2 | 3–4 |

Target: `compute_rolling_mean(Terrific, weeks=4)` ≈ 2.2 — below `quality_floor` (3.0).  
`compute_rolling_mean(Terrific, weeks=12)` ≈ 3.3 — decline > `quality_decline_threshold` (0.5).

### Upcoming exclusions — fabricated events

| Event | School | Dates | Effect |
|---|---|---|---|
| Year 10 school camp | ISHS (school 4) | Jun 8, 9, 11 | Year 10 excluded from all 3 ISHS sessions; 10% buffer added for non-dietary Yr10 cohort |
| Term 2 school holidays | All 6 schools | Jun 27–Jul 12 | Whole-session exclusions; agent skips order composition for all sessions in this window |

### Upcoming absences — fabricated

11 absences spread across the weeks of Jun 2 and Jun 9.  Student names are real
(from the enrolments table) but the absence dates are invented.  The Jun 9 ISHS
absence is for a non-Year-10 student to avoid confusion with the camp exclusion.

---

## Ingest decisions locked in this session

| # | Decision | What was decided |
|---|---|---|
| D1 | Source data path | All files live in `data/source/`, not `data/raw/`. CLAUDE.md corrected. |
| D2 | sessions.xlsx scope | The 11 sessions (week of 1–4 May 2026) represent the **recurring weekly schedule** for the term — same schools, same days, same times each week. Seed this week; the pattern repeats. |
| D3 | Cross-school duplicate names | Treat as **different students**. No student attends more than one school. All 13 cross-school name overlaps are different people. (All 13 confirmed cross-school in data_observations.md; zero same-school duplicates exist in the dataset.) |
| D4 | Same-school cross-session names | If a name appeared in two sessions at the same school, they are **one student** with two enrolments. Not applicable for this dataset — no such cases exist. Policy documented for future data. |
| D5 | Tutors | Only 7 session managers exist in source data. For the demo: ingest the 7 managers as the full tutor roster. Generate plausible `@padea.com.au` email addresses. Mark all `is_manager=true` for their assigned sessions. No additional non-manager tutors. Average ~5 students/tutor is noted for future full-roster build. |
| D6 | Halal tagging | Tag **all non-pork menu items** as `halal`. Pork items: Chicken Bacon Avo Wrap (Lakehouse), Grilled Pork Vermicelli Salad (Terrific), Bacon Carbonara (Terrific), Pulled pork burrito bowl (GyG). All other 36 items get the halal tag. |
| D7 | VO (Vegetarian Option) flag | VO means the item *can* be made vegetarian on request — it does **not** mean the item is safe for vegetarian students as listed. VO items are **not** tagged `vegetarian` in `menu_item_dietary_tags`. |
| D8 | "No X" restrictions (No Beef, No Fish, etc.) | No explicit menu-level flag exists for these. Must manually inspect item names to determine protein content. Items with ambiguous protein (e.g. "Spaghetti meatballs") are flagged in the per-entity detail below. Ingest scripts will include a manual lookup table. |
| D9 | GyG delivery fee | Source says "$50 delivery per trip" — wording differs from Terrific/Kenko ("per school per trip"). Decision: treat as **$0 delivery** (built into item cost) per operator direction. Store `delivery_fee_cents = 0` for GyG. Documented as assumption. |
| D10 | opted_out_of_catering | This value appears in the `Dietary` column in students.xlsx. It is **not** a dietary tag — extract it to the `opted_out_of_catering boolean` on `enrolments`. Seven students have it (6 alone, 1 combined with other tags). |

---

## Summary table

| V4 Table | Status | Source | Notes |
|---|---|---|---|
| `schools` | REAL | `data/source/sessions.xlsx` | 6 rows — complete for demo |
| `caterers` | REAL | `data/source/caterers.xlsx` + `caterer-contacts.pdf` | 4 rows — pricing, MOQ, region, contacts |
| `tutors` | PARTIAL/MOCK | `data/source/sessions.xlsx` (managers) | 7 rows — real names; emails + mobiles replaced with demo contact (kyec898@gmail.com / 0458971565) |
| `menu_items` | REAL | `data/source/caterer-menus.pdf` | 40 rows — complete |
| `dietary_tags` | REAL (vocabulary build needed) | `data/source/students.xlsx` + `caterer-menus.pdf` | 11 student-requirement tags; see D6–D8 |
| `menu_item_dietary_tags` | REAL (manual curation for "No X") | `data/source/caterer-menus.pdf` | GF/DF/NF explicit; halal derived; "No X" manual |
| `enrolments` | REAL | `data/source/students.xlsx` | 320 rows; 13 cross-school overlaps = different students |
| `enrolment_dietary_tags` | REAL | `data/source/students.xlsx` Dietary column | 59 rows with values; splitting + opt-out extraction needed |
| `session_slots` | REAL | `data/source/sessions.xlsx` | 11 rows (one demo week = recurring weekly pattern) |
| `session_tutor_assignments` | PARTIAL | `data/source/sessions.xlsx` managers | 11 rows; one manager per session only |
| `enrolment_session_slots` | PENDING | `data/source/students.xlsx` sheet names → `session_slots` id mapping | 0 rows seeded — `seed_enrolment_session_slots.py` not yet written; needed before Phase 3 tools |
| `absences` | REAL | `data/source/absences.pdf` | 10 rows for demo week |
| `exclusions` | REAL | `data/source/exclusions.pdf` | 3 rows for demo week |
| `orders` | MISSING | — | Generated by agent at runtime |
| `order_lines` | MISSING | — | Generated by agent at runtime |
| `feedback` | MISSING | — | Populated post-session by tutors/managers |
| `meal_preferences` | MISSING | — | Populated via parent enrolment email flow |
| `meal_requests` | MISSING | — | Populated via tutor app at runtime |
| `outbound_emails` | MISSING | — | Generated by agent |
| `agent_runs` | MISSING | — | Generated by agent |
| `agent_steps` | MISSING | — | Generated by agent |

---

## Per-entity detail

### dietary_tags (reference data — seed first)

**Status:** REAL source data; vocabulary build required  
**Sources:** `students.xlsx` Dietary column + `caterer-menus.pdf` legend  

The V4 schema (V4-OPT-06) uses a shared `dietary_tags` table for both enrolment requirements and menu item properties. The matching rule at order composition is `item.tags ⊇ student.tags`.

**Tags to seed** (11 student-requirement tags):

| Slug | Student label in source | Maps to menu-side how |
|---|---|---|
| `halal` | `Halal` | All non-pork items (see D6) |
| `vegetarian` | `Vegetarian` | Items that are inherently vegetarian (no VO — see D7) |
| `gluten_free` | `Gluten Free` | Items flagged `GF` |
| `dairy_free` | `Dairy Free` | Items flagged `DF` |
| `nut_free` | `Nut Free` | Items flagged `NF` |
| `no_beef` | `No Beef` | Items with no beef by name inspection |
| `no_pork` | `No Pork` | Items not containing pork (overlaps with halal) |
| `no_red_meat` | `No Red Meat` | Items with no beef, lamb, or pork by name inspection |
| `no_fish` | `No Fish` | Items with no fish by name inspection |
| `no_seafood` | `No Seafood` | Items with no fish or shellfish by name inspection |
| `no_shellfish` | `No Shellfish` | Items with no shellfish by name inspection |

**Note:** `opted_out_of_catering` is extracted to a boolean on `enrolments`, not a tag.  
**Note:** The `Halal, Vegetarian` combo (1 student) splits into two separate tag rows.  
**Note:** `No Beef, No Pork` combo (2 students) splits into two tag rows.

---

### schools

**Status:** REAL  
**Source:** `data/source/sessions.xlsx`  
**Row count:** 6  
**Known gaps:** No address, postcode, or school contact info in source data (not needed for demo — caterer-school assignments are declared explicitly in caterer-contacts.pdf)

| School | Abbreviation | Region | Building |
|---|---|---|---|
| Moreton Bay Boys' College | MBBC | Redlands | Library |
| John Paul College | JPC | South Brisbane | G Centre |
| MacGregor State High School | MSHS | South Brisbane | Library |
| Indooroopilly State High School | ISHS | West Brisbane | X Block |
| Loreto College | LC | Central Brisbane | Ella Building |
| Cannon Hill Anglican College | CHAC | Central Brisbane | E Centre |

**Ingest note:** `Building` is a school-level constant per source data (no room column). Store on `schools` or as a field on `session_slots` — whichever the V4 schema uses.

---

### caterers

**Status:** REAL  
**Sources:** `data/source/caterers.xlsx` (MOQ + region) + `data/source/caterer-contacts.pdf` (contacts, served schools, pricing from caterer-menus.pdf)  
**Row count:** 4

| Caterer | Region | Price/item | GST | Delivery | MOQ 4/5/6 items |
|---|---|---|---|---|---|
| Lakehouse Victoria Point | Redlands | $35.00 | excl | $0 | 15 / 20 / 25 |
| Terrific Noodles | South Brisbane | $20.50 | excl | $30/school/trip | 10 / 20 / 30 |
| Kenko Sushi House | West Brisbane | $5.50 | incl | $10/school/trip | 35 / 40 / 45 |
| Guzman y Gomez | Central Brisbane | $15.00 | incl | $0 (see D9) | 20 / 25 / 30 |

**In cents (for DB):** Lakehouse 3500 excl GST, Terrific 2050 excl GST, Kenko 550 incl GST, GyG 1500 incl GST

**Caterer contacts** (from caterer-contacts.pdf):

| Caterer | Contact name | Role | Email | CC on orders? |
|---|---|---|---|---|
| Lakehouse | Carmen Gabrielle | Order taker (primary) | carmen@padea.com.au | Yes (primary) |
| Terrific | Dylan Chern | Order taker (primary) | cherndylan@gmail.com | Yes (primary) |
| Terrific | James Chern | Chef | dylanchern808@gmail.com | **No** — explicitly does not want CC |
| Kenko | Big Mom | Order taker + chef (primary) | hellopadea@gmail.com | Yes (primary) |
| GyG | Big Chicken | Order taker (primary) | carmengabrielleee@gmail.com | Yes (primary) |
| GyG | Medium Giraffe | Chef | dylan@padea.com.au | **Yes** — explicitly wants CC |

**Note:** Three contact names are non-realistic placeholders (Big Mom, Big Chicken, Medium Giraffe). Treat as real — do not modify.

**Caterer school assignments:**

| Caterer | Currently serves | Also able to serve |
|---|---|---|
| Lakehouse | MBBC | CHAC |
| Terrific | JPC, MSHS | LC |
| Kenko | ISHS | (none) |
| GyG | LC, CHAC | MSHS |

---

### tutors

**Status:** PARTIAL (real names + mobiles) / MOCK (generated emails)  
**Source:** `data/source/sessions.xlsx` (manager column + manager-mobile column)  
**Row count:** 7

| Name | Mobile | Generated email | Sessions managed |
|---|---|---|---|
| Triet | kyec898@gmail.com | 0458971565 | MBBC Tue |
| Jessie | kyec898@gmail.com | 0458971565 | JPC Tue, MSHS Thu |
| Liam | kyec898@gmail.com | 0458971565 | JPC Wed |
| Lucian | kyec898@gmail.com | 0458971565 | ISHS Mon, ISHS Tue |
| Ethan | kyec898@gmail.com | 0458971565 | ISHS Thu, CHAC Mon |
| Claire | kyec898@gmail.com | 0458971565 | LC Mon, LC Tue |
| Camilo | kyec898@gmail.com | 0458971565 | CHAC Wed |

**Demo note:** All emails and phone numbers replaced with `kyec898@gmail.com` / `0458971565` for demo safety. Real mobile numbers from source data discarded.  
**Known gaps:** No non-manager tutors. A real-operation roster would have ~5 students per tutor per session, implying 3–9 tutors per session beyond the manager. Not in source data; deferred — managers-only for demo.

---

### menu_items + menu_item_dietary_tags

**Status:** REAL  
**Source:** `data/source/caterer-menus.pdf`  
**Row count:** 40 items (10 per caterer)

**Lakehouse Victoria Point** — $35 excl GST, $0 delivery:

| Item | GF | DF | NF | Vegetarian | Halal | Pork | Contains (by name) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| Shrimp Fried Rice | ✓ | ✓ | | | ✓ | | Shrimp (shellfish) |
| Spaghetti Bolognese + Garlic Bread | | | ✓ | | ✓ | | Beef implied |
| Sweet and Sour Chicken | ✓ | ✓ | ✓ | | ✓ | | Chicken |
| Classic Cream Pasta | | | ✓ | | ✓ | | No meat specified |
| Gnocchi in Tomato Sauce | | | ✓ | ✓ | ✓ | | Vegetarian |
| Chicken, Bacon, Avo Wrap | | | | | ✗ | ✓ | PORK (bacon) |
| Fried Chicken Burger + Chips | | | ✓ | | ✓ | | Chicken |
| Fish Taco Bowl | | | ✓ | | ✓ | | Fish |
| Korean Beef Bulgogi Rice Bowl | ✓ | ✓ | ✓ | | ✓ | | Beef |
| Japanese Chicken Curry | | ✓ | ✓ | VO only | ✓ | | Chicken |

**Terrific Noodles** — $20.50 excl GST, $30/school/trip:

| Item | GF | DF | NF | Vegetarian | Halal | Pork | Contains (by name) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| Spicy Miso Udon | | ✓ | | | ✓ | | No meat specified |
| Stir-fry Noodles topped with Chicken | ✓ | ✓ | ✓ | | ✓ | | Chicken |
| Grilled Pork Vermicelli Salad | ✓ | ✓ | ✓ | VO | ✗ | ✓ | PORK |
| Spaghetti meatballs | | | ✓ | | ⚠️ | ⚠️ | **Ambiguous** — meatball protein unknown |
| Lemongrass Grilled Beef and Noodles | ✓ | ✓ | ✓ | VO only | ✓ | | Beef |
| Creamy Garlic Beef Noodles | | | | VO only | ✓ | | Beef |
| Mie Goreng | ✓ | ✓ | ✓ | VO only | ✓ | | No meat specified |
| Beef Pad Thai | | | | | ✓ | | Beef |
| Bacon Carbonara | | | | | ✗ | ✓ | PORK (bacon) |
| Chinese Honey Soy Noodles | | ✓ | | | ✓ | | No meat specified |

**Kenko Sushi House** — $5.50 incl GST, $10/school/trip:

| Item | GF | DF | NF | Vegetarian | Halal | Pork | Contains (by name) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| Lamb wrap | | | ✓ | | ✓ | | Lamb (red meat) |
| Chicken Parmi, chips and salad | | ✓ | ✓ | | ✓ | | Chicken |
| Japanese Chicken Katsu | | | ✓ | VO only | ✓ | | Chicken |
| Teriyaki Salmon rice bowl | ✓ | ✓ | ✓ | VO only | ✓ | | Salmon (fish) |
| Chicken Karaage ricebowl | | ✓ | ✓ | VO only | ✓ | | Chicken |
| Creamy Udon | | | | | ✓ | | No meat specified |
| Beef Fried Rice | ✓ | ✓ | | VO only | ✓ | | Beef |
| Mongolian Beef and Rice | | | | | ✓ | | Beef |
| Sweet and Sour Chicken | ✓ | ✓ | | | ✓ | | Chicken |
| Chinese Honey Soy Noodles | | ✓ | | | ✓ | | No meat specified |

**Guzman y Gomez** — $15.00 incl GST, $0 delivery (D9):

| Item | GF | DF | NF | Vegetarian | Halal | Pork | Contains (by name) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| Breakfast Tacos | | | ✓ | VO only | ✓ | | No meat specified |
| Caesar Salad | ✓ | ✓ | ✓ | VO only | ✓ | | No meat specified |
| Cali Burrito | | | | | ✓ | | No meat specified |
| Grilled Chicken Burrito | | | | | ✓ | | Chicken |
| Pulled pork burrito bowl | ✓ | | ✓ | | ✗ | ✓ | PORK |
| Nachos | ✓ | | | VO only | ✓ | | No meat specified |
| Nacho Fries | ✓ | | | VO only | ✓ | | No meat specified |
| Chicken Quesadilla | | | | | ✓ | | Chicken |
| Chicken Enchilada | ✓ | ✓ | | | ✓ | | Chicken |
| Crispy Chicken Taco | | | | | ✓ | | Chicken |

**Ambiguous protein item requiring ingest decision:**  
- **Spaghetti meatballs (Terrific)** — meatball protein not specified in name. Cannot determine halal status or beef/pork content from source. Options: (a) treat as non-halal (conservative), (b) ask Dylan, (c) assume chicken meatballs (halal). Flagged for decision before ingest.

---

### enrolments + enrolment_dietary_tags

**Status:** REAL  
**Source:** `data/source/students.xlsx` (11 sheets)  
**Enrolment row count:** 320  
**Sheets:** MBBC (17), JPC-Tue (28), JPC-Wed (36), MSHS (8), ISHS-Mon (36), ISHS-Tue (45), ISHS-Thu (39), LC-Mon (35), LC-Tue (21), CHAC-Mon (16), CHAC-Wed (39)

**Columns per row:** Student name, Year Level (int), Subjects, Dietary (free text), Student Email, Parent name, Parent Email, Parent Mobile

**Known gaps:**
- No student ID — ingest will key on (name, school) within-school; cross-school same names are different students (D3)
- No existing meal preference history (fresh system)

**Dietary column processing required:**
- Split comma-separated values into individual tags (e.g. `"Gluten Free, Dairy Free"` → two rows in `enrolment_dietary_tags`)
- Extract `opted_out_of_catering` flag and write to boolean column, not tag table (D10)
- Map raw text to `dietary_tags` slug values (e.g. `"Nut Free"` → `nut_free`)

**Students with opted_out_of_catering flag (7):**

| Student | Session | Other dietary tags |
|---|---|---|
| (6 students with `Opted out of Catering` alone) | various | none |
| Lei Li | ISHS Tuesday | `Nut Free, No Seafood` (also opted out) |

**Distinct dietary values in source (from data_observations.md, 59 non-blank rows):**

| Raw value | Count | Action |
|---|---:|---|
| Halal | 16 | → `halal` tag |
| No Beef | 8 | → `no_beef` tag |
| Vegetarian | 8 | → `vegetarian` tag |
| Nut Free | 6 | → `nut_free` tag |
| Opted out of Catering | 6 | → `opted_out_of_catering = true`, no tag |
| No Beef, No Pork | 2 | → `no_beef` + `no_pork` tags |
| Gluten Free, Dairy Free | 2 | → `gluten_free` + `dairy_free` tags |
| Halal, Vegetarian | 1 | → `halal` + `vegetarian` tags |
| Dairy Free | 1 | → `dairy_free` tag |
| Gluten Free | 1 | → `gluten_free` tag |
| No Fish | 1 | → `no_fish` tag |
| No Pork | 1 | → `no_pork` tag |
| No Pork, No Shellfish | 1 | → `no_pork` + `no_shellfish` tags |
| No Red Meat | 1 | → `no_red_meat` tag |
| No Seafood | 1 | → `no_seafood` tag |
| No Shellfish | 1 | → `no_shellfish` tag |
| Nut Free, No Seafood | 1 | → `nut_free` + `no_seafood` tags |
| Nut Free, No Shellfish, Opted out of Catering | 1 | → `nut_free` + `no_shellfish` tags + `opted_out = true` |

---

### session_slots + session_tutor_assignments

**Status:** REAL (one demo week representing recurring weekly schedule — D2)  
**Source:** `data/source/sessions.xlsx`  
**Row count:** 11 session_slots, 11 session_tutor_assignments (one manager each)

| School | Date | Day | Start | End | Dinner | Year levels | Manager |
|---|---|---|---|---|---|---|---|
| MBBC | 2026-05-02 | Tue | 4:00pm | 7:00pm | 5:30pm | 11, 12 | Triet |
| JPC | 2026-05-02 | Tue | 4:30pm | 7:30pm | 6:00pm | 9, 10, 11, 12 | Jessie |
| JPC | 2026-05-03 | Wed | 4:30pm | 7:30pm | 6:00pm | 9, 10, 11, 12 | Liam |
| MSHS | 2026-05-04 | Thu | 3:15pm | 6:15pm | 4:45pm | 9, 10, 11, 12 | Jessie |
| ISHS | 2026-05-01 | Mon | 3:30pm | 6:30pm | 5:00pm | 9, 10, 11, 12 | Lucian |
| ISHS | 2026-05-02 | Tue | 3:30pm | 6:30pm | 5:00pm | 9, 10, 11, 12 | Lucian |
| ISHS | 2026-05-04 | Thu | 3:30pm | 6:30pm | 5:00pm | 9, 10, 11, 12 | Ethan |
| LC | 2026-05-01 | Mon | 3:30pm | 6:30pm | 5:00pm | 10, 11, 12 | Claire |
| LC | 2026-05-02 | Tue | 3:30pm | 6:30pm | 5:00pm | 10, 11, 12 | Claire |
| CHAC | 2026-05-01 | Mon | 3:30pm | 6:30pm | 5:00pm | 10, 11, 12 | Ethan |
| CHAC | 2026-05-03 | Wed | 3:30pm | 6:30pm | 5:00pm | 10, 11, 12 | Camilo |

**Ingest note — time format:** Times stored as strings in Excel (e.g. `"4:00pm"`). Convert to `time` or `timestamptz` at ingest.  
**Ingest note — concurrency:** GyG delivers to both LC and CHAC on Mon 1 May at 5:00pm. This is a known same-caterer concurrent delivery — intentional, not a data error.

---

### exclusions

**Status:** REAL  
**Source:** `data/source/exclusions.pdf`  
**Row count:** 3 (demo week only)

| School | Date | Scope | Reason | Year levels excluded |
|---|---|---|---|---|
| ISHS | 2026-05-04 | Whole session | Open Day | All (9, 10, 11, 12) |
| LC | 2026-05-02 | Whole session | Parent–Teacher Interviews | All (10, 11, 12) |
| CHAC | 2026-05-03 | Partial | School Camp | Years 10 and 12 only; Year 11 still attends |

**Applied impact:** ISHS Thu excluded (39 students, no order). LC Tue excluded (21 students, no order). CHAC Wed partial: 17 students excluded (4 Yr10 + 13 Yr12), 22 Year 11 students still attend and need meals.  
**Note:** Dietary-restricted students are still covered even in partial exclusions (rule 3 in CLAUDE.md).

---

### absences

**Status:** REAL  
**Source:** `data/source/absences.pdf`  
**Row count:** 10 (demo week only)

| Date | School | Student | Session |
|---|---|---|---|
| 2026-05-01 | LC | Holly Hill | LC Monday |
| 2026-05-01 | LC | Imogen Evans | LC Monday |
| 2026-05-02 | MBBC | Noah Baker | MBBC Tuesday |
| 2026-05-02 | JPC | Christina Hu | JPC Tuesday |
| 2026-05-02 | JPC | Nathan Smith | JPC Tuesday |
| 2026-05-02 | ISHS | Charlie Morris | ISHS Tuesday |
| 2026-05-02 | ISHS | Jack Carter | ISHS Tuesday |
| 2026-05-02 | ISHS | Charlie Mitchell | ISHS Tuesday |
| 2026-05-03 | CHAC | Henry Cook | CHAC Wednesday |
| 2026-05-04 | MSHS | Rose Smith | MSHS Thursday |

**Note:** Source provides student name and date only — no notification source, timestamp, or channel. Ingest with `reported_at = null` or a plausible demo timestamp.  
**Note:** Imogen Evans (LC Monday absent) also appears as a cross-school overlap case. Her LC Monday absence is for the LC Monday enrolment specifically; her ISHS Tuesday enrolment is unaffected.

---

## Files found but not ingest targets

| File | What it is | Action |
|---|---|---|
| `data/source/Padea_Operations_Engineer_Competition_Task_Sheet.pdf` | Competition brief | Keep in place. Not data. |
| `docs/v1_initials/data_observations.md` | Authoritative pre-analysis of source files | Reference doc — keep. This inventory supersedes it for ingest planning purposes. |
| `docs/archive/2026-05-26_initials_drafts_and_misc/data_observations.md` | Earlier draft of the above | In archive — leave as-is. |
| `memo/memo_material.md` | Append-only stream for memo writing | Keep. Not data. |
| `memo/questions_for_dylan.md` | Open questions log | Keep. Most resolved now except GyG delivery (D9 assumption taken). |
| `docs/archive/**` | V1–V3 historical schema drafts | Keep in archive. Not data or ingest targets. |

---

## Open items — all resolved

**Spaghetti meatballs (Terrific Noodles)** — ✅ **Decision: treat as ambiguous / unsafe.**  
No `halal` tag. No beef/pork/red-meat tags applied (protein unknown, so no safe assumption either way).  
Students with `halal`, `no_beef`, `no_pork`, or `no_red_meat` restrictions **cannot be assigned this item**.  
Consistent with CLAUDE.md rule 3 — err on the side of dietary safety.

---

## Next steps before Phase 2 ingest can run

1. **Run the two ALTER TABLE statements from session 005** — add `other_allergy_notes text` to `enrolments` and three checklist booleans to `feedback` (these are free changes; tables are empty)
2. **Decide on Spaghetti meatballs** — see open item above
3. **Write `src/ingest/` scripts** in this order:
   1. `seed_dietary_tags.py` — 11-row reference table
   2. `seed_schools.py` — 6 rows from sessions.xlsx
   3. `seed_caterers.py` — 4 rows from caterers.xlsx + caterer-contacts.pdf (MOQ, pricing, contacts, served schools)
   4. `seed_tutors.py` — 7 rows (real names/mobiles, generated emails)
   5. `seed_menu_items.py` — 40 rows from caterer-menus.pdf + dietary tag junction rows
   6. `seed_sessions.py` — 11 session_slot rows + 11 session_tutor_assignment rows
   7. `seed_enrolments.py` — 320 enrolment rows + enrolment_dietary_tags rows (with opt-out extraction)
   8. `seed_absences.py` — 10 rows
   9. `seed_exclusions.py` — 3 rows
4. **Verify with a row-count check** — confirm all seed counts match expectations before any agent run
