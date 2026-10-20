# Vehicle diagram panel

## Summary

The simulator window shows, next to the arena, a separate panel with a live schematic of one vehicle: its sensors, motors, units and the wiring between them. Wires and parts light up with the signals flowing through them, so you can see *why* the vehicle moves the way it does, not just *how*. This matters most from Vehicle 5 onward, where the interesting part is the 'nervous system' between sensors and motors.

## Layout

- The window is the arena on the left and the panel on the right, as tall as the arena and about 300 pixels wide.
- The panel shows, from top to bottom:
  1. A title with the vehicle's label from the scenario, e.g. `Aggression #1`, and below it the Braitenberg type and name from its definition, e.g. `Vehicle 2b: Aggression`.
  2. The diagram: a top-down view of the body with its front pointing up. The diagram does not rotate with the vehicle, so it stays easy to read.
  3. Live readouts: the value of each sensor, unit and motor, with a level bar.
  4. Vehicle values: `size`, `noise_std`, and the current forward speed and turn rate.

## Diagram

- **Body:** an outline of the vehicle's body.
- **Sensors, motors and units:** drawn at their position on the body, each with its own shape and labeled with its name (e.g. `left_eye`). The readouts below the diagram add the stimulus a sensor reads.
- **Wires:** lines from source to destination, marked `+` for excitatory and `-` for inhibitory connections. The mark sits near the destination, so crossed wires do not share it. A unit wired to itself is drawn as a small loop. Inactive connections (strength `0.7` or less, see [vehicle-definition.md](vehicle-definition.md)) are drawn as thin dim lines that never light up.
- **Live signals:** each part and wire is colored by its current activity level, from dim (0) to bright (1).

## Data model

The diagram is described by the vehicle, not by the renderer, so every vehicle definition gets a diagram without renderer changes:

- A vehicle's `diagram()` method, built from its definition ([vehicle-definition.md](vehicle-definition.md)), returns its parts (kind, name, position in body coordinates, current value and activity level in [0, 1]) and its wires (source part, destination part, sign, whether active, activity level).
- Body coordinates: the body center is `(0, 0)`, `+y` points forward, and the body spans `[-1, 1]` on both axes. Units without a `position` are spread across the middle of the body.
- Part kinds are `sensor`, `motor` and `unit`; a new kind is drawn with a generic shape until it gets a specific one.
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

## Acceptance criteria

1. **Structure:** Vehicle 1's diagram has exactly one sensor, one motor and one excitatory wire from the sensor to the motor.
2. **Levels:** every level is in [0, 1]. The sensor and motor levels are 0 with no stimulus and reach 1 when the motor saturates.
3. **Live:** after a simulation step, the diagram reflects the vehicle's current sensor reading and speed.
4. **Headless:** building a diagram never imports pygame.
5. **Renders:** the renderer draws a frame with the panel without errors, using SDL's dummy video driver so no window opens.
