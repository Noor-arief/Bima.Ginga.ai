# BIMA Ginga — Operational Resilience Roadmap

## P0 credential rotation checkpoint — 24 October 2026 (OPEN)

Canonical private runbook: [Railway credential rotation inventory and handover](https://github.com/Noor-arief/BIMA/blob/main/RAILWAY_CREDENTIAL_ROTATION_2026-10-24.md).

- [x] Read Railway preliminary incident report and owner-targeted notification; workspace targeting is not confirmed credential theft.
- [x] Verified existing Work browser Railway session and eight listed projects. Connector calls still return UNAUTHORIZED; do not repeatedly request reconnection. Chat without Work/browser must read the runbook and must not claim direct runtime access.
- [x] Content Studio Variables inventory confirms GEMINI_API_KEY, PIAPI_API_KEY, LTX_API_KEY and GOOGLE_CLIENT_SECRET. Prioritize paid-capable AI/cloud keys and privileged tokens; other project inventory is incomplete.
- [ ] Check provider usage/billing/audit logs since 20 October; revoke immediately if abuse is detected.
- [ ] Create replacement credentials, update every consumer/environment/shared-variable source and any Render/CI copies, deploy and verify, then revoke old credentials and retest.
- [ ] Complete remaining project, database/storage, GitHub/App/CI, email and OAuth token inventory; provider names in the runbook's conditional table are not confirmed runtime findings.
- [ ] Preserve encrypted state before TOKEN_ENCRYPTION_KEY rekey; never blindly overwrite it.

**No credentials have been rotated or revoked in this session.** Online/deployment-success observations do not close incident remediation. No secret values are in this update. Preserve existing roadmap work and approvals.

Updated: 23 October 2026. Master: https://github.com/Noor-arief/BIMA/issues/1

## P0 Railway incident & PHP2Shell risk — OPEN

Railway outage and token/security events between 20–23 Oct 2026 require provider-independent recovery. PHP2Shell CVE-2026-109618/109619 is a **separate** PHP runtime disclosure, patched 21 Oct (https://www.php.net/archive/2026.php). Main source tree uses Python/FastAPI, no tracked PHP files; deployed container and external dependencies still need review. No claim of a production breach or PHP exploit.

## Verified preparatory work
- [x] GitHub source inspected: task and memory state currently uses `/data/tasks.json`, `/data/conversations.json`, `/data/project_state.json` (depending on env config).
- [x] Cold-standby Render blueprint and recovery guide prepared in draft [PR #67](https://github.com/Noor-arief/Bima.Ginga.ai/pull/67). **Not merged or deployed.**

## P0 actions
- [ ] Inventory active containers/services, their PHP/runtime dependencies and all credentials; rotate exposed/at-risk credentials and investigate audit logs as provider guidance indicates.
- [ ] Create consistent encrypted backups of `/data` and task/approval records to independent storage; preserve confidentiality and test full restore.
- [ ] Confirm privileged endpoints require non-empty `BIMAGINGA_OWNER_KEY` on every host. Do not expose a standby process publicly with missing owner authorization.
- [ ] Review external DeepSeek/Gemini integrations and BIMA tasks: enforce rate/cost controls, single-writer execution and idempotent recovery after interruption.
- [ ] Prepare paid Render resources only after owner budget approval; keep the standby cold, with autonomous execution disabled. Restore and verify private data, then authenticated E2E and rollback before switching traffic.
- [ ] Add availability, backup freshness and recovery-drill reporting. Measure target RPO <=24h / RTO <=4h rather than claiming them achieved.

**Exit criteria:** off-Railway encrypted snapshot verified, isolated restore validated, one-writer failover and rollback tested, secrets/runtime assessed. The ability to load GitHub source alone is not disaster recovery.
