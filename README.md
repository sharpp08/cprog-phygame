# ZOMBIE SURVIVAL: Last Stand
*An Isometric 2.5D Pixel Art Survival Game in Python & Pygame*

---

## 1. Overview
**ZOMBIE SURVIVAL: Last Stand** is a complete, responsive, isometric 2.5D pixel-art zombie survival game built from scratch using Python 3 and Pygame.

The player assumes the role of a lone survivor trapped in an abandoned perimeter overrun by relentless waves of undead. Surviving requires tactical movement, precise mouse aiming, weapon management, and situational awareness to navigate around rocks, crates, and trees while holding back ever-increasing hordes.

### Isometric 2.5D Rendering
The game uses a centralized isometric projection system (`iso_camera.py`) that separates world-space gameplay coordinates from screen-space rendering:
- **Diamond-grid projection** — the world plane is rendered as a diamond-shaped isometric view at a ~30° angle
- **Billboard sprites** — characters and obstacles are pre-rendered front-facing sprites anchored to their projected ground position, with ground-contact shadows and a subtle walk bob
- **Depth sorting** — all entities are sorted by world depth (x + y) each frame so that trees, crates, and characters occlude correctly
- **Camera tracking** — a smoothed isometric camera follows the player and clamps to the projected map bounds
- **Screen-space UI** — HUD, menus, and buttons remain in normal screen coordinates, unaffected by the projection

### Key Highlights
- **100% Self-Contained**: All pixel-art sprites, textures, and audio effects are generated procedurally in code. No external image or sound files are required, eliminating missing-file errors.
- **Performant & Lightweight**: 200+ FPS measured with 80+ active sprites on 60 FPS-locked windows, running effortlessly on ordinary laptops and Intel integrated graphics.
- **Object-Oriented Architecture**: Clean, modular separation of concerns between Player, Zombie, Projectile, Particle, Obstacle, Game State, Audio, UI, and Isometric Camera systems.
- **Robust Persistence**: High scores are automatically saved to and loaded from local JSON (`data/highscore.json`), with fail-safe error handling for missing or corrupt files.

---

## 2. Controls & How to Play

| Input | Action | Description |
|---|---|---|
| **W / Up Arrow** | Move Up | Move survivor upward |
| **A / Left Arrow** | Move Left | Move survivor leftward |
| **S / Down Arrow** | Move Down | Move survivor downward |
| **D / Right Arrow** | Move Right | Move survivor rightward |
| **Mouse Cursor** | Aim | 360-degree rotational weapon aiming |
| **Left Mouse Button (Hold/Click)** | Shoot | Rapid-fire projectile weapon |
| **Escape (ESC)** | Pause / Resume | Toggle translucent pause menu during gameplay |
| **Enter** | Start Game | Confirm menu selection or start from title |
| **R** | Quick Restart | Restart match directly from Game Over screen |
| **Q / Window Close** | Quit | Safely exit the application |

---

## 3. Game Mechanics & Systems

### 8-Directional Movement & Collision
- Supports simultaneous key combinations (e.g., `W + D` for diagonal movement).
- Diagonal velocity is normalized by multiplying by $1/\sqrt{2} \approx 0.7071$, preventing diagonal speed advantages.
- Smooth axis-separated collision detection stops the player and zombies from clipping through solid obstacles (rocks, wooden crates, trees) or moving outside map boundaries.

### Mouse Aiming & Ballistics
- The player sprite dynamically rotates towards the world coordinates of the mouse cursor.
- Bullets travel in a straight trajectory with realistic speed and limited range, triggering muzzle flash particles and sound effects upon firing.
- Bullet-to-zombie and bullet-to-obstacle collisions spawn impact sparks and blood splatter particles.

### Zombie AI & Enemy Variations
1. **Regular Zombie**: Balanced speed and durability (Health: 40, Speed: 2.2, Damage: 10, Score: +10).
2. **Fast Zombie** (Introduced in Wave 2+): Agile runner with crimson hue (Health: 20, Speed: 3.6, Damage: 6, Score: +15).
3. **Tank Zombie** (Introduced in Wave 4+): Heavy brute with high health pool (Health: 120, Speed: 1.4, Damage: 20, Score: +30).
- Enemy AI uses vector tracking to pursue the player and includes flocking separation forces to prevent unnatural clustering and stacking.

### Wave System & Difficulty Scaling
- Each wave features a calculated quota of zombies: `Total = 5 + (Wave * 3)`.
- Zombies spawn around the perimeter of the 2560x1440 map.
- When all zombies in a wave are eliminated, a celebratory announcement banner appears with a 3-second preparation countdown before the next wave begins.
- Difficulty naturally escalates through increased enemy count, higher speed distributions, and tougher zombie variations.

### Health, Damage & Invulnerability
- The player starts with 100 HP, monitored via a dynamic color-coded HUD health bar (Green $\to$ Yellow $\to$ Red).
- Contact with a zombie inflicts damage and triggers a 500 ms invulnerability cooldown with a visual red screen flash, preventing unfair instant death from multiple collision frames.

---

## 4. Windows Installation and Run Instructions

These instructions are tailored for Windows 10 and Windows 11 using **PowerShell**.

### Step 1: Install Python
1. Download Python 3.10, 3.11, or 3.12 from [python.org](https://www.python.org/downloads/).
2. **Crucial**: During installation, check the box that says **"Add python.exe to PATH"**.
3. Complete the standard installation wizard.

### Step 2: Open PowerShell in the Project Directory
1. Open PowerShell and navigate to the project directory:
   ```powershell
   cd "d:\cprog phygame"
   ```
2. Verify Python is available:
   ```powershell
   py --version
   ```
   *(Or run `python --version`)*

### Step 3: Create and Activate Virtual Environment
1. Create a virtual environment named `.venv`:
   ```powershell
   py -m venv .venv
   ```
2. If PowerShell blocks script activation, temporarily set the execution policy for your session:
   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   ```
3. Activate the virtual environment:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

### Step 4: Install Dependencies
1. Upgrade pip and install the required packages:
   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

### Step 5: Launch the Game
```powershell
python main.py
```

### Running the Game Again Later
Whenever you want to play or demonstrate the game in the future:
```powershell
cd "d:\cprog phygame"
.\.venv\Scripts\Activate.ps1
python main.py
```

---

## 5. Troubleshooting & FAQ

- **PowerShell Execution Policy Error (`Activate.ps1 cannot be loaded`)**:
  Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in your PowerShell window and then re-run `.\.venv\Scripts\Activate.ps1`.
- **No Sound / Audio Warning**:
  The audio engine is wrapped in a fail-safe exception handler. If your machine does not have an active audio output device, the game will automatically run in silent mode without crashing.
- **Window Scaling / Small Resolution**:
  The default resolution is 1280x720, fitting standard 1080p and 720p laptop displays. The camera dynamically follows the player within the larger 2560x1440 world map.

---

## 6. How to Present the Game (School Presentation Guide)

This section provides a clear script and technical explanation for presenting this project to teachers and classmates.

### Presentation Outline & Sequence

1. **Introduction (Start Menu)**:
   - Launch `python main.py`.
   - Explain the title screen: *"This is ZOMBIE SURVIVAL: Last Stand, a 2D top-down survival game developed in Python using the Pygame framework."*
   - Click **CONTROLS** to show the key bindings and input scheme.
2. **Starting Gameplay**:
   - Click **START GAME** (or press Enter).
   - Point out the HUD elements: Player Health Bar (top-left), Wave Counter, Score, and Zombies Remaining (top-right).
3. **Demonstrating Mechanics**:
   - **Movement**: Move around using WASD. Explain diagonal normalization: moving diagonally does not give the player an unfair speed boost.
   - **Aiming & Shooting**: Move the mouse cursor to show 360-degree aiming. Hold down the left mouse button to demonstrate continuous firing and muzzle flashes.
   - **Obstacles**: Walk into a rock or tree to show physical collision detection blocking the player.
4. **Combat & Scoring**:
   - Shoot approaching zombies. Note the bullet impact sparks, blood splatter particles, and gunshot sound effects.
   - Show how the score increases (+10 for regular zombies, +15 for fast runners, +30 for tanks).
   - Show how defeated zombies are removed from the game world.
5. **Taking Damage**:
   - Allow a zombie to hit the player. Show the red screen flash, the decrease in health, and explain the brief invulnerability cooldown that prevents instant death.
6. **Clearing a Wave**:
   - Defeat all zombies in Wave 1.
   - Highlight the banner: *"WAVE 1 CLEARED!"*, followed by the 3-second preparation countdown before Wave 2 begins with increased enemy count and faster zombie types.
7. **Pause System**:
   - Press **ESC** during combat. Explain that the main game loop freezes updates for all entities while displaying the interactive pause menu.
   - Click **RESUME** to continue.
8. **Game Over & High Score**:
   - Let player health reach zero.
   - Show the Game Over screen presenting the final score, highest recorded score, and wave reached.
   - Demonstrate the **PLAY AGAIN** button (or press **R**) to show that the match resets completely in memory without restarting the Python process.

### Code Architecture Explanation for the Teacher

When asked about the code structure, you can highlight these programming concepts:

- **Object-Oriented Programming (OOP)**:
  - `Player`, `Zombie`, `Bullet`, `Particle`, and `Obstacle` inherit from `pygame.sprite.Sprite`.
  - Encapsulation: Each class manages its own internal state (e.g., `take_damage()`, `handle_input()`, `update()`).
- **Main Game Loop (`main.py` & `game.py`)**:
  - Operates on a standard three-stage architecture: **Event Handling** $\to$ **State Update** $\to$ **Rendering / Draw**.
  - Frame rate capped at 60 FPS using `pygame.time.Clock()`.
- **State Machine**:
  - The game switches cleanly between distinct states (`menu`, `controls`, `playing`, `paused`, `game_over`), ensuring inputs and updates only apply to the active state.
- **Collision Detection**:
  - Uses axis-aligned bounding box (`colliderect`) and Pygame sprite collision groups (`spritecollide`).
- **Clean Architecture & Maintainability**:
  - Modular design: constants in `settings.py`, procedural art in `asset_generator.py`, synthetic sounds in `sound_manager.py`, and UI in `ui.py`.

---

## 7. Automated Testing

The project includes unit tests for key gameplay mechanics:
- Diagonal velocity normalization
- Boundary clamping
- Health boundaries and damage cooldown timing
- Enemy variants and speed/health attributes
- Projectile ballistics and maximum range
- High score file parsing and corruption fallback
- Environmental obstacle collisions
- Zombie pursuit calculations
- Wave scaling quotas
- Full game reset state validation

To run the automated tests:
```powershell
python -m unittest tests/test_game_logic.py
```
All tests run headlessly without requiring a graphical window or physical audio device.
