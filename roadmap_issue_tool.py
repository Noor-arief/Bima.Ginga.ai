import json
import os
import time
import urllib.error
import urllib.request

import jwt


def _allowed(repo):
    allowed = [x.strip() for x in os.getenv("BIMA_GITHUB_ALLOWED_REPOS", "").split(",") if x.strip()]
    return repo in allowed


def _request(method, path, token, body=None):
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
            raw = res.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:1200]
        raise RuntimeError("GitHub HTTP %s: %s" % (exc.code, detail))


def _github_app_token():
    app_id = os.getenv("BIMA_GITHUB_APP_ID", "").strip()
    installation_id = os.getenv("BIMA_GITHUB_INSTALLATION_ID", "").strip()
    private_key = os.getenv("BIMA_GITHUB_APP_PRIVATE_KEY", "")
    if not app_id or not installation_id or not private_key.strip():
        return None

    # Railway stores multiline variables verbatim, but also tolerate escaped newlines.
    private_key = private_key.replace("\\n", "\n")
    now = int(time.time())
    app_jwt = jwt.encode(
        {"iat": now - 60, "exp": now + 540, "iss": app_id},
        private_key,
        algorithm="RS256",
    )
    data = _request(
        "POST",
        "/app/installations/%s/access_tokens" % installation_id,
        app_jwt,
    )
    token = data.get("token")
    if not token:
        raise RuntimeError("GitHub App installation token was not returned")
    return token


def _github(method, path, body=None):
    # Roadmap operations prefer the dedicated BimaGinga GitHub App identity.
    # Keep the existing PAT only as a compatibility fallback until migration is verified.
    token = _github_app_token() or os.getenv("BIMA_GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GitHub credentials are not configured")
    return _request(method, path, token, body)


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
