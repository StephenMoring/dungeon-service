import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from src.api.characters import character_router
from src.api.campaigns import campaigns_router
from src.api.auth import auth_router

# The app's own loggers (src.*) report at INFO, e.g. which memories each turn recalled.
logging.basicConfig(format="%(levelname)s:     %(name)s - %(message)s")
logging.getLogger("src").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@app.middleware("http")
async def require_csrf_header(request: Request, call_next):
    """The session is a cookie, which browsers attach to any request to this site, so
    a request that changes data must also carry X-Requested-With. Another site cannot
    add a custom header to a cross-site request without a CORS preflight, which this
    API refuses for any origin it does not list."""
    if (
        request.method not in SAFE_METHODS
        and request.headers.get("x-requested-with") != "dungeon-web"
    ):
        return JSONResponse(
            status_code=403, content={"detail": "Missing X-Requested-With header"}
        )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(character_router)
app.include_router(campaigns_router)
app.include_router(auth_router)


@app.get("/health")
def hello():
    return "App is up and healthy"
