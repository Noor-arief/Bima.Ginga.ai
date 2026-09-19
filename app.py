import os
import threading
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

from router import route_message
from task_store import create_task, get_task, list_tasks, needs_approval, recover_interrupted, update_task

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="BimaGinga Workspace", version="0.2.0")

SKILLS = {
    "write_improve": "Draft, rewrite, summarize, translate, or improve writing while preserving the user's intent.",
    "code_debug": "Coding/debugging: diagnose root cause, make the smallest safe change, test, and verify with evidence.",
    "analyze_data": "Analyze data, metrics, reports, and datasets with evidence-based conclusions.",
    "plan_strategize": "Turn goals into prioritized plans, milestones, tradeoffs, and next actions.",
    "learn_research": "Research and explain carefully; distinguish verified facts from assumptions.",
    "custom_task": "Handle cross-skill multi-step work and continue until completed, blocked, failed, or approval is required.",
}

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=12000)
    skill: Literal["write_improve","code_debug","analyze_data","plan_strategize","learn_research","custom_task"] = "custom_task"
    history: list[dict[str, str]] = Field(default_factory=list)

class TaskRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=12000)
    skill: Literal["write_improve","code_debug","analyze_data","plan_strategize","learn_research","custom_task"] = "custom_task"

def model_answer(prompt: str) -> tuple[str, str]:
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not deepseek_key and not gemini_key:
        raise RuntimeError("BIMA model provider is not configured.")
    primary = os.getenv("BIMA_PRIMARY_PROVIDER", "deepseek").strip().lower()
    order = [primary] + [x.strip().lower() for x in os.getenv("BIMA_FALLBACK_PROVIDERS", "gemini,deepseek").split(",")]
    order = list(dict.fromkeys(order))
    errors = []
    for provider in order:
        try:
            if provider == "deepseek" and deepseek_key:
                client = OpenAI(api_key=deepseek_key, base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
                response = client.chat.completions.create(
                    model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
                    messages=[{"role": "user", "content": prompt}],
                )
                answer = (response.choices[0].message.content or "").strip()
                if answer:
                    return answer, "deepseek"
            if provider == "gemini" and gemini_key and genai is not None:
                client = genai.Client(api_key=gemini_key)
                response = client.models.generate_content(model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"), contents=prompt)
                answer = (response.text or "").strip()
                if answer:
                    return answer, "gemini"
        except Exception as exc:
            errors.append(provider + ": " + str(exc))
    raise RuntimeError("All configured model providers failed: " + " | ".join(errors))

def run_task(task_id: str):
    task = get_task(task_id)
    if not task:
        return
    if needs_approval(task["message"]):
        update_task(task_id, state="approval_required", error="Protected action requires explicit approval before execution.")
        return
    update_task(task_id, state="running")
    try:
        prompt = (
            "You are BIMA Execution Worker. Complete the requested work as far as the currently available server capabilities allow. "
            "Never claim external inspection, edits, tests, deployment, or tool execution without evidence. "
            "If an external capability is unavailable, report the exact blocker rather than inventing success. "
            "Never execute real-money trading or wallet actions. "
            "Return a concise completion report with what is actually complete and any blocker.\n\n"
            "Skill: " + SKILLS[task["skill"]] + "\nTask: " + task["message"]
        )
        answer, provider = model_answer(prompt)
        update_task(task_id, state="completed", result={"answer": answer, "provider": provider})
    except Exception as exc:
        update_task(task_id, state="failed", error=str(exc))

@app.on_event("startup")
def startup():
    recover_interrupted()
    for task in list_tasks(100):
        if task.get("state") == "queued":
            threading.Thread(target=run_task, args=(task["id"],), daemon=True).start()

@app.get("/health")
def health():
    return {"status": "ok", "service": "BimaGinga", "mode": "execution-worker-v1", "task_store": str(os.getenv("BIMAGINGA_DATA_DIR", "/data"))}

@app.get("/")
def index():
    return FileResponse(ROOT / "index.html")

@app.post("/api/chat")
def chat(req: ChatRequest):
    decision = route_message(req.message)
    if decision.kind == "execution":
        task = create_task(req.message, req.skill)
        threading.Thread(target=run_task, args=(task["id"],), daemon=True).start()
        return {
            "answer": "Task diterima. BIMA Execution Worker menjalankannya sampai completed, blocked, failed, atau approval_required.",
            "skill": req.skill, "mode": "execution-worker-v1", "task": task,
        }

    system = (
        "You are BIMA, Arif's AI workspace and technical project partner. "
        "Use Indonesian informal language (gue/lo) unless asked otherwise. Be concise and concrete. "
        "Never claim external execution without evidence. Never imply real-money trading execution. "
        "Routing decision: " + decision.kind + ". Topic/domain context must not override this decision. "
        "Active skill: " + SKILLS[req.skill]
    )
    transcript = [system]
    for item in req.history[-16:]:
        role, text = item.get("role"), item.get("text", "")
        if role in {"user", "assistant"} and text:
            transcript.append(("ARIF: " if role == "user" else "BIMA: ") + text[:12000])
    transcript.append("ARIF: " + req.message)
    try:
        answer, provider = model_answer("\n\n".join(transcript))
        return {"answer": answer, "skill": req.skill, "provider": provider, "mode": "live-core-v2"}
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

@app.get("/api/tasks")
def tasks():
    return {"tasks": list_tasks()}

@app.get("/api/tasks/{task_id}")
def task(task_id: str):
    value = get_task(task_id)
    if not value:
        raise HTTPException(status_code=404, detail="Task not found")
    return value
