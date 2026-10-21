# Worlds

## Summary

A **world** is the environment a simulation runs in: the arena and the stimuli in it. Worlds are described in YAML files, so environments are changed by editing or picking a file, not by editing code.

World files live in the `worlds/` folder, e.g. `worlds/hot-spot.yaml`. A world does not place vehicles or hold simulation settings; a scenario does both ([scenarios.md](scenarios.md)).

## File format

```yaml
name: Hot spot
description: One heat source in the middle of the arena.

arena:
  width: 100
  height: 100
  edges: wrap            # wrap | bounce

stimuli:
  temperature:           # stimulus name; sensors refer to it by this name
    sources:
      - position: [50, 50]
        intensity: 10
        falloff: 15
```

### Sections

| Section | Required | Content |
|---|---|---|
| `name`, `description` | `name` required | Human-readable. |
| `arena` | yes | `width`, `height` (positive numbers) and `edges` (`wrap` or `bounce`, default `wrap`). Origin at the bottom-left corner, y pointing up. |
| `stimuli` | yes | A map from stimulus name (e.g. `temperature`, `light`, `oxygen`) to its definition. A world may have several stimuli; a sensor's `type` names the stimulus it reads ([vehicle-definition.md](vehicle-definition.md)). |

### Stimuli and sources

Each stimulus has a list of `sources`. Each source has:

- `position`: `[x, y]` inside the arena.
- `intensity`: value at the source itself.
- `falloff`: distance at which the value drops to half.
- `schedule` (optional): when the source is on (see *Schedules*). Without it the source is always on.
- `radius` and `height` (optional): make the source a thing that cameras see, an upright cylinder standing on the ground ([camera.md](camera.md), *Things*). `height` needs a `radius` and defaults to `2 * radius`. They change nothing about the field.

Field value at a point = sum over the stimulus' **active** sources of `intensity / (1 + (distance / falloff)^2)`. With `edges: wrap`, distance is measured on the torus (the shortest way around).

A stimulus with an empty `sources` list, or whose sources are all off, is zero everywhere.

### Schedules

A source with a `schedule` switches on and off on a fixed cycle, like a traffic light:

```yaml
stimuli:
  red:
    sources:
      - position: [50, 13]
        intensity: 10
        falloff: 15
        schedule: {period: 16, on_at: 0, off_at: 8}    # on for the first 8 s of every 16 s
  green:
    sources:
      - position: [50, 13]
        intensity: 10
        falloff: 15
        schedule: {period: 16, on_at: 8, off_at: 16}   # on for the other 8 s
```

| Key | Meaning |
|---|---|
| `period` | Length of the cycle, in seconds of simulated time. Positive. |
| `on_at` | Time within the cycle when the source switches on, from 0 to `period`. |
| `off_at` | Time within the cycle when it switches off, from 0 to `period`. |

At simulated time `t`, let `c = t mod period`. With `on_at < off_at` the source is on while `on_at <= c < off_at`. With `on_at > off_at` the cycle wraps: the source is on while `c >= on_at` or `c < off_at`. `on_at` and `off_at` must differ. (The keys are not `on` and `off` because YAML reads those as `true` and `false`.)

A source that is off contributes nothing to its stimulus; nothing else about it changes. The renderer draws active sources filled and inactive ones as hollow rings (in that color when the stimulus is named after one, such as `red` or `green`, and on top of other sources at the same place, so a red lamp that is also hot shows red), lists which scheduled stimuli are on, and its heat map follows them as they switch.

### Edges

When a vehicle moves past an edge:

- `wrap`: it reappears on the opposite side.
- `bounce`: it is reflected back into the arena and its heading is mirrored.

## Loading and validation

- Parse with `yaml.safe_load` (PyYAML), then validate into typed Python objects (dataclasses) before the simulation starts. The simulation never reads raw dictionaries.
- Fail fast with a clear message naming the file and the offending key when:
  - a required key is missing or has the wrong type;
  - an unknown key appears (catches typos such as `falof`, and `vehicles` or `simulation` sections, which belong in scenarios);
  - a source position lies outside the arena;
  - a `schedule` is missing a key, has a non-positive `period`, has `on_at` or `off_at` outside `[0, period]`, or has `on_at` equal to `off_at`.
  - a source's `radius` or `height` is not a positive number, or it has a `height` without a `radius`.
- Defaults are applied by the loader, so the rest of the code sees a complete world.
- The world model lives in the simulation side (`world.py`) and must not import pygame.

## Runtime changes

The renderer lets the user move sources during a run. These changes affect only the running simulation, not the file.

## Acceptance criteria

1. **Round trip:** loading the example file above produces a world whose arena and stimuli match the file.
2. **Defaults:** a file that omits `edges` loads with `wrap`.
3. **Validation:** each failure case listed under *Loading and validation* raises an error whose message names the file and the key.
4. **Field values:** for a single source, the field equals `intensity` at the source and `intensity / 2` at distance `falloff`.
5. **Wrapped distance:** with `edges: wrap`, a point near the left edge is affected by a source near the right edge as if they were close.
6. **Schedules:** a scheduled source contributes to its stimulus exactly while it is on, as defined in *Schedules*, including a cycle that wraps (`on_at > off_at`); a source without a schedule is always on.

## Out of scope

- Obstacles and walls inside the arena.
- Moving sources, and sources whose intensity changes gradually rather than switching on and off.
- Fields that are not built from point sources (e.g. gradients, images).
- Saving a running simulation back to a world file.
