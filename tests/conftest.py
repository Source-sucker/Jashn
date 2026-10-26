import pytest

from app.models.schemas import EventBrief, PlanResponse
from app.services.fallback import build_fallback_plan


@pytest.fixture(autouse=True)
def default_offline_env(monkeypatch):
    """Keep test suite fast and deterministic by default; specific tests explicitly patch key."""
    monkeypatch.setattr("app.config.settings.gemini_api_key", "")
    from app.services.ai_client import ai_client
    monkeypatch.setattr(ai_client, "_client", None)


@pytest.fixture
def sample_brief() -> EventBrief:
    return EventBrief(
        event_type="wedding",
        event_date="2026-12-25",
        city="Jaipur",
        guest_count=200,
        total_budget=800000,
        priorities=["catering", "decor_styling"],
        venue_preference="Heritage Haveli or Lawn",
        dietary_cultural_notes="Rajasthani Vegetarian with Jain counters",
        vibe="Royal Rajasthani Heritage",
        user_description="Planning a 2-day family wedding celebration in Jaipur on ₹8,00,000 budget."
    )


@pytest.fixture
def sample_birthday_brief() -> EventBrief:
    return EventBrief(
        event_type="birthday",
        event_date="2026-11-20",
        city="Bengaluru",
        guest_count=35,
        total_budget=45000,
        priorities=["cake_desserts", "entertainment_activities"],
        venue_preference="Apartment Clubhouse",
        dietary_cultural_notes="Kids party snacks and eggless chocolate cake",
        vibe="Colorful Superhero Carnival",
        user_description="5th birthday party for my child with games and cake."
    )


@pytest.fixture
def sample_plan(sample_brief) -> PlanResponse:
    return build_fallback_plan(sample_brief)
