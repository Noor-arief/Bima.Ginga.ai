"""Connector registry + health checks for the BimaGinga Connectors menu.

Status is derived from environment variables only (no secrets are ever returned).
`test_connector` makes one lightweight, read-only call to the provider.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import roadmap_issue_tool as gh

UA = "BimaGinga-Connectors/1.0"

CONNECTORS = {
    "github": {"name": "GitHub", "kind": "connector"},
    "railway": {"name": "Railway", "kind": "connector"},
    "resend": {"name": "Resend (Email)", "kind": "connector"},
    "sheets": {"name": "Google Sheets", "kind": "connector", "soon": True},
}


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def _github_configured() -> bool:
    app = gh._github_app_config()
    has_app = all([app[0], app[1], app[2].strip()])
    return (has_app or bool(_env("BIMA_GITHUB_TOKEN"))) and bool(_env("BIMA_GITHUB_ALLOWED_REPOS"))


def _configured(cid: str) -> bool:
    if cid == "github":
        return _github_configured()
    if cid == "railway":
        return bool(_env("RAILWAY_API_TOKEN"))
    if cid == "resend":
        return bool(_env("RESEND_API_KEY"))
    return False


def connector_status() -> list[dict]:
    out = []
    for cid, meta in CONNECTORS.items():
        if meta.get("soon"):
            state = "soon"
        else:
            state = "configured" if _configured(cid) else "not_configured"
        out.append({"id": cid, "name": meta["name"], "kind": meta["kind"], "state": state})
    return out


def _json_request(method, url, headers, body=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {"User-Agent": UA, "Accept": "application/json", **headers}
    if data is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            raw = res.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise RuntimeError("HTTP %s dari %s" % (exc.code, url.split("/")[2]))
    except urllib.error.URLError as exc:
        raise RuntimeError("Tidak bisa terhubung: %s" % exc.reason)


def test_connector(cid: str) -> dict:
    if cid not in CONNECTORS:
        raise KeyError(cid)
    if CONNECTORS[cid].get("soon"):
        return {"id": cid, "ok": False, "detail": "Belum tersedia."}
    if not _configured(cid):
        return {"id": cid, "ok": False, "detail": "Belum diatur: environment variable belum lengkap."}
    try:
        if cid == "github":
            repos = [r.strip() for r in _env("BIMA_GITHUB_ALLOWED_REPOS").split(",") if r.strip()]
            data = gh._github("GET", "/repos/%s" % repos[0])
            detail = "Bisa membaca repo %s." % data.get("full_name", repos[0])
        elif cid == "railway":
            data = _json_request(
                "POST", "https://backboard.railway.com/graphql/v2",
                {"Authorization": "Bearer " + _env("RAILWAY_API_TOKEN")},
                {"query": "{ me { name } }"},
            )
            if data.get("errors"):
                raise RuntimeError("Token ditolak atau bukan account token.")
            detail = "Token Railway valid."
        else:
            _json_request("GET", "https://api.resend.com/domains",
                          {"Authorization": "Bearer " + _env("RESEND_API_KEY")})
            detail = "API key Resend valid."
        return {"id": cid, "ok": True, "detail": detail}
    except Exception as exc:  # never leak secrets: only our own short messages
        return {"id": cid, "ok": False, "detail": str(exc)[:200]}
