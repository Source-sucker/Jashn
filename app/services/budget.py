import json
import math
from pathlib import Path

from app.models.schemas import BudgetCategoryAllocation, BudgetReport

TEMPLATES_PATH = Path(__file__).parent.parent / "data" / "event_templates.json"

# ---------------------------------------------------------------------------
# Budget calculation constants — change these, not the function body
# ---------------------------------------------------------------------------
#: Extra weight given to the user's top-priority category.
PRIORITY_BOOST_FACTOR: float = 0.20
#: Default minimum weight floor for any category (fraction of allocable budget).
DEFAULT_FLOOR_PCT: float = 0.02
#: Minimum contingency reserve in rupees regardless of total budget.
MIN_CONTINGENCY_AMOUNT: int = 500
#: All monetary values are rounded to the nearest ROUNDING_UNIT rupees.
ROUNDING_UNIT: int = 100
#: Per-guest spend multiplier above which the plan is "comfortable".
FEASIBILITY_COMFORTABLE_MULTIPLIER: float = 1.3
#: Per-guest spend multiplier above which the plan is "tight" (below = "unrealistic").
FEASIBILITY_TIGHT_MULTIPLIER: float = 0.8


def load_event_templates() -> dict:
    with open(TEMPLATES_PATH, encoding="utf-8") as f:
        return json.load(f)


CATEGORY_LABELS = {
    "catering": "Catering & Beverages",
    "catering_prasad": "Community Feast (Langar/Prasad)",
    "venue": "Venue & Banquet",
    "venue_tent_setup": "Pandal, Tent & Seating",
    "venue_conference": "Hotel / Conference Venue",
    "decor_styling": "Decor, Florals & Stage",
    "photography_videography": "Photography & Video",
    "photography": "Party Photography",
    "attire_grooming": "Outfits, Styling & Makeup",
    "entertainment_music": "Music, DJ & Sound",
    "entertainment_activities": "Games & Host Entertainment",
    "entertainment_audio": "Audio, DJ & Melodies",
    "cake_desserts": "Custom Cake & Dessert Bar",
    "invitations_gifts": "Invitations, Favors & Gifts",
    "gifts_favors": "Return Gifts & Favors",
    "puja_rituals_materials": "Puja Materials & Samagri",
    "sanitation_crowd_management": "Sanitation, Volunteers & Waste",
    "publicity_signage": "Signage & Community Notices",
    "av_tech_stage": "AV Tech, Stage & LED Screens",
    "activities_facilitator": "Team Activities & Facilitation",
    "branding_swag": "Event Branding & Attendee Kits",
    "contingency": "Emergency Contingency Reserve"
}


def _find_top_matched_priority(raw_weights: dict[str, float], priorities: list[str]) -> str | None:
    """Finds the first category key matching user priorities."""
    for p in priorities:
        p_clean = p.lower().strip()
        for cat_key in raw_weights:
            if p_clean in cat_key or cat_key in p_clean:
                return cat_key
    return None


def _adjust_priority_weights(
    raw_weights: dict[str, float],
    floors: dict[str, float],
    priorities: list[str],
) -> dict[str, float]:
    """Adjusts category weights based on user priorities while respecting minimum floors."""
    adjusted_weights = dict(raw_weights)
    if not priorities:
        return adjusted_weights

    top_p = _find_top_matched_priority(raw_weights, priorities)
    if top_p and top_p in adjusted_weights:
        boost = adjusted_weights[top_p] * PRIORITY_BOOST_FACTOR
        adjusted_weights[top_p] += boost
        other_keys = [k for k in adjusted_weights if k != top_p]
        if other_keys:
            reduction_per_cat = boost / len(other_keys)
            for k in other_keys:
                min_fl = floors.get(k, DEFAULT_FLOOR_PCT + 0.01)
                adjusted_weights[k] = max(min_fl, adjusted_weights[k] - reduction_per_cat)

    weight_sum = sum(adjusted_weights.values())
    if weight_sum > 0:
        for k in adjusted_weights:
            adjusted_weights[k] = adjusted_weights[k] / weight_sum

    return adjusted_weights


def _balance_discrete_units(
    base_units: dict[str, int],
    fractions: dict[str, float],
    unlocked_keys: list[str],
    rem_units: int,
) -> None:
    """Redistributes remainder discrete units across categories according to fraction magnitudes."""
    if rem_units < 0:
        sorted_by_frac_asc = sorted(unlocked_keys, key=lambda k: fractions[k])
        for k in sorted_by_frac_asc:
            reduction = min(abs(rem_units), max(0, base_units[k] - 1))
            base_units[k] -= reduction
            rem_units += reduction
            if rem_units >= 0:
                break
    elif rem_units > 0:
        sorted_by_frac_desc = sorted(unlocked_keys, key=lambda k: fractions[k], reverse=True)
        for i in range(rem_units):
            k = sorted_by_frac_desc[i % len(sorted_by_frac_desc)]
            base_units[k] += 1


def _distribute_allocations(
    adjusted_weights: dict[str, float],
    floors: dict[str, float],
    allocable_budget: int,
    locked_categories: dict[str, int],
) -> tuple[dict[str, int], int]:
    """Distributes allocable budget to 100-rupee units using largest-remainder algorithm."""
    category_allocations: dict[str, int] = {}
    locked_total = 0
    unlocked_keys: list[str] = []
    unlocked_weight_sum = 0.0

    for k, weight in adjusted_weights.items():
        if k in locked_categories:
            amt = locked_categories[k]
            locked_total += amt
            category_allocations[k] = amt
        else:
            unlocked_keys.append(k)
            unlocked_weight_sum += weight

    remaining_for_unlocked = max(0, allocable_budget - locked_total)
    odd_rupees = 0

    if unlocked_keys:
        if unlocked_weight_sum <= 0:
            unlocked_weight_sum = 1.0

        total_units = remaining_for_unlocked // ROUNDING_UNIT
        odd_rupees = remaining_for_unlocked % ROUNDING_UNIT

        base_units: dict[str, int] = {}
        fractions: dict[str, float] = {}

        for k in unlocked_keys:
            norm_w = adjusted_weights[k] / unlocked_weight_sum
            tu = norm_w * total_units
            bu = int(math.floor(tu))
            min_floor_units = int(math.ceil((floors.get(k, DEFAULT_FLOOR_PCT) * allocable_budget) / ROUNDING_UNIT))
            if bu < min_floor_units and total_units >= min_floor_units * len(unlocked_keys):
                bu = min_floor_units
            base_units[k] = bu
            fractions[k] = tu - bu

        assigned_units = sum(base_units.values())
        rem_units = total_units - assigned_units
        _balance_discrete_units(base_units, fractions, unlocked_keys, rem_units)

        for k in unlocked_keys:
            category_allocations[k] = base_units[k] * ROUNDING_UNIT

    return category_allocations, odd_rupees


def _evaluate_feasibility(
    total_budget: int,
    guest_count: int,
    template: dict,
) -> tuple[int, str, str]:
    """Calculates per-guest spend and evaluates budget feasibility status and reasoning."""
    per_guest_spend = total_budget // max(1, guest_count)
    benchmarks = template.get("benchmark_per_guest", {"tier1": 1500, "tier2": 1000, "tier3": 750})
    bench_val = benchmarks.get("tier2", 1000)

    if per_guest_spend >= bench_val * FEASIBILITY_COMFORTABLE_MULTIPLIER:
        return (
            per_guest_spend,
            "comfortable",
            f"At ₹{per_guest_spend:,}/guest, your budget is comfortable. You have ample room for full hospitality, "
            f"premium catering live counters, and high-quality photography."
        )
    if per_guest_spend >= bench_val * FEASIBILITY_TIGHT_MULTIPLIER:
        return (
            per_guest_spend,
            "tight",
            f"At ₹{per_guest_spend:,}/guest, your budget is tight but feasible. Focus on package deals for venue and decor, "
            f"and keep the menu curated rather than multi-cuisine."
        )
    return (
        per_guest_spend,
        "unrealistic",
        f"At ₹{per_guest_spend:,}/guest, this budget is unrealistic for a full {template.get('label', 'event')} with {guest_count} guests. "
        f"Standard catering and basic venue alone typically require at least ₹{bench_val:,}/guest. "
        f"Consider trimming guest count or switching to a community/home venue."
    )


def calculate_budget(
    total_budget: int,
    guest_count: int,
    event_type: str = "wedding",
    priorities: list[str] | None = None,
    city: str = "Tier 2 City",  # noqa: ARG001
    locked_categories: dict[str, int] | None = None
) -> BudgetReport:
    """
    Deterministic budget engine implementing:
    - Template weights from event_templates.json
    - Priority boosting (+20% to top priority, -15% from lowest)
    - Category minimum floors
    - 5-10% contingency reserve
    - Largest-remainder rounding to Rs 100 so the sum matches total_budget EXACTLY
    - Feasibility evaluation
    """
    templates = load_event_templates()
    template = templates.get(event_type.lower()) or templates["wedding"]
    priorities = priorities or []
    locked_categories = locked_categories or {}

    raw_weights: dict[str, float] = dict(template.get("category_weights", {}))
    floors: dict[str, float] = dict(template.get("floors", {}))
    contingency_pct: float = float(template.get("contingency_pct", 0.08))

    adjusted_weights = _adjust_priority_weights(raw_weights, floors, priorities)

    raw_contingency = total_budget * contingency_pct
    contingency_amount = max(MIN_CONTINGENCY_AMOUNT, int(round(raw_contingency / ROUNDING_UNIT) * ROUNDING_UNIT))
    allocable_budget = total_budget - contingency_amount

    category_allocations, odd_rupees = _distribute_allocations(
        adjusted_weights, floors, allocable_budget, locked_categories
    )
    contingency_amount += odd_rupees

    alloc_items: list[BudgetCategoryAllocation] = []
    subtotal = 0
    for k, amt in category_allocations.items():
        subtotal += amt
        pct = round((amt / total_budget) * 100.0, 1) if total_budget > 0 else 0.0
        floor_amt = int(floors.get(k, DEFAULT_FLOOR_PCT) * allocable_budget)
        alloc_items.append(
            BudgetCategoryAllocation(
                category_id=k,
                label=CATEGORY_LABELS.get(k, k.replace("_", " ").title()),
                allocated_amount=amt,
                percentage=pct,
                floor_amount=floor_amt,
                is_locked=(k in locked_categories),
                actual_spent=0,
                notes=f"Floor: ₹{floor_amt:,} (minimum viable tier)"
            )
        )

    contingency_pct_final = round((contingency_amount / total_budget) * 100.0, 1) if total_budget > 0 else 0.0
    alloc_items.append(
        BudgetCategoryAllocation(
            category_id="contingency",
            label=CATEGORY_LABELS["contingency"],
            allocated_amount=contingency_amount,
            percentage=contingency_pct_final,
            floor_amount=contingency_amount,
            is_locked=True,
            actual_spent=0,
            notes="Unallocated reserve for price variations, unexpected guests & emergency additions"
        )
    )

    per_guest_spend, feasibility_status, feasibility_reason = _evaluate_feasibility(
        total_budget, guest_count, template
    )

    return BudgetReport(
        total_budget=total_budget,
        contingency_amount=contingency_amount,
        allocated_subtotal=subtotal,
        categories=alloc_items,
        feasibility_status=feasibility_status,
        feasibility_reason=feasibility_reason,
        per_guest_spend=per_guest_spend
    )
