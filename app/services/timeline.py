import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from app.models.schemas import TimelineReport, TimelineTask

TEMPLATES_PATH = Path(__file__).parent.parent / "data" / "event_templates.json"


def load_event_templates() -> dict:
    with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def calculate_timeline(
    event_date_str: str,
    event_type: str = "wedding",
    today: Optional[date] = None,
    completed_task_ids: Optional[list[str]] = None,
    custom_tasks: Optional[list[dict]] = None
) -> TimelineReport:
    """
    Deterministic backward-scheduling timeline engine:
    - Schedules tasks backward from event_date
    - If days_remaining < standard_lead_days, compresses offsets proportionally and flags 'is_rush'
    - Identifies 'is_urgent' if due date is today or past
    - Tracks 'depends_on' and flags 'is_blocked' if any prerequisite is incomplete & overdue
    - Preserves completed statuses
    """
    templates = load_event_templates()
    template = templates.get(event_type.lower()) or templates["wedding"]
    standard_lead = int(template.get("standard_lead_days", 120))
    today = today or date.today()

    try:
        event_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()
    except Exception:
        # Fallback if invalid date string
        event_date = today + timedelta(days=60)
        event_date_str = event_date.strftime("%Y-%m-%d")

    days_remaining = (event_date - today).days
    is_compressed = (days_remaining < standard_lead) and (days_remaining > 0)
    compression_ratio = min(1.0, max(0.05, days_remaining / float(standard_lead))) if days_remaining > 0 else 0.0

    completed_ids = set(completed_task_ids or [])
    task_templates = list(template.get("task_templates", []))

    # Incorporate custom or AI-suggested tasks if provided
    if custom_tasks:
        for ct in custom_tasks:
            if isinstance(ct, dict) and "id" in ct and "title" in ct:
                task_templates.append(ct)

    computed_tasks: list[TimelineTask] = []
    completed_lookup: dict[str, bool] = {}
    overdue_lookup: dict[str, bool] = {}

    for t in task_templates:
        tid = str(t.get("id"))
        base_lead = int(t.get("lead_days_before_event", 14))

        if days_remaining <= 0:
            # Event is today or past
            actual_offset = 0
            task_due = event_date
            is_rush = True
        elif is_compressed:
            actual_offset = max(0, min(days_remaining - 1, int(round(base_lead * compression_ratio))))
            task_due = event_date - timedelta(days=actual_offset)
            is_rush = actual_offset < base_lead
        else:
            actual_offset = base_lead
            task_due = event_date - timedelta(days=actual_offset)
            is_rush = False

        is_completed = tid in completed_ids
        is_urgent = (task_due <= today) and (not is_completed)
        completed_lookup[tid] = is_completed
        overdue_lookup[tid] = is_urgent

        computed_tasks.append(
            TimelineTask(
                id=tid,
                title=t.get("title", "Task"),
                phase=t.get("phase", "General Planning"),
                due_date=task_due.strftime("%Y-%m-%d"),
                days_before_event=actual_offset,
                priority=t.get("priority", "medium"),
                category=t.get("category", "planning"),
                depends_on=list(t.get("depends_on", [])),
                is_completed=is_completed,
                is_rush=is_rush,
                is_urgent=is_urgent,
                is_blocked=False,
                notes=t.get("notes")
            )
        )

    # Resolve blocked dependencies
    for task in computed_tasks:
        if task.depends_on and not task.is_completed:
            for parent_id in task.depends_on:
                # If parent task is incomplete AND either overdue or scheduled after this task
                if not completed_lookup.get(parent_id, False):
                    task.is_blocked = True
                    break

    # Sort tasks chronologically by due date ascending, then by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    computed_tasks.sort(key=lambda x: (x.due_date, priority_order.get(x.priority, 1)))

    phases = [
        "Foundations & Venue",
        "Key Vendors",
        "Details & Decor",
        "Final Week Prep",
        "Event Day Execution"
    ]

    return TimelineReport(
        event_date=event_date_str,
        days_remaining=days_remaining,
        is_compressed=is_compressed,
        tasks=computed_tasks,
        phases=phases
    )
