from datetime import datetime, timedelta

from app.services.fallback import build_fallback_plan
from app.services.replan import compute_replan


def test_replan_extreme_cut_and_earlier_date(sample_brief):
    """
    NON-NEGOTIABLE TEST:
    Must handle budget reduced by 50% AND event moved 2 weeks earlier.
    """
    initial_plan = build_fallback_plan(sample_brief)

    # Mark first task as completed
    first_task_id = initial_plan.timeline.tasks[0].id
    initial_plan.timeline.tasks[0].is_completed = True

    # Cut budget by 50%: 8,00,000 -> 4,00,000
    new_budget = initial_plan.brief.total_budget // 2
    # Move date 14 days earlier
    cur_date = datetime.strptime(initial_plan.brief.event_date, "%Y-%m-%d")
    new_date = (cur_date - timedelta(days=14)).strftime("%Y-%m-%d")

    replan_res = compute_replan(
        current_plan=initial_plan,
        updated_budget=new_budget,
        updated_date=new_date,
        completed_task_ids=[first_task_id]
    )

    updated = replan_res.updated_plan
    # Assert budget was cut to exact amount
    assert updated.budget.total_budget == new_budget
    assert sum(c.allocated_amount for c in updated.budget.categories) == new_budget

    # Assert date moved
    assert updated.timeline.event_date == new_date

    # Assert completed task was preserved
    completed_task = next(t for t in updated.timeline.tasks if t.id == first_task_id)
    assert completed_task.is_completed is True

    # Assert diff summary contains key changes
    diff_text = " ".join(replan_res.diff_summary)
    assert "reduced by 50.0%" in diff_text
    assert new_date in diff_text

    # Assert 2-3 trade-off options generated with numeric calculations
    assert len(replan_res.tradeoff_options) >= 2
    for opt in replan_res.tradeoff_options:
        assert opt.numeric_saving > 0
        assert opt.title
        assert len(opt.pros) > 0


def test_replan_preserves_locked_categories(sample_brief):
    """Verify replan preserves user-locked category estimates."""
    initial_plan = build_fallback_plan(sample_brief)

    locked_amt = 250000
    replan_res = compute_replan(
        current_plan=initial_plan,
        updated_budget=700000,
        locked_categories={"catering": locked_amt}
    )

    updated_catering = next(
        c for c in replan_res.updated_plan.budget.categories if c.category_id == "catering"
    )
    assert updated_catering.allocated_amount == locked_amt
    assert updated_catering.is_locked is True
    assert sum(c.allocated_amount for c in replan_res.updated_plan.budget.categories) == 700000
