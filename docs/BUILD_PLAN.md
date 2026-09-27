# ShiftOps implementation and evidence plan

Visual thesis: a warm, quiet industrial control room, with a large live isometric facility twin, graphite navigation and restrained safety-orange actions.
Content plan: working facility view first; incident intake and robot status; decision/evidence inspector; work orders and audit history as alternate working surfaces.
Interaction thesis: interpolate actual server robot poses; animate route changes; reveal workflow evidence as durable events arrive. Reduced-motion users get direct state changes.

## Challenge contract
- Vultr VM runs API, workflow control, SQLite system of record, CPU MuJoCo and web assets.
- Public browser experience with isolated demonstration workspaces.
- Multi-step workflow: intake → classify → safe route → physical simulation inspection → parts/work order proposal → human approval → durable handoff.
- Reuse existing G1 project: robot URDF/STLs, frozen LSTM gait weights, NumPy gait executor. Clearly disclose previous work; new facility/workflow/enterprise UI is hackathon work.
- Public GitHub source, setup instructions, architecture, public deployed URL, recorded demo.
- No claim of live robot hardware, actual repair, external CMMS integration or real purchases. Scenario equipment readings are simulated. Robot poses are from CPU physics.

## Completion evidence
- API tests: tenant isolation, idempotency, approval/rejection, inventory accounting, persistence, stop/resume, bounded inputs.
- Physics test: robot reaches actual inspection location without falls or obstacle contacts.
- Browser: create mission, observe pose progression, approval, work order, replay/export; desktop and mobile screenshots; no console errors.
- Deployment: independently GET public health, assets, create/approve demo mission, restart container and verify persisted records.
- Demo video of actual browser flow; README links to live deployment and evidence.

Deployment and public verification completed on 2026-09-27; see
`DEPLOYMENT.md` and `validation/`. Winning is a judging outcome; do not assert
guaranteed results or invented ratings.
