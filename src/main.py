import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from src.api.characters import character_router
from src.api.campaigns import campaigns_router
from src.api.auth import auth_router
from src.config import API_DOCS

# The app's own loggers (src.*) report at INFO, e.g. which memories each turn recalled.
logging.basicConfig(format="%(levelname)s:     %(name)s - %(message)s")
logging.getLogger("src").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


async def require_csrf_header(request: Request, call_next):
    """The session is a cookie, which browsers attach to any request to this site, so
    a request that changes data must also carry X-Requested-With. Another site cannot
    add a custom header to a cross-site request without a CORS preflight, and this API
    allows no other origin (the frontend is served from the same one)."""
    if (
        request.method not in SAFE_METHODS
        and request.headers.get("x-requested-with") != "dungeon-web"
    ):
        return JSONResponse(
            status_code=403, content={"detail": "Missing X-Requested-With header"}
        )
    return await call_next(request)


def create_app(api_docs: bool) -> FastAPI:
    """The API. `api_docs` serves /docs and /openapi.json (off in production)."""
    app = FastAPI(
        lifespan=lifespan,
        docs_url="/docs" if api_docs else None,
        redoc_url="/redoc" if api_docs else None,
        openapi_url="/openapi.json" if api_docs else None,
    )
    app.middleware("http")(require_csrf_header)
    app.include_router(character_router)
    app.include_router(campaigns_router)
    app.include_router(auth_router)

    @app.get("/health")
    def hello():
        return "App is up and healthy"

    return app


app = create_app(api_docs=API_DOCS)
