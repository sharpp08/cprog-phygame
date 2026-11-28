# Environment Overhaul

The playable forest is now 96 × 96 tiles (4× the previous 48 × 48 area). Generation remains deterministic by seed and retains the shrine, pond, lily pads, bridge, waterfall, ruin, starting camp, loot and shrine-wave progression.

## World generation
- Winding, interconnected trails connect the starting camp, shrine and remote clearings.
- Clustered tree placement uses seven existing tree variants and per-tree scale/collision radii.
- Additional boulders, bushes, fallen timber, exposed roots and irregular dirt patches add environmental variation.
- A smooth low-relief height field adds subtle hills, slopes and a pond basin.

## Collision and navigation
- Tree cells remain blocked to A* while continuous movement resolves against circular trunk colliders.
- Other solid obstacles and water retain grid collision; out-of-bounds space remains solid.
- A* expansion limits scale with map size, diagonal corner cutting remains disabled, and zero-distance steering is guarded.
- Spawn points are normalized to nearby clear tiles; local cover queries use the obstacle spatial index.

## Rendering and performance
- Ground tiles, actors, pickups and obstacles use sampled terrain elevation.
- Fallen logs and exposed roots are inexpensive procedural primitives; existing tree, rock, bush and ruin sprites are reused.
- Obstacle visibility uses 12-tile spatial buckets, in addition to the renderer's camera culling and sprite caches.
- Existing weather, fog, flashlight, lighting and post-processing systems remain active.

## Validation
The environment test module covers deterministic map size/density, start-to-shrine connectivity, circular tree collision, elevation bounds, spawn-point reachability, obstacle culling and path clearance. Full graphics validation remains hardware-independent; a live FPS benchmark must be measured on the target PC.
