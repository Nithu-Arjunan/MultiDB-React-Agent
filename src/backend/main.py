"""FastAPI entry point — exposes POST /chat."""
from __future__ import annotations
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.auth import create_access_token, get_current_user, verify_google_id_token
from config import settings

from backend.agent import build_agent


# ── Request / Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str


class ToolCallRecord(BaseModel):
    tool: str
    input: str
    output: str


class ChatResponse(BaseModel):
    answer: str
    tool_calls: list[ToolCallRecord]
    warnings: list[str]
    elapsed_ms: int


class GoogleLoginRequest(BaseModel):
    credential: str


class AuthUser(BaseModel):
    sub: str
    email: str
    name: str = ""
    picture: str = ""


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: AuthUser


class AuthConfigResponse(BaseModel):
    google_client_id: str


def format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ── App setup ─────────────────────────────────────────────────────────────────

agent_executor = None


def get_frontend_dist_path() -> Path:
    return Path(__file__).resolve().parents[1] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent_executor
    agent_executor = build_agent()
    yield


app = FastAPI(title="SkyNova Multi-DB Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoint ──────────────────────────────────────────────────────────────────

@app.post("/auth/google", response_model=AuthResponse)
async def auth_google(req: GoogleLoginRequest):
    try:
        google_user = verify_google_id_token(req.credential)
        user = AuthUser(
            sub=google_user["sub"],
            email=google_user["email"],
            name=google_user.get("name", ""),
            picture=google_user.get("picture", ""),
        )
        access_token = create_access_token(user.model_dump())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google sign-in failed: {exc}",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication is not configured correctly: {exc}",
        ) from exc

    return AuthResponse(access_token=access_token, token_type="bearer", user=user)


@app.get("/auth/config", response_model=AuthConfigResponse)
async def auth_config():
    return AuthConfigResponse(google_client_id=settings.google_client_id)


@app.get("/auth/me", response_model=AuthUser)
async def auth_me(current_user: dict = Depends(get_current_user)):
    return AuthUser(
        sub=current_user["sub"],
        email=current_user["email"],
        name=current_user.get("name", ""),
        picture=current_user.get("picture", ""),
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    start = time.monotonic()

    result = agent_executor.invoke({"input": req.question})

    tool_calls = []
    warnings = []
    for action, observation in result.get("intermediate_steps", []):
        tool_calls.append(
            ToolCallRecord(
                tool=action.tool,
                input=str(action.tool_input),
                output=str(observation)[:1000],
            )
        )
        # Surface any SQL warnings from the tool output
        if '"warnings"' in str(observation):
            import json
            try:
                obs_data = json.loads(observation)
                warnings.extend(obs_data.get("warnings", []))
            except Exception:
                pass

    elapsed_ms = int((time.monotonic() - start) * 1000)

    return ChatResponse(
        answer=result["output"],
        tool_calls=tool_calls,
        warnings=warnings,
        elapsed_ms=elapsed_ms,
    )


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    def event_stream():
        try:
            for event in agent_executor.stream({"input": req.question}):
                event_type = event.get("type", "message")
                yield format_sse(event_type, event)
        except Exception as exc:
            yield format_sse("error", {"type": "error", "message": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"status": "ok"}


frontend_dist = get_frontend_dist_path()
if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_frontend_root():
        return FileResponse(frontend_dist / "index.html")

    @app.get("/{path:path}", include_in_schema=False)
    async def serve_frontend_app(path: str):
        requested_path = frontend_dist / path
        if requested_path.is_file():
            return FileResponse(requested_path)
        return FileResponse(frontend_dist / "index.html")
