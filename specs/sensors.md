# Sensors

## Summary

A catalog of the sensor types used so far, each by its `type`, with how it reads and which vehicles use it. The rules themselves are defined in [vehicle-definition.md](vehicle-definition.md) (*2. Sensors* and *5. Energy*) and [worlds.md](worlds.md); this spec gathers them in one place and is the place to add new sensor types.

There are two kinds of sensors:

- **World sensors** read a stimulus of the world at the sensor's position. Their `type` is the **name of a stimulus**, and any stimulus the world defines can be sensed: a new kind of world sensor needs a new stimulus in a world file, not new code.
- **Internal sensors**, also called **proprioceptive** sensors, read something about the vehicle itself. Their `type` is a **reserved name**. So far there is one: `energy`.

Whatever it reads, a sensor's **reading** passes through its **response** to give its **output**, the signal its connections carry (see *Responses* below).

## World sensors

A world sensor reads the value of its stimulus's field at the sensor's position on the body: the sum, over the stimulus's active sources, of `intensity / (1 + (distance / falloff)^2)` ([worlds.md](worlds.md)). Two sensors at different places on the body read different values, which is what lets a vehicle steer. The scenario checks that every world sensor's `type` is a stimulus of the world it runs in.

| `type` | Stimulus | Worlds | Used by | Status |
|---|---|---|---|---|
| `temperature` | Heat from a hot spot, or from a hot lamp switched by a schedule | `hot-spot`, `hot-lamp` | Vehicle 1 (`sensor`); Vehicle 7 wary moth (`heat`) | Implemented (Vehicle 7: specified) |
| `light` | Light from one or more lamps | `one-light`, `two-lights`, `far-lights`, `hot-lamp` | Vehicles 2a, 2b, 3a, 3b, 4a, 4b; Vehicle 5 moth, searcher and forager; Vehicle 7 wary moth (`left_eye`, `right_eye`) | Implemented |
| `red` | The red lamp of a traffic light, switched by a schedule; a red lamp | `traffic-light`, `hot-lamp` | Vehicle 5 driver; Vehicle 7 wary moth (`red_eye`) | Implemented |
| `green` | The green lamp of a traffic light, switched by a schedule | `traffic-light` | Vehicle 5 driver (`green_eye`) | Implemented |

```yaml
- sensor:
    name: left_eye
    type: light            # the stimulus it reads
    position: [-0.9, 0.9]  # where on the body: left side, at the front
```

### Field of view

A world sensor may have a `field_of_view`, in degrees: it then only detects sources within half that angle of the vehicle's heading, so it ignores what is behind it ([vehicle-definition.md](vehicle-definition.md), *Field of view*). Without one it detects sources in every direction. **Status:** implemented; used by the Vehicle 5 driver (90°). Every other sensor so far detects in every direction.

## Internal (proprioceptive) sensors

Internal sensors are also called proprioceptive: like the sense that tells an animal about its own body (its posture, its fatigue, its hunger), they tell the vehicle about its own state rather than about the world around it.

| `type` | Reads | Requires | Used by | Status |
|---|---|---|---|---|
| `energy` | The vehicle's own energy, from 0 to its `max` | An `energy` section in the definition ([vehicle-definition.md](vehicle-definition.md), *5. Energy*) | Vehicle 5 forager (`energy`) | Implemented |

```yaml
- sensor:
    name: energy
    type: energy           # the vehicle's own energy, not a stimulus
    position: [0, -0.8]    # only places it in the diagram
```

An internal sensor's `position` only places it in the diagram, and it has no field of view. Its `type` is reserved: a world cannot define a stimulus with that name and have it read by a world sensor.

## Responses

Every sensor, of either kind, has a response that turns its reading `r` into its output ([vehicle-definition.md](vehicle-definition.md), *Responses*):

| Response | Output | Used by |
|---|---|---|
| `linear` (default) | `r` | All sensors except those below |
| `peak` (`at`, `width`, `height`) | `height * exp(-((r - at) / width)^2 / 2)`: highest at a middle reading | Vehicle 4a (`at` 4, `width` 1.5) |
| `step` (`at`, `height`) | `height` when `r >= at`, otherwise `0` | Vehicle 4b (`at` 4) |

## In the diagrams

In the simulator's panel and the SVG diagrams ([vehicle-diagram.md](vehicle-diagram.md)), every sensor is drawn as a round eye with two antennae at its position, labeled with its name and its `type` (plus its response when it is not linear). A sensor's level is its output relative to a reference: what saturates or fires its strongest excitatory target for a linear world sensor, the response's `height` for `peak` and `step`, and the energy `max` for an `energy` sensor.

## Adding a sensor type

- **A new world sensor:** add a stimulus with that name to a world, with its sources, and give sensors that `type`. No code changes.
- **A new internal sensor:** reserve a new `type`, define what it reads and what the definition must provide for it, and add it to *Internal (proprioceptive) sensors* above. This needs code, as `energy` did.

## Acceptance criteria

This spec adds no rules of its own, so it has no criteria of its own: each rule is tested where it is defined.

- World sensor readings, responses and validation: [vehicle-definition.md](vehicle-definition.md) criteria 1, 3 and 8, and [worlds.md](worlds.md) criteria 4 to 6. Two sensors reading different values to steer: [vehicle-02.md](vehicle-02.md) criterion 1.
- Sensor types checked against the world: [scenarios.md](scenarios.md) criterion 5.
- `energy` sensors: [vehicle-definition.md](vehicle-definition.md) criterion 9.
- Field of view: [vehicle-definition.md](vehicle-definition.md) criterion 10.
