import json
import os
import threading
import time
import uuid
from pathlib import Path

DATA_DIR = Path(os.getenv("BIMAGINGA_DATA_DIR", "/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
STORE = DATA_DIR / "tasks.json"
_LOCK = threading.RLock()

TERMINAL = {"completed", "failed", "blocked", "approval_required"}

def _load():
    if not STORE.exists():
        return {}
    try:
        return json.loads(STORE.read_text("utf-8"))
    except Exception:
        return {}

def _save(tasks):
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), "utf-8")
    tmp.replace(STORE)

def create_task(message, skill):
    with _LOCK:
        tasks = _load()
        task_id = uuid.uuid4().hex
        now = int(time.time())
        tasks[task_id] = {
            "id": task_id, "message": message, "skill": skill,
            "state": "queued", "created_at": now, "updated_at": now,
            "result": None, "error": None,
        }
        _save(tasks)
        return tasks[task_id]

def get_task(task_id):
    with _LOCK:
        return _load().get(task_id)

def update_task(task_id, **changes):
    with _LOCK:
        tasks = _load()
        task = tasks.get(task_id)
        if not task:
            return None
        task.update(changes)
        task["updated_at"] = int(time.time())
        _save(tasks)
        return task

def list_tasks(limit=25):
    with _LOCK:
        values = list(_load().values())
    values.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return values[:limit]

def recover_interrupted():
    with _LOCK:
        tasks = _load()
        changed = False
        for task in tasks.values():
            if task.get("state") == "running":
                task["state"] = "queued"
                task["updated_at"] = int(time.time())
                changed = True
        if changed:
            _save(tasks)

def needs_approval(message):
    text = (message or "").lower()
    protected = (
        "production", "real money", "uang asli", "wallet", "private key",
        "delete service", "hapus service", "change visibility", "ubah visibility",
    )
    return any(term in text for term in protected)
