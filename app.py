import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from openai import OpenAI
try:
    from google import genai
except ImportError:
    genai = None

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
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not deepseek_key and not gemini_key:
        raise HTTPException(status_code=503, detail="BIMA model provider is not configured.")

    system = (
        "You are BIMA, Arif's AI workspace and technical project partner. "
        "Use Indonesian informal language (gue/lo) unless the user asks otherwise. "
        "Be concise, concrete, and do not claim that you inspected, changed, tested, deployed, or executed anything unless tool evidence exists. "
        "This web-core v1 has model conversation capability but no GitHub/Railway execution tools yet. "
        "Never imply real-money trading execution. "
        "Active skill: " + SKILLS[req.skill]
    )
    transcript = [system]
    for item in req.history[-16:]:
        role = item.get("role")
        text = item.get("text", "")
        if role in {"user", "assistant"} and text:
            transcript.append(("ARIF: " if role == "user" else "BIMA: ") + text[:12000])
    transcript.append("ARIF: " + req.message)
    prompt = "\n\n".join(transcript)

    errors = []
    primary = os.getenv("BIMA_PRIMARY_PROVIDER", "deepseek").strip().lower()
    order = [primary] + [x.strip().lower() for x in os.getenv("BIMA_FALLBACK_PROVIDERS", "gemini,deepseek").split(",")]
    order = list(dict.fromkeys(order))
    for provider in order:
        try:
            if provider == "deepseek" and deepseek_key:
                client = OpenAI(api_key=deepseek_key, base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
                response = client.chat.completions.create(model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"), messages=[{"role":"user","content":prompt}])
                answer = (response.choices[0].message.content or "").strip()
                if answer:
                    return {"answer": answer, "skill": req.skill, "provider": "deepseek", "mode": "live-core-v1"}
            if provider == "gemini" and gemini_key and genai is not None:
                client = genai.Client(api_key=gemini_key)
                response = client.models.generate_content(model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"), contents=prompt)
                answer = (response.text or "").strip()
                if answer:
                    return {"answer": answer, "skill": req.skill, "provider": "gemini", "mode": "live-core-v1"}
        except Exception as error:
            errors.append(provider + ": " + str(error))
    raise HTTPException(status_code=502, detail="Semua BIMA model provider gagal.")
