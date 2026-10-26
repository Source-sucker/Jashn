from datetime import date, timedelta

from app.services.timeline import calculate_timeline


def test_timeline_backward_scheduling():
    """Verify tasks are scheduled backwards from event date."""
    today = date(2026, 6, 1)
    event_date = today + timedelta(days=150)
    event_date_str = event_date.strftime("%Y-%m-%d")

    report = calculate_timeline(
        event_date_str=event_date_str,
        event_type="wedding",
        today=today
    )

    assert report.days_remaining == 150
    assert report.is_compressed is False

    for t in report.tasks:
        assert t.days_before_event >= 0
        expected_due = event_date - timedelta(days=t.days_before_event)
        assert t.due_date == expected_due.strftime("%Y-%m-%d")


def test_timeline_rush_compression():
    """Verify tasks compress proportionally and get flagged rush when days are short."""
    today = date(2026, 6, 1)
    # Wedding standard lead is 150 days. Give only 30 days!
    event_date = today + timedelta(days=30)
    event_date_str = event_date.strftime("%Y-%m-%d")

    report = calculate_timeline(
        event_date_str=event_date_str,
        event_type="wedding",
        today=today
    )

    assert report.days_remaining == 30
    assert report.is_compressed is True
    # Most tasks with original lead > 30 must be flagged rush
    rush_tasks = [t for t in report.tasks if t.is_rush]
    assert len(rush_tasks) > 0


def test_timeline_urgency_and_past_dates():
    """Verify tasks with due date <= today are flagged is_urgent."""
    today = date(2026, 6, 1)
    # Event scheduled for today
    event_date_str = today.strftime("%Y-%m-%d")

    report = calculate_timeline(
        event_date_str=event_date_str,
        event_type="birthday",
        today=today
    )

    urgent_tasks = [t for t in report.tasks if t.is_urgent]
    assert len(urgent_tasks) > 0
    for t in urgent_tasks:
        assert t.due_date <= event_date_str


def test_timeline_dependency_blocking():
    """Verify a task with an uncompleted dependency is marked is_blocked."""
    today = date(2026, 6, 1)
    event_date = today + timedelta(days=90)
    event_date_str = event_date.strftime("%Y-%m-%d")

    # task_book_caterer depends on task_book_venue
    # If task_book_venue is not completed, task_book_caterer should be blocked
    report_uncompleted = calculate_timeline(
        event_date_str=event_date_str,
        event_type="wedding",
        today=today,
        completed_task_ids=[]
    )
    caterer_task = next((t for t in report_uncompleted.tasks if t.id == "task_book_caterer"), None)
    if caterer_task and "task_book_venue" in caterer_task.depends_on:
        assert caterer_task.is_blocked is True

    # When task_book_venue is completed, task_book_caterer should no longer be blocked by it
    report_completed = calculate_timeline(
        event_date_str=event_date_str,
        event_type="wedding",
        today=today,
        completed_task_ids=["task_budget_guestlist", "task_book_venue"]
    )
    caterer_task_unblocked = next((t for t in report_completed.tasks if t.id == "task_book_caterer"), None)
    if caterer_task_unblocked:
        assert caterer_task_unblocked.is_blocked is False
