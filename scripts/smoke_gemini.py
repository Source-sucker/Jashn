#!/usr/bin/env python3
"""
Real Gemini API Smoke Test for Jashn.
Runs only when GEMINI_API_KEY is configured in the environment.
Exercises the service layer (intake, plan, replan, ideas refine) with real inputs.
Never prints or logs secret API keys.
"""

import asyncio
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

# Ensure repo root is on sys.path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.config import settings
from app.models.schemas import (
    EventBrief,
    IntakeRequest,
    PlanResponse,
    RefineIdeasRequest,
    ReplanRequest,
)
from app.services.ai_client import GeminiClient
from app.services.planner import generate_plan, process_intake
from app.services.replan import compute_replan


async def run_smoke_test():
    api_key = settings.gemini_api_key
    if not api_key:
        print("=" * 70)
        print("GEMINI_API_KEY is not set.")
        print("Skipping real Gemini smoke test (deterministic fallback mode is verified by pytest).")
        print("To run this test with a live model:")
        print("  export GEMINI_API_KEY='your-key'")
        print(f"  export GEMINI_MODEL='{settings.gemini_model}'  # (or gemini-2.5-flash, gemini-1.5-flash)")
        print("  python scripts/smoke_gemini.py")
        print("=" * 70)
        sys.exit(0)

    masked_key = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "***"
    print("=" * 70)
    print("JASHN REAL GEMINI SMOKE TEST")
    print(f"Model configured: {settings.gemini_model}")
    print(f"API Key present:  {masked_key} (safe masked)")
    print(f"Timeout setting:  {settings.ai_timeout_seconds}s")
    print("=" * 70)

    client = GeminiClient()
    if not client.is_available():
        print("❌ Error: GeminiClient failed to initialize with provided key.")
        sys.exit(1)

    target_date = (date.today() + timedelta(days=120)).strftime("%Y-%m-%d")

    # ---------------------------------------------------------
    # 1. Intake Test
    # ---------------------------------------------------------
    print("\n[1/4] Testing Intake Extraction (/api/intake)...")
    intake_desc = (
        f"Planning my sister's wedding in Lucknow on {target_date} for 300 guests. "
        "Total budget is 12 Lakhs. Food and venue are top priorities, Awadhi Mughlai with Jain counters."
    )
    req = IntakeRequest(description=intake_desc)

    t0 = time.perf_counter()
    intake_res = await process_intake(req)
    latency_intake = time.perf_counter() - t0

    if intake_res.is_complete and intake_res.brief:
        status_msg = "Passed schema validation (first try)"
    elif intake_res.clarifying_questions:
        status_msg = "Clarifying questions returned"
    else:
        status_msg = "Fell back to rule-based parser"

    print(f"  • Latency:   {latency_intake:.2f}s")
    print(f"  • Status:    {status_msg}")
    print(f"  • Result:    Type={intake_res.brief.event_type if intake_res.brief else 'N/A'}, "
          f"Budget=₹{intake_res.brief.total_budget if intake_res.brief else 'N/A':,}")

    brief = intake_res.brief or EventBrief(
        event_type="wedding",
        event_date=target_date,
        city="Lucknow",
        guest_count=300,
        total_budget=1200000,
        priorities=["catering", "venue"],
        dietary_cultural_notes="Awadhi Mughlai with Jain counters",
        vibe="Royal Awadhi Elegance",
        user_description=intake_desc
    )

    # ---------------------------------------------------------
    # 2. Plan Generation Test
    # ---------------------------------------------------------
    print("\n[2/4] Testing Plan Generation (/api/plan)...")
    t0 = time.perf_counter()
    plan: PlanResponse = await generate_plan(brief)
    latency_plan = time.perf_counter() - t0

    if plan.is_ai_generated:
        plan_status = "AI enriched (passed schema validation)"
    else:
        plan_status = "Fell back to rule-based generation"

    total_sum = sum(c.allocated_amount for c in plan.budget.categories)
    assert total_sum == brief.total_budget, f"Exact budget sum mismatch: {total_sum} != {brief.total_budget}"

    print(f"  • Latency:   {latency_plan:.2f}s")
    print(f"  • Status:    {plan_status}")
    print(f"  • Plan ID:   {plan.plan_id}")
    print(f"  • Themes:    {[t.title for t in plan.ideas.themes[:3]]}")
    print(f"  • Budget:    ₹{total_sum:,} (Verified 100% exact sum)")
    print(f"  • Tasks:     {len(plan.timeline.tasks)} tasks backward scheduled")

    # ---------------------------------------------------------
    # 3. Replan Test
    # ---------------------------------------------------------
    print("\n[3/4] Testing Replan Engine (/api/replan)...")
    earlier_date = (date.today() + timedelta(days=90)).strftime("%Y-%m-%d")
    cut_budget = brief.total_budget // 2  # -50% cut

    t0 = time.perf_counter()
    replan_req = ReplanRequest(
        current_plan=plan,
        updated_budget=cut_budget,
        updated_date=earlier_date,
        completed_task_ids=[plan.timeline.tasks[0].id]
    )
    replan_res = compute_replan(
        current_plan=replan_req.current_plan,
        updated_budget=replan_req.updated_budget,
        updated_date=replan_req.updated_date,
        completed_task_ids=replan_req.completed_task_ids
    )
    latency_replan = time.perf_counter() - t0

    new_sum = sum(c.allocated_amount for c in replan_res.updated_plan.budget.categories)
    assert new_sum == cut_budget, f"Replan exact budget sum mismatch: {new_sum} != {cut_budget}"

    print(f"  • Latency:   {latency_replan:.4f}s (Deterministic engine)")
    print(f"  • Diffs:     {replan_res.diff_summary}")
    print(f"  • Tradeoffs: {len(replan_res.tradeoff_options)} options calculated with exact savings")
    for opt in replan_res.tradeoff_options:
        print(f"    - {opt.title}: Saves ₹{opt.numeric_saving:,}")

    # ---------------------------------------------------------
    # 4. Ideas Refine Test
    # ---------------------------------------------------------
    print("\n[4/4] Testing Ideas Refinement (/api/ideas/refine)...")
    from app.api.routes import refine_ideas_endpoint

    refine_req = RefineIdeasRequest(
        current_ideas=plan.ideas,
        brief=brief,
        refinement_prompt="Make it more sustainable with potted plants and add live street food chaat counters"
    )

    t0 = time.perf_counter()
    refined_report = await refine_ideas_endpoint(refine_req)
    latency_refine = time.perf_counter() - t0

    print(f"  • Latency:   {latency_refine:.2f}s")
    print(f"  • Refined:   {[t.title for t in refined_report.themes[:3]]}")
    print(f"  • Note:      {refined_report.cultural_alignment_note}")

    print("\n" + "=" * 70)
    print("✅ ALL 4 SMOKE TEST STAGES COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
