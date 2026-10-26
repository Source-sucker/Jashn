from app.models.schemas import UserVendor
from app.services.budget import calculate_budget
from app.services.vendors import build_vendor_checklist


def test_vendor_checklist_matching_budget():
    """Verify vendor categories map estimated budgets from the deterministic budget report."""
    budget_report = calculate_budget(total_budget=500000, guest_count=100, event_type="wedding")
    vendors = build_vendor_checklist(event_type="wedding", budget_report=budget_report)

    assert len(vendors) > 0
    cat_map = {c.category_id: c.allocated_amount for c in budget_report.categories}

    for v in vendors:
        expected = cat_map.get(v.category_id, 0)
        assert v.estimated_budget == expected
        assert len(v.questions_to_ask) > 0


def test_vendor_custom_user_vendors():
    """Verify user-added vendors and quotes are preserved properly."""
    budget_report = calculate_budget(total_budget=500000, guest_count=100, event_type="wedding")
    existing_user_vendors = [
        UserVendor(
            id="v_1",
            category_id="catering",
            name="Sharma Catering Services",
            contact="9876543210",
            quote_amount=180000,
            status="shortlisted",
            notes="Tasting scheduled for Sunday"
        )
    ]

    vendors = build_vendor_checklist(
        event_type="wedding",
        budget_report=budget_report,
        existing_user_vendors=existing_user_vendors
    )

    catering_item = next(v for v in vendors if v.category_id == "catering")
    assert len(catering_item.user_vendors) == 1
    assert catering_item.user_vendors[0].name == "Sharma Catering Services"
    assert catering_item.user_vendors[0].quote_amount == 180000
