# Vehicle 12 — Trains of Thought: threshold control

**Status:** proposed, not implemented. This spec covers variable thresholds, the threshold control unit and a first example, the daydreamer, whose ideas are wired by hand. A version that learns its ideas, and the learning rule it needs (see *Open questions*), are still to be specified.

## Summary

Braitenberg's chapter on Vehicle 12 ("Trains of Thought") starts from a danger in the vehicles with learned associations. Units that excite each other can set off a chain reaction: if each active unit activates more than one other, activity explodes until the whole brain is on; if it activates fewer than one, activity dies out. His answer is a **threshold control**: a device that watches how many elements are active and raises everyone's threshold when there are too many, and lowers it when there are too few. Activity then neither explodes nor dies. It wanders through the network along its associations, even when the sensors are silent. That wandering is the train of thought.

This spec adds two things to the vehicle definition ([vehicle-definition.md](vehicle-definition.md)):

- **Variable thresholds:** a unit's threshold can move away from the value in its definition.
- **The threshold control unit**, a new unit type, `threshold_control`, which moves the thresholds of the units it controls according to how active the units it watches are.

### Why not inhibitory wires

An inhibitory wire from a threshold unit lowers a sum by 1 or not at all, because unit outputs are 0 or 1. A threshold control has to move in small steps, and it has to go in both directions: it must also make units easier to fire than their definition says, or a silent brain stays silent.

### Biological basis

In the book's biological notes, Braitenberg admits that the evidence in animal brains is only indirect, but finds it hard to see how they could work otherwise, with so many cortical neurons reciprocally connected by positive feedback. A cell assembly may be spread over wide regions of the cortex, so the mechanism that detects its ignition has to receive input from the entire cortex. He suggests the striatum-caudate complex, which accompanies the cortex throughout its extent and receives an orderly projection from all of it, acting back on the cortex probably through the paleostriatum-thalamus loop. He also suggests that the dynamics of threshold control may be chaotic, which he offers as a possible, and debatable, account of the freedom of thought.

So the example below names its control unit `caudate`, its `inputs` are the projection from the cortex, and its `delay` is the time around the loop.

## Variable thresholds

Every unit keeps its `threshold`, now called its **base threshold**, and has an **offset**, which starts at 0:

```
effective threshold = threshold + jitter + offset
```

- A threshold unit outputs 1 when the sum of its active inputs reaches its **effective threshold**, instead of its base threshold. Everything else about it stays as in [vehicle-definition.md](vehicle-definition.md), *Units*.
- The rule that a unit whose threshold is `0` or less fires on its own applies to the effective threshold.
- A unit that no threshold control controls has jitter 0 and offset 0, so it behaves exactly as before.
- A unit has at most one threshold control.

## The threshold control unit

```yaml
- unit:
    name: caudate
    type: threshold_control
    inputs:
      - input:
          from: idea[:]        # what it watches: the whole 'cortex'
    controls: [idea]           # whose thresholds it moves
    target: 5                  # how much activity it wants
    rate: 0.5                  # offset per second, per unit of activity above or below target
    delay: 0.1                 # seconds around the loop
    jitter: 0.02               # largest fixed difference from the base threshold
```

| Key | Required | Meaning |
|---|---|---|
| `name` | yes | Unique name. |
| `type` | yes | `threshold_control`. |
| `inputs` | yes | The signals it adds up, in the same form as a threshold unit's inputs (*Inputs*), including their signs and the simultaneity window. |
| `controls` | yes | A non-empty list of names of threshold units or arrays, whose thresholds it moves. |
| `target` | yes | The activity it wants. Not negative. |
| `rate` | yes | How fast it corrects. Positive. |
| `delay` | no | Seconds between computing an offset and the units using it. Default `0.05`. Must be positive. |
| `jitter` | no | The largest fixed difference between a controlled unit's threshold and its base threshold, in either direction. Not negative. Default `0`. |
| `position` | no | As for a threshold unit. |

### The rule

Each step, the control unit adds up its active inputs, as a threshold unit does; that sum is its **activity**. Then:

```
offset += rate * (activity - target) * dt
```

The offset has no limits and starts at 0. There is one offset per control unit, shared by all the units it controls.

The correction **accumulates**. A control that set the offset directly from the activity would hold a fixed offset whenever activity is 0, and if that offset is not low enough to fire anything, the brain stays silent forever. An accumulating control keeps lowering the thresholds until something fires. It needs no limits because it limits itself: once offsets are low enough, units fire on their own and activity pushes the offset back up. Likewise, once they are high enough, nothing fires and activity pushes it back down, provided the control watches units it controls.

### Jitter

Unit outputs are 0 or 1, so in a large network many units have exactly the same sum. As a falling threshold reaches that sum, they would all fire on the same step, which is the explosion the control exists to prevent. So when the vehicle is built, each controlled unit gets a fixed difference, drawn uniformly from `[-jitter, jitter]`. The values come from the scenario's seed and do not change during the run, so the units fire in a fixed order of precedence, and no noise is added to the dynamics. Each element of an array gets its own value. With `jitter` 0, nothing is drawn.

### Signal flow

Control units update in step 2 of the signal flow ([vehicle-definition.md](vehicle-definition.md), *Signal flow*), with the units:

- **Outputs.** Each control unit's visible offset becomes the one it computed `delay` seconds ago, rounded to whole steps, at least one. Before that it is 0.
- **Activations.** Threshold units compare their sums with their effective thresholds, using the visible offset. Control units compute their activity from the same input values and their new offset, which enters their delay line.
- **Learning** is as before, and uses base thresholds (see below).

### Learning uses the base threshold

The learning rules of Mnemotrix ([vehicle-07.md](vehicle-07.md)) and Ergotrix ([vehicle-11.md](vehicle-11.md)) keep comparing sums with `threshold`, the base threshold, and ignore jitter and offset. What a vehicle learns should depend on the events it meets, not on the momentary state of its control. An Ergotrix wire also needs this: with an effective threshold at 0 or below, its destination would count as driven all the time, and the wire would never see it turn on.

### Limits

For now, a control unit's only output is its offset:

- No threshold unit, motor or other control unit can take a control unit as an input.
- A control unit cannot be an array.

## Loading and validation

In addition to the checks in [vehicle-definition.md](vehicle-definition.md), *Loading and validation*, it is an error, naming the file and the key, if:

- `controls` is missing or empty, or names something that does not exist, a sensor or a control unit.
- A unit is controlled by more than one control unit.
- An input of a threshold unit, actuator or control unit comes from a control unit.
- `target` or `jitter` is negative, `rate` or `delay` is not positive, or a control unit has `threshold` or `array`.

## Display

- **Simulator panel:** each controlled unit shows its current effective threshold, with one decimal. The control unit shows its visible offset, with its sign.
- **SVG diagram** ([vehicle-diagram.md](vehicle-diagram.md)): a controlled unit shows its base threshold, because the diagram describes the definition, not a moment of the run. The control unit has its own shape. Its inputs are drawn like any others, and its `controls` as dashed arrows, one per array.
- **Analysis:** activity and offset are recorded over time, to plot with `matplotlib`.

## Example: the daydreamer

The daydreamer sits in an empty, dark arena. It has nothing to sense, yet it keeps moving: its movements come from a train of ideas inside it, one leading to the next.

### Ideas

The vehicle has no sensors. Its 'cortex' is an array of 8 threshold units, `idea[0]` to `idea[7]`, with `delay` 1, so that each idea stays on for about a second: long enough to see its gesture. Each idea excites two others, the next one and the one three places on, around a ring:

```
idea[k] → idea[k+1 mod 8] and idea[k+3 mod 8]
```

Since each idea fires two, the network is explosive on purpose. Indices outside an array are left out ([vehicle-08.md](vehicle-08.md), *Indices in inputs*), so the ring is closed with a second, shifted input for each neighbor, which exists only for the elements that need it:

```yaml
- unit:
    name: idea
    type: threshold
    threshold: 2
    array: 8
    delay: 1
    inputs:
      - input:
          from: idea[i-1]      # the previous idea ...
      - input:
          from: idea[i+7]      # ... for idea[0], which is idea[7]
      - input:
          from: idea[i-3]      # the idea three places back ...
      - input:
          from: idea[i+5]      # ... for idea[0] to idea[2]
      - input:
          from: wake[i]        # wake has one element, so only idea[0] gets it
```

### Gestures

Each idea moves the motors its own way. Motors do not run backwards, so the gestures are those of two forward motors:

| Ideas | Gesture | Left motor | Right motor |
|---|---|---|---|
| `idea[0]`, `idea[4]` | forward | on | on |
| `idea[1]`, `idea[5]` | turn left | off | on |
| `idea[2]`, `idea[6]` | turn right | on | off |
| `idea[3]`, `idea[7]` | stop | off | off |

So the left motor takes `idea[0]`, `idea[2]`, `idea[4]` and `idea[6]`, and the right motor `idea[0]`, `idea[1]`, `idea[4]` and `idea[5]`. A train of thought is a sequence of gestures, and it can be read in the vehicle's track.

### Waking up

All units start off, so something has to start the first idea. A pair of units makes a single pulse at the start of the run, with existing parts only:

| Unit | Threshold | Inputs | Does |
|---|---|---|---|
| `wake` (`array: 1`) | 0 | `awake`, inhibitory | fires on its own from the start, until `awake` stops it |
| `awake` | 1 | `wake[0]` and itself | turns on after `wake` and stays on |

`wake` sends one pulse to `idea[0]` and is then held off by `awake` for the rest of the run. It is an array of one element only so that the ideas can take it as `wake[i]`, which exists for `idea[0]` alone. Neither is controlled.

### Three variants

The demonstration is the same network in three variants:

| Variant | File | Base threshold | Control | Expected |
|---|---|---|---|---|
| Flooded | `vehicles/vehicle12-daydreamer-flooded.yaml` | 1 | none | The pulse fires `idea[0]`, which fires two, and soon all 8 ideas are on, each kept on by its two predecessors. Both motors get the same input, so the vehicle drives straight ahead forever: one fixed behavior, no sequence. |
| Silent | `vehicles/vehicle12-daydreamer-silent.yaml` | 2 | none | One active idea cannot reach a threshold of 2, and the pulse alone cannot either. Nothing ever fires and the vehicle never moves. |
| Daydreamer | `vehicles/vehicle12-daydreamer.yaml` | 2 | `caudate` | Activity stays at a few ideas and passes from one to the next: a sequence of gestures, with no stimulus at all. |

The daydreamer is the silent variant plus the control unit:

```yaml
- unit:
    name: caudate
    type: threshold_control
    inputs:
      - input:
          from: idea[0:8]
    controls: [idea]
    target: 1
    rate: 0.5
    delay: 0.1                 # much shorter than an idea, to catch an explosion early
    jitter: 0.02
```

The values of `target`, `rate`, `delay` and `jitter` are a starting point, to be tuned when this is implemented. With so little activity at first, the control lowers the thresholds until ideas fire; if the pulse has passed by then, an idea fires on its own, and the vehicle wakes up by itself.

The scenario `scenarios/vehicle12-daydreamer.yaml` places the daydreamer in `worlds/open-field.yaml`, and `scenarios/vehicle12-daydreamer-flooded.yaml` and `scenarios/vehicle12-daydreamer-silent.yaml` place the other two variants the same way.

### Whether its thoughts vary

Jitter is fixed, so at each branch the same idea could always win, and the daydreamer would repeat one loop of gestures forever. For the train to vary, the same idea has to lead to different successors depending on where the oscillating threshold is when it fires. Whether it does is not known until it runs, and it is what the criteria below measure rather than assume.

### Not the wanderer

From outside, the daydreamer could be mistaken for a vehicle with the `wander` module, which moves at random. It is different inside: there is no noise, the same seed gives the same run, and each idea turns on because an idea wired to it was on, or, when the thresholds are low enough, on its own.

## Acceptance criteria

The values in criteria 7 and 8, and in the daydreamer's criteria 14 to 17, are to be set when this is implemented, as for earlier vehicles.

1. **Unchanged without control:** a vehicle with no control unit produces exactly the same trajectory, for the same seed, as before this spec.
2. **Effective threshold:** with jitter 0, a unit with `threshold` 1 and a sum of 1 fires with offset 0 and does not fire with offset +0.05. A unit with `threshold` 2 and a sum of 1 fires with offset -1.
3. **Firing on its own:** with jitter 0, a controlled unit with `threshold` 1 and no active input fires once the offset reaches -1.
4. **The rule:** with `rate` 0.5, `target` 2 and `dt` 0.05, the offset rises by 0.05 per step at activity 4 and falls by 0.05 per step at activity 0, without limits.
5. **Delay:** with `delay` 0.1 and `dt` 0.05, a new offset reaches the controlled units 2 steps after it is computed.
6. **Learning:** a Mnemotrix or Ergotrix connection into a controlled unit changes its strength step by step exactly as it does with offset 0 and jitter 0, whatever the actual offset and jitter.
7. **No explosion:** a recurrent network with a fixed seed reaches full activity without a control unit. With one, its mean activity stays near `target` over the run.
8. **No extinction:** the same network, with a control unit, after all its activity is stopped, fires again within a given time, because the offset falls until something fires.
9. **Jitter:** each difference lies within `[-jitter, jitter]`, the same seed gives the same differences and the same run, and they do not change during the run. With `jitter` 0, every difference is 0.
10. **Validation:** each failure case under *Loading and validation* raises an error naming the file and the key.
11. **Display:** the diagram shows the control unit, its inputs and its dashed `controls` arrows, without importing pygame, and the renderer draws its window without errors.
12. **Headless:** loading and running a vehicle with a control unit never imports pygame.

The daydreamer, with `noise_std` 0, for seeds 0 to 4, 120 s each:

13. **Waking up:** in all three variants, `wake` fires for one pulse at the start and never again.
14. **Flooded:** within a given time, all 8 ideas are on, and they stay on to the end. From then on, both motors run at the same speed.
15. **Silent:** no idea ever fires, and the vehicle does not move.
16. **Daydreamer:** ideas keep firing to the end of the run, at least 6 different ideas fire, and, after the first seconds, never more than a given number are on at once. The vehicle travels more than a given distance and its heading takes more than a given number of values (in steps of 10°).
17. **Trains:** most idea onsets are along a wire: the idea turns on while an idea wired to it was on within its window. The fraction is to be set when this is implemented.
18. **Deterministic:** the same seed gives the same sequence of ideas. Different seeds, which give different jitter, are reported but not required to give different sequences (see *Whether its thoughts vary*).

## Open questions

These belong to the version of the daydreamer that learns its ideas, and have to be settled before it is specified:

- **A daydreamer that learns.** Instead of wired by hand, its ideas would be learned with Ergotrix wires: by day it sees colored lights in fixed sequences, and at night it rehearses them.
- **Thinking would erase memory.** A train of thought needs Ergotrix wires between internal units. In the dark, such a wire's source fires, the real event never comes, and the wire loses `forget` ([vehicle-11.md](vehicle-11.md), *The rule*). With the Vehicle 11 values (`forget` 0.1), a wire at strength 1 goes inactive after three rehearsals. It probably needs a rule such as: only a source driven by its fixed inputs starts a wait.
- **Chaos is not guaranteed.** The delayed feedback should make activity oscillate, but it may settle into a periodic cycle rather than the chaotic dynamics Braitenberg mentions. That is why no criterion here asks for chaos. Whether it appears, and for which values of `rate` and `delay`, has to be tried.
- **The sequence module.** The Ergotrix circuit of Vehicle 11 is due to become a module in `modules/` once Vehicle 12 is its second user ([modules.md](modules.md)).

## Out of scope

- Ideas made of several units each (cell assemblies), instead of one unit per idea.
- Several control units for one unit, regional controls beyond listing the units in `controls`, and control units that watch or control each other.
- Reading a control unit's offset from other parts, such as a motor that slows down when thresholds are high.
- Limits on the offset, and control rules other than the accumulating one.
- Random noise in thresholds during a run.
