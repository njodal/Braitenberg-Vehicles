# AGENTS.md

Instructions for AI coding agents working in this repo.

## Project

An implementation of the Vehicles from Valentino Braitenberg's book *Vehicles: Experiments in Synthetic Psychology*. The focus is Vehicles 5 and beyond, the ones with a 'nervous system' between the sensors and the actuators. See [README.md](README.md).

## Specs

Specifications live in the `specs/` folder. Read the relevant spec before implementing a vehicle or feature.

## Programming environment

The project is written in Python 3.11 or later.

- **Simulation:** pure Python + `numpy`. Differential-drive kinematics are simple enough that no physics engine is needed.
- **Visualization:** `pygame-ce` (the community-maintained pygame fork), used for real-time rendering and interaction (moving sources, pausing, selecting vehicles).
- **Configuration:** worlds, vehicle definitions and scenarios are YAML files loaded with `PyYAML` (see [specs/scenarios.md](specs/scenarios.md)).
- **Analysis:** `matplotlib` for plotting internal state (neuron activity, weights, fitness) after runs.
- **Tests:** `pytest`. Every acceptance criterion in a spec gets at least one test. Tests run headless (no pygame window) and use fixed seeds so they are deterministic. Run them with `pytest` from the repo root.

## Project structure

```
pyproject.toml          # package metadata and dependencies
braitenberg/            # the package
  __main__.py           # python -m braitenberg (see specs/scenarios.md)
  yamlfile.py           # shared YAML loading and validation helpers
  world.py              # arena, stimulus sources and fields
  definition.py         # vehicle definition files
  vehicle.py            # a vehicle built from a definition: signals, movement, diagram
  scenario.py           # scenarios: a world plus placed vehicles
  sim.py                # simulation loop (headless) and command line
  render.py             # pygame renderer
  record.py             # record a scenario to a GIF: python -m braitenberg.record
  diagram.py            # draw a definition as an SVG: python -m braitenberg.diagram
specs/                  # one spec per vehicle (vehicle-01.md, ...) plus shared specs
  images/               # GIFs and diagrams shown in the specs, generated with record and diagram
worlds/                 # environments in YAML, see specs/worlds.md
vehicles/               # vehicle definitions in YAML, see specs/vehicle-definition.md
scenarios/              # experiments in YAML, see specs/scenarios.md
tests/                  # pytest tests, one file per spec covering its acceptance criteria
```

A new vehicle is a new file in `vehicles/` (and usually a scenario to show it), not new code. Code changes are needed only for new kinds of parts, such as new unit types. Split a module into a subpackage when it grows too large.

## Architecture rule

Keep the simulation engine independent of rendering. World, vehicles and brains must not import pygame (only `render.py` and `record.py` do); the renderer only reads simulation state and draws it. The simulation must be able to run headless and faster than real time, which Vehicles 6+ (evolution, learning) depend on.
