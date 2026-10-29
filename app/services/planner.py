import logging
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.models.schemas import (
    ClarifyingQuestion,
    EventBrief,
    IdeasReport,
    IntakeRequest,
    IntakeResponse,
    PlanResponse,
    ThemeIdea,
)
from app.services.ai_client import ai_client
from app.services.budget import calculate_budget
from app.services.fallback import build_fallback_plan
from app.services.timeline import calculate_timeline
from app.services.vendors import build_vendor_checklist

logger = logging.getLogger("jashn.planner")
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _read_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    with open(path, encoding="utf-8") as f:
        return f.read()


def _format_prompt(template: str, params: dict[str, Any]) -> str:
    for k, v in params.items():
        template = template.replace(f"{{{k}}}", str(v))
    return template


def _extract_intake_facts(desc: str) -> dict[str, Any]:
    """
    Fast deterministic extractor to instantly parse celebration facts from natural language.
    Eliminates up to 30 seconds of AI latency when required fields can be parsed deterministically.
    """
    if not desc:
        return {}
    facts: dict[str, Any] = {}
    lower = desc.lower()

    # 1. Event Type
    if re.search(r"\b(wedding|shaadi|shadi|vivaah|marriage|reception|sangeet|mehendi|haldi|baraat)\b", lower):
        facts["event_type"] = "wedding"
    elif re.search(r"\b(birthday|bday|janamdin)\b", lower):
        facts["event_type"] = "birthday"
    elif re.search(r"\b(anniversary|salgirah)\b", lower):
        facts["event_type"] = "anniversary"
    elif re.search(r"\b(community|puja|pooja|festival|diwali|navratri|durga|ganesh|samajik|jagran)\b", lower):
        facts["event_type"] = "community"
    elif re.search(r"\b(corporate|annual meet|conference|seminar|office party|retreat)\b", lower):
        facts["event_type"] = "corporate"

    # 2. Guest Count
    guest_match = re.search(
        r"(?:for|with|around|approx|approximately)?\s*(\d{1,5})\s*(?:guests?|people|attendees?|pax|persons?|members?|baraatis?|kids?|children)",
        desc,
        re.IGNORECASE,
    ) or re.search(r"(?:guests?|attendees?|pax|people|kids?|children)\s*(?:of|around|approx|count|:)?\s*(\d{1,5})", desc, re.IGNORECASE)
    if guest_match:
        try:
            cnt = int(guest_match.group(1))
            if cnt > 0:
                facts["guest_count"] = cnt
        except ValueError:
            pass

    # 3. Budget in INR
    crore_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:crores?|crs?|cr)\b", desc, re.IGNORECASE)
    lakh_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:lakhs?|lacs?|lac|l)\b", desc, re.IGNORECASE)
    thousand_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:k|thousand)\b", desc, re.IGNORECASE)
    budget_prefix = re.search(r"(?:budget\s*(?:of|is|:)?\s*)(?:₹|rs\.?|inr)?\s*(\d[\d,]+)", desc, re.IGNORECASE)
    budget_suffix = re.search(r"(\d[\d,]+)\s*(?:budget|inr|rs|rupees)", desc, re.IGNORECASE)
    direct_curr = re.search(r"(?:₹|rs\.?)\s*(\d[\d,]+)", desc, re.IGNORECASE)

    if crore_match:
        facts["total_budget"] = int(float(crore_match.group(1)) * 10_000_000)
    elif lakh_match:
        facts["total_budget"] = int(float(lakh_match.group(1)) * 100_000)
    elif thousand_match:
        facts["total_budget"] = int(float(thousand_match.group(1)) * 1_000)
    elif budget_prefix:
        try:
            clean = int(budget_prefix.group(1).replace(",", ""))
            if clean >= 5000:
                facts["total_budget"] = clean
        except ValueError:
            pass
    elif budget_suffix:
        try:
            clean = int(budget_suffix.group(1).replace(",", ""))
            if clean >= 5000:
                facts["total_budget"] = clean
        except ValueError:
            pass
    elif direct_curr:
        try:
            clean = int(direct_curr.group(1).replace(",", ""))
            if clean >= 5000:
                facts["total_budget"] = clean
        except ValueError:
            pass

    # 4. City
    known_cities = [
        "Lucknow", "Jaipur", "Delhi", "New Delhi", "Mumbai", "Bengaluru", "Bangalore",
        "Kolkata", "Hyderabad", "Chennai", "Pune", "Ahmedabad", "Chandigarh", "Udaipur",
        "Agra", "Varanasi", "Indore", "Bhopal", "Goa", "Surat", "Patna", "Kanpur",
        "Nagpur", "Vadodara", "Ghaziabad", "Ludhiana", "Nashik", "Faridabad", "Meerut",
        "Rajkot", "Kochi", "Coimbatore", "Amritsar", "Dehradun", "Jodhpur", "Shimla",
        "Noida", "Gurgaon", "Gurugram",
    ]
    for c in known_cities:
        if re.search(rf"\b{c}\b", desc, re.IGNORECASE):
            facts["city"] = c
            break

    # 5. Date
    iso_date = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", desc)
    if iso_date:
        facts["event_date"] = iso_date.group(1)
    else:
        month_names = {
            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
            "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
            "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
        }
        in_months = re.search(r"\bin\s*(\d+)\s*months?\b", desc, re.IGNORECASE)
        if in_months:
            from datetime import date, timedelta
            n = int(in_months.group(1))
            facts["event_date"] = (date.today() + timedelta(days=n * 30)).strftime("%Y-%m-%d")
        else:
            for m_name, m_num in month_names.items():
                if re.search(rf"\b{m_name}\b", lower):
                    from datetime import date
                    today = date.today()
                    year = today.year if m_num > today.month else today.year + 1
                    facts["event_date"] = f"{year}-{m_num:02d}-15"
                    break

    return facts


async def process_intake(request: IntakeRequest) -> IntakeResponse:
    """
    Intake processor:
    - Parses free-text description and form fields
    - When form is fully structured, skips AI intake completely
    - When free-text is provided and fields are missing, uses Gemini to extract or clarify
    - If AI is unavailable or fails, uses fast deterministic extraction before falling back to clarifying questions
    """
    req_type = request.event_type or ""
    req_date = request.event_date or ""
    req_guests = request.guest_count
    req_budget = request.total_budget
    req_city = request.city or ""
    desc = (request.description or "").strip()

    # 1. Skip AI intake call completely if all critical form fields are provided
    if req_type and req_date and req_guests and req_budget:
        brief = EventBrief(
            event_type=req_type,
            event_date=req_date,
            city=req_city or "Tier 2 City",
            guest_count=req_guests,
            total_budget=req_budget,
            priorities=request.priorities or [],
            venue_preference=request.venue_preference or "",
            dietary_cultural_notes=request.dietary_cultural_notes or "",
            vibe=request.vibe or "",
            user_description=desc
        )
        return IntakeResponse(
            is_complete=True,
            brief=brief,
            clarifying_questions=[],
            extracted_summary=f"Event plan ready for {brief.event_type.title()} on {brief.event_date} with {brief.guest_count} guests."
        )

    # 2. If AI client is available and user provided description, use Gemini to parse & clarify
    if ai_client.is_available() and desc:
        try:
            template = _read_prompt("intake_v1.txt")
            prompt = _format_prompt(
                template,
                {
                    "description": desc,
                    "event_type": req_type or "Not specified",
                    "event_date": req_date or "Not specified",
                    "city": request.city or "Not specified",
                    "guest_count": str(req_guests) if req_guests else "Not specified",
                    "total_budget": str(req_budget) if req_budget else "Not specified",
                    "priorities": ", ".join(request.priorities or []) or "Not specified",
                    "venue_preference": request.venue_preference or "Not specified",
                    "dietary_cultural_notes": request.dietary_cultural_notes or "Not specified",
                    "vibe": request.vibe or "Not specified"
                }
            )

            ai_data = await ai_client.generate_json(prompt, task="intake")
            if ai_data and isinstance(ai_data, dict):
                is_comp = bool(ai_data.get("is_complete", False))
                brief_data = ai_data.get("brief")
                raw_questions = ai_data.get("clarifying_questions", [])

                if is_comp and brief_data and isinstance(brief_data, dict):
                    # Ensure critical fields have valid values
                    if (
                        brief_data.get("event_type")
                        and brief_data.get("event_date")
                        and brief_data.get("guest_count")
                        and brief_data.get("total_budget")
                    ):
                        brief = EventBrief(
                            event_type=str(brief_data.get("event_type")),
                            event_date=str(brief_data.get("event_date")),
                            city=str(brief_data.get("city", request.city or "Tier 2 City")),
                            guest_count=int(brief_data.get("guest_count")),
                            total_budget=int(brief_data.get("total_budget")),
                            priorities=list(brief_data.get("priorities", request.priorities or [])),
                            venue_preference=str(brief_data.get("venue_preference", request.venue_preference or "")),
                            dietary_cultural_notes=str(brief_data.get("dietary_cultural_notes", request.dietary_cultural_notes or "")),
                            vibe=str(brief_data.get("vibe", request.vibe or "")),
                            user_description=desc
                        )
                        return IntakeResponse(
                            is_complete=True,
                            brief=brief,
                            clarifying_questions=[],
                            extracted_summary=ai_data.get("extracted_summary")
                        )

                # Not complete: parse clarifying questions (at most 3)
                c_questions = []
                for q in raw_questions[:3]:
                    if isinstance(q, dict) and "field" in q and "question" in q:
                        c_questions.append(
                            ClarifyingQuestion(
                                field=q["field"],
                                question=q["question"],
                                options=q.get("options")
                            )
                        )

                if c_questions:
                    return IntakeResponse(
                        is_complete=False,
                        brief=None,
                        clarifying_questions=c_questions,
                        extracted_summary=ai_data.get("extracted_summary")
                    )
        except Exception as e:
            logger.warning(f"AI intake extraction error: {e}")

    # 3. Deterministic fallback extraction if AI was unavailable or incomplete
    if desc:
        extracted = _extract_intake_facts(desc)
        if not req_type and extracted.get("event_type"):
            req_type = extracted["event_type"]
        if not req_date and extracted.get("event_date"):
            req_date = extracted["event_date"]
        if not req_guests and extracted.get("guest_count"):
            req_guests = extracted["guest_count"]
        if not req_budget and extracted.get("total_budget"):
            req_budget = extracted["total_budget"]
        if not req_city and extracted.get("city"):
            req_city = extracted["city"]

        if req_type and req_date and req_guests and req_budget:
            brief = EventBrief(
                event_type=req_type,
                event_date=req_date,
                city=req_city or "Tier 2 City",
                guest_count=req_guests,
                total_budget=req_budget,
                priorities=request.priorities or [],
                venue_preference=request.venue_preference or "",
                dietary_cultural_notes=request.dietary_cultural_notes or "",
                vibe=request.vibe or "",
                user_description=desc
            )
            return IntakeResponse(
                is_complete=True,
                brief=brief,
                clarifying_questions=[],
                extracted_summary=f"Event plan ready for {brief.event_type.title()} on {brief.event_date} with {brief.guest_count} guests."
            )

    # 4. Deterministic clarifying questions fallback
    questions: list[ClarifyingQuestion] = []
    if not req_type:
        questions.append(
            ClarifyingQuestion(
                field="event_type",
                question="What kind of celebration are you organizing?",
                options=["Wedding / Reception", "Birthday Party", "Community Festival / Puja", "Anniversary Celebration", "Corporate Gathering"]
            )
        )
    if not req_date:
        questions.append(
            ClarifyingQuestion(
                field="event_date",
                question="When is the event scheduled to take place?",
                options=None
            )
        )
    if not req_guests:
        questions.append(
            ClarifyingQuestion(
                field="guest_count",
                question="Approximately how many guests will be attending?",
                options=["50 guests", "100 guests", "250 guests", "500 guests"]
            )
        )
    if not req_budget and len(questions) < 3:
        questions.append(
            ClarifyingQuestion(
                field="total_budget",
                question="What is your estimated total budget in INR?",
                options=["₹50,000", "₹2,00,000", "₹5,00,000", "₹10,00,000"]
            )
        )

    return IntakeResponse(
        is_complete=False,
        brief=None,
        clarifying_questions=questions[:3],
        extracted_summary="Please provide the missing details to generate your tailored budget and timeline."
    )


async def enrich_plan_ideas(
    brief: EventBrief,
    categories_summary: str | None = None,
    days_remaining: int | None = None
) -> tuple[IdeasReport, dict[str, list[str]], bool]:
    """
    Enriches plan ideas via Gemini. Returns (IdeasReport, vendor_questions, is_ai_generated).
    Falls back to deterministic curated themes on failure.
    """
    ai_themes: list[ThemeIdea] = []
    cultural_note = ""
    vendor_custom_questions: dict[str, list[str]] = {}
    is_ai_generated = False

    if ai_client.is_available():
        try:
            template = _read_prompt("plan_enrichment_v1.txt")
            prompt = _format_prompt(
                template,
                {
                    "event_type": brief.event_type,
                    "event_date": brief.event_date,
                    "days_remaining": str(days_remaining or 90),
                    "city": brief.city,
                    "guest_count": str(brief.guest_count),
                    "total_budget": str(brief.total_budget),
                    "priorities": ", ".join(brief.priorities) if brief.priorities else "None specified",
                    "venue_preference": brief.venue_preference or "Flexible",
                    "dietary_cultural_notes": brief.dietary_cultural_notes or "Standard regional preferences",
                    "vibe": brief.vibe or "Warm and welcoming",
                    "user_description": brief.user_description or "None provided",
                    "categories_summary": categories_summary or "Standard budget allocation"
                }
            )

            enrichment_data = await ai_client.generate_json(prompt, task="enrich", timeout=12.0)
            if enrichment_data and isinstance(enrichment_data, dict):
                raw_themes = enrichment_data.get("themes", [])
                for idx, t in enumerate(raw_themes[:3]):
                    if isinstance(t, dict) and "title" in t:
                        ai_themes.append(
                            ThemeIdea(
                                id=f"theme_{idx + 1}",
                                title=t.get("title", f"Theme {idx + 1}"),
                                tagline=t.get("tagline", ""),
                                decor_concept=t.get("decor_concept", ""),
                                menu_highlights=list(t.get("menu_highlights", []))[:2],
                                activities=list(t.get("activities", []))[:2],
                                budget_category=t.get("budget_category", "decor_styling"),
                                fits_allocation=True,
                                estimated_tier=t.get("estimated_tier", "Balanced")
                            )
                        )

                raw_note = str(enrichment_data.get("cultural_alignment_note", ""))
                import re
                note_sentences = re.split(r"(?<=[.!?])\s+", raw_note.strip())
                cultural_note = " ".join(note_sentences[:2]) if len(note_sentences) > 2 else raw_note.strip()
                v_qs = enrichment_data.get("vendor_questions", {})
                if isinstance(v_qs, dict):
                    vendor_custom_questions = v_qs

                if len(ai_themes) >= 3:
                    is_ai_generated = True
        except Exception as e:
            logger.warning(f"Plan enrichment error, falling back to rule-based ideas: {e}")

    # Fallback to deterministic ideas if AI failed or unconfigured
    if not ai_themes:
        fallback_plan = build_fallback_plan(brief)
        ai_themes = fallback_plan.ideas.themes
        cultural_note = fallback_plan.ideas.cultural_alignment_note

    ideas_report = IdeasReport(
        themes=ai_themes,
        cultural_alignment_note=cultural_note or f"Personalized plan tailored for {brief.event_type.title()} in {brief.city}."
    )
    return ideas_report, vendor_custom_questions, is_ai_generated


async def generate_plan(brief: EventBrief, enrich: bool = True) -> PlanResponse:
    """
    Main Plan Orchestrator:
    - Runs deterministic budget engine
    - Runs deterministic timeline engine
    - If enrich=True: calls Gemini for personalized themes, decor, menu, and vendor questions
    - If enrich=False: fast deterministic path returning budget and timeline immediately
    - If AI call fails or is unconfigured, uses deterministic fallback without failing
    """
    # 1. Deterministic Engines Execution
    budget_report = calculate_budget(
        total_budget=brief.total_budget,
        guest_count=brief.guest_count,
        event_type=brief.event_type,
        priorities=brief.priorities,
        city=brief.city
    )

    timeline_report = calculate_timeline(
        event_date_str=brief.event_date,
        event_type=brief.event_type
    )

    # 2. Themes & Ideas Enrichment
    if enrich:
        cat_summary = ", ".join(
            f"{c.label}: ₹{c.allocated_amount:,}" for c in budget_report.categories
        )
        ideas_report, vendor_custom_questions, is_ai_generated = await enrich_plan_ideas(
            brief=brief,
            categories_summary=cat_summary,
            days_remaining=timeline_report.days_remaining
        )
        ai_status_message = (
            "AI personalized plan with tailored cultural themes & vendor questions"
            if is_ai_generated
            else "AI unavailable: rule-based plan built from your inputs"
        )
    else:
        # Fast progressive path: instantaneous deterministic return
        fallback_plan = build_fallback_plan(brief)
        ideas_report = fallback_plan.ideas
        vendor_custom_questions = {}
        is_ai_generated = False
        ai_status_message = "Fast deterministic plan ready"

    vendor_items = build_vendor_checklist(
        event_type=brief.event_type,
        budget_report=budget_report,
        ai_personalized_questions=vendor_custom_questions
    )

    plan_id = f"plan_{uuid.uuid4().hex[:10]}"
    created_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    return PlanResponse(
        plan_id=plan_id,
        created_at=created_at,
        schema_version="v1",
        is_ai_generated=is_ai_generated,
        ai_status_message=ai_status_message,
        brief=brief,
        budget=budget_report,
        timeline=timeline_report,
        vendors=vendor_items,
        ideas=ideas_report
    )
