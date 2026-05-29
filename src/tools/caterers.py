"""
src/tools/caterers.py
Caterer reach, cost projection, and MOQ tools for the Padea operations agent.

Reads: caterers_within_range, project_weekly_cost, check_weekly_moq
Writes: none

Distance model (caterers_within_range):
  V4 schema carries postcodes only — no lat/lon, no stored distance.
  A hardcoded dict maps the 8 QLD demo postcodes to (lat, lon) centroids.
  geopy.distance.geodesic() gives Karney's geodesic distance in km.
  Measurement: school.postcode centroid → caterer.home_postcode centroid.
  Comparison: geodesic_km <= caterer.max_delivery_km.
  Raises ValueError on any postcode not in the dict — never silently wraps.
"""
from __future__ import annotations

from datetime import date, timedelta

from geopy.distance import geodesic

from src.ingest.db import get_conn

# ---------------------------------------------------------------------------
# QLD postcode → (lat, lon) centroids — covers all demo school + caterer postcodes
# ---------------------------------------------------------------------------
_QLD_POSTCODES: dict[str, tuple[float, float]] = {
    "4000": (-27.4698, 153.0251),   # Brisbane CBD            — GyG
    "4068": (-27.5100, 152.9706),   # Indooroopilly           — ISHS + Kenko
    "4101": (-27.4820, 153.0130),   # South Brisbane/West End — Terrific
    "4109": (-27.5644, 153.0680),   # MacGregor               — MSHS
    "4127": (-27.6273, 153.1152),   # Daisy Hill              — JPC
    "4151": (-27.4961, 153.0533),   # Coorparoo               — Loreto
    "4165": (-27.5836, 153.2512),   # Victoria Point          — MBBC + Lakehouse
    "4170": (-27.4697, 153.0930),   # Cannon Hill             — CHAC
}


def _distance_km(postcode_a: str, postcode_b: str) -> float:
    """Geodesic distance in km between two QLD postcode centroids."""
    if postcode_a not in _QLD_POSTCODES:
        raise ValueError(f"Postcode {postcode_a!r} not in known QLD postcode dict")
    if postcode_b not in _QLD_POSTCODES:
        raise ValueError(f"Postcode {postcode_b!r} not in known QLD postcode dict")
    return geodesic(_QLD_POSTCODES[postcode_a], _QLD_POSTCODES[postcode_b]).km


def caterers_within_range(
    school_id: int,
    exclude_caterer_id: int | None = None,
) -> list[dict]:
    """
    Return caterers whose home_postcode centroid is within their own
    max_delivery_km radius of the school's postcode centroid.

    exclude_caterer_id: omits this caterer from the returned list entirely —
    used to exclude the incumbent from an RFP candidate list, not a distance
    filter. The caterer is skipped before the distance check runs.

    Raises ValueError if school_id not found or a postcode is not in the
    known QLD postcode dict.

    Returns list of dicts with:
        caterer_id, name, contact_email, home_postcode,
        max_delivery_km, delivery_fee_cents, distance_km
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT postcode FROM schools WHERE id = %s", (school_id,))
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"school_id {school_id} not found")
            school_postcode: str = row[0]

            if exclude_caterer_id is not None:
                cur.execute(
                    """
                    SELECT id, name, contact_email, home_postcode,
                           max_delivery_km, delivery_fee_cents
                    FROM caterers
                    WHERE id != %s
                    """,
                    (exclude_caterer_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT id, name, contact_email, home_postcode,
                           max_delivery_km, delivery_fee_cents
                    FROM caterers
                    """
                )
            caterer_rows = cur.fetchall()

    results: list[dict] = []
    for cid, name, email, home_pc, max_km, delivery_fee in caterer_rows:
        dist = _distance_km(school_postcode, home_pc)
        if dist <= max_km:
            results.append({
                "caterer_id":       cid,
                "name":             name,
                "contact_email":    email,
                "home_postcode":    home_pc,
                "max_delivery_km":  max_km,
                "delivery_fee_cents": delivery_fee,
                "distance_km":      round(dist, 2),
            })

    return results


def project_weekly_cost(caterer_id: int, school_id: int) -> dict:
    """
    Project the weekly catering cost for this caterer at this school.

    V3-MP-01 zero margin: no Padea markup — projected_total = caterer prices only.
    All prices are normalised to GST-inclusive so cross-caterer projections are
    comparable regardless of whether a caterer quotes GST-inclusive or exclusive.

    Money: all integer cents. per_meal_price_cents = ROUND(AVG(price_cents))::int
    then rounded again to int after GST normalisation if price_includes_gst=False.

    MOQ: variety_count=5 assumed for projection — a full rotation across a typical
    cohort produces 4-6 varieties; 5 is the middle tier. moq_floor_cents is None
    if projected_items meets the tier; an int otherwise.

    Returns:
        cohort_size: int           — currently active, opted-in enrolments at school
        per_meal_price_cents: int  — avg active menu item price, GST-inclusive (rounded)
        delivery_fee_cents: int    — per-delivery flat fee, GST-inclusive (multiply by sessions for weekly total)
        moq_floor_cents: int|None  — extra cost if projected items < moq_5 tier
        projected_total_cents: int — total weekly cost, GST-inclusive, delivery × sessions + meals + any MOQ floor
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Cohort: active, opted-in enrolments at school as of today
            cur.execute(
                """
                SELECT count(*)
                FROM enrolments
                WHERE school_id = %s
                  AND opted_out_of_catering = false
                  AND (current_period_end_date IS NULL
                       OR current_period_end_date > CURRENT_DATE)
                """,
                (school_id,),
            )
            cohort_size: int = cur.fetchone()[0]

            # Average active menu item price — one round() produces the int
            cur.execute(
                """
                SELECT round(avg(price_cents))::int
                FROM menu_items
                WHERE caterer_id = %s AND active = true
                """,
                (caterer_id,),
            )
            per_meal_price_cents: int = cur.fetchone()[0] or 0

            # Active session slots at school → weekly session count
            cur.execute(
                "SELECT count(*) FROM session_slots WHERE school_id = %s AND active = true",
                (school_id,),
            )
            sessions_per_week: int = cur.fetchone()[0]

            # Caterer fees, MOQ tiers, and GST basis
            cur.execute(
                """
                SELECT delivery_fee_cents, moq_5_items,
                       price_includes_gst, gst_rate_percent
                FROM caterers
                WHERE id = %s
                """,
                (caterer_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"caterer_id {caterer_id} not found")
            delivery_fee_cents: int
            moq_5: int | None
            price_includes_gst: bool
            gst_rate_percent: float
            delivery_fee_cents, moq_5, price_includes_gst, gst_rate_percent = row

    # Normalise to GST-inclusive — one round() per value if needed
    if not price_includes_gst:
        per_meal_price_cents = round(per_meal_price_cents * (1 + gst_rate_percent / 100))
        delivery_fee_cents = round(delivery_fee_cents * (1 + gst_rate_percent / 100))

    projected_items = cohort_size * sessions_per_week
    projected_natural_cents = projected_items * per_meal_price_cents + delivery_fee_cents * sessions_per_week

    moq_floor_cents: int | None = None
    if moq_5 is not None and projected_items < moq_5:
        moq_floor_cents = (moq_5 - projected_items) * per_meal_price_cents

    projected_total_cents = projected_natural_cents + (moq_floor_cents or 0)

    return {
        "cohort_size":           cohort_size,
        "per_meal_price_cents":  per_meal_price_cents,
        "delivery_fee_cents":    delivery_fee_cents,
        "moq_floor_cents":       moq_floor_cents,
        "projected_total_cents": projected_total_cents,
    }


def check_weekly_moq(caterer_id: int, week_of: date) -> dict:
    """
    Check MOQ compliance for a caterer in the ISO week containing week_of.

    Week = Monday–Sunday (ISO), matching session day_of_week 1=Mon...7=Sun.

    MOQ semantics: moq_N_items = minimum total items when the week's order
    contains exactly N distinct meal varieties (N ∈ {4, 5, 6}).
    moq_applicable = None if variety_count is outside {4, 5, 6}.

    shortfall and shortfall_cents are always returned as ints (0 if no shortfall).
    Never silently swallows: the agent inspects the return dict and escalates.

    shortfall_cents = shortfall × avg_price_cents_of_ordered_items.
    Falls back to caterer's avg active menu item price if no items ordered.

    Reads: orders, order_lines, menu_items, caterers
    Writes: none
    """
    week_start = week_of - timedelta(days=week_of.weekday())
    week_end = week_start + timedelta(days=6)

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Total items and distinct varieties for this caterer in the week
            cur.execute(
                """
                SELECT count(*), count(DISTINCT ol.menu_item_id)
                FROM order_lines ol
                JOIN orders o ON o.id = ol.order_id
                WHERE o.caterer_id = %s
                  AND o.session_date >= %s
                  AND o.session_date <= %s
                """,
                (caterer_id, week_start, week_end),
            )
            total_items, variety_count = cur.fetchone()

            # MOQ tiers
            cur.execute(
                """
                SELECT moq_4_items, moq_5_items, moq_6_items,
                       price_includes_gst, gst_rate_percent
                FROM caterers WHERE id = %s
                """,
                (caterer_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"caterer_id {caterer_id} not found")
            moq_4, moq_5, moq_6, price_includes_gst, gst_rate_percent = row

            # Average price of the ordered items for shortfall_cents calculation.
            # Falls back to caterer's avg active menu item price when no items ordered.
            if total_items > 0:
                cur.execute(
                    """
                    SELECT round(avg(mi.price_cents))::int
                    FROM order_lines ol
                    JOIN orders o ON o.id = ol.order_id
                    JOIN menu_items mi ON mi.id = ol.menu_item_id
                    WHERE o.caterer_id = %s
                      AND o.session_date >= %s
                      AND o.session_date <= %s
                    """,
                    (caterer_id, week_start, week_end),
                )
                avg_price_cents: int = cur.fetchone()[0] or 0
            else:
                cur.execute(
                    """
                    SELECT round(avg(price_cents))::int
                    FROM menu_items
                    WHERE caterer_id = %s AND active = true
                    """,
                    (caterer_id,),
                )
                avg_price_cents = cur.fetchone()[0] or 0

    # Normalise avg price to GST-inclusive for shortfall cost calculation
    if not price_includes_gst:
        avg_price_cents = round(avg_price_cents * (1 + gst_rate_percent / 100))

    moq_map: dict[int, int | None] = {4: moq_4, 5: moq_5, 6: moq_6}
    moq_applicable: int | None = moq_map.get(variety_count)

    shortfall: int = max(0, moq_applicable - total_items) if moq_applicable is not None else 0
    shortfall_cents: int = shortfall * avg_price_cents

    return {
        "total_items":     total_items,
        "moq_applicable":  moq_applicable,
        "shortfall":       shortfall,
        "shortfall_cents": shortfall_cents,
    }
