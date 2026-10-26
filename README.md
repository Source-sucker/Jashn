# Jashn — GenAI Celebration & Event Planner for Families
### Built for PromptWars Virtual Challenge 5

> **Promise:** Not just a list of generic ideas, but a deterministic event plan that fits your budget in INR and **adapts when things change**.

---

## 1. Chosen Persona & Core Promise
- **Primary Persona:** *"The Family Organizer"* — a first-time organizer in India planning a wedding, birthday, or community gathering on a fixed budget in INR, overwhelmed by moving pieces, vendor negotiations, and unpredictable changes.
- **Core Problem:** Standard AI tools hallucinate prices, fail exact arithmetic, fabricate non-existent businesses, and offer generic advice. When a family faces an emergency budget cut (-50%) or an event moved 2 weeks earlier, generic LLM prompts break down.
- **The Jashn Solution:** An architecture where **AI proposes, but code disposes**. Financial numbers, backward scheduled timelines, category floors, and trade-off calculations are executed by deterministic Python engines. Gemini GenAI is restricted to creative cultural phrasing, themes, menu concepts, and empathetic explanations.

---

## 2. Where Gemini is Used vs Where Deterministic Code Takes Over

| Capability | Engine Type | Technology | Why This Division Matters |
|---|---|---|---|
| **Intake Extraction** | Hybrid | Gemini 2.5 Flash + Fallback Rules | Extracts structured facts from unstructured Hindi/English stories; asks ≤ 3 clarifying questions if key parameters are missing. |
| **Budget Calculation** | **Deterministic Code** | `app/services/budget.py` (Largest-Remainder Method) | Sum of all categories **equals total budget down to the exact rupee**, rounded to ₹100. Enforces minimum floors and 5–10% contingency reserve. |
| **Timeline Scheduling** | **Deterministic Code** | `app/services/timeline.py` | Calculates deadlines backwards from event date. If days remaining are tight, compresses proportionally and flags `Rush`; overdue items flagged `Urgent`. Resolves dependency blocks. |
| **Themes, Menus & Activities** | **GenAI (Gemini)** | `app/prompts/plan_enrichment_v1.txt` | Generates 3 diverse cultural concepts (Budget-Friendly, Balanced, Grand) tailored to user dietary restrictions (Jain, Sattvic, Vegan) and vibe. |
| **Vendor Questions** | **GenAI (Gemini)** | `app/services/vendors.py` | Supplies targeted negotiation questions to ask vendors. **Never invents fake vendor businesses or phone numbers.** |
| **Replan & Trade-Offs** | **Deterministic Code + AI** | `app/services/replan.py` | Recalculates allocations preserving completed tasks and user-locked numbers; computes 2–3 concrete trade-offs with **exact mathematical rupee savings**. |

---

## 3. Architecture

```mermaid
graph TD
    User([Family Organizer]) -->|Enters description / details| Intake[POST /api/intake]
    Intake -->|Parse with Gemini or Rules| CheckComplete{Complete Brief?}
    CheckComplete -->|Missing Type/Date/Guests/Budget| Questions[Return <= 3 Clarifying Questions]
    Questions --> User
    CheckComplete -->|Complete| GenPlan[POST /api/plan]
    
    subgraph Deterministic Core
        GenPlan --> BudgetEng[budget.py: Priority shift, floors, ₹100 exact rounding]
        GenPlan --> TimeEng[timeline.py: Backward scheduling, rush compression]
        GenPlan --> VendorEng[vendors.py: Category questions & quote matching]
    end
    
    subgraph GenAI Layer (Single Call)
        GenPlan --> Gemini[Gemini 2.5 Flash / Flash Latest]
        Gemini --> Themes[3 Cultural Themes, Decor, Menu, Activities]
        Gemini --> VendorQs[Personalized Vendor Questions]
    end

    Gemini -.->|Timeout / Error / No Key| Fallback[fallback.py: Rule-based generation]
    
    BudgetEng --> Assembler[PlanResponse Assembler]
    TimeEng --> Assembler
    VendorEng --> Assembler
    Themes --> Assembler
    Fallback -.-> Assembler
    
    Assembler --> ClientStore[Client-side localStorage v1]
    ClientStore --> UI[Accessible Dashboard: Overview, Budget, Timeline, Vendors, Ideas]
    
    UI -->|Adjust budget, guests, date| Replan[POST /api/replan]
    Replan --> ReplanEng[replan.py: Preserves completed tasks & locked values]
    ReplanEng --> Diff[Diff summary + 3 calculated trade-offs]
    Diff --> UI
```

---

## 4. Key Assumptions & Disclaimers
1. **Illustrative Estimates:** All allocated budget amounts and vendor category figures are planning estimates based on Indian market benchmarks, not confirmed vendor quotes.
2. **Vendor Privacy & Safety:** Jashn never invents real business names, contact numbers, or availability. Users record their own vendor interactions in the private quote tracker.
3. **Stateless Server:** No user data or uploaded plans are stored in backend databases. All session data resides in the user's browser `localStorage` (schema version `v1`) and can be exported as JSON at any time.

---

## 5. Local Setup & Running

### Prerequisites
- Python 3.12+ (tested with Python 3.12 and 3.13)
- Node.js (v20+ for optional pure frontend unit tests)

### 1. Setup Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
```bash
cp .env.example .env
# Optional: add your Gemini API key in .env
# If left empty, Jashn automatically runs in full deterministic rule-based mode!
```

### 3. Run the Development Server
```bash
uvicorn app.main:app --reload --port 8000
```
Open your browser at **`http://localhost:8000`**.

---

## 6. Running Tests & Quality Checks

### Run Pytest Suite with Coverage (Target >= 85% on Services)
```bash
pytest --cov=app/services --cov=app/api -v
```

### Run Ruff Linter
```bash
ruff check app tests
```

### Run Frontend Helper Unit Tests (Node:test)
```bash
node --test tests/frontend_tests/test_store_helpers.mjs
```

---

## 7. Security & Accessibility (WCAG 2.1 AA)
- **Security:**
  - In-memory sliding-window IP rate limiter (`RATE_LIMIT_PER_MIN`).
  - Strict security headers (`Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`).
  - Body payload size capped at 1 MB.
  - User text treated strictly as raw data; prompt injection payloads are blocked at schema and prompt boundary.
  - Zero XSS risk: UI inserts dynamic content via `textContent` rather than `innerHTML`.
- **Accessibility:**
  - Accessible warm indigo (`#1e1b4b`) and festive marigold (`#d97706` / `#f59e0b`) palette meeting WCAG 2.1 AA contrast requirements.
  - Skip-to-main-content link, labelled form controls, and error summaries.
  - `aria-live="polite"` dynamic region for real-time announcements.
  - Full keyboard navigation on tabs (Arrow keys, Home, End) and focus-trapped dialog modals.
  - Respects `prefers-reduced-motion` media queries.

---

## 8. Known Limitations
- Multi-day multi-city logistics (e.g. destination weddings spanning 3 cities) are modeled as single consolidated event budgets.
- Currencies are strictly in Indian Rupees (INR); multi-currency conversion is out of scope.
