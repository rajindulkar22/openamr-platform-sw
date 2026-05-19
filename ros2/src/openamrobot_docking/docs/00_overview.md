# Overview

What this package does, why it exists, and how to navigate the rest of the documentation.

For installation and a first run, see [`01_quickstart.md`](01_quickstart.md).

---

## What this package does

`openamrobot_docking` is a ROS 2 (Jazzy) package that makes a differential-drive robot autonomously dock onto a charging station marked with an **AprilTag** (family 36h11, ID 0).

In one sentence: **publish a `Bool true` on `/dock_trigger`, the robot drives to a staging zone near the dock, refines its position using the camera-detected AprilTag, and stops perpendicular to the tag at a configurable distance — aligned and ready to charge.**

This package handles:

- AprilTag detection from a simulated camera (`apriltag_ros`)
- TF transformation of the tag pose into the `map` frame
- Navigation to a *staging* pose in front of the dock (via Nav2's `NavigateToPose` action)
- A custom **4-phase docking sequencer** that takes over after staging:
  - in-camera centring scan,
  - running-average filtering of 40 detections,
  - in-place spin to the perpendicular yaw,
  - pure-pursuit line-tracking with **distance-weighted refinement** and **outlier rejection**, then a **handover to camera-frame visual servoing** in the near field once the line is stable.

This package does **not** handle:

- Battery monitoring or charge-state detection — needs separate code
- Map building — assume Nav2 + AMCL is running on a pre-built map (or SLAM in mapping mode)
- The decision of *when* to dock — must be triggered externally (UI, scheduler, behaviour tree, etc.)

---

## Why this design

A single-shot AprilTag detection has ~3 – 13 cm of position error depending on tag size, distance, lighting, and camera resolution. Relying on a single detection — or steering on the latest noisy detection in a closed loop — produces visible wobble at the dock.

The 4-phase pipeline addresses this in **four** layers:

1. **Centring scan (phase 2)** lines up the tag in the *centre of the camera* before any filtering, which makes solvePnP's residual lateral bias symmetric.
2. **Running-average filter (phases 2 + 4)** absorbs single-detection noise. The filter keeps updating in phase 4, refining the perpendicular line as the robot drives.
3. **Robust averaging in phase 4** — single-frame outliers are rejected before they reach the mean, and the remaining samples are **distance-weighted** so far-field (cleaner) detections dominate over noisier near-field ones.
4. **Line-tracking → visual-servo handover** — once the line has accumulated enough refinement samples (or the robot has approached too close for map-frame solvePnP to be trustworthy), the controller switches from steering on the map-frame perpendicular line to a **closed-loop on the image-frame angle** to the tag. The image-frame angle is robust to the same near-field noise that corrupts the map-frame line, because it directly tracks where the tag appears in the camera.

In simulation this delivers ~1–2 cm of lateral error and ~1° of yaw error at the dock — limited mostly by the discretisation of the AprilTag corner detection.

---

## High-level architecture

```
            ┌──────────────────────────────────────┐
            │  Gazebo camera plugin (gz sensor)    │
            └──────────────────┬───────────────────┘
                               │ gz /rgb_image
                               │ gz /camera_info
                               ▼
            ┌──────────────────────────────────────┐
            │  ros_gz_bridge (this package adds    │
            │  a /camera_info bridge instance)     │
            └──────────────────┬───────────────────┘
                               │ /rgb_image
                               │ /camera_info
                               ▼
            ┌──────────────────────────────────────┐
            │  apriltag_ros::apriltag_node         │
            │  (params: family 36h11, size 0.40)   │
            └──────────────────┬───────────────────┘
                               │ TF: camera_optical_frame →
                               │     charging_dock_apriltag
                               ▼
            ┌──────────────────────────────────────┐
            │  detected_dock_pose_publisher (C++)  │
            │  TF map→charging_dock_apriltag → Pose│
            └──────────────────┬───────────────────┘
                               │ /detected_dock_pose @ 10 Hz
                               ▼
            ┌──────────────────────────────────────┐
            │  dock_trigger.py (4-phase sequencer) │
            │  • Phase 1: NavigateToPose (Nav2)    │
            │  • Phase 2: scan + filter            │
            │  • Phase 3: align spin               │
            │  • Phase 4: line-tracking advance    │
            └──────────────────┬───────────────────┘
                               │ /cmd_vel
                               ▼
            ┌──────────────────────────────────────┐
            │  DiffDrive plugin (Gazebo)           │
            └──────────────────────────────────────┘
```

The full TF chain is in [`03_tf_frames.md`](03_tf_frames.md), the node graph + topic table in [`02_architecture.md`](02_architecture.md).

---

## Prerequisites at a glance

| What you need | Why |
|---|---|
| Ubuntu 24.04 + ROS 2 Jazzy | The whole stack targets Jazzy specifically |
| CycloneDDS as RMW (`export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`) | FastDDS has a Python crash bug on Jazzy that breaks `dock_trigger.py` silently when sending action goals |
| `openamrobot_gazebo` + `openamrobot_nav2` + `openamrobot_description` installed | This package composes them at runtime |
| `apriltag_ros` (`sudo apt install ros-jazzy-apriltag-ros`) | The detector |
| `topic_tools` (only if you choose the relay variant) and `ros_gz_bridge` | Bridge / forwarding utilities |

For exact install commands and the launch sequence, see [`01_quickstart.md`](01_quickstart.md).

---

## Where to go next

| If you want to… | Start with |
|---|---|
| Install everything and run the simulation | [`01_quickstart.md`](01_quickstart.md) |
| Understand how the pipeline works | [`02_architecture.md`](02_architecture.md) |
| Read about the TF chain | [`03_tf_frames.md`](03_tf_frames.md) |
| Set up AprilTag detection (sim or real) | [`04_apriltag.md`](04_apriltag.md) |
| Tune parameters | [`05_parameters.md`](05_parameters.md) |
| Calibrate a real camera | [`06_camera_calibration.md`](06_camera_calibration.md) |
| Reproduce results | [`07_reproduce_results.md`](07_reproduce_results.md) |
| Deep-dive the 4-phase sequencer | [`08_sequencer_4phase.md`](08_sequencer_4phase.md) |
| Diagnose a failure | [`09_troubleshooting.md`](09_troubleshooting.md) |
| See block diagrams | [`10_diagrams.md`](10_diagrams.md) |
| Understand what we changed from upstream | [`11_changes_from_upstream.md`](11_changes_from_upstream.md) |
| Learn from past mistakes | [`12_lessons_learned.md`](12_lessons_learned.md) |
