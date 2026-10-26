import math
from typing import Optional

from app.models.schemas import PlanResponse, ReplanResponse, TradeoffOption
from app.services.budget import calculate_budget
from app.services.timeline import calculate_timeline
from app.services.vendors import build_vendor_checklist


def compute_replan(
    current_plan: PlanResponse,
    updated_budget: Optional[int] = None,
    updated_guest_count: Optional[int] = None,
    updated_date: Optional[str] = None,
    updated_priorities: Optional[list[str]] = None,
    locked_categories: Optional[dict[str, int]] = None,
    completed_task_ids: Optional[list[str]] = None
) -> ReplanResponse:
    """
    Deterministic replan engine:
    - Preserves completed tasks and user-locked category estimates
    - Re-runs budget allocation under new constraints
    - Re-runs backward timeline scheduling with updated event date
    - Computes a clean diff summary of changes
    - Computes 2-3 concrete mathematical trade-off options with numbers calculated by code
    """
    old_brief = current_plan.brief
    new_budget = updated_budget if updated_budget is not None else old_brief.total_budget
    new_guests = updated_guest_count if updated_guest_count is not None else old_brief.guest_count
    new_date = updated_date if updated_date is not None else old_brief.event_date
    new_priorities = updated_priorities if updated_priorities is not None else old_brief.priorities
    locked_cats = dict(locked_categories or {})

    # Extract all completed tasks from the existing plan plus any extra IDs passed
    existing_completed = {t.id for t in current_plan.timeline.tasks if t.is_completed}
    if completed_task_ids:
        existing_completed.update(completed_task_ids)

    # 1. Diff Summary Calculation
    diffs: list[str] = []
    if new_budget != old_brief.total_budget:
        pct_change = round(((new_budget - old_brief.total_budget) / old_brief.total_budget) * 100, 1)
        direction = "increased" if pct_change > 0 else "reduced"
        diffs.append(
            f"Budget {direction} by {abs(pct_change)}% (₹{old_brief.total_budget:,} → ₹{new_budget:,})"
        )

    if new_guests != old_brief.guest_count:
        diff_guests = new_guests - old_brief.guest_count
        diffs.append(
            f"Guest count changed from {old_brief.guest_count} to {new_guests} ({'+' if diff_guests > 0 else ''}{diff_guests} guests)"
        )

    if new_date != old_brief.event_date:
        diffs.append(f"Event date shifted from {old_brief.event_date} to {new_date}")

    if new_priorities != old_brief.priorities:
        diffs.append(f"Priorities updated to: {', '.join(new_priorities)}")

    if locked_cats:
        diffs.append(f"{len(locked_cats)} budget categories locked to user-specified values")

    if not diffs:
        diffs.append("No parameter changes detected; plan recalculated with current constraints.")

    # 2. Recalculate Budget with Locked Values Preserved
    new_budget_report = calculate_budget(
        total_budget=new_budget,
        guest_count=new_guests,
        event_type=old_brief.event_type,
        priorities=new_priorities,
        city=old_brief.city,
        locked_categories=locked_cats
    )

    # 3. Recalculate Timeline with Completed Statuses Preserved
    new_timeline_report = calculate_timeline(
        event_date_str=new_date,
        event_type=old_brief.event_type,
        completed_task_ids=list(existing_completed)
    )

    # 4. Rebuild Vendors
    new_vendors = build_vendor_checklist(
        event_type=old_brief.event_type,
        budget_report=new_budget_report,
        existing_user_vendors=[
            uv for vcat in current_plan.vendors for uv in vcat.user_vendors
        ]
    )

    # 5. Compute Engine-Calculated Trade-Off Options
    tradeoff_options: list[TradeoffOption] = []

    # Trade-off 1: Guest List Optimization
    if new_guests > 20:
        trim_candidates = max(5, int(math.ceil(new_guests * 0.15)))
        guest_saving = trim_candidates * (new_budget // new_guests)
        guest_saving_rounded = int(round(guest_saving / 100.0) * 100)
        tradeoff_options.append(
            TradeoffOption(
                id="tradeoff_trim_guests",
                title=f"Trim Guest List by {trim_candidates} Attendees",
                impact_type="guest_reduction",
                numeric_saving=guest_saving_rounded,
                description=(
                    f"Trimming {trim_candidates} guests (from {new_guests} to {new_guests - trim_candidates}) "
                    f"frees up an estimated ₹{guest_saving_rounded:,} in catering and favor costs, "
                    f"raising your per-guest spending back to a comfortable level."
                ),
                pros=["Immediate direct reduction in catering and seating costs", "Allows higher hospitality quality for closest circle"],
                cons=["Requires difficult family conversations on secondary invites"],
                applied_changes={"guest_count": new_guests - trim_candidates}
            )
        )

    # Trade-off 2: Decor & Entertainment Streamlining
    decor_alloc = next((c.allocated_amount for c in new_budget_report.categories if "decor" in c.category_id), 0)
    ent_alloc = next((c.allocated_amount for c in new_budget_report.categories if "entertainment" in c.category_id), 0)
    decor_saving = int(round((decor_alloc * 0.35 + ent_alloc * 0.30) / 100.0) * 100)
    if decor_saving > 1000:
        tradeoff_options.append(
            TradeoffOption(
                id="tradeoff_simplify_decor",
                title="Adopt Minimalist Sustainable Decor & Local Talent",
                impact_type="decor_simplification",
                numeric_saving=decor_saving,
                description=(
                    f"Streamlining heavy structural staging and floral props to focus on fairy lights, seasonal marigolds, "
                    f"and curated Spotify/live acoustic sets saves approximately ₹{decor_saving:,} without affecting food or venue quality."
                ),
                pros=["Cuts fabrication costs drastically", "Modern aesthetic with lower environmental waste"],
                cons=["Less opulent stage backdrop and fewer grand mechanical entries"],
                applied_changes={"budget_reduction": decor_saving}
            )
        )

    # Trade-off 3: Catering Tier & Meal Timing Adjustment
    catering_alloc = next((c.allocated_amount for c in new_budget_report.categories if "catering" in c.category_id), 0)
    catering_saving = int(round((catering_alloc * 0.15) / 100.0) * 100)
    if catering_saving > 1000:
        tradeoff_options.append(
            TradeoffOption(
                id="tradeoff_catering_tier",
                title="Shift to Curated Regional Live-Counters",
                impact_type="catering_tier",
                numeric_saving=catering_saving,
                description=(
                    f"Replacing an overflowing 40-item generic buffet with a tight, high-flavor 18-item signature regional menu "
                    f"with 2 interactive live chaat/dosa counters saves approximately ₹{catering_saving:,} while delighting guests."
                ),
                pros=["Guests remember hotter, fresher food with faster counter service", "Zero food wastage"],
                cons=["Fewer total varieties on the dessert and salad tables"],
                applied_changes={"catering_saving": catering_saving}
            )
        )

    # Updated EventBrief
    new_brief = old_brief.model_copy(
        update={
            "total_budget": new_budget,
            "guest_count": new_guests,
            "event_date": new_date,
            "priorities": new_priorities
        }
    )

    updated_plan = current_plan.model_copy(
        update={
            "brief": new_brief,
            "budget": new_budget_report,
            "timeline": new_timeline_report,
            "vendors": new_vendors
        }
    )

    return ReplanResponse(
        updated_plan=updated_plan,
        diff_summary=diffs,
        tradeoff_options=tradeoff_options
    )
