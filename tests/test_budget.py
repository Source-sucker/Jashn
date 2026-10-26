from app.services.budget import calculate_budget


def test_budget_exact_sum_rule():
    """Verify sum of all category allocations equals total_budget down to the exact rupee."""
    test_budgets = [
        10000,
        20000,
        45000,
        150000,
        800000,
        2500000,
        5000000,
        888800,  # Rounding check
        999999   # Odd single rupees
    ]

    for b in test_budgets:
        report = calculate_budget(total_budget=b, guest_count=100, event_type="wedding")
        total_sum = sum(c.allocated_amount for c in report.categories)
        assert total_sum == b, f"Failed exact sum for budget ₹{b}: got ₹{total_sum}"


def test_budget_floors_enforced():
    """Ensure categories do not drop below their minimum viable floors."""
    report = calculate_budget(
        total_budget=500000,
        guest_count=150,
        event_type="wedding",
        priorities=["catering"]
    )
    for cat in report.categories:
        if cat.category_id != "contingency":
            assert cat.allocated_amount >= cat.floor_amount, (
                f"Category {cat.category_id} allocation ₹{cat.allocated_amount} is below floor ₹{cat.floor_amount}"
            )


def test_budget_priority_shifts():
    """Verify top priority receives boosted allocation compared to default."""
    default_report = calculate_budget(
        total_budget=500000,
        guest_count=100,
        event_type="wedding",
        priorities=[]
    )
    priority_report = calculate_budget(
        total_budget=500000,
        guest_count=100,
        event_type="wedding",
        priorities=["photography_videography"]
    )

    default_photo = next(c.allocated_amount for c in default_report.categories if c.category_id == "photography_videography")
    boosted_photo = next(c.allocated_amount for c in priority_report.categories if c.category_id == "photography_videography")

    assert boosted_photo > default_photo, (
        f"Expected boosted photography allocation ({boosted_photo}) > default ({default_photo})"
    )


def test_budget_rounding_to_100():
    """Check that category allocations are rounded to ₹100."""
    report = calculate_budget(total_budget=345600, guest_count=75, event_type="birthday")
    for cat in report.categories:
        if cat.category_id != "contingency":
            assert cat.allocated_amount % 100 == 0, (
                f"Allocation ₹{cat.allocated_amount} for {cat.category_id} is not rounded to ₹100"
            )


def test_budget_feasibility_statuses():
    """Check feasibility returns comfortable, tight, and unrealistic appropriately."""
    # Comfortable: ₹10,00,000 for 50 guests = ₹20,000/head
    comf = calculate_budget(total_budget=1000000, guest_count=50, event_type="wedding")
    assert comf.feasibility_status == "comfortable"
    assert "comfortable" in comf.feasibility_reason.lower()

    # Tight: ₹1,50,000 for 150 guests = ₹1,000/head
    tight = calculate_budget(total_budget=150000, guest_count=150, event_type="wedding")
    assert tight.feasibility_status == "tight"
    assert "tight" in tight.feasibility_reason.lower()

    # Unrealistic: ₹20,000 for 200 guests = ₹100/head
    unreal = calculate_budget(total_budget=20000, guest_count=200, event_type="wedding")
    assert unreal.feasibility_status == "unrealistic"
    assert "unrealistic" in unreal.feasibility_reason.lower()


def test_budget_with_locked_categories():
    """Verify that locked categories preserve user-edited numbers during calculation."""
    report = calculate_budget(
        total_budget=500000,
        guest_count=100,
        event_type="wedding",
        locked_categories={"catering": 200000}
    )
    cat_item = next(c for c in report.categories if c.category_id == "catering")
    assert cat_item.allocated_amount == 200000
    assert cat_item.is_locked is True
    # And total sum still matches
    assert sum(c.allocated_amount for c in report.categories) == 500000
