# Public deployment demonstration

[Watch the 2-minute-35-second demo](https://github.com/KaushikSiva/shiftops/releases/download/v1.0.0/shiftops-vultr-demo.mp4)

Recorded from https://shiftops.104-156-229-254.sslip.io on 2026-09-27.
Footage shows actual browser operations on the Vultr deployment, with scripted
Samantha narration and scene captions. The recording covers two complete workflows.

| Start | Scene |
| --- | --- |
| 0:00 | Live on Vultr · ShiftOps facility operations |
| 0:12 | Dispatch an air-handler inspection |
| 0:20 | Live MuJoCo physics · existing learned G1 gait |
| 0:27 | Pause retains the robot and controller checkpoint |
| 0:35 | Resume from durable state |
| 0:47 | Review evidence and the proposed parts reservation |
| 1:03 | Approval commits the handoff · repair remains pending |
| 1:12 | Durable decisions and downloadable evidence |
| 1:22 | Replay actual recorded robot poses |
| 1:36 | An exception: the replacement filter is out of stock |
| 2:04 | Stockout becomes a purchase request |
| 2:15 | Purchasing review queued · no external order sent |
| 2:23 | Vultr runs the app, workflow, physics and records |

The equipment readings and warehouse inventory are simulated. The G1 model and
learned gait are reused from the existing robotics project; the facility workflow,
approval ledger, operations UI and deployed backend are new hackathon work.

The work-order handoff does not claim a completed repair, and the stockout workflow
does not send an order to an external vendor. See [recording evidence](validation/recording-vultr.json)
for the exact duration, scene timing, scenario IDs and video hash.
