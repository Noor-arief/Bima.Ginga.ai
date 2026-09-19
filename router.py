import re
from dataclasses import dataclass

ACTION_RE = re.compile(r"\b(?:kerjakan|selesaikan|lanjutkan|lanjut|fix|perbaiki|debug|ubah|edit|implement|buat|test|uji|cek\s+repo|inspect\s+repo|audit)\b", re.I)
STATUS_RE = re.compile(r"\b(?:status|checkpoint|progress|progres|pending|roadmap|sampai\s+mana|posisi\s+terakhir)\b", re.I)

@dataclass(frozen=True)
class Route:
    kind: str
    reason: str

def route_message(message: str, active_task: bool = False) -> Route:
    text = " ".join((message or "").strip().split())
    if ACTION_RE.search(text):
        return Route("execution", "explicit execution intent")
    if active_task and re.search(r"^(?:lanjut|lanjutkan|terus|continue|gas|ok\s+lanjut)\b", text, re.I):
        return Route("execution", "continuation of active execution task")
    if STATUS_RE.search(text):
        return Route("status", "informational project-state request")
    return Route("chat", "normal conversation")
