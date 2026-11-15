"""Headless tests for the movement physics (no pygame required)."""
import math
import unittest

import config
from engine.camera import Camera
from engine.movement import (MoveProfile, aim_speed_multiplier,
                             cycles_per_tile, smooth_damp, step_velocity,
                             surface_for)
from entities.player import Player
from entities.weapon import Weapon
from systems.survival import SurvivalSystem

DT = 1.0 / 60.0


class OpenGrid:
    def move_circle(self, pos, delta, radius):
        return pos[0] + delta[0], pos[1] + delta[1]


class BlockedGrid:
    def move_circle(self, pos, delta, radius):
        return pos


class WallGrid:
    """A solid wall at x = limit (the circle may not pass it)."""

    def __init__(self, limit):
        self.limit = limit

    def move_circle(self, pos, delta, radius):
        return min(pos[0] + delta[0], self.limit), pos[1] + delta[1]


def simulate(player, seconds, mv=(1.0, 0.0), running=False, dt=DT,
             grid=None, **kw):
    grid = grid or OpenGrid()
    t = 0.0
    while t < seconds - 1e-9:
        player.apply_movement(mv, running, dt, grid, **kw)
        t += dt
    return player


def time_to_speed(player, frac, mv=(1.0, 0.0), running=False):
    target = (config.PLAYER_RUN_SPEED if running else
              config.PLAYER_WALK_SPEED) * frac
    t = 0.0
    while t < 5.0:
        player.apply_movement(mv, running, DT, OpenGrid())
        t += DT
        if player.actual_speed >= target:
            return t
    return None


def stop_distance(player):
    x0 = player.x
    for _ in range(240):
        player.apply_movement((0.0, 0.0), False, DT, OpenGrid())
    return player.x - x0


class TestVelocityModel(unittest.TestCase):
    def test_acceleration_is_limited_not_instant(self):
        p = Player(2.0, 2.0)
        p.apply_movement((1.0, 0.0), False, DT, OpenGrid())
        # the old exponential response reached ~0.8 tiles/s in the first frame
        self.assertLess(p.actual_speed, 0.5)

    def test_walk_reaches_speed_in_a_weighty_but_responsive_time(self):
        t = time_to_speed(Player(2.0, 2.0), 0.95)
        self.assertIsNotNone(t)
        self.assertGreater(t, 0.25)
        self.assertLess(t, 0.6)

    def test_sprint_takes_longer_than_walk_to_build(self):
        walk = time_to_speed(Player(2.0, 2.0), 0.95)
        sprint = time_to_speed(Player(2.0, 2.0), 0.95, running=True)
        self.assertGreater(sprint, walk + 0.4)

    def test_sprint_stops_further_than_walk(self):
        walker = simulate(Player(2.0, 2.0), 1.5)
        runner = simulate(Player(2.0, 2.0), 3.0, running=True)
        self.assertAlmostEqual(runner.actual_speed, config.PLAYER_RUN_SPEED,
                               delta=0.05)
        d_walk, d_run = stop_distance(walker), stop_distance(runner)
        self.assertGreater(d_run, d_walk * 2.0)
        self.assertLess(d_run, 2.0)
        self.assertEqual(walker._velocity, (0.0, 0.0))

    def test_reversal_brakes_through_zero_before_reaccelerating(self):
        p = simulate(Player(5.0, 5.0), 1.0)
        speeds = []
        for _ in range(60):
            p.apply_movement((-1.0, 0.0), False, DT, OpenGrid())
            speeds.append(p._velocity[0])
        self.assertTrue(any(v > 0.5 for v in speeds[:3]))
        self.assertLess(speeds[-1], -2.5)
        # sign change happens once, i.e. a clean brake, no oscillation
        flips = sum(1 for a, b in zip(speeds, speeds[1:]) if a * b < 0)
        self.assertEqual(flips, 1)

    def test_turning_removes_sideways_drift(self):
        p = simulate(Player(5.0, 5.0), 1.0)
        for _ in range(30):
            p.apply_movement((0.0, 1.0), False, DT, OpenGrid())
        vx, vy = p._velocity
        self.assertLess(abs(vx), 0.2)
        self.assertGreater(vy, 2.5)

    def test_step_velocity_never_exceeds_cap(self):
        prof = MoveProfile(3.2, 16.0, 26.0, 20.0, 18.0)
        vx = vy = 0.0
        for _ in range(300):
            vx, vy = step_velocity(vx, vy, 1.0, 0.0, prof, DT)
            self.assertLessEqual(math.hypot(vx, vy), 3.2 + 1e-9)

    def test_diagonal_is_not_faster(self):
        straight = simulate(Player(2.0, 2.0), 1.0)
        diag = simulate(Player(2.0, 2.0), 1.0, mv=(0.7071, 0.7071))
        self.assertAlmostEqual(straight.actual_speed, diag.actual_speed,
                               delta=0.02)


class TestFrameRateIndependence(unittest.TestCase):
    def test_distance_matches_across_frame_rates(self):
        results = []
        for fps in (20, 30, 60, 144, 240):
            p = Player(2.0, 2.0)
            simulate(p, 1.2, dt=1.0 / fps)
            simulate(p, 0.6, mv=(0.0, 0.0), dt=1.0 / fps)
            results.append((p.x, p._gait_total))
        xs = [r[0] for r in results]
        self.assertLess(max(xs) - min(xs), 0.03)
        gs = [r[1] for r in results]
        self.assertLess(max(gs) - min(gs), 0.03)


class TestCollisionResponse(unittest.TestCase):
    def test_wall_absorbs_velocity_and_reports_impact(self):
        p = simulate(Player(2.0, 2.0), 2.0, running=True)
        wall = WallGrid(p.x + 0.3)
        seen = 0.0
        for _ in range(30):
            p.apply_movement((1.0, 0.0), True, DT, wall)
            seen = max(seen, p.bump_impact)
        self.assertGreater(seen, config.PLAYER_BUMP_SHAKE_MIN)
        self.assertLess(abs(p._velocity[0]), 0.05)

    def test_no_restart_from_stale_velocity_after_leaving_wall(self):
        p = simulate(Player(2.0, 2.0), 1.0)
        wall = WallGrid(p.x + 0.2)
        for _ in range(30):
            p.apply_movement((1.0, 0.0), False, DT, wall)
        # let go of the keys, then open space: must not lurch forward
        p.apply_movement((0.0, 0.0), False, DT, OpenGrid())
        self.assertLess(p.actual_speed, 0.1)

    def test_blocked_player_does_not_cycle_gait_or_step(self):
        p = Player(2.0, 2.0)
        simulate(p, 0.5, grid=BlockedGrid())
        self.assertEqual(p._gait_total, 0.0)
        self.assertFalse(p.footstep_sound)


class TestFootsteps(unittest.TestCase):
    def test_footsteps_fire_exactly_on_ground_contacts(self):
        p = Player(2.0, 2.0)
        events = 0
        for _ in range(60 * 6):
            p.apply_movement((1.0, 0.0), False, DT, OpenGrid())
            events += int(p.footstep_sound)
        self.assertEqual(events, int(p._gait_total * 2.0))
        self.assertGreater(events, 5)

    def test_footsteps_stay_phase_locked_after_stopping(self):
        p = simulate(Player(2.0, 2.0), 1.0)
        simulate(p, 0.5, mv=(0.0, 0.0))
        events = 0
        for _ in range(60 * 3):
            p.apply_movement((1.0, 0.0), False, DT, OpenGrid())
            events += int(p.footstep_sound)
        # every event corresponds to a half-cycle boundary of the same phase
        self.assertEqual(p._last_contact, int(p._gait_total * 2.0))
        self.assertAlmostEqual(p._gait, p._gait_total % 1.0, places=9)
        self.assertGreater(events, 3)

    def test_step_side_alternates(self):
        p = Player(2.0, 2.0)
        sides = []
        for _ in range(60 * 4):
            p.apply_movement((1.0, 0.0), False, DT, OpenGrid())
            if p.footstep_sound:
                sides.append(p._step_side)
        self.assertGreater(len(sides), 4)
        self.assertTrue(all(a != b for a, b in zip(sides, sides[1:])))


class TestWeightAndLoad(unittest.TestCase):
    def test_backpedalling_is_slower_than_walking_forward(self):
        fwd, back = Player(5.0, 5.0), Player(5.0, 5.0)
        for p in (fwd, back):
            p.set_aim(1.0, 0.0)
        simulate(fwd, 1.5, mv=(1.0, 0.0))
        simulate(back, 1.5, mv=(-1.0, 0.0))
        self.assertAlmostEqual(
            back.actual_speed / fwd.actual_speed,
            aim_speed_multiplier(-1.0, 0.0, 1.0, 0.0), delta=0.01)
        self.assertLess(back.actual_speed, fwd.actual_speed * 0.8)

    def test_strafing_sits_between_forward_and_back(self):
        a = aim_speed_multiplier
        self.assertGreater(a(1, 0, 1, 0), a(0, 1, 1, 0))
        self.assertGreater(a(0, 1, 1, 0), a(-1, 0, 1, 0))
        self.assertEqual(a(0, 1, 0, 0), 1.0)      # no aim, no penalty

    def test_sprint_alignment_gate_is_off_by_default(self):
        p = Player(2.0, 2.0)
        p.set_aim(1.0, 0.0)
        self.assertTrue(p.sprint_allowed((-1.0, 0.0)))

    def test_heavier_weapon_is_slower_and_slower_to_start(self):
        pistol = Player(2.0, 2.0, [Weapon("pistol")])
        rifle = Player(2.0, 2.0, [Weapon("pistol"), Weapon("rifle")])
        rifle.select_weapon(1)
        simulate(pistol, 1.5)
        simulate(rifle, 1.5)
        self.assertLess(rifle.actual_speed, pistol.actual_speed)
        self.assertAlmostEqual(
            rifle.actual_speed / pistol.actual_speed,
            config.WEAPONS["rifle"]["handling"], delta=0.01)

    def test_reloading_and_firing_slow_the_player(self):
        free, busy = Player(2.0, 2.0), Player(2.0, 2.0)
        busy.weapon.mag = 1
        self.assertTrue(busy.weapon.start_reload())
        simulate(free, 1.5)
        simulate(busy, 1.5)
        self.assertAlmostEqual(busy.actual_speed / free.actual_speed,
                               config.PLAYER_RELOAD_SPEED, delta=0.01)
        shooter = Player(2.0, 2.0)
        shooter.mark_shoot()
        simulate(shooter, 0.3)
        self.assertLess(shooter.actual_speed,
                        config.PLAYER_WALK_SPEED * 0.95)

    def test_knockback_pushes_away_and_reduces_control(self):
        p = Player(5.0, 5.0)
        p.apply_knockback(4.0, 5.0, 26.0)       # hit from the west
        self.assertGreater(p._velocity[0], 2.0)
        self.assertGreater(p._stagger, 0.0)
        # trying to walk straight back into the attacker barely steers at first
        p.apply_movement((-1.0, 0.0), False, DT, OpenGrid())
        self.assertGreater(p._velocity[0], 0.0)
        for _ in range(60):
            p.apply_movement((-1.0, 0.0), False, DT, OpenGrid())
        self.assertLess(p._velocity[0], -2.5)
        self.assertEqual(p._stagger, 0.0)

    def test_knockback_scales_with_damage_within_limits(self):
        light, heavy = Player(5.0, 5.0), Player(5.0, 5.0)
        light.apply_knockback(4.0, 5.0, 7.0)
        heavy.apply_knockback(4.0, 5.0, 60.0)
        self.assertLess(light._velocity[0], heavy._velocity[0])
        self.assertLessEqual(heavy._velocity[0], config.PLAYER_KNOCKBACK_MAX)


class TestSurfaces(unittest.TestCase):
    def test_grass_slower_and_quieter_than_path(self):
        path, grass = Player(2.0, 2.0), Player(2.0, 2.0)
        simulate(path, 1.5, surface=surface_for(config.T_PATH))
        simulate(grass, 1.5, surface=surface_for(config.T_GRASS))
        self.assertLess(grass.actual_speed, path.actual_speed)
        self.assertLess(surface_for(config.T_GRASS).noise,
                        surface_for(config.T_BRIDGE).noise)

    def test_low_grip_lengthens_stopping(self):
        grippy, slick = Player(2.0, 2.0), Player(2.0, 2.0)
        simulate(grippy, 1.5, surface=surface_for(config.T_PATH))
        simulate(slick, 1.5, surface=surface_for(config.T_PATH))
        wet = surface_for(config.T_ROCK, rain=1.0)
        d_grip = d_slick = 0.0
        for p, surf, which in ((grippy, surface_for(config.T_ROCK), 0),
                               (slick, wet, 1)):
            x0 = p.x
            for _ in range(120):
                p.apply_movement((0.0, 0.0), False, DT, OpenGrid(),
                                 surface=surf)
            if which == 0:
                d_grip = p.x - x0
            else:
                d_slick = p.x - x0
        self.assertGreater(d_slick, d_grip)

    def test_rain_only_lowers_grip_above_threshold(self):
        dry = surface_for(config.T_PATH, rain=0.1)
        wet = surface_for(config.T_PATH, rain=1.0)
        self.assertEqual(dry.grip, 1.0)
        self.assertLess(wet.grip, 1.0)


class TestStamina(unittest.TestCase):
    def test_sprint_does_not_flicker_at_zero_stamina(self):
        s = SurvivalSystem()
        s.stamina = 3.0
        # keep holding sprint the whole time: the player is mashing Shift
        flags = [s.update(DT, True) for _ in range(60 * 6)]
        self.assertIn(False, flags)
        first_off = flags.index(False)
        # once exhausted the lock holds until stamina has recovered to the
        # resume level (it never re-opens while stamina sits near zero)
        regen_frames = int(config.STAMINA_RESUME / 18.0 / DT)
        self.assertFalse(any(flags[first_off:first_off + regen_frames - 5]))
        # ...and sprinting does come back afterwards
        self.assertTrue(any(flags[first_off + regen_frames:]))

    def test_winded_after_exhaustion_and_fades_out(self):
        s = SurvivalSystem()
        s.stamina = 0.5
        s.update(DT, True)          # drains to zero
        s.update(DT, True)
        self.assertTrue(s.winded)
        for _ in range(int(config.STAMINA_WINDED_TIME / DT) + 5):
            s.update(DT, False)
        self.assertFalse(s.winded)

    def test_sprint_factor_fades_when_low(self):
        s = SurvivalSystem()
        self.assertEqual(s.sprint_factor, 1.0)
        s.stamina = 5.0
        self.assertLess(s.sprint_factor, 1.0)
        self.assertGreaterEqual(s.sprint_factor, 0.8)

    def test_low_stamina_slows_the_sprint(self):
        fresh, tired = Player(2.0, 2.0), Player(2.0, 2.0)
        simulate(fresh, 3.0, running=True)
        simulate(tired, 3.0, running=True, run_scale=0.85)
        self.assertLess(tired.actual_speed, fresh.actual_speed)


class TestLean(unittest.TestCase):
    def test_lean_into_acceleration_then_settles(self):
        p = Player(2.0, 2.0)
        # +x world motion is +screen-x in the isometric projection
        simulate(p, 0.15)
        self.assertGreater(p.lean, 0.1)
        simulate(p, 1.5)
        self.assertLess(abs(p.lean), 0.05)

    def test_braking_leans_back(self):
        p = simulate(Player(2.0, 2.0), 1.5)
        simulate(p, 0.1, mv=(0.0, 0.0))
        self.assertLess(p.lean, -0.1)

    def test_lean_is_bounded(self):
        p = simulate(Player(2.0, 2.0), 2.0, running=True)
        for _ in range(30):
            p.apply_movement((-1.0, 0.0), True, DT, OpenGrid())
            self.assertLessEqual(abs(p.lean), 1.0)


class TestCamera(unittest.TestCase):
    def test_smooth_damp_converges_without_overshoot(self):
        x, v = 0.0, 0.0
        for _ in range(240):
            x, v = smooth_damp(x, 10.0, v, 0.2, DT)
            self.assertLessEqual(x, 10.0 + 1e-9)
        self.assertAlmostEqual(x, 10.0, places=3)

    def test_smooth_damp_is_stable_for_large_steps(self):
        x, v = 0.0, 0.0
        for _ in range(20):
            x, v = smooth_damp(x, 10.0, v, 0.2, 0.25)
        self.assertAlmostEqual(x, 10.0, places=2)

    def test_camera_follow_lags_less_than_the_old_exponential(self):
        cam = Camera(1280, 720)
        cam.set_bounds(-1000, -1000, 1000, 1000)
        cam.snap(0.0, 0.0)
        speed, t = config.PLAYER_RUN_SPEED, 0.0
        lead = speed * config.CAM_LOOKAHEAD
        for _ in range(600):
            t += DT
            cam.update(DT, speed * t + lead, 0.0)
        lag = speed * t - cam.fx
        old_lag = speed / config.CAM_FOLLOW_SMOOTH
        self.assertLess(lag, old_lag * 0.6)
        self.assertGreaterEqual(lag, 0.0)

    def test_snap_clears_spring_velocity(self):
        cam = Camera(1280, 720)
        cam.set_bounds(-1000, -1000, 1000, 1000)
        for _ in range(30):
            cam.update(DT, 50.0, 0.0)
        cam.snap(5.0, 5.0)
        cam.update(DT, 5.0, 5.0)
        self.assertAlmostEqual(cam.fx, 5.0, places=3)


class TestGaitMapping(unittest.TestCase):
    def test_contacts_land_on_phase_zero_and_half(self):
        p = Player(2.0, 2.0)
        phases = []
        for _ in range(60 * 5):
            before = p._gait_total
            p.apply_movement((1.0, 0.0), False, DT, OpenGrid())
            if p.footstep_sound:
                # the contact phase lies inside the interval just travelled
                contact = math.floor(p._gait_total * 2.0) / 2.0
                self.assertGreater(contact, before - 1e-9)
                self.assertLessEqual(contact, p._gait_total + 1e-9)
                phases.append(contact % 1.0)
        self.assertTrue(all(ph in (0.0, 0.5) for ph in phases))

    def test_cycles_per_tile_is_continuous_in_speed(self):
        prev = cycles_per_tile(0.0)
        for i in range(1, 600):
            cur = cycles_per_tile(i * 0.01)
            self.assertLess(abs(cur - prev), 0.01)
            prev = cur


if __name__ == "__main__":
    unittest.main()
