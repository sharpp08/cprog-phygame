# WHEN THE WOODS BLEED: Project Overview

*Repository: `sharpp08/cprog-phygame` · Review basis: commit `72603aa` (shallow clone), 14 Nov 2026*

> **How to read this document.** Everything marked **[verified]** was read directly from the source, config or CI files in this commit. Items marked **[unverified]** could not be confirmed. In particular, the game and test suite were **not executed** for this review (the review environment had no pygame installed and no network access), so no claim here about runtime behaviour, frame rate or test results should be treated as measured.

---

## 1. Summary

**WHEN THE WOODS BLEED** (internally "CPROG PHYGAME") is a single-player, isometric 2.5D zombie survival-horror shooter written in Python with pygame-ce and NumPy. The player starts at a camp in a 48 × 48-tile night forest, scavenges ammunition, medkits and flashlight batteries, fights or avoids eight kinds of infected, and tries to reach an ancient shrine at the centre of the map. Reaching it triggers three escalating waves; surviving them wins the game, and the ending shown depends on how many story clues the player found.

The project is well past the "planned" stage the README describes. A complete game loop, menus, save/load, horror pacing, enemy AI, weather and a full post-processing chain all exist in code, with 109 automated tests and two CI workflows. What it lacks is not features but **consolidation**: documentation that matches the code, repository hygiene, a verified release path and recorded performance numbers.

### Snapshot [verified]

| Item | Value |
|---|---|
| Language / runtime | Python, pinned to `>=3.12,<3.13` |
| Dependencies | `pygame-ce==2.5.8`, `numpy==2.5.4` (both required); `moderngl>=5.11` optional (`[gl]` extra) |
| Code size | ≈10,100 lines of Python: ≈8,400 source, ≈1,700 tests |
| Tests | 109 `test_*` functions across 9 modules, run with `unittest` |
| CI | 2 GitHub Actions workflows (Ubuntu, Python 3.12, headless SDL) |
| Entry point | `python main.py` (also declared as the `phygame` console script) |
| Art / audio | 100% procedural: sprites are generated at startup, sound effects and music are synthesised with NumPy. No `assets/` folder exists. |
| Map | 48 × 48 tiles, seeded generation (`seed=1234`), shrine at tile (24, 24) |
| Frame target | 60 FPS (`config.FPS`), unmeasured |
| Packaging | Not started (no PyInstaller spec, no release workflow) |

---

## 2. Gameplay

### 2.1 Objective and loop

1. **Explore phase.** Start at camp (a safe zone of radius 3.5 tiles that briefly shields the player from pursuit). Zombies spawn continuously, with the active cap growing from 8 by one every 20 seconds up to 42.
2. **Shrine phase.** Entering within 3.5 tiles of the shrine seals the player in. Three waves spawn in sequence, each starting when the previous one is cleared.
3. **Outcome.** Clearing wave 3 wins; dying loses.

Wave sizes follow `int(8 × 1.7^(wave−1))`, giving **8, 13 and 23** zombies. Wave composition is randomised across regular, fast, tank and the special types.

### 2.2 Player

- 8-directional movement (WASD or arrow keys, diagonals normalised), mouse aiming converted from screen space to the ground plane so aim stays correct under isometric projection.
- Walk 3.2 and run 5.6 tiles/s; **stamina** drains while sprinting and sprinting is disabled at zero.
- **Crouch** (Left Ctrl): 52% speed, quieter footsteps, shorter zombie sight range.
- 100 HP, 0.6 s invulnerability after a hit.
- Starts with the pistol. The shotgun and assault rifle are found as pickups.

### 2.3 Weapons [verified, `config.WEAPONS`]

| Weapon | Mode | Damage | Rate (shots/s) | Range (tiles) | Mag / reserve | Reload (s) | Notes |
|---|---|---|---|---|---|---|---|
| Pistol | Semi | 24 | 3.0 | 16 | 12 / 60 | 1.1 | Starting weapon |
| Shotgun | Semi | 14 × 7 pellets | 1.4 | 8 | 6 / 24 | 1.9 | Wide spread (0.34), heavy recoil |
| Assault rifle | Auto | 16 | 9.0 | 20 | 30 / 120 | 2.2 | Fastest bullets (34) |

Gunfire generates noise that can draw hordes (see 2.5).

### 2.4 Enemies [verified, `config.ZOMBIE_TYPES`]

| Type | HP | Speed | Damage | Detect range | Behaviour |
|---|---|---|---|---|---|
| Standard | 60 | 1.6 | 10 | 11 | Baseline pursuer |
| Runner | 34 | 3.3 | 8 | 15 | Fast, fragile |
| Tank | 240 | 0.9 | 26 | 12 | Slow, heavy hits, longer reach |
| Crawler | 45 | 1.2 | 12 | 9 | Low profile |
| Exploder | 50 | 1.9 | 18 | 10.5 | Deals extra close-range damage and hurts itself |
| Screamer | 72 | 1.25 | 7 | 16 | Alerts nearby zombies |
| Armored | 165 | 1.05 | 18 | 10.5 | Resists damage |
| Stalker | 52 | 2.0 | 13 | 8 | Silent, shadows last-known position |

**AI** uses A* navigation on the tile grid with octile distance. Zombies are blocked by solid geometry for line of sight, investigate noise, remember the player's last known position and share alerts. Flashlight use, crouching and heavy rain modify detection range.

### 2.5 Pacing and survival systems

- **Horror director.** Computes a tension value from nearby threats (weight 0.48), missing health (0.27), ammunition pressure (0.12), player noise (0.08) and elapsed time (up to 0.10), mapped to four levels: *quiet, uneasy, danger, critical*. It schedules atmospheric events (snapping branches, distant bells), refuses to stack scares on top of close attacks, and grants a recovery window after an escape.
- **Horde director.** Sustained gunfire pulls delayed groups from distant spawn lanes, bounded by spawn distance, spacing, cooldowns and the active-population cap.
- **Flashlight.** Finite charge (drains about 1.15%/s while on, never recharges). `B` installs a spare cell (start with 2, max 9). The beam flickers below 25% and is boosted in rain or fog.
- **Scavenging and crafting.** Zombies drop scrap; `C` converts 3 scrap into a 35 HP field dressing.
- **Story.** Journal and stone clues at landmarks (`E`); the number discovered selects one of three endings.
- **Pickups:** pistol, shotgun and rifle ammo (36 / 12 / 48), medkit (+40), battery cell, shotgun and rifle weapons.

---

## 3. Architecture

### 3.1 Layers

```
main.py ─► engine.Window ─► engine.Game  (state machine: menu / playing / pause / settings / game over)
                                │
     ┌───────────┬──────────────┼───────────────┬─────────────┐
   systems/    entities/      world/          engine/        ui/
 (rules, AI)  (data + state) (map, terrain)  (render, input,  (menus, HUD)
                                              audio, camera)
                                │
                            graphics/ + shaders/  (post-processing, quality, optional GLSL)
```

`config.py` is the single source of truth for tuning constants (resolution, projection, weapons, zombie stats, pickups, wave sizes, lighting, audio), and every layer reads from it.

### 3.2 Module map [verified]

| Package | Responsibility | Key files |
|---|---|---|
| `engine/` | Game loop, rendering, camera, input, audio, collision, lighting, particles, procedural assets | `game.py` (601 lines), `renderer.py` (650), `asset_manager.py` (1,051), `audio_manager.py`, `camera.py`, `iso.py`, `flashlight.py`, `visual_enhancement.py` |
| `entities/` | Plain game objects | `player.py`, `zombie.py`, `weapon.py`, `bullet.py`, `pickup.py`, `entity_base.py` |
| `systems/` | Rules and behaviour | `enemy_ai.py`, `navigation.py`, `combat.py`, `progression.py`, `survival.py`, `horror_director.py`, `horde_director.py`, `storytelling.py`, `weather.py`, `inventory.py`, `save_manager.py`, `world_manager.py` |
| `world/` | Map generation and world data | `map_generator.py`, `map_data.py`, `terrain.py`, `environment.py`, `obstacles.py` |
| `graphics/` | Post-processing and quality presets | `post_processing.py` (NumPy reference pipeline), `gpu_post.py`, `shader_manager.py`, `quality_settings.py` |
| `shaders/` | GLSL mirror of the post passes | 1 vertex + 10 fragment shaders (bloom, bloom extract, chromatic aberration, colour grading, distortion, film grain, final composite, vignette, flashlight, fog) |
| `ui/` | Screens and widgets | `main_menu.py`, `hud.py`, `pause_menu.py`, `settings_menu.py`, `game_over.py`, `widgets.py` |
| `tools/` | Developer diagnostics | GL checks, micro and post-processing benchmarks, profiler |
| `tests/` | `unittest` suites | animation, graphics, horror systems, progression, rendering, perception, flashlight, zombie archetypes, visual scenes |

### 3.3 Design rules the code already follows

- **World space and screen space are separate.** `engine/iso.py` and `engine/camera.py` own the conversion (`screen_x = (x − y) × 32`, `screen_y = (x + y) × 16 − z`, 2:1 diamond tiles of 64 × 32). Collision, AI and gameplay use world coordinates; the HUD is never transformed by the camera.
- **Graceful degradation.** The NumPy post-processing path is the reference implementation and always works. GLSL via ModernGL is optional and compile-validated only when a GL context exists.
- **Bounded cost.** Particle limit 520, zombie cap 42, effect resolution downscaled 2–8× by quality preset, cached sprites, shadows and light falloff.
- **Defensive saves.** Loading rejects missing, malformed or wrong-version files instead of crashing.

---

## 4. Rendering and atmosphere [verified from code and README]

- Procedural, cached sprites: seven tree variants, ground tiles, rocks, bushes, a red-roofed shrine, pond with lily pads, bridge and waterfall.
- Depth-sorted isometric rendering with zoom-consistent scaling (camera zoom 0.6–1.8, default 1.15).
- Night lighting: near-total darkness (0.98), radial player light, directional flashlight beam, shrine light, firefly and ember particles.
- **Post chain** (before the HUD so the HUD stays readable): colour grade LUT, dynamic vignette, film grain, chromatic aberration, bloom, distortion, camera shake. All react to horror-director tension, damage and low health.
- **Weather:** clear → mist → light rain → heavy rain with wind, lightning (flash, thunder, shake) and rain ambience.
- **Quality presets:** Low, Medium (default), High, Ultra, plus a Post-FX override (Auto / On / Off).
- **Animation:** eight-pose run cycles for the player and each infected type driven by a continuous gait phase (the most recent commits refine the animation model and simplify per-archetype profiles).

---

## 5. Setup and controls

### 5.1 Install and run

The authoritative dependency list is `pyproject.toml`; there is no `requirements.txt`.

```bash
git clone https://github.com/sharpp08/cprog-phygame.git
cd cprog-phygame
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1      macOS/Linux: source .venv/bin/activate
python -m pip install -e .          # add ".[gl]" for optional ModernGL shader validation
python main.py
```

Requires **Python 3.12.x**. The `<3.13` pin is strict, so 3.13 will refuse to install. The code is plain Python and pygame and likely runs on Linux and macOS, but CI is the only non-Windows evidence and Windows 10/11 remains the stated target.

### 5.2 Controls [verified, `engine/game.py`, `engine/input_manager.py`]

| Input | Action |
|---|---|
| W A S D / arrow keys | Move |
| Mouse | Aim |
| Left mouse button | Fire (hold for automatic weapons) |
| Left Shift | Sprint (uses stamina) |
| Left Ctrl | Crouch |
| R | Reload |
| 1 / 2 / 3 | Select pistol / shotgun / rifle (if owned) |
| F | Toggle flashlight |
| B | Install spare flashlight cell |
| C | Craft field dressing (3 scrap) |
| E | Investigate nearby clue |
| Esc or P | Pause |
| F1 | Toggle debug overlay |

The README currently lists two different control tables; this is the single combined set.

---

## 6. Quality, testing and performance

### 6.1 Automated tests [verified present, not executed]

| Module | Tests | Covers |
|---|---|---|
| `test_animation.py` | 32 | Gait cycles and pose animation |
| `test_graphics.py` | 29 | Post pipeline, shaders, quality presets |
| `test_horror_systems.py` | 16 | Director, hordes, survival, story |
| `test_progression.py` | 8 | Waves, objectives, win/lose |
| `test_enemy_perception.py` | 7 | Sight, noise, memory |
| `test_render.py` | 6 | Renderer smoke tests |
| `test_zombie_archetypes.py` | 6 | Per-type stats and behaviour |
| `test_flashlight.py` | 4 | Beam tracing |
| `test_visual_scenes.py` | 1 | Review-scene screenshots |

**Coverage gaps:** there are no dedicated tests for isometric projection round-trips, collision, combat damage, weapon reload and ammunition logic, or save/load validation, which are exactly the items the README's own testing section promises. Navigation and `SaveManager` are only touched incidentally.

### 6.2 Continuous integration

| Workflow | Triggers | Does |
|---|---|---|
| `tests.yml` | push and PR to `main`, manual | `pip install -e .`, `compileall`, `unittest discover` |
| `graphics-validation.yml` | **every branch** push, PR, manual | Installs pinned deps, headless SDL, `compileall`, `unittest`, uploads screenshots |

The two workflows run the same test suite, so every push to `main` runs it twice. The README says tests run only "on pushes to main", which is out of date.

### 6.3 Performance

No benchmark results are recorded anywhere in the repository. `tools/bench_micro.py`, `bench_post.py` and `profile_post.py` exist to produce them. The 60 FPS goal is therefore **a target, not a result**. The first step is to run these tools on reference hardware (including an integrated GPU) and commit the numbers.

---

## 7. Status by roadmap phase

| # | Phase | Status | Evidence |
|---|---|---|---|
| 1 | Foundation and architecture | **Done** | Layered packages, central `config.py`, CI |
| 2 | Isometric projection and camera | **Done** | `engine/iso.py`, `camera.py`; needs direct tests |
| 3 | Terrain rendering | **Done** | `world/`, procedural tiles |
| 4 | Player movement and animation | **Done** | `player.py`, 32 animation tests |
| 5 | Forest and shrine environment | **Done (procedural)** | The referenced "Isometric Forest Shrine Map" image is not in the repo |
| 6 | Zombie AI and navigation | **Done** | A*, perception, 8 archetypes, tests |
| 7 | Weapons and combat | **Done** | 3 weapons, spread, reload, recoil; needs direct tests |
| 8 | Survival and progression | **Done** | Stamina, flashlight, crafting, waves, endings |
| 9 | Lighting and visual effects | **Done** | Lighting, weather, multi-pass post chain |
| 10 | UI and audio | **Done** | Menus, HUD, synthesised audio |
| 11 | Save system | **Basic** | JSON, validated; see risks in 8.2 |
| 12 | Optimisation and testing | **Partial** | Tools exist, no results, test gaps |
| 13 | Windows executable release | **Not started** | No spec file or release pipeline |

"Done" means the feature exists in code and has at least some test or CI coverage. It does not mean it has been play-tested here.

---

## 8. Known issues and risks

### 8.1 Documentation vs reality [verified]

| README says | Actual |
|---|---|
| Status: "planned / verify" for phases 2–13 | Implemented (see section 7) |
| `requirements.txt` exists or is "to be created" | Not present; use `pyproject.toml` |
| NumPy is "optional" | Hard dependency (pinned in `pyproject.toml`; used by audio and post-processing) |
| Python "3.12 or another supported version" | Exactly 3.12.x |
| Structure lists `iso_projection.py`, `assets/`, `build/`, tests `test_camera/projection/combat/collision/enemy_ai` | Actual: `engine/iso.py`; no `assets/` or `build/`; those tests do not exist; unlisted `graphics/`, `shaders/`, `tools/`, `flashlight.py`, `visual_enhancement.py` and four systems modules exist |
| 3 zombie archetypes planned | 8 implemented |
| Controls: two inconsistent tables | One combined table in 5.2 |
| Game title WHEN THE WOODS BLEED | Window title and `pyproject` say "CPROG PHYGAME" |

### 8.2 Technical risks

1. **Save location breaks when packaged.** `SAVE_DIR` is derived from `__file__`. In a PyInstaller one-file build that is a temporary directory deleted on exit, and an installed copy under *Program Files* may not be writable. Saves would silently fail (`SaveManager.save` swallows exceptions and returns `False`). Use a per-user directory such as `%APPDATA%\WhenTheWoodsBleed`.
2. **Settings are not persisted on their own.** They are only stored inside a game save, and `main.py` carries a note that persisted settings are not yet applied at launch. Quality, resolution and volume reset every run.
3. **Possible dead-run "Continue" [unverified].** `Game._enter_gameover` saves state when the player *loses*, and `load_game` restores the saved HP. Continuing after a death may therefore resume a run with the player at 0 HP. This needs a quick manual test.
4. **Console script is likely broken after a wheel install [unverified].** `pyproject` declares `phygame = "main:main"` but the hatch wheel target lists packages only, not the top-level `main.py` and `config.py`. Editable installs (what CI and the README use) are unaffected.
5. **Resolution handling.** New games create the camera and menus from `config.WINDOW_W/H` rather than the actual screen size, which may misalign non-default resolutions. Needs a test at 800 × 450 and 1920 × 1080.
6. **Large modules.** `asset_manager.py` (1,051 lines), `renderer.py`, `game.py` and `post_processing.py` carry many responsibilities and are the main maintainability cost.
7. **Diagnostics via `print`.** World startup prints a banner to stdout; there is no logging layer, and the top-level handler only prints a traceback.

### 8.3 Repository hygiene [verified]

- **47 build/debug artefacts are tracked despite `.gitignore`:** 42 `.pyc` files under `__pycache__/` and 5 PNGs in the repository root (`anim_verify.png`, `diag_render.png`, `shot_playing.png`, `shot_test.png`, `test_render_screenshot.png`). They were committed before the ignore rules took effect.
- `.gitignore` references `saves/.gitkeep`, which does not exist (the directory is created at runtime, so this is harmless).
- `tests/` is listed in the wheel package set, which ships tests to end users.
- This is a shallow clone, so only recent history (about 50 commits) could be inspected; full history quality was not assessed.

---

## 9. Prioritised next steps

Effort: **S** < half a day, **M** 1–2 days, **L** several days.

### Priority 1: make the documentation and repo trustworthy

| Task | Effort | Done when |
|---|---|---|
| Rewrite README from this overview: correct status, structure, requirements, controls, CI description | S | No statement in the README contradicts the code |
| `git rm --cached` the 42 `.pyc` and 5 PNG files; move useful screenshots to `docs/images/` | S | `git ls-files` shows no `.pyc`; clean clone has no stray PNGs |
| Pick one title and apply it to the window caption, `pyproject` description and README | S | Single name everywhere |
| Merge the two workflows or restrict `graphics-validation` to screenshots only | S | Tests run once per push |

### Priority 2: close the correctness gaps

| Task | Effort | Done when |
|---|---|---|
| Add tests: projection round-trip, collision, combat/ammo/reload, save round-trip and corrupt-file handling | M | The five areas listed in the README's own testing section pass in CI |
| Manually test Continue-after-death and fix (do not write a lost-run save, or reset HP) | S | Dying then pressing Continue never resumes a dead player |
| Persist settings in their own `settings.json` and apply at launch | S | Quality, resolution and volume survive restart |
| Test and fix non-default resolutions | M | 800 × 450, 1280 × 720 and 1920 × 1080 render aligned menus, HUD and camera |

### Priority 3: measure performance

| Task | Effort | Done when |
|---|---|---|
| Run `bench_micro`, `bench_post` and a 5-minute in-game profile on 2 hardware tiers at all four quality presets | M | A table of average and 1% low FPS is committed under `docs/` |
| Tune presets or default Post-FX to Auto-off on slow machines, based on those numbers | M | Medium preset holds ≥ 60 FPS on the reference integrated-GPU machine, or the target is revised |

### Priority 4: ship it

| Task | Effort | Done when |
|---|---|---|
| Move saves and settings to a per-user directory | S | Works from a read-only install location |
| Commit a PyInstaller spec (one-dir, windowed), including the `shaders/` data files | M | The built `.exe` starts on a clean Windows machine with no Python |
| Windows build job in GitHub Actions publishing a zip on tags | M | Tagging `v0.1.0` produces a downloadable build |
| Fix the `phygame` console script or remove it | S | `pip install .` followed by `phygame` works, or the entry is gone |

### Priority 5: maintainability

Split `asset_manager.py` by asset family (terrain, trees, characters, UI); extract state handling from `game.py`; replace `print` diagnostics with `logging`; add a CONTRIBUTING note for the existing guideline set.

---

## 10. Assets and licensing

All sprites and audio are generated by code at runtime, so there are currently **no third-party asset licences to track**, which is a notable strength for public release. If external art, fonts or recorded audio are added later, keep an `ASSETS.md` listing source, author and licence for each file, and add an `assets/` folder to the build spec. Add a `LICENSE` file for the code itself; none is present.

---

## 11. Development guidelines (retained and tightened)

1. Keep systems modular; put every tunable number in `config.py`.
2. Keep gameplay, AI and collision in world space; convert only at the render boundary through `engine/iso.py` and `Camera`.
3. Every new system ships with a headless `unittest` module.
4. Keep the game launchable at every commit; CI must pass before merge.
5. Optimise from measurements and record them; never claim a frame rate that was not measured.
6. Update the roadmap status only after a feature is implemented *and* tested.
7. Never commit generated files (`__pycache__`, screenshots, saves).
8. Keep this overview and the README in step with the code when architecture changes.

---

*Review limits: static review of one shallow-cloned commit. Not verified: that the game launches, that the 109 tests pass, actual frame rates, GL shader compilation, and the 8.2 items marked [unverified].*
