# OpenAMR Platform Software

ROS 2 Jazzy software stack for the **OpenAMRobot** mobile robot platform: robot description, Gazebo Harmonic simulation, Nav2 navigation, AprilTag-based autodocking.

> 📦 **Status: experimental.** Tuned end-to-end in the docking simulation. Real-robot bringup (drivers, control, hardware integration) is in progress and will land under the placeholder packages described below.

---

## Quickstart — docking simulation

```bash
# One-time system setup
sudo apt install -y \
  ros-jazzy-nav2-bringup ros-jazzy-nav2-amcl \
  ros-jazzy-apriltag-ros ros-jazzy-image-proc \
  ros-jazzy-ros-gz-sim ros-jazzy-ros-gz-bridge ros-jazzy-ros-gz-image \
  ros-jazzy-rmw-cyclonedds-cpp ros-jazzy-topic-tools \
  ros-jazzy-laser-filters ros-jazzy-slam-toolbox
echo 'export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp' >> ~/.bashrc
source ~/.bashrc

# Clone + build
git clone https://github.com/openAMRobot/openamr-platform-sw.git
cd openamr-platform-sw/ros2          # the colcon workspace is ros2/ (it contains src/)
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install        # creates build/ install/ log/ inside ros2/
source install/setup.bash
```

Sourcing does **not** carry over between terminals, so in **every** new terminal run these three lines first (from `ros2/`, the workspace root):

```bash
source /opt/ros/jazzy/setup.bash
source install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

**Then launch everything with one command:**

```bash
ros2 launch openamrobot_docking bringup_sim.launch.py
```

This brings up the three layers in order — Gazebo, then Nav2 (+8 s), then the docking pipeline (+16 s). On a slower machine, increase the gaps: `... bringup_sim.launch.py nav2_delay:=10 docking_delay:=22`.

<details>
<summary>Or run the three layers separately, one per terminal (handy for tuning/restarting one layer)</summary>

```bash
# Terminal 1 — Gazebo + robot + bridge
ros2 launch openamrobot_gazebo gz_simulator.launch.py

# Terminal 2 — Nav2 + AMCL + map + RViz
ros2 launch openamrobot_nav2 sim_bringup_launch.py

# Terminal 3 — docking pipeline (this is where the magic happens)
ros2 launch openamrobot_docking openamrobot_docking.launch.py
```

> If Terminal 3 fails with `package 'openamrobot_docking' not found`, you forgot the `source install/setup.bash` in that terminal.
</details>

Wait ~10 s for Nav2 to localize, then drive the robot from any sourced terminal:

```bash
ros2 topic pub /dock_trigger  std_msgs/msg/Bool "{data: true}" --once   # dock
ros2 topic pub /undock_robot  std_msgs/msg/Bool "{data: true}" --once   # undock: reverse 1.5 m + spin 180°
```

You can also send a navigation goal (RViz "2D Goal Pose", or a `PoseStamped` on `/goal_pose`): if the robot is docked it undocks first, then drives to the goal.

The robot navigates to a staging zone, scans for the AprilTag, aligns perpendicular to it, then drives onto the dock. End state: ~90 cm from the tag, perpendicular.

For a step-by-step walkthrough including diagnostics: [`ros2/src/openamrobot_docking/docs/01_quickstart.md`](ros2/src/openamrobot_docking/docs/01_quickstart.md).

---

## Why CycloneDDS

The default Jazzy RMW (FastDDS) has a Python-side crash bug that makes `dock_trigger.py` exit silently when sending Nav2 action goals. Always export:

```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

Put it in your `~/.bashrc` once and forget about it.

---

## Repository layout

```
openamr-platform-sw/
├── ros2/
│   └── src/
│       ├── openamrobot_description/    URDF + meshes + Gazebo sensor plugin tags
│       ├── openamrobot_gazebo/         Gazebo Harmonic bringup + ros↔gz bridge + worlds
│       ├── openamrobot_nav2/           Nav2 stack + AMCL + map + RViz layout
│       ├── openamrobot_docking/        AprilTag + 4-phase docking sequencer + dock model
│       ├── openamrobot_bringup/        (placeholder) top-level launch compositions
│       ├── openamrobot_control/        (placeholder) ros2_control + low-level control
│       ├── openamrobot_drivers/        (placeholder) hardware drivers (lidar, camera, IMU…)
│       └── openamrobot_perception/     (placeholder) perception modules beyond docking
│
├── config/                              (reserved) product-level configuration slots
├── simulation/                          (reserved) cross-package simulation assets
├── scripts/                             (reserved) operator utilities
├── tools/                               (reserved) developer tools
├── docs/                                pointer docs (engineering docs live next to code)
│
├── README.md                            you are here
├── LICENSE                              MIT
├── CONTRIBUTING.md                      how to send PRs
├── SECURITY.md                          private disclosure
├── NOTICE.md                            third-party attributions
├── AUTHORS.md                           contributors
└── CHANGELOG.md                         history of significant changes
```

The four `(placeholder)` packages exist as folder + `README.md` markers; they don't yet build. They reserve the architectural slot for upcoming work.

---

## Package responsibilities

Strict separation of concerns:

| Package | Owns | Does NOT own |
|---|---|---|
| `openamrobot_description` | Robot URDF, meshes, mass/inertia, Gazebo sensor plugin tags | Worlds, navigation, docking |
| `openamrobot_gazebo` | Simulator bringup, ros↔gz bridge, generic + scenario worlds | Robot model, navigation, docking |
| `openamrobot_nav2` | Nav2 params, AMCL on a saved map, RViz layout | Gazebo, docking |
| `openamrobot_docking` | AprilTag detection, dock model, 4-phase sequencer | Robot, simulator, navigation stack |

Each package may **reference** sibling packages at launch composition time (`FindPackageShare` + `IncludeLaunchDescription`), but **must not duplicate** their files.

---

## Architecture — the `/cmd_vel` flow

In the docking simulation, six links chain the trigger to the wheels:

```
dock_trigger.py / Nav2 controller       ──>  /cmd_vel
                                              │
                                              ▼
                          ros_gz_bridge  ──>  gz /cmd_vel
                                              │
                                              ▼
                          DiffDrive plugin    (Gazebo, applies torques to joints)
                                              │
                                              ▼
                          ODE contact solver  (friction, the robot moves)
                                              │
                                              ▼
                          gz odom + tf  ──>   /odom, /tf  (via bridge)
                                              │
                                              ▼
                          robot_state_publisher fills in base_link → camera_optical_frame → ...
```

If any link breaks, the robot stops moving. The most common failure mode is the bridge not forwarding `/cmd_vel` (verify with `ros2 topic info /cmd_vel`).

The full TF chain on top of this is in [`ros2/src/openamrobot_docking/docs/03_tf_frames.md`](ros2/src/openamrobot_docking/docs/03_tf_frames.md).

---

## Per-package documentation

Each package ships its own README. Engineering docs live under [`ros2/src/openamrobot_docking/docs/`](ros2/src/openamrobot_docking/docs/) (13 numbered files: overview, quickstart, architecture, TF chain, AprilTag setup, parameters, troubleshooting, lessons learned).

| Package | Read its README at |
|---|---|
| `openamrobot_description` | [`ros2/src/openamrobot_description/README.md`](ros2/src/openamrobot_description/README.md) |
| `openamrobot_gazebo` | [`ros2/src/openamrobot_gazebo/README.md`](ros2/src/openamrobot_gazebo/README.md) |
| `openamrobot_nav2` | [`ros2/src/openamrobot_nav2/README.md`](ros2/src/openamrobot_nav2/README.md) |
| `openamrobot_docking` | [`ros2/src/openamrobot_docking/README.md`](ros2/src/openamrobot_docking/README.md) |

For the docking pipeline specifically, start with [`docs/01_quickstart.md`](ros2/src/openamrobot_docking/docs/01_quickstart.md).

---

## Related repositories (organisation-level)

This repo is the **software** side of the OpenAMRobot platform. Sister repositories cover the rest of the stack:

| Repo | Contents |
|---|---|
| `openamr-platform-hw` | Mechanical CAD, BOM, wiring, electrical |
| `openamr-platform-fw` | Embedded firmware (STM32, Teensy, ESP32) |
| `openamrobot-docs` | Organisation-wide user-facing documentation |
| `openamrobot-interfaces` | Shared ROS 2 messages, services, actions |
| `openamrobot-comm` | Shared communication contracts |
| `openamrobot-ui` | Operator interface (publishes `/dock_trigger` on docking) |

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

Key rule: a contribution should modify **only the package or directory related to the task**.

For example, an autodocking contribution should normally modify only:

```
ros2/src/openamrobot_docking/
```

If a docking change *requires* a touch in `openamrobot_gazebo` (e.g. to fix a regression that prevents the docking from working), describe the necessity in the PR and consider opening a separate PR against the sibling package.

---

## Community and discussions

Architecture, roadmap, and collaboration: <https://github.com/orgs/openAMRobot/discussions>

---

## Safety notice

This repository may affect real-robot behaviour. Users are responsible for validating:

- robot safety (E-stop, watchdog, fault handling)
- navigation behaviour
- docking behaviour
- motor control behaviour
- sensor integration
- deployment suitability
- regulatory compliance

This software is provided for research, education, and development.

---

## License

MIT. See [`LICENSE`](LICENSE).

Attribution for bundled third-party assets (AprilTag panel texture, etc.) is in [`NOTICE.md`](NOTICE.md).
