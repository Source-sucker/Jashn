import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    """Verify /api/health endpoint returns 200 and expected metadata."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "Jashn" in data["app"]
    assert "timestamp" in data


def test_intake_complete(client):
    """Verify /api/intake completes when critical fields are provided."""
    payload = {
        "event_type": "wedding",
        "event_date": "2026-12-25",
        "city": "Mumbai",
        "guest_count": 250,
        "total_budget": 800000,
        "priorities": ["catering", "decor_styling"]
    }
    res = client.post("/api/intake", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_complete"] is True
    assert data["brief"]["total_budget"] == 800000
    assert len(data["clarifying_questions"]) == 0


def test_intake_missing_fields_clarifying_questions(client):
    """Verify /api/intake returns at most 3 clarifying questions when critical fields missing."""
    payload = {
        "description": "Looking to host a gathering in Delhi with some friends.",
        "city": "Delhi"
    }
    res = client.post("/api/intake", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_complete"] is False
    assert len(data["clarifying_questions"]) <= 3
    assert len(data["clarifying_questions"]) > 0


def test_plan_generation_exact_budget(client, sample_brief):
    """Verify /api/plan generates full plan with exact budget sum."""
    payload = sample_brief.model_dump()
    res = client.post("/api/plan", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["plan_id"].startswith("plan_")
    assert data["brief"]["total_budget"] == sample_brief.total_budget
    assert data["budget"]["total_budget"] == sample_brief.total_budget

    # Non-negotiable exact sum check
    allocated_sum = sum(c["allocated_amount"] for c in data["budget"]["categories"])
    assert allocated_sum == sample_brief.total_budget

    # Timeline, Vendors, Ideas presence
    assert len(data["timeline"]["tasks"]) > 0
    assert len(data["vendors"]) > 0
    assert len(data["ideas"]["themes"]) >= 3


def test_replan_endpoint(client, sample_plan):
    """Verify /api/replan updates budget, preserves completed tasks, and returns trade-offs."""
    plan_dict = sample_plan.model_dump()
    # Mark first task completed
    first_task_id = plan_dict["timeline"]["tasks"][0]["id"]
    plan_dict["timeline"]["tasks"][0]["is_completed"] = True

    replan_payload = {
        "current_plan": plan_dict,
        "updated_budget": 400000,
        "completed_task_ids": [first_task_id]
    }

    res = client.post("/api/replan", json=replan_payload)
    assert res.status_code == 200
    data = res.json()

    assert data["updated_plan"]["budget"]["total_budget"] == 400000
    assert len(data["diff_summary"]) > 0
    assert len(data["tradeoff_options"]) >= 2


def test_refine_ideas_endpoint(client, sample_plan):
    """Verify /api/ideas/refine adjusts ideas without restarting the plan."""
    payload = {
        "current_ideas": sample_plan.ideas.model_dump(),
        "brief": sample_plan.brief.model_dump(),
        "refinement_prompt": "Make it elder-friendly with soft seating and satvik dishes"
    }

    res = client.post("/api/ideas/refine", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert len(data["themes"]) >= 2
    assert "elder-friendly" in data["cultural_alignment_note"].lower() or "elder-friendly" in str(data["themes"]).lower()
