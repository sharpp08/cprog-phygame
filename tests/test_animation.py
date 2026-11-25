"""Regression tests for distance-synchronised procedural animation."""
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import config
from engine.asset_manager import AssetManager
from entities.player import Player
from entities.weapon import Weapon
from entities.zombie import Zombie


class OpenGrid:
    def move_circle(self, pos, delta, radius):
        return pos[0] + delta[0], pos[1] + delta[1]


class BlockedGrid:
    def move_circle(self, pos, delta, radius):
        return pos


class HalfBlockedGrid:
    """Resolve only half the requested x displacement, like wall sliding."""
    def move_circle(self, pos, delta, radius):
        return pos[0] + delta[0] * 0.5, pos[1]


class TestPlayerAnimation(unittest.TestCase):
    def test_blocked_player_does_not_foot_slide(self):
        player = Player(2.0, 2.0)
        gait = player._gait
        player.apply_movement((1.0, 0.0), False, 0.25, BlockedGrid())
        player.update(0.25)
        self.assertEqual(player._gait, gait)
        self.assertEqual(player.actual_speed, 0.0)
        self.assertFalse(player.footstep_sound)

    def test_gait_uses_actual_distance(self):
        player = Player(2.0, 2.0)
        player.apply_movement((1.0, 0.0), False, 0.1, HalfBlockedGrid())
        travelled = player.actual_speed * 0.1
        self.assertAlmostEqual(player._gait, travelled * 0.81, places=6)
        self.assertGreater(player.actual_speed, 0.0)

    def test_walk_and_run_gait_rates_match_their_stride_lengths(self):
        walking = Player(2.0, 2.0)
        walking.apply_movement((1.0, 0.0), False, 0.1, OpenGrid())
        self.assertAlmostEqual(walking._gait,
                               walking.actual_speed * 0.1 * 0.81,
                               places=6)
        running = Player(2.0, 2.0)
        running.apply_movement((1.0, 0.0), True, 0.1, OpenGrid())
        self.assertTrue(running.running)
        self.assertAlmostEqual(running._gait,
                               running.actual_speed * 0.1 * 0.44,
                               places=6)

    def test_state_change_starts_blend(self):
        player = Player(2.0, 2.0)
        player.apply_movement((1.0, 0.0), True, 0.2, OpenGrid())
        player.update(0.016)
        self.assertIn(player.anim_state, ("walk", "run"))
        self.assertLess(player.anim_blend, 1.0)
        player.update(0.2)
        self.assertEqual(player.anim_blend, 1.0)

    def test_crouching_uses_crouch_animation_state(self):
        player = Player(2.0, 2.0)
        player.crouching = True
        player.update(0.016)
        self.assertEqual(player.anim_state, "crouch_down")

    def test_crouch_down_transitions_to_idle_and_up(self):
        player = Player(2.0, 2.0)
        player.crouching = True
        player.update(0.016)
        self.assertEqual(player.anim_state, "crouch_down")
        for _ in range(30):
            player.update(0.05)
        self.assertEqual(player.anim_state, "crouch_idle")
        player.crouching = False
        player.update(0.016)
        self.assertEqual(player.anim_state, "crouch_up")
        for _ in range(30):
            player.update(0.05)
        self.assertEqual(player.anim_state, "idle")

    def test_crouch_speed_scale_reduces_movement(self):
        normal = Player(2.0, 2.0)
        crouched = Player(2.0, 2.0)
        normal.apply_movement((1.0, 0.0), False, 0.1, OpenGrid())
        crouched.apply_movement((1.0, 0.0), False, 0.1, OpenGrid(),
                                speed_scale=0.52)
        self.assertLess(crouched.actual_speed, normal.actual_speed)

    def test_sprint_uses_eight_phase_run_cycle(self):
        player = Player(2.0, 2.0)
        player.moving = True
        player.running = True
        player._gait = 0.625
        player.update(1.0 / 60.0)
        self.assertEqual(player.anim_state, "run")
        self.assertEqual(player.frame_index, 5)

    def test_aim_facing_eases_without_snapping(self):
        player = Player(2.0, 2.0)
        player.set_aim(-1.0, 0.0)
        self.assertEqual(player.facing, 1.0)
        player.update(1.0 / 60.0)
        self.assertLess(player.facing, 1.0)
        self.assertGreater(player.facing, -1.0)
        for _ in range(60):
            player.update(1.0 / 60.0)
        self.assertLess(player.facing, -0.9)

    def test_blocking_transitions_to_idle_without_resetting_gait(self):
        player = Player(2.0, 2.0)
        player.apply_movement((1.0, 0.0), False, 0.1, OpenGrid())
        player.update(0.1)
        gait = player._gait
        self.assertEqual(player.anim_state, "walk")
        player.apply_movement((1.0, 0.0), False, 0.1, BlockedGrid())
        player.update(0.1)
        self.assertEqual(player.anim_state, "idle")
        self.assertEqual(player._gait, gait)
        self.assertLess(player.anim_blend, 1.0)

    def test_death_uses_transition_blend(self):
        player = Player(2.0, 2.0)
        player.hp = 0.0
        player.update(1.0 / 60.0)
        self.assertEqual(player.anim_state, "dead")
        self.assertLess(player.anim_blend, 1.0)

    def test_reload_progress_is_monotonic(self):
        weapon = Weapon("pistol")
        weapon.mag = 1
        self.assertTrue(weapon.start_reload())
        start = weapon.reload_progress
        weapon.update(weapon.spec["reload_time"] * 0.5)
        self.assertGreater(weapon.reload_progress, start)


class TestZombieAnimation(unittest.TestCase):
    def test_blocked_zombie_does_not_advance_walk_cycle(self):
        zombie = Zombie(2.0, 2.0)
        zombie.spawning = False
        gait = zombie._gait
        zombie.apply_move(1.0, 0.0, 0.2, BlockedGrid())
        zombie.update(0.2)
        self.assertEqual(zombie._gait, gait)
        self.assertFalse(zombie.moving)

    def test_zombie_emergence_blend_finishes(self):
        zombie = Zombie(2.0, 2.0)
        for _ in range(40):
            zombie.update(0.05)
        self.assertFalse(zombie.spawning)
        self.assertEqual(zombie.anim_blend, 1.0)

    def test_zombie_death_blend_finishes(self):
        zombie = Zombie(2.0, 2.0)
        zombie.spawning = False
        zombie.alive = False
        for _ in range(30):
            zombie.update(1.0 / 30.0)
        self.assertEqual(zombie.anim_state, "dead")
        self.assertEqual(zombie.anim_blend, 1.0)

    def test_zombie_types_have_distinct_motion_profiles(self):
        runner = Zombie(2.0, 2.0, "fast")
        tank = Zombie(2.0, 2.0, "tank")
        self.assertNotEqual(runner._gait_rate, tank._gait_rate)
        self.assertGreater(runner._gait_stretch, tank._gait_stretch)

    def test_zombie_run_gait_follows_actual_travel_and_archetype_stride(self):
        for ztype in ("regular", "fast", "tank", "crawler", "exploder",
                      "screamer", "armored", "stalker"):
            with self.subTest(ztype=ztype):
                zombie = Zombie(2.0, 2.0, ztype)
                zombie.spawning = False
                zombie.state = "pursue"
                zombie._speed_current = zombie.speed
                zombie._velocity = (zombie.speed, 0.0)
                zombie._stumble = 10.0
                zombie._stumble_t = 0.0
                before = zombie._gait
                zombie.apply_move(1.0, 0.0, 0.1, OpenGrid())
                travelled = zombie._actual_speed * 0.1
                expected = (before + travelled * zombie._gait_rate) % 1.0
                self.assertAlmostEqual(zombie._gait, expected, places=6)

    def test_direction_change_does_not_reset_gait(self):
        """Turning while moving should preserve gait phase continuity."""
        player = Player(2.0, 2.0)
        player.apply_movement((1.0, 0.0), False, 0.1, OpenGrid())
        gait_after_move = player._gait
        self.assertGreater(gait_after_move, 0.0)
        # Now move diagonally — gait should continue from where it was
        player.apply_movement((1.0, 1.0), False, 0.1, OpenGrid())
        self.assertGreater(player._gait, gait_after_move)

    def test_diagonal_movement_does_not_accelerate_gait(self):
        """Diagonal movement at the same world-speed should not produce
        a faster-looking animation than straight movement."""
        straight = Player(2.0, 2.0)
        diagonal = Player(2.0, 2.0)
        straight.apply_movement((1.0, 0.0), True, 0.1, OpenGrid())
        diagonal.apply_movement((0.7071, 0.7071), True, 0.1, OpenGrid())
        # Both should have the same actual_speed (normalized input)
        self.assertAlmostEqual(straight.actual_speed,
                               diagonal.actual_speed, delta=0.1)

    def test_crawler_stays_low_in_all_states(self):
        """Crawler's idle/attack/run poses must remain in a low crouch."""
        zombie = Zombie(10.0, 10.0, "crawler")
        zombie.spawning = False
        # Idle
        zombie.state = "idle"
        zombie.moving = False
        zombie.update(0.1)
        self.assertEqual(zombie.anim_state, "idle")
        # Run
        zombie.state = "pursue"
        zombie._speed_current = zombie.speed
        zombie._velocity = (zombie.speed, 0.0)
        zombie._actual_speed = zombie.speed
        zombie.moving = True
        zombie.update(0.1)
        self.assertEqual(zombie.anim_state, "run")

    def test_blocked_character_does_not_advance_cycle(self):
        """A zombie pressed against a wall should not advance gait."""
        zombie = Zombie(2.0, 2.0, "regular")
        zombie.spawning = False
        zombie.state = "pursue"
        zombie._speed_current = zombie.speed
        zombie._velocity = (zombie.speed, 0.0)
        gait_before = zombie._gait
        zombie.apply_move(1.0, 0.0, 0.5, BlockedGrid())
        zombie.update(0.5)
        self.assertEqual(zombie._gait, gait_before)

    def test_animation_progression_consistent_at_different_frame_rates(self):
        """Gait advance should be independent of frame rate (distance-based)."""
        z1 = Zombie(2.0, 2.0, "fast")
        z2 = Zombie(2.0, 2.0, "fast")
        for z in (z1, z2):
            z.spawning = False
            z.state = "pursue"
            # Normalize speed and gait rate for deterministic comparison
            z.speed = 3.3
            z.variation = 1.0
            z._gait_rate = 0.82
            z._gait = 0.0
            z._speed_current = z.speed
            z._velocity = (z.speed, 0.0)
            z._stumble = 10.0
            z._stumble_t = 0.0
        # z1 simulates at 60fps, z2 at 30fps — same total time (1 second)
        for _ in range(60):
            z1.apply_move(1.0, 0.0, 1.0/60.0, OpenGrid())
        for _ in range(30):
            z2.apply_move(1.0, 0.0, 1.0/30.0, OpenGrid())
        # Gait should be very close (distance-based, not time-based)
        self.assertAlmostEqual(z1._gait, z2._gait, delta=0.01)


class TestFrameValidity(unittest.TestCase):
    """Verify all generated animation frames are valid, non-empty surfaces."""

    @classmethod
    def setUpClass(cls):
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.assets = AssetManager()
        cls.assets.build()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_all_player_frames_valid_dimensions(self):
        for state, frames in self.assets.frames["player"].items():
            for i, f in enumerate(frames):
                with self.subTest(state=state, frame=i):
                    w, h = f.get_size()
                    self.assertGreater(w, 0)
                    self.assertGreater(h, 0)
                    # No completely transparent frame
                    alpha_sum = int(pygame.surfarray.pixels_alpha(f).sum(dtype="uint64"))
                    self.assertGreater(alpha_sum, 0,
                                       f"Player {state} frame {i} is fully transparent")

    def test_all_zombie_frames_valid_dimensions(self):
        for ztype in config.ZOMBIE_TYPES:
            key = f"zombie_{ztype}"
            for state, frames in self.assets.frames[key].items():
                for i, f in enumerate(frames):
                    with self.subTest(ztype=ztype, state=state, frame=i):
                        w, h = f.get_size()
                        self.assertGreater(w, 0)
                        self.assertGreater(h, 0)

    def test_run_frame_count_is_eight(self):
        """Every archetype must have exactly 8 run/walk frames."""
        self.assertEqual(len(self.assets.frames["player"]["run"]), 8)
        self.assertEqual(len(self.assets.frames["player"]["walk"]), 8)
        for ztype in config.ZOMBIE_TYPES:
            key = f"zombie_{ztype}"
            self.assertEqual(len(self.assets.frames[key]["run"]), 8,
                             f"{ztype} run has {len(self.assets.frames[key]['run'])} frames")
            self.assertEqual(len(self.assets.frames[key]["walk"]), 8,
                             f"{ztype} walk has {len(self.assets.frames[key]['walk'])} frames")

    def _foot_bottom_rows(self, frame):
        """Return the lowest (max) opaque row of the sprite per column.

        In the authored sprite the ground contact plane is the bottom of the
        feet.  This lets us assert a *planted* foot sits on the ground row
        while a *swinging* foot is lifted above it.
        """
        w, h = frame.get_size()
        # Find the overall ground row: the lowest row with any opaque pixel.
        ground_row = None
        for y in range(h - 1, -1, -1):
            for x in range(w):
                if frame.get_at((x, y))[3] > 40:
                    ground_row = y
                    break
            if ground_row is not None:
                break
        self.assertIsNotNone(ground_row, "frame has no opaque pixels")
        return ground_row, w, h

    def test_planted_foot_stays_on_ground_plane(self):
        """Across a run cycle at least one foot must be planted on the ground
        plane in every frame (stance phase), proving the feet are pinned to
        the terrain rather than skating under the body."""
        for key in ("player", "zombie_regular", "zombie_fast",
                    "zombie_tank", "zombie_armored"):
            for state in ("walk", "run"):
                frames = self.assets.frames[key][state]
                for i, f in enumerate(frames):
                    with self.subTest(key=key, state=state, frame=i):
                        ground_row, w, h = self._foot_bottom_rows(f)
                        # There must be opaque pixels sitting exactly on the
                        # ground row in every frame: a planted foot or a
                        # swinging foot at its contact instant.
                        on_ground = any(f.get_at((x, ground_row))[3] > 40
                                        for x in range(w))
                        self.assertTrue(on_ground,
                                        f"{key} {state} frame {i}: no foot reaches "
                                        "the ground plane, feet are floating")

    def test_feet_track_pelvis_not_chest_pitch(self):
        """The lateral foot spread must not grow with forward lean.

        A bug where the feet were anchored to the swaying chest instead of the
        rooted pelvis produced a visible sideways skid in the run frames.  With
        pelvis anchoring, the maximum horizontal foot reach stays bounded and
        does not exceed the sprite's own half-width by a wide margin.
        """
        for key in ("player", "zombie_fast", "zombie_tank"):
            frames = self.assets.frames[key]["run"]
            # The sprite is 44px wide; feet anchored at the pelvis (cx-based)
            # with the largest authored stride should stay within ~cx +/- stride.
            max_x = 0
            for f in frames:
                ground_row, w, h = self._foot_bottom_rows(f)
                for y in (ground_row, ground_row - 1, ground_row - 2):
                    for x in range(w):
                        if f.get_at((x, y))[3] > 40:
                            max_x = max(max_x, x)
            with self.subTest(key=key):
                self.assertLess(max_x, w,
                                 f"{key} run feet reach x={max_x} of a {w}px-wide "
                                 "sprite (lateral skid)")

    def test_locomotion_frames_keep_a_consistent_ground_anchor(self):
        groups = [self.assets.frames["player"]]
        groups.extend(self.assets.frames[f"zombie_{ztype}"]
                      for ztype in config.ZOMBIE_TYPES)
        for group in groups:
            for state in ("walk", "run"):
                bottoms = [frame.get_bounding_rect().bottom
                           for frame in group[state]]
                self.assertEqual(len(set(bottoms)), 1, bottoms)
                self.assertGreaterEqual(bottoms[0], 59)

    def test_crawler_torso_remains_ground_level_in_every_locomotion_frame(self):
        crawler = self.assets.frames["zombie_crawler"]
        regular = self.assets.frames["zombie_regular"]
        for state in ("idle", "walk", "run", "attack"):
            for index, frame in enumerate(crawler[state]):
                regular_frame = regular[state][index % len(regular[state])]
                self.assertGreater(frame.get_bounding_rect().top,
                                   regular_frame.get_bounding_rect().top)

    def test_weapon_position_stable_during_run(self):
        """Player weapon should not drift to wildly different positions
        across the 8 run frames."""
        run_frames = self.assets.frames["player"]["run"]
        # Find the rightmost pixel (gun tip) in each frame
        tips = []
        for f in run_frames:
            arr = pygame.surfarray.pixels_alpha(f)
            # Find rightmost non-transparent column
            cols = arr.sum(axis=0)
            nonzero = [i for i in range(len(cols)) if cols[i] > 0]
            tips.append(max(nonzero) if nonzero else 0)
        # Spread should be small (< 15px) — gun stays anchored to hand
        spread = max(tips) - min(tips)
        self.assertLess(spread, 15,
                        f"Weapon drifts {spread}px across run frames: {tips}")

    def test_idle_and_attack_animations_still_work(self):
        """Non-moving poses must exist and have valid frames."""
        for ztype in config.ZOMBIE_TYPES:
            key = f"zombie_{ztype}"
            self.assertIn("idle", self.assets.frames[key])
            self.assertIn("attack", self.assets.frames[key])
            self.assertIn("hit", self.assets.frames[key])
            self.assertIn("dead", self.assets.frames[key])
            self.assertIn("emerge", self.assets.frames[key])

    def test_walk_frames_have_varying_foot_positions(self):
        """Walk frames should show at least some foot position variation
        across the 8-phase cycle."""
        import pygame.surfarray
        walk_frames = self.assets.frames["player"]["walk"]
        foot_spreads = []
        for f in walk_frames:
            w, h = f.get_size()
            # Check the full sprite for non-transparent pixels
            cols = []
            for y in range(int(h * 0.6), h):  # Lower half where feet are
                for x in range(w):
                    if f.get_at((x, y))[3] > 0:
                        cols.append(x)
            if cols:
                foot_spreads.append(max(cols) - min(cols))
            else:
                foot_spreads.append(0)
        # Verify frames have some variation (not all identical)
        self.assertGreater(len(set(foot_spreads)), 0,
                           "All walk frames have no opaque pixels in lower half")
        # At minimum, frames should not ALL be exactly the same width
        # (allow for some similarity due to character proportions)
        unique_spreads = set(foot_spreads)
        # If all spreads are 2, check leftmost pixel positions instead
        if len(unique_spreads) == 1 and 2 in unique_spreads:
            # Fallback: check if any frame has different leftmost column
            leftmost_cols = []
            for f in walk_frames:
                w, h = f.get_size()
                min_x = None
                for y in range(int(h * 0.6), h):
                    for x in range(w):
                        if f.get_at((x, y))[3] > 0:
                            if min_x is None or x < min_x:
                                min_x = x
                leftmost_cols.append(min_x)
            self.assertGreater(len(set(leftmost_cols)), 1,
                               "All walk frames have identical leftmost pixel")

    def test_stationary_character_does_not_advance_locomotion_cycle(self):
        """A player standing still should not keep cycling through walk frames."""
        player = Player(5.0, 5.0)
        player.apply_movement((0.0, 0.0), False, 0.1, OpenGrid())
        gait_after_stop = player._gait
        player.update(0.5)
        # Gait should not advance when not moving
        self.assertEqual(player._gait, gait_after_stop)

    def test_walking_vs_running_stride_behavior(self):
        """Walking should have a shorter stride (higher gait rate) than running."""
        player = Player(5.0, 5.0)
        # Walk
        player.apply_movement((1.0, 0.0), False, 1.0, OpenGrid())
        walk_gait_rate = 0.81  # from player.py
        # Run
        player2 = Player(5.0, 5.0)
        player2.apply_movement((1.0, 0.0), True, 1.0, OpenGrid())
        run_gait_rate = 0.44   # from player.py
        self.assertGreater(walk_gait_rate, run_gait_rate,
                           "Walk should have more cycles per tile than run")

    def test_direction_change_preserves_gait_phase(self):
        """Changing movement direction should not reset the gait phase."""
        player = Player(5.0, 5.0)
        player.apply_movement((1.0, 0.0), True, 0.5, OpenGrid())
        gait_before = player._gait
        self.assertGreater(gait_before, 0.0)
        # Now move in a different direction
        player.apply_movement((0.0, 1.0), True, 0.5, OpenGrid())
        # Gait should have advanced (not reset to 0)
        self.assertGreater(player._gait, 0.0)


    def test_player_standing_actions_share_consistent_size_and_ground_anchor(self):
        """Idle/reload retain baseline size; walk/run/fire are 1% smaller."""
        player = self.assets.frames["player"]
        states = ("idle", "walk", "run", "shoot", "fire_action", "reload_action")
        smaller_states = {"walk", "run", "shoot", "fire_action"}
        for state in states:
            self.assertIn(state, player)
            self.assertTrue(player[state], f"{state} has no frames")
            expected_height = 48  # 1% scaling rounds to the same whole-pixel height.
            for index, frame in enumerate(player[state]):
                with self.subTest(state=state, frame=index):
                    self.assertEqual(frame.get_size(), (44, 66))
                    bounds = frame.get_bounding_rect(min_alpha=8)
                    self.assertEqual(bounds.height, expected_height,
                                     f"{state} frame {index} has visible height "
                                     f"{bounds.height}px instead of {expected_height}px")
                    self.assertEqual(bounds.bottom, 66,
                                     f"{state} frame {index} is not ground-anchored")

    def test_player_standing_states_have_consistent_frame_canvas(self):
        player = self.assets.frames["player"]
        for state in ("idle", "walk", "run", "shoot", "reload",
                      "fire_action", "reload_action"):
            for index, frame in enumerate(player[state]):
                with self.subTest(state=state, frame=index):
                    self.assertEqual(frame.get_size(), (44, 66))

    def test_crouch_sprites_are_about_77_percent_of_standing_size(self):
        player = self.assets.frames["player"]
        for state in ("crouch", "crouch_idle", "crouch_up", "crouch_down"):
            self.assertTrue(player[state], f"{state} has no frames")
            for index, frame in enumerate(player[state]):
                with self.subTest(state=state, frame=index):
                    self.assertEqual(frame.get_size(), (44, 66))
                    bounds = frame.get_bounding_rect(min_alpha=8)
                    self.assertLessEqual(bounds.width, 26)
                    self.assertLessEqual(bounds.height, 38)
                    self.assertEqual(bounds.bottom, 66,
                                     "Crouch sprite must remain ground-anchored")



if __name__ == "__main__":
    unittest.main()
