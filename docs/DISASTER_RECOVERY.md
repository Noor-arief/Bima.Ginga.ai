# BIMA Ginga — disaster recovery readiness (23 Oct 2026)

Status: **configuration prepared only**. No second server, backup, or restore is claimed live. Railway has not been changed. This plan must be activated and verified by the owner.

## Production state to preserve

Source: `task_store.py`, `app.py` (main branch, 23 Oct 2026). With `BIMAGINGA_DATA_DIR=/data` the state includes:
- `/data/tasks.json`: execution tasks, statuses, approvals.
- `/data/conversations.json`: conversation continuity.
- `/data/project_state.json`: project checkpoints.
- Any other assets in the mounted volume, once inventoried.

Back up a **consistent snapshot**, not a partial copy of JSON files being written. Encryption is mandatory at rest and in transit, with keys held outside GitHub and outside Railway. Verify a test restore on a nonproduction environment. Maintain a recent offsite copy on another provider (e.g. an S3-compatible bucket that is not hosted by Railway), retain daily backups for at least 7 days plus weekly backups for 4 weeks, and alert on failed or stale copies. Exact schedule/storage cost awaits inspection of the real volume.

## Cold standby procedure (Render)

1. Import `render.yaml` via Render Blueprint only after reviewing recurring hosting + persistent disk costs. The template **does not** deploy itself.
2. On creation, require nonempty `BIMAGINGA_OWNER_KEY` before ever exposing privileged endpoints. **Code presently checks this key only when configured; missing owner key weakens protection.** Treat this as an activation blocker and verify access denial without a valid key.
3. Leave AI-provider and GitHub access tokens unset for smoke tests. Never copy secrets into the repo, CI logs, or chat. Reissue/revoke credentials after a suspected provider incident.
4. Restore `/data` from a verified external encrypted backup; check file ownership and permissions. Confirm task IDs, approvals, conversation counts, and state format; do not fabricate a clean state as recovered.
5. Run `/health`, then authenticated API checks and a read-only continuity check. A 200 response from `/health` alone does **not** validate restored data or downstream AI access.
6. Only after a verified restore and authorization checks, configure private provider credentials and the backup API URL; switch frontend traffic manually. Keep the original production process from executing the same pending tasks at the same time.
7. Reconcile tasks that may have completed during the outage. Resume write operations only after declaring one active primary. Document data-loss window and rollback path.

## Failover policy

- Default: Railway primary; Render cold standby; GitHub source of code; separate provider object storage for encrypted offsite data.
- Trigger: verified inability to serve required app endpoints after incident triage; do not fail over solely on inaccessible ChatGPT connector.
- Never run both task executors concurrently against independently copied state.
- Any service whose code/state does not yet have a verified offsite backup remains **not disaster recovered**.
- Quarterly: restore drill from external storage, review secret rotation and service-endpoint documentation.

Public documentation only: never add live tokens, customer records, emails, encryption keys, or volume data to this repository.
