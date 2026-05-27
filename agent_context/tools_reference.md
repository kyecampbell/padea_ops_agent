# Tools Reference — Padea Operations Agent

This document is both the **agent's reference** for what tools it can call
and the **build spec** for `src/tools/`. Every tool here maps to a Python
function that the agent can invoke via Claude's tool-calling API.

Tools are grouped by functional area. Each entry shows:
- **Function signature** (Python)
- **When to call it** (agent guidance)
- **Returns** (what the agent gets back)
- **Build status** (stub / in-progress / done)

---

## Infrastructure tools

### `create_agent_run`
```python
def create_agent_run(trigger_reason: str) -> int
```
**When**: First thing every run. Creates the `agent_runs` row.  
**Returns**: `run_id` (bigint)  
**Build status**: stub

### `complete_agent_run`
```python
def complete_agent_run(run_id: int, notes: str) -> None
```
**When**: Last thing every run. Writes `completed_at` and summary notes.  
**Build status**: stub

### `log_agent_step`
```python
def log_agent_step(
    run_id: int,
    step_index: int,
    tool_name: str | None,
    tool_input: dict | None,
    tool_output_full: dict | None,
    reasoning: str | None,
    urgency: Literal['urgent', 'notable', 'informational', 'none']
) -> int  # step_id
```
**When**: After every significant action. Routine tool calls use urgency='none'.  
**Build status**: stub

### `check_and_resolve_crashed_runs`
```python
def check_and_resolve_crashed_runs(staleness_minutes: int = 30) -> list[int]
```
**When**: Startup of every run. Returns list of run_ids marked as crashed.  
**Build status**: stub

---

## Gmail tools

### `gmail_poll_inbox`
```python
def gmail_poll_inbox(since_timestamp: datetime) -> list[dict]
```
**When**: Start of every run, before any processing.  
**Returns**: List of dicts with keys: `gmail_message_id`, `received_at`, `from_address`, `from_name`, `to_address`, `subject`, `body_plain`, `body_html`, `raw_headers`.  
**Notes**: Authenticates via OAuth2 token at `gmail_token_path` from config. Returns only messages not already in `inbound_email_records`.  
**Build status**: stub

### `gmail_send`
```python
def gmail_send(
    to: str,
    subject: str,
    body: str,
    email_type: str,
    cc: list[str] | None = None,
    related_order_id: int | None = None,
    related_caterer_id: int | None = None,
    related_enrolment_id: int | None = None,
    related_run_id: int | None = None,
    related_step_id: int | None = None
) -> int  # outbound_email_id
```
**When**: After composing any email that should actually send.  
**Returns**: `outbound_email_id`. Raises on send failure (agent catches and escalates).  
**Notes**: In demo mode, rewrites `to` to `demo_email_address` from config, prepends `[DEMO — Intended for: {to}]` to body. Writes `outbound_emails` row with full audit trail.  
**Build status**: stub

### `queue_email_for_approval`
```python
def queue_email_for_approval(
    email_type: str,
    to: str,
    subject: str,
    body: str,
    related_run_id: int,
    related_step_id: int,
    related_order_id: int | None = None,
    related_caterer_id: int | None = None
) -> int  # outbound_email_id
```
**When**: For commercial emails (warning, rfp, cancellation, rfp_loser_courtesy). Sets status='queued_for_approval'. Never sends directly.  
**Build status**: stub

---

## Session + scheduling tools

### `get_sessions_needing_orders`
```python
def get_sessions_needing_orders(
    as_of: datetime,
    window_hours: float = 1.0
) -> list[dict]
```
**When**: Every run, to find T-72hrs triggers.  
**Returns**: List of `{session_slot_id, session_date, school_id, caterer_id, session_start_datetime}` for sessions whose 72-hour mark falls within `[as_of - window_hours, as_of + window_hours]` AND no `orders` row already exists for that `(session_slot_id, session_date)`.  
**Build status**: stub

### `get_session_slot`
```python
def get_session_slot(session_slot_id: int) -> dict
```
**Returns**: Full `session_slots` row including school_id, day_of_week, times, room.  
**Build status**: stub

---

## Enrolment tools

### `get_enrolments_for_session`
```python
def get_enrolments_for_session(session_slot_id: int, session_date: date) -> list[dict]
```
**When**: Step 2 of order composition.  
**Returns**: Active, non-opted-out enrolments for the school that owns this session_slot, active on session_date. Each dict includes `enrolment_id`, `student_name`, `student_year_level`, `parent_email`, plus list of `dietary_tag_names`.  
**Notes**: Date parameter required — never defaults to today.  
**Build status**: stub

### `get_enrolment_dietary_tags`
```python
def get_enrolment_dietary_tags(enrolment_id: int) -> list[str]
```
**Returns**: List of dietary tag name strings (e.g. `['halal', 'no_seafood']`).  
**Build status**: stub

---

## Absence and exclusion tools

### `get_absence`
```python
def get_absence(enrolment_id: int, absence_date: date) -> dict | None
```
**Returns**: Absence row if one exists for this (enrolment, date), else None. Returns None if the absence has been walked back (the tool handles this — don't return walked-back absences).  
**Build status**: stub

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
**Notes**: Idempotent — ignores duplicate (enrolment_id, absence_date) pairs.  
**Build status**: stub

### `get_exclusions`
```python
def get_exclusions(school_id: int, session_date: date) -> list[dict]
```
**Returns**: All exclusion rows covering this school on this date. Each dict has `school_id`, `enrolment_id` (null for full-school), `reason`, `start_date`, `end_date`.  
**Build status**: stub

### `get_year_level_exclusions`
```python
def get_year_level_exclusions(school_id: int, session_date: date) -> list[dict]
```
**Returns**: Exclusions that target a specific year level (i.e., `enrolment_id IS NULL` but a year-level `reason` pattern). Returns list of `{reason, excluded_year_levels: list[str]}`.  
**Notes**: In V3, year-level exclusions are modelled as school-level exclusions with reason text. The tool parses the reason to extract affected year levels.  
**Build status**: stub

---

## Meal selection tools

### `get_meal_request`
```python
def get_meal_request(enrolment_id: int, session_slot_id: int, session_date: date) -> dict | None
```
**Returns**: Unconsumed `meal_requests` row if one exists, else None.  
**Build status**: stub

### `consume_meal_request`
```python
def consume_meal_request(request_id: int) -> None
```
**When**: Immediately after using a meal_request in order composition.  
**Build status**: stub

### `get_next_rotation_meal`
```python
def get_next_rotation_meal(enrolment_id: int, caterer_id: int) -> dict | None
```
**Returns**: The next menu_item in the student's rotation — the item from their approved set (intersection with canonical_menu_order) that was served least recently. Returns None if no approved set exists for this caterer.  
**Algorithm**:
1. Fetch current approved set for (enrolment, caterer) from `term_meal_preferences` where `superseded_at IS NULL`.
2. Fetch `canonical_menu_order` from `caterers`.
3. Filter canonical order to items in approved set.
4. Find the item in that filtered list with the oldest `order_lines.created_at` (or never served = highest priority).
5. Return that menu_item dict.  
**Build status**: stub

### `auto_pick_dietary_meal`
```python
def auto_pick_dietary_meal(enrolment_id: int, caterer_id: int) -> dict | None
```
**When**: Rotation pick failed dietary safety check. Last resort.  
**Returns**: Any active menu_item for this caterer that passes all the student's dietary tags. Returns None if no safe item exists (triggers urgent escalation in the agent).  
**Build status**: stub

### `item_is_safe_for_enrolment`
```python
def item_is_safe_for_enrolment(menu_item_id: int, enrolment_id: int) -> bool
```
**Returns**: True if the menu item passes all of the student's dietary restrictions.  
**Build status**: stub

---

## Order tools

### `check_weekly_moq`
```python
def check_weekly_moq(caterer_id: int, week_of: date) -> dict
```
**Returns**: `{total_items: int, moq_applicable: int | None, shortfall: int, shortfall_cents: int}`.  
`moq_applicable` is None if the caterer has no MOQ tier matching the variety count.  
**Algorithm**: Sum `order_lines` for all orders with this `caterer_id` in the week containing `week_of`. Look up the applicable MOQ tier from `caterers.moq_N_items` columns.  
**Build status**: stub

### `create_order`
```python
def create_order(
    session_slot_id: int,
    session_date: date,
    caterer_id: int,
    order_lines: list[dict],  # each: {enrolment_id, menu_item_id, source}
    moq_floor_applied: bool = False,
    moq_variance_cents: int = 0,
    total_cost_cents: int = 0
) -> int  # order_id
```
**When**: Step 8 of order composition.  
**Notes**: Idempotent — if a row already exists for (session_slot_id, session_date) raises an error rather than duplicating.  
**Build status**: stub

### `compose_order_email`
```python
def compose_order_email(order_id: int) -> str
```
**Returns**: Rendered email body string (uses template from `agent_context/email_templates/session_order.py`).  
Body includes: per-student meal list (student_name — meal_name), per-meal totals, predicted total cost with delivery fee, `[DEMO — Intended for: {caterer_email}]` header if in demo mode.  
**Build status**: stub

---

## Quality / feedback tools

### `get_feedback_for_session`
```python
def get_feedback_for_session(session_slot_id: int, session_date: date) -> dict
```
**Returns**: `{manager_rating: int | None, manager_comments: str | None, tutor_ratings: list[int | None], student_avg: float | None}`.  
**Build status**: stub

### `compute_rolling_mean`
```python
def compute_rolling_mean(caterer_id: int, weeks: int = 4) -> float | None
```
**Returns**: Unweighted mean of all filled feedback ratings (tutor + manager) for this caterer in the last `weeks` weeks. Returns None if fewer than 3 ratings exist (insufficient data).  
**Build status**: stub

### `get_feedback_since`
```python
def get_feedback_since(since_timestamp: datetime) -> list[dict]
```
**Returns**: All feedback rows submitted after `since_timestamp`, with `session_slot_id`, `session_date`, `caterer_id`, `source`, `rating` joined in.  
**Build status**: stub

---

## Caterer reach tools

### `caterers_within_range`
```python
def caterers_within_range(school_id: int, exclude_caterer_id: int | None = None) -> list[dict]
```
**Returns**: List of caterers where distance(school.postcode, caterer.home_postcode) ≤ caterer.max_delivery_km. Excludes `exclude_caterer_id` (typically the incumbent). Uses geopy or equivalent postcode-to-coordinate lookup.  
**Build status**: stub

### `project_weekly_cost`
```python
def project_weekly_cost(caterer_id: int, school_id: int) -> dict
```
**Returns**: `{cohort_size: int, per_meal_price_cents: int, delivery_fee_cents: int, moq_floor_cents: int | None, projected_total_cents: int}`.  
**Notes**: Cohort size uses current active enrolment count for the school. MOQ floor applied if weekly projected total falls below applicable tier.  
**Build status**: stub

---

## Weekly summary tools

### `generate_weekly_summary`
```python
def generate_weekly_summary(caterer_id: int, week_ending_date: date) -> dict
```
**Returns**: `{total_items: int, total_cost_cents: int, moq_floor_applied: bool, moq_variance_cents: int, gst_amount_cents: int, grand_total_cents: int, session_breakdown: list[dict]}`.  
**Notes**: Aggregates all orders for this caterer in the 7 days ending on `week_ending_date`. Applies GST according to `caterers.price_includes_gst` and `gst_rate_percent`.  
**Build status**: stub

### `compose_weekly_summary_email`
```python
def compose_weekly_summary_email(caterer_id: int, summary: dict) -> str
```
**Returns**: Rendered email body string.  
**Build status**: stub

---

## Inbound email tools

### `record_inbound_email`
```python
def record_inbound_email(
    gmail_message_id: str,
    received_at: datetime,
    from_address: str,
    subject: str | None,
    classification: str,
    related_absence_id: int | None = None,
    related_order_id: int | None = None,
    related_enrolment_id: int | None = None
) -> None
```
**When**: After processing each inbound message, to mark it as processed and prevent re-processing.  
**Build status**: stub

### `classify_inbound_email`
```python
def classify_inbound_email(email: dict) -> str
```
**Returns**: One of `'absence'`, `'caterer_order_confirmation'`, `'caterer_price_change_notification'`, `'parent_enrolment_response'`, `'unclassified'`.  
**Notes**: This tool calls Claude Haiku for classification reasoning. The agent uses this during inbound processing.  
**Build status**: stub

---

## Preferences tools

### `create_term_meal_preferences`
```python
def create_term_meal_preferences(
    enrolment_id: int,
    caterer_id: int,
    menu_item_ids: list[int],
    captured_by: Literal['parent', 'tutor', 'operator']
) -> int  # preference_id
```
**When**: Processing a parent enrolment response or tutor preference reset.  
**Notes**: Supersedes any existing non-superseded preference for the same (enrolment, caterer). Sets `superseded_at` on the old row before creating the new one.  
**Build status**: stub

### `compute_canonical_menu_order`
```python
def compute_canonical_menu_order(caterer_id: int, school_id: int) -> list[int]
```
**Returns**: Ordered list of menu_item_ids, most popular first.  
**Algorithm**: Count appearances of each menu_item_id across all non-superseded `term_meal_preference_items` for this caterer's school. Rank descending. Random tiebreak.  
**When**: Term start and on caterer change. Writes result to `caterers.canonical_menu_order`.  
**Build status**: stub

---

## HTML decision log

### `regenerate_decision_log`
```python
def regenerate_decision_log(output_path: str = "logs/decision_log.html") -> None
```
**When**: Last step of every run.  
**Notes**: Queries `agent_runs` + `agent_steps`, renders Jinja2 template. Groups by week. Sorts within each week: urgent first (red), notable (amber), informational (green), none (grey/collapsed). Includes summary counts per run ("3 urgent, 4 notable, 12 informational"). Writes static HTML file.  
**Build status**: stub
