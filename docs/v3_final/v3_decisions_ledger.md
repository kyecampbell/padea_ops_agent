# PADEA Operations Agent — V3 Reinstatements Ledger

This document carries the ten V3 add-back decisions in their canonical form. All amendments from later decisions have been integrated into their parent blocks; cross-references have been reconciled; the document reads consistently end-to-end.

Companion documents: cuts_v1_to_v2.md (master cuts ledger), summary_v2.md (V2 baseline), schema_v2.md (V2 schema), requirements_v1.md, assumptions.md, data_observations.md, v3_edge_cases.md, memo_notes.md.

## Group 3 — Feedback Ecosystem

### V3-FB-01: Feedback ecosystem (manager + tutor + rolling quality picture)

**Decision summary.** Add back a multi-source feedback loop covering both ends of the meal — preferences in, ratings out — using channels staffed by people Padea pays (tutors and session managers) rather than channels depending on parents or students submitting voluntarily on a weekly cadence. The full loop closes V2's open-ended order workflow without depending on data sources that have historically been unreliable.

#### The operational scenario

**Term start.** Parent receives an email with two tasks. First, pick dietary attributes for the kid from an extensible list (no pork, no seafood, halal, vegetarian, mild not spicy, etc.). Second, from the current caterer's menu — already filtered by those dietary tags — tick the meals the kid would be happy to be served. Framing is transparent: "select the meals we'll cycle between for your student — could be any number, even all of them." A kid who only likes two ticks two; a kid with broad taste ticks ten. The dietary profile is durable across caterer changes; the approved meal set is tied to the current caterer. This is the only parent ask for the term under normal operation.

**Mid-term enrolment is handled differently — see V3-PV-01.** No system-generated parent email fires for mid-term joins; the operator captures dietary tags and approved meal set directly via phone or email exchange with the parent. The kid enters the system with full preference data already in place. The auto-email term-start flow applies only to enrolments active at term start.

**Edge — parent approves zero meals.** The system can't pick anything if nothing is approved. Escalates to the operator; manual conversation with parent follows.

**Each operational week.** The system orders one meal per kid from their approved set, picking least-recently-served so the same meal doesn't recur weeks running by chance. Dietary kids get a dietary-compatible meal auto-chosen. If a kid has a meal request filed via the tutor app (see below) for the upcoming week, that request overrides the rotation for that kid only — they get the meal they asked for. The order cadence is per-session: each caterer-session pair gets its own order email at exactly 72 hours before the session (see V3-AI-01 for the full cadence model). V2's underlying order workflow concepts (exclusions, absences, MOQ, escalations) carry forward into the per-session cadence.

**After dinner at every session — tutor input.** Tutor opens the app. Each kid in their group has a new post-dinner box. The meal the kid was served is pre-loaded. Tutor enters a 1–5 score the kid verbalised — after the tutor probed it rather than accepting the first number ("really a 5? or a 4?"). Free-text comment captures plate behaviour, swaps, anything notable. Tutor is filling other session notes anyway; this is one extra box per kid.

**Request mechanism on the same box.** Tutor app exposes a "request a meal for next week" picker per kid. The picker shows any meal on the current caterer's menu the kid can dietary-safely eat — not constrained to the parent-approved cycling set. A kid who tells their tutor "my mum ticked five things but I'd love to try the chilli chicken next week" can have that request filed and the system will order it for them. The request is a one-off override for the next week's order only; it does not change the kid's durable approved set. Filed after the next session's T-72hrs order has gone, the request defers naturally to the session after that.

**Session manager fills out their report alongside.** Already richer than the tutor's report. Now includes a session-level 1–5 food score, a structured checklist (food on time, anything visibly wrong), free-text comments, count of meals left, and names of specific kids who didn't eat. In-app reminder anchors the scale: 5 = perfect, 3 = satisfactory. Manager view is the cross-check on tutor-collected data.

**Edge — tutor doesn't fill in the post-dinner box.** System assumes nothing. The kid's rotation continues from preferences as normal; that session's tutor rating for that kid is recorded as missing, not zero, and is not folded into the rolling mean. Manager's session-level rating still feeds the mean if filled. Repeated missing tutor data on a tutor or session is itself a soft signal the operator can spot in the weekly report.

**Data flows into a per-caterer rolling picture.** Unweighted 4-week mean of all *filled* ratings (tutor + manager combined) per caterer. Stored, queryable, surfaced in the decision log on every run. Comment text is stored but not algorithmically used in V3 — substrate for future versions.

**Two surfaces where this data lives.** The decision log gets a "current quality picture" panel showing recent ratings, rolling mean, and concerning patterns. A weekly report regenerates alongside the decision log: cross-school visual view showing every caterer's trend, rolling mean, and recent decline signals. Operator reads the weekly report Friday over coffee for slow-drift awareness; decision log handles real-time per-incident attention.

**Three single-week auto-escalations.**

1. Manager 1 or 2 on any session → operator reviews. Single-session signal that something went badly wrong.
2. Student-average 1 or 2 on any session → same treatment. Lets a session where the tutors all scored low get attention even if the manager didn't flag it.
3. Tutor 1s as a pattern → when 1s exceed a configurable percentage of total tutor scores in a rolling window, escalation fires. Single tutor 1s feed the average but don't escalate individually (avoids per-kid alert fatigue). Manager is the per-session escalation channel because they have whole-session context.

Extreme scores stay in the rolling average — they're real data; escalation is parallel awareness, not a replacement.

**Sustained decline → rotation chain over several weeks.** When the 4-week rolling mean drops materially below the prior 12-week mean AND below an absolute floor, the system fires a decline escalation. Drafts a polite warning email to the incumbent caterer — names the drop, explains what will happen if it doesn't improve. Sent only after operator approves with one click.

If the operator judges that the score hasn't recovered (manual call, no auto-trigger), they ask the system to fire an RFP. System drafts a competitive enquiry to all caterers capable of serving that school on that day: "seeking a replacement caterer for [school/day], starting [date ~2 weeks out]. Out of those who agree, we'll pick." Operator approves before send. RFP framing creates implicit pricing pressure without explicit negotiation.

Responses come in. Operator picks. System drafts the cancellation email to the incumbent ("two weeks remaining on current arrangement, thank you for service") — operator approves and sends. Two weeks of incumbent service continue while the new caterer is onboarded.

**New caterer arrives — preview week.** Week 1 with a new caterer is unassigned — operator manually composes that week's order based on what they assume kids will want, mirroring pre-system operation. Whole week's order is flagged as an escalation so the operator knows to act. Dietary kids get a dietary-compatible meal auto-chosen even in the preview week.

During or after that first week, tutors reset each kid's approved meal set entirely by reading the new caterer's options to them on the app — informed by what kids saw, ate, and discussed during the preview week. The set isn't a fixed number — it's whichever meals the kid would actually be happy with. Old approved sets stay archived in case the school ever reverts. Restricted-diet kids accept the limited set the new caterer offers. Parent involvement on caterer-change is zero by design; the tutor-led reset is the standing process.

From week 2, the standard "least-recently-served from approved set" rotation resumes, plus the per-week request override mechanism (request picker continues to draw from the full dietary-safe menu, not just the kid's approved set).

**Edge — zero or one RFP responses.** Zero: system escalates, suggests the operator find another caterer manually or extend the RFP. Cancellation email has not yet been sent, so no commercial damage. One: operator decides whether to accept or stay with incumbent; "competitive" framing breaks but process completes.

**End of term.** No food-specific survey. Existing tutor-performance survey could absorb a food question if ever wanted, but not in V3.

#### Structured fields

1. **Feature/table/system:** Multi-source feedback ecosystem — parent preference capture (dietary tags + variable-size approved meal set), tutor per-kid post-dinner scoring, tutor-mediated per-week meal requests (drawing from full dietary-safe menu, not just approved set), tutor-led preference reset on caterer change, manager session-level scoring, rolling per-caterer quality score, decline detection, rotation chain (warning → RFP → cancellation), weekly cross-school report.
2. **V2 status:** Entirely absent. V2 collects no feedback of any kind, has no quality scoring, has no rotation mechanism, has no request mechanism, has no preference-reset workflow. V2 keeps per-student `acceptable_menu_item_ids` as a JSON column but cut weekly selection, request mechanism, and variety tracking.
3. **Requirement supported:** Quality maintained over time (brief's #2 named problem); student meal satisfaction (brief's #1 named problem); dietary safety floor; reducing coordinator bottleneck; visible operation / auditability.
4. **Value score:** 5/5. Closes the brief's two most-cited operational complaints. Without this group V3 has no signal on food quality and no mechanism to act when it declines. The request mechanism and tutor-led preference reset specifically address the failure modes where parent-captured prefs don't reflect what the kid actually wants and where parent burden across caterer changes would otherwise compound.
5. **Complexity score:** 4/5. Multiple new tables, multi-week rotation chain with several drafted-and-approved email types, two new app surfaces (tutor + manager input boxes), tutor-app per-week request picker, tutor-led preference-reset workflow, per-caterer rolling math, configurable thresholds. Drags in tutors as modelled entities, per-meal granularity, outbound email audit, dietary tag structure.
6. **Bugs / fixability / onboarding risks:** Tutor / manager training is non-trivial — staff must understand the scale anchoring (5 = perfect, 3 = satisfactory) and the probing norm ("really a 5?"). Tutors must understand the request-vs-preference distinction (one-off override vs. durable set) and must lead the preference-reset workflow on caterer-change weeks. Risk of rater drift without normalisation (accepted, V4 build candidate). Risk of LLM tone misfire on warning emails (mitigated by operator approval). Risk of poor signal on first 2–3 weeks of a new caterer until rolling mean stabilises. Preview-week operator workload is real but bounded. Risk of "request gaming" where a kid asks for the same meal every week (treated as honest signal — feeds the V4 algorithmic preference-adjustment candidate).
7. **Decision:** **ADD BACK, SIMPLIFIED.** All proposed cross-rater analytics, normalisation, timing decay, comment-text extraction, end-of-term survey, autonomous warning send, autonomous RFP fire, and request-pattern algorithmic action are explicitly DEFERRED to V4. Multi-source data collection, unweighted rolling math, tutor-mediated per-week request override, and tutor-led preference-reset on caterer change committed for V3.
8. **Schema impact (sketch — formalise later):**
   - New entity: tutors (required to attribute per-kid scoring).
   - New entity: session_tutor_assignments (which tutor saw which kids at which session).
   - Promote `meal_assignments` JSON → `order_lines` proper table (per-meal-per-kid rows so feedback can attach).
   - New entity: feedback (polymorphic: source = tutor / manager, scoped to order_line for tutor, scoped to order for manager). Nullable rating to express "tutor didn't fill in."
   - New entity: dietary_tags (extensible vocabulary — replaces JSON `dietary_flags`).
   - New entity: enrolment_dietary_tags (junction).
   - New entity: term_meal_preferences (per-enrolment-per-caterer approved set, variable size, supersession-aware so old sets archive on caterer swap; captured by parent at term start / new enrolment, and re-captured by tutor at caterer change).
   - New entity: meal_requests (per-kid per-week override; populated by tutor app from full dietary-safe menu; consumed at order composition; falls through to rotation if absent).
   - No `caterer_school_capabilities` table — replaced by distance-radius targeting in V3-CR-01.
   - Extend orders: rotation-escalation status, preview-week flag.
   - Extend caterers: any fields needed for RFP-eligible enumeration.
   - Promote outbound_emails to first-class audit table (warning, RFP, cancellation, weekly order — all logged with status, draft-vs-sent, operator approver).
   - Two new operator surfaces: decision-log "current quality picture" panel, weekly cross-school report (HTML, regenerated alongside decision log).
9. **Agent logic impact:**
   - Order composition: for each kid, check meal_requests for the target week first; if absent, query least-recently-served from term_meal_preferences. Auto-pick dietary-compatible meal for restricted kids whether requested or rotated.
   - Post-run: query feedback for the week just elapsed (excluding null tutor scores), compute per-caterer rolling means, evaluate single-week escalation conditions (manager 1–2, student-avg 1–2, tutor-1-pattern), evaluate sustained-decline condition (4w mean drop vs 12w prior + absolute floor).
   - On decline detection: draft warning email, queue for operator approval.
   - On operator RFP request: enumerate capable caterers for that school/day, draft competitive enquiry to all, queue for approval.
   - On operator caterer selection: draft incumbent cancellation email, queue for approval. Mark new caterer's first week as preview/unassigned.
   - On preview-week order composition: skip auto-matching, flag whole-week order as escalation, allow operator manual composition.
   - On post-preview-week: tutor app exposes preference-reset workflow per kid; tutor captures new approved set; system stores new prefs and archives old ones. No fixed cardinality.
   - Tutor-app request picker queries menu_items filtered by enrolment_dietary_tags; *not* filtered by term_meal_preferences.
   - Weekly report generation: cross-school visual of all caterer rolling means, trends, recent escalations, and (memo flag) request-pattern density per kid as a soft signal.
10. **Notes for V4 optimisation:**
    - Per-rater baseline normalisation (build trigger: ~30+ ratings per rater stable).
    - Submission-timing decay weighting.
    - Cross-rater divergence detection (tutor-vs-manager systematic drift).
    - LLM extraction of structured signals from comment text (taste / portion / temperature / freshness).
    - Algorithmic action on plate-behaviour patterns (auto-drop items kids consistently leave).
    - Algorithmic action on request patterns (kid requests X four weeks running → propose adding X to standing prefs).
    - End-of-term meal-ranking survey (recall bias deferred; existing tutor survey could absorb).
    - Per-rater "extreme score explanation" prompts on tutor app.
    - Auto-send warning email without operator approval (deferred: commercial-relationship risk > 30s saving).
    - Auto-fire RFP after warning-window expiry (deferred: rotation-stakes decisions stay human-initiated).
    - Caterer-facing tokened scorecard (deferred: external transparency mechanism not demoable, treat as separate V4 decision).
    - Missing-tutor-data pattern detection (if a tutor or session is repeatedly empty, surface as operational issue).

#### Memo flags (non-design notes for the submission memo)

- **Dietary-kid-low-variety problem.** Restricted-diet kid on a new caterer with few dietary options will receive the same one or two meals repeatedly. We chose dietary safety over variety deliberately; a production version would chase caterers for an expanded dietary range as a procurement requirement.
- **Competitive RFP framing.** Used rather than serial enquiry because it parallelises response time and creates implicit pricing pressure without explicit negotiation.
- **Honest rotation timeline.** Detection → warning → recovery window → RFP → responses → operator pick → cancellation notice → preview week → standard rotation is realistically a 3–5 week process, not "starting next week." Draft templates reflect this.
- **Tutor / manager training as a system precondition.** The data quality of this loop depends on tutors and managers being trained to use the scale consistently, to probe rather than accept first-numbers from kids, to use the request mechanism transparently, and to lead the preference-reset workflow on caterer-change weeks. The system surfaces the data; staff must collect it well.
- **Transparent preference framing.** Asking parents to "pick the meals we'll cycle between for your student" rather than "pick five" is a deliberate honesty move. Five is arbitrary; the real ask is "which subset of this caterer's menu is acceptable." Variable cardinality makes that explicit.
- **Request mechanism as a release valve for parent-pref drift.** Parent-captured prefs sometimes don't reflect what the kid actually wants (kid wasn't consulted, kid's taste has changed, kid was being polite). The request mechanism lets the kid express real preference through the tutor — drawing from any dietary-safe menu item, not just the parent-approved set — without forcing a parent-loop re-ask. Pattern data on requests feeds V4 algorithmic preference adjustment.
- **Parent burden minimised by design.** Parents are asked once per enrolment for dietary tags and the approved set. Caterer changes don't trigger a parent re-ask; the tutor-led preference reset handles it. The dietary profile is durable; the menu-specific approved set isn't.

---

## Group 4 — Caterer Reach & Cost Comparison

### V3-CR-01: Region-based RFP targeting (distance radius)

**Decision summary.** Replace the V1 caterer-school capability matrix with two simple facts: each caterer's home postcode and stated max delivery range, plus each school's postcode. RFP targeting becomes a distance query — caterers within range of the school's postcode get the email, minus the incumbent. Availability for any specific session is asked at RFP time, not stored. The matrix's other ambitions (day-of-week granularity, status enums, effective dates, preference rank, source provenance) are cut entirely.

#### The operational scenario

**Caterer onboarding.** When a caterer is onboarded, two new questions: their home (kitchen) postcode, and the maximum distance they'll deliver in kilometres. For caterers already in the system, postcode is found manually on first need; max delivery range defaults to a generous system-wide value (~50km, intentionally over-reaching) until the caterer is asked directly.

**Each school.** Stores its own postcode. Once at school onboarding, then immutable until the school physically moves (which would be an operator-initiated update, not an automated flow).

**RFP firing.** Operator triggers the RFP from the rotation chain (see V3-FB-01). System queries: "all caterers where distance(school.postcode, caterer.home_postcode) ≤ caterer.max_delivery_km, excluding the incumbent." The result is the recipient list. Distance is computed using a postcode-to-geo lookup (Australian Post lookup table or geopy equivalent), wrapped as a deterministic tool the agent calls.

**RFP email body.** Asks two things: can you cover [school] on [day-of-week], starting [date ~2 weeks out]; and (if not already on file) what's your current per-meal pricing, delivery fee structure, and lead time. Transparent that the email has gone to multiple caterers and the operator will pick from the yeses.

**Responses arrive.** Operator sees, for each respondent:
- Caterer name and contact
- Their stated start date (from their reply)
- Their current per-meal price (from caterer record, or from the reply if they quoted a new figure)
- Their delivery fee structure
- A *projected weekly cost* for this school's cohort, computed by the system: (cohort size × per-meal price) + delivery fee, with MOQ floor applied if relevant
- Their lead time

No historical performance overlay — Padea's reality is one caterer per school over time, so cross-school performance comparison has no data to draw on. If V4 ever produces that data, Shape C (historical performance per respondent) becomes a natural upgrade.

**Operator decides.** Picks one, dismisses the rest. System drafts the cancellation email to the incumbent and (after operator approval) the engagement email to the chosen new caterer. Other respondents get a polite "thank you, we've gone another direction this time" autodraft, also operator-approved.

**Edge — no respondents within range.** System escalates: "no caterers within range of [school] responded. Options: extend the search radius, find a new caterer manually, retain the incumbent with new conditions." Operator decides. No automated fallback.

**Edge — caterer's actual range exceeds their declared one.** A caterer's declared max_delivery_km is conservative — they might do further on a case-by-case basis. The RFP filter intentionally over-reaches by defaulting to a generous range for un-asked caterers; once a caterer declares their own, that's authoritative. This means a caterer who *could* do an unusual delivery but didn't declare the range to cover it gets excluded; we accept the false negative because the alternative (asking every caterer about every school every time) defeats the purpose of having stored ranges.

#### Structured fields

1. **Feature/table/system:** Region-based RFP targeting via stored caterer postcode + declared delivery radius + stored school postcode. Distance query as a deterministic tool. Cost projection at RFP-response time using current pricing only (no historical overlay).
2. **V2 status:** Entirely absent. V2 has `schools.current_caterer_id` and nothing else relating caterers to schools. No alternates concept, no postcode fields, no delivery range, no projected-cost arithmetic.
3. **Requirement supported:** Quality maintained over time (rotation mechanism becomes operable); reliable delivery (alternate path on incumbent non-response, even if the alternate-routing flow stays scoped to rotation only in V3); reducing coordinator bottleneck (operator gets a targeted recipient list and a projected-cost panel, not a blank "go find caterers" prompt).
4. **Value score:** 4/5. Without this, the rotation chain in V3-FB-01 has no recipient list to draw from — the RFP couldn't fire. It's a dependency of the highest-value V3 feature. Slightly below 5 only because the standalone value (without rotation) is lower.
5. **Complexity score:** 2/5. Three new columns (caterer.home_postcode, caterer.max_delivery_km, school.postcode), one deterministic distance tool wrapped around geopy or an equivalent library, one query helper, projected-cost arithmetic that already has its inputs. No new tables. No new lifecycle. The cut version of the capability matrix (10+ columns, joins, effective dates) would have been a 4/5 build; this is genuinely 2/5.
6. **Bugs / fixability / onboarding risks:** Postcode-to-coordinate lookup needs a current dataset (Australia Post coordinates change occasionally; using a maintained Python library mitigates). Stale max_delivery_km if a caterer expands or contracts their range and doesn't tell us (false-negative bias — accepted). 50km default for un-asked caterers is a judgement call (memo flag). Cohort size for projected-cost calculation needs to reflect realistic attendance, not raw enrolment — pulled from session attendance averages where available, falls back to enrolment count.
7. **Decision:** **ADD BACK, SIMPLIFIED.** Capability matrix as a modelled concept is REPLACED with distance-radius targeting. Day-of-week granularity, status enums, effective dates, preference rank, source provenance, and capability-history reconstruction are CUT entirely. Cost comparison (Shape B) committed; historical performance overlay (Shape C) DEFERRED to V4 contingent on the multi-caterer-per-school data ever existing.
8. **Schema impact (sketch):**
   - Extend caterers: `home_postcode` (text), `max_delivery_km` (integer, default 50).
   - Extend schools: `postcode` (text).
   - No new tables.
   - No `caterer_school_capabilities` table introduced (deliberately).
9. **Agent logic impact:**
   - New tool: `caterers_within_range(school_id) → list[caterer_id]` — computes distance via postcode lookup, filters by each caterer's max_delivery_km, excludes incumbent.
   - New tool: `project_weekly_cost(caterer_id, school_id) → cents` — uses cohort-size estimate × per-meal price + delivery fee, MOQ floor applied.
   - RFP composition flow: agent calls `caterers_within_range`, drafts personalised emails to each, queues for operator approval.
   - Response-handling flow: agent ingests replies, populates the comparison panel with stored pricing + projected cost per respondent, surfaces to operator.
10. **Notes for V4 optimisation:**
    - Historical performance overlay on RFP responses (Shape C) — only if multi-caterer-per-school data ever accumulates.
    - Dynamic max_delivery_km adjustment based on observed past delivery history (currently impossible — Padea has only ever had one caterer per school).
    - Auto-extending the radius if zero respondents (e.g., bump to 75km and re-fire) — deferred because the manual "extend the search radius" operator option handles this with less risk.
    - Postcode-to-region clustering for cross-region cost analysis (e.g., "Brisbane Northside caterers are 8% cheaper on average than Inner City") — analytical, not operational.

#### Memo flags

- **Capability matrix considered and rejected.** V1 designed a full (caterer, school, day, status, effective_dates, preference_rank, source) relational matrix with 11 downstream join points. We considered it carefully and rejected it for V3: the matrix solves problems Padea's operation doesn't yet have (day-of-week kitchen restrictions, multi-tier preference ordering, capability supersession history). Distance + RFP-time confirmation gives the same operational outcome (the right caterers get asked, the operator picks) with three columns instead of one full relational subsystem. Strong Learning-criterion sentence.
- **Generous default delivery range as a design choice.** The 50km default for un-asked caterers is deliberately permissive. The cost of an over-reach is a caterer politely declining an RFP; the cost of an under-reach is silently excluding a caterer who'd have said yes. We optimise for the second mistake being impossible.
- **Postcode-to-geo lookup is a real dependency.** A maintained Python library (geopy or equivalent) handles this; we don't build it. Worth naming as a third-party dependency in the build artifact.
- **Cohort-size estimate for projected cost.** Uses session attendance averages where available, falls back to raw enrolment count. The projected number is approximate — operator sees it as decision support, not a binding quote.
- **Padea's actual caterer history is single-caterer-per-school.** This means the brief's "with each caterer" plural framing is historical/operational reality (caterers have been changed over Padea's lifetime) rather than current-state multiplicity. Shape C (historical performance overlay) has no data to feed it in V3 and is deferred accordingly.

---

## Group 5 — Order Costing & Menu History

### V3-OC-01: Derive cost history; trust current menu prices; popularity-ranked canonical order

**Decision summary.** The system retains current menu prices on `menu_items` and stores per-order total cost and student count on `orders` — nothing more. Cost-per-student over time, cost trajectory per caterer, and any cross-order economic analysis are *derivations* over those two fields, not stored snapshots. Menu effective-date history (V1 ADR-019) and order economics scenario snapshots (V1 order_economics_snapshots table) are cut entirely. Order composition is constrained by preferences and requests, not by economic targets — the system never narrows variety to clear MOQ. Pricing surprises are caught by the caterer's reply channel (price-change escalation) and by including a predicted total cost on each order email and on the weekly consolidated summary email.

#### The operational scenario

**Menu prices live as the current price on each menu item.** When a caterer raises a price, the menu row is overwritten in place. No effective-date columns, no end-dating, no history table. The system treats the menu's current state as authoritative for composition.

**Each order stores total cost and student count.** Two existing V2 fields (`total_cost_aud`, `total_items`) carry the load. Cost-per-student for any past order is `total_cost / total_items`. Cost trajectory for a caterer over the term is a query over their orders. No additional storage, no `unit_price_at_order`, no per-line price snapshots.

**Composition is preference-driven, not economics-driven.** Each kid gets a meal chosen by the least-recently-served logic over their approved set (or by their per-week request if one was filed). Natural variety in the order is whatever falls out of the cohort's collective preferences. The agent does not consider variety tiering, MOQ thresholds, or cost minimisation when picking meals. Whatever the cohort wants is what gets ordered.

**Canonical meal ordering by popularity, snapshotted at term start and caterer change.** A global canonical order is computed per caterer by ranking menu items by how frequently they appear across all kids' approved sets at the school — most popular first, ties randomised. Each kid's rotation traverses the subset of that order matching their approved meals, in canonical sequence. A kid with preferences `{C, B, A}` cycles through them in whatever order popularity puts A, B, and C; a kid with `{C, E, A}` cycles through theirs in that order too. The result: kids with overlapping preferences tend to land on the same meal in any given week, which softly clusters the order without explicit clustering logic, and the most-popular meals get served first which lines up with what students will most likely request. The canonical order is computed and stored once at term start, and recomputed once on caterer change. It does not refresh mid-term as new enrolments arrive or as preferences shift; this gives stability through a term and aligns with the rare ‘save money via cluster alignment’ benefit without forcing constant recomputation.

**MOQ handling: pay the difference, notify, continue.** If the natural composition falls below the caterer's MOQ at its natural variety, the order goes through as-is and the system pays for the MOQ floor anyway. A notification escalation fires — operator sees that this week's order at [school] underran the caterer's MOQ by N meals, costing $X. The system takes no autonomous action: doesn't pad the order, doesn't reduce variety to find a lower tier, doesn't suggest rotation. The escalation is informational. Recurring shortfalls accumulate as a pattern the operator reviews in the weekly report; sustained shortfalls feed the human rotation conversation alongside quality decline (V3-FB-01). MOQ is assessed against the full week’s total in the consolidated summary, not against individual sessions.

**Predicted cost surfaces in two places.** First: every per-session order email at T-72hrs carries a predicted total — kid count × per-meal price + delivery fee proportional share (per-session). Caterer sees 'Expected total for this session: $480 — 4 chicken × $12, 8 pasta × $10, 6 salad × $14, delivery $20'. Second: the weekly consolidated summary at Monday 3:30 PM carries a full-week predicted total per caterer — sum across all that caterer's sessions, MOQ floor applied if relevant, GST line per the caterer's `price_includes_gst` and `gst_rate_percent` flags. Together these create transparency and a soft check: if the caterer's pricing has changed and they reply to flag it, the discrepancy lands as an inbound escalation. If the caterer invoices a different amount weeks later, the original predicted figures on each order row and on the summary row give the operator a reference point during invoice review. The system does not ingest caterer invoices in V3, so invoice-vs-prediction variance is not an automated escalation — that's a V4 build (Shape B in the design discussion). V3 catches pricing surprises via the caterer-reply channel only.

**Edge — caterer-declared price change.** Caterer replies to an order email saying "prices have changed, chicken is now $14." Agent classifies the reply as a price-change notification, escalates. Operator reviews, updates the menu price on the affected items. No history kept of the old price. Future orders use the new price.

**Edge — caterer invoices a higher amount weeks later.** Without invoice ingestion (deferred to V4), this is caught manually — operator notices during invoice review, queries the order row to see what was predicted, raises the discrepancy with the caterer themselves. The order row's stored total + predicted total give the operator the data they need to investigate, but the system isn't proactively flagging it.

**Operator-facing surface: weekly cost view.** The weekly report (introduced in V3-FB-01) gains a cost panel: per-caterer cost trajectory over the term, average cost per student, total spend, recent MOQ shortfalls. Lives as a query, not a stored snapshot. Operator reads it Friday alongside the quality data.

#### Structured fields

1. **Feature/table/system:** Order cost memory via derivation, not stored history. Trust the current menu price as authoritative. Compose orders by preference/request only — never re-optimise composition against MOQ or cost targets. Pay MOQ shortfall and notify the operator without taking autonomous action. Predicted cost on every per-session order email and on the Monday consolidated summary as a soft pricing-change tripwire. Canonical meal order computed by popularity-rank, snapshotted at term start and caterer change.
2. **V2 status:** V2 already stores `total_cost_aud` and `total_items` on the order row. Menu prices are mutable with no history (consistent with V3 stance). What V2 doesn't do: include predicted cost on the order email, escalate MOQ shortfalls, expose cost trajectory anywhere, or treat caterer-reply pricing changes as a structured escalation type.
3. **Requirement supported:** Reducing coordinator bottleneck (cost surprises surface via existing channels rather than requiring operator monitoring); visible operation / auditability (predicted total on every order email gives a defensible reference point during invoice disputes); reliable delivery (composition logic never sacrifices kid satisfaction for cost — meal kids actually want > pad-the-order tactics).
4. **Value score:** 3/5. Low standalone value — none of this is the brief's named problems. But the *cuts* it represents are valuable: removes the V1 economics scaffolding (variety tiering at composition, surplus calculations, lower-MOQ scenario snapshots) that was solving a problem Padea's growth trajectory is materially shrinking.
5. **Complexity score:** 1/5. Two new escalation types (MOQ shortfall, caterer-declared price change). Predicted-cost line in the per-session order email template and on the consolidated summary template. Weekly cost view as a query on existing data. Popularity-rank computation runs at term start and on caterer change only. No new tables, no new columns beyond what V3-FB-01 already adds.
6. **Bugs / fixability / onboarding risks:** Menu prices being overwrite-only means a botched manual update can't be rolled back. Mitigated by the order row carrying the predicted total at the time it was sent — even if the menu state is later wrong, the original prediction is preserved. Predicted-cost-on-email depends on the menu being accurate; a stale menu produces a wrong prediction, which the caterer's reply corrects. Popularity-rank canonical order is a snapshot — kids whose preferences change mid-term don't trigger a recomputation, which is fine because their own rotation continues over their approved set in the order set at term start. New enrolments mid-term don't shift the canonical order either; their meals fold into whatever the term-start order is.
7. **Decision:** **ADD BACK, SIMPLIFIED.** Cost-per-student trajectory committed as derivation. Predicted-cost on per-session order email AND on weekly consolidated summary committed. MOQ-shortfall and price-change escalations committed. Menu effective-date history CUT entirely. `unit_price_at_order` column CUT entirely. Order economics scenario snapshots CUT entirely. Invoice ingestion + variance escalation DEFERRED to V4. Canonical meal ordering by popularity-rank with term-start + caterer-change snapshot committed.
8. **Schema impact (sketch):**
   - No new tables.
   - No new columns beyond what V3-FB-01 introduces (which already brings `order_lines` for per-meal-per-kid rows; we explicitly do *not* add `unit_price_at_order` to those rows).
   - One field per caterer to hold the canonical menu order snapshot: `canonical_menu_order` (JSON list of menu_item_ids in popularity-ranked sequence) on `caterers`. Populated at term start and on caterer change; not updated otherwise.
9. **Agent logic impact:**
   - Composition: for each kid, check `meal_requests` first; if absent, query the kid's `term_meal_preferences`, intersect with the caterer's `canonical_menu_order` in stored sequence, advance to the next item past their last-served meal. Auto-pick dietary-compatible meal for restricted kids.
   - Canonical-order computation: runs as a tool invoked at term start and on caterer change. Tool reads all `term_meal_preferences` for the caterer's school(s), counts menu-item appearances, ranks descending with random tiebreak, writes the result to `caterers.canonical_menu_order`.
   - After composition: compute predicted total; populate the order's email body with the prediction line; populate the order's `total_cost_aud` field with the same number.
   - MOQ check: assessed against the full week’s total in the Monday consolidated summary (per V3-AI-01). If `weekly_total_items < lowest_applicable_moq_tier`, log a shortfall escalation (notification, not action-required); show MOQ floor + variance on the consolidated summary email; proceed to send.
   - Caterer reply classification: new email-type `price_change_notification`. On classification, escalate; do not auto-update menu prices.
   - Weekly report generation: extend with cost panel (per-caterer trajectory, recent shortfalls, term spend).
10. **Notes for V4 optimisation:**
    - Invoice ingestion + variance escalation (Shape B): caterer invoices arrive as simulated emails, agent parses amount, compares against order's predicted total, escalates on material variance.
    - Auto-updating menu prices from a caterer's price-change reply (current V3: operator does it manually after escalation).
    - Menu effective-date history if pricing audit becomes a real operational need — currently the predicted-total-on-order-row covers it.
    - Order economics scenario snapshots (5C) if MOQ becomes binding again and variety/cost trade-offs matter — currently growth dissolves this.
    - Mid-term canonical-order recomputation triggered by significant preference shifts (currently fixed-snapshot at term + caterer change).

#### Memo flags

- **MOQ as a transient problem.** The whole V1 MOQ-optimisation layer (variety tiering at composition, surplus calculations, lower-MOQ scenario snapshots) was solving a problem that is materially shrinking with Padea's growth trajectory. We chose to pay occasional shortfalls and surface them to the operator rather than build a system whose value decays as the cohort grows. Strong Learning-criterion sentence.
- **Prioritising freedom over cost optimisation.** The V1 economics scaffolding optimised under constraint; V3 accepts the constraint as a small ongoing cost and delivers more freedom per dollar instead. Composition is preference-driven; cost falls out of preferences, it doesn't shape them.
- **Predicted cost on the order email as a soft tripwire.** Sending the prediction creates a low-effort verification channel — caterers see what we expect to pay, they reply if it's wrong. Catches pricing surprises through existing communication rather than building invoice ingestion infrastructure. Genuine cycle-time win.
- **Popularity-ranked canonical order as soft cluster alignment.** Each kid’s rotation traverses a fixed sequence in popularity order; kids with overlapping preferences tend to land on the same meal in the same week without any explicit clustering. Most-popular meals get served first, which lines up with what students will most likely request. Solves the MOQ-relief problem that cycle-start alignment was going to solve, with one stored field per caterer and a recomputation only at term boundaries.
- **Menu price history considered and rejected.** The V1 effective-date system would let us reconstruct what chicken cost on any past date. We decided the order row's stored total + predicted total give the operator everything they need for invoice disputes, and that the cost of carrying history (extra table, end-dating logic, queries that have to time-walk) exceeded its value at Padea's scale.

---

## Group 6 — Preference Capture & Variety

### V3-PV-01: Preference capture, opt-out flow, and rare-case operator handling

**Decision summary.** Most of this group's substance was absorbed into V3-FB-01 (weekly request mechanism, canonical-order rotation for variety, parent-set approved meals at enrolment). What remained were three edge cases: how mid-term enrolments enter the system, how parents opt their kid out of catering, and how the system handles kids whose status sits outside the standard rotation. All three resolve toward operator handling for rare cases and a clean opt-out signal in the parent email for the routine case. The system models the common path well; rare cases are explicitly out of scope for automation and handled manually.

#### The operational scenario

**Term-start parent email gives parents three responses.** Submit dietary tags + approved meal set (the standard happy path, kid joins rotation); opt out of catering entirely for the term (single-click response); or do nothing (operator chases with reminder, eventually treated as no-response and handled manually). The opt-out option is presented in the email body as a peer of the standard submission, not buried — making it a first-class choice rather than a difficult-to-find exit.

**Opt-out as a parent-controlled flag.** Once a parent clicks opt-out, the kid's enrolment is marked opted-out and stays that way until the parent explicitly reverses it. The kid still attends sessions normally; they just don't receive catered meals. Their enrolment row carries the flag; the agent's order composition skips them entirely.

**Tutor app for opt-out kids: minimal surface with opt-back-in checkbox.** Where other kids show a 1–5 rating box, comment field, and per-session meal request picker after dinner, opt-out kids show only a small 'opt-out' label in the same slot plus a single checkbox: *'student wishes to opt back in for meals.'* No rating, no comment, no request picker. The checkbox is the only interactive element. Ticking and submitting fires an autonomous email to the parent (see V3-MP-01 for the opt-back-in flow). Tutors trained that if a kid wants meals and isn't getting them, ticking this checkbox starts the parent conversation — the tutor doesn't capture the kid's reasoning or preferences in the system.

**Mid-term enrolment: full operator handling.** The brief explicitly flags mid-term enrolment as rare. V3 doesn't build for it. When a mid-term enrolment happens, the operator handles it end-to-end: captures dietary tags and approved meal set directly (typically off a phone call or email exchange with the parent), composes the kid's first-session meal manually as part of that session's order, and enters the kid into the system with full preference data already in place. From the following session onward, the kid is in the rotation like any other enrolment — the system has no rare-case-handling logic because the operator did the handling before the system saw the data.

**Opt-out reversal: also operator-handled.** Parent later emails Padea saying their kid now wants catering. Operator captures dietary tags and approved meal set (if not already on file from a previous term), flips the opt-out flag to false, and the kid joins rotation from the following session. The system doesn't model this reversal flow because reversals are rare-case territory like mid-term enrolments.

**Default state for new enrolments is catering-opted-in.** Silence on the parent email means catering is on; the parent has to actively opt out via the email click. This matches V2's default-false on the `opted_out_of_catering` flag.

**Opt-out kids still count toward session attendance.** Tutor staffing, capacity planning, room booking — all unaffected. Only the meal count is reduced for an opted-out kid. The system distinguishes "not present at session" (absence row) from "present but no meal" (opt-out flag); these never confuse downstream.

**Edge cases of edge cases (all operator-handled).** Parent submits dietary tags but not the approved set within the timeout window: operator decides whether to manually compose first-week meals or wait. Parent submits approved set but not dietary tags: blocking — operator chases for dietary tags before any meal can be safely ordered. Parent submits an empty approved set: operator-handled, same as zero-approved-meals case in V3-FB-01.

#### Structured fields

1. **Feature/table/system:** Parent email with three-way response (submit / opt out / no response); opt-out flag on enrolment with tutor app showing minimal opt-out label plus opt-back-in checkbox; mid-term enrolment and opt-out reversal fully operator-handled; default-opted-in posture for new enrolments.
2. **V2 status:** V2 has `enrolments.opted_out_of_catering` as a boolean column with default false. V2 has no opt-out elicitation flow (operator sets it manually). V2 has no concept of mid-term enrolment as a category — every enrolment is treated as current and pre-loaded. The tutor app and the parent-facing email are V3 additions.
3. **Requirement supported:** Dietary safety (mid-term enrolments don't slip through with incomplete dietary data — operator captures before system processes); reducing coordinator bottleneck (opt-out elicited via email, not chased manually); visible operation (opt-out kids visibly labelled in the tutor app, no ambiguity about why they aren't being served).
4. **Value score:** 2/5. None of this addresses the brief's named problems directly. The value is in *not building* — explicitly scoping rare cases out of system logic and handling them with operator labour. Standalone build value is low; the cost-of-not-building is much lower than the cost-of-building.
5. **Complexity score:** 1/5. One UI variant on the tutor app (opt-out label + opt-back-in checkbox vs. standard box). One additional email response type (opt-out click) and one additional email type (opt-back-in request — see V3-MP-01). No new tables. Existing `opted_out_of_catering` column carries the state.
6. **Bugs / fixability / onboarding risks:** Tutor training must cover the "kid wants meals but is opted out → parent must email" rule, or tutors will try to override the system on the kid's behalf. The opt-out email click needs to feel like a peer of the submission button, not a hidden exit — wording matters. Operator workload for mid-term enrolments is real but bounded (brief calls them rare). Reversal flow being operator-handled means a slow-to-respond operator delays the kid's first meal by a session run; acceptable for the demo, memo flag for production.
7. **Decision:** **ADD BACK, SIMPLIFIED.** Opt-out as a click in the parent email committed. Tutor-app opt-out label + opt-back-in checkbox committed (see V3-MP-01 for the email-firing logic). Mid-term enrolment fully operator-handled — no automated handling built in V3. Opt-out reversal fully operator-handled. Default-opted-in inherited from V2.
8. **Schema impact (sketch):**
   - No new tables.
   - No new columns. `enrolments.opted_out_of_catering` already exists in V2 and is reused.
   - Possibly extend the parent email's structured response to include opt-out as a distinct submission type; implementation detail of how the parent email is processed at ingest, not a schema change.
9. **Agent logic impact:**
   - Order composition: skip enrolments where `opted_out_of_catering = true`. No meal ordered, no row in `order_lines`.
   - Parent email ingest: classify response into one of {full_submission, opt_out, partial, no_response}; route accordingly.
   - Tutor app rendering: for opt-out kids in the session, render the opt-out label instead of the rating/comment/request UI.
   - Weekly report: opt-out kids are counted in session attendance totals but excluded from meal-count totals. Surface the per-school opt-out rate as a small data point (operator awareness of catering uptake).
10. **Notes for V4 optimisation:**
    - Mid-term enrolment automation if the rare-case frequency rises (build trigger: operator manually handling more than ~5 mid-term enrolments per term).
    - Opt-out reversal as a structured parent-email flow (currently a free-form email-to-operator).
    - Opt-out kid signal capture (comment field reintroduced) if there's ever evidence kids opted out by their parents are systematically being underserved — currently no signal that this is happening.
    - Trend tracking on opt-out rates per school as a marketing/operational signal — currently visible as a number in the weekly report, not analysed.

#### Memo flags

- **Rare cases handled by humans, not code.** Mid-term enrolments are flagged as rare in the brief; opt-out reversals are rarer still. Building automation for both would expand the system's surface area for a benefit that fires only a handful of times per term. We chose to let the operator handle these end-to-end and to keep the system focused on the common path. This is the inverse of the V1 instinct to model every edge case.
- **Removing the tutor opt-out comment box but keeping the opt-back-in checkbox.** An earlier design had tutors recording free-text comments on opt-out kids (“kid wants meals,” “kid is jealous of friends”). We cut the comment box because the operational signal it carries (kid wants in) is better served by a structured checkbox that fires the parent email directly. The checkbox does the work of “surface the kid’s interest to the system” without the open-ended text capture overhead.
- **Default-opted-in posture.** Catering is the default; parents opt out actively. Matches operational reality (most parents want catering; the friction of opting out is appropriate for the minority who don't).
- **Parent-controlled, not kid-controlled.** The opt-out flag changes only on parent action — kids can't toggle it through tutors or directly. This protects against impulse changes and keeps the catering relationship anchored where parental consent legally lives.
- **Opt-out kids count toward attendance, not meal counts.** The system distinguishes "absent" from "present but opted out"; these are different states for different operational purposes (staffing vs. catering).


## Group 7 — Communications Layer

### V3-CM-01: Real bidirectional Gmail, outbound audit table, code-resident templates

**Decision summary.** V3 sends real emails through the Gmail API and receives real emails the same way. Every system-sent email is logged as a row in an outbound emails table — to address, subject, full body, send status, failure reason, link back to the agent run that composed it. Email templates live as Python format strings in code (not as database rows). Incoming emails get classified and routed to their existing domain tables (absences, order confirmations, parent enrolment responses, etc.) with a filename reference back to the source; unclassifiable inbound emails escalate to the operator with the file on disk. No general incoming-emails table.

#### The operational scenario

**Outbound — every system email is real.** The system uses the Gmail API (OAuth2 desktop-app flow) to send actual emails through a dedicated Gmail account. For the demo, every outbound email's `To` field is rewritten to the developer's address (`kye@…`) with the original intended recipient preserved in a body header line and in the database row. In production this rewrite flag flips off and the real recipient receives the message. Zero code change between the two modes; one config flag.

Each outbound email lives as a row in `outbound_emails`. The row stores: intended recipient, cc list, subject, full rendered body, when it was composed, when it was sent (null until sent), status (drafted / queued_for_approval / approved / sending / sent / failed), failure reason if relevant, the agent run and step that produced it, and an email type enum.

**Canonical email type enum:**
`session_order`, `weekly_consolidated_summary`, `warning`, `rfp`, `cancellation`, `rfp_loser_courtesy`, `parent_enrolment`, `parent_reminder`, `opt_back_in_request_to_parent`, `operator_notification`, `other`.

(V2's `weekly_order` type is not carried into V3 — the per-session cadence in V3-AI-01 deprecates it in favour of `session_order` and `weekly_consolidated_summary`. The `opt_back_in_request_to_parent` type covers the tutor-triggered parent email per V3-MP-01.)

Status transitions are explicit. Routine, pre-approved messages (session orders to current incumbent, weekly consolidated summaries, opt-back-in parent emails) go `drafted → sending → sent`. Commercial-change messages (warning, RFP, cancellation, RFP loser courtesy) go `drafted → queued_for_approval → approved → sending → sent`. Failed sends transition to `failed` with the failure reason captured; the failed row triggers an escalation so the operator knows something didn't land.

**Inbound — real Gmail polling on each run.** At the start of every agent run, the system queries the same Gmail account's inbox via the Gmail API for messages received since the last run. Each new message is classified by the agent into one of: parent absence notification, caterer order confirmation, caterer price-change notification, parent enrolment response, or unclassified.

Classified messages flow into their domain tables. An absence email creates an `absences` row with `source_email_filename` (or `source_email_message_id` from Gmail) on it. A caterer order confirmation updates the relevant `orders` row's `confirmed_at` and stores the source reference. A parent enrolment response updates the relevant `enrolments` row's dietary tags and approved meal set. A caterer price-change notification fires an escalation and stores the reference.

Unclassified messages — anything the agent can't confidently route, including the disputing-caterer scenario where someone emails to complain about a decision — fires an escalation. The escalation row stores the sender, subject, received timestamp, and source reference. The original email content sits in the file system (downloaded copy from Gmail) for the operator to read. No general inbound emails table exists.

**Templates live in code.** Each outbound email type has a Python module containing its subject template and body template as format strings. To change wording, edit the file, redeploy. Versioning happens in git. The operator never edits a template through the system because the operator is, for V3, also the engineer.

**Demo presentation.** The demo runs against a real Gmail account. Judges see emails arrive in the inbox in real time as the agent composes them. The demo includes the operator replying to a system email from their phone — the agent picks up the reply on the next run and processes it. This is the Taste-criterion move: the system isn't simulating email, it's using email.

**Edge — Gmail OAuth token expiry.** Unverified OAuth apps have 7-day token expiry. Tokens are re-issued by running the auth flow once a week on the dev machine; production deployment would put the app through Google's verification process to remove the limit. Memo flag, not a system issue.

**Edge — Gmail API rate limits.** The Gmail API has generous quotas (billions of quota units per day for most operations); V3's volume is nowhere near them. No rate-limit handling logic needed for V3; memo flag for production.

**Edge — Send failure mid-run.** If the Gmail API call fails (network, auth, rate limit), the outbound row marks status=failed with the error captured, the escalation fires, the agent run continues. Other emails in the same run that succeed are unaffected. Operator reviews the failure and decides — retry, manually send via Gmail's web interface, or skip.

**Edge — Reply arriving for an unknown thread.** A caterer replies to an old order email referencing it by subject, but the agent can't tie it to a current open order. Falls through to unclassified, escalates, operator handles.

#### Structured fields

1. **Feature/table/system:** Real-mode Gmail send/receive via the Gmail API; structured outbound emails table with status lifecycle and failure handling; templates as code; inbound classification into existing domain rows with file references; unclassified inbound as escalation with no general inbox table.
2. **V2 status:** V2 simulates email via filesystem folders. The order email body is stored on the `orders` row as `email_body`. No outbound emails table, no template versioning, no incoming emails table, no real send mechanism. V2's design was self-consistent because V2 only sent one kind of email (the weekly order).
3. **Requirement supported:** Reducing coordinator bottleneck (real email means the operator's workflow is the same in demo and production); visible operation (audit trail of every email ever sent, queryable by recipient, type, date); reliable delivery (send failures escalate explicitly rather than being silently swallowed); dietary safety indirect (parent enrolment responses arrive structurally, not via filesystem copy-paste).
4. **Value score:** 4/5. The real-email upgrade is partly Taste — the demo is meaningfully more credible — and partly Functionality — failure handling becomes real, audit becomes durable. Without real Gmail, V3 demos as "this would work if we plugged it in"; with it, V3 demos as "this is working." That gap is significant for judging on Functionality criterion 3 (how well executed is your automation of the solution).
5. **Complexity score:** 3/5. Gmail API setup is a 60–90 minute one-time task. OAuth flow, send tool, polling tool. The outbound emails table is six core fields plus the enum. The inbound classification logic already exists in V2 form (filesystem-based); upgrading the source to Gmail API is a change of fetcher, not of logic. The real complexity addition is the status lifecycle, failure handling, and the demo-vs-production address rewrite flag.
6. **Bugs / fixability / onboarding risks:** OAuth token expiry every 7 days — must re-auth weekly until production verification. Demo-mode address rewrite flag MUST default to demo mode (rewrite on); accidentally shipping with the flag off in development would send real test emails to real caterers. Mitigated by explicit env-variable check at startup and a loud log line at every send showing the rewrite status. Gmail's spam filtering may snag system-formatted emails on first sends; memo flag — usually resolved by sending a few "warmup" emails from the account before the demo. Per-run polling (5–7 times per week under per-session cadence) introduces small lag on incoming emails; idempotent classification via `gmail_message_id` prevents double-processing across closely-spaced runs.
7. **Decision:** **ADD BACK, EXPANDED BEYOND V1.** Real bidirectional Gmail via API committed. Outbound emails table committed. Templates in code committed. Domain-row references for classified inbound committed. Unclassified-inbound-as-escalation committed. No general inbound table.
8. **Schema impact (sketch):**
   - New table: `outbound_emails`. Fields: id, intended_to_address, intended_cc_addresses (json/text), subject, rendered_body, composed_at, sent_at (nullable), status (enum), failure_reason (nullable text), related_run_id, related_step_id, email_type (enum), gmail_message_id (nullable, populated after send).
   - Extend existing domain tables with source reference fields: `absences.source_email_message_id` (in addition to existing `source_email_filename`), similar on order-confirmation flow and enrolment-response flow.
   - No `incoming_emails` table. No `email_templates` table.
   - One config field (env variable): `EMAIL_MODE` with values `demo` or `production`, controls the address-rewrite behaviour.
9. **Agent logic impact:**
   - New deterministic tools: `gmail_send(to, cc, subject, body, email_type) → outbound_email_id`, `gmail_poll_inbox(since_timestamp) → list[inbound_email_dict]`, `gmail_get_message_body(message_id) → text` (used when classification needs the full body, not just headers/snippet).
   - At run start: poll inbox, classify each new message, route to domain handler or escalation.
   - At email-send time: render template, write outbound_emails row with status=drafted, transition through approval (if commercial), call gmail_send, transition to sent or failed.
   - Decision log integration: every outbound row links back to a run + step, so the HTML decision log renders the email beside the reasoning that produced it.
10. **Notes for V4 optimisation:**
    - Templates in database (migration trigger: non-engineering operators need to edit copy).
    - Production OAuth verification (remove 7-day token limit).
    - Inbound deduplication / threading (currently each inbound is treated independently; threading is V4 work).
    - Attachment handling (V3 ignores attachments; V1 had attachment metadata).
    - Rate-limit handling / backoff (V3 doesn't approach Gmail limits; V4 if volume scales).
    - Inbound classification confidence thresholds (currently binary classified-or-not; V4 could carry a confidence score and escalate borderline cases without escalating clear-but-novel ones).
    - Spam / sender-validation handling on inbound (V3 trusts Gmail's spam filter).

#### Memo flags

- **Real bidirectional email is a Taste call.** We considered three levels of email simulation (filesystem-only, real outbound + simulated inbound, real bidirectional via Gmail API). We chose bidirectional because the demo video is materially more credible when judges see real emails moving through real channels — and because failure handling becomes real rather than aspirational. Demo mode rewrites all outbound recipients to a dev address; production mode is one config flag away.
- **Database as source of truth, Gmail as transport.** Audit lives in the database, not in the mail server. The database survives account changes, retention policies, and archival mistakes. This is a deliberate inversion of the "Gmail's sent folder IS our audit" instinct — convenient in the short term, fragile in the long term.
- **Templates in code with a documented V4 migration trigger.** Templates live as Python format strings during V3 because every editor is an engineer. The migration trigger to database-stored templates is when non-engineering operators need to edit copy — at that point, code edits require deployment cycles operators don't have. Documented now so the future migration is a deliberate event, not a "we'll think about it later."
- **Unclassified inbound as escalation, not as a new domain.** We chose not to build a general inbound emails table to catch unclassified messages. Reasoning: unclassified inbound is by definition rare (the classifier handles the common cases), and the operator workflow for handling weird inbound is "read the email and decide" — which doesn't benefit from structured rows. File on disk + escalation row carrying enough context = sufficient.
- **OAuth token expiry as a known operational quirk.** 7-day expiry on unverified OAuth apps means a weekly re-auth on the dev machine. Production verification removes the limit but requires Google's verification process (not worth doing for the competition). Memo-flagged so the demo-day re-auth is planned, not a surprise.
- **Demo-mode flag as a safety mechanism.** The address-rewrite flag is loud, logged on every send, and defaults to demo mode. Accidentally shipping with it off would send test emails to real caterers — a non-trivial commercial-relationship risk. The flag is treated as a safety mechanism, not a convenience toggle.


## Group 8 — Enrolment Lifecycle

### V3-EL-01: Date-driven enrolment lifecycle, derived active state, no history tables

**Decision summary.** Enrolment lifecycle returns as date-driven, not status-driven. Each enrolment row carries an original start date (stable forever), a current-period start date (updated on return after a departure), and a current-period end date (null while the kid is active, set when they leave). "Currently enrolled on date X" is derived from those three dates plus the absences table — not from a separate status field. Opt-out from catering remains an orthogonal boolean (V2 carried forward) because opting out of catering is a different fact from leaving Padea. No history tables for dietary changes, menu prices, caterer details, or anything else — overwrite-in-place is the discipline. School holidays and term breaks are handled as full-school exclusions in the existing exclusions table; the system has no concept of "academic term" in its schema. The accepted gap is the rare dietary-incident-dispute scenario where the dietary tag history would matter — flagged as a memo concern, not a system feature.

#### The operational scenario

**Each enrolment row has three lifecycle dates.** `original_start_date` is set when the kid first ever enrols with Padea and never changes afterward. `current_period_start_date` is set to the same value initially, but if the kid leaves and returns, the operator updates this to reflect the new period. `current_period_end_date` is null while the kid is active and set when they leave. The three dates together let the system answer "when did Sam first join Padea?" (original), "when did Sam most recently rejoin?" (current period start), and "is Sam currently active?" (end date null OR end date in the future).

**Active state is always derived, never stored.** No status field. To check whether a kid is currently active: `current_period_end_date IS NULL OR current_period_end_date > [date-of-interest]`. The date-of-interest is the session's date when composing orders, today's date when surfacing current enrolment counts in the weekly report, or any past date when reconstructing what happened on a specific day.

**Opt-out from catering is a separate boolean.** Lives as `opted_out_of_catering` on the enrolment row (inherited from V2). Captures the fact that the kid is currently a Padea student but doesn't want catered meals. Operationally indistinguishable from withdrawal for the catering workflow (both skip the kid in order composition), but factually distinct — Sam-opted-out is at MBBC on March 14th; Sam-withdrawn is not. The safety/emergency traceability scenario depends on this distinction.

**Mid-term enrolment under the lifecycle model.** Operator creates a new row when a kid joins mid-term: `original_start_date` and `current_period_start_date` both set to the join date, `current_period_end_date` null, dietary tags and approved meal set captured manually as per V3-PV-01. The system sees the kid from that date onwards. The new lifecycle handles this cleanly — no special-case logic needed beyond the existing operator-handled flow.

**Mid-term withdrawal.** Operator sets `current_period_end_date` to the kid's last day. From that date onwards, order composition skips them. Historical orders, feedback rows, and the rest of the kid's data remain queryable. Term reports for the period the kid was active include them; current reports don't.

**Re-enrolment after a gap.** Kid left at end of term 1 (end date set to last day of term 1). Returns at start of term 3. Operator updates the same row: `current_period_start_date` becomes the new join date, `current_period_end_date` cleared back to null. `original_start_date` is untouched — the kid's full Padea history is unified under the same row.

**Term seam handling — no bulk reset.** The operator doesn't run an import script between terms. Instead: kids who left at term 1's end have their end dates set as part of the routine withdrawal flow. Kids joining at term 2 start get new rows as part of the routine enrolment flow. Continuing kids — the vast majority — need nothing done. Term breaks themselves are marked as full-school exclusions covering the holiday dates across all six schools (operator adds these in bulk via a quick script or admin UI action at term end). The system runs continuously across terms with no concept of "term" in code — terms are a property of the exclusions calendar, not of the enrolment schema.

**Date-parameterised enrolment queries throughout.** No agent tool ever asks "is Sam currently enrolled" — every tool asks "was Sam enrolled on [date]." Order composition asks against the session date. Weekly report asks against the report date. Incident investigation asks against the incident date. This is enforced in the tool layer, not as a documentation hope — the parameter is required, not defaulted to today.

**Holidays as exclusions, in volume.** A two-week school holiday across six schools means roughly sixty exclusion rows (six schools × five session-days × two weeks). Bulk-inserted via a one-off operator script at term end. The existing V2 exclusions table handles this without modification.

**Edge — kid withdraws and returns to a different school.** Treated as a new enrolment row at the new school, not a return. Each enrolment row ties a kid to a school; cross-school identity is not modelled in V3 (Group 9 candidate, deferred). The kid's original Padea history is technically split, but the operator can manually note the link if needed. Memo flag.

**Edge — operator forgets to set end_date when a kid leaves.** The kid stays "active" in the system, gets included in orders, gets a meal that nobody eats. The session manager flags it via the "kids who didn't eat" field; operator catches the discrepancy in the weekly report; sets the end date retroactively. Self-correcting through existing surfaces; no automatic detection needed.

**Edge — dietary status changes mid-term and a later incident raises a dispute.** This is the accepted gap. A parent claims Padea served their kid food they were allergic to. The dietary tag was updated three weeks earlier when the parent first emailed; by the time of the incident investigation, the tag reflects current state but not the state at the time of the incident. The system cannot answer "what was Sam's dietary tag on March 14th." Operator reconstructs from email logs and notes. Production version would add dietary tag history; V3 accepts the risk because (a) kids generally know what they can and can't eat and self-protect at the point of meal service, (b) the operator-mediated email exchange that initiated the change is itself a record outside the system, and (c) the build cost of a history table for one rare-case dispute scenario doesn't earn its place.

#### Structured fields

1. **Feature/table/system:** Three-date lifecycle on enrolments (`original_start_date`, `current_period_start_date`, `current_period_end_date`); derived active state via date comparison; `opted_out_of_catering` boolean carried forward from V2 as an orthogonal fact; school holidays as full-school exclusions; operator-managed term seams with no bulk reset; no history tables for any other entity.
2. **V2 status:** V2 treats every enrolment as current. No lifecycle dates. Withdrawal is either row deletion or conflation with the opt-out boolean. Dietary changes overwrite. No academic-term concept; the system runs against one snapshot.
3. **Requirement supported:** Visible operation / auditability (historical enrolment state is reconstructible for safety/incident review); reducing coordinator bottleneck (no bulk reset script needed at term seams — routine flows handle it); dietary safety partial (current dietary tags are authoritative; historical dietary state is the accepted gap).
4. **Value score:** 3/5. Standalone value is moderate — the system functions without lifecycle dates as long as nobody asks historical questions. Value is in unblocking other things: continuous-across-terms operation, the safety traceability scenario, the cross-term return case. The brief doesn't name this as a problem, but the operational reality (term cycles, kids leaving, kids returning) makes it real.
5. **Complexity score:** 2/5. Three date columns on the existing enrolments table. The `opted_out_of_catering` boolean already exists. The exclusions table already exists. Date-parameterised queries are a refactor of existing tools — each tool that currently asks "current enrolment" now asks "enrolment on [date]" — but the logic itself doesn't change. No new tables.
6. **Bugs / fixability / onboarding risks:** Operator forgetting to set end_date on a departing kid produces an order for someone who isn't there (self-correcting through existing surfaces, see edge above). Operator returning a kid via clearing end_date instead of setting current_period_start_date loses the new-period semantic — mitigated by surfacing both dates in any operator UI. Date-parameterised queries can produce wrong results if the date parameter defaults to today instead of the operation's natural date (e.g., composing an order for next week but querying enrolment as of today) — mitigated by making the date parameter required, not optional. Holidays-as-exclusions volume (~60 rows per holiday) is bulk-inserted; a typo in the date range produces no orders and is loudly visible.
7. **Decision:** **ADD BACK, EXPANDED FROM V1.** Lifecycle dates committed (three-date version, not the simpler two-date version V1 had). Derived active state committed. `opted_out_of_catering` boolean retained. Holidays as exclusions committed. Date-parameterised queries committed. All history tables CUT — enrolment history, menu item history, caterer history, exclusion supersession. Dietary status history DEFERRED to V4 with the rare-case-dispute scenario as the accepted gap.
8. **Schema impact (sketch):**
   - Extend `enrolments`: add `original_start_date` (date, not null), `current_period_start_date` (date, not null), `current_period_end_date` (date, nullable).
   - `opted_out_of_catering` boolean retained from V2; no change.
   - No new tables.
   - No history tables (`enrolment_history`, `menu_item_history`, `caterer_history` all explicitly cut).
   - Existing `exclusions` table from V2 absorbs school holiday handling without modification.
9. **Agent logic impact:**
   - Tool `get_enrolments_for_session(session_id, date)` filters by `current_period_start_date <= date AND (current_period_end_date IS NULL OR current_period_end_date > date) AND opted_out_of_catering = false`.
   - Tool `get_enrolment_history(enrolment_id, date)` returns the enrolment's known state as of the given date — useful for incident investigation surfaces.
   - Weekly report includes enrolment-count trajectory (active count per school over the term) computed from the date-parameterised queries.
   - Order composition uses session date as the query parameter; never uses today's date implicitly.
   - Term-seam-handling: no agent logic. The operator manages enrolment dates and exclusion ranges manually.
10. **Notes for V4 optimisation:**
    - Dietary tag history table (build trigger: dietary-incident dispute that V3's overwrite-in-place couldn't answer).
    - Automated mid-term-enrolment flow (currently fully operator-handled).
    - Cross-school identity for kids who move between Padea schools (currently treated as two unrelated enrolments).
    - Academic-term concept in schema if cross-term reporting becomes a routine operator surface (currently terms are exclusion-driven, not first-class).
    - Bulk-import / sync from Padea's internal app for term-seam efficiency (currently operator handles departures and arrivals individually).

#### Memo flags

- **Active state is derived, never stored.** A status field was considered and rejected: it adds an orthogonal source of truth that can drift from the date columns. Derived state from dates means there's one source of truth and one place to update.
- **Three lifecycle dates, not two.** V1 had `start_date` and `end_date`. V3 splits the start into `original_start_date` (the durable fact of when a kid first joined Padea) and `current_period_start_date` (the start of their current continuous period). This preserves the "first-ever-joined" fact through re-enrolments — a small extra column, real audit value.
- **end_date means "end of Padea catering relationship," not "left the school."** Padea operates at schools but is a separate entity. A kid who leaves Padea but stays at the school has their Padea end_date set; the school is none of the system's business. Memo-flagged so the semantic is clear in operator training.
- **Opt-out and withdrawal are different facts.** Both look the same to the catering composer (skip the kid). They look different to the safety auditor (was Sam at MBBC on March 14th?). V3 preserves the distinction via the orthogonal boolean rather than collapsing them.
- **Date-parameterised enrolment queries throughout.** No tool asks "is Sam enrolled" — every tool asks "was Sam enrolled on [date]." This is a discipline applied across the tool layer, not a one-off. Lets historical incident investigation use the same query infrastructure as routine order composition.
- **Dietary history as the accepted gap.** A parent disputing "you served my kid something they couldn't eat — you knew about the restriction" can't be answered from system state because dietary tags overwrite. We accepted the risk because (a) kids self-protect at the point of meal service, (b) the email exchange initiating the change is its own record, and (c) the build cost of a history table for one rare-case dispute doesn't earn its place at V3 scale. Production-build trigger documented; until then, this is a known gap in the audit.
- **Term seam handled by routine flows, not by bulk reset.** Earlier design instinct was to have the operator run an import script at term boundaries. V3 model removes the bulk operation — kids leaving at term 1's end get end-dated through the routine withdrawal flow; kids joining at term 2's start get new rows through the routine enrolment flow; school holidays are exclusion-driven. The system is term-agnostic; terms exist in the exclusion calendar, not in the schema.
- **History tables cut by policy.** No `enrolment_history`, no `menu_item_history`, no `caterer_history`. The cost of capturing every mutation across these tables is high; the cases where mutation history actually gets queried are rare. V3 chooses overwrite-in-place and accepts the audit gap as a memo flag rather than a system feature.


## Group 11 — Observability & Escalation

### V3-OE-01: Three-tier escalation severity, flat decision log, no lifecycle state

**Decision summary.** V3 keeps V2's flat `agent_steps` model and adds one piece of structure to it: a three-tier urgency classification on every step that carries escalation weight. Urgent items await operator decision before something can proceed. Notable items are patterns or events worth investigating. Informational items are recorded for awareness with no action expected. Everything else from V1's escalation modelling — lifecycle state machines, dedup with recurrence counts, retry notifications, hierarchical decision trees, cross-entity reference columns — is cut. The system's responsibility ends at clear surfacing; the operator's discipline carries handling.

#### The operational scenario

**Each agent step that surfaces something to the operator carries an urgency tier.** Three values, used consistently across every kind of escalation V3 produces:

*Urgent.* The step is gating something. Until the operator acts, an email isn't sent, an order isn't composed, a caterer isn't engaged. Examples: warning email awaiting approval, RFP awaiting approval, cancellation email awaiting approval, unclassified inbound requiring routing, Gmail send failure requiring a retry decision. These are what the operator works first when they open the decision log.

*Notable.* Worth the operator's attention but not blocking. Recurring patterns the operator should pattern-match against, single-session signals worth investigating. Examples: MOQ shortfall recurring for the same school across weeks, manager 1 or 2 on any session, tutor-1-pattern firing on a tutor or caterer. The operator reads these, makes notes, decides if they warrant follow-up.

*Informational.* Recorded for awareness with no action expected. Examples: one-off MOQ shortfall (caterer was paid for the floor, system continues), weekly order sent successfully, parent opt-out elicited, caterer order confirmation received. These accumulate in the log as the audit trail of what happened.

**The decision log renders these visibly.** The HTML decision log generated after every run sorts urgent items to the top, notable in the middle, informational at the bottom — colour-coded (red for urgent, amber for notable, green for informational) so the operator's eye finds urgent items at a glance without reading entries. A summary count at the top of the log shows "3 urgent, 4 notable, 12 informational" so the operator knows the scale of what's waiting before scrolling.

**No lifecycle. No "I've handled this" state.** The decision log is regenerated from scratch every run. There is no acknowledgement field, no resolution status, no "open vs. closed" state. When the operator handles a thing, the next run reflects whatever new state of the world results — the urgent warning-email-awaiting-approval becomes a sent warning email recorded in `outbound_emails`; the urgent unclassified inbound becomes a routed domain row or stays unclassified and re-appears. State transitions happen in the underlying data; the log just renders the latest snapshot.

**Per-run regeneration, grouped by week.** Under per-session cadence (V3-AI-01), the agent runs 5–7 times per week. The decision log regenerates after each run. The HTML log organises events by week for readability — opens to the current week’s events at the top, prior weeks collapsible below. Operator can open the log at any time and see whatever the latest snapshot is. The Monday 3:30 PM run regenerates the log with the week’s complete activity grouped clearly.

**No dedup, no recurrence counts.** A recurring MOQ shortfall at MBBC produces four separate informational entries across four weekly runs. The operator pattern-matches by reading the log; the weekly cross-school report (V3-FB-01) surfaces patterns over time as a separate view. The system doesn't try to compress duplicate events into one row with a count — that's V1's `match_key` design, and V3 cut it.

**No retry notification.** If the operator doesn't act on an urgent item, it stays urgent on the next run. The system doesn't ping. The system doesn't escalate to anyone else. Operator discipline carries the load.

**No tree structure on the decision log.** Steps are flat with a step_index. A complex multi-step reasoning chain (order composition spanning enrolment lookup, exclusion application, dietary matching, MOQ check) renders as a sequence rather than a hierarchy. The cost is some loss of "what was a sub-step of what" — usually inferrable from the step content, occasionally not.

**No cross-entity references column.** Foreign keys touched by a step live inside the step's `tool_input` and `tool_output_full` JSON. Forensic queries like "show me every decision that touched enrolment #487" work via JSON search, slower than V1's explicit column but acceptable at V3 scale.

**Wording and subject-line discipline carries most of the value.** Because the system relies on the operator reading and acting, the wording of each escalation matters more than its structural metadata. Subject lines are descriptive ("MOQ shortfall at MBBC, week of 2026-05-26, $48 difference paid"). Body text states what happened, why it was surfaced, what the operator's decision space is (if any), and what the system will do next without intervention. This is the load-bearing piece of the design — the urgency tier sorts the list; the wording does the work.

#### Structured fields

1. **Feature/table/system:** Three-tier urgency classification (urgent / notable / informational) applied consistently across every escalation type. Decision log sorts and colour-codes by tier. Top-of-log summary count. No lifecycle state, no dedup, no retry, no tree, no cross-entity references column. Per-run regeneration with weekly grouping.
2. **V2 status:** V2 has `agent_steps.severity` as a free-text field with values like "info", "warning", "escalation". No consistent tier definition, no operator-facing rendering convention, no summary count. The decision log shows steps in chronological order with severity colours but doesn't sort by urgency. V2 generates the log once per Thursday run.
3. **Requirement supported:** Reducing coordinator bottleneck (operator triages urgent items first, doesn't have to read everything to find them); visible operation (clear urgency hierarchy makes the system's state legible at a glance); dietary safety indirect (urgent items for unclassified inbound or send failures surface fast enough that nothing safety-critical sits unhandled by accident).
4. **Value score:** 3/5. Standalone value is moderate — V2 functions without tiers as long as the operator reads everything carefully. Value emerges as V3's escalation volume rises (eight-to-ten distinct escalation types across the locked decisions, more on busy weeks). At that volume, scan-ability becomes meaningful.
5. **Complexity score:** 1/5. One enum field on `agent_steps` (or replacing the existing free-text severity field with a constrained enum). Sort + colour logic in the decision log renderer. Summary count at the top of the log. No new tables, no new tools. Per-run regeneration with weekly grouping in the renderer.
6. **Bugs / fixability / onboarding risks:** Drift between intended tier and applied tier — the agent could mis-classify an urgent thing as informational. Mitigated by reserving urgent for the small, well-defined set of "system is waiting for you" events and keeping the rest in the notable/informational range. Subject-line and body-text quality is critical and is a prompt-engineering concern, not a schema concern; surface as memo flag. Operator missing an urgent item is an accepted risk (V3 trusts discipline); V4 trigger documented if it becomes a real issue.
7. **Decision:** **ADD BACK, SIMPLIFIED.** Three-tier urgency committed. Decision log sort/colour by tier committed. Summary count at top of log committed. Wording discipline as a system precondition committed via memo flag. Lifecycle state CUT. Dedup with recurrence_count CUT. Retry notification CUT. Decision tree CUT. Cross-entity references column CUT. Per-run regeneration with weekly grouping committed.
8. **Schema impact (sketch):**
   - Replace `agent_steps.severity` (currently free-text) with `agent_steps.urgency` (enum: urgent / notable / informational / none) — the `none` value covers steps that are routine tool calls with no operator-facing weight.
   - No new tables.
   - Existing `outbound_emails.status` already carries the "awaiting approval" state for emails specifically; urgent agent_steps reference those rows where relevant.
9. **Agent logic impact:**
   - Every step the agent produces tags an urgency level. Tool-call steps default to `none`; escalation steps tag urgent / notable / informational explicitly.
   - Decision log renderer sorts steps within each run by (urgency rank descending, step_index ascending) so urgents float to the top, then notables, then informationals, then routine.
   - Summary count at the top of the log queries the run's steps grouped by urgency.
10. **Notes for V4 optimisation:**
    - Lifecycle state on escalations (build trigger: operator team grows beyond one person, or volume exceeds what one person can track from memory).
    - Dedup with recurrence counts (build trigger: pattern-matching by operator becomes unreliable due to volume).
    - Retry notification (build trigger: unhandled urgent items become a real problem).
    - Hierarchical decision log (build trigger: reasoning chains routinely span more than ~5-7 steps and the flat list becomes hard to follow).
    - Cross-entity references column (build trigger: forensic queries against JSON become unacceptably slow).

#### Memo flags

- **System surfaces; the human handles.** V1 designed elaborate lifecycle state machines for escalations. V3 trusts that the operator reads the log, does the work, and the next run reflects whatever new state results. The system's responsibility ends at clear surfacing. This is a deliberate philosophical inversion — building state machines that mirror operator workflow is overhead when there is only one operator and the workflow is reliable. Strong Learning-criterion sentence: "we chose operator discipline over system-enforced state machines because the system was being built for a single operator on a per-session cadence — modelling workflow state for that scale is solving the wrong problem."
- **Three tiers map onto V3's actual escalation surface.** Urgent for things gating other things. Notable for patterns and single-session signals worth investigating. Informational for the audit trail. Not arbitrary — chosen because the eight-to-ten escalation types V3 produces fall cleanly into these three buckets.
- **Wording and subject lines carry the value, not the structure.** Because the system doesn't track resolution state, the operator's first read of each escalation has to be sufficient to act on. Subject lines describe what happened. Body text states the decision space and what the system will do without intervention. This is a prompt-engineering and template-quality concern, not a schema design concern, but it's load-bearing.
- **The decision log is the operator's surface; the database is the audit.** Decision log is regenerated from the database every run. The database's state is the source of truth; the log is a view onto it. V3 doesn't build operator surfaces beyond the log and the weekly cross-school report (introduced in V3-FB-01).
- **Per-run regeneration with weekly grouping.** Under per-session cadence (V3-AI-01), the log regenerates after every run (5–7 times per week). The HTML renderer groups by week so the operator can see ‘what’s happened this week’ at the top without scrolling through prior weeks.
- **V4 triggers documented for each cut.** Lifecycle, dedup, retry, tree, references column — each has a specific operational signal that would justify building it. Cutting them isn't "we don't need this," it's "we don't need this *yet*, and here's what would tell us to build it."


## Group 9 — Identity Layers

### V3-IL-01: Tutors as first-class, students/parents as denormalised columns, dual-role manager-tutor model

**Decision summary.** Of the four V1 identity layers (students, parents, tutors, cross-school identity), only tutors return as a first-class entity in V3 — and only because the feedback ecosystem in V3-FB-01 requires per-tutor attribution of scoring. Students stay denormalised onto enrolments (each enrolment carries the kid's name; no separate students table). Parents stay denormalised onto enrolments (parent_name and parent_email columns; no separate parents table). Cross-school identity resolution stays cut entirely — no kid in the data attends multiple schools. The tutor model handles dual-role cases where a session manager is also a tutor with their own students: one assignment row per person per session, with `is_manager` and `is_tutor` boolean flags. Feedback from a dual-role person submits to two channels (manager-level + per-kid-tutor-level) and the aggregation math counts them as two independent rater perspectives. V2's `session_slots.manager_name` and `session_slots.manager_phone` columns are deprecated — `session_tutor_assignments` is the source of truth for manager identity from V3 onwards.

#### The operational scenario

**Tutors as the only first-class identity table.** A `tutors` table stores tutor identity (name, email, mobile, optional employee identifier). Each tutor exists once across all sessions they work, regardless of school or role. This is the schema requirement for V3-FB-01's per-kid post-dinner scoring — without a tutors table, scoring attribution would have to live as a name string on every feedback row, which loses the cross-session identity needed for rater tracking, missing-data signals, and any future V4 normalisation.

**Session manager + tutor assignment via dual-role rows.** A `session_tutor_assignments` table links tutors to sessions they staff. Each row carries `(session_id, tutor_id, is_manager, is_tutor)`. A person tutoring only — `is_tutor=true, is_manager=false`. A person managing only — `is_manager=true, is_tutor=false`. A person doing both — both true. The structure naturally handles all four combinations including no-assignment (which simply means no row).

**Feedback attribution under dual roles.** A dual-role person at a single session submits two distinct feedback channels: their manager-level session report (session-wide score, checklist, meals-left, names of kids who didn't eat) and their per-kid post-dinner ratings for whichever kids they're tutoring that session. Both submissions go into the same `feedback` table; the polymorphic source field (`manager` vs. `tutor`) distinguishes them. The rolling-mean math (V3-FB-01) aggregates them as two independent perspectives — manager scores and tutor scores roll up separately and only converge at the per-caterer level.

**Students as denormalised name columns.** Each enrolment row carries `student_name` directly. No `students` table, no `student_id` foreign key. Same kid at the same school across two terms is one enrolment row updated via the lifecycle dates (V3-EL-01). Same kid hypothetically at two schools would be two unrelated enrolment rows with the same name — but the data shows no such case, so V3 doesn't model the resolution.

**Parents as denormalised contact columns.** Each enrolment row carries `parent_name` and `parent_email`. No `parents` table. Sibling enrolments at the same or different schools each carry the parent's contact independently — if a parent updates their email, the operator updates each enrolment row touching that parent. Memo flag: this is a maintenance cost for the rare multi-sibling case, accepted because the build cost of a parents table (with the foreign key cascade across enrolments) exceeds the rare-update cost.

**Cross-school identity resolution explicitly out of scope.** The data shows zero cases of a kid attending multiple Padea schools. If such a case emerged operationally, the operator would manually note the link in comments; the system would treat them as two unrelated enrolments. V4 build trigger documented; nothing built in V3.

**Edge — unregistered attendee.** A kid not on the enrolment list shows up at a session expecting food. The brief and operational reality handle this before dinner — attendance is marked, anyone not on the list is dealt with by the school's normal processes (sibling tagging along, friend visiting, paperwork-pending new enrolment). The catering system has no concept of an unregistered attendee; if one appears, no meal is ordered for them and the school handles the situation outside catering. Not a system case; memo flag for clarity.

**Edge — parent email changes mid-term.** Operator updates the parent_email column on every enrolment row touching that parent (typically one row, occasionally two or three for siblings). No automatic propagation because there's no parents table to propagate from. V4 trigger: parents promoted to first-class if multi-sibling email maintenance becomes a regular operator chore.

**Deprecation of V2’s `session_slots.manager_name` and `session_slots.manager_phone`.** These two columns existed in V2 as denormalised manager identity per (school, day-of-week). V3’s `session_tutor_assignments` table is the source of truth from V3 onwards. The V2 columns are dropped during migration; manager contact for any session comes from joining `session_tutor_assignments` (where `is_manager=true`) to `tutors`. This removes the risk of drift between two sources of truth.

#### Structured fields

1. **Feature/table/system:** `tutors` table as first-class entity; `session_tutor_assignments` with `(session_id, tutor_id, is_manager, is_tutor)` for dual-role support; students and parents denormalised onto `enrolments` rows; no cross-school identity table; feedback polymorphism handles dual-role submission attribution; V2 `session_slots.manager_name` / `manager_phone` deprecated.
2. **V2 status:** V2 has no tutors table whatsoever — session_slots carry `manager_name` and `manager_phone` as denormalised strings. V2 has no concept of per-kid tutor identity. Students and parents are already denormalised onto enrolments in V2; V3 keeps this. No cross-school identity in V2 either.
3. **Requirement supported:** Quality maintained over time (per-tutor feedback attribution unlocks the rolling-mean math from V3-FB-01); reducing coordinator bottleneck (dual-role modelling means one assignment row per person per session rather than two); visible operation (cross-session tutor identity makes "show me everything tutor X did this term" a real query).
4. **Value score:** 3/5 standalone — but functionally required by V3-FB-01, so the real value is whatever V3-FB-01 unlocks. Without tutors as first-class, the feedback ecosystem doesn't work.
5. **Complexity score:** 2/5. One new tutors table. One new session_tutor_assignments table. Dual-role booleans rather than role enum (cleaner queries, naturally handles all four states). Two columns dropped from session_slots (manager_name, manager_phone). No upgrades to enrolments needed; the existing denormalised student_name and parent_email columns suffice.
6. **Bugs / fixability / onboarding risks:** Tutor identity drift if the same person is entered as two rows by mistake (e.g., once with full name, once with nickname). Mitigated by operator-discipline at onboarding. Migration from V2: any existing manager_name/manager_phone data needs to be back-filled into tutors + session_tutor_assignments rows before the V2 columns are dropped. Dual-role attribution requires the agent to know which kids the dual-role person tutored — comes from `session_tutor_assignments` rows where `is_tutor=true` AND a kid lookup against the assignment's session and the tutor's per-kid relationship (which V3 doesn't yet model explicitly). Memo flag: per-kid-to-tutor assignment within a session is operator-knowledge, not yet a system fact; usually the manager knows. V4 trigger documented if this becomes ambiguous.
7. **Decision:** **ADD BACK (TUTORS), CUT (STUDENTS, PARENTS, CROSS-SCHOOL).** Tutors as first-class committed (covered by V3-FB-01 schema requirement). Dual-role assignment model committed. Students denormalised on enrolment committed. Parents denormalised on enrolment committed. Cross-school identity CUT, V4 trigger documented. V2 `session_slots.manager_name` and `session_slots.manager_phone` deprecated.
8. **Schema impact (sketch):**
   - New table: `tutors` (id, name, email, mobile, optional employee_identifier).
   - New table: `session_tutor_assignments` (id, session_id FK, tutor_id FK, is_manager bool, is_tutor bool, assigned_at).
   - `enrolments` already carries student_name, parent_email, parent_name; no change.
   - No `students` table, no `parents` table, no `student_identity_merge` table.
   - Drop `session_slots.manager_name` and `session_slots.manager_phone` after V2 data has been migrated to tutors + session_tutor_assignments.
9. **Agent logic impact:**
   - Order composition queries `session_tutor_assignments` for the session's manager (where `is_manager=true`) to get manager contact for caterer emails.
   - Feedback ingestion classifies by `source` (manager vs. tutor); each goes into its own scope of the rolling-mean math.
   - Per-kid feedback attribution traces from the kid's session, to the assignment rows where `is_tutor=true`, to whichever tutor is the one who entered the score. (How the kid-to-tutor mapping happens within a session is an operational concern for V3 — usually one tutor per group of ~5 kids, the operator-tutor relationship — and a V4 trigger for explicit modelling.)
10. **Notes for V4 optimisation:**
    - Students as first-class (build trigger: real cross-school case emerges, or per-student multi-school history becomes a real query).
    - Parents as first-class (build trigger: multi-sibling parent-email maintenance becomes a recurring operator chore, OR per-parent reliability stats become operationally meaningful).
    - Cross-school identity resolution (build trigger: any kid case that genuinely spans schools).
    - Per-session per-tutor kid assignments as explicit rows (build trigger: kid-to-tutor attribution becomes ambiguous or contested in feedback data).
    - Unregistered attendee modelling (build trigger: this becomes a recurring operational case rather than an exception).

#### Memo flags

- **Tutors as first-class because feedback requires it; no other identity table earns return.** Students, parents, and cross-school identity all stay denormalised. The bar for promoting an entity to first-class is "the system needs to ask cross-context questions about it," and only tutors clear that bar in V3.
- **Dual-role manager-tutor handled via boolean flags, not role enum.** A person can be a manager, a tutor, both, or neither at any given session. The boolean shape naturally expresses all four; a role enum forces awkward "both" semantics or two rows per person.
- **Feedback attribution counts manager and tutor as independent rater perspectives even when the same human submits both.** Manager scores and tutor scores roll up separately and only converge at the per-caterer level. A single dual-role human doesn't get their perspective double-counted into a single score.
- **Per-kid-to-tutor mapping within a session is operator knowledge, not yet a system fact.** Each tutor works with a small group of kids; which tutor scored which kid in the feedback comes from the tutor's session app interaction, not from a schema-modelled assignment. V4 trigger documented if this becomes ambiguous in practice.
- **Deprecating V2’s manager_name/manager_phone columns rather than keeping them as fallback.** Two sources of truth for manager identity creates drift risk. V3 commits to one (`session_tutor_assignments`) and drops the V2 columns during migration. Per-date manager variation is automatically supported because the assignment table is per-session.
- **Maintenance cost of denormalised parents accepted as a memo flag.** When a parent email changes, the operator updates each enrolment row touching that parent. For one-sibling families (most cases) it's one row; for multi-sibling cases (uncommon), one update per sibling. The alternative is a parents table with FK cascade — meaningful build complexity for a low-frequency maintenance task.

---

## Group 10 — Margins, Predictions & Reconciliation

### V3-MP-01: Zero operational margin, cut all prediction infrastructure, walkups suffer one week no-meal

**Decision summary.** V3 commits to **zero operational margin** on every order. The order is the exact count of expected attendees with their preference or request applied. No flat margin, no walkup buffer, no tutor buffer, no ML prediction adjustment. Walkups, unexpected attendees, and opted-out kids who change their mind on the day are not served; they are told to have their parents email Padea to update their status, and the system handles them from the next session run. The opted-out kid's tutor app surface gains a small "request opt-back-in" checkbox that, when ticked, triggers an autonomous email to the parent asking them to confirm and submit dietary tags + approved meal set. Aside from this checkbox, every prediction, reconciliation, and buffer concept from V1 is cut.

#### The operational scenario

**Orders contain exactly the expected cohort.** For a session at MBBC on Monday with twelve enrolled kids and one absence for that date, the order is eleven meals (one per kid, drawn from preferences + requests). No additional buffer for walkups, no extra for tutors who might eat, no margin for uncertainty. The order count tracks the expected attendance count directly.

**Walkups (unregistered or unexpected attendees) get no meal.** A kid who didn't get ordered for and shows up wanting food doesn't get fed by Padea that day. Cases:

- *Opted-out kid changes their mind on the day.* They told their parent they didn't want catering at term start; mid-term they see their friends eating and want in. They don't get a meal that session; the tutor can flag the opt-back-in checkbox (see below) which fires the parent email; from the next session run after the parent submits, the kid is in rotation.
- *Truly unexpected attendee (sibling tagging along, paperwork-pending new enrolment).* Handled before dinner by the school's normal attendance processes per Group 9. Catering system has no concept of them.
- *Late absence walkback (kid was marked absent but turns up).* Whatever meal was ordered for them was either redistributed or wasted; no special handling.

In rare cases, an absent kid's unused meal might be available for a walkup — but the system doesn't model or assume this; the manager handles in-the-moment redistribution by their own discretion.

**Opt-back-in checkbox on opted-out kids in the tutor app.** Where opted-in kids see the rating box, opted-out kids see the opt-out label (V3-PV-01). V3 adds a small checkbox under the label: *"student wishes to opt back in for meals."* Ticking and submitting fires an autonomous email to the parent — same structure as the original enrolment email (request for dietary tags and approved meal set for the current caterer). No operator approval required because the email is parent-facing and carries no commercial-relationship risk. From the next session run after the parent submits, the kid is in rotation.

**Send-once tracking on opt-back-in email.** A tutor ticking the checkbox triggers exactly one email per kid per opt-out period. If the parent doesn't respond, the tutor ticking the checkbox again next week does *not* fire a second email — the system tracks that the email has already gone. Repeated ticks accumulate as a soft signal in the weekly report (kid ticked for opt-in three weeks running, parent hasn't responded) without spamming the parent.

**Faster cycle under per-session cadence.** Under V3-AI-01’s per-session cadence, a tutor’s opt-back-in tick on Monday evening fires the parent email at the next scheduled agent run — typically within 24–48 hours of the tick. If the parent responds before the next session’s T-72hrs order composition, the kid is included in that session’s order. ~3–4 days from kid’s interest to first meal under per-session cadence (vs ~7 days under a weekly-omnibus model).

**No reconciliation infrastructure beyond manager session reports.** V3-FB-01's manager report captures meals-left and names of kids who didn't eat at each session. That's the only post-session "what actually happened" data the system has. No formal session reconciliation table, no walkup count, no excess/shortfall structured count. The free-text comments on the manager report are where the operator catches the nuance.

**MOQ shortfalls handled per V3-OC-01.** Order goes through as composed; if MOQ floor isn't met, system pays the difference, notifies operator informationally, continues. Nothing changes here.

#### Structured fields

1. **Feature/table/system:** Zero operational margin policy applied uniformly across all orders. Tutor-app opt-back-in checkbox firing an autonomous parent email with send-once tracking. No walkup tracking, no buffer modelling, no prediction infrastructure.
2. **V2 status:** V2 carries `orders.margin_meals_per_session` and `orders.tutor_buffer_meals_per_session` columns. V2's order composition assumed a small flat margin (~10%). V2 has no walkup modelling. V2 has the opt-out boolean but no reversal flow.
3. **Requirement supported:** Reducing coordinator bottleneck (no margin tuning, no prediction tooling, no reconciliation surfaces to maintain); reliable delivery (operationally, "we order what we need" — caterers can plan around exact counts); visible operation (margin-related complexity removed from the decision log).
4. **Value score:** 3/5. The cut value is the savings — removing the V1 prediction infrastructure, buffer-tuning loops, and reconciliation table is a meaningful complexity reduction. The opt-back-in checkbox adds a small new capability but the bigger story is the deletion. Memo-worthy as a "we deleted the part" success.
5. **Complexity score:** 1/5. Removal of two columns from V2's orders table. One new boolean field on `feedback` (or wherever the opt-back-in tick is captured). One new email type in the outbound table (`opt_back_in_request_to_parent`). Autonomous send; no approval flow. Send-once tracking via querying outbound for prior matching emails.
6. **Bugs / fixability / onboarding risks:** Caterer occasionally bringing extra meals "just in case" might leave excess; manager note captures it; not a system bug. Tutor mis-ticking the opt-back-in checkbox produces a spurious parent email; recovery is a phone call. Real risk is operator drift — over time, "we used to have a 10% buffer, why doesn't the system have one anymore?" The memo flag makes the choice explicit and documents the trigger for revisiting.
7. **Decision:** **CUT (margins, predictions, walkups, reconciliation), ADD (opt-back-in tutor checkbox + parent email flow).** Zero operational margin committed. ML predictions CUT. Walkup events CUT. Per-parent reliability stats CUT. Buffer auto-tuning CUT. Session reconciliations table CUT (partial reconciliation absorbed by V3-FB-01's manager report). Tutor meals buffer CUT. Raw absence verbatim/structured split CUT.
8. **Schema impact (sketch):**
   - `orders.margin_meals_per_session` and `orders.tutor_buffer_meals_per_session` cut.
   - One new field on the `feedback` table (or a separate small table): a record that the opt-back-in checkbox fired for a kid at a given session, with `email_sent_at` timestamp to enforce send-once.
   - New email type in `outbound_emails.email_type` enum: `opt_back_in_request_to_parent`.
   - No new tables for predictions, walkups, reconciliations, or per-parent stats.
9. **Agent logic impact:**
   - Order composition: count enrolled kids who are not absent, not excluded, not opted-out for the target session date. Multiply by 1.0. That's the order count.
   - Opt-back-in checkbox handling: on tick, check whether an opt-back-in email has been sent for this kid since their opt-out was set; if not, draft and send the parent email autonomously, mark the timestamp; if yes, record the recurring tick in the feedback row but do not re-send.
   - Weekly report: include count of opt-back-in checkboxes ticked vs. resolved (parent responded and rejoined) as a soft signal.
10. **Notes for V4 optimisation:**
    - Operational margin (build trigger: caterer complaints about shortfall, or operator observation that walkup/no-show pattern causes regular waste).
    - Walkup tracking (build trigger: enough unregistered attendees that operator pattern-matching can't keep up).
    - Session reconciliations as a formal table (build trigger: feedback ecosystem matures and per-session ground-truth becomes a real query surface).
    - Per-parent reliability stats (build trigger: parents promoted to first-class (Group 9) AND walkup tracking comes back).
    - ML predictions (build trigger: 6+ months of attendance + reconciliation data + observable shortfall pattern).
    - Tutor meals as designed primitive (build trigger: tutor feedback (1C) becomes a real V4 candidate, which is itself gated on observed value gap).

#### Memo flags

- **Zero operational margin is a deliberate design call.** The V1 design carried walkup buffers, tutor buffers, and ML-predicted absence margins. V3 cut all three and the underlying margin field. The cost of being wrong: occasional walkup who doesn't get a meal that day. The cost saved: an entire prediction/reconciliation/tuning subsystem that produces output the operator doesn't reliably trust. Strong "we deleted the part" sentence: "we removed every margin concept from the system because each margin solved a problem we don't yet have data to model, and shipped a system that orders exactly what it knows it needs."
- **Walkups suffer one week of no-meal.** This is an accepted operational cost. The kid gets told to ask their parent to email Padea about opting back in. From the next session run, they're in rotation. The week of no-meal is the forcing function that keeps opt-out as a real choice rather than a default-off the kid can flip on a whim. Memo this as an intentional friction.
- **Opt-back-in via the tutor app is the kid's signal channel that doesn't depend on the parent noticing first.** Tutor app surface for opted-out kids is minimal (no rating, no comment) but the opt-back-in checkbox lets the kid's interest surface to the system via the tutor's eye. The actual reversal still requires parent action; the system just makes the start of that conversation easier.
- **Autonomous parent emails for opt-back-in.** Unlike commercial-relationship emails (warning, RFP, cancellation — all queued for operator approval), the opt-back-in email is parent-facing and low-risk. Operator approval is reserved for commercial-relationship messages; parent-facing routine communications send autonomously.
- **Send-once tracking prevents tutor-app-driven email spam.** Repeated checkbox ticks fire one email per opt-out period. Recurring ticks accumulate as a soft signal in the weekly report.
- **No reconciliation surface beyond manager session reports.** V1 had a `session_reconciliations` table with structured attendance, walkup, excess, shortfall counts. V3 absorbs partial reconciliation into the manager's session feedback (meals-left, names of kids who didn't eat) and accepts the loss of structured count fidelity. V4 trigger documented if reconciliation becomes a real surface.

## Groups 12, 13, 14, 15 — Architecture, Session Location, Dietary Vocabulary, Deferred Production Concerns

### V3-AI-01: Per-session ordering cadence on Supabase Postgres

**Decision summary.** V3 abandons V2's "weekly Thursday omnibus" trigger model in favour of a per-session ordering cadence: each caterer-session pair receives its binding order email at 3 PM exactly 72 hours before the session, and a weekly consolidated summary per caterer is sent at 3:30 PM each Monday capturing the full week's commitments with MOQ floor and GST applied. The system runs ~5–7 times per week on a cron-style external scheduler, autonomous through weekends. The database is Supabase Postgres from day one — no SQLite-then-mirror dance. Hybrid event triggers, Haiku routing, dated session rows, MOQ-rules table, controlled dietary tag taxonomy, dietary severity, network-level dietary analytics, PII redaction, users/auth, forensic query interfaces, simulators, anomaly detection, school-attributes table, dietary-resolution pending state — all CUT and DEFERRED with V4 build triggers.

#### The operational scenario

**Per-session order cadence, not weekly omnibus.** Each session a Padea caterer is committed to gets exactly one order email, sent at 3 PM on the day three days before the session. Monday session → Friday 3 PM. Tuesday → Saturday 3 PM. Wednesday → Sunday 3 PM. Thursday → Monday 3 PM. (V3's data has no Friday sessions; the pattern generalises if added.) Each email is binding from the moment it's sent — no provisional/final distinction. The caterer prepares for whatever's in the email; the email is the contract.

**Order email body lists meal-name + allocated kid per line.** This is load-bearing for two reasons. One: the caterer needs to know what to prepare, and meal names disambiguate ("Chicken Caesar Salad" not "salad"). Two: the named allocations are how feedback attaches to specific kids in V3-FB-01 — the order is the source-of-truth for "what did Sam get on March 14th." Email structure: header (school, session, time, building, room), then meal-by-meal breakdown ("Chicken — Sam Smith. Pasta — Lily Chen. Vegetarian curry — Marcus Patel..."), then per-session totals, then expected cost.

**Weekly consolidated summary at Monday 3:30 PM per caterer.** After the week's individual order emails have gone out (Friday for Monday's session, Saturday for Tuesday's, etc.), the system produces a single summary per caterer at 3:30 PM Monday. The summary aggregates that caterer's full week — total meals across all their Padea sessions, MOQ tier hit, MOQ floor applied if relevant, GST line per the caterer's `price_includes_gst` and `gst_rate_percent` flags, expected total. This is the canonical document for spending tracking and the document against which payment crystallises.

**Payment crystallises Monday 3:30–4:00 PM.** Operator-handled. The payment mechanism (Padea transfers, caterer debits, accounting system processes, etc.) is unknown from the brief and explicitly memo-flagged. V3 records the expected total on the summary; the actual payment flow happens outside the system. V4 build trigger: payment integration (Stripe, accounting software, bank API) becomes worth building when V3's operator labour for payment handling becomes a bottleneck.

**Operator checks emails over the weekend.** Saturday and Sunday agent runs produce order emails autonomously. Any escalations from those runs surface in the decision log; operator's expected to glance at it over the weekend. Commercial-relationship emails (warning, RFP, cancellation per V3-CM-01) still require operator approval — those won't auto-send on weekends; they queue for the next time the operator approves them.

**Cron-style scheduler.** External scheduler (Python `schedule` library, system cron, or Supabase scheduled functions) wakes the agent at the right times. The agent's logic on invocation: "what session is exactly 72 hours from now? If any, compose and send the order. Is it Monday 3:30 PM? If so, generate the week's consolidated summaries for each caterer." The trigger is a scheduling concern; the agent's only knowledge is "I've been invoked, here's what time it is, here's what I should do."

**Inbound polling per run.** Each agent run starts with a Gmail API poll (V3-CM-01) for new inbound mail. Under per-session triggers, that's 5–7 polls per week instead of one — more responsive, processes absences and replies as they arrive rather than waiting for Thursday. Memo flag: the agent might see the same inbound email across multiple runs if classification is ambiguous; idempotent classification (using `gmail_message_id` as a dedup key) prevents double-processing.

**Supabase Postgres from day one.** No SQLite-local-with-mirror-on-submission. Schema lives in Supabase Postgres as Postgres DDL; the repo carries the SQL files for reproducibility; judges access via the Supabase project link in the "Database Access" deliverable. Application code connects via the standard Postgres connection string in an environment variable.

**Room field on session_slots.** V2 had `building` on schools and nothing for room. V3 adds `room` to session_slots so caterer-facing order emails can give complete delivery directions ("Building A, Room 12"). Per-(school, day-of-week) constant; per-date variation is V4 territory (13B).

**Per-date manager variation handled implicitly via session_tutor_assignments.** V3-IL-01's assignment model is per-session, not per-(school, day-of-week). A standin manager covering a one-off session just gets an assignment row for that session. No separate mechanism needed. Memo-flagged quiet win.

**Dietary tags as a controlled vocabulary with junction.** V3-FB-01 introduced `dietary_tags` and `enrolment_dietary_tags`. The taxonomy is operator-extensible (any new tag can be added through the database or admin tooling). No severity field — V3 treats every dietary tag as safety-critical by default. V4 build trigger: data ingestion brings severity (school health forms, parent-provided severity markers).

**Hybrid event triggers, Haiku routing, MOQ rules table, dietary trend analytics, PII redaction, users/auth, forensic query UI, simulators, anomaly detection, school attributes table, dietary-resolution pending state — all cut.** Each with a documented V4 build trigger.

#### Structured fields

1. **Feature/table/system:** Per-session ordering cadence with T-72hrs trigger and Monday 3:30 PM consolidated summary; cron-style external scheduler running 5–7 times per week; Supabase Postgres as the database from day one; `room` field on session_slots; per-date manager variation via existing assignment table; dietary tags + junction (already committed via V3-FB-01).
2. **V2 status:** V2 has weekly Thursday omnibus cadence with one order per (caterer, week) emailed at Thursday 3 PM. SQLite local, no Postgres, no Supabase. Session_slots have building (via schools) but no room. Manager identity is denormalised on session_slots. Dietary as JSON `dietary_flags`. No event triggers, no Haiku routing, no MOQ rules table, no analytics, no PII redaction, no auth, no forensic UI, no simulator, no anomaly detection, no attributes table.
3. **Requirement supported:** Reliable delivery (every caterer gets the same 72-hour prep window; no school disadvantaged by cadence; tight Monday session turnaround managed by operational discipline); reducing coordinator bottleneck (system runs autonomously through weekends; consolidated summary collapses the week's commitments into one operator-facing document); visible operation (each order email lists meals with kid attribution, summary email surfaces MOQ + GST + expected total); dietary safety (controlled dietary taxonomy with junction unlocks proper menu filtering and enrolment tracking).
4. **Value score:** 4/5. The per-session cadence is the architectural win — fair to caterers, tighter feedback loop on absences, consolidated summary as canonical spending document. Supabase from day one is the demo-quality win (brief recommends it; native Postgres is the strongest "Database Access" deliverable). Room field is small but important. Most other items in this group are cuts, and the value of those cuts is real (avoided complexity, deferred infrastructure).
5. **Complexity score:** 3/5. Cron-style scheduler implementation (~30–60 min Python + cron config or Supabase scheduled functions). Schema migration from SQLite syntax to Postgres syntax (manageable — Postgres is a superset for V3's needs). Two new email templates (session_order, weekly_consolidated_summary). Aggregation tool for the consolidated summary. One column on session_slots. Per-run Gmail polling already covered by V3-CM-01 with minimal cadence change. Decision log regeneration after each run already covered by V3-OE-01.
6. **Bugs / fixability / onboarding risks:** Cron misfires (job doesn't run at expected time) — mitigated by per-run idempotency (running twice produces the same outbound state because dedup happens at email level). Postgres syntax differences from SQLite (mostly around JSON handling, date functions, and auto-increment) — caught at first migration attempt. Monday-session caterers operating on tight turnaround (Friday 3 PM order → Monday 4 PM delivery, 73 hours) — the email IS final from Friday, so caterers prep against it; the Monday 3:30 PM summary is administrative; no real risk if caterers treat order emails as binding. Weekend escalations not seen until operator checks email — acceptable for V3 demo; production hardening trigger documented. Supabase free-tier limits at scale — well within bounds for V3 demo.
7. **Decision:** **ADD BACK (per-session cadence, summary, room, Supabase), CUT (hybrid triggers, Haiku, MOQ table, dated sessions, dietary severity/analytics/pending, PII, auth, forensic UI, simulator, anomaly detection, attributes table).** Each cut has a V4 build trigger.
8. **Schema impact (sketch):**
   - Migration of all V2 + V3-locked schema from SQLite to Postgres DDL.
   - Extend `session_slots`: add `room` (text, nullable).
   - No new tables in this group (`dietary_tags`, `enrolment_dietary_tags`, `tutors`, `session_tutor_assignments` all already committed in prior groups).
   - No `email_templates` table, no `incoming_emails` table, no `inbound_correspondence` table, no `school_attributes` table, no `caterer_moq_rules` table, no `students` table, no `parents` table.
9. **Agent logic impact:**
   - Scheduler invokes the agent at the right times; agent's `main()` looks at the current time and determines what action to take (per-session order composition, weekly summary, or weekend inbound poll only).
   - New tool: `compose_session_order(session_id)` — computes the per-session order, drafts the email, calls `gmail_send`, writes to outbound_emails table.
   - New tool: `compose_weekly_summary(caterer_id, week_start)` — aggregates the week's orders for the caterer, computes MOQ floor and GST, drafts the summary email, sends, writes to outbound_emails.
   - Gmail inbound polling integrated as a step that fires at the start of every agent invocation.
   - Decision log regeneration after every run (per V3-OE-01); the log groups events by week for readability.
10. **Notes for V4 optimisation:**
    - Hybrid event triggers (build trigger: caterer non-response or other mid-session-cycle event becomes operationally urgent).
    - Haiku 4.5 routing (build trigger: production deployment where per-call cost or latency matters).
    - Dated session rows (build trigger: routine per-date variation in time/room/cohort that exclusions can't express).
    - MOQ rules as separate table (build trigger: MOQ tiers vary across caterers or change over time).
    - Dietary severity field (build trigger: severity data becomes available from any source).
    - Network-level dietary analytics (build trigger: term reports become a recurring leadership deliverable).
    - PII redaction (build trigger: real deployment with real parent data).
    - Users/auth (build trigger: operator team exceeds one person).
    - Forensic query UI (build trigger: non-engineer operators need routine forensic queries).
    - What-if simulators (build trigger: rotation becomes high-frequency enough to warrant pre-decision modelling).
    - Anomaly detection (build trigger: input data volume exceeds operator-by-eye review capacity).
    - School attributes table (build trigger: per-school operational variation exceeds what columns + prompt context can carry).
    - Dietary resolution pending state (build trigger: menu ingestion becomes a high-volume automated pipeline).
    - Payment integration (build trigger: operator labour for payment handling becomes a bottleneck).

#### Memo flags

- **Per-session cadence is the architectural design call of V3.** V2 inherited Thursday-for-all-week from the human's existing operation. We noticed that Thursday cadence was an artifact of the human's schedule, not a system requirement, and built a 72-hour-per-session cadence that's fair to every caterer regardless of which day they serve. The Monday 3:30 PM consolidated summary collapses the week's commitments into one spending-tracking document. Strong Functionality + Learning sentence: "the existing cadence was a human-calendar artifact; we replaced it with a system-native cadence that gives every caterer equal prep time."
- **Order emails are final from the moment they're sent.** No provisional/final distinction. Caterer treats every order email as binding. The Monday consolidated summary is administrative — it doesn't replace orders, it summarises them.
- **Payment is a known unknown.** The brief doesn't specify how Padea pays caterers. V3 assumes Monday 3:30–4:00 PM is the financial crystallisation window (transfer initiated by Padea or debit by caterer; unclear which). The summary email is the de-facto invoice from Padea's side. V3 doesn't model payment integration; this is V4 territory.
- **Operator checks email over weekends.** Saturday and Sunday agent runs send orders autonomously. Escalations from weekend runs sit until operator reads them — acceptable for V3 demo, production hardening trigger documented.
- **Supabase native from day one.** Brief recommends Supabase as the "harder" database option. Going Postgres-native rather than SQLite-with-mirror is a Taste call — judges accessing the database via the link see a real Postgres instance with the actual schema, not a snapshot from a local file.
- **Order email body shape carries operational and feedback weight.** Each order line is meal-name + allocated-kid. Meal names disambiguate prep; kid attribution lets V3-FB-01 attach feedback to specific (kid, meal) pairs. The order email is the source-of-truth document for "what did Sam get on March 14th."
- **Room field as the one missing piece.** V2 had building (at school level) but no room. Caterer emails couldn't say "Building A, Room 12." One column on session_slots fixes it; the brief explicitly mentions caterers asking for help finding session location.
- **Per-date manager variation handled via session_tutor_assignments.** V3-IL-01's assignment model is per-session, so a standin manager covering one session gets an assignment row for that session. Quiet win — V3 supports something V2 didn't, without adding any new mechanism.
- **Dietary safety: every tag is safety-critical by default.** No severity field means the system can't distinguish "preference" from "anaphylactic allergy." V3 chose to treat every dietary tag as if it were an allergy. Over-cautious, but the safe direction. V4 brings severity if data arrives carrying it.
- **Every deferred item carries a V4 build trigger.** Cutting is not silent absence; it's documented intent. The cuts list above carries a "build when this happens" condition for each item. Strong Learning-criterion sentence: "we documented every deferred capability with the operational signal that would justify building it later — deletion was active, not passive."

---

## Edge Cases and Accepted Gaps

This appendix inventories every edge case considered during V3 design. Entries are either handled in the design (with a reference to the decision block) or explicitly out of scope (with the reason and, where relevant, a V4 build trigger). The purpose is to make the design’s coverage transparent and to document deliberate gaps so they’re not mistaken for oversights.

### Handled

- **Mid-term enrolment.** Operator handles end-to-end via V3-PV-01 + V3-EL-01. No auto parent email.
- **Late mid-term enrolment (after T-72hrs).** Kid misses next session, waits for following one (V3-PV-01 amendment).
- **Routine absence.** Gmail polled at each run, classifies absence email, creates row, kid excluded from next order composition (V3-CM-01 + V3-AI-01).
- **Late absence (after order sent).** Recorded for audit but doesn’t amend order. Caterer prepares meal anyway (V3-AI-01).
- **Walkup / opt-out wants meal.** Tutor app checkbox triggers parent email; standard reversal flow follows (V3-MP-01).
- **Unexpected attendee (sibling, paperwork-pending).** Handled before dinner by school processes; catering system has no concept (V3-IL-01).
- **Caterer non-confirmation.** Assumed OK unless Gmail bounce/error (V3-CM-01).
- **Caterer RFP tie.** Operator decides manually (V3-CR-01).
- **Caterer improves after warning.** Rolling means catch it automatically; operator manually dismisses warning escalation (V3-FB-01).
- **Dietary contradiction.** Dietary tags are hard floor; system filters at every stage (V3-FB-01).
- **Mid-term dietary change.** Operator updates dietary tags directly on enrolment row (V3-PV-01).
- **Tutor missing data.** Null rating doesn’t feed mean; pattern signal in weekly report (V3-FB-01).
- **Manager missing session report.** Same as tutor missing data — null doesn’t feed mean (V3-FB-01).
- **Out-of-range scores.** Enum constraint at parsing layer (1–5 only); out-of-range escalates as malformed (V3-FB-01).
- **Duplicate tutor submission for same (kid, session).** Last write wins (V3-FB-01).
- **Dual-role manager-tutor at same session.** Two independent rater channels in feedback table (V3-IL-01).
- **School holiday.** Operator marks dates as full-school exclusions; agent skips order composition silently (V3-EL-01).
- **Exam-week MOQ dip.** Order goes through; MOQ floor paid; recurring patterns surface in weekly report (V3-OC-01).
- **Same-name students at same session.** Operator discipline at enrolment entry uses distinguishable names; database IDs exist for system attribution (V3-IL-01).
- **Gmail send failure.** Outbound row marked failed; escalation fires; operator decides retry/manual/skip (V3-CM-01).
- **Unclassifiable inbound.** Escalation with sender, subject, timestamp, Gmail message ID; operator reads in Gmail (V3-CM-01).
- **Inbound for unknown thread.** Falls through to unclassified, escalates (V3-CM-01).
- **Opt-out elicitation.** Single-click response in term-start parent email (V3-PV-01).
- **Opt-out reversal.** Tutor checkbox triggers parent email; operator handles reversal capture; send-once tracking prevents spam (V3-MP-01).

### Out of scope

- **Parent never responds to enrolment email.** No timeout-driven escalation, no automatic default-to-opt-out. Operator notices during weekly review and handles manually. V4 trigger: parent-no-response becomes a routine recurring case.
- **Parent revokes consent mid-term via structured flow.** Mid-term changes go through direct operator handling. V4 trigger: multiple structured parent-state-change emails per term.
- **Caterer cancels delivery last-minute.** Unclassified inbound; operator handles via direct communication. No alternative-routing flow. V4 trigger: if last-minute cancellations become non-rare, build emergency RFP to regional caterer list.
- **Caterer RFP counter-offer.** Unclassified inbound; operator reviews and decides. V4 trigger: repeated RFP counter-offers become recurring.
- **Email in spam folder.** No read-receipt detection. V4 trigger: read-receipts or follow-up reminder logic if engagement metrics matter.
- **Mid-run agent failure.** Idempotent runs (database is source of truth; outbound emails dedupe). Operator re-runs manually. V4 trigger: run failures become regular.
- **Database inconsistency.** No periodic consistency checks. V3 trusts operator discipline and FK constraints. V4 trigger: operator team grows or errors recur.
- **Daylight saving time transitions.** Cron may fire 1 hour off during DST changeover. Agent’s “what session is 72 hours away” logic absorbs this. V4 trigger: never anticipated to build.
- **Multi-time-zone operation.** V3 single time zone (Australia/Brisbane). UTC internal, operator-local display. V4 trigger: Padea expands to different timezone.
- **Zero-cohort session.** Vanishingly rare; not planned for. Operator handles manually if it ever happens.
- **Cross-school student identity.** No data shows multi-school kids. Operator manually notes any link. V4 trigger: real cross-school case emerges.
- **Padea-vs-school attendance integration.** Padea marks attendance independently. V4 trigger: never anticipated.
- **Silent no-show (kid in order but doesn’t show, no absence email).** Manager records via “kids who didn’t eat” field. V4 trigger: school attendance integration.
- **Multiple simultaneous operators.** V3 single operator. V4 trigger: operator team > 1.
- **Payment integration (Stripe, accounting, bank API).** V3 records expected total; payment outside system. V4 trigger: operator labour for payment becomes bottleneck.
- **PII redaction / data retention policies.** Real-deployment precondition. V4 trigger: real deployment with real parent data.
- **Anomaly detection on input changes.** Operator review covers it. V4 trigger: input volume exceeds operator review capacity.
- **What-if simulators.** V4 trigger: rotation becomes high-frequency.
