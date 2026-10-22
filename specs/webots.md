# Webots: vehicles on a simulated e-puck

## Summary

The vehicles of this project run in our own simulator, a flat arena with fields. [Webots](https://cyberbotics.com/) is a 3D robot simulator, free and open source, that ships a model of the **e-puck**, a small two-wheeled robot used in research on Braitenberg vehicles and evolutionary robotics. Running a vehicle on the Webots e-puck checks it against a more realistic body: real light sensors with their own angles and noise, wheels that slip, inertia, collisions. It is also the step before a real e-puck, which runs the same controller.

This spec adds an **adapter**: a Webots controller that loads a vehicle definition, the same YAML file the simulator uses, and runs its network on the e-puck. Each step it reads the e-puck's light sensors, turns them into the readings the definition's sensors expect, lets the vehicle think, and turns its motor speeds into wheel speeds. The network is the project's own (`Vehicle.think`); only the body changes.

```
e-puck light sensors ──► readings ──► Vehicle.think ──► motor speeds ──► e-puck wheels
   (raw, 0 to 4095)      (0 to scale)   (the definition)                   (rad/s)
```

The adapter is `braitenberg/webots.py`. Webots files live in `webots/`: the controller in `webots/controllers/braitenberg/` and test worlds in `webots/worlds/`.

## The e-puck

The e-puck is a cylinder 7 cm across with two wheels, one on each side, and eight infrared sensors around its body. Each of them measures proximity (`ps0` to `ps7`) and ambient light (`ls0` to `ls7`). The adapter uses the light sensors and the two wheel motors (`left wheel motor`, `right wheel motor`).

The light sensors point outward, at these angles from the front, positive to the right (from their positions in Webots' e-puck model):

| Sensor | `ls0` | `ls1` | `ls2` | `ls3` | `ls4` | `ls5` | `ls6` | `ls7` |
|---|---|---|---|---|---|---|---|---|
| Angle | 18° | 49° | 90° | 153° | −153° | −90° | −49° | −18° |

A light sensor's raw value goes **down** as the light goes up: 4095 in the dark, 0 in full light. In Webots it is a linear function of the irradiance `E` at the sensor, 4095 at `E = 1` and 0 at `E = 2`, clamped outside that range, with 1% noise.

## Which vehicles can run

A vehicle can run on the e-puck when:

- **Its sensors are all `light` sensors** without a camera. The e-puck has no temperature sensor and no color sensors, and its camera is not mapped yet, so definitions with `temperature`, `red`, `green`, `energy` or camera sensors are rejected with a `ConfigError` that names the sensor.
- **It has two motors, one on each side of the body**: one with a negative `x` position (the left wheel) and one with a positive one (the right wheel). Anything else is rejected.

Today that is Vehicles 2a, 2b, 3a, 3b, 4a, 4b, the Vehicle 5 moth and searcher, and the Vehicle 8 prey.

A sensor's `field_of_view` is ignored: the e-puck's sensors have their own aperture. The definition's `noise_std` is ignored too: Webots adds its own noise to sensors and motion.

## Sensors

Each `light` sensor of the definition reads the e-puck light sensor **nearest in angle** to it. A definition sensor's angle is that of its position on the body, `atan2(x · width, y · length)`, from the front and positive to the right. The eyes of Vehicles 2 to 5, at `[-0.9, 0.9]` and `[0.9, 0.9]`, are at −45° and 45°, so they read `ls6` and `ls1`.

The raw value becomes a reading between 0 (dark) and `light_scale` (full light):

`reading = light_scale × (1 − raw / 4095)`

`light_scale` defaults to **10**, the intensity of the lamps in the project's worlds, so the vehicles' gains and thresholds work as they are. The reading then goes through the sensor's `response` as in the simulator.

## Motors

Each step, `Vehicle.think` gives every motor a speed between 0 and its `max_speed`. The adapter sets each wheel to

`wheel speed = max_wheel_speed × motor speed / top speed`

where `top speed` is the larger `max_speed` of the two motors, so the two wheels keep the ratio the definition gives them. `max_wheel_speed` defaults to 6.28 rad/s, the e-puck's top speed.

## Time

The vehicle's `dt` is Webots' `basicTimeStep`, in seconds, so units' delays last as long as in the simulator.

## Running it

The controller takes its arguments from the robot's `controllerArgs` in the world file:

```
controllerArgs [ "vehicles/vehicle2b-aggression.yaml" "--light-scale" "10" ]
```

| Argument | Default | Meaning |
|---|---|---|
| definition | (required) | The vehicle definition, relative to the repo root |
| `--light-scale` | 10 | The reading in full light |
| `--max-wheel-speed` | 6.28 | Wheel speed, in rad/s, for a motor at the top speed |

Webots runs the controller with its own Python command (Preferences, *Python command*). Point it at a Python that has the project's dependencies, such as the project's virtual environment.

### The test world

`webots/worlds/vehicle2-fear-and-aggression.wbt` is the scenario of [vehicle-02.md](vehicle-02.md) on two e-pucks: a 2 m arena with one lamp at the height of the e-pucks' sensors, Fear on the left and Aggression on the right, both facing it. Aggression turns toward the lamp and drives up to it; Fear turns its back on it and stops.

Both stop for the same reason: the e-puck's eyes look out at 49° to each side, so a lamp right in front of them, close, or behind them gives them almost no light. Aggression stops a few centimeters from the lamp, when it is between its eyes; Fear stops once the lamp is behind it. Braitenberg's vehicles, with eyes that see all around, would hit the lamp and keep running from it.

The lamp is a `PointLight` with `intensity 3` and `attenuation 1 0 1`, so the irradiance it gives a sensor facing it is `3 / (1 + d²)`, with `d` in meters: the same falloff as a source in the project's worlds with a falloff of 1 m. A sensor facing the lamp reads `light_scale` up to 71 cm from it and 0 beyond 1.41 m; a sensor at an angle to the lamp reads less, by the cosine of that angle. The e-pucks start 60 cm from the lamp. Light sensors count every light in the world, so the world has no other lights: the scene is lit for the eye by the background only.

## Acceptance criteria

1. **Sensor mapping.** Each definition `light` sensor reads the e-puck light sensor nearest in angle to it: the eyes at `[-0.9, 0.9]` and `[0.9, 0.9]` read `ls6` and `ls1`, and a sensor straight ahead reads `ls0` or `ls7`.
2. **Light readings.** A raw value of 4095 gives a reading of 0, a raw value of 0 gives `light_scale`, and readings in between are linear.
3. **Motors.** The motor on the left of the body drives the left wheel. Wheel speeds are motor speeds scaled by `max_wheel_speed / top speed`: a motor at its top speed turns its wheel at `max_wheel_speed`. With Vehicle 2b, more light on the right eye makes the left wheel faster.
4. **Time.** The vehicle's `dt` is the robot's basic time step in seconds.
5. **Unsupported vehicles.** Definitions with a sensor other than a `light` sensor (Vehicle 1, the Vehicle 5 driver and forager, the Vehicle 8 hunter) or without one motor on each side are rejected with a `ConfigError`.
6. **Controller loop.** The controller enables every light sensor it uses with the basic time step, puts both wheels in velocity mode, and sets their speeds every step until Webots ends the simulation.
7. **Headless.** `braitenberg.webots` imports neither pygame nor Webots' `controller` module, so it can be tested without Webots.
8. **Behavior.** On a model e-puck with the Webots light sensor and differential drive, starting 60 cm from one lamp and facing it: Aggression ends within 15 cm of the lamp, facing it (within 30°); Fear ends with the lamp behind it (more than 90° from its heading), no closer than 55 cm.
9. **World file.** Every robot in `webots/worlds/` uses the `braitenberg` controller with a definition that the adapter accepts.
