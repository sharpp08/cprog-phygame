"""CPROG PHYGAME - Global configuration and tuning constants.

Central place for all adjustable values. Modules import from here so the
game's balance, resolution and behaviour can be tuned in one location.
"""
from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(PROJECT_ROOT, "saves")
ASSET_DIR = os.path.join(PROJECT_ROOT, "assets")

# ---------------------------------------------------------------------------
# Window / display
# ---------------------------------------------------------------------------
DEFAULT_RES = (1280, 720)
MIN_RES = (960, 540)
MAX_RES = (1920, 1080)
RESDIC = {
    "800x450": (800, 450),
    "960x540": (960, 540),
    "1280x720": DEFAULT_RES,
    "1600x900": (1600, 900),
    "1920x1080": (1920, 1080),
}
FPS = 60
WINDOW_TITLE = "CPROG PHYGAME - Isometric Zombie Survival"

# Graphics quality levels: Low disables fog/fireflies/water-anim/light rays,
# Medium enables them, High adds contact AO and more particles.
QUALITY = ("low", "medium", "high")

# ---------------------------------------------------------------------------
# Isometric projection (2:1 diamond tiles)
#   screen_x = (world_x - world_y) * SCALE_X
#   screen_y = (world_x + world_y) * SCALE_Y - world_z * HEIGHT_SCALE
# ---------------------------------------------------------------------------
TILE_W = 64          # full diamond width in pixels
TILE_H = 32         # full diamond height in pixels
SCALE_X = TILE_W / 2.0    # 32
SCALE_Y = TILE_H / 2.0    # 16
HEIGHT_SCALE = 1.0       # world Z -> pixels
SCALE_Z = HEIGHT_SCALE    # obstacle Z offset used by the renderer

# ---------------------------------------------------------------------------
# Map / world
# ---------------------------------------------------------------------------
MAP_W = 48         # map width in tiles
MAP_H = 48         # map height in tiles

# Tile / surface kinds
T_GRASS = 0
T_DIRT = 1
T_PATH = 2
T_WATER = 3
T_BRIDGE = 4
T_LILY = 5
T_ROCK = 6         # water edge / rock ledge

# Obstacle classes (grid collision)
BLOCK_NONE = 0
BLOCK_SOLID = 1
BLOCK_WATER = 2    # water is solid for ground movement (can't wade)

# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------
CAM_MIN_ZOOM = 0.6
CAM_MAX_ZOOM = 1.8
CAM_DEFAULT_ZOOM = 1.15
CAM_FOLLOW_SMOOTH = 4.0      # higher = snappier follow
CAM_MARGIN = 4.0            # world-space clamp margin around the map


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------
PLAYER_WALK_SPEED = 3.2     # world tiles / second
PLAYER_RUN_SPEED = 5.6
PLAYER_TURN_SMOOTH = 20.0   # direction smoothing
PLAYER_MAX_HP = 100
PLAYER_INVULN = 0.6        # seconds of i-frames after being hit
PLAYER_RADIUS = 0.42      # collision radius in tiles

# ---------------------------------------------------------------------------
# Weapons  (tunable stats, referenced by entities.weapon)
# ---------------------------------------------------------------------------
WEAPONS = {
    "pistol": {
        "name": "Pistol", "fire_mode": "semi", "damage": 24,
        "fire_rate": 3.0,           # shots / second
        "range": 16.0,              # tiles
        "mag_size": 12, "reserve_max": 60,
        "reload_time": 1.1, "spread": 0.02, "pellets": 1,
        "bullet_speed": 26.0, "recoil": 0.10, "ammo_type": "pistol",
        "color": (210, 190, 150),
    },
    "shotgun": {
        "name": "Shotgun", "fire_mode": "semi", "damage": 14,
        "fire_rate": 1.4,
        "range": 8.0,
        "mag_size": 6, "reserve_max": 24,
        "reload_time": 1.9, "spread": 0.34, "pellets": 7,
        "bullet_speed": 22.0, "recoil": 0.5, "ammo_type": "shotgun",
        "color": (230, 170, 110),
    },
    "rifle": {
        "name": "Assault Rifle", "fire_mode": "auto", "damage": 16,
        "fire_rate": 9.0,
        "range": 20.0,
        "mag_size": 30, "reserve_max": 120,
        "reload_time": 2.2, "spread": 0.05, "pellets": 1,
        "bullet_speed": 34.0, "recoil": 0.07, "ammo_type": "rifle",
        "color": (190, 200, 220),
    },
}
WEAPON_ORDER = ("pistol", "shotgun", "rifle")

# ---------------------------------------------------------------------------
# Zombies
# ---------------------------------------------------------------------------
ZOMBIE_TYPES = {
    "regular": {
        "hp": 60, "speed": 1.6, "damage": 10, "attack_cd": 0.9,
        "range": 1.0, "color": (110, 140, 90), "score": 10,
        "radius": 0.42, "detect": 11.0,
    },
    "fast": {
        "hp": 34, "speed": 3.3, "damage": 8, "attack_cd": 0.6,
        "range": 1.0, "color": (150, 120, 80), "score": 18,
        "radius": 0.38, "detect": 15.0,
    },
    "tank": {
        "hp": 240, "speed": 0.9, "damage": 26, "attack_cd": 1.4,
        "range": 1.25, "color": (70, 95, 70), "score": 45,
        "radius": 0.6, "detect": 12.0,
    },
}
ZOMBIE_START_COUNT = 12
ZOMBIE_MAX_ACTIVE = 42
WAVE_SPAWN_INTERVAL = 6.0     # seconds between spawn surges (phase 1)

# ---------------------------------------------------------------------------
# Pickups
# ---------------------------------------------------------------------------
PICKUP_TYPES = {
    "ammo_pistol": {"color": (150, 140, 90), "value": 36},
    "ammo_shotgun": {"color": (170, 130, 90), "value": 12},
    "ammo_rifle": {"color": (150, 160, 190), "value": 48},
    "medkit": {"color": (230, 70, 70), "value": 40},
    "weapon_shotgun": {"color": (210, 180, 120), "value": 1},
    "weapon_rifle": {"color": (200, 210, 230), "value": 1},
}

# ---------------------------------------------------------------------------
# Progression / waves
# ---------------------------------------------------------------------------
SHRINE_POS = (24, 24)        # world tile centre of the shrine landmark
WAVES_AT_SHRINE = 3         # final waves to survive at the shrine
WAVE_BASE_COUNT = 8
WAVE_GROWTH = 1.7

# ---------------------------------------------------------------------------
# Lighting / atmosphere
# ---------------------------------------------------------------------------
SUN_DIR = (0.55, 0.35)       # shadow direction (world offset per height)
SHADOW_LENGTH = 0.55
NIGHT_DARKNESS = 0.42        # base ambient darkness strength
LIGHT_RADIUS_PLAYER = 7.5
LIGHT_RADIUS_SHRINE = 10.0
PARTICLE_LIMIT = 520

# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------
MASTER_VOL = 0.9
MUSIC_VOL = 0.55
SFX_VOL = 0.9

# ---------------------------------------------------------------------------
# Compat aliases used by the engine / UI (kept in one place)
# ---------------------------------------------------------------------------
WINDOW_W, WINDOW_H = DEFAULT_RES
TARGET_FPS = FPS
MIN_FPS = 5
RESOLUTIONS = [v for v in RESDIC.values()]        # list of (w, h) tuples
DEFAULT_RESOLUTION = RESOLUTIONS.index(DEFAULT_RES)
FULLSCREEN = False
DEFAULT_ZOOM = CAM_DEFAULT_ZOOM
ZOOM_MIN = CAM_MIN_ZOOM
ZOOM_MAX = CAM_MAX_ZOOM
WINDOW_CAPTION = WINDOW_TITLE

