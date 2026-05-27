# Domain Knowledge Reference
# Compact reference for the Padea Operations Agent.
# Covers business rules, controlled vocabularies, and data model highlights.
# The agent can consult this inline; it doesn't need to re-read design docs.

---

## The operation in brief

Padea runs tutoring sessions at six schools in Queensland. Most schools have one session per week (Mon–Thu), each 2–3 hours long with dinner in the middle. One caterer supplies meals for each (school, day-of-week) pair. The agent's primary job is to make sure the right meals are ordered for the right students at the right time, every week.

**Scale (approximate):** 6 schools, ~320 unique students, ~5 caterers, ~11 sessions per week.

---

## Session cadence

| School session day | Order sent (T-72hrs) |
|---|---|
| Monday | Friday ~15:00 |
| Tuesday | Saturday ~15:00 |
| Wednesday | Sunday ~15:00 |
| Thursday | Monday ~15:00 |

The Monday T-72hrs trigger fires on the same Monday as the consolidated summary (~15:00 vs ~15:30 — order first, then summary).

---

## Dietary tags (controlled vocabulary)

These are the `dietary_tags` rows seeded in the database. Every tag is treated as safety-critical — there is no severity hierarchy.

| name | label | What it means for meal selection |
|---|---|---|
| `no_pork` | No pork | Exclude items where `menu_items.contains_pork = true` |
| `no_seafood` | No seafood | Exclude items where `menu_items.contains_seafood = true` |
| `no_nuts` | No nuts | Exclude items where `menu_items.contains_nuts = true` |
| `no_dairy` | No dairy | Exclude items where `menu_items.contains_dairy = true` |
| `halal` | Halal | Practically: exclude `contains_pork` items (V3 assumption — non-pork = halal) |
| `vegetarian` | Vegetarian | Include only items where `menu_items.is_vegetarian = true` |
| `vegan` | Vegan | Include only items where `menu_items.is_vegan = true` |
| `gluten_free` | Gluten free | Include only items where `menu_items.is_gluten_free = true` |
| `mild_only` | Mild only | No structural field yet — operator must manually verify; flag in order notes |

**Rule for matching:** A meal is safe for a student if it passes ALL of the student's active dietary tags. The intersection of all constraints applies.

**`halal` + `no_pork`**: These are often co-occurring but not identical. `halal` alone is sufficient to trigger the pork exclusion. `no_pork` alone covers students who avoid pork for non-halal reasons (e.g., taste, religious reasons other than halal).

---

## Menu item safety check logic

```python
def item_is_safe_for_student(menu_item, student_dietary_tag_names):
    rules = {
        'no_pork':     not menu_item.contains_pork,
        'halal':       not menu_item.contains_pork,
        'no_seafood':  not menu_item.contains_seafood,
        'no_nuts':     not menu_item.contains_nuts,
        'no_dairy':    not menu_item.contains_dairy,
        'vegetarian':  menu_item.is_vegetarian,
        'vegan':       menu_item.is_vegan,
        'gluten_free': menu_item.is_gluten_free,
        'mild_only':   True,  # No DB field — manual verification required
    }
    return all(rules[tag] for tag in student_dietary_tag_names if tag in rules)
```

---

## Meal rotation logic

Each student has an approved meal set for the current caterer (`term_meal_preferences` → `term_meal_preference_items`). Within that approved set, meals are served in a canonical order.

**Canonical order** (`caterers.canonical_menu_order`): A JSON array of menu_item_ids, ranked by how frequently they appear across all students' approved sets at the school — most popular first, ties broken randomly. Computed once at term start and once at caterer change. Stored on the caterer row.

**Rotation step**: For a given student at a given caterer, take the intersection of their approved menu_item_ids with the caterer's canonical_menu_order. Find the item in that intersection that was served least recently. Serve it next.

**Override**: If a meal_request exists for (enrolment_id, session_slot_id, session_date) with `consumed_at IS NULL`, use the requested item instead. Requests can be any dietary-safe item on the menu, not constrained to the approved set.

---

## Order composition filters (applied in order)

1. Whole-session exclusion → no order at all
2. Enrolment active on session_date
3. Not opted out (`opted_out_of_catering = false`)
4. Not individually absent (unless dietary-restricted)
5. Not in excluded year level (unless dietary-restricted)
6. → Remaining students get meals via request or rotation
7. → Year-level exclusion buffer: `ceil(0.10 × excluded_count)` contingency meals

---

## Enrolment active state

**Active on date D** means:
```sql
current_period_start_date <= D
AND (current_period_end_date IS NULL OR current_period_end_date > D)
```

Never use "today" as D implicitly. The date of interest is always the session date (for orders), the report date (for weekly report), or the incident date (for investigation).

---

## Caterer rotation chain (human-in-the-loop)

1. **Sustained decline detected** → agent raises notable escalation, drafts warning email (status=queued_for_approval).
2. **Operator approves** → warning email sent to incumbent caterer.
3. **Operator judges no recovery** (manual call) → operator asks agent to fire RFP.
4. **Agent fires RFP** → calls `caterers_within_range(school_id)`, drafts RFP emails to all eligible caterers (status=queued_for_approval). Operator approves.
5. **Responses arrive** → classified as `parent_enrolment_response` ... actually no, these are unclassified inbound. They escalate. Operator reviews. Agent drafts comparison panel.
6. **Operator picks** → agent drafts cancellation to incumbent + engagement email to new caterer. Both queued_for_approval. Operator approves.
7. **New caterer onboarded** → first week flagged as `is_preview_week=true`. Operator composes that week manually. Tutors reset student preferences after the preview week.

---

## Email type → approval flow

```
Routine (no approval needed):
  session_order, weekly_consolidated_summary,
  parent_enrolment, parent_reminder,
  opt_back_in_request_to_parent, operator_notification

Commercial (queued_for_approval before sending):
  warning, rfp, cancellation, rfp_loser_courtesy
```

Status lifecycle:
- Routine: `drafted → sending → sent` (or `failed`)
- Commercial: `drafted → queued_for_approval → approved → sending → sent` (or `failed`)

---

## Escalation dedup convention

Before creating a new escalation-type agent step, check if a similar notable/urgent step already exists in the current run for the same entity. The same run should not produce two "MOQ shortfall" steps for the same caterer-week pair.

Across runs: the decision log is regenerated from scratch each run. Recurring conditions (MOQ shortfall at the same school 4 weeks running) appear 4 times in the log — this is intentional. The weekly report aggregates them for pattern recognition.

---

## Demo mode (EMAIL_MODE=demo)

When `email_mode = demo` in runtime_config.yaml:
- Every `gmail_send` call rewrites the `to` address to `demo_email_address`.
- The original intended_to_address is preserved in `outbound_emails.intended_to_address` and prepended to the email body: `[DEMO — Intended for: {original_address}]`.
- The database row reflects the original intent. The Gmail thread shows the rewrite.
- No code change between demo and production — flip `email_mode` to 'production' in config.

---

## Key assumptions from design (V3-locked)

- Non-pork items are treated as halal (from source PDF rule, assumption #2).
- One caterer per school per day (operational constraint, assumption #5).
- Caterer rotation is human-in-the-loop — no automatic replacement (assumption #21).
- MOQ treated as a hard weekly contract minimum — pay the floor, don't pad (assumption #22).
- "3 days before" = 3 days before session *start* time, not dinner time (assumption #23).
- Dietary tags overwrite in place — no history table for dietary changes (known gap, memo-flagged).
- Menu prices overwrite in place — no effective-date history. Order total at composition time is the audit record.

---

## Database: key table relationships

```
schools ──< session_slots ──< session_tutor_assignments >── tutors
                 │
                 ▼
enrolments >── session_slots (via school_id)
enrolments ──< enrolment_dietary_tags >── dietary_tags
enrolments ──< term_meal_preferences ──< term_meal_preference_items >── menu_items
enrolments ──< meal_requests >── menu_items
enrolments ──< absences
enrolments ──< order_lines >── orders >── session_slots
order_lines ──< feedback (tutor, per-line)
orders ──< feedback (manager, per-order)
agent_runs ──< agent_steps
outbound_emails ── (related_order_id, related_run_id, related_step_id)
inbound_email_records ── (related_absence_id, related_order_id, related_enrolment_id)
```

---

## Source data summary (ingest reference)

| File | Contents | Key note |
|---|---|---|
| `data/source/students.xlsx` | ~320 unique students across 6 schools | Multi-enrolment students (same name, same school) = same student |
| `data/source/sessions.xlsx` | Session slots per school | Times, days, room information |
| `data/source/caterers.xlsx` | Caterer identity, MOQ tiers | Contact info (Padea-controlled demo emails) |
| `data/source/caterer-menus.pdf` | Per-caterer menu items with prices | Contains "VO" (vegetarian option) notations |
| `data/source/caterer-contacts.pdf` | Contacts per caterer, roles | Email/name pairings are placeholder |
| `data/source/absences.pdf` | Sample absences for demo seeding | |
| `data/source/exclusions.pdf` | Sample exclusions for demo seeding | |
