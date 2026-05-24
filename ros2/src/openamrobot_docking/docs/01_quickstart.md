# Quickstart — From zero to docking

This document walks you from a fresh Ubuntu install to a working docking sequence in simulation. Follow it linearly the first time.

For background on **what** this package does, see [`00_overview.md`](00_overview.md) first.

---

## Prerequisites

### System

- **Ubuntu 24.04 (Noble)** — native install. WSL2 / macOS / Windows are not supported (Gazebo Harmonic needs a Linux display server).
- **ROS 2 Jazzy** installed system-wide ([install guide](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html)).
- **Gazebo Harmonic** (`gz-sim 8.x`) — comes with `ros-jazzy-ros-gz-sim`.
- A working **X11 or Wayland** display.

### ROS 2 packages (one-time)

```bash
sudo apt update
sudo apt install -y \
  ros-jazzy-nav2-bringup \
  ros-jazzy-nav2-lifecycle-manager \
  ros-jazzy-nav2-amcl \
  ros-jazzy-apriltag-ros \
  ros-jazzy-image-proc \
  ros-jazzy-tf2-ros \
  ros-jazzy-tf2-tools \
  ros-jazzy-tf2-geometry-msgs \
  ros-jazzy-rmw-cyclonedds-cpp \
  ros-jazzy-ros-gz-sim \
  ros-jazzy-ros-gz-bridge \
  ros-jazzy-ros-gz-image \
  ros-jazzy-robot-state-publisher \
  ros-jazzy-joint-state-publisher \
  ros-jazzy-laser-filters \
  ros-jazzy-rviz2 \
  ros-jazzy-topic-tools \
  python3-colcon-common-extensions
```

> ⚠️ **CycloneDDS is required.** The default Jazzy RMW (FastDDS) has a Python crash bug that makes `dock_trigger.py` exit silently when sending Nav2 action goals. Always export:
> ```bash
> export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
> ```
> Put this in `~/.bashrc` once and you're done.

---

## 2. Clone and build

```bash
cd ~/Downloads
git clone <fork-or-org-url>/openamr-platform-sw.git
cd openamr-platform-sw

source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

`colcon build` should finish in <10 s with all packages succeeded. If a package is missing dependencies, re-run the `apt install` above.

---

## 3. The 3-terminal launch sequence

The docking pipeline is **layered**. Each layer runs in its own terminal so you can restart any one without bringing the others down. In every terminal you open, first source the workspace:

```bash
source /opt/ros/jazzy/setup.bash
source ~/Downloads/openamr-platform-sw/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

(Or put these in a shell alias: `alias src-amr='source ...'`.)

### Terminal 1 — Gazebo + robot + ros↔gz bridge

```bash
ros2 launch openamrobot_gazebo gz_simulator.launch.py
```

This brings up Gazebo Harmonic with `walled_world.sdf` (a 10×10 m walled arena containing the AprilTag dock on the +x wall), spawns the robot at world `(0, 0, 0)`, and runs the ros↔gz bridge for `/clock`, `/odom`, `/tf`, `/cmd_vel`, `/scan`, `/rgb_image`, `/camera/camera_info`, `/imu`.

Wait for the Gazebo GUI window to open and the robot to be visible (~3 s).

### Terminal 2 — Nav2 + localization + RViz

```bash
ros2 launch openamrobot_nav2 sim_bringup_launch.py
```

This brings up Nav2's planner / controller / behavior server, AMCL on a saved map (`maps/my_map.yaml`), and the RViz layout. AMCL is initialised at map `(0, 0, 0)`, so **map ≡ world**.

Wait for RViz to show the robot localized on the map (you'll see the lidar scan overlaying the map walls, ~10 s).

### Terminal 3 — Docking layer (this package)

```bash
ros2 launch openamrobot_docking openamrobot_docking.launch.py
```

This adds three nodes on top:

- `apriltag_ros::apriltag_node` (in the `/apriltag` namespace) subscribing to `/rgb_image` + `/camera_info`
- `detected_dock_pose_publisher` (C++) publishing `/detected_dock_pose` at 10 Hz
- `dock_trigger.py` (Python, the 4-phase sequencer) waiting on `/dock_trigger`
- A small `camera_info_bridge` `ros_gz_bridge` instance bridging `gz /camera_info → ROS /camera_info` (image_transport derives the camera_info topic from the image topic and looks for the root-level `/camera_info`, which the upstream bridge doesn't provide directly)

Wait for the `[dock_trigger.py-N] [INFO] Dock trigger ready on 'dock_trigger'` log line.

---

## 4. Trigger the docking

In any sourced terminal (or from the UI):

```bash
ros2 topic pub /dock_trigger std_msgs/msg/Bool "{data: true}" --once
```

Watch the **Terminal 3** logs. You should see this sequence:

```
── Phase 1/4: NavigateToPose → staging zone
   → staging (3.40, 0.00, yaw=0.00)
   ... (Nav2 controller messages)
   Goal succeeded
── Phase 2/4: tag search + initial filter (40 samples)
   scanning to centre tag in camera (tolerance ±2.0°, need 5 consecutive frames)
   tag centred in camera (image_angle=±X.X°, consecutive=5)
   tag at (≈4.9, ≈0) after 40 samples
── Phase 3/4: ALIGN (spin to perpendicular yaw 0.000)
   spin done: yaw=±0.02 target=0.00 err=0.02
── Phase 4/4: line-tracking advance to 0.90m
   start d_to_tag=2.19m, forward to travel ≈ 1.29m
   ... (the robot advances; logs once if tag is lost in the near field)
   reached: d_to_tag=0.89m, lateral=±X.Xcm (N samples averaged, M during Phase 4)
   Phase 4 done.
```

End state: the robot is **stopped ~0.9 m in front of the tag, perpendicular to the tag plane**.

---

## 5. Diagnostics if something doesn't behave

| Symptom | Quick check |
|---|---|
| Robot stays at the staging point | `ros2 topic hz /apriltag/detections` — is it >0 Hz? Look for `id: 0` in `ros2 topic echo /apriltag/detections` |
| `tag never detected during scan` | `ros2 run rqt_image_view rqt_image_view /rgb_image` — is the AprilTag pattern visible (black/white) or uniformly grey? |
| Robot moves in RViz but not in Gazebo | `ros2 topic info /cmd_vel` — does the bridge subscribe? |
| Phase 4 finishes but robot stopped 2 m short | Tag size mismatch — check `config/tags_36h11_sim.yaml` `size:` matches the panel face size (`models/apriltag_dock/model.sdf`) |

Full troubleshooting matrix in [`09_troubleshooting.md`](09_troubleshooting.md).

---

## 6. Where to go next

- [`05_parameters.md`](05_parameters.md) — every YAML knob explained
- [`08_sequencer_4phase.md`](08_sequencer_4phase.md) — phase-by-phase walkthrough of `dock_trigger.py`
- [`07_reproduce_results.md`](07_reproduce_results.md) — exact reproduction checklist
- [`02_architecture.md`](02_architecture.md) — node graph, lifecycle, topics

---

## Real-robot port (high level)

To deploy the same pipeline on hardware, the changes from this quickstart are:

1. Stop using `openamrobot_gazebo` / `sim_bringup_launch.py`. Instead, launch:
   - your camera driver (e.g. `camera_ros`) publishing `/camera/image_raw` + `/camera/camera_info`
   - `image_proc` for rectification, publishing `/camera/image_rect`
   - your lidar driver publishing `/scan`
   - your motor controller driver publishing `/odom` + `/tf (odom → base_link)` and consuming `/cmd_vel`
   - `robot_state_publisher` with your robot URDF
   - Nav2 with AMCL on a pre-built map of the real environment
2. Use `apriltag.launch.yml` (real-robot variant) instead of `apriltag_sim.launch.yml`. It expects rectified images.
3. Update `config/dock_trigger.yaml`:
   - `dock_pose_x`, `dock_pose_y`, `dock_pose_yaw` = the measured real-world dock pose in the map frame
   - All other parameters can stay (the 4-phase logic is hardware-agnostic)
4. Print a physical AprilTag 36h11 ID 0 of measured size; update `tags_36h11.yaml` `size:` to match (in metres, **side of the outer black square**).
5. Calibrate the camera and ship the intrinsics — see [`06_camera_calibration.md`](06_camera_calibration.md).

The Python sequencer is unchanged.
