from unittest.mock import AsyncMock, patch

import pytest

from app.models.schemas import IntakeRequest
from app.services.planner import generate_plan, process_intake


@pytest.mark.asyncio
async def test_process_intake_with_ai_complete():
    """Verify process_intake successfully parses brief when AI returns complete JSON."""
    mock_ai_output = {
        "is_complete": True,
        "brief": {
            "event_type": "wedding",
            "event_date": "2026-11-20",
            "city": "Lucknow",
            "guest_count": 300,
            "total_budget": 1200000,
            "priorities": ["catering", "venue"],
            "venue_preference": "Open Lawn",
            "dietary_cultural_notes": "Awadhi Mughlai cuisine with veg counters",
            "vibe": "Nawabi Elegance",
            "user_description": "Hosting a grand Awadhi wedding in Lucknow"
        },
        "extracted_summary": "Extracted wedding for 300 guests in Lucknow."
    }

    with patch("app.services.planner.ai_client.is_available", return_value=True):
        with patch("app.services.planner.ai_client.generate_json", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_ai_output

            req = IntakeRequest(
                description="Planning my sister's wedding in Lucknow on 20 Nov 2026 for 300 people with 12 Lakh budget."
            )
            res = await process_intake(req)

            assert res.is_complete is True
            assert res.brief is not None
            assert res.brief.total_budget == 1200000
            assert res.brief.city == "Lucknow"
            mock_gen.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_intake_skips_ai_when_fully_structured():
    """Verify process_intake skips AI intake call when critical form fields are fully provided."""
    with patch("app.services.planner.ai_client.is_available", return_value=True):
        with patch("app.services.planner.ai_client.generate_json", new_callable=AsyncMock) as mock_gen:
            req = IntakeRequest(
                event_type="wedding",
                event_date="2026-12-15",
                guest_count=250,
                total_budget=800000,
                city="Jaipur",
                description="We want a royal themed family celebration."
            )
            res = await process_intake(req)

            assert res.is_complete is True
            assert res.brief is not None
            assert res.brief.event_type == "wedding"
            assert res.brief.total_budget == 800000
            assert res.brief.guest_count == 250
            # AI generation MUST NOT have been invoked
            mock_gen.assert_not_called()


@pytest.mark.asyncio
async def test_process_intake_with_ai_clarifying_questions():
    """Verify process_intake returns clarifying questions when AI marks incomplete."""
    mock_ai_output = {
        "is_complete": False,
        "clarifying_questions": [
            {
                "field": "total_budget",
                "question": "What is your approximate budget ceiling in INR?",
                "options": ["₹2,00,000", "₹5,00,000", "₹10,00,000"]
            }
        ],
        "extracted_summary": "Need budget to calculate allocation."
    }

    with patch("app.services.planner.ai_client.is_available", return_value=True):
        with patch("app.services.planner.ai_client.generate_json", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_ai_output

            req = IntakeRequest(
                description="Birthday party in Pune on next month 15th for 40 kids."
            )
            res = await process_intake(req)

            assert res.is_complete is False
            assert len(res.clarifying_questions) == 1
            assert res.clarifying_questions[0].field == "total_budget"


@pytest.mark.asyncio
async def test_generate_plan_with_ai_enrichment(sample_brief):
    """Verify generate_plan incorporates AI themes and custom vendor questions."""
    mock_ai_enrichment = {
        "themes": [
            {
                "id": "theme_1",
                "title": "Nawabi Royal Banquet",
                "tagline": "Grand candlelit dinner with Awadhi heritage.",
                "decor_concept": "Ivory drapery and brass urlis.",
                "menu_highlights": ["Galouti Kebab", "Dum Biryani"],
                "activities": ["Sufi Ghazal night"],
                "budget_category": "decor_styling",
                "fits_allocation": True,
                "estimated_tier": "Grand"
            },
            {
                "id": "theme_2",
                "title": "Zardozi & Marigold Heritage",
                "tagline": "Traditional family warmth.",
                "decor_concept": "Marigold strings and clay lamps.",
                "menu_highlights": ["Paneer Pasanda", "Kesari Kheer"],
                "activities": ["Dholak sangeet circle"],
                "budget_category": "decor_styling",
                "fits_allocation": True,
                "estimated_tier": "Balanced"
            },
            {
                "id": "theme_3",
                "title": "Eco-Chic Lucknowi Garden",
                "tagline": "Sustainable open air celebration.",
                "decor_concept": "Recycled jute, brass lamps.",
                "menu_highlights": ["Seasonal artisanal thali"],
                "activities": ["Plant sapling favors"],
                "budget_category": "decor_styling",
                "fits_allocation": True,
                "estimated_tier": "Budget-Friendly"
            }
        ],
        "cultural_alignment_note": "Customized for royal Awadhi traditions in Lucknow.",
        "vendor_questions": {
            "catering": ["Can you do live tandoor and copper handi presentation on-site?"]
        }
    }

    with patch("app.services.planner.ai_client.is_available", return_value=True):
        with patch("app.services.planner.ai_client.generate_json", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_ai_enrichment

            plan = await generate_plan(sample_brief)

            assert plan.is_ai_generated is True
            assert "AI personalized plan" in plan.ai_status_message
            assert len(plan.ideas.themes) == 3
            assert plan.ideas.themes[0].title == "Nawabi Royal Banquet"
            catering_vendor = next(v for v in plan.vendors if v.category_id == "catering")
            assert "Can you do live tandoor and copper handi presentation on-site?" in catering_vendor.questions_to_ask
