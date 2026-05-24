# Authors and Contributors

This repository is maintained by the OpenAMRobot organization.

## Maintainer

- OpenAMRobot organization
- Contact: botshare.ai@gmail.com

## Contributors

Recognition is given to contributors whose work has materially shaped this repository. Contributions are grouped by area of focus rather than by chronology. Listing here does not replace GitHub history — it complements it by making non-trivial contributions easy to find for new readers, students, and downstream users.

### Repository architecture

- **Alex** ([OpenAMRobot maintainer](mailto:botshare.ai@gmail.com))
  - Top-level `openamr-platform-sw` monorepo structure (`ros2/src/`, `simulation/`, `config/`, `docs/`, `scripts/`, `tools/`)
  - Initial package scaffolding for `openamrobot_description`, `openamrobot_gazebo`, `openamrobot_nav2`, `openamrobot_docking`
  - Placeholder packages reserved for future work: `openamrobot_bringup`, `openamrobot_control`, `openamrobot_drivers`, `openamrobot_perception`
  - Repository governance scaffolding (`LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, `NOTICE.md`, `AUTHORS.md`, `CHANGELOG.md`)
  - Initial `gz_simulator.launch.py` and `walled_world.sdf` test world in `openamrobot_gazebo`
  - PR review, scope guidance, repository conventions

### Simulation, navigation and robot description

- **Raj Indulkar** — [@rajindulkar22](https://github.com/rajindulkar22)
  - **Populated `openamrobot_nav2`** from the empty scaffold to a complete Nav2 stack:
    - `config/nav2_params.yaml` — RegulatedPurePursuitController, NavfnPlanner, AMCL, behavior tree, costmaps (global + local with `obstacle_layer + voxel_layer`), velocity smoother, collision monitor.
    - `config/slam.yaml` — SLAM Toolbox configuration for online mapping.
    - `config/scan_body_filter.yaml` — `laser_filters` configuration to mask the robot's own body from the lidar scan.
    - `launch/navigation_launch.py` — Nav2 lifecycle bringup.
    - `launch/localization_launch.py` — AMCL on a saved map.
    - `launch/online_async_launch.py` — SLAM Toolbox online launch.
    - `launch/sim_bringup_launch.py` — composed simulation bringup (localization + navigation + RViz).
    - `maps/my_map.yaml` + `my_map.pgm` — a saved map of the walled world used by AMCL.
    - `rviz/nav2_view.rviz` — the pre-configured RViz layout for the navigation stack.
  - **Extended `openamrobot_description`** to add the front-facing RGB camera:
    - `camera_link` (`base_link + (0.35, 0, 0.20)` m, 4 × 8 × 4 cm box, 0.05 kg).
    - `camera_optical_frame` with the `rpy = (−π/2, 0, −π/2)` ROS optical convention required by `apriltag_ros::solvePnP`.
    - Gazebo `camera` sensor in `gazebo_control.xacro` (640×480 @ 30 Hz, FOV 1.047 rad, topic `/rgb_image`, `gz_frame_id: camera_optical_frame`).
  - **Built the docking scenario inside `openamrobot_gazebo/worlds/walled_world.sdf`**:
    - Inserted the AprilTag dock (`apriltag_dock` model with PBR `<albedo_map>`) on the inner face of the `+x` wall at world `(4.899, 0, 0.5)` yaw=π.
    - Shipped the `apriltag_36h11_id0.png` texture inside `worlds/`.
  - **Extended `openamrobot_gazebo/config/gz_bridge.yaml`** with the camera bridge entries (`/rgb_image`, `/camera/camera_info`).

### Docking pipeline and platform integration

- **Matthieu Vinet** — [@SHuttooo](https://github.com/SHuttooo)
  - **End-to-end integration of the docking pipeline into the platform-software repository.** The simulation, navigation, and robot-description packages were developed independently of the docking package; making them compose into a working end-to-end stack required substantial reconciliation work:
    - Migrated the 4-phase pipeline from the standalone `openamrobot-docking-main` repository into the integrated `openamr-platform-sw` structure.
    - Reconciled frame and topic naming conventions between the docking package and the description/simulation packages (`camera_optical_frame` vs `camera_rgb_optical_frame`, `/rgb_image` vs `/camera/image_raw`, `base_link` vs `base_footprint`).
    - Adapted the 4-phase sequencer parameters to the simulation's world coordinates (dock at map `(4.899, 0)`, approach yaw `0`, staging distance `1.5 m`).
    - Replaced the inline `apriltag_dock` model in `walled_world.sdf` (which had a hardcoded absolute texture path that did not resolve on any other machine) with a proper Gazebo model directory + `<include>` for portability across machines.
    - Bridged the gz `/camera_info` topic into ROS so `apriltag_ros::CameraSubscriber` could synchronise image + intrinsics (the upstream bridge only forwarded `/camera/camera_info`, which the detector's derived path could not find).
    - Restored the wheel-collision-cylinder vs DiffDrive-kinematic-radius mismatch required for ODE traction (without the 1 cm penetration the robot could not move under torque).
    - Extended `GZ_SIM_RESOURCE_PATH` in `gz_simulator.launch.py` so `model://apriltag_dock` resolves at world-load time.
    - Diagnosed and fixed the CycloneDDS / FastDDS issue that crashes `dock_trigger.py` silently on ROS 2 Jazzy.
    - Removed three duplicate / dead-code paths inherited from earlier iterations (`visual_servo_distance` parameter, `legacy/` docs, opennav_docking server invocation in the docking launch).
  - **4-phase docking sequencer** (`ros2/src/openamrobot_docking/scripts/dock_trigger.py`, ~977 lines), iterated from earlier 7-phase / auto-calibration designs to a final 4-phase pipeline:
    - Phase 1 — Nav2 `NavigateToPose` to the staging zone.
    - Phase 2 — camera-frame closed-loop centring scan + 40-sample running-average filter (true incremental mean for position, sign-aligned componentwise for the quaternion).
    - Phase 3 — in-place align spin to the running-average `perpendicular_yaw`.
    - Phase 4 — pure-pursuit on the perpendicular line through the averaged tag centre, with on-the-fly line refinement on every fresh detection; once detections stop arriving in the near field, the line is frozen and the robot follows it open-loop until `docking_distance`.
    - Bypasses `opennav_docking::SimpleChargingDock::controlled_approach` (curved trajectory) for a head-on, predictable approach.
    - Bypasses `nav2_behaviors::Spin` to avoid the costmap-collision false-positive triggered by the lidar glimpsing the robot's own body during fast rotation.
  - **TF → PoseStamped bridge** (`ros2/src/openamrobot_docking/src/detected_dock_pose_publisher.cpp`) republishing the chained `map → charging_dock_apriltag` TF as a 10 Hz `/detected_dock_pose`.
  - **Docking-layer launch** (`ros2/src/openamrobot_docking/launch/openamrobot_docking.launch.py`) composing `apriltag_sim.launch.yml` + `detected_dock_pose_publisher` + `dock_trigger.py` on top of an already-running Gazebo + Nav2 stack. Adds a small `ros_gz_bridge` instance for the gz `/camera_info` topic (image_transport's derived camera_info path).
  - **AprilTag detection assets**:
    - `launch/apriltag_sim.launch.yml` and `config/tags_36h11_sim.yaml`.
    - **Proper Gazebo model directory** `models/apriltag_dock/` with `model.config`, `model.sdf` (0.40 × 0.40 m PBR panel), and `materials/textures/apriltag_36h11_id0.png` — resolved via `GZ_SIM_RESOURCE_PATH + model://apriltag_dock`.
    - Replaced the previous inline AprilTag definition in `walled_world.sdf` (which had a hardcoded absolute path) with `<include><uri>model://apriltag_dock</uri></include>` for portability.
  - **CycloneDDS / FastDDS diagnostic** and workaround for the Python action-client crash bug on ROS 2 Jazzy.
  - **13 in-depth engineering documents** under `ros2/src/openamrobot_docking/docs/` (00 → 12): overview, quickstart, architecture, TF frames, AprilTag, parameters, camera calibration, reproduction checklist, sequencer walkthrough, troubleshooting, diagrams, changes from upstream, and the lessons-learned diary.

### Robot description — upstream geometry and meshes

- **Stephen Brawner** — original author of the SolidWorks-to-URDF Exporter ([sw_urdf_exporter](http://wiki.ros.org/sw_urdf_exporter)) used to generate the OpenAMRobot URDF and STL mesh set.
- **Niraj Dhakal** — original SolidWorks URDF export of the OpenAMRobot mobile base.
- **Raj Indulkar** ([@rajindulkar22](https://github.com/rajindulkar22)) — upstream packaging in [`openamrobot-simulation`](https://github.com/rajindulkar22/openamrobot-simulation) and the first ROS 2 description package skeleton.

Modifications applied in this revision (see *Simulation, navigation and robot description* and *Docking pipeline* above for credits):
- Camera link + optical frame added (Raj).
- DiffDrive plugin kinematic `wheel_radius` set to `0.10 m` while keeping the wheel collision cylinder at `0.11 m` so ODE has the 1 cm contact penetration required for traction.
- Lidar range tuned to the 10 × 10 m walled world (`0.15 m` near limit, `12 m` far limit).

---

## How to be listed here

If you submit a Pull Request that adds a substantive contribution (a new feature, a documented bug fix, a simulation asset, a significant doc rewrite), you may add yourself to the relevant section in the same PR. Trivial changes (typos, formatting) are recognized through GitHub commit history rather than in this file.

When adding yourself, follow the existing format:

```
- **Your Name** — [@your-handle](https://github.com/your-handle)
  - One-line summary of your contribution
  - Bullet points for specific files, features, or design decisions
```

Maintainers may reorganize, condense, or move entries to keep the file readable.

## Attribution policy

Contributors retain attribution for their work through GitHub history and through this file.

By contributing to this repository, contributors agree that their contributions may be used, modified, distributed, sublicensed, and commercialized under the repository license and contribution policy.

See:

- [`LICENSE`](LICENSE)
- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`NOTICE.md`](NOTICE.md)
