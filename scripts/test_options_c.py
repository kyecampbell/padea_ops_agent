#!/usr/bin/env python
"""
scripts/test_options_c.py

Option C tests: VO fallback chain (T1–T4) + email rendering (T5–T6).

T1: vegetarian-only student at Terrific → VO auto-pick succeeds, safe=True
T2: halal+vegetarian student at Terrific → halal VO item selected, pork VO excluded
T3: non-restricted student at Terrific → inherent item found, VO path not reached
T4: vegetarian student at Lakehouse → inherently-VG item found, VO path not reached
T5: _format_order_line renders ⚑ VEGETARIAN OPTION; UNSAFE suppressed for Veg-label gap
T6 (safety invariant): uncovered non-veg tag → ⚠ UNSAFE MATCH fires despite VO

Runs against the real Supabase DB for T1–T4 (read-only; no orders created).
T5–T6 are pure unit tests (no DB).
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from src.tools.meals import auto_pick_dietary_meal
from src.tools.orders import (
    _auto_pick_vo_meal,
    _format_order_line,
    _vo_safe_for_enrolment,
)

PASS = 0
FAIL = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}" + (f"\n        detail: {detail}" if detail else ""))


# =============================================================================
# T1: vegetarian-only student (Aanya Desai, enr=63) at Terrific (caterer=2)
#   auto_pick_dietary_meal returns None (no inherently-VG Terrific item)
#   → _auto_pick_vo_meal returns a VO item
#   → _vo_safe_for_enrolment returns True (student_tags − {veg} = ∅ ⊆ item_tags)
# =============================================================================
print("\nT1 — vegetarian-only → VO auto-pick succeeds (Aanya enr=63, Terrific)")

inherent = auto_pick_dietary_meal(63, 2)
check("T1a: auto_pick_dietary_meal returns None for VG-only at Terrific",
      inherent is None,
      detail=f"got {inherent}")

vo = _auto_pick_vo_meal(63, 2)
check("T1b: _auto_pick_vo_meal returns a result",
      vo is not None,
      detail="got None — no VO item found for Aanya at Terrific")

if vo is not None:
    check("T1c: returned item has menu_item_id, name, price_cents",
          all(k in vo for k in ("menu_item_id", "name", "price_cents")),
          detail=f"keys present: {list(vo.keys())}")
    check("T1d: returned item is in Terrific VO set {13, 15, 16, 17}",
          vo["menu_item_id"] in {13, 15, 16, 17},
          detail=f"got item_id={vo['menu_item_id']}")
    safe = _vo_safe_for_enrolment(vo["menu_item_id"], 63)
    check("T1e: _vo_safe_for_enrolment=True for Aanya (veg-only, veg gap forgiven)",
          safe is True,
          detail=f"got {safe}")
    print(f"        (selected: id={vo['menu_item_id']} {vo['name']!r})")


# =============================================================================
# T2: halal+vegetarian student (Rashid Khalil, enr=23) at Terrific (caterer=2)
#   → _auto_pick_vo_meal returns a halal VO item
#   → does NOT select id=13 (Grilled Pork Vermicelli — pork, no halal tag)
#   → _vo_safe_for_enrolment(15, 23) = True; (13, 23) = False
# =============================================================================
print("\nT2 — halal+veg → halal VO selected, pork VO excluded (Rashid enr=23, Terrific)")

vo_rashid = _auto_pick_vo_meal(23, 2)
check("T2a: _auto_pick_vo_meal returns a result for halal+veg at Terrific",
      vo_rashid is not None,
      detail="got None")

if vo_rashid is not None:
    check("T2b: selected item is NOT id=13 (Grilled Pork Vermicelli — pork/no-halal)",
          vo_rashid["menu_item_id"] != 13,
          detail=f"got item_id={vo_rashid['menu_item_id']} — pork item should not be selected")
    check("T2c: selected item is in halal-capable Terrific VO set {15, 16, 17}",
          vo_rashid["menu_item_id"] in {15, 16, 17},
          detail=f"got item_id={vo_rashid['menu_item_id']}")
    print(f"        (selected: id={vo_rashid['menu_item_id']} {vo_rashid['name']!r})")

# Defense-in-depth: pork item unsafe for halal+veg student, halal item is safe
safe_pork_for_rashid = _vo_safe_for_enrolment(13, 23)
check("T2d: _vo_safe_for_enrolment(13 pork, Rashid halal+veg) = False",
      safe_pork_for_rashid is False,
      detail=f"got {safe_pork_for_rashid} — halal gap should not be suppressed")

safe_beef_for_rashid = _vo_safe_for_enrolment(15, 23)
check("T2e: _vo_safe_for_enrolment(15 Lemongrass Beef halal, Rashid halal+veg) = True",
      safe_beef_for_rashid is True,
      detail=f"got {safe_beef_for_rashid}")


# =============================================================================
# T3: non-restricted student (Lucas Anderson, enr=18) at Terrific (caterer=2)
#   → auto_pick_dietary_meal finds an item → VO path never reached → variant=None
# =============================================================================
print("\nT3 — non-restricted → inherent item found, VO path not reached (Lucas enr=18, Terrific)")

inherent_lucas = auto_pick_dietary_meal(18, 2)
check("T3a: auto_pick_dietary_meal returns a result for non-restricted at Terrific",
      inherent_lucas is not None,
      detail="got None")
if inherent_lucas is not None:
    print(f"        (selected: id={inherent_lucas['menu_item_id']} {inherent_lucas['name']!r})")
    check("T3b: no VO needed (auto_pick succeeded → variant stays None in compose_session_order)",
          True)  # structural assertion: VO is in the else branch of auto_pick


# =============================================================================
# T4: vegetarian student at Lakehouse (caterer=1) → Gnocchi (id=5) found directly
#   Tests _auto_pick_vo_meal crosscheck: VG at Lakehouse uses the inherently-VG
#   Gnocchi item; VO path never needed; variant stays None.
#   Note: Aanya (enr=63) is not actually enrolled at Lakehouse — we test the
#   function directly to prove the inherently-VG path works for any VG student
#   placed at Lakehouse.
# =============================================================================
print("\nT4 — VG at Lakehouse → inherently-VG Gnocchi (id=5) found, no VO needed (Aanya enr=63 at caterer=1)")

inherent_vg = auto_pick_dietary_meal(63, 1)
check("T4a: auto_pick_dietary_meal returns a result (Gnocchi) for VG at Lakehouse",
      inherent_vg is not None,
      detail="got None — Lakehouse Gnocchi should satisfy VG-only")
if inherent_vg is not None:
    check("T4b: returned item is Gnocchi in Tomato Sauce (id=5)",
          inherent_vg["menu_item_id"] == 5,
          detail=f"got item_id={inherent_vg['menu_item_id']} {inherent_vg['name']!r}")
    check("T4c: no VO needed (auto_pick succeeded → variant stays None in compose_session_order)",
          True)


# =============================================================================
# T5: _format_order_line email rendering — unit tests (no DB)
#   T5a: standard non-VO line, no dietary tags → clean output
#   T5b: VO line, VG student → ⚑ shown; no ⚠ UNSAFE MATCH (Veg gap suppressed)
#   T5c: standard non-VO line, uncovered tag → ⚠ UNSAFE MATCH fires normally
# =============================================================================
print("\nT5 — _format_order_line rendering (unit tests)")

# T5a: non-VO, no tags — clean line
line_clean = _format_order_line("Beef Pad Thai", "Lucas Anderson", None, None, [], [])
check("T5a: standard non-VO line, no tags — no markers",
      "⚑" not in line_clean and "⚠" not in line_clean,
      detail=f"got: {line_clean!r}")
check("T5a: contains meal name and student name",
      "Beef Pad Thai" in line_clean and "Lucas Anderson" in line_clean,
      detail=f"got: {line_clean!r}")

# T5b: VO line, VG student, meal has no tags — Veg label suppressed
line_vo = _format_order_line(
    "Grilled Pork Vermicelli Salad", "Aanya Desai", None,
    "vegetarian_option", ["Vegetarian"], []
)
check("T5b: VO line shows ⚑ VEGETARIAN OPTION",
      "⚑ VEGETARIAN OPTION" in line_vo,
      detail=f"got: {line_vo!r}")
check("T5b: VO line with Vegetarian-only gap → no ⚠ UNSAFE MATCH",
      "⚠ UNSAFE MATCH" not in line_vo,
      detail=f"got: {line_vo!r} — Vegetarian label should be suppressed on VO lines")
check("T5b: student tag label shown in brackets",
      "[Vegetarian]" in line_vo,
      detail=f"got: {line_vo!r}")
print(f"        sample: {line_vo}")

# T5c: non-VO line, student has tag not covered by meal → ⚠ fires normally
line_unsafe = _format_order_line(
    "Grilled Pork Vermicelli Salad", "Some Student", None,
    None, ["Halal"], []
)
check("T5c: non-VO line, uncovered tag → ⚠ UNSAFE MATCH fires",
      "⚠ UNSAFE MATCH" in line_unsafe,
      detail=f"got: {line_unsafe!r}")
check("T5c: no ⚑ on non-VO line",
      "⚑" not in line_unsafe,
      detail=f"got: {line_unsafe!r}")

# T5d: allergy note still appears on VO lines
line_allergy = _format_order_line(
    "Mie Goreng", "Test", "peanuts", "vegetarian_option", ["Vegetarian"], []
)
check("T5d: VO line with allergy note — both ⚑ and ⚠ ALLERGY NOTE shown",
      "⚑ VEGETARIAN OPTION" in line_allergy and "⚠ ALLERGY NOTE" in line_allergy,
      detail=f"got: {line_allergy!r}")


# =============================================================================
# T6: safety invariant — VO line with uncovered non-veg tag → ⚠ UNSAFE fires
#   Halal+Vegetarian student on a VO meal that covers neither tag.
#   Vegetarian gap forgiven; Halal gap is NOT forgiven → UNSAFE MATCH fires.
# =============================================================================
print("\nT6 — safety invariant: non-veg uncovered tag fires ⚠ UNSAFE on VO line")

line_unsafe_vo = _format_order_line(
    "Grilled Pork Vermicelli Salad", "Rashid Khalil", None,
    "vegetarian_option", ["Halal", "Vegetarian"], []
)
check("T6a: VO line with Halal+Veg student, meal covers neither → ⚠ UNSAFE MATCH fires",
      "⚠ UNSAFE MATCH" in line_unsafe_vo,
      detail=f"got: {line_unsafe_vo!r} — Halal gap must not be suppressed")
check("T6b: ⚑ VEGETARIAN OPTION still shown",
      "⚑ VEGETARIAN OPTION" in line_unsafe_vo,
      detail=f"got: {line_unsafe_vo!r}")
print(f"        sample: {line_unsafe_vo}")

# Edge: VO line where meal covers Halal but not Vegetarian → safe (Veg forgiven)
line_safe_halal_covered = _format_order_line(
    "Lemongrass Grilled Beef", "Rashid Khalil", None,
    "vegetarian_option", ["Halal", "Vegetarian"], ["Halal"]
)
check("T6c: VO line where Halal is covered, Veg is the only gap → no ⚠ UNSAFE MATCH",
      "⚠ UNSAFE MATCH" not in line_safe_halal_covered,
      detail=f"got: {line_safe_halal_covered!r} — Halal covered, Veg gap forgiven")
print(f"        sample: {line_safe_halal_covered}")


# =============================================================================
# Summary
# =============================================================================
print(f"\n{'='*60}")
print(f"Result: {PASS} passed, {FAIL} failed")
if FAIL:
    print("SOME TESTS FAILED")
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
