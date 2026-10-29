import math

from app.models.schemas import BudgetReport, PlanResponse, ReplanResponse, TradeoffOption
from app.services.budget import calculate_budget
from app.services.timeline import calculate_timeline
from app.services.vendors import build_vendor_checklist

# ---------------------------------------------------------------------------
# Replan trade-off constants — adjust here without touching business logic
# ---------------------------------------------------------------------------
#: Minimum guest count before "trim guest list" trade-off is offered.
MIN_GUESTS_FOR_TRIM: int = 20
#: Fraction of guests suggested for trimming (e.g., 0.15 = 15%).
GUEST_TRIM_RATE: float = 0.15
#: Minimum calculated saving (INR) for a trade-off option to be shown.
MIN_TRADEOFF_SAVING_INR: int = 1000
#: Fraction of decor allocation to save in the decor streamlining trade-off.
DECOR_REDUCTION_RATE: float = 0.35
#: Fraction of entertainment allocation to save in the decor trade-off.
ENT_REDUCTION_RATE: float = 0.30
#: Fraction of catering allocation to save in the catering-tier trade-off.
CATERING_REDUCTION_RATE: float = 0.15


def _generate_tradeoff_options(
    new_budget: int,
    new_guests: int,
    new_budget_report: BudgetReport,
) -> list[TradeoffOption]:
    """Generates deterministic tradeoff options based on budget thresholds and allocations."""
    tradeoff_options: list[TradeoffOption] = []

    # Trade-off 1: Guest List Optimization
    if new_guests > MIN_GUESTS_FOR_TRIM:
        trim_candidates = max(5, int(math.ceil(new_guests * GUEST_TRIM_RATE)))
        trim_pct = round((trim_candidates / new_guests) * 100)
        guest_saving = trim_candidates * (new_budget // new_guests)
        guest_saving_rounded = int(round(guest_saving / 100.0) * 100)
        tradeoff_options.append(
            TradeoffOption(
                id="tradeoff_trim_guests",
                title=f"Trim Guest List by ~{trim_pct}% ({trim_candidates} Attendees)",
                impact_type="guest_reduction",
                numeric_saving=guest_saving_rounded,
                description=(
                    f"Trimming {trim_candidates} guests (from {new_guests} to {new_guests - trim_candidates}) "
                    f"frees up an estimated ₹{guest_saving_rounded:,} in catering and favor costs, "
                    f"raising your per-guest spending back to a comfortable level."
                ),
                assumption_note=f"Estimated savings based on an average allocation of ₹{new_budget // new_guests:,} per attendee. Actual savings depend on caterer minimum plate guarantees.",
                pros=["Immediate direct reduction in catering and seating costs", "Allows higher hospitality quality for closest circle"],
                cons=["Requires difficult family conversations on secondary invites"],
                applied_changes={"guest_count": new_guests - trim_candidates}
            )
        )

    # Trade-off 2: Decor & Entertainment Streamlining
    decor_alloc = next((c.allocated_amount for c in new_budget_report.categories if "decor" in c.category_id), 0)
    ent_alloc = next((c.allocated_amount for c in new_budget_report.categories if "entertainment" in c.category_id), 0)
    decor_saving = int(round((decor_alloc * DECOR_REDUCTION_RATE + ent_alloc * ENT_REDUCTION_RATE) / 100.0) * 100)
    if decor_saving > MIN_TRADEOFF_SAVING_INR:
        tradeoff_options.append(
            TradeoffOption(
                id="tradeoff_simplify_decor",
                title="Adopt Minimalist Sustainable Decor & Local Talent (~30% Decor Savings)",
                impact_type="decor_simplification",
                numeric_saving=decor_saving,
                description=(
                    f"Streamlining heavy structural staging and floral props to focus on fairy lights, seasonal marigolds, "
                    f"and curated Spotify/live acoustic sets saves an estimated ₹{decor_saving:,} without affecting food or venue quality."
                ),
                assumption_note="Estimated 30-35% decor reduction assumes replacing custom metal/wood fabrication with reusable floral and fabric elements.",
                pros=["Cuts fabrication costs drastically", "Modern aesthetic with lower environmental waste"],
                cons=["Less opulent stage backdrop and fewer grand mechanical entries"],
                applied_changes={"budget_reduction": decor_saving}
            )
        )

    # Trade-off 3: Catering Tier & Meal Timing Adjustment
    catering_alloc = next((c.allocated_amount for c in new_budget_report.categories if "catering" in c.category_id), 0)
    catering_saving = int(round((catering_alloc * CATERING_REDUCTION_RATE) / 100.0) * 100)
    if catering_saving > MIN_TRADEOFF_SAVING_INR:
        tradeoff_options.append(
            TradeoffOption(
                id="tradeoff_catering_tier",
                title="Shift to Curated Regional Live-Counters (~15% Catering Savings)",
                impact_type="catering_tier",
                numeric_saving=catering_saving,
                description=(
                    f"Replacing an overflowing 40-item generic buffet with a tight, high-flavor 18-item signature regional menu "
                    f"with 2 interactive live chaat/dosa counters saves an estimated ₹{catering_saving:,} while delighting guests."
                ),
                assumption_note="Estimated 15% menu savings assumes fixed-item live stations rather than high-wastage multi-course spread.",
                pros=["Guests remember hotter, fresher food with faster counter service", "Zero food wastage"],
                cons=["Fewer total varieties on the dessert and salad tables"],
                applied_changes={"catering_saving": catering_saving}
            )
        )

    return tradeoff_options


def compute_replan(
    current_plan: PlanResponse,
    updated_budget: int | None = None,
    updated_guest_count: int | None = None,
    updated_date: str | None = None,
    updated_priorities: list[str] | None = None,
    locked_categories: dict[str, int] | None = None,
    completed_task_ids: list[str] | None = None
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
    tradeoff_options = _generate_tradeoff_options(new_budget, new_guests, new_budget_report)

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
