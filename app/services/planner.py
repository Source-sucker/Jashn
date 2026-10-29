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

# ---------------------------------------------------------------------------
# Planner constants
# ---------------------------------------------------------------------------
#: Minimum budget amount (in INR) recognized from raw natural language input.
MIN_RECOGNIZABLE_BUDGET: int = 5000
#: Maximum clarifying questions to return when intake information is incomplete.
MAX_CLARIFYING_QUESTIONS: int = 3
#: Maximum sentences in cultural alignment notes.
MAX_CULTURAL_NOTE_SENTENCES: int = 2
#: Minimum themes returned for AI generation to be marked complete.
MIN_ENRICHMENT_THEMES: int = 3


def _read_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    with open(path, encoding="utf-8") as f:
        return f.read()


def _format_prompt(template: str, params: dict[str, Any]) -> str:
    for k, v in params.items():
        template = template.replace(f"{{{k}}}", str(v))
    return template


def _extract_event_type(lower: str) -> str | None:
    """Extracts known celebration event type from lowercase text."""
    if re.search(r"\b(wedding|shaadi|shadi|vivaah|marriage|reception|sangeet|mehendi|haldi|baraat)\b", lower):
        return "wedding"
    if re.search(r"\b(birthday|bday|janamdin)\b", lower):
        return "birthday"
    if re.search(r"\b(anniversary|salgirah)\b", lower):
        return "anniversary"
    if re.search(r"\b(community|puja|pooja|festival|diwali|navratri|durga|ganesh|samajik|jagran)\b", lower):
        return "community"
    if re.search(r"\b(corporate|annual meet|conference|seminar|office party|retreat)\b", lower):
        return "corporate"
    return None


def _extract_guest_count(desc: str) -> int | None:
    """Extracts attendee count from natural language text."""
    guest_match = re.search(
        r"(?:for|with|around|approx|approximately)?\s*(\d{1,5})\s*(?:guests?|people|attendees?|pax|persons?|members?|baraatis?|kids?|children)",
        desc,
        re.IGNORECASE,
    ) or re.search(r"(?:guests?|attendees?|pax|people|kids?|children)\s*(?:of|around|approx|count|:)?\s*(\d{1,5})", desc, re.IGNORECASE)
    if guest_match:
        try:
            cnt = int(guest_match.group(1))
            if cnt > 0:
                return cnt
        except ValueError:
            pass
    return None


def _extract_budget(desc: str) -> int | None:
    """Extracts estimated total budget in INR from text (handling Crore, Lakh, k, and numbers)."""
    crore_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:crores?|crs?|cr)\b", desc, re.IGNORECASE)
    if crore_match:
        return int(float(crore_match.group(1)) * 10_000_000)

    lakh_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:lakhs?|lacs?|lac|l)\b", desc, re.IGNORECASE)
    if lakh_match:
        return int(float(lakh_match.group(1)) * 100_000)

    thousand_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:k|thousand)\b", desc, re.IGNORECASE)
    if thousand_match:
        return int(float(thousand_match.group(1)) * 1_000)

    for pattern in (
        r"(?:budget\s*(?:of|is|:)?\s*)(?:₹|rs\.?|inr)?\s*(\d[\d,]+)",
        r"(\d[\d,]+)\s*(?:budget|inr|rs|rupees)",
        r"(?:₹|rs\.?)\s*(\d[\d,]+)",
    ):
        match = re.search(pattern, desc, re.IGNORECASE)
        if match:
            try:
                clean = int(match.group(1).replace(",", ""))
                if clean >= MIN_RECOGNIZABLE_BUDGET:
                    return clean
            except ValueError:
                pass
    return None


def _extract_city(desc: str) -> str | None:
    """Extracts known Indian tier-1/tier-2 city from description."""
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
            return c
    return None


def _extract_date(desc: str, lower: str) -> str | None:
    """Extracts or infers ISO event date from exact strings or relative month references."""
    iso_date = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", desc)
    if iso_date:
        return iso_date.group(1)

    in_months = re.search(r"\bin\s*(\d+)\s*months?\b", desc, re.IGNORECASE)
    if in_months:
        from datetime import date, timedelta
        n = int(in_months.group(1))
        return (date.today() + timedelta(days=n * 30)).strftime("%Y-%m-%d")

    month_names = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
        "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    for m_name, m_num in month_names.items():
        if re.search(rf"\b{m_name}\b", lower):
            from datetime import date
            today = date.today()
            year = today.year if m_num > today.month else today.year + 1
            return f"{year}-{m_num:02d}-15"
    return None


def _extract_intake_facts(desc: str) -> dict[str, Any]:
    """
    Fast deterministic extractor to instantly parse celebration facts from natural language.
    Eliminates up to 30 seconds of AI latency when required fields can be parsed deterministically.
    """
    if not desc:
        return {}
    facts: dict[str, Any] = {}
    lower = desc.lower()

    event_type = _extract_event_type(lower)
    if event_type:
        facts["event_type"] = event_type

    guests = _extract_guest_count(desc)
    if guests:
        facts["guest_count"] = guests

    budget = _extract_budget(desc)
    if budget:
        facts["total_budget"] = budget

    city = _extract_city(desc)
    if city:
        facts["city"] = city

    event_date = _extract_date(desc, lower)
    if event_date:
        facts["event_date"] = event_date

    return facts


def _build_complete_intake_response(
    request: IntakeRequest,
    params: dict[str, Any],
    desc: str,
    extracted_summary: str | None = None,
) -> IntakeResponse:
    """Builds a finalized IntakeResponse containing a complete EventBrief."""
    brief = EventBrief(
        event_type=params["event_type"],
        event_date=params["event_date"],
        city=params.get("city") or "Tier 2 City",
        guest_count=int(params["guest_count"]),
        total_budget=int(params["total_budget"]),
        priorities=request.priorities or [],
        venue_preference=request.venue_preference or "",
        dietary_cultural_notes=request.dietary_cultural_notes or "",
        vibe=request.vibe or "",
        user_description=desc
    )
    summary = extracted_summary or f"Event plan ready for {brief.event_type.title()} on {brief.event_date} with {brief.guest_count} guests."
    return IntakeResponse(
        is_complete=True,
        brief=brief,
        clarifying_questions=[],
        extracted_summary=summary
    )


def _parse_ai_intake_response(
    ai_data: dict[str, Any],
    request: IntakeRequest,
    desc: str,
) -> IntakeResponse | None:
    """Parses raw JSON from Gemini into a validated complete brief or clarifying questions."""
    is_comp = bool(ai_data.get("is_complete", False))
    brief_data = ai_data.get("brief")
    raw_questions = ai_data.get("clarifying_questions", [])

    if (
        is_comp
        and isinstance(brief_data, dict)
        and brief_data.get("event_type")
        and brief_data.get("event_date")
        and brief_data.get("guest_count")
        and brief_data.get("total_budget")
    ):
        return _build_complete_intake_response(
            request=request,
            params={
                "event_type": str(brief_data.get("event_type")),
                "event_date": str(brief_data.get("event_date")),
                "guest_count": brief_data.get("guest_count"),
                "total_budget": brief_data.get("total_budget"),
                "city": str(brief_data.get("city", request.city or "Tier 2 City")),
            },
            desc=desc,
            extracted_summary=ai_data.get("extracted_summary")
        )

    c_questions: list[ClarifyingQuestion] = []
    for q in raw_questions[:MAX_CLARIFYING_QUESTIONS]:
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
    return None


def _build_fallback_clarifying_questions(
    req_type: str,
    req_date: str,
    req_guests: int | None,
    req_budget: int | None,
) -> list[ClarifyingQuestion]:
    """Generates standardized clarifying questions for any missing required fields."""
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
    if not req_budget and len(questions) < MAX_CLARIFYING_QUESTIONS:
        questions.append(
            ClarifyingQuestion(
                field="total_budget",
                question="What is your estimated total budget in INR?",
                options=["₹50,000", "₹2,00,000", "₹5,00,000", "₹10,00,000"]
            )
        )
    return questions[:MAX_CLARIFYING_QUESTIONS]


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
        return _build_complete_intake_response(
            request,
            {
                "event_type": req_type,
                "event_date": req_date,
                "guest_count": req_guests,
                "total_budget": req_budget,
                "city": req_city,
            },
            desc,
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
                parsed = _parse_ai_intake_response(ai_data, request, desc)
                if parsed:
                    return parsed
        except Exception as e:
            logger.warning(f"AI intake extraction error: {e}")

    # 3. Deterministic fallback extraction if AI was unavailable or incomplete
    if desc:
        extracted = _extract_intake_facts(desc)
        req_type = req_type or extracted.get("event_type", "")
        req_date = req_date or extracted.get("event_date", "")
        req_guests = req_guests or extracted.get("guest_count")
        req_budget = req_budget or extracted.get("total_budget")
        req_city = req_city or extracted.get("city", "")

        if req_type and req_date and req_guests and req_budget:
            return _build_complete_intake_response(
                request,
                {
                    "event_type": req_type,
                    "event_date": req_date,
                    "guest_count": req_guests,
                    "total_budget": req_budget,
                    "city": req_city,
                },
                desc,
            )

    # 4. Deterministic clarifying questions fallback
    questions = _build_fallback_clarifying_questions(req_type, req_date, req_guests, req_budget)
    return IntakeResponse(
        is_complete=False,
        brief=None,
        clarifying_questions=questions,
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
                cultural_note = " ".join(note_sentences[:MAX_CULTURAL_NOTE_SENTENCES]) if len(note_sentences) > MAX_CULTURAL_NOTE_SENTENCES else raw_note.strip()
                v_qs = enrichment_data.get("vendor_questions", {})
                if isinstance(v_qs, dict):
                    vendor_custom_questions = v_qs

                if len(ai_themes) >= MIN_ENRICHMENT_THEMES:
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
