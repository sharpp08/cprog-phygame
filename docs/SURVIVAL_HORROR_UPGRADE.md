# Survival horror upgrade – implementation notes

This branch improves reliability and combat behavior without replacing the existing
isometric game systems or generated assets.

## Changes in this upgrade

- **Portable saves:** save/settings data use a per-user writable directory
  (`%APPDATA%/CPROG-PhyGame` on Windows, or the platform data directory elsewhere).
  Set `CPROG_PHYGAME_DATA_DIR` to override it for portable installs or tests.
- **Atomic save writes:** snapshots are written to a temporary file and atomically
  replaced, preventing interrupted writes from corrupting the previous save.
- **Save validation:** malformed structures, non-finite coordinates/health and
  zero-health runs are rejected before world restoration.
- **Correct Continue behavior:** a defeated run is deleted instead of leaving a
  zero-HP save behind. Returning to the main menu while alive still saves progress.
- **Coordinated approach lanes:** pursuing infected alternate their approach angle
  and radius, encouraging surrounding pressure rather than a single queue.

## Existing systems retained

The project already contains eight infected archetypes, A* navigation, line-of-sight
and sound perception, stealth/crouch behavior, group alerts, horde pacing, weapon
recoil/spread/reload, crafting and survival resources, weather, flashlight lighting,
particles, procedural audio, post-processing and quality presets. This upgrade
keeps those systems and their existing assets intact.

## Validation checklist

Run from the repository root with Python 3.12:

```powershell
python -m unittest discover -s tests -v
python tools/bench_micro.py
python tools/bench_post.py
```

Then manually verify:
1. Save by returning alive to the main menu, restart, and choose Continue.
2. Die and verify Continue is no longer offered for that defeated run.
3. Change resolution/fullscreen/quality/volumes, restart, and confirm settings persist.
4. Test each quality preset and weather state on integrated graphics.
5. Confirm enemies approach from different directions without walking through blocked tiles.

The 60 FPS objective remains a measured target; it is not claimed as achieved until
profiling is run on the target hardware.