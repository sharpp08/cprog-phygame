# 🌲 WHEN THE WOODS BLEED
### Isometric 2.5D Zombie Survival Horror

> The forest remembers. The dead awaken. Survival is only the beginning.

**WHEN THE WOODS BLEED** is an in-development, single-player isometric survival-horror shooter built with Python and Pygame-ce. Explore a hostile forest, manage scarce supplies, fight different infected, and survive the waves around an ancient shrine.

> **Development status:** Active development. Features documented here reflect the current project implementation; balance, assets, and controls may change as development continues.

---

## Table of Contents

- [Game Overview](#game-overview)
- [World and Visual Design](#world-and-visual-design)
- [Gameplay Features](#gameplay-features)
- [Controls](#controls)
- [Weapons, Equipment, and Survival](#weapons-equipment-and-survival)
- [Character Animations](#character-animations)
- [Menus and Settings](#menus-and-settings)
- [Atmosphere and Rendering](#atmosphere-and-rendering)
- [Technology and Project Structure](#technology-and-project-structure)
- [Setup and Installation](#setup-and-installation)
- [Testing and Development](#testing-and-development)
- [Assets and Licensing](#assets-and-licensing)

## Game Overview

| Category | Details |
|---|---|
| Title | WHEN THE WOODS BLEED |
| Genre | Survival horror / zombie action shooter |
| Perspective | Isometric 2.5D |
| Language | Python |
| Framework | Pygame-ce |
| Rendering | Software-rendered 2D with optional shader support |
| Target platform | Windows 10/11 |
| Game mode | Single-player |
| Simulation target | 60 updates per second; rendering is capped separately |
| Status | In development |

## World and Visual Design

The game is set in an overgrown forest surrounding an isolated shrine. Its visual identity uses a dark, moonlit palette with muted greens, deep blue-green shadows, weathered earth, and restrained amber light.

### Forest-shrine environment

The environment is built from procedural and cached game assets rather than using a static screenshot as the playable background. Its landmarks and visual elements include:

- **Ancient wooden shrine:** A small shrine with a distinctive red roof, serving as a focal point in the forest.
- **Forest clearing:** An open, overgrown space framed by dense trees and vegetation.
- **Sacred pond:** Green water, lily pads, reflective highlights, and a surrounding natural edge.
- **Stone routes and bridge areas:** Paths that connect the forest spaces and landmarks.
- **Waterfall and water features:** Animated water details, ripples, and mist.
- **Dense woodland:** Layered trees, rocks, bushes, roots, grass, and natural obstacles.

### Main menu atmosphere

The main menu now uses a forest scene that reflects the actual game setting: a moonlit clearing, layered tree silhouettes and trunks, a shrine landmark, a pond, a worn trail, drifting ground fog, and subtle cloud movement. The information panel presents a survival status for the Shrine Sector and the objective to survive the waves. The menu retains **New Game**, **Continue**, **Settings**, and **Exit**.

## Gameplay Features

### Movement and combat

- Isometric player movement using WASD or the arrow keys.
- Mouse-directed aiming and left-click shooting.
- Walking, sprinting, and crouching, with movement easing and collision-aware animation.
- Weapon selection, ammunition management, and reloading.
- Projectile collision with enemies and solid world obstacles.
- Melee attacks and throwable grenades.
- Health, damage feedback, and survival resources.

### Infected and horror systems

The game includes multiple infected archetypes with different movement and combat characteristics, including regular infected, Runners, Brutes/Tanks, Crawlers, Exploders, Stalkers, Screamers, and Armored infected.

Current enemy and horror behaviors include:

- Detection and pursuit, with solid geometry blocking line of sight.
- Player visibility and noise affected by crouching, flashlight use, and weather.
- Investigation of sound and alerts shared between nearby infected.
- Gunfire-attracted horde pressure and managed spawn pacing.
- Different enemy durability, speed, and special behaviors.
- An adaptive horror director that responds to nearby threats, player condition, ammunition pressure, noise, and survival time.
- Environmental audio cues and tension/recovery pacing.

### Exploration and progression

- Search the forest for pickups and supplies.
- Investigate discoverable clues at landmarks.
- Collect scrap from defeated enemies.
- Craft and use medical supplies.
- Maintain flashlight charge and replace depleted cells.
- Save/load support for player progress and survival resources.
- Shrine-related story outcomes influenced by discovered clues.

## Controls

The following are the current keyboard and mouse controls.

| Input | Action |
|---|---|
| **W / A / S / D** or **Arrow keys** | Move |
| **Mouse movement** | Aim |
| **Left mouse button** | Fire current weapon |
| **Left Shift / Right Shift** | Sprint (consumes stamina) |
| **Left Ctrl / Right Ctrl** | Crouch (slower movement, reduced noise and visibility) |
| **1 / 2 / 3** | Select weapon slot |
| **R** | Reload |
| **F** | Toggle flashlight |
| **B** | Replace flashlight cell |
| **Q** | Melee attack |
| **G** | Throw grenade |
| **H** | Use a medkit (restores up to 40 HP) |
| **C** | Craft a medkit (costs 3 scrap) |
| **E** | Investigate a nearby story clue |
| **Esc / P** | Pause or open the pause menu |
| **F1** | Toggle debug display |

Some actions require the relevant item or resource. For example, battery replacement requires a spare cell, grenade throwing requires a grenade, and medkit use requires a stored medkit and missing health.

## Weapons, Equipment, and Survival

### Weapons

The player can switch between available weapon slots with **1**, **2**, and **3**. The weapon set includes a pistol, shotgun, and assault rifle. Each weapon has its own firing characteristics, ammunition, reload behavior, and audio feedback.

### Equipment

| Equipment | Key | Current behavior |
|---|---|---|
| Knife / melee | **Q** | Close-range directional strike with a cooldown; the equipped firearm remains selected |
| Grenade | **G** | Throws toward the current aim direction; detonates after a short fuse and damages nearby infected |
| Medkit | **H** | Consumes a stored medkit to restore up to 40 HP |
| Craft medkit | **C** | Uses 3 scrap to craft and store a medkit |
| Flashlight | **F** | Illuminates the surroundings and consumes battery charge while active |
| Spare flashlight cell | **B** | Replaces the depleted/low cell when a spare is available |

Equipment counts and survival information are shown in the HUD. Pickups and saved game data preserve supported inventory and resource state.

### Survival mechanics

- **Health:** Damage reduces player health; temporary invulnerability prevents consecutive hits from registering instantly.
- **Stamina:** Sprinting consumes stamina. Resting allows it to recover; sprinting is restricted when exhausted.
- **Stealth:** Crouching slows movement, reduces footstep noise, and makes the player harder for infected to detect.
- **Flashlight battery:** The flashlight drains while active. Turning it off conserves charge; spare cells can be collected and installed.
- **Scrap and crafting:** Scrap collected from defeated enemies can be spent to craft a medkit.

## Character Animations

Player animation states are separated so actions do not incorrectly reuse locomotion frames:

- **Idle:** Dedicated idle animation.
- **Walking:** Dedicated movement cycle.
- **Running:** Dedicated sprint cycle.
- **Crouching:** Separate crouch-down transition, crouch-idle loop, and crouch-up transition.
- **Firing:** Dedicated firing sprite animation while shooting.
- **Reloading:** Dedicated reload sprite animation while reloading.
- **Damage and death:** Separate reaction states.

The player animation system blends between states and uses actual collision-resolved movement to drive locomotion, helping prevent foot sliding when blocked by obstacles. Crouch animation uses a smaller fitted sprite scale so it remains visually consistent with the other player poses.

The infected also have distinct movement cycles and animation styles suited to their archetypes.

## Menus and Settings

### Main menu

- **New Game** starts a new run.
- **Continue** loads an available save; it is disabled when no save is present.
- **Settings** opens the configuration screen.
- **Exit** closes the game.

A loading screen is shown during world initialization, followed by a transition into the menu/game presentation.

### Settings

The settings interface is organized into **Sound & Camera** and **Display & Graphics** sections.

| Setting | Behavior |
|---|---|
| Master volume | Adjusts overall audio level |
| Music volume | Adjusts music independently |
| SFX volume | Adjusts sound effects independently |
| Camera zoom | Changes camera zoom within the supported range |
| Resolution | Cycles through supported display resolutions |
| Fullscreen | Toggles fullscreen mode |
| Graphics quality | Selects Low, Medium, High, or Ultra |
| Post processing | Auto / On / Off |

Settings are saved separately from the game save in `saves/settings.json` and loaded on startup. Audio and camera changes apply as they are adjusted; display and graphics changes are applied through the settings workflow.

## Atmosphere and Rendering

The renderer combines cached procedural assets with atmospheric effects designed for the forest setting.

- Layered forest silhouettes and detailed environmental objects.
- Isometric terrain, depth sorting, and camera-aware visibility.
- Nighttime color grading, ambient darkness, and a directional flashlight.
- Fog and ground mist, fireflies, film grain, vignette, and restrained post-processing.
- Animated water ripples, waterfall mist, leaves, dust, embers, and foliage movement.
- Dynamic weather including mist, rain, wind gusts, lightning, and synthesized thunder.
- Camera shake and visual/audio tension effects during horror events.
- Quality presets that scale visual effects for different hardware.
- Optional shader support with a software/NumPy fallback.

The HUD is rendered after the cinematic scene effects so that gameplay information remains readable.

## Technology and Project Structure

### Technology stack

| Technology | Purpose |
|---|---|
| Python 3.12 | Primary language used for development |
| Pygame-ce | Window, input, rendering, and audio |
| NumPy | Numerical and image-processing operations |
| ModernGL | Optional shader validation/acceleration support |
| Git / GitHub | Version control and source hosting |

### Main directories

```text
cprog-phygame/
├── main.py                 # Application entry point
├── config.py               # Shared configuration and tuning
├── engine/                 # Game loop, camera, renderer, assets, audio, input
├── entities/               # Player, enemies, weapons, bullets, pickups
├── systems/                # Combat, AI, inventory, survival, story, saves
├── world/                  # Map, terrain, environment, obstacles
├── ui/                     # Menus, HUD, settings, loading screen
├── graphics/               # Shader and post-processing support
├── assets/                 # Sprites, references, audio, and other assets
├── tests/                  # Automated tests
└── .github/workflows/      # CI workflows
```

The codebase is organized by responsibility so that gameplay systems, world simulation, rendering, and interface code can be maintained independently.

## Setup and Installation

### Requirements

- Windows 10 or Windows 11.
- Python 3.12 (recommended for the current development environment).
- Git.
- pip.

### 1. Clone the repository

```bash
git clone https://github.com/sharpp08/cprog-phygame.git
cd cprog-phygame
```

### 2. Create and activate a virtual environment

PowerShell:

```powershell
python -m venv .venv
.venv\\Scripts\\Activate.ps1
```

Command Prompt:

```cmd
python -m venv .venv
.venv\\Scripts\\activate.bat
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Launch the game

```bash
python main.py
```

If PowerShell blocks virtual-environment activation, use the appropriate execution policy for your machine or activate the environment through Command Prompt.

## Testing and Development

Run the automated test suite from the repository root:

```bash
python -m unittest discover -v
```

Compile-check the Python source files:

```bash
python -m compileall -q .
```

The repository includes a GitHub Actions workflow for automated checks. A successful code update should still be tested in the actual game, particularly for rendering, animation transitions, settings changes, and combat interactions. Performance depends on the user's hardware and scene complexity; no universal FPS guarantee is made.

### Development guidelines

1. Keep gameplay calculations in world space and rendering/UI placement in the appropriate coordinate space.
2. Keep systems modular and avoid unnecessary dependencies.
3. Preserve the separation between idle, locomotion, firing, and reload animations.
4. Profile performance before removing visual features or adding costly effects.
5. Verify third-party asset licenses before redistribution.
6. Update this README when controls or implemented features change.
7. Do not describe planned or untested behavior as verified.

## Assets and Licensing

Use original, properly licensed, or public-domain assets. Verify redistribution rights for sprites, textures, audio, fonts, and other third-party resources before including them in public releases. Keep source references and license information with the project where appropriate.

The forest-shrine reference is a visual guide. The playable world is assembled from game terrain, objects, and procedural assets rather than using the reference image as a flat background.

## Repository

**GitHub:** https://github.com/sharpp08/cprog-phygame

---

<p align="center">
<strong>WHEN THE WOODS BLEED</strong><br>
<em>The forest remembers. The dead awaken. Survival is only the beginning.</em>
</p>
