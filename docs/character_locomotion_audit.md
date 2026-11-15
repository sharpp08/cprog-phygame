# Character locomotion and environmental interaction audit

This document records the movement model implemented for the player and all
infected archetypes. World-space positions are measured in tile units; the
renderer projects them into the 2:1 isometric view.

## Character inventory and authored gait profiles

| Character | Locomotion identity | Gameplay speed (tiles/s) | Radius (tiles) |
|---|---|---:|---:|
| Player | Upright walk/run, weapon-stabilized right arm, counter-swinging support arm | 3.2 walk / 5.6 run | 0.42 |
| Regular infected | Forward shamble, asymmetric arm reach, moderate sway | 1.6 | 0.42 |
| Fast infected | Longer forward lean, higher knee lift, rapid directional response | 3.3 | 0.38 |
| Tank | Heavy torso, short stride, low acceleration and braking response | 0.9 | 0.60 |
| Crawler | Four-limb, low-to-ground alternating crawl | 1.2 | 0.36 |
| Exploder | Unsteady torso, uneven lurch and close-range explosive attack | 1.9 | 0.40 |
| Screamer | Extended reach and alert behavior, moderate movement response | 1.25 | 0.40 |
| Armored infected | Heavy, compact stride and high inertia | 1.05 | 0.55 |
| Stalker | Low-profile, quick redirection and stealth pursuit | 2.0 | 0.38 |

The exact gameplay values are centralized in `config.ZOMBIE_TYPES`; visual
stride, lift, arm swing, sway and body proportions are authored in
`engine/asset_manager.py`. These are deliberately separate: silhouette
parameters should not silently change collision size or world speed.

## Shared locomotion model

1. AI/navigation supplies a desired world-space direction.
2. Archetype-specific acceleration or braking response eases current velocity
   toward that target. Fast and stalker types redirect quickly; tanks and
   armored types retain momentum.
3. Circle-vs-grid collision resolves the proposed displacement.
4. Actual displacement divided by simulation time becomes the new velocity.
   Blocked axes lose momentum while an unobstructed axis can continue sliding.
5. Gait phase advances from resolved travel distance, not requested input.
   A character blocked against a wall therefore does not cycle its feet.
6. Facing follows the resolved isometric screen-space travel direction.

Projectile recoil is a decaying impulse along the vector from the projectile
impact through the zombie. Stumbles are short, timed speed interruptions with
a small lateral catch-step; their timers advance in seconds rather than being
tied to frame count.

## Gait model

Each upright leg uses a 60% stance / 40% swing cycle. The stance foot travels
back relative to the body while remaining at ground height. During swing it
returns forward with a smooth horizontal trajectory and a sinusoidal lift.
The opposite leg is offset by half a cycle, creating a brief double-support
interval. The crawler retains its separate quadrupedal limb pattern.

This is a stylized 2D sprite approximation, not a full skeletal simulation:
there is no joint torque solver, ground-reaction-force simulation, foot IK,
or motion-capture input. The phase proportions follow the broad human gait
cycle; the visual amplitudes remain game-art tuning values.

## Environmental interaction: current behavior and limits

- The grid collision model treats blocked tiles and map boundaries as solid;
  circle resolution permits wall sliding.
- A* uses eight-way movement and prevents diagonal corner cutting.
- Zombie separation adds local steering to reduce stacking, including a stable
  fallback direction when two enemies occupy exactly the same centre.
- Player footsteps and gunfire emit noise; zombie perception also accounts
  for line of sight, flashlight state, crouching and rain.
- Water is treated as impassable ground rather than a wading surface.
- Ground materials currently do not apply measured friction, slope, traction,
  mud drag or footstep-material audio. Those should only be introduced with
  explicit material rules and tests, not arbitrary per-frame speed multipliers.
- The current sprites are profile-oriented and flip horizontally. They do not
  provide full eight-direction skeletal poses, so diagonal and north/south
  travel are still a 2D projection compromise.

## Validation targets

The automated suite checks gait phase proportions, double support, smooth swing
lift, archetype-specific inertial turning, braking, collision feedback and
directional recoil. Visual playtesting is still required to tune the pixel
stride against the 2:1 projection at different camera zoom levels.
