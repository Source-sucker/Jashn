import json
from pathlib import Path
from typing import Optional

from app.models.schemas import BudgetReport, UserVendor, VendorCategoryItem

TEMPLATES_PATH = Path(__file__).parent.parent / "data" / "event_templates.json"


def load_event_templates() -> dict:
    with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_vendor_checklist(
    event_type: str,
    budget_report: BudgetReport,
    ai_personalized_questions: Optional[dict[str, list[str]]] = None,
    existing_user_vendors: Optional[list[UserVendor]] = None
) -> list[VendorCategoryItem]:
    """
    Builds the vendor checklist per category.
    - Matches estimated budget from the deterministic budget report.
    - Attaches baseline vendor questions plus any AI-personalized questions.
    - Preserves user-added vendor records (quotes, status, notes).
    - NEVER generates fake businesses or phone numbers.
    """
    templates = load_event_templates()
    template = templates.get(event_type.lower()) or templates["wedding"]
    raw_cats = template.get("vendor_categories", [])
    ai_questions = ai_personalized_questions or {}

    # Map category budget allocations
    budget_map: dict[str, int] = {
        cat.category_id: cat.allocated_amount for cat in budget_report.categories
    }

    # Group existing user vendors by category if present
    vendors_by_cat: dict[str, list[UserVendor]] = {}
    if existing_user_vendors:
        for uv in existing_user_vendors:
            # Match to a category or default
            cid = getattr(uv, "category_id", "catering")
            vendors_by_cat.setdefault(cid, []).append(uv)

    result: list[VendorCategoryItem] = []
    for rc in raw_cats:
        cid = rc["id"]
        est_amount = budget_map.get(cid, 0)
        default_qs = list(rc.get("default_questions", []))
        # If AI provided custom questions for this category, prepend or merge them
        if cid in ai_questions and ai_questions[cid]:
            merged_qs = ai_questions[cid] + [q for q in default_qs if q not in ai_questions[cid]]
        else:
            merged_qs = default_qs

        result.append(
            VendorCategoryItem(
                category_id=cid,
                name=rc.get("name", cid.replace("_", " ").title()),
                estimated_budget=est_amount,
                questions_to_ask=merged_qs[:5],
                user_vendors=vendors_by_cat.get(cid, [])
            )
        )

    return result
