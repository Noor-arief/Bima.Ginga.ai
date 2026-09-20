import re
import os
import threading
from pathlib import Path
from typing import Literal
import base64
import io
import json
import time
import uuid
import urllib.request

from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pypdf import PdfReader
from docx import Document
from openai import OpenAI
try:
    from google import genai
except ImportError:
    genai = None

from router import is_continuation, route_message
from task_store import create_task, get_task, list_tasks, needs_approval, recover_interrupted, update_task
from executor import execute_task

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

class Attachment(BaseModel):
    name: str = Field(..., max_length=255)
    type: str = Field(default="application/octet-stream", max_length=120)
    data: str = Field(..., max_length=14000000)

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=12000)
    skill: Literal["write_improve","code_debug","analyze_data","plan_strategize","learn_research","custom_task"] = "custom_task"
    history: list[dict[str, str]] = Field(default_factory=list)
    active_task_id: str | None = None
    attachments: list[Attachment] = Field(default_factory=list, max_length=5)

def require_owner(x_bima_key: str | None):
    expected = os.getenv("BIMAGINGA_OWNER_KEY")
    if expected and x_bima_key != expected:
        raise HTTPException(status_code=401, detail="BimaGinga owner authentication failed.")

class ConversationRequest(BaseModel):
    id: str | None = None
    title: str = ""
    messages: list[dict[str, str]] = Field(default_factory=list)
    updated_at: int | None = None

CONV_STORE = Path(os.getenv("BIMAGINGA_DATA_DIR", "/data")) / "conversations.json"
CONV_LOCK = threading.RLock()

def load_conversations():
    with CONV_LOCK:
        if not CONV_STORE.exists():
            print(f"[history] store_missing path={CONV_STORE}", flush=True)
            return []
        try:
            items = json.loads(CONV_STORE.read_text("utf-8"))
            print(f"[history] loaded count={len(items) if isinstance(items, list) else 0} path={CONV_STORE}", flush=True)
            return items if isinstance(items, list) else []
        except Exception as exc:
            print(f"[history] load_failed path={CONV_STORE} error={type(exc).__name__}", flush=True)
            return []

def save_conversation(req: ConversationRequest):
    with CONV_LOCK:
        items = load_conversations()
        cid = req.id or uuid.uuid4().hex
        value = {"id":cid,"title":req.title or "Percakapan baru","messages":req.messages[-200:],"updated_at":int(req.updated_at or time.time())}
        items = [x for x in items if x.get("id") != cid]
        items.insert(0,value)
        tmp=CONV_STORE.with_suffix(".tmp");tmp.write_text(json.dumps(items[:100],ensure_ascii=False,indent=2),"utf-8");tmp.replace(CONV_STORE)
        return value


PROJECT_STATE_STORE = Path(os.getenv("BIMAGINGA_DATA_DIR", "/data")) / "project_state.json"
PROJECT_STATE_LOCK = threading.RLock()

def load_project_state() -> dict:
    with PROJECT_STATE_LOCK:
        if not PROJECT_STATE_STORE.exists():
            return {}
        try:
            value = json.loads(PROJECT_STATE_STORE.read_text("utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception as exc:
            print(f"[project_state] load_failed error={type(exc).__name__}", flush=True)
            return {}

def save_project_state(value: dict) -> None:
    with PROJECT_STATE_LOCK:
        tmp = PROJECT_STATE_STORE.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(PROJECT_STATE_STORE)

def update_project_state_from_turn(message: str, answer: str) -> None:
    project_signal = bool(re.search(
        r"\b(project|proyek|checkpoint|phase|fase|deploy|deployment|repo|github|railway|bima|trading|treding|handover|ho|bug|fix|fixed|selesai|lanjut)\b",
        (message + "\n" + answer).lower(),
    ))
    if not project_signal:
        return
    state = load_project_state()
    state["active"] = {
        "updated_at": int(time.time()),
        "last_user_message": message[-6000:],
        "last_assistant_result": answer[-10000:],
    }
    save_project_state(state)

def trading_runtime_context(message: str) -> str:
    """Read live paper-trading status for trading-related BIMA Web questions."""
    if not re.search(r"\b(trading|trade|paper|shadow|position|posisi|pnl|profit|loss|market|coin|meme)\b", message.lower()):
        return ""
    url = os.getenv("BIMA_TRADING_STATUS_URL", "").strip()
    if not url:
        return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BimaGinga-Workspace/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            payload = json.loads(response.read(2_000_000).decode("utf-8"))
        validation = payload.get("validation") or {}
        paper = validation.get("paper_metrics") or {}
        risk = validation.get("risk_metrics") or {}
        persistent = payload.get("persistent_metrics") or {}
        compact = {
            "dataset_cycles": payload.get("dataset_cycles"),
            "cycle_observations": payload.get("cycle_observations"),
            "persistent_open_positions": persistent.get("open", len(payload.get("open_positions") or [])),
            "persistent_closed_positions": persistent.get("closed", len(payload.get("closed_positions") or [])),
            "wins": persistent.get("wins", paper.get("wins")),
            "losses": persistent.get("losses", paper.get("losses")),
            "realized_pnl_usd": persistent.get("realized_pnl_usd", risk.get("realized_pnl_usd")),
            "validation_status": validation.get("status"),
            "validation_reasons": validation.get("validation_reasons"),
            "validation_closed": validation.get("closed"),
            "open_positions": payload.get("open_positions") or [],
        }
        return (
            "LIVE TRADING ENGINE STATUS (read-only, source of truth for current trading runtime):\n"
            + json.dumps(compact, ensure_ascii=False)
            + "\nTrading is paper/shadow only. Never claim a real-money order was executed unless a separate authorized execution system provides evidence."
        )
    except Exception as exc:
        print(f"[trading_status] unavailable error={type(exc).__name__}", flush=True)
        return "LIVE TRADING ENGINE STATUS: temporarily unavailable. Do not invent current trading metrics.\n"

def persistent_workspace_context(message: str, recent_history: list[dict[str, str]]) -> str:
    """Retrieve durable cross-session workspace state from persisted conversations."""
    conversations = load_conversations()
    if not conversations:
        return ""
    # Sort by the conversation's real last-change timestamp, not storage-list position.
    conversations = sorted(conversations, key=lambda x: int(x.get("updated_at") or 0), reverse=True)

    query_text = " ".join(
        [message] + [str(x.get("text", "")) for x in recent_history[-6:]]
    ).lower()
    stop = {
        "yang","dan","atau","ini","itu","gue","lo","aku","saya","kita","bima","jadi",
        "udah","sudah","belum","mau","bisa","gak","nggak","aja","lagi","dari","untuk",
        "dengan","di","ke","ya","apa","kalau","terus","lanjut","project","proyek"
    }
    terms = {
        token for token in re.findall(r"[a-zA-Z0-9_.-]{3,}", query_text)
        if token not in stop
    }
    continuation = bool(re.search(
        r"\b(lanjut|lanjutkan|terus|project kita|proyek kita|yang tadi|sebelumnya|handover|ho)\b",
        query_text,
    ))

    ranked = []
    for recency, conv in enumerate(conversations[:50]):
        title = str(conv.get("title", ""))
        messages = conv.get("messages") or []
        searchable = (title + " " + " ".join(str(m.get("text", "")) for m in messages[-60:])).lower()
        lexical = sum(3 if term in title.lower() else 1 for term in terms if term in searchable)
        # Recency is the source-of-truth tie breaker for continuation requests.
        # A stale conversation may be relevant, but must not outrank newer project state
        # merely because it repeats more keywords.
        recency_score = max(0, 50 - recency) if continuation else max(0, 8 - recency)
        score = lexical * 10 + recency_score
        if score > 0:
            ranked.append((score, -recency, title, messages))

    ranked.sort(reverse=True)
    chunks = []
    budget = 32000
    for _, neg_recency, title, messages in ranked[:8]:
        selected = messages[-24:]
        body = "\n".join(
            ("ARIF: " if m.get("role") == "user" else "BIMA: ") + str(m.get("text", ""))[:4000]
            for m in selected if m.get("role") in {"user", "assistant"} and m.get("text")
        )
        chunk = f"[Saved conversation recency={-neg_recency}, title={title or 'Percakapan'}]\n{body}".strip()
        if not chunk:
            continue
        if len(chunk) > budget:
            chunk = chunk[-budget:]
        chunks.append(chunk)
        budget -= len(chunk)
        if budget <= 0:
            break

    if not chunks:
        return ""
    project_state = load_project_state()
    state_context = ""
    active_state = project_state.get("active")
    if active_state:
        state_age = int(time.time()) - int(active_state.get("updated_at") or 0)
        if state_age <= 7 * 24 * 60 * 60:
            state_context = "EXPLICIT ACTIVE PROJECT STATE (highest priority):\\n" + json.dumps(active_state, ensure_ascii=False) + "\\n\\n"
    return (
        state_context + "PERSISTENT WORKSPACE MEMORY. Saved conversations are ordered by recency: recency=0 is newest. "
        "For continuation/handover questions, treat the newest concrete checkpoint/status as the source of truth. "
        "Older conversations are historical evidence only and must not override a newer checkpoint. "
        "If newer messages say a bug/phase/task is fixed, completed, deployed, or moved forward, do not report the older state as current. "
        "Prefer Arif's explicit latest status/decision over an older assistant summary. "
        "Use the memory to continue work without asking Arif to repeat context.\n\n" + "\n\n".join(chunks)
    )

class TaskRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=12000)
    skill: Literal["write_improve","code_debug","analyze_data","plan_strategize","learn_research","custom_task"] = "custom_task"

def model_answer(prompt: str, images: list[Attachment] | None = None) -> tuple[str, str]:
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    if not deepseek_key and not gemini_key:
        raise RuntimeError("BIMA model provider is not configured.")
    primary = os.getenv("BIMA_PRIMARY_PROVIDER", "deepseek").strip().lower()
    order = [primary] + [x.strip().lower() for x in os.getenv("BIMA_FALLBACK_PROVIDERS", "gemini,deepseek").split(",")]
    order = list(dict.fromkeys(order))
    errors = []
    images = images or []
    if images and gemini_key and genai is not None:
        try:
            client = genai.Client(api_key=gemini_key)
            contents = [prompt]
            for image in images:
                raw = base64.b64decode(image.data.split(",", 1)[-1], validate=True)
                contents.append(genai.types.Part.from_bytes(data=raw, mime_type=image.type))
            response = client.models.generate_content(model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"), contents=contents)
            answer = (response.text or "").strip()
            if answer:
                return answer, "gemini-vision"
        except Exception as exc:
            errors.append("gemini-vision: " + str(exc))
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
    detail = " | ".join(errors)
    print(f"[model] all_providers_failed {detail}", flush=True)
    raise RuntimeError("All configured model providers failed: " + detail)


def attachment_context(items: list[Attachment]) -> str:
    if not items:
        return ""
    parts = []
    for item in items:
        try:
            raw = base64.b64decode(item.data.split(",", 1)[-1], validate=True)
        except Exception:
            parts.append(f"[Attachment {item.name}: invalid data]")
            continue
        if len(raw) > 8 * 1024 * 1024:
            parts.append(f"[Attachment {item.name}: exceeds 8 MB limit]")
            continue
        text = ""
        try:
            if item.type == "application/pdf" or item.name.lower().endswith(".pdf"):
                reader = PdfReader(io.BytesIO(raw))
                text = "\n".join((p.extract_text() or "") for p in reader.pages[:40])
            elif item.name.lower().endswith(".docx"):
                doc = Document(io.BytesIO(raw))
                text = "\n".join(p.text for p in doc.paragraphs)
            elif item.type.startswith("text/") or item.name.lower().endswith((".txt",".md",".csv",".json",".py",".js",".html",".css")):
                text = raw.decode("utf-8", errors="replace")
            elif item.type.startswith("image/"):
                parts.append(f"[Image attachment: {item.name}. Image bytes received; current text provider path cannot inspect pixels yet.]")
                continue
            else:
                parts.append(f"[Attachment {item.name}: unsupported content type {item.type}]")
                continue
        except Exception as exc:
            parts.append(f"[Attachment {item.name}: parse failed: {exc}]")
            continue
        parts.append(f"[Attachment: {item.name}]\n{text[:50000]}")
    return "\n\n".join(parts)

def run_task(task_id: str):
    task = get_task(task_id)
    if not task:
        return
    if needs_approval(task["message"]):
        update_task(task_id, state="approval_required", error="Protected action requires explicit approval before execution.")
        return
    update_task(task_id, state="running")
    try:
        result = execute_task(task["message"], SKILLS[task["skill"]])
        terminal_state = result.pop("terminal_state", "completed")
        update_task(task_id, state=terminal_state, result=result)
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
def chat(req: ChatRequest, x_bima_key: str | None = Header(default=None)):
    active_task = get_task(req.active_task_id) if req.active_task_id else None
    active_execution = bool(active_task and active_task.get("state") in {"queued", "running"})
    decision = route_message(req.message, active_task=active_execution)
    # Attachments must stay on the model path so parsed document content reaches BIMA.
    if req.attachments:
        decision = type(decision)("chat", "attachment content requires model inspection")
    # Planning/writing/analysis/research skills are advisory by default. Action verbs inside
    # the requested deliverable (e.g. "buat strategi") must not start the execution worker.
    advisory_skills = {"write_improve", "analyze_data", "plan_strategize", "learn_research"}
    if req.skill in advisory_skills:
        decision = type(decision)("chat", "advisory skill handles requested deliverable in conversation")
    if decision.kind == "execution":
        # Privileged execution remains owner-protected; ordinary BIMA chat must not
        # require a server-only secret that the browser cannot possess.
        require_owner(x_bima_key)
        if active_execution and is_continuation(req.message):
            return {
                "answer": "Task yang aktif masih berjalan. BIMA melanjutkan task yang sama.",
                "skill": req.skill, "mode": "execution-worker-v1", "task": active_task,
            }
        task = create_task(req.message, req.skill)
        threading.Thread(target=run_task, args=(task["id"],), daemon=True).start()
        return {
            "answer": "Task diterima. BIMA Execution Worker menjalankannya sampai completed, blocked, failed, atau approval_required.",
            "skill": req.skill, "mode": "execution-worker-v1", "task": task,
        }

    system = (
        "You are BIMA, Arif's AI workspace and technical project partner. "
        "Conversation continuity is mandatory: infer what Arif is referring to from the supplied chat history before answering. "
        "When Arif says lanjut/terus/back to a topic, continue the most recent relevant topic already present in history; do not invent a new plan, generic framework, or ask him to restate context if history already contains it. "
        "Use Indonesian informal language (gue/lo) unless asked otherwise. Be concise and concrete. Default to a compact answer: maximum 6 bullets or short sections and roughly 180 words unless the user explicitly asks for detail. Do not add extra frameworks, questions, caveats, or metrics beyond what the user requested unless essential. "
        "Never claim external execution without evidence. Never imply real-money trading execution. "
        "Routing decision: " + decision.kind + ". Topic/domain context must not override this decision. "
        "Active skill: " + SKILLS[req.skill]
    )
    transcript = [system]
    persistent_context = persistent_workspace_context(req.message, req.history)
    if persistent_context:
        transcript.append(persistent_context)
    trading_context = trading_runtime_context(req.message)
    if trading_context:
        transcript.append(
            trading_context
            + "\nCURRENT PROJECT OVERRIDE: Trading is the active project and is running autonomous paper/shadow validation. "
              "Do not describe persistent-memory/Project-State work as the active checkpoint and do not say trading is queued. "
              "Persistent memory is completed infrastructure. The current next action is continued shadow validation plus technical audit until the validation gate is satisfied."
        )
    for item in req.history[-16:]:
        role, text = item.get("role"), item.get("text", "")
        if role in {"user", "assistant"} and text:
            transcript.append(("ARIF: " if role == "user" else "BIMA: ") + text[:12000])
    attachment_text = attachment_context(req.attachments)
    image_items = [item for item in req.attachments if item.type.startswith("image/")]
    attachment_instruction = ""
    if req.attachments:
        attachment_instruction = ("\n\nATTACHMENT INSTRUCTION: The attachment content below was extracted by the server. "
                                  "Read and use it as the source of truth. Do not claim you can only see the filename when extracted content is present.")
    transcript.append("ARIF: " + req.message + attachment_instruction + (("\n\nATTACHMENTS:\n" + attachment_text) if attachment_text else ""))
    try:
        answer, provider = model_answer("\\n\\n".join(transcript), images=image_items)
        update_project_state_from_turn(req.message, answer)
        return {"answer": answer, "skill": req.skill, "provider": provider, "mode": "live-core-v2"}
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

@app.get("/api/tasks")
def tasks(x_bima_key: str | None = Header(default=None)):
    require_owner(x_bima_key)
    return {"tasks": list_tasks()}

@app.get("/api/tasks/{task_id}")
def task(task_id: str, x_bima_key: str | None = Header(default=None)):
    require_owner(x_bima_key)
    value = get_task(task_id)
    if not value:
        raise HTTPException(status_code=404, detail="Task not found")
    return value

@app.get("/api/conversations")
def conversations():
    return {"conversations": load_conversations()}

@app.put("/api/conversations/{conversation_id}")
def put_conversation(conversation_id: str, req: ConversationRequest):
    # Conversation persistence is part of the normal chat session, not an owner-only action.
    # Keep owner authentication on privileged task/execution endpoints only.
    req.id = conversation_id
    return save_conversation(req)
