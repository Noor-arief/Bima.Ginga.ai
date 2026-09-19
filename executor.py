import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from openai import OpenAI

def _allowed(repo):
    allowed = [x.strip() for x in os.getenv("BIMA_GITHUB_ALLOWED_REPOS", "").split(",") if x.strip()]
    return repo in allowed

def _github(method, path, body=None):
    token = os.getenv("BIMA_GITHUB_TOKEN")
    if not token:
        raise RuntimeError("BIMA_GITHUB_TOKEN is not configured")
    url = "https://api.github.com" + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "BimaGinga-Execution-Worker",
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as res:
            return json.loads(res.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:1200]
        raise RuntimeError("GitHub HTTP %s: %s" % (exc.code, detail))

def _default_ref(repo):
    refs = {"Noor-arief/BIMA": "telegram-autonomous-project-execution", "Noor-arief/Bima.Ginga.ai": "main"}
    return refs.get(repo, "main")

def github_get_file(repo, path, ref=None):
    if not _allowed(repo):
        raise RuntimeError("Repository is not in BIMA_GITHUB_ALLOWED_REPOS")
    ref = ref or _default_ref(repo)
    q = urllib.parse.urlencode({"ref": ref})
    data = _github("GET", "/repos/%s/contents/%s?%s" % (repo, urllib.parse.quote(path), q))
    content = base64.b64decode(data["content"]).decode("utf-8")
    return {"repo": repo, "path": path, "ref": ref, "sha": data["sha"], "content": content[:30000]}

def github_put_new_file(repo, path, content, message, branch):
    if not _allowed(repo):
        raise RuntimeError("Repository is not in BIMA_GITHUB_ALLOWED_REPOS")
    if branch in {"main", "master"}:
        raise RuntimeError("Sandbox branch required")
    payload = {"message": message, "content": base64.b64encode(content.encode()).decode(), "branch": branch}
    data = _github("PUT", "/repos/%s/contents/%s" % (repo, urllib.parse.quote(path)), payload)
    return {"commit_sha": data["commit"]["sha"], "path": path, "branch": branch}

def github_update_file(repo, path, content, message, sha, branch="main"):
    if not _allowed(repo):
        raise RuntimeError("Repository is not in BIMA_GITHUB_ALLOWED_REPOS")
    payload = {"message": message, "content": base64.b64encode(content.encode()).decode(), "sha": sha, "branch": branch}
    data = _github("PUT", "/repos/%s/contents/%s" % (repo, urllib.parse.quote(path)), payload)
    return {"commit_sha": data["commit"]["sha"], "path": path, "branch": branch}

def railway_project_status(project_id):
    allowed = [x.strip() for x in os.getenv("BIMA_RAILWAY_ALLOWED_PROJECTS", "").split(",") if x.strip()]
    if project_id not in allowed:
        raise RuntimeError("Project is not in BIMA_RAILWAY_ALLOWED_PROJECTS")
    token = os.getenv("BIMA_RAILWAY_TOKEN")
    if not token:
        raise RuntimeError("BIMA_RAILWAY_TOKEN is not configured")
    body = {"query": "query($id: String!) { project(id: $id) { id name services { edges { node { id name } } } } }", "variables": {"id": project_id}}
    req = urllib.request.Request("https://backboard.railway.com/graphql/v2", data=json.dumps(body).encode(), method="POST", headers={"Authorization":"Bearer "+token,"Content-Type":"application/json","User-Agent":"BimaGinga-Execution-Worker"})
    with urllib.request.urlopen(req, timeout=25) as res:
        payload = json.loads(res.read().decode())
    if payload.get("errors"):
        raise RuntimeError("Railway GraphQL error: " + json.dumps(payload["errors"])[:1200])
    return payload.get("data", {}).get("project")

TOOLS = [
    {"type":"function","function":{"name":"github_put_new_file","description":"Create a new text artifact on an existing sandbox branch.","parameters":{"type":"object","properties":{"repo":{"type":"string"},"path":{"type":"string"},"content":{"type":"string"},"message":{"type":"string"},"branch":{"type":"string"}},"required":["repo","path","content","message","branch"]}}},
    {"type":"function","function":{"name":"github_get_file","description":"Read a UTF-8 file from an allowlisted GitHub repository.","parameters":{"type":"object","properties":{"repo":{"type":"string"},"path":{"type":"string"},"ref":{"type":"string","description":"Optional branch/ref. Omit to use the repository canonical default configured by BIMA."}},"required":["repo","path"]}}},
    {"type":"function","function":{"name":"github_update_file","description":"Update an existing UTF-8 file in an allowlisted GitHub repository. Never use for production/protected changes without approval.","parameters":{"type":"object","properties":{"repo":{"type":"string"},"path":{"type":"string"},"content":{"type":"string"},"message":{"type":"string"},"sha":{"type":"string"},"branch":{"type":"string"}},"required":["repo","path","content","message","sha"]}}},
    {"type":"function","function":{"name":"railway_project_status","description":"Read project and service identity from an allowlisted Railway project. Read-only.","parameters":{"type":"object","properties":{"project_id":{"type":"string"}},"required":["project_id"]}}},
]

def execute_task(message, skill_instruction):
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    client = OpenAI(api_key=key, base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    messages = [
        {"role":"system","content":"You are BIMA Execution Worker. Use tools when the task requires repository evidence or edits. Never invent tool results. Keep changes minimal. For Noor-arief/BIMA, the canonical working branch is telegram-autonomous-project-execution unless the user explicitly names another branch. Never perform production, destructive, wallet, or real-money actions. Continue until the task is actually complete or a concrete blocker exists. "+skill_instruction},
        {"role":"user","content":message},
    ]
    evidence = []
    for _ in range(10):
        response = client.chat.completions.create(model=model, messages=messages, tools=TOOLS, tool_choice="auto")
        msg = response.choices[0].message
        if not msg.tool_calls:
            answer = (msg.content or "").strip()
            failed_tools = [item for item in evidence if not item.get("ok")]
            state = "blocked" if failed_tools else "completed"
            return {"answer": answer, "evidence": evidence, "provider": "deepseek", "terminal_state": state}
        messages.append(msg)
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments or "{}")
            try:
                if call.function.name == "github_put_new_file":
                    result = github_put_new_file(**args)
                elif call.function.name == "github_get_file":
                    result = github_get_file(**args)
                elif call.function.name == "github_update_file":
                    result = github_update_file(**args)
                else:
                    raise RuntimeError("Unknown tool")
                evidence.append({"tool": call.function.name, "ok": True, "summary": {k:v for k,v in result.items() if k != "content"}})
                payload = result
            except Exception as exc:
                evidence.append({"tool": call.function.name, "ok": False, "error": str(exc)})
                payload = {"error": str(exc)}
            messages.append({"role":"tool","tool_call_id":call.id,"content":json.dumps(payload, ensure_ascii=False)})
    raise RuntimeError("Execution step limit reached before completion")
