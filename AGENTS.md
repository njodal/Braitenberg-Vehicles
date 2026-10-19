# AGENTS.md

Instructions for AI coding agents working in this repo.

## Project

An implementation of the Vehicles from Valentino Braitenberg's book *Vehicles: Experiments in Synthetic Psychology*. The focus is Vehicles 5 and beyond, the ones with a 'nervous system' between the sensors and the actuators. See [README.md](README.md).

## Specs

Specifications live in the `specs/` folder. Read the relevant spec before implementing a vehicle or feature.

## Programming environment

The project is written in Python 3.11 or later.

- **Simulation:** pure Python + `numpy`. Differential-drive kinematics are simple enough that no physics engine is needed.
- **Visualization:** `pygame-ce` (the community-maintained pygame fork), used for real-time rendering and interaction (moving sources, pausing, adding vehicles).
- **Configuration:** worlds are YAML files loaded with `PyYAML` (see [specs/worlds.md](specs/worlds.md)).
- **Analysis:** `matplotlib` for plotting internal state (neuron activity, weights, fitness) after runs.
- **Tests:** `pytest`. Every acceptance criterion in a spec gets at least one test. Tests run headless (no pygame window) and use fixed seeds so they are deterministic. Run them with `pytest` from the repo root.

## Project structure

```
pyproject.toml          # package metadata and dependencies
braitenberg/            # the package
  world.py              # arena, stimulus sources and fields
  vehicle.py            # bodies, sensors, motors
  sim.py                # simulation loop (headless)
  render.py             # pygame renderer (the only module that imports pygame)
  vehicle1.py           # one runnable module per vehicle: python -m braitenberg.vehicle1
  ...
specs/                  # one spec per vehicle (vehicle-01.md, ...) plus shared specs (worlds.md)
worlds/                 # world files in YAML, see specs/worlds.md
tests/                  # pytest tests, one file per vehicle covering its spec's acceptance criteria
```

Shared building blocks go in `world.py`, `vehicle.py` and `sim.py`; each `vehicleN.py` only wires them together for that vehicle. Split a module into a subpackage when it grows too large.

## Architecture rule

Keep the simulation engine independent of rendering. World, vehicles and brains must not import pygame; the renderer only reads simulation state and draws it. The simulation must be able to run headless and faster than real time, which Vehicles 6+ (evolution, learning) depend on.
