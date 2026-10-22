# Vehicle Definition File

## Summary

A vehicle is described in a YAML file: its body, its sensors, its actuators and the units (the 'nervous system') between them. One generic vehicle implementation reads the file and simulates it, so a new vehicle, or a variation of one, is a new file rather than new code.

Vehicle definition files live in the `vehicles/` folder, e.g. `vehicles/vehicle1.yaml`, `vehicles/vehicle2b-aggression.yaml`. Scenarios place them in worlds ([scenarios.md](scenarios.md)).

## File format

```yaml
general:
  type: "2b"                 # which of Braitenberg's vehicles this is
  name: Aggression
  description: Two sensors, each wired to the motor on the opposite side.
  size: 4                    # body length and width, in arena units
  noise_std: 0.3             # optional heading perturbation, default 0

sensors:
  - sensor:
      name: left_eye
      type: light              # the stimulus it reads
      position: [-0.5, 0.9]
  - sensor:
      name: right_eye
      type: light
      position: [0.5, 0.9]

actuators:
  - actuator:
      name: left_motor
      type: motor
      position: [-0.8, -0.6]
      inputs:
        - input:
            from: right_eye      # crossed wiring
  - actuator:
      name: right_motor
      type: motor
      position: [0.8, -0.6]
      inputs:
        - input:
            from: left_eye

units: []
```

Each item in `sensors`, `actuators` and `units` is wrapped in a key naming its kind: `- sensor:`, `- actuator:` and `- unit:` respectively, with the item's fields indented below it. `general`, `sensors` and `actuators` are required (`sensors` may be an empty list); `units`, `energy` and `appearance` may be omitted. `appearance` (how other vehicles' cameras see this one) is defined in [camera.md](camera.md), *Vehicles as things*.

### 1. General

| Key | Required | Meaning |
|---|---|---|
| `type` | yes | Which of Braitenberg's vehicles this corresponds to, as a string: `"1"`, `"2a"`, `"2b"`, `"3a"`, `"5"`, … Informational: it is shown in the simulator, but the behavior comes only from the rest of the file. |
| `name` | yes | Human-readable name, e.g. `Aggression`. |
| `description` | no | Free text. |
| `size` | yes | Body length and width in arena units, unless `length` or `width` say otherwise. |
| `length` | no | The body's length from back to front, in arena units. Positive. Default `size`. |
| `width` | no | The body's width from side to side, in arena units. Positive. Default `size`. |
| `noise_std` | no | Heading perturbation strength, as in [vehicle-01.md](vehicle-01.md). Default 0. |
| `height` | no | The body's height, as cameras see it ([camera.md](camera.md)). Positive. Default `size / 2`. |

The body is a rectangle `width` across and `length` long, centered on the vehicle and turned with its heading; by default it is a square `size` on each side. Body coordinates `[-1, 1]` map to `[-width/2, width/2]` from left to right and to `[-length/2, length/2]` from back to front, so a part at `[1, 1]` sits at the front right corner however long or wide the body is. Cameras see the body as a box of that footprint and `height` ([camera.md](camera.md), *Vehicles as things*).

### 2. Sensors

| Key | Required | Meaning |
|---|---|---|
| `name` | yes | Unique name (see *Names*). |
| `type` | yes | The stimulus the sensor reads, e.g. `temperature`, `light`. It must be defined in the world the vehicle runs in. |
| `position` | yes | `[x, y]` in body coordinates. |
| `response` | no | How the sensor's output depends on its reading (see *Responses*). Default: `linear`. |
| `field_of_view` | no | The angle, in degrees, of the cone in front of the vehicle in which the sensor detects sources (see *Field of view*). Default 360: it detects sources in every direction. |
| `camera` | no | Makes the sensor a camera, whose output is a matrix of pixels instead of one value ([camera.md](camera.md)). A camera needs a `field_of_view`. |

A sensor **reads** the value of its stimulus at the sensor's position in the arena (or, for an `energy` sensor, the vehicle's own energy; see *5. Energy*), and its **output**, the signal its connections carry, is that reading passed through its response. Sensors at different places on the body read different values; that is what lets Vehicles 2 and up steer.

#### Field of view

By default a sensor detects sources all around it. A sensor with a `field_of_view` of `F` degrees only detects the sources it **sees ahead**: those whose direction from the sensor is within `F / 2` degrees of the vehicle's heading. Sources outside that cone contribute nothing to its reading, however close they are. (With `edges: wrap`, the direction is the shortest way around, as for distance.)

```yaml
- sensor:
    name: red_eye
    type: red
    position: [0, 0.9]
    field_of_view: 90      # only sources up to 45 degrees to either side of straight ahead
```

A vehicle that has passed a source then no longer senses it behind it. `field_of_view` must be greater than 0 and at most 360. An `energy` sensor has none, since it does not look at the world.

#### Responses

`response` is a mapping with a `type` and that type's fields:

| `type` | Fields | Output for a reading `r` |
|---|---|---|
| `linear` | none | `r`. This is the default, used by Vehicles 1 to 3. |
| `peak` | `at` (required), `width` (required, positive), `height` (default 1) | `height * exp(-((r - at) / width)^2 / 2)`: highest when the reading is `at`, falling off on both sides. A vehicle with this response prefers a middle amount of stimulus (Vehicle 4a). |
| `step` | `at` (required), `height` (default 1) | `height` when `r >= at`, `0` otherwise: nothing below the threshold, then a sudden jump (Vehicle 4b). |

```yaml
- sensor:
    name: left_eye
    type: light
    position: [-0.9, 0.9]
    response:
      type: peak
      at: 4
      width: 1.5
```

### 3. Actuators

| Key | Required | Meaning |
|---|---|---|
| `name` | yes | Unique name. |
| `type` | yes | `motor` (the only type for now): a wheel pushing the body forward. |
| `position` | yes | `[x, y]` in body coordinates. Its `x` decides how it steers (see *Movement*). |
| `inputs` | yes | Where its signal comes from: sensors and/or units (see *Inputs*). |
| `gain` | no | Multiplier on the summed input. Default 1. |
| `base_speed` | no | Speed with no input. Default 0. Vehicle 3 needs it, since its inhibitory wiring slows a motor that would otherwise run. |
| `max_speed` | no | Speed cap. Default 5. |

A motor adds up the signals of its active inputs, excitatory ones with `+` and inhibitory ones with `-`. Its speed is `base_speed + gain * sum`, clipped to `[0, max_speed]`. Motors do not run backwards.

### 4. Units

| Key | Required | Meaning |
|---|---|---|
| `name` | yes | Unique name. |
| `type` | yes | `threshold` (the only type for now): Braitenberg's threshold device from Vehicle 5. |
| `threshold` | yes | The unit fires when the sum of its active inputs reaches this value. `0` or less means the unit fires on its own, unless an inhibitory connection stops it. |
| `inputs` | yes | Sensors and/or other units, including itself (see *Inputs*). |
| `delay` | no | Seconds between the inputs reaching the threshold and the output appearing. Default `0.05`. Must be positive. |
| `position` | no | `[x, y]` in body coordinates, used only to place the unit in the diagram. If missing, the diagram lays it out automatically. |
| `array` | no | Makes the item an array of units, one per index, all wired alike ([vehicle-08.md](vehicle-08.md), *Arrays of units*). |

A threshold unit adds up the signals of its **active** inputs, excitatory ones with `+` and inhibitory ones with `-`, and outputs `1` when that sum is greater than or equal to `threshold`, and `0` otherwise. Inactive inputs are ignored. With no active input the sum is `0`, so a unit with `threshold` `0` or less fires on its own; an active inhibitory input with a strong enough signal brings the sum below the threshold and stops it.

**Units react with a delay.** As Braitenberg puts it, in a threshold device "the output does not appear immediately upon activation of the input, but only after a short delay, say one tenth of a second". This project uses a default of 0.05 seconds. A unit's output at time `t` is what its inputs called for at time `t - delay`. Brains have to be designed with this in mind: a signal that passes through a chain of units arrives one delay later per unit, and a loop of units has a rhythm set by its delays.

**Inputs close in time count as simultaneous.** Two inputs do not have to arrive at exactly the same instant to add up: if they arrive less than the unit's `delay` apart, the unit treats them as simultaneous. Concretely, each input contributes the largest value it had during the last `delay` seconds (the steps less than `delay` before now, and now), not only its value at this instant. This applies to inhibitory inputs too: an inhibition that arrived shortly before still counts. The window is measured in whole steps, so it only spans more than the current step when `delay` is larger than `dt`: with `delay` 0.05 and `dt` 0.05 it is just the current step, and with `dt` 0.01 it is the last 5 steps.

### 5. Energy

A vehicle may have an **energy** level: an internal store that movement uses up and a stimulus recharges. Without an `energy` section the vehicle has none.

```yaml
energy:
  initial: 50
  max: 100
  consumption: 0.5      # per unit of distance traveled
  basal: 2              # per second, for being alive, even standing still
  charge_from: light    # the stimulus that recharges it
  charge_gain: 2        # per second, per unit of that stimulus at the body center
```

| Key | Required | Meaning |
|---|---|---|
| `initial` | yes | Energy at the start, between 0 and `max`. |
| `max` | yes | The most energy the vehicle can hold. Positive. |
| `consumption` | yes | Energy used per unit of distance the vehicle travels. Not negative. |
| `basal` | no | Energy used per second just for being alive, whether the vehicle moves or not. Default 0: a vehicle that stands still uses none. Not negative. |
| `charge_from` | no | The stimulus that recharges it. It must be defined in the world. Without it, the vehicle never recharges. |
| `charge_gain` | no | Energy gained per second for each unit of `charge_from` read at the center of the body. Default 1. Not negative. |

Each step, after the vehicle moves a distance `d`: `energy += charge_gain * reading * dt - consumption * d - basal * dt`, clipped to `[0, max]`, where `reading` is `charge_from` at the body center before the move. Energy has no effect on movement: a vehicle with no energy left keeps moving, it just stays at 0.

The vehicle senses its own energy through a sensor of type `energy`. It reads the current energy, like any other sensor reading, and can have a `response`. An `energy` sensor's `position` only places it in the diagram. A vehicle with an `energy` sensor must have an `energy` section.

### Names

- Names of sensors, actuators and units share one namespace and must be unique across all three, so an input refers to its source by name alone.
- Names are lowercase identifiers: letters, digits and `_`, starting with a letter.

### Inputs

`inputs` of a unit or an actuator is a list. Like sensors, actuators and units, each item is wrapped in `- input:`, with its fields indented below it:

| Key | Required | Meaning |
|---|---|---|
| `from` | yes | Name of a sensor or unit. A camera's pixels and an array's elements are named with indices, such as `retina[0, 3]`, `lump[0:12]` or, inside an array, `lump[i-1]` ([camera.md](camera.md), *Pixel inputs*; [vehicle-08.md](vehicle-08.md), *Indices in inputs*). |
| `type` | no | `excitatory` (default) or `inhibitory`. |
| `strength` | no | Connection strength, from `0` to `1`. Default `1`. For a learning connection, its starting strength. |
| `learning` | no | Makes the strength change while the vehicle runs (see *Learning connections*). Without it the strength is fixed. |

```yaml
inputs:
  - input:
      from: left_eye         # excitatory, strength 1
  - input:
      from: alarm
      type: inhibitory       # inhibitory, strength 1
  - input:
      from: memory
      type: excitatory
      strength: 0.5          # inactive for now
```

A connection is **active** when its strength is above `0.7`. Only active connections carry a signal; an inactive one is ignored, as if it were not there. Strength is a gate, not a multiplier: an active connection carries its source's full signal, added if it is excitatory and subtracted if it is inhibitory. (Learning connections, below, change strength while the vehicle runs, which switches them on and off.)

Connections have no weights. How strongly a motor responds is set on the motor, with `gain`, `base_speed` and `max_speed`; when a unit fires is set on the unit, with `threshold`.

#### Learning connections

An input with a `learning` section changes its strength while the vehicle runs. The only learning type so far is Braitenberg's **Mnemotrix** wire from Vehicle 7 ([vehicle-07.md](vehicle-07.md)): it grows stronger when its source fires together with its destination.

```yaml
inputs:
  - input:
      from: sees_red
      strength: 0            # starting strength: inactive
      learning:
        type: mnemotrix
        learn: 0.3           # per second, while sees_red fires and the destination's other inputs make it fire
        forget: 0.01         # per second, while sees_red fires and they do not
```

| Key | Required | Meaning |
|---|---|---|
| `type` | yes | `mnemotrix`, the only learning type for now. |
| `learn` | yes | Strength gained per second while the source fires and the destination is driven by its other inputs. Not negative. |
| `forget` | no | Strength lost per second while the source fires and the destination is not driven by its other inputs. Not negative. Default 0. |

Each step, a Mnemotrix connection from source `S` to unit `D` checks whether the source is **on** (its contribution in `D`'s simultaneity window is 1) and whether `D` is **driven by its other inputs** (the sum of `D`'s other active inputs, leaving out this connection, reaches `D`'s threshold). Then:

| Source | Destination driven by other inputs | Strength |
|---|---|---|
| on | yes | `+= learn * dt` |
| on | no | `-= forget * dt` |
| off | either | unchanged |

The strength is clipped to `[0, 1]`. The connection's own contribution is left out so that a learned association cannot keep confirming itself and can still be unlearned ([vehicle-07.md](vehicle-07.md) explains why).

- The source must be a unit and the destination must be a unit. A unit may not learn from itself.
- A learning connection may be excitatory or inhibitory; the rule is the same.
- Each vehicle starts with the strengths in its definition and learns on its own. Learning never changes the definition file.

### Sources

Inputs may come from sensors or units. Actuators cannot be inputs. Units may form loops (a unit may feed back into itself or into an earlier unit); this is how Vehicle 5 builds memory.

## Signal flow

Simulation time is measured in seconds; each step advances it by `dt` (see [scenarios.md](scenarios.md)).

Each simulation step:

1. **Sensors** read the stimulus at their current position.
2. **Units** all update at once, in three parts:
   - **Outputs.** Each unit's visible output becomes the activation it computed `delay` seconds ago. Delays are rounded to a whole number of steps, at least one: with the default `delay` 0.05 and `dt` 0.05, one step; with `dt` 0.01, five steps. Outputs start at 0, and so do activations still on their way.
   - **Activations.** Each unit computes its activation, `1` or `0`, from its inputs: this step's sensor outputs and the unit outputs just made visible. Each input contributes the largest value it had within the unit's simultaneity window, which is the last `round(delay / dt)` steps including this one. The activation enters the unit's delay line, to become its output `delay` seconds later.
   - **Learning.** Each learning connection updates its strength (see *Learning connections*) from the values just used for the activations: its source's contribution in the destination's window and the destination's other inputs. The new strength takes effect from the next step; within a step, a connection is active or not as decided by its strength at the start of the step.
3. **Actuators** compute their speed from this step's sensor outputs and the visible unit outputs from step 2. Actuators have no delay: a sensor wired straight to a motor acts at once, as in Vehicles 1 to 4.
4. **Movement** (below), then the arena's edge rule.

So a signal from a sensor through units A and B to a motor reaches the motor `delay(A) + delay(B)` after the sensor reading changed. A unit wired to itself sees its own output, which makes loops well defined: a self-excited unit, once on, stays on.

## Movement

The body moves like a wheeled vehicle. With motor speeds `s_i` at body positions `x_i` (converted to arena units, `x_i * width / 2`):

- forward speed: `v = mean(s_i)`
- turn rate: `ω = Σ s_i x_i / Σ x_i²`, or `0` when every motor sits on the center line (`Σ x_i² = 0`)

Then, in this order (the same order as Vehicle 1):

1. `θ += ω * dt + noise_std * sqrt(dt) * N(0, 1)`
2. `x += v * cos(θ) * dt`, `y += v * sin(θ) * dt`

With one motor on the center line this is exactly Vehicle 1. With a left motor at `-a` and a right motor at `+a`, `ω = (s_right - s_left) / (2a)`: a faster right wheel turns the vehicle left (counterclockwise).

## Loading and validation

As with world files ([worlds.md](worlds.md)): parse with `yaml.safe_load`, validate into dataclasses, and fail fast with a message naming the file and the key when:

- a required key is missing, has the wrong type, or an unknown key appears;
- an item is not wrapped in the key for its list (e.g. `- unit:` inside `sensors`, or an input not wrapped in `- input:`);
- a name is repeated (the message names both places) or is not a valid identifier;
- an input names something that does not exist, or names an actuator;
- an input has a `type` other than `excitatory` or `inhibitory`, or a `strength` outside `[0, 1]`;
- a `learning` section has an unknown `type`, is missing `learn`, has an unknown key, or has a `learn` or `forget` that is negative or not a number;
- a learning connection comes from a sensor, goes into an actuator, or connects a unit to itself;
- a `position` is outside `[-1, 1]`;
- `general.length` or `general.width` is not a positive number;
- a unit's `delay` is not positive;
- a `field_of_view` is not greater than 0 and at most 360, or is given for an `energy` sensor;
- an `energy` value is missing, of the wrong type or out of range (e.g. `initial` above `max`), or a sensor has type `energy` and there is no `energy` section;
- a `response` has an unknown `type`, is missing a required field for its type, has a field that its type does not use, or has a `width` that is not positive;
- a sensor, actuator or unit `type` is unknown;
- there are no actuators.

A sensor `type` that the world does not define is reported when a scenario puts the vehicle in that world ([scenarios.md](scenarios.md)).

## Diagram

The diagram panel ([vehicle-diagram.md](vehicle-diagram.md)) is built from the definition: sensors, actuators and units at their positions, a wire for each input labeled with its sign, and live levels. Units are drawn as neurons that light up when they fire. The title shows the vehicle's label from the scenario, and below it `general.type` and `general.name`.

## Example: Vehicle 1

```yaml
general:
  type: "1"
  name: Getting around
  size: 4
  noise_std: 0.3

sensors:
  - sensor:
      name: sensor
      type: temperature
      position: [0, 0.8]

actuators:
  - actuator:
      name: motor
      type: motor
      position: [0, -0.8]
      inputs:
        - input:
            from: sensor
      max_speed: 5

units: []
```

## Example: a threshold unit (Vehicle 5)

A motor that runs only while the eye sees light of at least `2`:

```yaml
units:
  - unit:
      name: detector
      type: threshold
      threshold: 2
      inputs:
        - input:
            from: eye

actuators:
  - actuator:
      name: motor
      type: motor
      position: [0, -0.8]
      inputs:
        - input:
            from: detector
      gain: 3
```

## Example: an inhibitory connection

A motor that runs only while the eye sees light below `2`. `idle` has threshold `0`, so it fires on its own; `detector` fires when the light reaches `2` and, through an inhibitory connection, stops `idle`. (Each unit adds its delay of 0.05 seconds, as described in *Signal flow*: the motor stops 0.1 seconds after the light reaches `2`, and restarts 0.1 seconds after it drops below.)

```yaml
units:
  - unit:
      name: detector
      type: threshold
      threshold: 2
      inputs:
        - input:
            from: eye
  - unit:
      name: idle
      type: threshold
      threshold: 0
      inputs:
        - input:
            from: detector
            type: inhibitory

actuators:
  - actuator:
      name: motor
      type: motor
      position: [0, -0.8]
      inputs:
        - input:
            from: idle
      gain: 3
```

## Acceptance criteria

1. **Vehicle 1 unchanged:** a Vehicle 1 definition with its sensor at the body center `[0, 0]` placed like the current default world's vehicle produces exactly the same trajectory, for the same seed, as the current Vehicle 1 implementation (which reads the stimulus at the body center). The shipped `vehicles/vehicle1.yaml`, with its sensor at the front, passes the acceptance criteria of [vehicle-01.md](vehicle-01.md).
2. **Inputs:** for units and actuators alike, an input with only `from` loads as excitatory with strength `1`, and `type` and `strength` load with their values.
3. **Validation:** each failure case under *Loading and validation* raises an error naming the file and the key.
4. **Steering:** two sensors wired to two motors make the vehicle steer, as specified for Vehicle 2 in [vehicle-02.md](vehicle-02.md).
5. **Inhibition:** with `base_speed` above 0 and an inhibitory input, a motor slows down as its sensor reading rises. An inactive input (strength `0.7` or less) does not change the motor's speed.
6. **Threshold units:** a unit outputs 1 exactly when the sum of its active inputs reaches its threshold. An inhibitory input lowers that sum. A connection with strength `0.7` or less has no effect, and one above `0.7` does. A unit with threshold `0` fires with no input and stops when an active inhibitory input carries a signal. A unit's output appears `delay` seconds (rounded to steps, at least one) after its activation: in a chain sensor → unit A → unit B with the default delay and `dt` 0.05, A's output turns on 1 step after the sensor reading crosses A's threshold, and B's 1 step after that. With `delay` 0.1, each takes 2 steps. A unit wired to itself keeps firing after its input stops. Two excitatory inputs, each too weak alone to reach the threshold, make the unit fire when they arrive less than `delay` apart, and do not when they arrive `delay` or more apart.
7. **Diagram:** the diagram has one part per sensor, actuator and unit and one wire per input, with the right signs.
8. **Responses:** a sensor without `response` outputs its reading. A `peak` response outputs `height` at `at` and `height * exp(-1/2)` at `at ± width`. A `step` response outputs `0` just below `at` and `height` from `at` up.
9. **Energy:** with no light, a vehicle's energy drops by `consumption` times the distance it travels plus `basal` per second; without `basal` it does not change while the vehicle stands still, and with it it drops by `basal` per second. Near a `charge_from` source it rises by `charge_gain` times the reading at the body center, per second, minus what movement uses. It never goes below 0 or above `max`. An `energy` sensor reads the current energy.
10. **Field of view:** a sensor with a `field_of_view` reads a source straight ahead exactly as a sensor without one does, reads nothing from a source behind it or outside the cone, and a sensor without a `field_of_view` reads sources in every direction.
11. **Headless:** loading and running a definition never imports pygame.
12. **Body shape:** a definition without `length` and `width` loads with both equal to `size`, and moves and places its parts exactly as before. With `width` 6 and `length` 2, a sensor at `[1, 1]` sits 3 units to the right of the center and 1 unit ahead of it, and two motors at `x = ±1` turn the vehicle at `(s_right - s_left) / 6`.

Learning connections have their own criteria in [vehicle-07.md](vehicle-07.md) (criteria 6 to 12).

## Out of scope

- Other unit types, and learning types other than Mnemotrix (e.g. Vehicle 8's Ergotrix connections, which learn sequences).
- Response curves other than `linear`, `peak` and `step`, and responses on actuators or connections.
- Overriding definition values from a scenario.
- Evolving or editing definitions at runtime (Vehicle 6).
