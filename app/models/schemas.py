from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class EventBrief(BaseModel):
    event_type: str = Field(description="Normalized event type: wedding, birthday, community, anniversary, corporate")
    event_date: str = Field(description="Event date in YYYY-MM-DD format")
    city: str = Field(default="Tier 2 City", description="Event city in India")
    guest_count: int = Field(ge=1, le=50000, description="Estimated total guests")
    total_budget: int = Field(ge=5000, le=1000000000, description="Total budget in INR")
    priorities: list[str] = Field(default_factory=list, description="Ordered priority categories")
    venue_preference: Optional[str] = Field(default="", description="e.g. Banquet Hall, Open Lawn, Home")
    dietary_cultural_notes: Optional[str] = Field(default="", description="Cultural, vegetarian, Jain, regional specifics")
    vibe: Optional[str] = Field(default="", description="e.g. Royal Traditional, Modern Minimalist, Festive Community")
    user_description: Optional[str] = Field(default="", description="Original user text input")

    @field_validator("event_type")
    @classmethod
    def normalize_event_type(cls, v: str) -> str:
        v_clean = v.lower().strip()
        for key in ["wedding", "birthday", "community", "anniversary", "corporate"]:
            if key in v_clean:
                return key
        if "shaadi" in v_clean or "marriage" in v_clean or "reception" in v_clean or "sangeet" in v_clean:
            return "wedding"
        if "bday" in v_clean or "party" in v_clean:
            return "birthday"
        if "puja" in v_clean or "festival" in v_clean or "utsav" in v_clean or "society" in v_clean or "eid" in v_clean or "diwali" in v_clean:
            return "community"
        if "jubilee" in v_clean:
            return "anniversary"
        return "wedding"


class ClarifyingQuestion(BaseModel):
    field: str
    question: str
    options: Optional[list[str]] = None


class IntakeRequest(BaseModel):
    description: Optional[str] = Field(default="", max_length=2000)
    event_type: Optional[str] = Field(default=None, max_length=100)
    event_date: Optional[str] = Field(default=None, max_length=20)
    city: Optional[str] = Field(default=None, max_length=100)
    guest_count: Optional[int] = Field(default=None, ge=1, le=50000)
    total_budget: Optional[int] = Field(default=None, ge=5000, le=1000000000)
    priorities: Optional[list[str]] = Field(default_factory=list)
    venue_preference: Optional[str] = Field(default=None, max_length=200)
    dietary_cultural_notes: Optional[str] = Field(default=None, max_length=500)
    vibe: Optional[str] = Field(default=None, max_length=200)


class IntakeResponse(BaseModel):
    is_complete: bool
    brief: Optional[EventBrief] = None
    clarifying_questions: list[ClarifyingQuestion] = Field(default_factory=list)
    extracted_summary: Optional[str] = None


class BudgetCategoryAllocation(BaseModel):
    category_id: str
    label: str
    allocated_amount: int
    percentage: float
    floor_amount: int
    is_locked: bool = False
    actual_spent: int = 0
    notes: Optional[str] = None


class BudgetReport(BaseModel):
    total_budget: int
    contingency_amount: int
    allocated_subtotal: int
    categories: list[BudgetCategoryAllocation]
    feasibility_status: str  # "comfortable" | "tight" | "unrealistic"
    feasibility_reason: str
    per_guest_spend: int


class TimelineTask(BaseModel):
    id: str
    title: str
    phase: str
    due_date: str
    days_before_event: int
    priority: str  # "high" | "medium" | "low"
    category: str
    depends_on: list[str] = Field(default_factory=list)
    is_completed: bool = False
    is_rush: bool = False
    is_urgent: bool = False
    is_blocked: bool = False
    notes: Optional[str] = None


class TimelineReport(BaseModel):
    event_date: str
    days_remaining: int
    is_compressed: bool
    tasks: list[TimelineTask]
    phases: list[str]


class UserVendor(BaseModel):
    id: str
    category_id: str = "catering"
    name: str
    contact: Optional[str] = ""
    quote_amount: Optional[int] = None
    status: str = "pending"  # "pending" | "shortlisted" | "confirmed"
    notes: Optional[str] = ""


class VendorCategoryItem(BaseModel):
    category_id: str
    name: str
    estimated_budget: int
    questions_to_ask: list[str]
    user_vendors: list[UserVendor] = Field(default_factory=list)


class ThemeIdea(BaseModel):
    id: str
    title: str
    tagline: str
    decor_concept: str
    menu_highlights: list[str]
    activities: list[str]
    budget_category: str
    fits_allocation: bool
    estimated_tier: str  # "Budget-Friendly" | "Balanced" | "Grand"


class IdeasReport(BaseModel):
    themes: list[ThemeIdea]
    cultural_alignment_note: str


class PlanResponse(BaseModel):
    plan_id: str
    created_at: str
    schema_version: str = "v1"
    is_ai_generated: bool
    ai_status_message: str
    brief: EventBrief
    budget: BudgetReport
    timeline: TimelineReport
    vendors: list[VendorCategoryItem]
    ideas: IdeasReport


class ReplanRequest(BaseModel):
    current_plan: PlanResponse
    updated_budget: Optional[int] = Field(default=None, ge=5000, le=1000000000)
    updated_guest_count: Optional[int] = Field(default=None, ge=1, le=50000)
    updated_date: Optional[str] = None
    updated_priorities: Optional[list[str]] = None
    locked_categories: Optional[dict[str, int]] = Field(default_factory=dict)
    completed_task_ids: Optional[list[str]] = Field(default_factory=list)


class TradeoffOption(BaseModel):
    id: str
    title: str
    impact_type: str  # "guest_reduction" | "decor_simplification" | "catering_tier" | "other"
    numeric_saving: int
    description: str
    pros: list[str]
    cons: list[str]
    applied_changes: dict[str, Any] = Field(default_factory=dict)


class ReplanResponse(BaseModel):
    updated_plan: PlanResponse
    diff_summary: list[str]
    tradeoff_options: list[TradeoffOption]


class RefineIdeasRequest(BaseModel):
    current_ideas: IdeasReport
    brief: EventBrief
    refinement_prompt: str = Field(max_length=500)
