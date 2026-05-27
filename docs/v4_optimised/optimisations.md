# V4 Optimisations

**Version:** V4 (post-review pass on V3 final schema)
**Date:** 28 May 2026
**Schema file:** `docs/v4_optimised/Schema/v4_schema.sql`
**V3 reference:** `docs/v3_final/Schema/v3_schema.sql` (unchanged)

---

## Context

After V3 was finalised and deployed, a review pass over the schema identified five changes worth making before tool code is written. None alter the system's behaviour or contradict any of the ten V3 design decisions. They are structural correctness and performance improvements that would otherwise surface as silent bugs, query complexity, or data integrity gaps during development.

V3 is preserved unchanged as the historical record. V4 is the working schema going forward.

---

## OPT-01 — `updated_at` trigger function

**What V3 had:** Six tables carry an `updated_at timestamptz NOT NULL DEFAULT now()` column — `schools`, `caterers`, `menu_items`, `tutors`, `enrolments`, `session_slots`. The `DEFAULT now()` only fires on `INSERT`. On any subsequent `UPDATE` the column stays frozen at the original insert time, silently returning stale data to any code that reads it.

**What V4 changes:** Adds a single shared trigger function:

```sql
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;
```

Then attaches a `BEFORE UPDATE` trigger to each of the six affected tables immediately after their `CREATE TABLE` statement:

```sql
CREATE TRIGGER trg_<table>_updated_at
    BEFORE UPDATE ON <table>
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

**Tables with triggers added:**

| Table | Trigger name |
|---|---|
| `schools` | `trg_schools_updated_at` |
| `caterers` | `trg_caterers_updated_at` |
| `menu_items` | `trg_menu_items_updated_at` |
| `tutors` | `trg_tutors_updated_at` |
| `enrolments` | `trg_enrolments_updated_at` |
| `session_slots` | `trg_session_slots_updated_at` |

No other tables in the schema carry an `updated_at` column, so no other triggers are needed.

**Why it matters:** `updated_at` is used by incremental sync patterns, cache invalidation, and audit queries. A column that never updates is worse than no column — it looks correct but returns wrong data. One trigger function shared by all tables keeps the fix trivial to audit.

---

## OPT-02 — Three text-CHECK columns promoted to enum types

**What V3 had:** Three columns stored domain-constrained values as `text` with either a `CHECK` constraint or just an inline comment listing valid values:

| Table | Column | V3 definition |
|---|---|---|
| `term_meal_preferences` | `captured_by` | `text NOT NULL CHECK (captured_by IN ('parent', 'tutor', 'operator'))` |
| `order_lines` | `source` | `text NOT NULL CHECK (source IN ('rotation', 'request', 'preview_week_operator', 'dietary_auto_pick'))` |
| `orders` | `rotation_status` | `text` — valid values listed in an inline comment only, no CHECK |

**What V4 changes:** Creates three new Postgres enum types and converts the columns to use them. The CHECK constraints are removed because the enum enforces the domain at the type level.

```sql
CREATE TYPE preference_capture_source AS ENUM (
    'parent', 'tutor', 'operator'
);

CREATE TYPE order_line_source AS ENUM (
    'rotation', 'request', 'preview_week_operator', 'dietary_auto_pick'
);

CREATE TYPE order_rotation_status AS ENUM (
    'normal', 'warning_active', 'rfp_pending'
);
```

Column changes:
- `term_meal_preferences.captured_by` → `preference_capture_source NOT NULL`
- `order_lines.source` → `order_line_source NOT NULL`
- `orders.rotation_status` → `order_rotation_status` (nullable — an order with no rotation context is valid)

**Why it matters:** Postgres enums are stricter than CHECK constraints: they reject invalid values at the type layer before any constraint check runs, they self-document in `\d` and schema introspection tools, and they give Python code a well-defined set of literals to validate against. The `rotation_status` column was particularly at risk — a free-text column with no CHECK constraint is invisible to any enforcement at all.

---

## OPT-03 — UNIQUE constraint on `outbound_emails.gmail_message_id`

**What V3 had:** A partial index:

```sql
CREATE INDEX idx_outbound_emails_gmail_msg
    ON outbound_emails (gmail_message_id) WHERE gmail_message_id IS NOT NULL;
```

A partial index improves lookup speed but does not enforce uniqueness. Two rows could hold the same `gmail_message_id` without any error, allowing the same sent Gmail message to be associated with multiple outbound rows.

**What V4 changes:** Removes the partial index and adds a `UNIQUE` constraint inline on the column:

```sql
gmail_message_id text UNIQUE,
```

**Why it matters:** `gmail_message_id` is Postgres's uniqueness guarantee over outgoing Gmail messages. Allowing duplicates would break the idempotency assumption that the rest of the system relies on — if two rows share a message ID, any query joining through `gmail_message_id` would produce double rows in a non-obvious way. Postgres UNIQUE constraints allow multiple `NULL` values by default, so unsent rows (where `gmail_message_id` is still `NULL`) do not conflict with each other. The constraint provides the protection that the V3 partial index implied but did not actually deliver.

---

## OPT-04 — `caterer_id` denormalised onto `feedback`

**What V3 had:** The `feedback` table has no direct reference to a caterer. For tutor feedback, the chain is: `feedback.order_line_id → order_lines.order_id → orders.caterer_id`. For manager feedback: `feedback.order_id → orders.caterer_id`. The rolling-mean query — which is the most frequently computed analytic in the entire system — requires at minimum one join (manager path) and two joins (tutor path) just to filter by caterer.

**What V4 changes:** Adds a denormalised `caterer_id` column directly on `feedback`:

```sql
caterer_id bigint NOT NULL REFERENCES caterers(id) ON DELETE RESTRICT,
```

And adds a supporting index for the rolling-mean hot path:

```sql
CREATE INDEX idx_feedback_caterer_date
    ON feedback (caterer_id, submitted_at);
```

**Why it matters:** The rolling-mean computation fires on every agent run — five to seven times a week — for every caterer. Eliminating the join path from a two-step traversal to a direct column filter is a real query simplification, not a micro-optimisation. The denormalisation is safe: a caterer is assigned to an order at composition time and never changes retroactively. `caterer_id` on a feedback row will therefore never drift out of sync after the initial `INSERT`. The column comment in the SQL makes this reasoning explicit so future maintainers do not mistake it for accidental redundancy.

---

## OPT-05 — `gst_rate_percent` snapshotted onto `orders`

**What V3 had:** GST rate lived only on the `caterers` table (`gst_rate_percent numeric(4,2) NOT NULL DEFAULT 10.0`). There was no copy of the rate on the `orders` table. Computing the correct GST for any historical order required joining back to `caterers` and reading the current rate — which may have changed since the order was composed.

**What V4 changes:** Adds a snapshot column to `orders`:

```sql
gst_rate_percent numeric(5,2) NOT NULL,
```

This is populated at order-composition time by copying the caterer's current `gst_rate_percent`. The type is widened to `numeric(5,2)` (up from `numeric(4,2)` on `caterers`) to give slightly more headroom.

**Why it matters:** Australia's GST rate is currently stable at 10%, but any schema that relies on a mutable rate column for historical cost calculations is architecturally fragile. The Monday weekly consolidated summary, the historical cost trajectory in the weekly report, and any payment dispute resolution all depend on knowing what rate was in effect at the time the order was composed — not what it is today. Snapshotting the rate at composition time is the standard accounting pattern for this class of data. Cost is `total_cost_cents`; GST rate is the evidence of how that cost was computed. Both should be immutable once the order is sent.

---

## OPT-06 — `menu_items` dietary boolean columns replaced with a junction table

**What V3 had:** Eight boolean columns sat directly on `menu_items` to describe dietary properties:

```sql
contains_pork    boolean NOT NULL DEFAULT false,
is_vegetarian    boolean NOT NULL DEFAULT false,
is_vegan         boolean NOT NULL DEFAULT false,
is_halal         boolean NOT NULL DEFAULT false,
is_gluten_free   boolean NOT NULL DEFAULT false,
contains_seafood boolean NOT NULL DEFAULT false,
contains_nuts    boolean NOT NULL DEFAULT false,
contains_dairy   boolean NOT NULL DEFAULT false,
```

The `dietary_tags` table and `enrolment_dietary_tags` junction already existed to record student dietary requirements — but menu items had no relationship to that vocabulary at all. The two sides used completely separate mechanisms: student requirements via structured tags, item properties via raw booleans. The `dietary_tags` seed descriptions were student-facing: `'Kid does not eat pork'`, `'Kid eats only halal meals'`, etc.

**What V4 changes:** The eight boolean columns are dropped from `menu_items`. A new junction table is introduced:

```sql
CREATE TABLE menu_item_dietary_tags (
    menu_item_id   bigint NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
    dietary_tag_id bigint NOT NULL REFERENCES dietary_tags(id) ON DELETE RESTRICT,
    PRIMARY KEY (menu_item_id, dietary_tag_id)
);

CREATE INDEX idx_menu_item_dietary_tags_tag
    ON menu_item_dietary_tags (dietary_tag_id);
```

The `dietary_tags` seed descriptions are updated from student-facing to neutral so they read correctly on both sides — `'Pork-free'` instead of `'Kid does not eat pork'`, `'Halal-certified'` instead of `'Kid eats only halal meals'`, and so on.

**The semantic rule introduced:** The same `dietary_tags` vocabulary now serves both sides. On a student enrolment via `enrolment_dietary_tags`: "I need this property." On a menu item via `menu_item_dietary_tags`: "I satisfy this property." The safety check at order composition is therefore a clean set operation:

```
item is safe for student  ⟺  item.tags ⊇ student.tags
```

This replaces the V3 approach of checking a mixed boolean state across eight columns — a series of boolean ANDs that would require a schema migration every time a new dietary requirement appeared.

**Why it matters:** The boolean-column approach had two compounding problems. First, adding a new dietary requirement — say, sesame-free — required an `ALTER TABLE` to add a column, a migration, and code changes across every query that checked dietary safety. The junction approach requires only a single `INSERT INTO dietary_tags`. Second, the asymmetry between the student side (structured tags) and the item side (booleans) meant the dietary safety check was split across two different mechanisms with different failure modes. Unifying them into a single vocabulary makes the safety logic a single auditable function, and makes the system's extensibility consistent from day one of tool development.

---

## Summary table

| ID | What changed | Tables affected |
|---|---|---|
| OPT-01 | `updated_at` trigger function + 6 triggers | `schools`, `caterers`, `menu_items`, `tutors`, `enrolments`, `session_slots` |
| OPT-02 | 3 text columns → enum types | `term_meal_preferences`, `order_lines`, `orders` |
| OPT-03 | `gmail_message_id` partial index → UNIQUE constraint | `outbound_emails` |
| OPT-04 | Denormalised `caterer_id` + new index | `feedback` |
| OPT-05 | Snapshotted `gst_rate_percent` | `orders` |
| OPT-06 | 8 dietary boolean columns → `menu_item_dietary_tags` junction; neutral tag descriptions | `menu_items`, `dietary_tags` (seed), new `menu_item_dietary_tags` |
