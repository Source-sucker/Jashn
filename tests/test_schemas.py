import pytest
from pydantic import ValidationError

from app.models.schemas import EventBrief, IntakeRequest


def test_schema_rejects_negative_or_tiny_budget():
    """Verify validation error when budget is below minimum threshold."""
    with pytest.raises(ValidationError):
        EventBrief(
            event_type="wedding",
            event_date="2026-12-15",
            city="Delhi",
            guest_count=100,
            total_budget=1000  # Below 5000 minimum
        )


def test_schema_rejects_zero_or_excessive_guests():
    """Verify validation error when guest count is 0 or > 50,000."""
    with pytest.raises(ValidationError):
        EventBrief(
            event_type="wedding",
            event_date="2026-12-15",
            city="Delhi",
            guest_count=0,
            total_budget=500000
        )

    with pytest.raises(ValidationError):
        EventBrief(
            event_type="wedding",
            event_date="2026-12-15",
            city="Delhi",
            guest_count=100000,
            total_budget=500000
        )


def test_schema_normalizes_cultural_event_aliases():
    """Verify shaadi, marriage, bday are normalized to standard keys."""
    b1 = EventBrief(
        event_type="Grand Shaadi & Sangeet",
        event_date="2026-12-15",
        city="Delhi",
        guest_count=150,
        total_budget=500000
    )
    assert b1.event_type == "wedding"

    b2 = EventBrief(
        event_type="Kids 5th Bday Party",
        event_date="2026-12-15",
        city="Delhi",
        guest_count=30,
        total_budget=40000
    )
    assert b2.event_type == "birthday"

    b3 = EventBrief(
        event_type="Society Diwali Utsav Puja",
        event_date="2026-12-15",
        city="Delhi",
        guest_count=200,
        total_budget=150000
    )
    assert b3.event_type == "community"


def test_intake_request_max_length_capping():
    """Verify oversized descriptions are rejected at schema boundary."""
    with pytest.raises(ValidationError):
        IntakeRequest(
            description="a" * 3000  # Limit is 2000
        )
