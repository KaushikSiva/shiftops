# Challenge 2 submission checklist

## Product
ShiftOps — embodied facility operations from incident to approved maintenance handoff.

## Required deliverables
- [x] Public GitHub repository: https://github.com/KaushikSiva/shiftops
- [ ] Vultr VM instance ID and provider evidence (pending VM access)
- [ ] Public browser demo URL (pending deployment)
- [x] Recorded local demo video: https://github.com/KaushikSiva/shiftops/releases/download/v0.1.0-local-preview/shiftops-demo.mp4
- [ ] Final video against the deployed public URL
- [x] Setup documentation and architecture
- [x] Multi-step operational workflow and enterprise-style web UI
- [x] CPU simulation/digital twin integration with existing G1 assets

## Judge walkthrough
Start a blocked-aisle air-handler inspection → see live physics route → pause and
resume → inspect evidence → approve → verify work order and reserved stock →
replay/download evidence. Then use the filter scenario to demonstrate a stockout.

## Cloud verification
The deployed Vultr VM must serve the frontend, API, database and workflow/physics
worker. A tunnel to a laptop or static frontend hosted elsewhere does not satisfy
this project's deployment claim. Run the public smoke test, restart the app and
verify durable state, and capture console proof with secrets redacted.

## Disclosure
Robot model, gait weights and NumPy executor predate this hackathon. The operations
platform, facility planner, persistence, UI and deployment package are new work.
Check event rules on reuse with organizers before submission if unclear.

Sensor observations are fictional, clearly labeled simulation. No real equipment
is inspected, no physical robot is actuated, no vendor is contacted, and no
maintenance repair is claimed. Existing learned locomotion supplies the AI;
workflow decisions are inspectable rules as permitted by the provided brief.
