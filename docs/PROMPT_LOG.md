# Jashn — Prompt Engineering & System Prompt Log

## Version 1: Master Specification Prompt (Challenge 5)
```
ROLE
You are a senior full-stack engineer and product designer. Build "Jashn", a GenAI-powered
celebration & event planner web app, for PromptWars Virtual Challenge 5. Work inside the
cloned repo. Use ONE branch (main) only.

PERSONA & PROMISE
Primary user: "The Family Organizer": a first-time organizer in India planning a wedding,
birthday, or community event on a fixed budget in INR, overwhelmed by moving pieces.
Promise: not a list of ideas, but a plan that fits their budget and ADAPTS when things change.

PROCESS (follow in order)
1. Write docs/IMPLEMENTATION_PLAN.md (architecture, file list, test plan), then proceed.
2. Build everything below.
3. Run the tests. Start the server. Verify in the browser: happy path, replan path, and the
   AI-failure path. Fix what fails.
4. Commit in small, meaningful commits to main. Never create other branches.

TECH
- Python 3.12, FastAPI, Pydantic v2, uvicorn, google-genai SDK, pytest, pytest-cov, httpx, ruff.
- Frontend: vanilla HTML/CSS/ES modules. No frameworks, no build step. Served by FastAPI.
- Server is STATELESS. Client keeps plans in localStorage (schema-versioned, validated on load).
- Config only via env vars: GEMINI_API_KEY, GEMINI_MODEL (default "gemini-flash-latest"; make it
  easy to change), AI_TIMEOUT_SECONDS, RATE_LIMIT_PER_MIN, ALLOWED_ORIGINS. Provide .env.example.
- Keep dependencies minimal. Repo must stay far below 10 MB (no node_modules, media, or large
  assets; add a thorough .gitignore).
...
```

---

## Task Prompts

### 1. `app/prompts/intake_v1.txt`
- **Objective**: Parse unstructured event text or form inputs, extract critical fields (event type, date, guests, budget), or return up to 3 clarifying questions.
- **Guardrail**: Strict JSON schema output, instructions to treat user text purely as untrusted data, and prevention of hallucinated real vendors.

### 2. `app/prompts/plan_enrichment_v1.txt`
- **Objective**: Single-call enrichment generating 3 theme concepts (Budget-Friendly, Balanced, Grand), decor descriptions, dietary-compliant menus, interactive activities, and personalized vendor questions.
- **Guardrail**: Prohibits altering or calculating budget numbers (all numbers pre-computed by deterministic Python engine); strictly respects user dietary notes.

### 3. `app/prompts/ideas_refine_v1.txt`
- **Objective**: Fine-tune themes in real-time based on natural language feedback (e.g., "too expensive, make decor sustainable and add live chaat counters").
- **Guardrail**: Updates themes while maintaining the active budget allocation and brief constraints.

### 4. `app/prompts/replan_explain_v1.txt`
- **Objective**: Empathetically explain engine-calculated budget cuts, date changes, and mathematical trade-offs for the Family Organizer.

---

## Version 2: Stage 1.5 Hardening Prompt
```
Stage 1.5 hardening for Jashn. Stay on main. Do NOT add features. Commit each step separately.

1. Frontend checks (browser automation is unavailable): add tests/frontend_tests/test_modules.mjs that
   (a) syntax-parses every web/js file, (b) verifies every relative import resolves and every named
   import is exported, (c) verifies element ids referenced in JS exist in web/index.html or are
   created by the views. Run it in CI.
2. CSP audit: compare the Content-Security-Policy in app/security.py against web/index.html, the CSS,
   the inline SVG donut and all JS modules. Ensure nothing is blocked (inline styles, style attributes,
   data: URIs, fonts, ES modules). Do not use 'unsafe-inline' for scripts; remove inline <script> and
   on* handlers instead. Add tests asserting the CSP header and no inline scripts in index.html.
3. Rate limiter behind a proxy: use the real client IP from X-Forwarded-For only when
   TRUSTED_PROXY_COUNT is set (default safe), evict stale IP entries to cap memory, and add test
   covering trusted vs untrusted forward headers.
4. Real Gemini smoke test: add scripts/smoke_gemini.py that exercises the service layer with real
   inputs when GEMINI_API_KEY is present, prints the model name, latency, and whether output passed
   schema validation on the first try. Do not commit secrets. Document which model was tested.
5. Text clean-up: remove raw LaTeX/markdown artifacts (e.g. $N$) from UI strings/API responses; label
   trade-off percentages as estimates with a plain-language assumption note.
6. Coverage: enforce --cov-fail-under=85 on app/services and app/api in CI. Expand tests on the
   weakest modules.
7. Docs/README: add table "Where AI is used vs where deterministic code decides", Assumptions list,
   Screenshots section placeholder; append user prompts to docs/PROMPT_LOG.md.
8. Verify ruff, pytest, node --test pass, git status is clean on main, push to origin main. Report
   what was verified and what was NOT (be honest about browser automation).
```
