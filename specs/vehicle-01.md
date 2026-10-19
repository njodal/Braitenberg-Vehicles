# Vehicle 1 — Getting Around

## Summary

The simplest vehicle: one sensor wired directly to one motor. The more of a stimulus the sensor detects, the faster the motor turns. With no steering of its own, the vehicle moves along a straight line, but small random perturbations (friction, an uneven surface) slowly deflect its heading. The result looks restless in warm areas, where it speeds up, and lingers in cold areas, where it slows down.

This vehicle sets up the shared building blocks every later vehicle reuses: world, stimulus field, sensor, motor, simulation loop and renderer.

## World

The arena, stimuli and edge rule are defined in [worlds.md](worlds.md). Vehicle 1 needs a single stimulus (e.g. `temperature`) for its one sensor.

Default world: `worlds/vehicle1-hot-spot.yaml`, the example in [worlds.md](worlds.md) (a 100×100 wrapping arena with one heat source in the center and one vehicle).

In the world file, a `vehicle1` entry has a `sensor` key naming the stimulus it reads, and `params` may override any value in the table below.

## Vehicle

- **Body:** a point with a position `(x, y)` and a heading `θ`, drawn as a small oriented shape so the direction is visible.
- **Sensor:** one, at the front of the body. It reads the stimulus field value at its position.
- **Motor:** one, at the rear, pushing the vehicle forward along its heading.
- **Connection:** direct and excitatory: `speed = gain * sensor_value`, capped at `max_speed`. Optional `base_speed` (default 0) added before the cap.

## Dynamics

Each time step `dt`:

1. Read the sensor.
2. Compute the speed from the connection above.
3. Perturb the heading: `θ += noise_std * sqrt(dt) * N(0, 1)`. Without noise the vehicle would move in a straight line forever.
4. Move: `x += speed * cos(θ) * dt`, `y += speed * sin(θ) * dt`.
5. Apply the edge rule.

All randomness comes from a seeded random generator, so runs are reproducible.

## Parameters

| Name | Meaning | Default |
|---|---|---|
| `gain` | sensor-to-motor multiplier | 1.0 |
| `base_speed` | speed added regardless of stimulus | 0.0 |
| `max_speed` | speed cap | 5.0 |
| `noise_std` | heading perturbation strength | 0.3 |

The time step `dt` and the random `seed` are simulation settings in the world file.

## Visualization

- Draw the stimulus field as a background heat map.
- Draw sources, the vehicle and an optional fading trail of its recent path.
- Interaction: drag sources with the mouse, pause/resume, step one frame, reset, toggle trail.

## Acceptance criteria

1. **Speed follows stimulus:** a vehicle placed near a source moves faster than one placed far from it.
2. **No stimulus, no motion:** with no sources and `base_speed = 0`, the vehicle does not move.
3. **Straight line without noise:** with `noise_std = 0`, the heading never changes.
4. **Lingers where it is cold:** in the default world, run headless for 100,000 steps. The time-averaged stimulus at the vehicle's position must be lower than the field's average over the whole arena (computed on a grid of at least 100×100 points). Check this for seeds 0 to 4; it must hold for each one.
5. **Reproducible:** two headless runs with the same seed and configuration produce identical trajectories.
6. **Headless:** the simulation runs without pygame being imported, as required by the architecture rule in [AGENTS.md](../AGENTS.md).

## Out of scope

- Multiple sensors or motors and steering (Vehicle 2 onward).
- Inhibitory connections (Vehicle 3).
- Collisions between vehicles.
