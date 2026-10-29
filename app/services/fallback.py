import uuid
from datetime import UTC, datetime

from app.models.schemas import (
    EventBrief,
    IdeasReport,
    PlanResponse,
    ThemeIdea,
)
from app.services.budget import calculate_budget
from app.services.timeline import calculate_timeline
from app.services.vendors import build_vendor_checklist

FALLBACK_THEMES = {
    "wedding": [
        ThemeIdea(
            id="theme_royal_marigold",
            title="Royal Heritage & Genda Phool",
            tagline="Classic Indian warmth with golden marigolds, brass urlis, and ambient brass lanterns.",
            decor_concept="Warm marigold garlands, terracotta and brass centerpieces, and gentle fairy-light canopies.",
            menu_highlights=["Live Dal Baati / Biryani Counter", "Gulab Jamun with Rabdi", "Kesari Chai Bar"],
            activities=["Sangeet choreography circle", "Mehndi corner with folk music", "Traditional welcome with dhol"],
            budget_category="decor_styling",
            fits_allocation=True,
            estimated_tier="Balanced"
        ),
        ThemeIdea(
            id="theme_boho_pastel",
            title="Contemporary Pastel Garden",
            tagline="Understated elegance with soft blush tones, eucalyptus greens, and natural wooden textures.",
            decor_concept="Pastel drapery, dry pampas accents, fairy-light tunnels, and minimalist photo booths.",
            menu_highlights=["Woodfired artisanal pizzas", "Paneer Tikka skewers", "Mango Kulfi shots"],
            activities=["Polaroid guestbook signing", "Acoustic indie band", "Sparkler send-off"],
            budget_category="decor_styling",
            fits_allocation=True,
            estimated_tier="Grand"
        ),
        ThemeIdea(
            id="theme_eco_friendly",
            title="Eco-Chic & Sustainable Celebration",
            tagline="Zero single-use plastic, potted plant giveaways, and handloom fabric drapery.",
            decor_concept="Khadi and jute drapes, upcycled glass bottle fairy lights, and live potted plant arrangements.",
            menu_highlights=["Farm-to-table seasonal thali", "Organic millet pooris", "Coconut water welcome drinks"],
            activities=["Seed-paper blessing tree", "Family memories storytelling circle", "Local artisan stalls"],
            budget_category="decor_styling",
            fits_allocation=True,
            estimated_tier="Budget-Friendly"
        )
    ],
    "birthday": [
        ThemeIdea(
            id="theme_carnival_fest",
            title="Vibrant Street Carnival",
            tagline="High-energy color burst with retro games, popcorn carts, and festive bunting.",
            decor_concept="Multi-color fabric flags, balloon clusters, photo props, and game stall kiosks.",
            menu_highlights=["Sliders & Fries counter", "Live candy floss & popcorn", "Cupcake decoration bar"],
            activities=["Ring toss & balloon darts", "Musical freeze dance", "Magic show & balloon twisting"],
            budget_category="entertainment_activities",
            fits_allocation=True,
            estimated_tier="Balanced"
        ),
        ThemeIdea(
            id="theme_starlit_cinema",
            title="Under-the-Stars Movie Night",
            tagline="Cozy open-air cinema with floor cushions, blankets, and fairy lights.",
            decor_concept="Warm string lights, boho rugs, floor cushions, and a large projection screen setup.",
            menu_highlights=["Gourmet popcorn flavors", "Mini nachos & cheese", "Ice cream sundae bar"],
            activities=["Favorite movie screening", "Trivia quiz on birthday star", "Karaoke warm-up"],
            budget_category="entertainment_activities",
            fits_allocation=True,
            estimated_tier="Budget-Friendly"
        ),
        ThemeIdea(
            id="theme_glow_party",
            title="Neon Glow Dance Extravaganza",
            tagline="UV blacklights, glow accessories, and punchy dance music.",
            decor_concept="Neon tape geometric patterns, UV floodlights, and fluorescent party banners.",
            menu_highlights=["Glowing mocktail bar", "Cheesy finger food", "Churros with chocolate dip"],
            activities=["Glow face painting", "DJ dance battle", "Glow stick relay races"],
            budget_category="entertainment_activities",
            fits_allocation=True,
            estimated_tier="Grand"
        )
    ],
    "community": [
        ThemeIdea(
            id="theme_utsav_mela",
            title="Anand Mela & Cultural Milan",
            tagline="Vibrant community fair celebrating local heritage, fellowship, and togetherness.",
            decor_concept="Festive rangolis, fabric shamianas, paper lanterns, and traditional torans.",
            menu_highlights=["Traditional Prasad feast (Kheer, Puri, Sabzi)", "Fresh Lemonade stall", "Poha & Jalebi breakfast"],
            activities=["Community folk dance (Garba/Bhangra)", "Kids drawing and recitation competition", "Senior citizen felicitations"],
            budget_category="catering_prasad",
            fits_allocation=True,
            estimated_tier="Balanced"
        ),
        ThemeIdea(
            id="theme_seva_harmony",
            title="Seva & Green Community Gathering",
            tagline="Cleanliness drive, tree-planting, and shared community meal.",
            decor_concept="Zero-waste cotton banners, banana leaf dining tables, and recycled paper signage.",
            menu_highlights=["Community Langar / Satvik Khichdi", "Buttermilk and jaggery sweets", "Seasonal fruits"],
            activities=["Tree sapling distribution", "Health & wellness awareness kiosk", "Antakshari across age groups"],
            budget_category="catering_prasad",
            fits_allocation=True,
            estimated_tier="Budget-Friendly"
        ),
        ThemeIdea(
            id="theme_heritage_night",
            title="Classical Heritage & Music Evening",
            tagline="Soulful classical music, diya lighting, and community dinner.",
            decor_concept="Earthen clay diyas, brass lamps, fabric drapes, and fragrant mogra strings.",
            menu_highlights=["Regional authentic thali", "Hot Badam Milk", "Traditional Halwa"],
            activities=["Bhajan / Ghazal recital by residents", "Community storytelling session", "Lamp lighting ceremony"],
            budget_category="catering_prasad",
            fits_allocation=True,
            estimated_tier="Grand"
        )
    ]
}


def build_fallback_plan(brief: EventBrief) -> PlanResponse:
    """
    Builds a 100% deterministic, rules-only plan when Gemini is unavailable,
    unconfigured, or times out.
    """
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

    vendor_items = build_vendor_checklist(
        event_type=brief.event_type,
        budget_report=budget_report
    )

    # Determine theme ideas based on event type
    etype = brief.event_type.lower()
    themes = FALLBACK_THEMES.get(etype) or FALLBACK_THEMES["wedding"]

    # Adapt diet / cultural notes if present
    notes = brief.dietary_cultural_notes or "Standard curated menu"
    cultural_note = (
        f"Rule-based plan adapted for {brief.event_type.title()} in {brief.city}. "
        f"Menu and timeline honor your guidance: '{notes}'."
    )

    ideas_report = IdeasReport(
        themes=themes,
        cultural_alignment_note=cultural_note
    )

    plan_id = f"plan_{uuid.uuid4().hex[:10]}"
    created_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    return PlanResponse(
        plan_id=plan_id,
        created_at=created_at,
        schema_version="v1",
        is_ai_generated=False,
        ai_status_message="AI unavailable: rule-based plan built from your inputs",
        brief=brief,
        budget=budget_report,
        timeline=timeline_report,
        vendors=vendor_items,
        ideas=ideas_report
    )
