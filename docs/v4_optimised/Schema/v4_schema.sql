-- =============================================================================
-- PADEA Operations Agent — V4 Database Schema (Supabase Postgres)
-- =============================================================================
--
-- V4 = V3 + post-review optimisations. V3 is preserved unchanged as the
-- historical record. The six V4 changes are:
--
--   V4-OPT-01  updated_at trigger function — timestamps now self-maintain.
--   V4-OPT-02  Three text-CHECK columns promoted to proper enum types:
--                  order_rotation_status, preference_capture_source,
--                  order_line_source.
--   V4-OPT-03  UNIQUE constraint on outbound_emails.gmail_message_id
--                  (replaces the V3 partial index; allows multiple NULLs).
--   V4-OPT-04  caterer_id denormalised onto feedback — rolling-mean hot path.
--   V4-OPT-05  gst_rate_percent snapshotted onto orders — preserves what GST
--                  rate was in effect at order-composition time.
--   V4-OPT-06  menu_items dietary boolean columns replaced with a shared
--                  menu_item_dietary_tags junction table, using the same
--                  dietary_tags vocabulary as enrolments. Tag descriptions
--                  updated from student-facing to neutral. Safety check at
--                  order composition becomes item.tags ⊇ student.tags.
--
-- This schema implements the ten locked V3 decisions (unchanged):
--   V3-FB-01  Feedback ecosystem
--   V3-CR-01  Caterer reach (distance-radius RFP targeting)
--   V3-OC-01  Order costing (popularity-ranked canonical order)
--   V3-PV-01  Preference capture + opt-out
--   V3-CM-01  Communications layer (real bidirectional Gmail)
--   V3-EL-01  Enrolment lifecycle (three-date model)
--   V3-OE-01  Observability (three-tier urgency)
--   V3-IL-01  Identity (tutors first-class, dual-role manager-tutor)
--   V3-MP-01  Zero operational margin
--   V3-AI-01  Per-session cadence + Supabase Postgres
--
-- Conventions:
--   - Snake_case for all tables and columns.
--   - All primary keys are bigserial (auto-incrementing bigint).
--   - All foreign keys are explicit, with on-delete behaviour documented.
--   - All money values stored in cents (integer), not dollars (float).
--   - All timestamps stored as timestamptz (UTC; rendered in operator's local).
--   - All dates stored as date (no time component).
--   - Postgres enums used where the domain is fixed and small.
--   - JSON columns used for variable-shape data (canonical_menu_order, tool I/O).
--   - Comments on every table and every non-obvious column.
--
-- Run order:
--   1. Trigger function (V4-OPT-01)
--   2. Enums (V3 original + three new V4-OPT-02 enums)
--   3. Core entity tables (schools, caterers, tutors, menu_items)
--   4. Enrolment + linking tables
--   5. Operational tables (session_slots, exclusions, absences)
--   6. Orders + order_lines + feedback
--   7. Preferences + requests + dietary tags
--   8. Communications (outbound_emails)
--   9. Observability (agent_runs, agent_steps)
--  10. Indexes
--
-- =============================================================================


-- =============================================================================
-- V4-OPT-01  UPDATED_AT TRIGGER FUNCTION
-- =============================================================================
-- A single shared function used by every table that carries an updated_at column.
-- Attached via per-table BEFORE UPDATE triggers defined immediately after each
-- CREATE TABLE statement.

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- ENUMS
-- =============================================================================

-- Email types — canonical list per V3-CM-01.
-- V2's `weekly_order` is not carried into V3; replaced by session_order +
-- weekly_consolidated_summary per V3-AI-01's per-session cadence.
CREATE TYPE email_type AS ENUM (
    'session_order',                 -- per-session, T-72hrs, binding
    'weekly_consolidated_summary',   -- Monday 3:30 PM per caterer, payment crystallisation
    'warning',                       -- decline-detection warning to incumbent caterer
    'rfp',                           -- request for proposal to candidate caterers
    'cancellation',                  -- cancellation notice to outgoing caterer
    'rfp_loser_courtesy',            -- "thanks, gone another direction" to RFP losers
    'parent_enrolment',              -- term-start parent email
    'parent_reminder',               -- chase reminder when parent hasn't responded
    'opt_back_in_request_to_parent', -- tutor-triggered, autonomous send
    'operator_notification',         -- system-to-operator escalation surfacing
    'other'
);

-- Outbound email status lifecycle per V3-CM-01.
-- Routine emails: drafted -> sending -> sent.
-- Commercial emails: drafted -> queued_for_approval -> approved -> sending -> sent.
CREATE TYPE email_status AS ENUM (
    'drafted',
    'queued_for_approval',
    'approved',
    'sending',
    'sent',
    'failed'
);

-- Agent step urgency tier per V3-OE-01.
-- `none` covers routine tool calls with no operator-facing weight.
CREATE TYPE step_urgency AS ENUM (
    'urgent',
    'notable',
    'informational',
    'none'
);

-- Feedback source — polymorphic per V3-FB-01.
-- Manager submissions attach to orders; tutor submissions attach to order_lines.
CREATE TYPE feedback_source AS ENUM (
    'tutor',
    'manager'
);

-- Inbound email classification per V3-CM-01.
-- Classified messages route to their domain tables; unclassified escalates.
CREATE TYPE inbound_classification AS ENUM (
    'absence',
    'caterer_order_confirmation',
    'caterer_price_change_notification',
    'parent_enrolment_response',
    'unclassified'
);

-- V4-OPT-02: order_rotation_status — replaces the free-text rotation_status column
-- on orders. Values confirmed from V3 column comment: 'normal', 'warning_active',
-- 'rfp_pending'.
CREATE TYPE order_rotation_status AS ENUM (
    'normal',
    'warning_active',
    'rfp_pending'
);

-- V4-OPT-02: preference_capture_source — replaces the text CHECK on
-- term_meal_preferences.captured_by. Values confirmed from V3 CHECK constraint:
-- ('parent', 'tutor', 'operator').
CREATE TYPE preference_capture_source AS ENUM (
    'parent',
    'tutor',
    'operator'
);

-- V4-OPT-02: order_line_source — replaces the text CHECK on order_lines.source.
-- Values confirmed from V3 CHECK constraint:
-- ('rotation', 'request', 'preview_week_operator', 'dietary_auto_pick').
CREATE TYPE order_line_source AS ENUM (
    'rotation',
    'request',
    'preview_week_operator',
    'dietary_auto_pick'
);


-- =============================================================================
-- CORE ENTITIES
-- =============================================================================

-- ---------------------------------------------------------------------------
-- schools — the locations Padea operates at.
-- V2 inherits; V3 adds `postcode` for V3-CR-01 distance-radius targeting.
-- ---------------------------------------------------------------------------
CREATE TABLE schools (
    id                  bigserial PRIMARY KEY,
    name                text NOT NULL,
    building            text,                       -- e.g. "Building A" — was on V2
    postcode            text NOT NULL,              -- V3-CR-01: required for distance calc
    current_caterer_id  bigint,                     -- FK set below after caterers exists
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE  schools IS 'Padea school locations. One row per school.';
COMMENT ON COLUMN schools.postcode IS 'V3-CR-01: used by caterers_within_range() distance query.';
COMMENT ON COLUMN schools.current_caterer_id IS 'Single caterer per school (Padea operational reality). FK to caterers.';

-- V4-OPT-01: auto-maintain updated_at
CREATE TRIGGER trg_schools_updated_at
    BEFORE UPDATE ON schools
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ---------------------------------------------------------------------------
-- caterers — the food suppliers.
-- V3-CR-01 adds home_postcode + max_delivery_km for RFP targeting.
-- V3-OC-01 adds canonical_menu_order (popularity-ranked snapshot).
-- ---------------------------------------------------------------------------
CREATE TABLE caterers (
    id                      bigserial PRIMARY KEY,
    name                    text NOT NULL,
    contact_email           text NOT NULL,
    contact_phone           text,
    home_postcode           text NOT NULL,              -- V3-CR-01
    max_delivery_km         integer NOT NULL DEFAULT 50, -- V3-CR-01: deliberately generous default
    delivery_fee_cents      integer NOT NULL DEFAULT 0,  -- V2; per-delivery flat fee
    price_includes_gst      boolean NOT NULL DEFAULT false,
    gst_rate_percent        numeric(4,2) NOT NULL DEFAULT 10.0,  -- AU GST = 10%
    -- MOQ tiers — V2 inherits the three columns. Per V3-AI-01 we explicitly
    -- chose NOT to promote these to a separate caterer_moq_rules table.
    moq_4_items             integer,                    -- nullable: not all caterers have all tiers
    moq_5_items             integer,
    moq_6_items             integer,
    -- V3-OC-01: popularity-ranked menu order, snapshot at term start + caterer change.
    -- Stored as a JSON array of menu_item ids in canonical sequence.
    -- Example: [12, 7, 19, 3, 22, 5]
    canonical_menu_order    jsonb,
    canonical_order_set_at  timestamptz,                -- when the snapshot was last computed
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE  caterers IS 'Catering suppliers. One row per caterer.';
COMMENT ON COLUMN caterers.max_delivery_km IS 'V3-CR-01: deliberately generous default (50km); we over-reach rather than miss caterers.';
COMMENT ON COLUMN caterers.canonical_menu_order IS 'V3-OC-01: JSON array of menu_item ids, ranked by popularity across all approved sets at the caterer''s school. Snapshot at term start and caterer change only.';

-- V4-OPT-01: auto-maintain updated_at
CREATE TRIGGER trg_caterers_updated_at
    BEFORE UPDATE ON caterers
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Backfill the FK on schools now that caterers exists.
ALTER TABLE schools
    ADD CONSTRAINT fk_schools_current_caterer
    FOREIGN KEY (current_caterer_id) REFERENCES caterers(id)
    ON DELETE SET NULL;


-- ---------------------------------------------------------------------------
-- menu_items — what each caterer offers.
-- V2 inherits. V3-OC-01: prices overwrite in place (no history table).
-- V4-OPT-06: V3 had 8 boolean columns (contains_pork, is_halal, etc.) for
-- dietary properties. These are removed here; dietary properties are now
-- carried via the menu_item_dietary_tags junction introduced below.
-- ---------------------------------------------------------------------------
CREATE TABLE menu_items (
    id              bigserial PRIMARY KEY,
    caterer_id      bigint NOT NULL REFERENCES caterers(id) ON DELETE CASCADE,
    name            text NOT NULL,
    description     text,
    price_cents     integer NOT NULL,           -- V3-OC-01: overwrite-in-place, no history
    active          boolean NOT NULL DEFAULT true,  -- V2: caterers retire items occasionally
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE  menu_items IS 'Per-caterer menu. Prices overwrite in place (V3-OC-01). V4-OPT-06: dietary properties via menu_item_dietary_tags junction (replaced V3 boolean columns).';
COMMENT ON COLUMN menu_items.price_cents IS 'V3-OC-01: current price. No effective-date history; the order row''s stored total preserves what was paid.';

-- V4-OPT-01: auto-maintain updated_at
CREATE TRIGGER trg_menu_items_updated_at
    BEFORE UPDATE ON menu_items
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ---------------------------------------------------------------------------
-- tutors — V3-IL-01 promotes from V2's denormalised manager_name on session_slots.
-- Required by V3-FB-01 for per-tutor feedback attribution.
-- ---------------------------------------------------------------------------
CREATE TABLE tutors (
    id                  bigserial PRIMARY KEY,
    name                text NOT NULL,
    email               text,
    mobile              text,
    employee_identifier text,                       -- optional: Padea's internal ID if any
    active              boolean NOT NULL DEFAULT true,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE tutors IS 'V3-IL-01: tutors as first-class entities. Required by V3-FB-01 for per-tutor feedback attribution. A "tutor" here also covers session managers (a person can be both via session_tutor_assignments flags).';

-- V4-OPT-01: auto-maintain updated_at
CREATE TRIGGER trg_tutors_updated_at
    BEFORE UPDATE ON tutors
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =============================================================================
-- DIETARY VOCABULARY (V3-FB-01)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- dietary_tags — extensible vocabulary replacing V2's JSON dietary_flags.
-- V3-AI-01: no severity field; every tag is safety-critical by default.
-- No updated_at column — tags are append-only in practice; deactivate via active=false.
-- ---------------------------------------------------------------------------
CREATE TABLE dietary_tags (
    id          bigserial PRIMARY KEY,
    name        text NOT NULL UNIQUE,           -- e.g. "no_pork", "halal", "vegetarian"
    label       text NOT NULL,                  -- human-facing, e.g. "No pork"
    description text,
    active      boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE dietary_tags IS 'V3-FB-01: controlled vocabulary for dietary restrictions. Extensible by operator. No severity field per V3-AI-01 — every tag treated as safety-critical.';

-- Seed the dietary tags used by both enrolments (requirements) and menu items
-- (satisfied properties). A tag on a student means "I need this"; the same tag on
-- an item means "I satisfy this." Safety check: item tags ⊇ student tags.
-- V4-OPT-06: descriptions updated from student-facing (e.g. 'Kid does not eat pork')
-- to neutral (e.g. 'Pork-free') so they read correctly on both students and items.
INSERT INTO dietary_tags (name, label, description) VALUES
    ('no_pork',         'No pork',         'Pork-free'),
    ('no_seafood',      'No seafood',       'Seafood/shellfish-free'),
    ('no_nuts',         'No nuts',          'Nut-free (treat as allergy — no severity distinction per V3-AI-01)'),
    ('no_dairy',        'No dairy',         'Dairy-free'),
    ('halal',           'Halal',            'Halal-certified'),
    ('vegetarian',      'Vegetarian',       'Meat-free'),
    ('vegan',           'Vegan',            'Free of all animal products'),
    ('gluten_free',     'Gluten free',      'Gluten-free'),
    ('mild_only',       'Mild only',        'Mild — no spicy ingredients');


-- =============================================================================
-- ENROLMENTS + DIETARY JUNCTION (V3-FB-01, V3-EL-01, V3-IL-01)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- enrolments — kid-at-school records.
-- V3-IL-01: students + parents denormalised here (no separate tables).
-- V3-EL-01: three lifecycle dates (original, current period start, end).
-- V3-PV-01: opt-out boolean carried forward from V2.
-- ---------------------------------------------------------------------------
CREATE TABLE enrolments (
    id                          bigserial PRIMARY KEY,
    school_id                   bigint NOT NULL REFERENCES schools(id) ON DELETE RESTRICT,

    -- Student identity (denormalised per V3-IL-01)
    student_name                text NOT NULL,              -- operator uses distinguishable names for same-name kids
    student_year_level          integer,                    -- nullable: some schools may not track year-level

    -- Parent contact (denormalised per V3-IL-01)
    parent_name                 text NOT NULL,
    parent_email                text NOT NULL,
    parent_phone                text,

    -- Lifecycle dates per V3-EL-01
    original_start_date         date NOT NULL,              -- never changes: first ever joined Padea
    current_period_start_date   date NOT NULL,              -- updated on return after departure
    current_period_end_date     date,                       -- null while active; set when kid leaves

    -- Catering opt-out per V3-PV-01 (default-opted-in carried from V2)
    opted_out_of_catering       boolean NOT NULL DEFAULT false,

    -- Free-text allergy note for restrictions outside the structured dietary_tags vocabulary.
    -- Non-null at term-start email time triggers an operator escalation.
    other_allergy_notes         text,

    created_at                  timestamptz NOT NULL DEFAULT now(),
    updated_at                  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE enrolments IS 'V3-IL-01: kid-at-school records with denormalised student + parent identity. V3-EL-01: three-date lifecycle (original/current/end). Active state derived from dates + opt-out flag.';
COMMENT ON COLUMN enrolments.original_start_date IS 'V3-EL-01: never changes after creation. Preserves "first ever joined Padea" for audit.';
COMMENT ON COLUMN enrolments.current_period_start_date IS 'V3-EL-01: updated when a kid returns after a departure.';
COMMENT ON COLUMN enrolments.current_period_end_date IS 'V3-EL-01: null while active. Set when kid leaves. Active state = (end_date IS NULL OR end_date > date_of_interest).';
COMMENT ON COLUMN enrolments.opted_out_of_catering IS 'V3-PV-01: parent-controlled flag. Default false (catering on). Tutor-led opt-back-in via V3-MP-01 checkbox.';
COMMENT ON COLUMN enrolments.other_allergy_notes IS 'Free-text allergy/restriction entered by parent that does not fit any structured dietary_tag. Non-null triggers an operator escalation at term-start email processing.';

-- V4-OPT-01: auto-maintain updated_at
CREATE TRIGGER trg_enrolments_updated_at
    BEFORE UPDATE ON enrolments
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- enrolment_dietary_tags — junction (V3-FB-01).
-- One row per (enrolment, dietary_tag).
-- ---------------------------------------------------------------------------
CREATE TABLE enrolment_dietary_tags (
    enrolment_id    bigint NOT NULL REFERENCES enrolments(id) ON DELETE CASCADE,
    dietary_tag_id  bigint NOT NULL REFERENCES dietary_tags(id) ON DELETE RESTRICT,
    captured_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (enrolment_id, dietary_tag_id)
);

COMMENT ON TABLE enrolment_dietary_tags IS 'V3-FB-01: junction between enrolments and dietary_tags. One row per (enrolment, tag).';


-- ---------------------------------------------------------------------------
-- menu_item_dietary_tags — V4-OPT-06: new junction table replacing V3's 8
-- boolean columns on menu_items. Uses the same dietary_tags vocabulary as
-- enrolment_dietary_tags so the safety check is a clean set operation:
-- item is safe for a student iff item.tags ⊇ student.tags.
-- ---------------------------------------------------------------------------
CREATE TABLE menu_item_dietary_tags (
    menu_item_id    bigint NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
    dietary_tag_id  bigint NOT NULL REFERENCES dietary_tags(id) ON DELETE RESTRICT,
    PRIMARY KEY (menu_item_id, dietary_tag_id)
);

COMMENT ON TABLE menu_item_dietary_tags IS 'V4-OPT-06: replaces 8 boolean dietary columns on menu_items. Same dietary_tags vocabulary as enrolment_dietary_tags. Safety rule: item tags ⊇ student tags (set containment, not boolean ANDs).';

CREATE INDEX idx_menu_item_dietary_tags_tag
    ON menu_item_dietary_tags (dietary_tag_id);


-- =============================================================================
-- SESSION OPERATIONS (V3-AI-01, V3-IL-01)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- session_slots — recurring (school, day-of-week) sessions.
-- V2 inherits but V3 drops manager_name and manager_phone (V3-IL-01 deprecation).
-- V3-AI-01: adds `room` for caterer-facing email completeness.
-- ---------------------------------------------------------------------------
CREATE TABLE session_slots (
    id                  bigserial PRIMARY KEY,
    school_id           bigint NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    day_of_week         integer NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),  -- 1=Mon ... 7=Sun
    start_time          time NOT NULL,           -- typically ~15:30
    dinner_time         time NOT NULL,           -- typically ~17:30
    end_time            time NOT NULL,           -- typically ~18:30
    room                text,                    -- V3-AI-01: e.g. "Building A, Room 12"
    active              boolean NOT NULL DEFAULT true,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (school_id, day_of_week)              -- one session per (school, day-of-week)
);

COMMENT ON TABLE session_slots IS 'V2: recurring sessions as (school, day-of-week) templates. V3-IL-01: manager_name/manager_phone columns dropped — manager identity now via session_tutor_assignments.';
COMMENT ON COLUMN session_slots.room IS 'V3-AI-01: per-(school, day-of-week) constant. Caterer emails include this for delivery directions.';

-- V4-OPT-01: auto-maintain updated_at
CREATE TRIGGER trg_session_slots_updated_at
    BEFORE UPDATE ON session_slots
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- session_tutor_assignments — V3-IL-01: who staffed which session, in what role.
-- Dual-role booleans (is_manager + is_tutor) handle all four combinations.
-- Per-session granularity supports per-date manager variation naturally.
-- ---------------------------------------------------------------------------
CREATE TABLE session_tutor_assignments (
    id              bigserial PRIMARY KEY,
    session_slot_id bigint NOT NULL REFERENCES session_slots(id) ON DELETE CASCADE,
    session_date    date NOT NULL,                       -- the specific date this assignment covers
    tutor_id        bigint NOT NULL REFERENCES tutors(id) ON DELETE RESTRICT,
    is_manager      boolean NOT NULL DEFAULT false,
    is_tutor        boolean NOT NULL DEFAULT false,
    assigned_at     timestamptz NOT NULL DEFAULT now(),
    CHECK (is_manager OR is_tutor),                      -- at least one role per assignment
    UNIQUE (session_slot_id, session_date, tutor_id)     -- one row per person per session
);

COMMENT ON TABLE session_tutor_assignments IS 'V3-IL-01: links tutors to specific session-date instances. Dual-role booleans (is_manager + is_tutor) handle all combinations including a manager who also tutors at the same session.';

-- ---------------------------------------------------------------------------
-- exclusions — V2 inherits.
-- V3-EL-01: school holidays handled as bulk full-school exclusions here.
-- ---------------------------------------------------------------------------
CREATE TABLE exclusions (
    id              bigserial PRIMARY KEY,
    school_id       bigint REFERENCES schools(id) ON DELETE CASCADE,  -- null = system-wide exclusion (rare)
    enrolment_id    bigint REFERENCES enrolments(id) ON DELETE CASCADE, -- null = full-school exclusion
    start_date      date NOT NULL,
    end_date        date NOT NULL,
    reason          text,                                              -- "school holiday", "exam week", etc.
    created_at      timestamptz NOT NULL DEFAULT now(),
    CHECK (start_date <= end_date),
    -- An exclusion must target either a school, an enrolment, or both.
    CHECK (school_id IS NOT NULL OR enrolment_id IS NOT NULL)
);

COMMENT ON TABLE exclusions IS 'V2: date-range exclusions from order composition. V3-EL-01: school holidays bulk-inserted here at term-end (one row per school per holiday week per day).';

-- ---------------------------------------------------------------------------
-- absences — V2 inherits.
-- V3-CM-01: adds source_email_message_id (Gmail) alongside V2's source_email_filename.
-- ---------------------------------------------------------------------------
CREATE TABLE absences (
    id                          bigserial PRIMARY KEY,
    enrolment_id                bigint NOT NULL REFERENCES enrolments(id) ON DELETE CASCADE,
    absence_date                date NOT NULL,
    received_at                 timestamptz NOT NULL DEFAULT now(),
    source_email_filename       text,                                  -- V2 legacy
    source_email_message_id     text,                                  -- V3-CM-01: Gmail message ID
    notes                       text,
    UNIQUE (enrolment_id, absence_date)                                -- idempotent: same absence twice = one row
);

COMMENT ON TABLE absences IS 'Parent-notified absences. V3-CM-01: source_email_message_id added alongside V2''s source_email_filename for Gmail traceability.';


-- =============================================================================
-- PREFERENCES + REQUESTS (V3-FB-01)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- term_meal_preferences — per-enrolment-per-caterer approved meal set.
-- Captured by parent at term start; reset by tutor at caterer change.
-- Supersession-aware: old sets archive when a new one is captured for the same caterer.
-- ---------------------------------------------------------------------------
CREATE TABLE term_meal_preferences (
    id              bigserial PRIMARY KEY,
    enrolment_id    bigint NOT NULL REFERENCES enrolments(id) ON DELETE CASCADE,
    caterer_id      bigint NOT NULL REFERENCES caterers(id) ON DELETE CASCADE,
    captured_at     timestamptz NOT NULL DEFAULT now(),
    -- V4-OPT-02: was text CHECK ('parent', 'tutor', 'operator'); now typed enum.
    captured_by     preference_capture_source NOT NULL,
    superseded_at   timestamptz,                                       -- null = current; set when replaced
    notes           text
);

COMMENT ON TABLE term_meal_preferences IS 'V3-FB-01: per-enrolment-per-caterer approved meal set. Captured by parent at term start (captured_by=''parent''). Reset by tutor at caterer change (captured_by=''tutor''). Supersession via superseded_at.';

-- ---------------------------------------------------------------------------
-- term_meal_preference_items — junction (V3-FB-01).
-- Which menu items are in this preference set.
-- ---------------------------------------------------------------------------
CREATE TABLE term_meal_preference_items (
    preference_id   bigint NOT NULL REFERENCES term_meal_preferences(id) ON DELETE CASCADE,
    menu_item_id    bigint NOT NULL REFERENCES menu_items(id) ON DELETE RESTRICT,
    PRIMARY KEY (preference_id, menu_item_id)
);

COMMENT ON TABLE term_meal_preference_items IS 'V3-FB-01: junction between a preference set and its approved menu items.';

-- ---------------------------------------------------------------------------
-- meal_requests — per-kid per-session one-off override (V3-FB-01).
-- Tutor-app populated; consumed at order composition; falls through to rotation if absent.
-- Drawn from full dietary-safe menu (NOT constrained to approved set).
-- ---------------------------------------------------------------------------
CREATE TABLE meal_requests (
    id              bigserial PRIMARY KEY,
    enrolment_id    bigint NOT NULL REFERENCES enrolments(id) ON DELETE CASCADE,
    session_slot_id bigint NOT NULL REFERENCES session_slots(id) ON DELETE CASCADE,
    session_date    date NOT NULL,                                     -- the specific session being targeted
    menu_item_id    bigint NOT NULL REFERENCES menu_items(id) ON DELETE RESTRICT,
    requested_at    timestamptz NOT NULL DEFAULT now(),
    consumed_at     timestamptz,                                       -- set when order composition uses it
    UNIQUE (enrolment_id, session_slot_id, session_date)               -- one request per kid per session
);

COMMENT ON TABLE meal_requests IS 'V3-FB-01: per-kid per-session meal request override. Filed via tutor app. Consumed by order composition (T-72hrs); falls through to canonical-order rotation if no request exists. Drawn from full dietary-safe menu, not just the kid''s approved set.';


-- =============================================================================
-- ORDERS + ORDER LINES (V3-FB-01, V3-OC-01, V3-AI-01)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- orders — per-session order to a caterer.
-- V2 had meal_assignments as JSON column; V3-FB-01 promotes that to order_lines table.
-- V3-MP-01: margin_meals_per_session and tutor_buffer_meals_per_session DROPPED.
-- V3-AI-01: per-session orders (one per caterer-session pair).
-- V4-OPT-02: rotation_status promoted from text to order_rotation_status enum.
-- V4-OPT-05: gst_rate_percent snapshotted at composition time.
-- ---------------------------------------------------------------------------
CREATE TABLE orders (
    id                      bigserial PRIMARY KEY,
    session_slot_id         bigint NOT NULL REFERENCES session_slots(id) ON DELETE RESTRICT,
    caterer_id              bigint NOT NULL REFERENCES caterers(id) ON DELETE RESTRICT,
    session_date            date NOT NULL,                             -- the session this order covers
    total_items             integer NOT NULL,                          -- count of meals ordered (no margin)
    total_cost_cents        integer NOT NULL,                          -- predicted total at order time
    -- V4-OPT-05: GST rate in effect at order-composition time. Snapshot so historical
    -- cost reports stay correct if the federal GST rate ever changes.
    gst_rate_percent        numeric(5,2) NOT NULL,
    moq_floor_applied       boolean NOT NULL DEFAULT false,            -- V3-OC-01: was MOQ floor paid?
    moq_variance_cents      integer NOT NULL DEFAULT 0,                -- amount paid above natural total due to MOQ
    composed_at             timestamptz NOT NULL DEFAULT now(),
    sent_at                 timestamptz,                               -- when order email actually sent
    is_preview_week         boolean NOT NULL DEFAULT false,            -- V3-FB-01: new-caterer preview week
    -- V4-OPT-02: was text (no CHECK constraint); now typed enum.
    rotation_status         order_rotation_status,
    UNIQUE (session_slot_id, session_date)                             -- one order per session per date
);

COMMENT ON TABLE orders IS 'V3-AI-01: per-session orders, sent T-72hrs from session. V3-MP-01: zero operational margin — total_items is the exact expected cohort. V3-OC-01: total_cost_cents is the predicted total at composition time.';
COMMENT ON COLUMN orders.total_items IS 'V3-MP-01: zero operational margin. Count of meals ordered = expected attendees - absences - opt-outs.';
COMMENT ON COLUMN orders.moq_floor_applied IS 'V3-OC-01: true if the week''s consolidated total fell below MOQ and the floor was paid.';
COMMENT ON COLUMN orders.gst_rate_percent IS 'V4-OPT-05: snapshot of caterers.gst_rate_percent at composition time. Preserves the correct rate for historical cost reporting if the federal GST rate ever changes.';

-- ---------------------------------------------------------------------------
-- order_lines — V3-FB-01 promotes from V2's meal_assignments JSON column.
-- One row per (order, kid, meal). Required for per-meal feedback attribution.
-- V4-OPT-02: source promoted from text CHECK to order_line_source enum.
-- ---------------------------------------------------------------------------
CREATE TABLE order_lines (
    id              bigserial PRIMARY KEY,
    order_id        bigint NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    enrolment_id    bigint NOT NULL REFERENCES enrolments(id) ON DELETE RESTRICT,
    menu_item_id    bigint NOT NULL REFERENCES menu_items(id) ON DELETE RESTRICT,
    -- V4-OPT-02: was text CHECK ('rotation', 'request', ...); now typed enum.
    source          order_line_source NOT NULL,
    UNIQUE (order_id, enrolment_id)                                    -- one meal per kid per order
);

COMMENT ON TABLE order_lines IS 'V3-FB-01: per-meal-per-kid rows promoted from V2''s meal_assignments JSON. Required so feedback (V3-FB-01) can attach to specific (kid, meal) combinations. Source field tracks why each kid got each meal.';


-- =============================================================================
-- FEEDBACK (V3-FB-01)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- feedback — polymorphic per V3-FB-01.
-- source='tutor': scoped to order_line (per-kid post-dinner rating).
-- source='manager': scoped to order (session-wide score + checklist + meals_left + comments).
-- Nullable rating expresses "tutor/manager didn't fill in" (does not feed mean).
-- V4-OPT-04: caterer_id denormalised here for rolling-mean query performance.
-- ---------------------------------------------------------------------------
CREATE TABLE feedback (
    id                      bigserial PRIMARY KEY,
    source                  feedback_source NOT NULL,

    -- Tutor feedback attaches to order_line; manager feedback attaches to order.
    -- Exactly one of these is set per row.
    order_line_id           bigint REFERENCES order_lines(id) ON DELETE CASCADE,
    order_id                bigint REFERENCES orders(id) ON DELETE CASCADE,

    tutor_id                bigint REFERENCES tutors(id) ON DELETE RESTRICT,  -- who submitted

    -- V4-OPT-04: denormalised caterer_id for rolling-mean hot path.
    -- Intentionally redundant: the caterer for a given order never changes retroactively,
    -- so this column can never drift out of sync after initial INSERT. The benefit is
    -- significant: the rolling-mean query goes from
    --   feedback -> order_lines -> orders -> caterer_id  (2 joins)
    -- to a direct filter on feedback.caterer_id  (0 joins).
    caterer_id              bigint NOT NULL REFERENCES caterers(id) ON DELETE RESTRICT,

    rating                  integer CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),  -- nullable + bounded
    comment                 text,

    -- Manager-only fields (null for tutor submissions)
    -- Checklist: five boolean questions covering the session delivery quality.
    food_on_time                boolean,                                           -- arrived on time?
    correct_count_received      boolean,                                           -- correct number of meals?
    correct_dietary_delivered   boolean,                                           -- dietary meals correct?
    food_temperature_ok         boolean,                                           -- food at right temperature?
    visibly_wrong               boolean,                                           -- packaging intact / nothing wrong?
    meals_left                  integer,
    kids_who_didnt_eat          text,                                              -- free-text names

    submitted_at            timestamptz NOT NULL DEFAULT now(),

    -- Enforce polymorphism: exactly one of order_line_id or order_id must be set.
    CHECK ((source = 'tutor' AND order_line_id IS NOT NULL AND order_id IS NULL)
        OR (source = 'manager' AND order_id IS NOT NULL AND order_line_id IS NULL))
);

COMMENT ON TABLE feedback IS 'V3-FB-01: polymorphic feedback. Tutor source attaches to order_line for per-kid scoring. Manager source attaches to order for session-level scoring + checklist + meals-left + names. Null rating = ''did not fill in'' and does not feed the rolling mean.';
COMMENT ON COLUMN feedback.rating IS 'V3-FB-01: 1-5 enum constrained at this DB layer (enforced 1-5). Null when rater didn''t fill in — not folded into rolling mean.';
COMMENT ON COLUMN feedback.caterer_id IS 'V4-OPT-04: intentionally denormalised. Caterer for a given order never changes retroactively, so this column is always consistent. Allows the rolling-mean query to filter directly on feedback without joining through order_lines -> orders.';
COMMENT ON COLUMN feedback.correct_count_received IS 'Manager checklist: did the caterer deliver the correct number of meals?';
COMMENT ON COLUMN feedback.correct_dietary_delivered IS 'Manager checklist: were the correct dietary-safe meals present for all restricted students?';
COMMENT ON COLUMN feedback.food_temperature_ok IS 'Manager checklist: was the food delivered at an appropriate temperature (hot food hot)?';

-- ---------------------------------------------------------------------------
-- opt_back_in_requests — V3-MP-01: tutor checkbox tick history.
-- Send-once tracking: one email per kid per opt-out period.
-- ---------------------------------------------------------------------------
CREATE TABLE opt_back_in_requests (
    id                  bigserial PRIMARY KEY,
    enrolment_id        bigint NOT NULL REFERENCES enrolments(id) ON DELETE CASCADE,
    session_slot_id     bigint NOT NULL REFERENCES session_slots(id) ON DELETE RESTRICT,
    session_date        date NOT NULL,
    submitted_by_tutor  bigint REFERENCES tutors(id) ON DELETE SET NULL,
    submitted_at        timestamptz NOT NULL DEFAULT now(),
    email_sent_at       timestamptz,                                           -- null = no email fired yet
    parent_resolved_at  timestamptz                                            -- null = parent hasn't responded
);

COMMENT ON TABLE opt_back_in_requests IS 'V3-MP-01: tutor app opt-back-in checkbox ticks. Send-once tracking via email_sent_at — first tick per opt-out period fires email, subsequent ticks within the same opt-out period record but do not re-send.';


-- =============================================================================
-- COMMUNICATIONS (V3-CM-01)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- outbound_emails — V3-CM-01 first-class audit table.
-- Every system-sent email lives here regardless of type or status.
-- V4-OPT-03: gmail_message_id now has a UNIQUE constraint (multiple NULLs allowed).
-- ---------------------------------------------------------------------------
CREATE TABLE outbound_emails (
    id                          bigserial PRIMARY KEY,
    email_type                  email_type NOT NULL,
    status                      email_status NOT NULL DEFAULT 'drafted',
    intended_to_address         text NOT NULL,                                 -- where it would go in production
    intended_cc_addresses       jsonb,                                         -- array of strings
    subject                     text NOT NULL,
    rendered_body               text NOT NULL,
    composed_at                 timestamptz NOT NULL DEFAULT now(),
    queued_for_approval_at      timestamptz,
    approved_at                 timestamptz,
    approved_by                 text,                                          -- operator identifier
    sent_at                     timestamptz,
    failed_at                   timestamptz,
    failure_reason              text,
    -- V4-OPT-03: UNIQUE constraint replaces V3's partial index.
    -- Postgres allows multiple NULLs in unique constraints, so unsent emails
    -- (gmail_message_id IS NULL) do not conflict with each other.
    gmail_message_id            text UNIQUE,

    -- Optional links back into the system for audit traceability.
    related_run_id              bigint,                                        -- FK set after agent_runs exists
    related_step_id             bigint,                                        -- FK set after agent_steps exists
    related_order_id            bigint REFERENCES orders(id) ON DELETE SET NULL,
    related_caterer_id          bigint REFERENCES caterers(id) ON DELETE SET NULL,
    related_enrolment_id        bigint REFERENCES enrolments(id) ON DELETE SET NULL
);

COMMENT ON TABLE outbound_emails IS 'V3-CM-01: every system-sent email. Status lifecycle: drafted -> (queued_for_approval -> approved ->) sending -> sent. Commercial-relationship emails (warning, rfp, cancellation, rfp_loser_courtesy) go through the queued_for_approval path; routine emails skip to sending. Failed sends transition to failed with failure_reason captured.';
COMMENT ON COLUMN outbound_emails.intended_to_address IS 'V3-CM-01: the production recipient. Demo mode rewrites the actual send to a dev address while preserving this field as the intended recipient.';
COMMENT ON COLUMN outbound_emails.gmail_message_id IS 'V4-OPT-03: UNIQUE constraint (was a partial index in V3). Postgres allows multiple NULLs, so unsent rows with NULL gmail_message_id do not conflict.';

-- ---------------------------------------------------------------------------
-- inbound_email_records — V3-CM-01 lightweight dedup table.
-- We deliberately do NOT have a general inbound_emails table; classifications
-- flow into their domain tables (absences, etc.). This minimal table just
-- prevents double-processing across closely-spaced runs.
-- ---------------------------------------------------------------------------
CREATE TABLE inbound_email_records (
    gmail_message_id    text PRIMARY KEY,                                      -- one row per Gmail message
    received_at         timestamptz NOT NULL,
    from_address        text NOT NULL,
    subject             text,
    classified_as       inbound_classification NOT NULL,
    classified_at       timestamptz NOT NULL DEFAULT now(),
    -- Links to whichever domain row was created from this inbound (if any).
    related_absence_id      bigint REFERENCES absences(id) ON DELETE SET NULL,
    related_order_id        bigint REFERENCES orders(id) ON DELETE SET NULL,
    related_enrolment_id    bigint REFERENCES enrolments(id) ON DELETE SET NULL
);

COMMENT ON TABLE inbound_email_records IS 'V3-CM-01: minimal dedup table keyed on gmail_message_id. Prevents double-processing across closely-spaced runs. Classified messages also create rows in their respective domain tables; unclassified messages stay here + create an escalation in agent_steps.';


-- =============================================================================
-- OBSERVABILITY (V3-OE-01)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- agent_runs — V2 inherits. One row per agent invocation.
-- V3-AI-01: under per-session cadence, ~5-7 rows per week.
-- ---------------------------------------------------------------------------
CREATE TABLE agent_runs (
    id                  bigserial PRIMARY KEY,
    started_at          timestamptz NOT NULL DEFAULT now(),
    completed_at        timestamptz,
    trigger_reason      text NOT NULL,                                         -- e.g. 'session_order_t72', 'monday_summary'
    notes               text
);

COMMENT ON TABLE agent_runs IS 'V2: one row per agent invocation. V3-AI-01: ~5-7 invocations per week under per-session cadence (vs 1/week under V2''s Thursday omnibus).';

-- ---------------------------------------------------------------------------
-- agent_steps — V2 inherits. One row per step within a run.
-- V3-OE-01: severity (free text) replaced with urgency (enum: urgent/notable/informational/none).
-- ---------------------------------------------------------------------------
CREATE TABLE agent_steps (
    id                  bigserial PRIMARY KEY,
    run_id              bigint NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    step_index          integer NOT NULL,
    tool_name           text,
    tool_input          jsonb,
    tool_output_full    jsonb,
    reasoning           text,
    urgency             step_urgency NOT NULL DEFAULT 'none',                  -- V3-OE-01
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, step_index)
);

COMMENT ON TABLE agent_steps IS 'V2: per-step record within an agent_run. V3-OE-01: severity text replaced with urgency enum (urgent/notable/informational/none). Decision log renderer sorts by (urgency rank, step_index) and colour-codes.';
COMMENT ON COLUMN agent_steps.urgency IS 'V3-OE-01: three-tier urgency. Urgent = gating something. Notable = pattern worth investigating. Informational = audit trail. None = routine tool call with no operator-facing weight.';

-- Backfill outbound_emails FKs now that agent_runs and agent_steps exist.
ALTER TABLE outbound_emails
    ADD CONSTRAINT fk_outbound_emails_run
    FOREIGN KEY (related_run_id) REFERENCES agent_runs(id) ON DELETE SET NULL;
ALTER TABLE outbound_emails
    ADD CONSTRAINT fk_outbound_emails_step
    FOREIGN KEY (related_step_id) REFERENCES agent_steps(id) ON DELETE SET NULL;


-- =============================================================================
-- INDEXES
-- =============================================================================
-- Indexes for the queries V4's tools and reports run repeatedly.
-- Postgres auto-indexes primary keys and unique constraints — we add others below.

-- Enrolments: date-parameterised queries (V3-EL-01) hit these constantly.
CREATE INDEX idx_enrolments_school_dates
    ON enrolments (school_id, current_period_start_date, current_period_end_date);
CREATE INDEX idx_enrolments_school_active
    ON enrolments (school_id) WHERE current_period_end_date IS NULL;

-- Absences: order composition queries by (enrolment, date).
CREATE INDEX idx_absences_enrolment_date
    ON absences (enrolment_id, absence_date);

-- Exclusions: order composition queries by (school, date range).
CREATE INDEX idx_exclusions_school_dates
    ON exclusions (school_id, start_date, end_date);
CREATE INDEX idx_exclusions_enrolment_dates
    ON exclusions (enrolment_id, start_date, end_date) WHERE enrolment_id IS NOT NULL;

-- Orders: lookup by session + date for re-composition idempotency.
CREATE INDEX idx_orders_session_date
    ON orders (session_slot_id, session_date);
CREATE INDEX idx_orders_caterer_date
    ON orders (caterer_id, session_date);

-- Order lines: feedback joins through these.
CREATE INDEX idx_order_lines_enrolment
    ON order_lines (enrolment_id);

-- Feedback: rolling-mean queries by caterer + submitted_at.
-- V4-OPT-04: caterer_id is now on feedback directly — this index replaces the
-- V3 multi-join path (feedback -> order_lines -> orders -> caterer_id).
CREATE INDEX idx_feedback_caterer_date
    ON feedback (caterer_id, submitted_at);
CREATE INDEX idx_feedback_submitted_at
    ON feedback (submitted_at);
CREATE INDEX idx_feedback_order
    ON feedback (order_id) WHERE order_id IS NOT NULL;
CREATE INDEX idx_feedback_order_line
    ON feedback (order_line_id) WHERE order_line_id IS NOT NULL;

-- Meal requests: order composition checks for an unconsumed request per (kid, session, date).
CREATE INDEX idx_meal_requests_lookup
    ON meal_requests (enrolment_id, session_slot_id, session_date) WHERE consumed_at IS NULL;

-- Outbound emails: status queue queries + Gmail message ID lookups.
-- Note: the V3 partial index on gmail_message_id is replaced by the UNIQUE constraint
-- defined inline on the column (V4-OPT-03). The status + type/recipient indexes remain.
CREATE INDEX idx_outbound_emails_status
    ON outbound_emails (status);
CREATE INDEX idx_outbound_emails_type_recipient
    ON outbound_emails (email_type, intended_to_address);

-- Agent steps: decision log queries by run + urgency for the three-tier sort.
CREATE INDEX idx_agent_steps_run_urgency
    ON agent_steps (run_id, urgency, step_index);

-- Session tutor assignments: fast lookup by (session, date) for order composition + feedback.
CREATE INDEX idx_session_tutor_assignments_lookup
    ON session_tutor_assignments (session_slot_id, session_date);

-- Term meal preferences: fast lookup of the current set per (enrolment, caterer).
CREATE INDEX idx_term_meal_preferences_current
    ON term_meal_preferences (enrolment_id, caterer_id) WHERE superseded_at IS NULL;

-- Enrolment dietary tags: fast filter at order composition.
CREATE INDEX idx_enrolment_dietary_tags_enrolment
    ON enrolment_dietary_tags (enrolment_id);

-- Opt-back-in requests: send-once check per (enrolment, opt-out period).
CREATE INDEX idx_opt_back_in_pending_email
    ON opt_back_in_requests (enrolment_id, email_sent_at);


-- =============================================================================
-- HELPFUL VIEWS (optional but useful for the operator surfaces)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- v_active_enrolments — derived active state per V3-EL-01.
-- Convenience view; tools should still pass an explicit date parameter when
-- composing historical orders, but for the weekly report this view gives
-- "currently active" without recomputing the date logic in every query.
-- ---------------------------------------------------------------------------
CREATE VIEW v_active_enrolments AS
    SELECT e.*
    FROM enrolments e
    WHERE e.current_period_end_date IS NULL
       OR e.current_period_end_date > CURRENT_DATE;

COMMENT ON VIEW v_active_enrolments IS 'V3-EL-01: convenience view for "currently active" enrolments. For historical queries (incident investigation, past-order recomposition), use the explicit date-parameterised query pattern instead.';

-- ---------------------------------------------------------------------------
-- v_current_term_preferences — the non-superseded preference set per (enrolment, caterer).
-- ---------------------------------------------------------------------------
CREATE VIEW v_current_term_preferences AS
    SELECT tmp.*
    FROM term_meal_preferences tmp
    WHERE tmp.superseded_at IS NULL;

COMMENT ON VIEW v_current_term_preferences IS 'V3-FB-01: current (non-superseded) preference set per (enrolment, caterer). Old sets archive when a new one is captured for the same caterer.';


-- =============================================================================
-- END OF V4 SCHEMA
-- =============================================================================
-- Roughly 25 tables (incl. junctions) + 2 views + 8 enums + 17 indexes.
-- V4 adds: 1 trigger function + 6 table triggers, 3 new enums, 1 UNIQUE constraint
-- (outbound_emails.gmail_message_id), 1 denormalised FK (feedback.caterer_id),
-- 1 snapshot column (orders.gst_rate_percent), 1 new index (idx_feedback_caterer_date),
-- 1 new junction table (menu_item_dietary_tags) replacing 8 boolean columns on
-- menu_items, neutral dietary_tags seed descriptions.
-- =============================================================================
