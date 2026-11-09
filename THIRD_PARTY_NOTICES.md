# Third-Party Notices & Asset Licences

## 1. Python & Simulation Libraries
- **Pydantic** (`MIT License`) — Schema validation and JSON Schema generation in `contracts/schemas.py`.
- **NumPy** (`BSD-3-Clause License`) — Numerical arrays, hair spline generation, and kinematics integration.
- **MuJoCo** (`Apache-2.0 License`, DeepMind) — Physics MJCF specification in `simulation/habitats/v1.xml` and benchmark in `scripts/bench_mujoco.py`.
- **Gymnasium** (`MIT License`, Farama Foundation) — Environment API convention used by `simulation/habitat_env.py`.
- **Blender 5.2.3 LTS** (`GPL-3.0-or-later`) — Headless Cycles + OptiX rendering and `HairCurves` / `Geometry Nodes` evaluation.

## 2. 3D Textures, HDRIs & Reference Datasets
- **Poly Haven Textures & HDRI (`CC0 1.0 Universal Public Domain Dedication`):**
  - `fine_grained_wood`, `plywood`, `bark_brown_02`, `concrete_floor_worn_001`, and `brown_photostudio_02_1k.hdr`.
  - Full per-file attribution and source URLs are logged in `reference/licence_log.csv`.
- **Reference Photos (`reference/photos/images.cv_23mpmrt35vasncelu0dtfo`):**
  - User-provided hamster dataset (`images.cv`, 1,464 images across `train`/`val`/`test`), used strictly for local anatomical proportion and coat-color reference comparison (`renders/compare/05_compare_with_reference.png`).

