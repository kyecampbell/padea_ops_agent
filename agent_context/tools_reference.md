# Tools Reference — Padea Operations Agent

This document is both the **agent's reference** for what tools it can call
and the **build spec** for `src/tools/`. Every tool here maps to a Python
function that the agent can invoke via Claude's tool-calling API.

Tools are grouped by functional area. Each entry shows:
- **Function signature** (Python — matches the real implementation)
- **When to call it** (agent guidance)
- **Returns** (what the agent gets back)

**Every tool listed below is implemented** and registered in
`src/agent/loop.py` (`TOOL_SCHEMAS` / `TOOL_REGISTRY`), except those in the final
**Not implemented** section, which are kept only to document the original design
intent. `check_and_resolve_crashed_runs` and `create_agent_run` /
`complete_agent_run` are loop-owned (called by `run()` directly) and are not
exposed to the model as tools.

---

## Infrastructure tools

### `create_agent_run`
```python
def create_agent_run(trigger_reason: str) -> int
```
**When**: First thing every run, called by the loop. Creates the `agent_runs` row.
**Returns**: `run_id` (bigint)
**Loop-owned** — not a model tool.

### `complete_agent_run`
```python
def complete_agent_run(run_id: int, notes: str) -> None
```
**When**: Last thing every run, called by the loop. Writes `completed_at` and summary notes.
**Loop-owned** — not a model tool.

### `log_agent_step`
```python
def log_agent_step(
    run_id: int,
    step_index: int,
    tool_name: str | None,
    tool_input: dict | None,
    tool_output_full: dict | None,
    reasoning: str | None,
    urgency: Literal['urgent', 'notable', 'informational', 'none'] = 'none'
) -> int  # step_id
```
**When**: After every dispatched tool call, called by the loop. The model does not call this directly — it records steps via `add_note`.
**Loop-owned** — not a model tool.

### `check_and_resolve_crashed_runs`
```python
def check_and_resolve_crashed_runs(staleness_minutes: int = 30) -> list[int]
```
**When**: Startup of every run, called by the loop right after `create_agent_run`. Closes any prior run left `running` past the staleness threshold (`completed_at IS NULL` and `started_at` older than the threshold). Returns the run_ids it closed.
**Loop-owned** — not a model tool.

### `add_note`
```python
# Loop meta-tool — no standalone Python function; handled in dispatch().
add_note(label: str, body: str, urgency: Literal['urgent','notable','informational','none'])
```
**When**: To record an observation, branch decision, or escalation in the decision log. `label` becomes `tool_name` in `agent_steps` (e.g. `sustained_decline_detected`, `moq_shortfall`, `unclassified_inbound`); `urgency` drives rendering in the HTML decision log.
**Returns**: nothing the model needs to use — the step is logged as a side effect.

---

## Gmail tools

### `gmail_poll_inbox`
```python
def gmail_poll_inbox(since_last_run_timestamp: str | None = None, max_results: int = 50) -> list[dict]
```
**When**: Start of every run, before any processing.
**Returns**: List of dicts with keys: `gmail_message_id`, `from_address`, `subject`, `received_at` (ISO), `body`. Reads UNREAD messages from the real `padea.catering` inbox (OAuth token identity, `userId="me"`) and drops any already in `inbound_email_records` (dedup by `gmail_message_id`).
**Notes**: `since_last_run_timestamp` is an optional ISO datetime; a future value (demo clock ahead of real time) is ignored so genuinely new mail is never hidden. Poll is isolated from demo-mode SEND rewriting — it always reads the real inbox.

### `gmail_send`
```python
def gmail_send(
    to: str,
    subject: str,
    body: str,
    email_type: str,            # 'session_order' | 'weekly_consolidated_summary' only
    cc: list[str] | None = None,
    related_order_id: int | None = None,
    related_caterer_id: int | None = None,
    related_run_id: int | None = None,   # injected by the loop — do not pass
    related_step_id: int | None = None
) -> int  # outbound_email_id
```
**When**: After composing a routine email that should actually send.
**Returns**: `outbound_email_id`. Writes status `'sent'` with the real `gmail_message_id` on success; on send failure writes a `'failed'` row with `failure_reason` and re-raises (the loop escalates it).
**Notes**: Commercial-relationship types (`warning`, `rfp`, `cancellation`, `rfp_loser_courtesy`) are **rejected** here — they must go through `queue_email_for_approval`. In demo mode the email is really sent to `demo_email_address`; `intended_to_address` keeps the real recipient and the body is prefixed `[DEMO — Intended for: {to}]` (idempotent). `related_run_id` is injected by the loop, never the model.

### `queue_email_for_approval`
```python
def queue_email_for_approval(
    email_type: str,            # 'warning' | 'rfp' | 'cancellation' | 'rfp_loser_courtesy'
    to: str,
    subject: str,
    body: str,
    related_run_id: int,        # injected by the loop — do not pass
    related_step_id: int | None = None,
    related_order_id: int | None = None,
    related_caterer_id: int | None = None
) -> int  # outbound_email_id
```
**When**: For commercial emails. Sets status `'queued_for_approval'`. **Never sends and never auto-advances** — a human approves it downstream.
**Notes**: Demo mode keeps `intended_to_address` real and prefixes the stored body with the demo marker.

---

## Session + scheduling tools

### `get_sessions_needing_orders`
```python
def get_sessions_needing_orders(as_of: datetime, window_hours: float = 1.0) -> list[dict]
```
**When**: Every run, to find T-72hrs triggers.
**Returns**: List of `{session_slot_id, session_date, school_id, caterer_id, session_start_datetime}` for sessions whose 72-hour mark falls within `[as_of - window_hours, as_of + window_hours]` AND that have no `orders` row yet.
**Notes**: If `as_of` is omitted by the model, the loop injects now() Brisbane (or the demo-clock override).

### `get_session_slot`
```python
def get_session_slot(session_slot_id: int) -> dict
```
**Returns**: Full `session_slots` row: `{id, school_id, day_of_week, start_time, dinner_time, end_time, room, active}`. Raises `ValueError` if not found.

---

## Enrolment tools

### `get_enrolments_for_session`
```python
def get_enrolments_for_session(session_slot_id: int, session_date: date) -> list[dict]
```
**When**: Internal to `compose_session_order` — the model does not call it directly during order composition.
**Returns**: Active, opted-in students needing a meal. Each dict: `enrolment_id`, `student_name`, `student_year_level`, `parent_email`, `dietary_tag_names` (list[str]), `other_allergy_notes`. Applies absences, whole-school and year-level exclusions, and the dietary override (dietary students always get a meal unless the school is physically closed).
**Notes**: Date parameter required — never defaults to today.

### `get_enrolment_dietary_tags`
```python
def get_enrolment_dietary_tags(enrolment_id: int) -> list[str]
```
**Returns**: List of dietary tag name strings (e.g. `['halal', 'vegetarian']`). Empty = no restrictions.

### `find_session_for_absence`
```python
def find_session_for_absence(student_name: str, session_date: date, parent_email: str | None = None) -> list[dict]
```
**When**: Processing an inbound `absence` email. Bridges student-name + date → `enrolment_id`, session slot, and order status (an absence email never carries an enrolment_id).
**Returns**: List of candidate dicts: `enrolment_id`, `student_name`, `parent_email`, `school_id`, `session_slot_id`, `session_date`, `day_of_week`, `order_exists`, `order_id`, `order_sent`. Matches by case-insensitive student_name, active on the date, with a session on that date's weekday. `parent_email` is preferred-not-filtered (demo dataset shares one parent address).
**Notes**: Empty list = no match (escalate). >1 row = ambiguous (escalate). Feeds `upsert_absence`; when `order_exists`/`order_sent` is true the agent must NOT amend the order.

---

## Absence and exclusion tools

### `get_absence`
```python
def get_absence(enrolment_id: int, absence_date: date) -> dict | None
```
**Returns**: Absence row if one exists for this (enrolment, date), else None. Walk-backs are row deletions, so a returned row is always an active absence.

### `upsert_absence`
```python
def upsert_absence(
    enrolment_id: int,
    absence_date: date,
    source_email_message_id: str | None = None,
    notes: str | None = None
) -> int  # absence_id
```
**When**: Processing an `absence` inbound email.
**Notes**: Idempotent — `ON CONFLICT DO NOTHING` on (enrolment_id, absence_date), original `received_at` preserved.

### `get_exclusions`
```python
def get_exclusions(school_id: int, session_date: date) -> list[dict]
```
**Returns**: All exclusion rows covering this school on this date. Each dict: `id`, `school_id`, `enrolment_id` (null = school-wide scope), `reason`, `start_date`, `end_date`, `year_levels_excluded`. `year_levels_excluded=[]` means whole-school (school physically closed).

### `get_year_level_exclusions`
```python
def get_year_level_exclusions(school_id: int, session_date: date) -> list[dict]
```
**Returns**: School-level exclusions targeting specific year levels (`enrolment_id IS NULL` and `year_levels_excluded != []`). List of `{id, reason, excluded_year_levels: list[int]}`.
**Notes**: Scope is read from the structured `year_levels_excluded` column — not parsed from `reason` text.

---

## Meal selection tools

### `get_meal_request`
```python
def get_meal_request(enrolment_id: int, session_slot_id: int, session_date: date) -> dict | None
```
**Returns**: Unconsumed `meal_requests` row if one exists (`{request_id, menu_item_id, name, price_cents}`), else None.
**Notes**: Internal to `compose_session_order`.

### `consume_meal_request`
```python
def consume_meal_request(request_id: int) -> None
```
**When**: Immediately after using a meal_request in order composition. Internal to `compose_session_order`.

### `get_next_rotation_meal`
```python
def get_next_rotation_meal(enrolment_id: int, caterer_id: int) -> dict | None
```
**Returns**: The next menu_item in the student's rotation — the item from their approved set (canonical popularity order) served least recently. `{menu_item_id, name, price_cents}` or None if no approved set exists for this caterer.
**Notes**: Internal to `compose_session_order`. Rotation recency uses `MAX(orders.session_date)` for prior service of each item.

### `auto_pick_dietary_meal`
```python
def auto_pick_dietary_meal(enrolment_id: int, caterer_id: int) -> dict | None
```
**When**: Dietary safety fallback. Returns any active menu_item for this caterer that passes all the student's dietary tags, else None. Internal to `compose_session_order`; a None result triggers the VO fallback, then an urgent escalation.

### `item_is_safe_for_enrolment`
```python
def item_is_safe_for_enrolment(menu_item_id: int, enrolment_id: int) -> bool
```
**Returns**: True if `item.tags ⊇ student.tags` (set containment). Students with no dietary tags are vacuously safe.

---

## Order tools

### `compose_session_order`
```python
def compose_session_order(session_slot_id: int, session_date: date) -> dict
```
**When**: The single order-composition call per session (system prompt §Order composition, Step 2). Handles the whole cohort pipeline internally: enrolments → absences/exclusions with dietary override → meal selection (request → rotation → dietary auto-pick → VO fallback) → per-line safety checks → `create_order` persist.
**Returns**: `{order_id, caterer_id, total_students, total_cost_cents, order_lines, safety_records, escalations}`. `safety_records` has one entry per student (`safe` bool, `variant`, `other_allergy_notes`); the loop processes these unconditionally after dispatch and logs dietary-safety / allergy / VO steps. `escalations` is a list of no-safe-meal strings.
**Notes**: Do NOT call the internal meal/enrolment tools separately — it wastes the tool budget.

### `check_weekly_moq`
```python
def check_weekly_moq(caterer_id: int, week_of: date) -> dict
```
**Returns**: `{total_items, moq_applicable (int | None), shortfall, shortfall_cents}`. `moq_applicable` is None if the week's variety count is outside {4,5,6}. `shortfall`/`shortfall_cents` are always ints (0 if none).
**Algorithm**: Sums `order_lines` across all of this caterer's orders in the ISO week containing `week_of`; looks up the applicable `caterers.moq_N_items` tier by variety count.

### `create_order`
```python
def create_order(
    session_slot_id: int,
    session_date: date,
    caterer_id: int,
    order_lines: list[dict],   # each: {enrolment_id, menu_item_id, source, variant?}
    total_cost_cents: int,
    gst_rate_percent: float = 10.0,
    moq_floor_applied: bool = False,
    moq_variance_cents: int = 0
) -> int  # order_id
```
**When**: Internal to `compose_session_order` — not called by the model directly.
**Notes**: Raises `ValueError` if an order already exists for (session_slot_id, session_date) rather than duplicating.

### `compose_order_email`
```python
def compose_order_email(order_id: int) -> str
```
**Returns**: Rendered email body string: session details, deliver-by time (dinner − 10 min), per-student meal list with dietary safety flags (`⚠ UNSAFE MATCH`, `⚠ ALLERGY NOTE (unverified)`, `⚑ VEGETARIAN OPTION`), and per-meal count summary.
**Notes**: **No costs appear on per-session order emails** (V4 ruling — costs live in the Monday consolidated summary). Demo mode prepends `[DEMO — Intended for: {caterer_email}]`. Read-only.

---

## Quality / feedback tools

### `get_feedback_for_session`
```python
def get_feedback_for_session(session_slot_id: int, session_date: date) -> dict
```
**Returns**: `{manager_rating, manager_comments, food_on_time, correct_count_received, correct_dietary_delivered, food_temperature_ok, visibly_wrong, meals_left, kids_who_didnt_eat, tutor_ratings (list[int|None]), student_avg}`. All null/empty if no order exists for (session_slot, date).

### `compute_rolling_mean`
```python
def compute_rolling_mean(caterer_id: int, weeks: int = 4, as_of: datetime | None = None) -> float | None
```
**Returns**: Unweighted mean of all non-null feedback ratings (tutor + manager) for this caterer in the `weeks`-week window ending at `as_of` (default now() Brisbane). Returns None if fewer than 3 non-null ratings exist.
**Notes**: V4-OPT-04 — `caterer_id` is denormalised onto `feedback`, no joins. `as_of` is pinnable for deterministic demo/tests.

### `get_feedback_since`
```python
def get_feedback_since(since_timestamp: datetime) -> list[dict]
```
**Returns**: All feedback rows submitted strictly after `since_timestamp`, each: `{id, source, caterer_id, rating, submitted_at, session_slot_id, session_date}`. Takes one parameter only — use `compute_rolling_mean` for per-caterer aggregation.

---

## Caterer reach tools

### `caterers_within_range`
```python
def caterers_within_range(school_id: int, exclude_caterer_id: int | None = None) -> list[dict]
```
**Returns**: List of caterers where `geodesic(school.postcode, caterer.home_postcode) ≤ caterer.max_delivery_km`. Each: `{caterer_id, name, contact_email, home_postcode, max_delivery_km, delivery_fee_cents, distance_km}`. `exclude_caterer_id` (typically the incumbent) is omitted before the distance check.
**Notes**: Distance uses a hardcoded QLD postcode→centroid dict + `geopy` geodesic. Raises `ValueError` on an unknown postcode — never silently wraps.

### `project_weekly_cost`
```python
def project_weekly_cost(caterer_id: int, school_id: int) -> dict
```
**Returns**: `{cohort_size, per_meal_price_cents, delivery_fee_cents, moq_floor_cents (int|None), projected_total_cents}`. All amounts GST-inclusive integer cents. Cohort = current active opted-in enrolments at the school; moq_5 tier assumed for projection.

---

## Weekly summary tools

### `generate_weekly_summary`
```python
def generate_weekly_summary(caterer_id: int, week_of: date, as_of: datetime | None = None) -> dict
```
**Returns**: Dict with `caterer_id, caterer_name, caterer_email, week_start, week_end, total_items, total_cost_cents, grand_total_cents, gst_amount_cents, delivery_fee_cents, total_delivery_cents, sessions_count, moq_applicable, moq_floor_applied, moq_variance_cents, mean_4w, mean_12w, sustained_decline, session_breakdown, already_completed`.
**Notes**: Aggregates all orders for this caterer in the ISO week (Mon–Sun) containing `week_of`. GST normalised to an inclusive total over meals + delivery×sessions, one round at the boundary. `as_of` pins the quality rolling means. If a `weekly_consolidated_summary` email already exists for this caterer this week, returns `{already_completed: True}` with no mutations. Pass the whole dict to `compose_weekly_summary_email`.

### `compose_weekly_summary_email`
```python
def compose_weekly_summary_email(caterer_id: int, summary: dict) -> str
```
**Returns**: Rendered email body string — a **payment document only**: week header, per-session breakdown, cost block (meals + delivery + GST + TOTAL DUE), MOQ floor note if applied. No quality ratings, decline alerts, or "warning queued" text ever reach the caterer (that is operator-facing decision-log content).
**Notes**: Do not call with the `{already_completed: True}` early-return form. Demo mode prepends the demo marker. Read-only.

---

## Inbound email tools

### `classify_inbound_email`
```python
def classify_inbound_email(
    gmail_message_id: str,
    from_address: str,
    subject: str,
    body: str,
    received_at: datetime
) -> dict  # {gmail_message_id, classification}
```
**When**: For each message returned by `gmail_poll_inbox`. Routes into exactly one of `'absence'`, `'caterer_order_confirmation'`, `'caterer_price_change_notification'`, `'parent_enrolment_response'`, `'unclassified'`.
**Notes**: Uses Claude **Haiku** (`settings.classifier_model`) — the only sanctioned Haiku use in the architecture. An unrecognised reply falls back to `'unclassified'`. **Also writes the `inbound_email_records` dedup row** (`ON CONFLICT DO NOTHING`) — there is no separate `record_inbound_email` step. Sonnet (the agent loop) does all downstream reasoning and routing.

---

## Not implemented

These appeared in the original design but are **not built** and **not registered**.
The agent must never call them; the system prompt routes the relevant inbound
labels to escalations instead.

- `record_inbound_email` — folded into `classify_inbound_email` (the dedup write happens there).
- `create_term_meal_preferences` — enrolment intake is operator-owned end-to-end; `parent_enrolment_response` escalates for manual entry.
- `compute_canonical_menu_order` — canonical order is seeded, not computed at runtime.
- `confirm_order` — no order-confirmation write; `caterer_order_confirmation` is logged for audit only.
- `update_enrolment_dietary_tags` — no enrolment-write tool; see `parent_enrolment_response` handling.
- `regenerate_decision_log` — superseded by the offline renderer `scripts/build_renderer.py`, which is run manually (read-only over `agent_runs` / `agent_steps`), not a runtime tool.
