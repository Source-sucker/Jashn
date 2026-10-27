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


def test_refine_ideas_empty_prompt_returns_unchanged(client, sample_plan):
    """Verify empty refinement prompt returns current ideas without changes."""
    payload = {
        "current_ideas": sample_plan.ideas.model_dump(),
        "brief": sample_plan.brief.model_dump(),
        "refinement_prompt": "   "
    }
    res = client.post("/api/ideas/refine", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert len(data["themes"]) == len(sample_plan.ideas.themes)
    assert data["cultural_alignment_note"] == sample_plan.ideas.cultural_alignment_note


def test_refine_ideas_with_ai_success(client, sample_plan):
    """Verify /api/ideas/refine processes AI response when ai_client is available."""
    from unittest.mock import AsyncMock, patch

    mock_ai_response = {
        "themes": [
            {
                "title": "Sufi Mehfil & Qawwali Night",
                "tagline": "Intimate soulful melodies with ambient candlelit seating.",
                "decor_concept": "Low floor seating, brass lanterns, velvet bolsters.",
                "menu_highlights": ["Awadhi Biryani", "Galouti Kebabs", "Phirni"],
                "activities": ["Live Qawwali troupe", "Shayari session"],
                "budget_category": "decor_styling",
                "estimated_tier": "Balanced"
            },
            {
                "title": "Modern Ghazal Lounge",
                "tagline": "Contemporary acoustic arrangements with mocktail pairings.",
                "decor_concept": "Fairy lights, pastel drapes, minimal floral centerpieces.",
                "menu_highlights": ["Fusion sliders", "Paneer Tikka", "Kulfi"],
                "activities": ["Acoustic guitar set", "Poetry reading"],
                "budget_category": "decor_styling",
                "estimated_tier": "Grand"
            }
        ],
        "cultural_alignment_note": "Refined for soulful musical evening."
    }

    with patch("app.api.routes.ai_client.is_available", return_value=True):
        with patch("app.api.routes.ai_client.generate_json", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_ai_response

            payload = {
                "current_ideas": sample_plan.ideas.model_dump(),
                "brief": sample_plan.brief.model_dump(),
                "refinement_prompt": "Add sufi musical theme and live ghazal performance"
            }
            res = client.post("/api/ideas/refine", json=payload)
            assert res.status_code == 200
            data = res.json()
            assert len(data["themes"]) == 2
            assert data["themes"][0]["title"] == "Sufi Mehfil & Qawwali Night"
            assert "soulful" in data["cultural_alignment_note"]


def test_refine_ideas_with_ai_exception_falls_back(client, sample_plan):
    """Verify /api/ideas/refine falls back safely if AI generation raises an exception."""
    from unittest.mock import AsyncMock, patch

    with patch("app.api.routes.ai_client.is_available", return_value=True):
        with patch("app.api.routes.ai_client.generate_json", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = RuntimeError("AI quota exceeded")

            payload = {
                "current_ideas": sample_plan.ideas.model_dump(),
                "brief": sample_plan.brief.model_dump(),
                "refinement_prompt": "Make it royal traditional"
            }
            res = client.post("/api/ideas/refine", json=payload)
            assert res.status_code == 200
            data = res.json()
            # Falls back to local refinement
            assert len(data["themes"]) >= 2
            assert "royal traditional" in data["cultural_alignment_note"]


def test_intake_endpoint_exception_handling(client):
    """Verify /api/intake returns 400 when an internal processing exception occurs."""
    from unittest.mock import patch

    with patch("app.api.routes.process_intake", side_effect=ValueError("Corrupt parsing state")):
        payload = {"description": "Some description"}
        res = client.post("/api/intake", json=payload)
        assert res.status_code == 400
        assert "Could not process intake details" in res.json()["detail"]


def test_plan_endpoint_exception_handling(client, sample_brief):
    """Verify /api/plan returns 500 when plan generation fails unexpectedly."""
    from unittest.mock import patch

    with patch("app.api.routes.generate_plan", side_effect=RuntimeError("Engine failure")):
        payload = sample_brief.model_dump()
        res = client.post("/api/plan", json=payload)
        assert res.status_code == 500
        assert "Failed to generate celebration plan" in res.json()["detail"]


def test_replan_endpoint_exception_handling(client, sample_plan):
    """Verify /api/replan returns 400 when compute_replan raises an exception."""
    from unittest.mock import patch

    with patch("app.api.routes.compute_replan", side_effect=ValueError("Invalid replan constraints")):
        replan_payload = {
            "current_plan": sample_plan.model_dump(),
            "updated_budget": 500000
        }
        res = client.post("/api/replan", json=replan_payload)
        assert res.status_code == 400
        assert "Could not replan with provided updates" in res.json()["detail"]


def test_intake_skips_ai_when_form_structured(client):
    """Verify /api/intake skips AI when form fields are fully provided."""
    from unittest.mock import AsyncMock, patch

    with patch("app.services.planner.ai_client.is_available", return_value=True):
        with patch("app.services.planner.ai_client.generate_json", new_callable=AsyncMock) as mock_gen:
            payload = {
                "event_type": "birthday",
                "event_date": "2026-12-10",
                "guest_count": 50,
                "total_budget": 50000,
                "city": "Bengaluru",
                "description": "5th birthday party for kids."
            }
            res = client.post("/api/intake", json=payload)
            assert res.status_code == 200
            data = res.json()
            assert data["is_complete"] is True
            assert data["brief"]["event_type"] == "birthday"
            assert data["brief"]["guest_count"] == 50
            # AI generation MUST NOT have been called
            mock_gen.assert_not_called()


def test_plan_fast_mode_skips_enrichment(client, sample_brief):
    """Verify /api/plan?enrich=false returns fast deterministic plan without AI."""
    payload = sample_brief.model_dump()
    res = client.post("/api/plan?enrich=false", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_ai_generated"] is False
    assert "Fast deterministic plan" in data["ai_status_message"]
    assert len(data["ideas"]["themes"]) >= 3
    assert len(data["budget"]["categories"]) > 0


def test_plan_enrich_endpoint(client, sample_brief):
    """Verify /api/plan/enrich returns enriched IdeasReport."""
    payload = {
        "brief": sample_brief.model_dump(),
        "categories_summary": "Food: 4L, Decor: 2L",
        "days_remaining": 90
    }
    res = client.post("/api/plan/enrich", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "themes" in data
    assert len(data["themes"]) >= 3
    assert "cultural_alignment_note" in data


def test_vercel_entrypoint_app():
    """Verify api/index.py exposes ASGI app instance for Vercel Serverless Function."""
    from api.index import app as vercel_app
    assert vercel_app is not None
    vercel_client = TestClient(vercel_app)
    res = vercel_client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"


def test_root_and_static_routes(client):
    """Verify root HTML and web alias routes return 200 OK and HTML content."""
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "Jashn" in res_root.text

    res_index = client.get("/index.html")
    assert res_index.status_code == 200

    res_alias = client.get("/web/index.html")
    assert res_alias.status_code == 200

    res_css = client.get("/css/styles.css")
    assert res_css.status_code == 200

