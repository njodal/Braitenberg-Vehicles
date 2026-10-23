# Vehicle diagram panel

## Summary

The simulator window shows, next to the arena, a separate panel with a live schematic of one vehicle: its sensors, motors, units and the wiring between them. Wires and parts light up with the signals flowing through them, so you can see *why* the vehicle moves the way it does, not just *how*. This matters most from Vehicle 5 onward, where the interesting part is the 'nervous system' between sensors and motors.

## Layout

- The window is the arena on the left and the panel on the right, 420 pixels wide. The window is as tall as the arena, and at least 600 pixels so that the panel fits; a long, narrow arena (such as a road) is drawn at the top, with empty space below it. A vehicle with many readout lines (such as the Vehicle 7 wary moth) makes the window taller still, so that its diagram keeps a radius of at least 110 pixels, or of 150 pixels for a vehicle with cameras or arrays of units (such as the Vehicle 8 hunter).
- The panel shows, from top to bottom:
  1. A title with the vehicle's label from the scenario, e.g. `Aggression #1`, and below it the Braitenberg type and name from its definition, e.g. `Vehicle 2b: Aggression`.
  2. The diagram: a top-down view of the body with its front pointing up. The diagram does not rotate with the vehicle, so it stays easy to read.
  3. Live readouts, one compact line per part: its name and label (a sensor's stimulus, or `threshold` and the value for a unit), a level bar and its value. Then one line per learning connection, e.g. `sees_red->danger  M  0.42`, with a strength bar from 0 to 1 and a tick at 0.7.
  4. Vehicle values, on two lines: `body` (its width × length × height, e.g. `4×4×2`), `noise_std`, and the current forward speed and turn rate.
- The diagram takes the space left above the readouts, up to a maximum size, so that a vehicle with many units (such as Vehicle 5) still fits; the readouts start right below the diagram.

## Diagram

- **Body:** an outline of the vehicle's body, with its proportions: a body longer than it is wide is drawn taller than wide, and its parts sit where their body coordinates put them on it.
- **Sensors, motors and units:** drawn at their position on the body, each with its own shape and labeled with its name (e.g. `left_eye`). A unit is a circle with its threshold written inside. The readouts below the diagram add the stimulus a sensor reads.
- **Wires:** lines from source to destination, marked `+` for excitatory and `-` for inhibitory connections. The mark sits near the destination, so crossed wires do not share it. A unit wired to itself is drawn as a small loop. Inactive connections (strength `0.7` or less, see [vehicle-definition.md](vehicle-definition.md)) are drawn as thin dim lines that never light up.
- **Learning wires:** a Mnemotrix connection ([vehicle-07.md](vehicle-07.md)) has its own color and is labeled `M`. Its width grows with its current strength, and it is dashed while inactive, so the moment it switches on, or off again, is visible.
- **Live signals:** each part and wire is colored by its current activity level, from dim (0) to bright (1).
- **Modules:** a module ([modules.md](modules.md)) is drawn as one box at its position, with its inputs on top and its outputs below, and gets one readout line with its outputs as cells. Its units and the wires between them are not drawn; a wire into it ends at its input, and one out of it starts at its output.
- **Cameras and arrays of units:** drawn as grids of cells, one per pixel or element, each lit by its level. Their wires are drawn as one per pair of parts and sign, and the readouts show one line per camera or array, with its cells and how many are on ([camera.md](camera.md), [vehicle-08.md](vehicle-08.md)). In the arena, the `V` key shows the selected vehicle's camera views.

## Data model

The diagram is described by the vehicle, not by the renderer, so every vehicle definition gets a diagram without renderer changes:

- A vehicle's `diagram()` method, built from its definition ([vehicle-definition.md](vehicle-definition.md)), returns its parts (kind, name, position in body coordinates, current value and activity level in [0, 1]) and its wires (source part, destination part, sign, whether active, activity level, current strength, and learning type or none).
- Body coordinates: the body center is `(0, 0)`, `+y` points forward, and the body spans `[-1, 1]` on both axes. Units without a `position` are spread across the middle of the body.
- Part kinds are `sensor`, `motor`, `unit`, `camera`, `array` and `module`; a new kind is drawn with a generic shape until it gets a specific one.
- `diagram()` lives on the simulation side and must not import pygame.

Levels:

- **Sensor:** its reading divided by a reference reading, capped at 1. The reference is the lowest reading at which one of its active excitatory targets saturates: for a motor `(max_speed - base_speed) / gain`, for a unit `threshold` (when above 0). With no excitatory targets the reference is 1.
- **Unit:** its output, 0 or 1.
- **Motor:** `speed / max_speed`.
- **Wire:** the level of its source, or 0 for an inactive connection.

For Vehicle 1 this gives a sensor level of `reading / ((max_speed - base_speed) / gain)`, which reaches 1 exactly when the motor saturates.

## Selecting a vehicle

- The panel shows the first vehicle by default.
- Clicking a vehicle in the arena selects it; the selected vehicle is marked with a ring in the arena.
- If the scenario has no vehicles, the panel says so.

## Static diagram

The same diagram can be exported from a definition file as an SVG image, for specs and docs:

```
python -m braitenberg.diagram vehicles/vehicle5-moth.yaml --out specs/images/vehicle5-moth.svg
```

- It shows the title (`Vehicle <type>: <name>`), the body, every sensor, actuator and unit at its diagram position with its name (and a sensor's stimulus or a unit's threshold below it), and every wire as an arrow from source to target.
- Wires are colored by kind, blue for excitatory and red for inhibitory, and marked `+` or `−`; inactive connections are dashed and gray. Learning connections are drawn as in the panel, with their starting strength, and labeled `M`. A legend explains the colors and, when the vehicle has learning connections, the `M`.
- It has no live signals, and it does not import pygame.

## Recording

A scenario can be recorded to an animated GIF, drawn by the same renderer as the window, panel included, without opening a window:

```
python -m braitenberg.record scenarios/vehicle5-moth.yaml --seconds 40 --out specs/images/vehicle5-moth.gif
```

Options: `--every` (simulated seconds between frames, default 0.1), `--speed` (playback speed, default 2), `--scale` (image scale, default 0.6) and `--seed`. It needs Pillow.

## Acceptance criteria

1. **Structure:** Vehicle 1's diagram has exactly one sensor, one motor and one excitatory wire from the sensor to the motor.
2. **Levels:** every level is in [0, 1]. The sensor and motor levels are 0 with no stimulus and reach 1 when the motor saturates.
3. **Live:** after a simulation step, the diagram reflects the vehicle's current sensor reading and speed.
4. **Headless:** building a diagram never imports pygame.
5. **Renders:** the renderer draws a frame with the panel without errors, using SDL's dummy video driver so no window opens.
6. **Static diagram:** the SVG for a definition is well-formed XML, names every part, has one arrow per input with the right color for its sign (dashed when inactive), marks learning connections with `M`, and is produced without importing pygame.
8. **Learning wires:** for a vehicle with a learning connection, the diagram reports the connection's current strength after each step, and the wire is active exactly when that strength is above 0.7.
7. **Recording:** recording a scenario writes a GIF with one frame per `--every` seconds of simulated time, plus the first frame.
