# Diagrams

Mermaid diagrams summarising the docking system. Use them in reports
or lectures.

## System block diagram (real robot, opennav_docking flow)

```mermaid
graph LR
  subgraph SENSORS[Perception]
    CAM[camera_ros]
    RECT[image_proc Rectify]
    TAG[apriltag_ros]
    CAM --> RECT --> TAG
  end

  subgraph TF[TF Tree]
    LOC["map → odom (AMCL)"]
    ODOM["odom → base_link (wheel odom)"]
    URDF["base_link → base_link → camera_link → camera_optical_frame (URDF static)"]
    TAGTF["camera_optical_frame → charging_dock_apriltag (apriltag_ros)"]
    LOC --> ODOM --> URDF --> TAGTF
  end

  subgraph DOCK[Docking]
    DET[detected_dock_pose_publisher]
    SERVER[opennav_docking::SimpleChargingDock]
    TRIG[dock_trigger.py]
  end

  TAG --> TAGTF
  TAGTF --> DET
  DET -->|/detected_dock_pose| SERVER
  TRIG -->|DockRobot action| SERVER
  SERVER --> NAV[Nav2 NavigateToPose]
  SERVER --> APP[graceful_controller approach]
```

## System block diagram (simulation, 4-phase sequencer)

```mermaid
graph LR
  subgraph GZ[Gazebo Harmonic]
    WORLD[docking_world.sdf]
    DOCK_SDF[apriltag_dock.sdf]
    PHYSICS[Physics + Camera + Lidar plugins]
  end

  XACRO[openamrobot_description xacro → URDF] -->|/robot_description| RSP[robot_state_publisher]
  XACRO -->|ros_gz_sim create at launch| GZ

  GZ --> BR[ros_gz_bridge]

  subgraph ROS[ROS 2 Jazzy]
    BR --> SCAN[/scan/]
    BR --> ODOM_T[/odom/]
    BR --> CAM_IMG[/camera/image_raw/]
    BR --> CAM_INFO[/camera/camera_info/]

    CAM_IMG --> APRIL[apriltag_ros]
    CAM_INFO --> APRIL

    SCAN --> SLAM[slam_toolbox]
    ODOM_T --> SLAM
    SLAM -->|map → odom| TFTREE

    RSP -->|static TFs| TFTREE[TF Tree]
    APRIL -->|camera_optical → tag| TFTREE

    TFTREE --> DPP[detected_dock_pose_publisher]
    DPP -->|/detected_dock_pose| TRIG[dock_trigger.py 4-phase]
    TFTREE -->|camera_optical → tag direct lookup| TRIG

    SCAN --> NAV2[Nav2 stack]
    SLAM --> NAV2
    TRIG -->|NavigateToPose phase 1| NAV2
    NAV2 --> SMO[velocity_smoother]
    TRIG -->|/cmd_vel_nav direct| SMO
    SMO --> CM[collision_monitor]
    CM -->|/cmd_vel| BR
  end
```

## TF tree (simulation)

```mermaid
graph TD
  MAP[map]
  ODOM[odom]
  BFP[base_link]
  BL[base_link]
  LIDAR[lidar_link]
  CAML[camera_link]
  CAMOPT[camera_optical_frame]
  TAG[charging_dock_apriltag]
  WHEELS[left_wheel / right_wheel / 4 caster + 4 caster-wheel links]

  MAP --> ODOM --> BFP --> BL
  BL --> LIDAR
  BL --> CAML --> CAMOPT --> TAG
  BL --> WHEELS
```

`map → odom` from `slam_toolbox`. `odom → base_link` from the
`DiffDrive` plugin. Everything below is static, from the
`openamrobot_description` xacro.

## 4-phase docking state machine

```mermaid
stateDiagram-v2
  [*] --> Idle
  Idle --> Phase1 : /dock_trigger=true

  Phase1 : NavigateToPose → staging zone (Nav2)
  Phase1 --> Phase2 : Nav2 succeeds
  Phase1 --> Idle : Nav2 fails

  Phase2 : Tag search (centring scan) + filter 40 samples
  Phase2 --> Phase3 : tag centred + N samples collected
  Phase2 --> Idle : scan timeout / no detections

  Phase3 : Spin in place to perpendicular yaw
  Phase3 --> Phase4a : yaw err < tol

  Phase4a : Line-tracking pure-pursuit (refines running average,\noutlier-rejected, distance-weighted)
  Phase4a --> Phase4b : line stabilised\n(samples ≥ N OR distance ≤ visual_servo_distance)
  Phase4a --> Idle : travel safety exceeded

  Phase4b : Visual servo (closed-loop on image-frame angle,\nrunning average frozen, low-pass smoothing)
  Phase4b --> Done : distance ≤ docking_distance
  Phase4b --> Idle : travel safety exceeded

  Done --> [*]
```

## Parameter dependency graph

```mermaid
graph TD
  TAGSIZE[Tag physical size] -->|must match| TAGCFG[apriltag_ros size param]
  CAMINTR[Camera intrinsics] -->|via /camera_info| SOLVEPNP[apriltag solvePnP]
  TAGCFG --> SOLVEPNP
  SOLVEPNP -->|TF camera_optical → tag| DET[detected_dock_pose_publisher]
  SOLVEPNP -->|TF camera_optical → tag direct| SCAN[Phase 2 centring scan]
  TFCHAIN[map→odom→base_link→base_link→camera] --> DET
  DET --> POSE[/detected_dock_pose/]
  POSE --> TRIG[dock_trigger.py 4-phase]
  STATIC[dock_pose_* in dock_trigger.yaml] --> TRIG
  STAGING[staging_distance] --> TRIG
  DOCKING[docking_distance] --> TRIG
  LINE[line_yaw_kp + line_lookahead_distance] --> TRIG
  FILTER[filter_num_samples] --> TRIG
  TRIG -->|rotate / advance / final align| OUTPUT[Robot final pose]
```

## Velocity command chain (simulation, Raj's setup)

```mermaid
graph LR
  RPP[Nav2 controller phase 1] -->|action result| ACT[NavigateToPose action server]
  ACT -->|internal cmd_vel chain| CM[collision_monitor / Nav2 internals]
  CM -->|/cmd_vel| BR
  TRIG[dock_trigger.py phases 2/3/4] -->|/cmd_vel direct| BR
  BR[ros_gz_bridge] -->|gz /cmd_vel| DD[DiffDrive plugin]
  DD -->|wheel torques| GZ[Gazebo physics]
```

> Phase 1 uses the Nav2 NavigateToPose action (its internal cmd_vel is published by Nav2's controller_server and routed through the Nav2 internals to `/cmd_vel`). Phases 2/3/4 publish directly on `/cmd_vel` because Raj's Nav2 stack does not run a `velocity_smoother` subscribed to `/cmd_vel_nav` — there's no smoothing layer to go through.

When debugging "robot doesn't move", check each topic's
`ros2 topic hz` to find which link is silent.

## Trajectory schematic (simulation, 4-phase, Raj's world)

```
                                     ↑ +y (map north)
                                     │
                                     │
   ██████████████████████████████████│██████████████████████████  ← East wall
                                     │                       ┌─┐    (x = 5)
                                     │                       │ │ tag at (4.899, 0)
                                     │                       └─┘
                                     │                        ▲
                                     │                       │ │   phase 4: line-tracking
                                     │                       │ │             (pure-pursuit, all the way
                                     │                       │ │              down to docking_distance)
   ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ── ── ── ── ── ── ── ── ●─┴── ← stop at (4.0, 0)
                                     │                                ~90 cm from tag
                                     │                       ↑
                                     │                       │
                                     │                       ●  ← staging at (3.40, 0) — Phase 1 stop
                                     │                       │     phase 2 scans + filter
                                     │                       │     phase 3 aligns
                                     │                       │
                                     ● ← robot spawn at (0, 0)  phase 1: Nav2 plans + tracks
   ──────────────────────────────────┼────────────────────────────────→ +x (map east)
                                     │
```

The robot starts at the map origin, navigates 3.4 m east to the staging zone, scans + filters there, spins to face the tag perpendicular (yaw = 0), then advances under line-tracking pure-pursuit until ~0.9 m from the dock. The perpendicular line is refined by every fresh AprilTag detection during the advance.

The line-tracking phase converges the lateral offset to zero while
advancing, then the final-align + straight-line phase guarantees a
clean perpendicular arrival at the dock.
