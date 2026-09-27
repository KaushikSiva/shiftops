# Third-party notices

## Unitree G1 assets and frozen locomotion policy

The G1 URDF, STL meshes and frozen LSTM gait arrays are reused from the author's
G1 Street Wise project. Its upstream source is Unitree Robotics' `unitree_rl_gym`,
whose BSD 3-Clause license is preserved in [docs/UNITREE_LICENSE.txt](docs/UNITREE_LICENSE.txt).
The original policy and model lineage is the official G1 12-DOF model and
`deploy/pre_train/g1/motion.pt`. The locally recorded provenance manifest contains
the source paths and SHA-256 hashes of the exact reused files.

The NumPy LSTM executor is adapted from the author's existing project. ShiftOps
changes matrix-vector execution to NumPy contractions while retaining the weights
and equations. No policy training or improvement is claimed.

## Dependencies

MuJoCo, NumPy, FastAPI, Uvicorn, Three.js, urdf-loader, Lucide, Vite, Playwright and
the other pinned dependencies retain their respective upstream licenses. They
are external package dependencies. DM Sans and IBM Plex Mono are served by Google
Fonts and use the SIL Open Font License; the interface has system-font fallbacks.

The facility geometry and operator interface are created for this project. No
third-party character art, private customer records, or robotics credentials are
included. Unitree and Vultr do not endorse this application.
