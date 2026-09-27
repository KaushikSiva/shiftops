# Validation evidence

Local checks were measured on 2026-09-26. The public Vultr deployment was verified
on 2026-09-27 at https://shiftops.104-156-229-254.sslip.io.

## Public Vultr verification

- [Provider evidence](validation/provider-vultr.json): the Vultr API identifies
  instance `d6fa84e7-0877-4ae1-926d-29fc2719435c` in `sjc`; the VM reports Vultr
  as its hardware vendor. Runtime commit: `4773d610343a6a1273d07234d62c9d181918e29c`.
- [External smoke test](validation/smoke-vultr.txt): an actual CPU inspection,
  199 recorded poses, zero obstacle contacts, and one approved work order with
  one bearing reservation, including a repeated approval request.
- [Public browser report](validation/browser-vultr.json): all 16 desktop/mobile
  checks passed with no browser errors, including pause/resume, cancellation,
  evidence export, replay and persistent reload.
- [Restart report](validation/persistence-vultr.json): an in-flight run recovered
  paused at the last recorded pose, resumed to inspection and retained its approved
  order and inventory through another restart. HTTPS, secure cookies, request
  limits, same-origin enforcement and unbuffered SSE also passed on the public VM.
- [Linux CI](https://github.com/KaushikSiva/shiftops/actions/runs/36290083728):
  19 backend tests, the frontend build and all 16 browser checks passed.

- [Public recording](validation/recording-vultr.json): two complete scenarios,
  including the stockout purchase request, captured from the deployed browser.

The browser renderer runs on the visitor's device; all simulation, workflow
decisions and persisted operations run on the Vultr VM.

## Backend and physics

`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q`
passed **19 tests**, including all three scenario routes in live MuJoCo.
The suite covers no-contact arrival, approval gating, idempotent approvals,
inventory reservations, stockout purchase requests, rejected requests, isolated
sessions, input validation, pause/resume and persistent restart recovery.

Six concurrency cases hold a physics step in flight while HTTP clients pause,
pause/resume or cancel the run. Both successful and failing stale steps are
discarded; resumed physics matches an independent engine restored from the last
committed checkpoint. Four cancellation cases cover planning, navigation, paused
and approval states, retaining evidence without changing stock or creating work.

One directly measured blocked-aisle air-handler inspection reached the target
in **39.8 simulated seconds**, walked approximately **15.0 meters**, and recorded
**zero obstacle contacts**. These are simulation results, not hardware benchmarks
or real-world safety guarantees.

## Browser

The browser walkthrough passed 16 checks:
dispatch/live inspection; pause freezes pose; resume; approval required; work order;
single stock reservation; evidence download; audit events; recorded-pose replay;
reload retains state; mobile without horizontal overflow; mobile intake; no browser errors.
It also verifies mobile cancellation without inventory changes, cancellation
persistence after reload, and accurate paused/canceled workflow labels.
See the [local browser report](validation/browser-local.json).

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

## Full local proxy stack

The current Compose application was also exercised behind its Caddy proxy, using
HTTPS with Caddy's local CA trusted explicitly by the test client. The
[proxy report](validation/proxy-local.json) records six passing checks:

- HTTPS and response headers; Secure, HttpOnly, SameSite=Strict session cookies.
- Successful same-origin writes and rejected foreign-origin/oversized writes.
- Two live SSE snapshots delivered without proxy buffering.
- Restart during navigation restores the last recorded pose and pauses the run.
- Explicit resume reaches inspection with zero obstacle contacts.
- One approved work order and one inventory reservation persist after a second restart.

This local rehearsal did not establish public DNS, public certificate issuance or
Vultr hosting. Those are now covered by the public verification above. CI also runs
the browser walkthrough and uploads its report/screenshots for review.

## Limits of this evidence

These checks verify an operational hackathon deployment, not a production SLA or
physical-robot safety certification. Robot assets are reused and disclosed;
equipment sensors, inventory and purchasing are simulation data. Event eligibility
and judging outcomes are not determined by application tests.
