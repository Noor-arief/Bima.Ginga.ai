import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from openai import OpenAI

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="BimaGinga Workspace", version="0.1.0")

SKILLS = {
    "write_improve": "Draft, rewrite, summarize, translate, or improve writing while preserving the user's intent.",
    "code_debug": "Help with coding and debugging. Diagnose root cause, propose the smallest safe fix, and clearly distinguish suggested work from work actually executed.",
    "analyze_data": "Analyze data, metrics, reports, and datasets. Identify trends, outliers, and evidence-based conclusions.",
    "plan_strategize": "Turn goals into prioritized plans, roadmaps, milestones, tradeoffs, and next actions.",
    "learn_research": "Explain and research topics carefully. Distinguish verified information from assumptions.",
    "custom_task": "Handle free-form and cross-skill tasks. Break multi-step work into concrete actions and continue until complete, blocked, or an approval gate is required.",
}

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=12000)
    skill: Literal["write_improve","code_debug","analyze_data","plan_strategize","learn_research","custom_task"] = "custom_task"
    history: list[dict[str, str]] = Field(default_factory=list)

@app.get("/health")
def health():
    return {"status": "ok", "service": "BimaGinga", "mode": "live-core-v1"}

@app.get("/")
def index():
    return FileResponse(ROOT / "index.html")

@app.post("/api/chat")
def chat(req: ChatRequest):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="BimaGinga model provider is not configured.")

    messages = [{
        "role": "system",
        "content": (
            "You are BIMA, Arif's AI workspace and technical project partner. "
            "Use Indonesian informal language (gue/lo) unless the user asks otherwise. "
            "Be concise, concrete, and do not claim that you inspected, changed, tested, deployed, or executed anything unless tool evidence exists. "
            "This web-core v1 has model conversation capability but no GitHub/Railway execution tools yet. "
            "Never imply real-money trading execution. "
            "Active skill: " + SKILLS[req.skill]
        )
    }]
    for item in req.history[-16:]:
        role = item.get("role")
        text = item.get("text", "")
        if role in {"user", "assistant"} and text:
            messages.append({"role": role, "content": text[:12000]})
    messages.append({"role": "user", "content": req.message})

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=os.getenv("BIMAGINGA_MODEL", "gpt-5-mini"),
        messages=messages,
    )
    answer = (response.choices[0].message.content or "").strip()
    return {"answer": answer, "skill": req.skill, "mode": "live-core-v1"}
