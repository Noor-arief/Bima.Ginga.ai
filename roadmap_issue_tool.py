import json
import os
import urllib.error
import urllib.request


def _allowed(repo):
    allowed = [x.strip() for x in os.getenv("BIMA_GITHUB_ALLOWED_REPOS", "").split(",") if x.strip()]
    return repo in allowed


def _github(method, path, body=None):
    token = os.getenv("BIMA_GITHUB_TOKEN")
    if not token:
        raise RuntimeError("BIMA_GITHUB_TOKEN is not configured")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        "https://api.github.com" + path,
        data=data,
        method=method,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "BimaGinga-Roadmap-Worker",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as res:
            return json.loads(res.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:1200]
        raise RuntimeError("GitHub HTTP %s: %s" % (exc.code, detail))


def get_roadmap_issue(repo, issue_number):
    if not _allowed(repo):
        raise RuntimeError("Repository is not in BIMA_GITHUB_ALLOWED_REPOS")
    data = _github("GET", "/repos/%s/issues/%s" % (repo, int(issue_number)))
    return {
        "repo": repo,
        "issue_number": int(issue_number),
        "title": data.get("title"),
        "body": data.get("body") or "",
        "state": data.get("state"),
        "html_url": data.get("html_url"),
    }


def update_roadmap_issue(repo, issue_number, body):
    canonical_repo = os.getenv("BIMA_CANONICAL_REPO", "Noor-arief/BIMA").strip()
    canonical_issue = int(os.getenv("BIMA_ROADMAP_ISSUE_NUMBER", "1"))
    if not _allowed(repo):
        raise RuntimeError("Repository is not in BIMA_GITHUB_ALLOWED_REPOS")
    if repo != canonical_repo or int(issue_number) != canonical_issue:
        raise RuntimeError("Roadmap write is restricted to the canonical BIMA roadmap issue")
    if not isinstance(body, str) or not body.strip():
        raise RuntimeError("Roadmap issue body cannot be empty")
    data = _github("PATCH", "/repos/%s/issues/%s" % (repo, canonical_issue), {"body": body})
    return {
        "repo": repo,
        "issue_number": canonical_issue,
        "html_url": data.get("html_url"),
        "updated_at": data.get("updated_at"),
    }
