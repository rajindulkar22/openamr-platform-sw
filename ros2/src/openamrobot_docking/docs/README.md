# openamrobot_docking — engineering documentation

This folder contains the engineering documentation for the autodocking pipeline shipped by [`openamrobot_docking`](../).

The package-level [README.md](../README.md) is the practical entry point ("how to run it today"). These docs are the **engineering record** — the *why* and *how it's built*.

---

## Layout

```
docs/
├── README.md                       ← this file (index)
│
├── 00_overview.md                  what the package is and why this design
├── 01_quickstart.md                run the docking simulation end-to-end
├── 02_architecture.md              node graph, lifecycle, topic flow
├── 03_tf_frames.md                 the TF chain (robot, camera, dock)
├── 04_apriltag.md                  AprilTag setup (sim + real robot)
├── 05_parameters.md                every dock_trigger.yaml parameter
├── 06_camera_calibration.md        intrinsics + extrinsics (real robot)
├── 07_reproduce_results.md         end-to-end reproduction checklist
├── 08_sequencer_4phase.md          the 4-phase pipeline, phase by phase
├── 09_troubleshooting.md           symptom → cause → fix matrix
├── 10_diagrams.md                  block / TF / state diagrams (text)
├── 11_changes_from_upstream.md     what this revision changes vs prior pipelines
└── 12_lessons_learned.md           decisions diary with rationale
```

---

## How to read

| Goal | Read |
|---|---|
| **New to the pipeline** | `00_overview.md` → `01_quickstart.md` → `02_architecture.md` |
| **Run it on my machine** | `01_quickstart.md` (3-terminal flow) |
| **Tune the controller** | `05_parameters.md` + `08_sequencer_4phase.md` |
| **Something doesn't work** | `09_troubleshooting.md` then `12_lessons_learned.md` for the deeper why |
| **Onboarding a teammate** | `08_sequencer_4phase.md` + `10_diagrams.md` |
| **Port to real hardware** | `04_apriltag.md` + `06_camera_calibration.md` + `03_tf_frames.md` |
| **Audit / understand a design choice** | `11_changes_from_upstream.md` + `12_lessons_learned.md` |

---

## Conventions used throughout these docs

- **Frames**: `map → odom → base_link → camera_link → camera_optical_frame → charging_dock_apriltag` (the chain produced by SLAM/AMCL + URDF static + apriltag_ros).
- **Topics**:
  - Image: `/rgb_image` (gz bridge)
  - Camera intrinsics: `/camera_info` (bridged in this package's launch)
  - Tag detections: `/apriltag/detections`
  - Dock pose in map: `/detected_dock_pose` (PoseStamped, 10 Hz)
  - Drive commands: `/cmd_vel` (Phase 4 publishes directly; Phase 1 goes through Nav2's action server)
  - Trigger: `/dock_trigger` (Bool)
- **World coordinates** (Raj's `walled_world.sdf`):
  - Robot spawn: world `(0, 0, 0)` yaw=0
  - AprilTag dock: world `(4.899, 0, 0.5)` yaw=π (panel mounted on the +x wall, tag normal facing −x)
  - Map ≡ world (AMCL initialised at map origin = robot spawn position)
- **Sequencer**: the 4-phase pipeline in [`scripts/dock_trigger.py`](../scripts/dock_trigger.py).
