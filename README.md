# 🌲 WHEN THE WOODS BLEED
### Isometric 2.5D Zombie Survival Horror

> The forest remembers. The dead awaken. Survival is only the beginning.

**WHEN THE WOODS BLEED** is an in-development single-player isometric 2.5D zombie survival shooter built with Python and Pygame-ce. The project is being developed as a new game from scratch, with a modular architecture for its rendering, world, entities, gameplay systems, interface, and audio.

> **Development status:** In development. This README describes the project vision and intended features. Items below are not claims that every feature is already implemented.

---

## Table of Contents

- [About](#about)
- [Game Overview](#game-overview)
- [World and Visual Direction](#world-and-visual-direction)
- [Gameplay](#gameplay)
- [Technical Design](#technical-design)
- [Planned Project Structure](#planned-project-structure)
- [Technology Stack](#technology-stack)
- [Setup and Installation](#setup-and-installation)
- [Controls](#controls)
- [Performance Goals](#performance-goals)
- [Testing](#testing)
- [Development Roadmap](#development-roadmap)
- [Development Guidelines](#development-guidelines)
- [Packaging](#packaging)
- [Assets and Licensing](#assets-and-licensing)
- [Repository](#repository)

## About

The game takes place in a mysterious forest filled with hostile infected creatures, abandoned structures, hidden locations, and an ancient shrine. Players explore the environment, collect supplies, manage ammunition, fight or evade enemies, and work toward reaching the shrine.

The project uses an isometric projection to create the appearance of a three-dimensional world while retaining a 2D rendering workflow. The goal is to combine responsive action gameplay with an atmospheric environment, readable combat, and a maintainable codebase.

## Game Overview

| Category | Description |
|---|---|
| Title | WHEN THE WOODS BLEED |
| Genre | Zombie Survival / Action / Shooter |
| Perspective | Isometric 2.5D |
| Language | Python |
| Framework | Pygame-ce |
| Optional library | NumPy |
| Target platform | Windows 10/11 |
| Intended mode | Single-player |
| Performance goal | 60 FPS target, subject to profiling |
| Status | In development |

## World and Visual Direction

The primary environment is a mysterious forest guided by the saved **Isometric Forest Shrine Map** reference. The reference informs the environment's composition, palette, atmosphere, and landmarks; it is not intended to be used as a flat game background.

### Planned landmarks

- **Ancient shrine:** A wooden shrine with a distinctive red roof and a major exploration landmark.
- **Forest clearing:** An open area for traversal and combat.
- **Sacred pond:** Green water with pink lily pads and surrounding vegetation.
- **Stone bridge and paths:** Routes connecting areas of the forest.
- **Waterfall:** A natural landmark with water and mist effects.
- **Dense forest:** Trees, bushes, rocks, and layered vegetation.
- **Hidden areas:** Optional locations for supplies and discoveries.

### Planned environmental systems

- Isometric terrain and ground surfaces.
- Trees, rocks, bushes, and natural obstacles.
- Layered foreground and background objects.
- Depth sorting and environmental occlusion.
- Atmospheric lighting, shadows, and fog.
- Animated water, foliage, and particles where performance permits.

### Implemented graphical foundation

The current renderer now includes a procedural, cached art pipeline and an atmospheric presentation layer:

- Seven tree silhouettes, including leafy, pine, dead, and twisted variants.
- More detailed ground tiles with clipped surface variation, roots, bark grain, foliage highlights, and weathered shrine details.
- Zoom-consistent terrain, character, obstacle, particle, and shadow sizing to preserve isometric alignment.
- Cool night ambience, cached radial light falloff, a directional flashlight beam, and a subtle screen vignette.
- Layered ground mist, high-quality film grain, fireflies, animated water ripples, waterfall mist, and gentle tree sway.
- Reusable shadow and sprite-scale caches to reduce per-frame surface creation.
- Low, Medium, High, and Ultra quality presets remain available in
  Settings; atmospheric detail scales with the selected preset. A
  Post-FX toggle (Auto / On / Off) lets integrated GPUs disable the
  cinematic chain without changing the quality preset.

The procedural assets are generated at startup and cached; the playable map is still composed from world tiles and objects, not a screenshot background. Headless render validation captures review scenes for the forest, player/vegetation, zombie encounters, shrine/pond, and flashlight lighting.

### Cinematic post-processing pipeline (graphics upgrade)

The world renders to the scene surface, then the cinematic chain runs
before the HUD is drawn (the HUD always stays perfectly readable):

- **Color grade** - dark, desaturated environment, cool blue-green
  shadows, warm lantern highlights, controlled contrast (256-entry
  LUT + strength mix).
- **Dynamic vignette** - cinematic edge darkening that reacts to the
  horror director's tension, horror events, and a low-HP heartbeat.
- **Film grain** - animated, rotating noise tiles; stronger under
  tension and supernatural events.
- **Chromatic aberration** - restrained RGB edge split on damage,
  lightning and high tension; eases back to normal.
- **Bloom** - threshold + double 3x3 box blur (HDR-style glow around
  the flashlight pool, embers and muzzle flashes).
- **Screen distortion** - heat-warp style sine field, eased in/out
  for horror events.
- **Camera shake** - exponential-decay shake with per-event intensity
  (damage, lightning, horror events, restrained recoil).

All passes run at a downscaled effect resolution (8x/4x/2x depending on
the quality preset) so the cost is small on integrated graphics. The
NumPy pipeline is the reference implementation and keeps the game fully
playable with no GPU; the GLSL sources in `shaders/` mirror the same
passes and are compile-validated with ModernGL (optional dependency,
`pip install -e .[gl]`) when a GL context is available.

### Weather, particles and audio-reactive effects

- Dynamic weather: clear -> mist -> light rain -> heavy rain, with wind
  gusts, pooled screen-space rain streaks and lightning (a blue-white
  flash + synthesized thunder + camera shake).
- Ambient particle population: drifting leaves, dust motes and shrine
  embers, all wind-aware and quality-scaled.
- Rain ambience loops under the music; the flashlight beam gains a
  volumetric-style boost during rain and flickers smoothly when the
  battery is critically low (the survival battery mechanics are
  unchanged).
- Horror events from the director spike the vignette, grain and
  distortion, and give the camera a gentle shake.
- Close pursuing enemies cast a subtle cool glow so threats read in the
  dark without revealing distant positions.


## Gameplay

### Core objective

**Survive the forest and reach the ancient shrine.**

The intended gameplay loop is:

1. Explore the forest and discover routes.
2. Search for ammunition, medical supplies, and other resources.
3. Encounter hostile zombies.
4. Fight or evade enemies.
5. Manage health and ammunition.
6. Progress toward the shrine.
7. Complete the final objective.

### Player

Planned player capabilities include:

- Eight-directional movement.
- Walking and running.
- Directional animations.
- Collision with world obstacles.
- Health and damage states.
- Weapon aiming and firing.
- Reloading and weapon switching.
- Interacting with objects and collecting supplies.

### Weapons

The initial weapon lineup is planned as:

| Weapon | Fire mode | Intended role |
|---|---|---|
| Pistol | Semi-automatic | General-purpose sidearm |
| Shotgun | Semi-automatic | High close-range damage |
| Assault rifle | Automatic | Sustained ranged combat |

The weapon system is intended to support configurable damage, fire rate, range, magazine size, ammunition, recoil, muzzle flashes, projectile or hit detection, and weapon-specific audio.

### Enemies

Planned enemy archetypes:

- **Regular Zombie:** Average speed and health; pursues and attacks at close range.
- **Fast Zombie:** High movement speed and lower health; pressures the player.
- **Tank Zombie:** Slow, durable, and capable of heavy attacks.

Enemy AI is intended to include detection, pursuit, navigation, obstacle avoidance, attacks, damage reactions, death behavior, and spawn management.

### Survival resources

Planned pickups include ammunition, medical supplies, weapons, and other survival items. Player status is expected to include health, current weapon, ammunition, inventory, and survival state.


## Implemented horror and survival systems

The current `main` branch integrates the following playable systems with the existing Pygame architecture:

- **Adaptive horror director:** tracks nearby threats, player health, ammunition pressure, noise, and survival time. Four tension levels pace scares, while recovery windows prevent constant attacks.
- **Smarter zombie perception:** solid geometry blocks sight; flashlight use, crouching, and heavy rain modify detection range. Zombies investigate noise, remember the last known player position, and share alerts.
- **Sound-attracted hordes:** sustained gunfire can draw delayed groups from distant spawn lanes. Spawn distance, group spacing, cooldowns, and an active-population cap prevent unfair spawns and uncontrolled entity growth.
- **Special infected:** Runners, Brutes/Tanks, Crawlers, Exploders, silent Stalkers, Screamers, and Armored zombies use different stat profiles. Chasing infected accelerate gradually; Stalkers shadow the last known position while remaining quiet. Screamers alert nearby enemies; Armored zombies resist incoming damage.
- **Finite flashlight cells:** press **F** to toggle the flashlight. It drains while on and does not recharge while off. Press **B** to install a spare cell; collectible cells are placed in the forest and spare-cell inventory is saved.
- **Stealth:** hold **Left Ctrl** to crouch, move more slowly, make less noise, and reduce zombie sight range. A dedicated crouch animation is generated with the existing procedural sprite system.
- **Stamina:** sprinting consumes stamina and resting restores it. Sprinting is temporarily disabled when stamina is depleted.
- **Audio feedback:** nearby zombie groans use stereo positioning and distance attenuation. Screamers have a distinct synthesized call; low health and exhaustion trigger restrained heartbeat and breathing cues.
- **Crafting:** defeated zombies yield scrap; press **C** to craft a 35-HP field dressing for 3 scrap.
- **Safe zone and environmental clues:** the starting camp briefly protects the player from pursuit. Press **E** near discoverable journal/stone clues at forest landmarks.
- **Psychological atmosphere and endings:** distant sounds, footsteps, bells, and unnatural quiet messages are paced by the horror director. The shrine encounter produces one of three story outcomes based on discovered clues.
- **Save support:** discovered clues, stamina, scrap, flashlight charge/state, and spare battery cells persist through the existing save system.

### Controls

| Input | Action |
|---|---|
| F | Toggle flashlight |
| B | Replace flashlight cell |
| Left Ctrl | Crouch / reduce noise and visibility |
| E | Investigate a nearby clue |
| C | Craft a medkit (3 scrap) |
| Shift | Sprint (uses stamina) |
| R | Reload |

The systems are modular under `systems/` and include headless unit tests under `tests/`. The GitHub Actions workflow in `.github/workflows/tests.yml` compiles the Python sources and runs `python -m unittest discover -v` on pushes to `main`.

## Technical Design

### Isometric projection

The renderer will use a centralized transformation between world coordinates and screen coordinates. A basic diamond projection can be expressed as:

```python
screen_x = (world_x - world_y) * scale_x
screen_y = (world_x + world_y) * scale_y - world_z * height_scale
```

The exact implementation may be adapted to the chosen coordinate system and rendering architecture.

World-space and screen-space coordinates must remain separate. Collision, navigation, and gameplay calculations should use world coordinates; rendering and UI placement should use the appropriate screen-space coordinates.

### Camera

Planned camera features:

- Smooth player tracking.
- Configurable zoom.
- World and viewport boundaries.
- Stable interpolation.
- World-to-screen and screen-to-world conversion.

### Rendering and depth

The rendering system is intended to handle terrain, environment objects, characters, effects, and screen-space UI in a consistent order. Depth sorting should allow characters to pass behind trees and structures where appropriate. Tall objects should distinguish their ground position from their visual height.

### Lighting and atmosphere

Planned visual effects include ambient and directional lighting, character and environmental shadows, contact shadows, fog, particles, waterfall mist, animated water, and subtle foliage movement. Effects should be introduced incrementally and profiled rather than added at the expense of stable gameplay.

### Audio

A centralized audio manager is planned for menu music, exploration ambience, combat music, footsteps, weapons, enemy sounds, environmental audio, and UI feedback. Music and sound-effect volumes should be independently configurable.

### Interface

Planned screens and interface elements:

- Main menu: New Game, Continue, Settings, Exit.
- HUD: health, weapon, ammunition, and objective.
- Pause menu: Resume, Settings, Restart, Main Menu.
- Settings: audio levels, resolution, fullscreen, graphics quality, camera zoom, and controls.

UI elements must remain in screen space and must not be transformed by the isometric camera.

### Save system

A save system is planned for progression, player status, current weapon, inventory, objective progress, and settings. Loading should validate save data and handle missing or corrupted files safely.

## Planned Project Structure

The following is the intended modular organization. The actual repository may evolve as implementation progresses.

```text
cprog-phygame/
├── main.py
├── config.py
├── requirements.txt
├── README.md
├── engine/
│   ├── game.py
│   ├── camera.py
│   ├── iso_projection.py
│   ├── renderer.py
│   ├── asset_manager.py
│   ├── audio_manager.py
│   ├── input_manager.py
│   ├── collision.py
│   ├── lighting.py
│   └── particles.py
├── entities/
│   ├── entity_base.py
│   ├── player.py
│   ├── zombie.py
│   ├── bullet.py
│   ├── weapon.py
│   └── pickup.py
├── systems/
│   ├── combat.py
│   ├── enemy_ai.py
│   ├── navigation.py
│   ├── inventory.py
│   ├── progression.py
│   ├── world_manager.py
│   └── save_manager.py
├── world/
│   ├── map_generator.py
│   ├── terrain.py
│   ├── environment.py
│   ├── obstacles.py
│   └── map_data.py
├── ui/
│   ├── main_menu.py
│   ├── hud.py
│   ├── pause_menu.py
│   ├── settings_menu.py
│   └── game_over.py
├── assets/
│   ├── references/
│   ├── sprites/
│   ├── characters/
│   ├── enemies/
│   ├── environment/
│   ├── weapons/
│   ├── effects/
│   ├── audio/
│   ├── fonts/
│   └── ui/
├── tests/
│   ├── test_camera.py
│   ├── test_projection.py
│   ├── test_combat.py
│   ├── test_collision.py
│   └── test_enemy_ai.py
└── build/
```

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Primary programming language |
| Pygame-ce | Window, input, 2D rendering, and audio |
| NumPy | Numerical operations and optional rendering optimization |
| OpenGL | Optional hardware acceleration if justified |
| PyInstaller | Windows executable packaging |
| Git / GitHub | Version control and source hosting |

## Setup and Installation

### Requirements

- Windows 10 or Windows 11.
- Python 3.12 or another version supported by the project's dependencies.
- pip.
- Git (optional).

### 1. Clone the repository

```bash
git clone https://github.com/sharpp08/cprog-phygame.git
cd cprog-phygame
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

### 3. Activate it

PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Command Prompt:

```cmd
.venv\Scripts\activate.bat
```

### 4. Install dependencies

If a `requirements.txt` file is present:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If the dependency file has not yet been created, install the framework required by the current implementation and generate a pinned requirements file as part of setup. Do not assume optional libraries are required.

### 5. Run the game

When `main.py` is the configured entry point:

```bash
python main.py
```

> **Note:** The commands above describe the intended setup. Keep this section synchronized with the actual entry point and dependency list as the project develops.

## Controls

Intended default controls:

| Input | Action |
|---|---|
| W / A / S / D | Move |
| Shift | Run |
| Mouse movement | Aim |
| Left mouse button | Shoot |
| R | Reload |
| 1 / 2 / 3 | Select weapon |
| E | Interact / collect |
| Esc | Pause |

Controls may be customized through settings once that system is implemented.

## Performance Goals

The project targets a stable 60 FPS on reasonably capable systems, including integrated graphics. This is a target, not a verified performance claim.

Optimization priorities:

- Camera-based object culling.
- Efficient sprite rendering and depth sorting.
- Reusable rendering resources.
- Efficient collision and navigation queries.
- Controlled particle counts.
- Delta-time-based movement and animation.
- Efficient asset loading and audio management.
- Configurable graphics quality.

Profile representative scenes before optimizing. Do not disable visual features blindly or claim performance improvements without measurements.

## Testing

The project should add automated tests for:

- Isometric projection and inverse projection.
- Camera tracking and boundaries.
- Player movement and diagonal normalization.
- Mouse aiming and projectile direction.
- Collision detection.
- Enemy navigation.
- Weapon reload and ammunition.
- Health and damage.
- Resource pickups.
- Save and load validation.

Manual testing should verify that the game starts, initializes a visible world, renders the player and environment, supports movement and combat, handles UI interactions, and remains stable during gameplay.

A window opening successfully is not sufficient evidence that the game is playable. Capture and inspect actual gameplay output during visual validation.

## Development Roadmap

| Phase | Goal | Status |
|---|---|---|
| 1 | Project foundation and architecture | In development |
| 2 | Isometric projection and camera | Planned / verify |
| 3 | Ground and terrain rendering | Planned / verify |
| 4 | Player movement and animation | Planned / verify |
| 5 | Forest and shrine environment | Planned / verify |
| 6 | Zombie AI and navigation | Planned / verify |
| 7 | Weapons and combat | Planned / verify |
| 8 | Survival mechanics and progression | Planned / verify |
| 9 | Lighting and visual effects | Planned / verify |
| 10 | UI and audio | Planned / verify |
| 11 | Save system | Planned / verify |
| 12 | Optimization and testing | Planned / verify |
| 13 | Windows executable release | Planned / verify |

Update statuses only after each feature has been implemented and tested.

## Development Guidelines

1. Keep systems modular and maintainable.
2. Centralize coordinate transformations.
3. Keep gameplay and collision calculations in world space.
4. Reuse assets where appropriate and verify licenses.
5. Avoid unnecessary dependencies and unrelated changes.
6. Optimize based on profiling.
7. Keep the game playable at each major milestone.
8. Test each system before expanding it.
9. Document significant architectural changes.
10. Verify asset references before deleting files.
11. Do not mark unfinished features as complete.

## Packaging

The intended Windows packaging tool is PyInstaller. A basic starting command is:

```bash
pip install pyinstaller
pyinstaller --noconfirm --clean --windowed --name WhenTheWoodsBleed main.py
```

The final build configuration must bundle required assets, fonts, audio, and runtime dependencies. Test the packaged executable on a machine or environment that does not rely on the development virtual environment.

## Assets and Licensing

Use original, properly licensed, or public-domain assets. Verify redistribution rights for sprites, textures, audio, fonts, and other third-party resources before including them in public releases. Keep source references and license information with the project where appropriate.

The Isometric Forest Shrine Map is a visual design reference. The playable environment should be constructed from game assets and world objects rather than using the reference image as a static background.

## Repository

**GitHub:** https://github.com/sharpp08/cprog-phygame

---

<p align="center">
<strong>WHEN THE WOODS BLEED</strong><br>
<em>The forest remembers. The dead awaken. Survival is only the beginning.</em>
</p>
