# Vehicle diagram panel

## Summary

The simulator window shows, next to the arena, a separate panel with a live schematic of one vehicle: its sensors, motors and the wiring between them. Wires and parts light up with the signals flowing through them, so you can see *why* the vehicle moves the way it does, not just *how*. This matters most from Vehicle 5 onward, where the interesting part is the 'nervous system' between sensors and motors.

## Layout

- The window is the arena on the left and the panel on the right, as tall as the arena and about 300 pixels wide.
- The panel shows, from top to bottom:
  1. A title with the vehicle type and index, e.g. `vehicle1 #0`.
  2. The diagram: a top-down view of the body with its front pointing up. The diagram does not rotate with the vehicle, so it stays easy to read.
  3. Live readouts: the value of each sensor and motor.
  4. The vehicle's parameters (e.g. `gain`, `max_speed`, `noise_std`).

## Diagram

- **Body:** an outline of the vehicle's body.
- **Sensors:** drawn at their position on the body, labeled with the stimulus they read (e.g. `temperature`).
- **Motors:** drawn at their position on the body.
- **Wires:** lines from source to destination, marked `+` for excitatory and `−` for inhibitory connections.
- **Live signals:** each part and wire is colored by its current activity level, from dim (0) to bright (1).

## Data model

The diagram is described by the vehicle, not by the renderer, so every new vehicle type gets a diagram without renderer changes:

- Each vehicle class provides a `diagram()` method returning its parts (kind, name, position in body coordinates, current value and activity level in [0, 1]) and its wires (source part, destination part, sign, activity level).
- Body coordinates: the body center is `(0, 0)`, `+y` points forward, and the body spans `[-1, 1]` on both axes.
- Part kinds start with `sensor` and `motor`; later vehicles add more (e.g. `neuron`), which the renderer draws with a generic shape until it gets a specific one.
- `diagram()` lives on the simulation side and must not import pygame.

For Vehicle 1: one sensor at the front `(0, 0.8)`, one motor at the rear `(0, -0.8)` and one excitatory wire between them. The sensor's level is its reading divided by the reading at which the motor saturates (`(max_speed - base_speed) / gain`), capped at 1. The motor's level is `speed / max_speed`.

## Selecting a vehicle

- The panel shows the first vehicle by default.
- Clicking a vehicle in the arena selects it; the selected vehicle is marked with a ring in the arena.
- If the world has no vehicles, the panel says so.

## Acceptance criteria

1. **Structure:** Vehicle 1's diagram has exactly one sensor, one motor and one excitatory wire from the sensor to the motor.
2. **Levels:** every level is in [0, 1]. The sensor and motor levels are 0 with no stimulus and reach 1 when the motor saturates.
3. **Live:** after a simulation step, the diagram reflects the vehicle's current sensor reading and speed.
4. **Headless:** building a diagram never imports pygame.
5. **Renders:** the renderer draws a frame with the panel without errors, using SDL's dummy video driver so no window opens.
