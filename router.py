import re
from dataclasses import dataclass

ACTION_RE = re.compile(
    r"\b(?:kerjakan|selesaikan|fix|perbaiki|debug|ubah|edit|implement|test|uji|cek\s+repo|inspect\s+repo|audit|update)\b",
    re.I,
)
CREATE_RE = re.compile(
    r"\bbuat\s+(?:file|branch|commit|pull request|pr|endpoint|api|fungsi|function|script|kode|code|folder|service|deployment)\b",
    re.I,
)
STATUS_RE = re.compile(
    r"\b(?:status|checkpoint|progress|progres|pending|roadmap|sampai\s+mana|posisi\s+terakhir)\b",
    re.I,
)
CONTINUE_RE = re.compile(r"^(?:lanjut|lanjutkan|terus|continue|gas|ok\s+lanjut)\b", re.I)


@dataclass(frozen=True)
class Route:
    kind: str
    reason: str


def is_continuation(message: str) -> bool:
    text = " ".join((message or "").strip().split())
    return bool(CONTINUE_RE.search(text))


def route_message(message: str, active_task: bool = False) -> Route:
    text = " ".join((message or "").strip().split())
    if ACTION_RE.search(text) or CREATE_RE.search(text):
        return Route("execution", "explicit execution intent")
    if active_task and is_continuation(text):
        return Route("execution", "continuation of active execution task")
    if STATUS_RE.search(text):
        return Route("status", "informational project-state request")
    return Route("chat", "normal conversation")
