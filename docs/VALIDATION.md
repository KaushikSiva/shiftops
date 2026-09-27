# Validation evidence

Measured locally on 2026-09-26. Deployment on Vultr is not yet verified.

## Backend and physics

`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q`
passed **9 tests**, including all three scenario routes in live MuJoCo.
The suite covers no-contact arrival, approval gating, idempotent approvals,
inventory reservations, stockout purchase requests, rejected requests, isolated
sessions, input validation, pause/resume and persistent restart recovery.

One directly measured blocked-aisle air-handler inspection reached the target
in **39.8 simulated seconds**, walked approximately **15.0 meters**, and recorded
**zero obstacle contacts**. These are simulation results, not hardware benchmarks
or real-world safety guarantees.

## Browser

The browser walkthrough passed 13 checks:
dispatch/live inspection; pause freezes pose; resume; approval required; work order;
single stock reservation; evidence download; audit events; recorded-pose replay;
reload retains state; mobile without horizontal overflow; mobile intake; no browser errors.

Artifacts are produced by `npm run test:e2e`. Selected screenshots are committed
under `docs/media/`. The recording is an actual local application session.

## Linux container

The image built and ran as the unprivileged application user with a read-only root
filesystem and a dedicated writable SQLite volume. An HTTP smoke test completed
inspection and approval, exported **199 recorded poses**, and verified zero contacts.

An actual container restart during navigation:
1. Left the run paused after recovery.
2. Restored the last persisted pose, matching the last recorded trajectory frame.
3. Resumed and reached the inspection target.
4. Created one work order and reserved one seal kit after approval.
5. Retained that work order and inventory balance after a second container restart.

The container test ran locally on Linux ARM64 via Docker Desktop. It does not prove
Vultr hosting or Linux AMD64 execution. CI exercises the portable Python/backend
suite on GitHub's Linux runner. [The first Linux AMD64 CI run passed](https://github.com/KaushikSiva/shiftops/actions/runs/36289223571), including all nine tests and the frontend build.

## Still required

- A configured Vultr VM, public hostname/URL and provider evidence.
- Public endpoint smoke test plus deployed persistence check.
- Rerecord the final judging video against that public deployment.
- Review event rules concerning previously built robot assets.
