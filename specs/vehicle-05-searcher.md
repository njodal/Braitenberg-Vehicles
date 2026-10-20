# Vehicle 5 — Searcher (zigzag)

## Summary

The second example of Vehicle 5, summarized in [vehicle-05.md](vehicle-05.md) next to the first, the moth. Where the moth shows that a loop of units can **remember**, the searcher shows that a loop of units can keep a **rhythm** of its own.

While the searcher sees no light, a small oscillator of three units makes it zigzag, turning left and right in turn, as a moth does when it has lost the trail of a scent and sweeps the air to find it again. As soon as a light is in sight, the oscillator is silenced and the searcher steers straight to the light.

![Searcher: it zigzags until the light is in sight, then goes straight to it](images/vehicle5-searcher.gif)

*The default scenario, first 20 seconds (seed 0, played at twice the speed). In the panel, `osc_b` and `osc_c` take turns until `sees` lights up; from then on `seek_left` and `seek_right` steer.*

## Design

![Diagram of the searcher: two eyes, an oscillator of three units, and the units that switch between zigzagging and seeking](images/vehicle5-searcher.svg)

### The oscillator

Braitenberg points out that a loop of units has a rhythm set by their delays. The simplest loop, a unit that silences itself, does oscillate, but unevenly: with the simultaneity window ([vehicle-definition.md](vehicle-definition.md)) its own output holds it off for an extra delay, so it stays on for one delay and off for about two. Used for steering, it would turn longer to one side than to the other and drive in circles. Two units that silence each other start together and stay in step.

The searcher uses a ring of three units, each silenced by the one before it: `osc_a` ← `osc_c` ← `osc_b` ← `osc_a`. All have threshold 0 (they fire on their own) and a delay of 0.3 s. An extra excitatory connection from `osc_a` to `osc_c` breaks the symmetry at the start, when all units are 0, so the ring does not lock into firing in step. The result: `osc_b` and `osc_c` are each on for the same time in every cycle, overlap briefly, and are never both off. Driving one motor each, they turn the searcher left and right by the same amount: a zigzag that keeps its overall direction.

### Parts

- **Body:** `size` 4, `noise_std` 0.1.
- **Sensors:** `left_eye` at `[-0.9, 0.9]` and `right_eye` at `[0.9, 0.9]`, both reading `light`.
- **Motors:** `left_motor` at `[-0.5, -0.7]` and `right_motor` at `[0.5, -0.7]`, with `base_speed` 3, `gain` 2 and `max_speed` 5. A motor runs at 3, and at 5 while it gets a signal.

### Units

| Unit | Inputs | Threshold | Fires when | Role |
|---|---|---|---|---|
| `osc_a` | inhibitory `osc_c` | 0 | on its own, unless `osc_c` is on | Oscillator |
| `osc_b` | inhibitory `osc_a` | 0 | on its own, unless `osc_a` is on | Oscillator: zig |
| `osc_c` | inhibitory `osc_b`, `osc_a` | 0 | on its own, unless `osc_b` is on and `osc_a` off | Oscillator: zag |
| `sees` | `left_eye`, `right_eye` | 4 | both eyes together read 4 or more (within about 30 units in `one-light`) | A light is in sight |
| `left_brighter` | `left_eye`, inhibitory `right_eye` | 0.05 | the left eye reads at least 0.05 more than the right | Light is to the left |
| `right_brighter` | `right_eye`, inhibitory `left_eye` | 0.05 | the right eye reads at least 0.05 more than the left | Light is to the right |
| `zig` | `osc_b`, inhibitory `sees` | 1 | `osc_b` AND NOT `sees` | Turn left while searching |
| `zag` | `osc_c`, inhibitory `sees` | 1 | `osc_c` AND NOT `sees` | Turn right while searching |
| `seek_left` | `left_brighter`, `sees` | 2 | light to the left AND in sight | Turn toward it |
| `seek_right` | `right_brighter`, `sees` | 2 | light to the right AND in sight | Turn toward it |

The oscillator units have a delay of 0.3 s; the rest have the default 0.05 s.

### Motors

To turn left the right motor speeds up; to turn right, the left one does.

| Motor | Inputs (all excitatory) |
|---|---|
| `right_motor` | `zig`, `seek_left` |
| `left_motor` | `zag`, `seek_right` |

## Definition and scenario

- `vehicles/vehicle5-searcher.yaml`: the definition above.
- `scenarios/vehicle5-searcher.yaml`: one searcher in `worlds/one-light.yaml` (a light at `[60, 50]`), starting at `[10, 70]` with heading 0, so the light is out of sight at first; `dt` 0.01 so that delays are resolved finely, as for the moth.

## Acceptance criteria

1. **Zigzag:** in a world without light and with `noise_std` 0, after the first 3 seconds the searcher's heading swings back and forth by at least 30°, the same in every cycle: it keeps its overall direction instead of turning in circles.
2. **Even turns:** over whole oscillator cycles, `osc_b` is on alone for the same time as `osc_c` (within 2%), and at least one of them is always on.
3. **Finds the light:** in the default scenario, for each of seeds 0 to 4, the searcher comes within 2 units of the light within 30 seconds.
4. **Straight to the light:** whenever `sees` has been on for at least 0.1 s, `zig` and `zag` are off.
5. **Logic:** given chosen eye readings and oscillator outputs, once the units' delays have passed: `sees` fires exactly when the eyes together read 4 or more; `zig` exactly when `osc_b` is on and `sees` off, `zag` likewise with `osc_c`; `seek_left` exactly when `left_brighter` and `sees` are on, `seek_right` likewise.

## Out of scope

- Wider sweeps that grow while the light stays out of sight, as real moths do (would need a slower, adjustable rhythm).
- Combining the searcher with the moth's memory.
