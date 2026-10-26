import logging
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import settings
from app.security import RateLimitMiddleware, SecurityHeadersMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("jashn.main")

WEB_DIR = Path(__file__).parent.parent / "web"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Jashn — Celebration & Event Planner",
        description="GenAI-powered celebration planner for The Family Organizer. AI proposes, code disposes.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url=None
    )

    # Middleware Stack (order matters: outer executes first)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Include API Router
    app.include_router(router)

    # Global Exception Handler (Stateless, prevents leaking internal stack traces)
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Uncaught server exception on {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An unexpected error occurred while processing your celebration request. Please retry.",
                "path": request.url.path
            }
        )

    # Mount static frontend
    if WEB_DIR.exists():
        app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
    else:
        logger.warning(f"Static web directory not found at {WEB_DIR}")

    return app


app = create_app()
