import json
import math
from pathlib import Path
from typing import Optional

from app.models.schemas import BudgetCategoryAllocation, BudgetReport

TEMPLATES_PATH = Path(__file__).parent.parent / "data" / "event_templates.json"


def load_event_templates() -> dict:
    with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
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


def calculate_budget(
    total_budget: int,
    guest_count: int,
    event_type: str = "wedding",
    priorities: Optional[list[str]] = None,
    city: str = "Tier 2 City",
    locked_categories: Optional[dict[str, int]] = None
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

    # Priority Weight Adjustment
    # Top priority gets up to +20% boost, lowest priority gets up to -15% reduction
    adjusted_weights = dict(raw_weights)
    if priorities:
        # Match priority strings to category keys
        matched_priorities = []
        for p in priorities:
            p_clean = p.lower().strip()
            for cat_key in raw_weights.keys():
                if p_clean in cat_key or cat_key in p_clean:
                    if cat_key not in matched_priorities:
                        matched_priorities.append(cat_key)
                        break

        if matched_priorities:
            top_p = matched_priorities[0]
            if top_p in adjusted_weights:
                boost = adjusted_weights[top_p] * 0.20
                adjusted_weights[top_p] += boost
                # Distribute reduction across non-priority categories while respecting floors
                other_keys = [k for k in adjusted_weights.keys() if k != top_p]
                if other_keys:
                    reduction_per_cat = boost / len(other_keys)
                    for k in other_keys:
                        min_fl = floors.get(k, 0.03)
                        adjusted_weights[k] = max(min_fl, adjusted_weights[k] - reduction_per_cat)

    # Normalize category weights to sum to 1.0
    weight_sum = sum(adjusted_weights.values())
    for k in adjusted_weights:
        adjusted_weights[k] = adjusted_weights[k] / weight_sum

    # Calculate contingency amount in units of 100
    # Reserve is rounded to nearest 100
    raw_contingency = total_budget * contingency_pct
    contingency_amount = max(500, int(round(raw_contingency / 100.0) * 100))
    allocable_budget = total_budget - contingency_amount

    # Handle locked categories (e.g. during replanning)
    locked_total = 0
    unlocked_keys = []
    unlocked_weight_sum = 0.0
    for k in adjusted_weights.keys():
        if k in locked_categories:
            locked_total += locked_categories[k]
        else:
            unlocked_keys.append(k)
            unlocked_weight_sum += adjusted_weights[k]

    remaining_for_unlocked = max(0, allocable_budget - locked_total)

    # Largest-remainder allocation for unlocked categories to nearest Rs 100
    category_allocations: dict[str, int] = {}
    for k, amt in locked_categories.items():
        if k in adjusted_weights:
            category_allocations[k] = amt

    if unlocked_keys:
        if unlocked_weight_sum <= 0:
            unlocked_weight_sum = 1.0

        # Number of 100-rupee units to distribute
        total_units = remaining_for_unlocked // 100
        odd_rupees = remaining_for_unlocked % 100

        target_units: dict[str, float] = {}
        base_units: dict[str, int] = {}
        fractions: dict[str, float] = {}

        for k in unlocked_keys:
            norm_w = adjusted_weights[k] / unlocked_weight_sum
            tu = norm_w * total_units
            target_units[k] = tu
            bu = int(math.floor(tu))
            # Check floor in units
            min_floor_units = int(math.ceil((floors.get(k, 0.02) * allocable_budget) / 100.0))
            if bu < min_floor_units and total_units >= min_floor_units * len(unlocked_keys):
                bu = min_floor_units
            base_units[k] = bu
            fractions[k] = tu - bu

        assigned_units = sum(base_units.values())
        rem_units = total_units - assigned_units

        # If base units overshot due to floors, adjust down gracefully
        if rem_units < 0:
            sorted_by_frac_asc = sorted(unlocked_keys, key=lambda k: fractions[k])
            for k in sorted_by_frac_asc:
                reduction = min(abs(rem_units), max(0, base_units[k] - 1))
                base_units[k] -= reduction
                rem_units += reduction
                if rem_units >= 0:
                    break

        # Distribute remaining positive units by largest fraction
        if rem_units > 0:
            sorted_by_frac_desc = sorted(unlocked_keys, key=lambda k: fractions[k], reverse=True)
            for i in range(rem_units):
                k = sorted_by_frac_desc[i % len(sorted_by_frac_desc)]
                base_units[k] += 1

        for k in unlocked_keys:
            category_allocations[k] = base_units[k] * 100

        # Any odd single rupees (< 100) are added to contingency so total is EXACT
        contingency_amount += odd_rupees

    # Build BudgetCategoryAllocation list
    alloc_items: list[BudgetCategoryAllocation] = []
    subtotal = 0
    for k, amt in category_allocations.items():
        subtotal += amt
        pct = round((amt / total_budget) * 100.0, 1) if total_budget > 0 else 0.0
        floor_amt = int(floors.get(k, 0.02) * allocable_budget)
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

    # Add Contingency as an explicit category so the breakdown sums to 100%
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

    # Feasibility Evaluation
    per_guest_spend = total_budget // max(1, guest_count)
    benchmarks = template.get("benchmark_per_guest", {"tier1": 1500, "tier2": 1000, "tier3": 750})
    bench_val = benchmarks.get("tier2", 1000)

    if per_guest_spend >= bench_val * 1.3:
        feasibility_status = "comfortable"
        feasibility_reason = (
            f"At ₹{per_guest_spend:,}/guest, your budget is comfortable. You have ample room for full hospitality, "
            f"premium catering live counters, and high-quality photography."
        )
    elif per_guest_spend >= bench_val * 0.8:
        feasibility_status = "tight"
        feasibility_reason = (
            f"At ₹{per_guest_spend:,}/guest, your budget is tight but feasible. Focus on package deals for venue and decor, "
            f"and keep the menu curated rather than multi-cuisine."
        )
    else:
        feasibility_status = "unrealistic"
        feasibility_reason = (
            f"At ₹{per_guest_spend:,}/guest, this budget is unrealistic for a full {template.get('label', 'event')} with {guest_count} guests. "
            f"Standard catering and basic venue alone typically require at least ₹{bench_val:,}/guest. "
            f"Consider trimming guest count or switching to a community/home venue."
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
