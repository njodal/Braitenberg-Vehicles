# Scenarios

## Summary

A simulation is built from three kinds of YAML files, each with one job:

| File | Folder | Describes |
|---|---|---|
| World | `worlds/` | The environment: arena and stimuli ([worlds.md](worlds.md)). |
| Vehicle definition | `vehicles/` | One kind of vehicle: body, sensors, actuators and units ([vehicle-definition.md](vehicle-definition.md)). |
| **Scenario** | `scenarios/` | An experiment: which world, which vehicles placed where, and the simulation settings. |

The same world can host different vehicles, and the same vehicle can be tried in different worlds, without copying files. A scenario saves one combination so it can be rerun exactly.

## File format

```yaml
name: Fear and aggression
description: Vehicles 2a and 2b side by side in front of one light.

world: ../worlds/one-light.yaml

vehicles:
  - vehicle:
      definition: ../vehicles/vehicle2a-fear.yaml
      position: [20, 40]
      heading: 0             # degrees, 0 = +x, counterclockwise
  - vehicle:
      definition: ../vehicles/vehicle2b-aggression.yaml
      position: [20, 60]
      heading: 0
      label: aggressor       # optional

simulation:
  dt: 0.05
  seed: 0
```

| Key | Required | Meaning |
|---|---|---|
| `name` | yes | Shown in the window title. |
| `description` | no | Free text. |
| `world` | yes | Path to a world file. |
| `vehicles` | yes | A list; each item is wrapped in `- vehicle:` (see below). May be empty. |
| `simulation` | no | `dt`, the time step in seconds (default 0.05), and `seed` (default 0). |

Each `vehicle` has:

| Key | Required | Meaning |
|---|---|---|
| `definition` | yes | Path to a vehicle definition file. The same file may be used by several vehicles. |
| `position` | yes | `[x, y]` inside the world's arena. |
| `heading` | yes | Initial heading in degrees. |
| `label` | no | Name shown in the diagram panel. Default: the definition's `general.name` followed by `#` and the vehicle's index, e.g. `Aggression #1`. |

Paths are relative to the scenario file.

## Running

```
python -m braitenberg scenarios/vehicle2-fear-and-aggression.yaml
python -m braitenberg scenarios/vehicle2-fear-and-aggression.yaml --headless --steps 100000 --seed 3
```

For quick tries without writing a scenario, a world and one or more vehicles can be given directly:

```
python -m braitenberg --world worlds/one-light.yaml --vehicle vehicles/vehicle2b-aggression.yaml
python -m braitenberg --world worlds/one-light.yaml --vehicle vehicles/vehicle2a-fear.yaml --start 20,40,0
```

This builds the same scenario a file would:

- `--vehicle` may be repeated; vehicles are added in order.
- `--start x,y,heading` may be repeated; the n-th `--start` places the n-th vehicle. Vehicles without one are spread along the left side of the arena: vehicle `i` of `n` at `(0.2 * width, (i + 1) * height / (n + 1))`, heading 0.
- Simulation settings take their defaults.

Options for both forms:

| Option | Meaning |
|---|---|
| `--headless` | Run without a window, as fast as possible. |
| `--steps N` | Steps to run when headless (default 10000). |
| `--seed N` | Override `simulation.seed`. |

## Loading and validation

Loading a scenario loads the world and every vehicle definition it names, then checks that they fit together. As with the other files: `yaml.safe_load`, validation into dataclasses, and fail fast with a message naming the file and the key when:

- a required key is missing, has the wrong type, or an unknown key appears;
- an item in `vehicles` is not wrapped in `- vehicle:`;
- a referenced file does not exist. The message names the scenario key that refers to it, e.g. `vehicles[1].definition`;
- a referenced file is invalid. The message names that file and key, and the scenario key that refers to it;
- a vehicle's `position` is outside the world's arena;
- a vehicle has a sensor whose `type` is not a stimulus of the world. The message names the scenario, the vehicle, the sensor and the world file.

The quick form reports its problems the same way, naming the command-line option instead of a scenario key.

## Acceptance criteria

1. **Load:** loading the example scenario produces a world, two placed vehicles with their definitions, and the simulation settings from the file.
2. **Relative paths:** a scenario loads the same from any working directory.
3. **Shared definitions:** two vehicles using the same definition file are independent: moving one does not move the other.
4. **Quick form:** `--world W --vehicle V --start x,y,h` builds a scenario equal to a file with the same world, vehicle and start. Default starts follow the rule above.
5. **Validation:** each failure case under *Loading and validation* raises an error with the names it lists.
6. **Seed override:** `--seed` replaces `simulation.seed`, and two runs with the same seed produce identical results.
7. **Headless:** loading and running a scenario never imports pygame.

## Out of scope

- Overriding vehicle definition values from a scenario.
- Adding or removing vehicles while a simulation runs.
- Batches of scenarios, parameter sweeps and evolution runs (Vehicle 6).
