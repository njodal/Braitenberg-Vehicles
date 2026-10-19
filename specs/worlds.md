# Worlds

## Summary

A **world** is the environment a simulation runs in: the arena, the stimuli in it, the vehicles placed in it and the simulation settings. Worlds are described in YAML files and loaded at startup, so experiments are changed by editing or picking a file, not by editing code.

World files live in the `worlds/` folder. Each vehicle ships with at least one world, e.g. `worlds/vehicle1-hot-spot.yaml`.

## Running a world

```
python -m braitenberg.vehicle1 worlds/vehicle1-hot-spot.yaml
python -m braitenberg.vehicle1 worlds/vehicle1-hot-spot.yaml --headless --steps 100000
```

- If no file is given, the vehicle module loads its default world.
- `--seed N` overrides `simulation.seed`, so the same world can be rerun with different randomness without copying the file.

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

vehicles:
  - type: vehicle1
    position: [20, 20]
    heading: 0           # degrees, 0 = +x, counterclockwise
    sensor: temperature  # which stimulus the sensor reads
    params:              # overrides the vehicle's defaults from its spec
      gain: 1.0
      noise_std: 0.3

simulation:
  dt: 0.05
  seed: 0
```

### Sections

| Section | Required | Content |
|---|---|---|
| `name`, `description` | `name` required | Human-readable; the renderer shows `name` in the window title. |
| `arena` | yes | `width`, `height` (positive numbers) and `edges` (`wrap` or `bounce`, default `wrap`). Origin at the bottom-left corner, y pointing up. |
| `stimuli` | yes | A map from stimulus name (e.g. `temperature`, `light`, `oxygen`) to its definition. A world may have several stimuli; later vehicles have sensors for different ones. |
| `vehicles` | yes | A list of vehicles. Each has a `type` (the vehicle module, e.g. `vehicle1`), initial `position` and `heading`, the stimulus each sensor reads, and optional `params` overriding the defaults in that vehicle's spec. Vehicle-specific keys are defined in each vehicle's spec. |
| `simulation` | no | `dt` (default 0.05) and `seed` (default 0). |

### Stimuli and sources

Each stimulus has a list of `sources`. Each source has:

- `position`: `[x, y]` inside the arena.
- `intensity`: value at the source itself.
- `falloff`: distance at which the value drops to half.

Field value at a point = sum over the stimulus' sources of `intensity / (1 + (distance / falloff)^2)`. With `edges: wrap`, distance is measured on the torus (the shortest way around).

A stimulus with an empty `sources` list is zero everywhere.

## Loading and validation

- Parse with `yaml.safe_load` (PyYAML), then validate into typed Python objects (dataclasses) before the simulation starts. The simulation never reads raw dictionaries.
- Fail fast with a clear message naming the file and the offending key when:
  - a required key is missing or has the wrong type;
  - an unknown key appears (catches typos such as `falof`);
  - a position lies outside the arena;
  - a vehicle refers to a stimulus not defined in `stimuli`, or to an unknown vehicle `type` or parameter.
- Defaults are applied by the loader, so the rest of the code sees a complete world.
- The world model lives in the simulation side (`world.py`) and must not import pygame.

## Runtime changes

The renderer may let the user move sources, pause or add vehicles during a run. These changes affect only the running simulation, not the file. Saving the current state back to YAML is out of scope for now.

## Acceptance criteria

1. **Round trip:** loading the example file above produces a world whose arena, stimuli, vehicles and settings match the file.
2. **Defaults:** a file that omits `edges`, `simulation` and vehicle `params` loads with the documented defaults.
3. **Validation:** each failure case listed under *Loading and validation* raises an error whose message names the file and the key.
4. **Field values:** for a single source, the field equals `intensity` at the source and `intensity / 2` at distance `falloff`.
5. **Wrapped distance:** with `edges: wrap`, a point near the left edge is affected by a source near the right edge as if they were close.
6. **Seed override:** `--seed` replaces `simulation.seed`, and two runs of the same world and seed produce identical results.
7. **Headless:** loading a world and running it never imports pygame.

## Out of scope

- Obstacles and walls inside the arena.
- Moving or time-varying sources.
- Fields that are not built from point sources (e.g. gradients, images).
- Saving a running simulation back to a world file.
