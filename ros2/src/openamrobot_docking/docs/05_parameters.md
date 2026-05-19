# Parameters reference

Every YAML knob that `openamrobot_docking` reads, grouped by config file. Defaults are the values shipped in this package and tuned for the simulation.

The YAML files this doc covers:

```
config/
├── dock_trigger.yaml              ← 4-phase sequencer (the bulk of this doc)
├── tags_36h11_sim.yaml            ← AprilTag detector (simulation)
└── docking_pose_publisher.yaml    ← TF → PoseStamped publisher
```

---

## `config/dock_trigger.yaml` — the 4-phase sequencer

Read by `scripts/dock_trigger.py`. Every parameter is also commented in-place in the YAML.

### Trigger plumbing

| Parameter | Default | Meaning |
|---|---|---|
| `trigger_topic` | `dock_trigger` | Bool topic that fires the sequence. `true` = dock. |
| `undock_on_false` | `false` | If `true`, `Bool false` triggers undocking (calls `UndockRobot`). Off by default — the 4-phase pipeline doesn't yet implement undock. |

### Dock pose in the `map` frame

| Parameter | Default | Meaning |
|---|---|---|
| `dock_pose_x` | `4.899` | Dock x in the **map** frame |
| `dock_pose_y` | `0.0` | Dock y in the **map** frame |
| `dock_pose_yaw` | `0.0` | **Approach yaw** — the heading the robot has when docked (facing the tag) |

> The simulation places the AprilTag panel at world `(4.899, 0, 0.5)` with the tag plane normal pointing `-x`. AMCL is initialised at map `(0, 0, 0)` = world `(0, 0, 0)`, so map ≡ world for this scenario. The robot approaches from `-x` heading `+x` → approach yaw = `0`.

### Phase 1 — Nav2 staging

| Parameter | Default | Meaning |
|---|---|---|
| `staging_distance` | `1.5` | Distance (m) in front of the dock at which Nav2 stops. With a 0.40 m tag and 1.047 rad camera FOV, 1.5 m gives ~120 px of tag in the image — comfortable for sub-pixel solvePnP. |
| `staging_hold_seconds` | `1.0` | Quiet time at staging before the tag scan begins (velocity decay + image stabilisation). |

### Phase 2 — tag search + initial filter

| Parameter | Default | Meaning |
|---|---|---|
| `scan_rotation_speed` | `0.3` | Open-loop scan rotation rate (rad/s) and clamp on the centring P-loop. |
| `scan_consecutive_target` | `5` | Centred-frame count required in a row before the scan exits. |
| `scan_centring_tolerance` | `0.035` | Tag must be within this many rad (~2°) of image centre to count as centred. |
| `scan_centring_kp` | `1.0` | P-gain on the camera-frame image angle during the closed-loop centring. |
| `detection_topic` | `/detected_dock_pose` | PoseStamped topic from `detected_dock_pose_publisher`. |
| `detection_max_age` | `1.5` | Drop detections older than this (s) — staleness guard. |
| `filter_num_samples` | `40` | Number of fresh detections folded into the running-average tag pose during phase 2. |
| `filter_max_collect_time` | `6.0` | Max seconds spent collecting samples. 40 samples at 10 Hz needs ≥ 4 s; the extra 2 s is margin for drops. |

### Phase 3 — align spin

| Parameter | Default | Meaning |
|---|---|---|
| `spin_kp` | `1.5` | Angular P gain for the in-place spin to `perpendicular_yaw`. |
| `spin_max_omega` | `0.3` | Clamp on the spin angular velocity (rad/s). |
| `spin_yaw_tolerance` | `0.02` | Exit when `\|yaw_err\| < this` (~1.1°). |

### Phase 4 — line-tracking advance

| Parameter | Default | Meaning |
|---|---|---|
| `docking_distance` | `0.9` | Final distance (m) from the running-average tag at which Phase 4 stops. The robot ends ~90 cm in front of the tag, perpendicular. |
| `drive_speed` | `0.05` | Forward speed (m/s) during Phase 4, linearly tapered inside `2 × docking_distance` so the robot eases into the final stop. |
| `line_yaw_kp` | `2.5` | Yaw P gain: `omega = line_yaw_kp · (desired_yaw − robot_yaw)`. |
| `line_lookahead_distance` | `0.3` | Pure-pursuit lookahead. `desired_yaw = perp_yaw − atan2(lateral, lookahead)`. Smaller = more aggressive lateral convergence (steeper desired heading at the same offset). |
| `drive_yaw_max_omega` | `0.3` | Clamp on omega during Phase 4 (rad/s). |
| `drive_rate_hz` | `20.0` | Control loop rate for phases 2/3/4. |
| `cmd_vel_topic` | `/cmd_vel` | Topic where dock_trigger publishes `Twist` during phases 2/3/4. Published directly on `/cmd_vel` because Raj's Nav2 doesn't run a `velocity_smoother` subscribed to `/cmd_vel_nav`. |

### Phase 4 — robust running-average update

The running-average tag pose is refined during Phase 4 by each fresh detection. Two safeguards make this update **robust against noisy near-field detections** (the camera sits slightly above the tag, so as the robot approaches the tag drifts toward the bottom of the FOV and solvePnP becomes noisier):

| Parameter | Default | Meaning |
|---|---|---|
| `refinement_outlier_threshold` | `0.30` | A new detection that lands more than this many metres from the current running-average position (XY) is SKIPPED — almost certainly a single-frame solvePnP glitch. Typical legitimate jitter is ~5 cm, so 0.30 m is a generous cutoff. Set to 0 to disable. |
| `refinement_weight_min` | `0.1` | Lower bound on the per-sample weight in the distance-weighted mean. |
| `refinement_weight_full_distance` | `1.5` | Distance (m) at which a sample contributes full weight (=1.0). Closer samples have weight = `clamp(distance / full_distance, weight_min, 1.0)`. |

The weighted mean keeps **all** accepted detections in the running average but lets clean far-field samples dominate over noisier near-field ones. At 1.5 m a sample has weight 1.0; at 0.75 m it has weight 0.5; at 0.15 m it's clamped to the 0.1 floor.

### Phase 4 — visual-servo handover

Once the line is stable enough, Phase 4 hands the heading controller over from map-frame line-tracking to **camera-frame visual servoing** (closed-loop on the image-frame angle to the tag). This last leg of the approach doesn't depend on the noisy near-field solvePnP map-frame outputs.

| Parameter | Default | Meaning |
|---|---|---|
| `line_stabilization_samples` | `25` | Number of accepted Phase-4 refinements after which the line is declared "stabilised" and the visual servo takes over. Set to 0 to disable (only the distance trigger remains). |
| `visual_servo_distance` | `1.0` | Distance (m) below which the visual servo takes over **regardless** of refinement count — failsafe for the case where outlier rejection kills most samples. Set to 0 to disable (only the count trigger remains). |
| `visual_servo_kp` | `0.6` | P gain on the image-frame angle: `omega = −visual_servo_kp · atan2(X_optical, Z_optical)`. |
| `visual_servo_filter_alpha` | `0.2` | Low-pass smoothing on the image-frame angle (rejects single-frame solvePnP spikes). `0.0 < alpha ≤ 1.0`. Lower = more smoothing, slower response. |

The handover trigger is **first-of**: whichever of `line_stabilization_samples` or `visual_servo_distance` happens first. From that point the running-average is frozen and `omega` comes from the live camera-frame angle.

### Tuning intuitions

- **Robot oscillates near the line** → increase `line_lookahead_distance` (smoother heading) or decrease `line_yaw_kp`.
- **Robot converges too slowly to the line** → decrease `line_lookahead_distance` (more aggressive) or increase `line_yaw_kp` (watch `drive_yaw_max_omega` saturation).
- **Visual servo wobbles** → lower `visual_servo_kp` (e.g. 0.4) or lower `visual_servo_filter_alpha` (e.g. 0.1).
- **Visual servo is too sluggish** → raise `visual_servo_kp` or raise `visual_servo_filter_alpha`.
- **One bad detection visibly shifts the line** → tighten `refinement_outlier_threshold` (e.g. 0.20 m).
- **Far samples don't dominate enough** → raise `refinement_weight_full_distance` (e.g. 2.0).
- **Handover happens too late, robot already misaligned** → lower `line_stabilization_samples` (e.g. 15) or raise `visual_servo_distance`.
- **Handover happens too early, line wasn't established** → raise `line_stabilization_samples` (e.g. 35).
- **Robot overshoots the staging zone** → softer linear decel in `velocity_smoother`, or reduce `staging_distance`.
- **Phase 2 timeouts** → either the tag isn't in the camera, or the detector isn't getting `/camera_info` (see [`09_troubleshooting.md`](09_troubleshooting.md)).

---

## `config/tags_36h11_sim.yaml` — AprilTag detector (simulation)

| Parameter | Default | Meaning |
|---|---|---|
| `family` | `36h11` | Tag family. |
| `size` | `0.40` | **Tag side length** in metres — measure the panel face in `models/apriltag_dock/model.sdf`. Must match or solvePnP returns wrong distances. |
| `max_hamming` | `0` | Bit-error tolerance (0 = strict). |
| `image_transport` | `raw` | Sim camera publishes raw uncompressed, no rectification needed. |
| `detector.threads` | `2` | CPU threads for detection. |
| `detector.decimate` | `1.0` | Image down-sampling factor. 1.0 = no decimation (camera is already 640×480). |
| `detector.blur` | `0.0` | Pre-detection Gaussian blur σ. |
| `detector.refine` | `True` | Sub-pixel corner refinement. |
| `detector.sharpening` | `0.25` | Pre-detection sharpening. |
| `pose_estimation_method` | `pnp` | Use solvePnP for the tag → camera transform. |
| `tag.ids` | `[0]` | Tag IDs to detect (filter — others ignored). |
| `tag.frames` | `[charging_dock_apriltag]` | TF child frame name for each tag. Must match `docking_pose_publisher.yaml` `child_frame`. |

---

## `config/docking_pose_publisher.yaml` — TF → PoseStamped bridge

| Parameter | Default | Meaning |
|---|---|---|
| `parent_frame` | `map` | The frame in which the dock pose is published. |
| `child_frame` | `charging_dock_apriltag` | The tag's TF frame. Must match `tag.frames` in the AprilTag YAML. |
| `output_topic` | `detected_dock_pose` | PoseStamped output. Must match `detection_topic` in `dock_trigger.yaml`. |
| `publish_rate` | `10.0` | Hz. |

---

## Where these parameters interact

```
config/dock_trigger.yaml
  dock_pose_x/y/yaw  ──────  ground truth: the AprilTag panel pose in walled_world.sdf

  detection_topic  ─────────  Must equal  ────────  docking_pose_publisher.yaml output_topic

  scan_centring_tolerance  ─  Tighter than  ──────  Phase 4's line_lookahead/yaw — otherwise
                                                     Phase 4 wobbles around the line

config/tags_36h11_sim.yaml
  size  ────────────────────  Must equal  ────────  models/apriltag_dock/model.sdf
                                                     <box><size>0.001 0.40 0.40</size> face

  tag.frames[0]  ───────────  Must equal  ────────  docking_pose_publisher.yaml child_frame
                                                     and dock_trigger.py's TF lookup
                                                     target ('charging_dock_apriltag')

URDF (openamrobot_description)
  camera_optical_frame  ────  Used by  ──────────  apriltag_ros (tag pose published here)
                                 and by  ─────────  detected_dock_pose_publisher (lookup
                                                     base for the map-frame transform)
                                 and by  ─────────  dock_trigger.py (camera-frame centring)

  base_link             ────  Used by  ──────────  dock_trigger.py (map → base_link lookup
                                                     for the robot's current pose)
```

When you change one value, update the matching consumer.

---

## Real-robot deployment

To port to a real robot:

1. Use `tags_36h11.yaml` instead of `tags_36h11_sim.yaml`. Differences:
   - `size` set to **your measured printed tag side** (in metres, side of the outer black square — typically 0.05–0.20 m for indoor robots).
   - `decimate` may need to be `2.0` or higher to keep the detector real-time on the robot's CPU.
   - `image_transport: compressed` (typical) — `apriltag.launch.yml` includes `image_proc` rectification.
2. Set `dock_pose_x/y/yaw` to the **measured map-frame pose** of your physical dock.
3. All other 4-phase parameters carry over unchanged — the pipeline is hardware-agnostic.
