import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import settings
from app.security import RateLimitMiddleware, SecurityHeadersMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("jashn.main")


def resolve_web_dir() -> Path:
    """
    Resolves the directory containing the static frontend assets.
    Handles standard local directory structures as well as Vercel/Lambda serverless bundles.
    """
    candidates = [
        Path(os.getcwd()) / "public",
        Path(os.getcwd()) / "web",
        Path(__file__).resolve().parent.parent / "public",
        Path(__file__).resolve().parent.parent / "web",
        Path(__file__).resolve().parent / "public",
        Path(__file__).resolve().parent / "web",
        Path("/var/task/public"),
        Path("/var/task/web"),
    ]
    for candidate in candidates:
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return candidate
    return Path(__file__).resolve().parent.parent / "web"


WEB_DIR = resolve_web_dir()


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

    # Frontend Root & Alias Routes
    web_dir = resolve_web_dir()

    @app.get("/", include_in_schema=False)
    @app.get("/index.html", include_in_schema=False)
    @app.get("/web", include_in_schema=False)
    @app.get("/web/index.html", include_in_schema=False)
    async def serve_index():
        index_file = web_dir / "index.html"
        if index_file.is_file():
            return FileResponse(str(index_file))
        return JSONResponse(status_code=404, content={"detail": f"index.html not found in {web_dir}"})

    @app.get("/favicon.ico", include_in_schema=False)
    async def serve_favicon():
        fav = web_dir / "favicon.ico"
        if fav.is_file():
            return FileResponse(str(fav))
        return Response(status_code=204)

    # Mount static assets
    if (web_dir / "css").is_dir():
        app.mount("/css", StaticFiles(directory=str(web_dir / "css")), name="css")
        app.mount("/web/css", StaticFiles(directory=str(web_dir / "css")), name="web_css")
    if (web_dir / "js").is_dir():
        app.mount("/js", StaticFiles(directory=str(web_dir / "js")), name="js")
        app.mount("/web/js", StaticFiles(directory=str(web_dir / "js")), name="web_js")
    if web_dir.is_dir():
        app.mount("/web", StaticFiles(directory=str(web_dir), html=True), name="web_alias")
        app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")
    else:
        logger.warning(f"Static web directory not found at {web_dir}")

    return app


app = create_app()
