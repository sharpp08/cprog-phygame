"""Pure-Python movement maths shared by the player and the camera.

Nothing here imports pygame, so the physics can be unit-tested headlessly.

* :func:`step_velocity` - acceleration-limited velocity with separate
  acceleration, braking, friction and lateral grip (replaces a plain lerp
  towards the target velocity, which gave maximum acceleration on frame one).
* :class:`Surface` / :func:`surface_for` - per-terrain traction and noise.
* :func:`cycles_per_tile` - gait cycles per tile of travel, continuous in
  speed so the stride lengthens smoothly between walking and sprinting.
* :func:`smooth_damp` - critically damped follow used by the camera.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Tuple

import config


def clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


# ---------------------------------------------------------------------------
# Velocity integration
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MoveProfile:
    """Tuning for one physics step (speeds in tiles/s, rates in tiles/s^2)."""

    max_speed: float
    accel: float
    brake: float            # input opposes current velocity
    friction: float         # no input: constant deceleration
    grip: float             # removal rate of sideways velocity while turning
    accel_high: float = -1.0   # acceleration above ``knee`` (<0: same as accel)
    knee: float = 0.0          # speed where accel_high takes over (0: off)
    overspeed_decel: float = 12.0   # slowing from sprint towards a lower cap


def step_velocity(vx: float, vy: float, wx: float, wy: float,
                  p: MoveProfile, dt: float, ramp: float = 1.0,
                  control: float = 1.0) -> Tuple[float, float]:
    """Advance velocity by ``dt`` towards the unit input direction (wx, wy).

    ``ramp`` scales forward acceleration only (jerk limiting at the start of
    a move).  ``control`` scales every force the player can apply, so a
    stagger leaves momentum mostly intact while input barely steers it.
    """
    if wx == 0.0 and wy == 0.0:
        speed = math.hypot(vx, vy)
        if speed <= 1e-9:
            return 0.0, 0.0
        k = max(0.0, speed - p.friction * control * dt) / speed
        return vx * k, vy * k

    along = vx * wx + vy * wy
    lx, ly = vx - along * wx, vy - along * wy
    lat = math.hypot(lx, ly)
    if lat > 1e-9:
        cut = min(lat, p.grip * control * dt)
        lx -= lx / lat * cut
        ly -= ly / lat * cut

    if along < 0.0:
        along += p.brake * control * dt
    elif along > p.max_speed:
        along = max(p.max_speed, along - p.overspeed_decel * control * dt)
    else:
        a = p.accel
        if p.accel_high >= 0.0 and p.knee > 0.0 and along >= p.knee:
            a = p.accel_high
        a *= 1.0 - 0.6 * along / max(p.max_speed, 1e-6)   # taper near the cap
        along = min(p.max_speed, along + a * ramp * control * dt)
    return along * wx + lx, along * wy + ly


def aim_speed_multiplier(wx: float, wy: float, ax: float, ay: float) -> float:
    """Speed factor from movement direction relative to aim.

    Forward 1.0, strafing ~0.86, backpedalling ~0.72.  No aim, no penalty.
    """
    if math.hypot(ax, ay) < 0.04:
        return 1.0
    rel = clamp(wx * ax + wy * ay, -1.0, 1.0)
    return config.PLAYER_AIM_SPEED_BASE + config.PLAYER_AIM_SPEED_GAIN * rel


# ---------------------------------------------------------------------------
# Surfaces
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Surface:
    """Traction and noise of the ground under the player (1.0 = neutral)."""

    speed: float = 1.0
    accel: float = 1.0
    grip: float = 1.0
    noise: float = 1.0


NEUTRAL = Surface()

SURFACES = {
    config.T_GRASS: Surface(0.96, 0.95, 0.90, 0.90),
    config.T_DIRT: Surface(1.00, 1.00, 1.00, 0.95),
    config.T_PATH: Surface(1.00, 1.00, 1.00, 1.00),
    config.T_BRIDGE: Surface(1.00, 1.00, 1.05, 1.35),   # hollow planks
    config.T_ROCK: Surface(0.92, 0.90, 0.85, 1.20),
    config.T_LILY: Surface(0.80, 0.70, 0.50, 1.00),
}


def surface_for(tile_type: int, rain: float = 0.0) -> Surface:
    """Surface for a terrain tile type; heavy rain lowers traction."""
    s = SURFACES.get(tile_type, NEUTRAL)
    if rain > 0.3:
        wet = 1.0 - 0.15 * clamp((rain - 0.3) / 0.7, 0.0, 1.0)
        s = replace(s, grip=s.grip * wet)
    return s


# ---------------------------------------------------------------------------
# Gait
# ---------------------------------------------------------------------------
def cycles_per_tile(speed: float) -> float:
    """Gait cycles per tile travelled, smooth between walk and sprint.

    The endpoints keep the stride lengths the baked eight-frame cycle was
    authored for, so feet stay planted visually; only the blend between them
    is new (it used to switch abruptly with the ``running`` flag).
    """
    walk, run = config.PLAYER_WALK_SPEED, config.PLAYER_RUN_SPEED
    t = clamp((speed - walk) / max(run - walk, 1e-6), 0.0, 1.0)
    t = t * t * (3.0 - 2.0 * t)
    return (config.PLAYER_GAIT_CYCLES_WALK
            + (config.PLAYER_GAIT_CYCLES_RUN
               - config.PLAYER_GAIT_CYCLES_WALK) * t)


# ---------------------------------------------------------------------------
# Camera spring
# ---------------------------------------------------------------------------
def smooth_damp(cur: float, target: float, vel: float,
                smooth_time: float, dt: float) -> Tuple[float, float]:
    """Critically damped spring (no overshoot, stable for any dt)."""
    smooth_time = max(smooth_time, 1e-4)
    omega = 2.0 / smooth_time
    x = omega * dt
    e = 1.0 / (1.0 + x + 0.48 * x * x + 0.235 * x * x * x)
    change = cur - target
    temp = (vel + omega * change) * dt
    new_vel = (vel - omega * temp) * e
    return target + (change + temp) * e, new_vel
