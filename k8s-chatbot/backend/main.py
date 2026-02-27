import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import CORS_ORIGINS
from agents.parser import parse_command, CommandIntent
from executors import k8s_execute, loki_execute, prometheus_execute

app = FastAPI(title="K8s Chatbot API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    intent: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


def _execute(intent: CommandIntent) -> str:
    if intent.action == "unknown":
        return "Tôi chưa hiểu lệnh. Thử: 'check pods in banking', 'rollout restart deployment in banking', 'logs error of <pod-name>'"
    if intent.action in ("get_pods", "get_deployments", "rollout_restart", "get_logs"):
        return k8s_execute(intent)
    if intent.action == "logql":
        return loki_execute(intent)
    if intent.action == "promql":
        return prometheus_execute(intent)
    return "Action chưa được hỗ trợ"


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message is required")
    intent = parse_command(req.message.strip())
    reply = _execute(intent)
    return ChatResponse(reply=reply, intent=intent.action)


# Serve frontend static (when built) - must be last
_static = Path(__file__).parent / "frontend" / "dist"
if _static.exists():
    app.mount("/", StaticFiles(directory=str(_static), html=True), name="static")
