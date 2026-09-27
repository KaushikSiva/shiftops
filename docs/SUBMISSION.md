# Challenge 2 submission checklist

## Product
ShiftOps — embodied facility operations from incident to approved maintenance handoff.

## Required deliverables
- [x] Public GitHub repository: https://github.com/KaushikSiva/shiftops
- [x] Vultr VM: `d6fa84e7-0877-4ae1-926d-29fc2719435c`, Silicon Valley. [Provider evidence](validation/provider-vultr.json).
- [x] Public browser demo: https://shiftops.104-156-229-254.sslip.io
- [x] Recorded local demo video: https://github.com/KaushikSiva/shiftops/releases/download/v0.1.0-local-preview/shiftops-demo.mp4
- [x] Final public-deployment video (2:35): https://github.com/KaushikSiva/shiftops/releases/download/v1.0.0/shiftops-vultr-demo.mp4
- [x] Setup documentation and architecture
- [x] Multi-step operational workflow and enterprise-style web UI
- [x] CPU simulation/digital twin integration with existing G1 assets

## Judge walkthrough
Start a blocked-aisle air-handler inspection → see live physics route → pause and
resume → inspect evidence → approve → verify work order and reserved stock →
replay/download evidence. Then use the filter scenario to demonstrate a stockout.

## Cloud verification
The Vultr VM serves the frontend, API, database and workflow/physics worker.
Public browser tests and the HTTP smoke test passed. Two real container restarts
verified recovery of an in-flight checkpoint and persistence of the approved order
and inventory. [Verification reports](VALIDATION.md) include provider metadata,
trusted HTTPS, the deployed commit and the public walkthrough results.

## Disclosure
Robot model, gait weights and NumPy executor predate this hackathon. The operations
platform, facility planner, persistence, UI and deployment package are new work.
Check event rules on reuse with organizers before submission if unclear.

Sensor observations are fictional, clearly labeled simulation. No real equipment
is inspected, no physical robot is actuated, no vendor is contacted, and no
maintenance repair is claimed. Existing learned locomotion supplies the AI;
workflow decisions are inspectable rules as permitted by the provided brief.
