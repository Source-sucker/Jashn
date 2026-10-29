import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.models.schemas import (
    EventBrief,
    IdeasReport,
    IntakeRequest,
    IntakeResponse,
    PlanEnrichRequest,
    PlanResponse,
    RefineIdeasRequest,
    ReplanRequest,
    ReplanResponse,
    ThemeIdea,
)
from app.services.ai_client import ai_client
from app.services.planner import enrich_plan_ideas, generate_plan, process_intake
from app.services.replan import compute_replan

logger = logging.getLogger("jashn.routes")
router = APIRouter(prefix="/api", tags=["Jashn Core API"])
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _read_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    with open(path, encoding="utf-8") as f:
        return f.read()


def _format_prompt(template: str, params: dict[str, Any]) -> str:
    for k, v in params.items():
        template = template.replace(f"{{{k}}}", str(v))
    return template


@router.get("/health")
@router.get("/health/", include_in_schema=False)
async def health_check() -> dict[str, Any]:
    """Health status and configuration info."""
    return {
        "status": "ok",
        "app": "Jashn - Celebration & Event Planner",
        "version": "1.0.0",
        "model": settings.gemini_model,
        "ai_available": ai_client.is_available(),
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    }


@router.post("/intake", response_model=IntakeResponse)
@router.post("/intake/", response_model=IntakeResponse, include_in_schema=False)
async def intake_endpoint(request: IntakeRequest) -> IntakeResponse:
    """Extracts structured EventBrief or returns up to 3 clarifying questions."""
    try:
        return await process_intake(request)
    except Exception as e:
        logger.error(f"Error in /api/intake: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not process intake details. Please check your inputs."
        ) from e


@router.post("/plan", response_model=PlanResponse)
@router.post("/plan/", response_model=PlanResponse, include_in_schema=False)
async def plan_endpoint(brief: EventBrief, enrich: bool = True) -> PlanResponse:
    """Generates complete budget, timeline, vendor checklist, and personalized ideas."""
    try:
        return await generate_plan(brief, enrich=enrich)
    except Exception as e:
        logger.error(f"Error in /api/plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate celebration plan. Please verify event parameters."
        ) from e


@router.post("/plan/enrich", response_model=IdeasReport)
@router.post("/plan/enrich/", response_model=IdeasReport, include_in_schema=False)
async def plan_enrich_endpoint(request: PlanEnrichRequest) -> IdeasReport:
    """Asynchronously generates personalized AI themes & vendor questions for progressive UI."""
    try:
        ideas_report, _, _ = await enrich_plan_ideas(
            brief=request.brief,
            categories_summary=request.categories_summary,
            days_remaining=request.days_remaining
        )
        return ideas_report
    except Exception as e:
        logger.error(f"Error in /api/plan/enrich: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enrich celebration themes."
        ) from e


@router.post("/replan", response_model=ReplanResponse)
@router.post("/replan/", response_model=ReplanResponse, include_in_schema=False)
async def replan_endpoint(request: ReplanRequest) -> ReplanResponse:
    """
    Recomputes plan while preserving completed tasks and user-locked category estimates.
    Returns diff summary and 2-3 engine-calculated trade-off options.
    """
    try:
        return compute_replan(
            current_plan=request.current_plan,
            updated_budget=request.updated_budget,
            updated_guest_count=request.updated_guest_count,
            updated_date=request.updated_date,
            updated_priorities=request.updated_priorities,
            locked_categories=request.locked_categories,
            completed_task_ids=request.completed_task_ids
        )
    except Exception as e:
        logger.error(f"Error in /api/replan: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not replan with provided updates. Please verify parameters."
        ) from e


@router.post("/ideas/refine", response_model=IdeasReport)
@router.post("/ideas/refine/", response_model=IdeasReport, include_in_schema=False)
async def refine_ideas_endpoint(request: RefineIdeasRequest) -> IdeasReport:
    """Refines celebration theme ideas based on user follow-up prompt without restarting plan."""
    if not request.refinement_prompt.strip():
        return request.current_ideas

    if ai_client.is_available():
        try:
            template = _read_prompt("ideas_refine_v1.txt")
            current_themes_summary = "\n".join(
                f"- {t.title}: {t.tagline}. Decor: {t.decor_concept}. Menu: {', '.join(t.menu_highlights)}"
                for t in request.current_ideas.themes
            )
            prompt = _format_prompt(
                template,
                {
                    "event_type": request.brief.event_type,
                    "city": request.brief.city,
                    "guest_count": str(request.brief.guest_count),
                    "total_budget": str(request.brief.total_budget),
                    "dietary_cultural_notes": request.brief.dietary_cultural_notes or "Standard preferences",
                    "vibe": request.brief.vibe or "Warm celebration",
                    "current_ideas_json": current_themes_summary,
                    "refinement_prompt": request.refinement_prompt
                }
            )

            res = await ai_client.generate_json(prompt, task="refine")
            if res and isinstance(res, dict) and "themes" in res:
                refined_themes = []
                for idx, t in enumerate(res.get("themes", [])[:3]):
                    if isinstance(t, dict) and "title" in t:
                        refined_themes.append(
                            ThemeIdea(
                                id=f"refined_{idx + 1}",
                                title=t.get("title", f"Theme {idx + 1}"),
                                tagline=t.get("tagline", ""),
                                decor_concept=t.get("decor_concept", ""),
                                menu_highlights=list(t.get("menu_highlights", []))[:4],
                                activities=list(t.get("activities", []))[:3],
                                budget_category=t.get("budget_category", "decor_styling"),
                                fits_allocation=True,
                                estimated_tier=t.get("estimated_tier", "Balanced")
                            )
                        )
                if len(refined_themes) >= 2:
                    raw_note = str(res.get("cultural_alignment_note", f"Refined with request: '{request.refinement_prompt}'."))
                    import re
                    note_sentences = re.split(r"(?<=[.!?])\s+", raw_note.strip())
                    capped_note = " ".join(note_sentences[:2]) if len(note_sentences) > 2 else raw_note.strip()
                    return IdeasReport(
                        themes=refined_themes,
                        cultural_alignment_note=capped_note
                    )
        except Exception as e:
            logger.warning(f"AI refinement failed, falling back to local adjustment: {e}")

    # Fallback refinement: adjust titles/notes locally with user prompt
    updated_themes = []
    for t in request.current_ideas.themes:
        updated_themes.append(
            t.model_copy(
                update={
                    "tagline": f"{t.tagline} (Customized: {request.refinement_prompt[:40]})"
                }
            )
        )

    return IdeasReport(
        themes=updated_themes,
        cultural_alignment_note=f"Themes adjusted locally to accommodate: '{request.refinement_prompt}'."
    )


@router.get("/intake", include_in_schema=False)
@router.get("/intake/", include_in_schema=False)
@router.get("/plan", include_in_schema=False)
@router.get("/plan/", include_in_schema=False)
@router.get("/plan/enrich", include_in_schema=False)
@router.get("/plan/enrich/", include_in_schema=False)
@router.get("/replan", include_in_schema=False)
@router.get("/replan/", include_in_schema=False)
@router.get("/ideas/refine", include_in_schema=False)
@router.get("/ideas/refine/", include_in_schema=False)
async def api_endpoints_info() -> dict[str, str]:
    """Provides friendly guidance for browser visits to API endpoints."""
    return {
        "status": "ok",
        "message": "This Jashn API endpoint accepts POST requests with a JSON payload.",
        "ui": "/",
        "docs": "/docs"
    }
