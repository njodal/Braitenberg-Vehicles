# Vehicle 5 — Forager (energy)

## Summary

The third example of Vehicle 5, summarized in [vehicle-05.md](vehicle-05.md) next to the moth and the searcher. The forager is the searcher ([vehicle-05-searcher.md](vehicle-05-searcher.md)) with an **energy** store and a sense of its own energy ([vehicle-definition.md](vehicle-definition.md), *5. Energy*).

Moving uses energy; light recharges it. While the forager is hungry it behaves like the searcher: it zigzags until a light is in sight, then goes to it, and there it recharges. Once it is **full**, it zigzags away to explore, even with the light in plain sight, until it is hungry again and goes back to searching. It combines both ideas of Vehicle 5: a rhythm (the zigzag) and a memory (being full).

![Forager: it goes to the light while hungry, recharges, and zigzags away once full](images/vehicle5-forager.gif)

*The default scenario, first 90 seconds (seed 0, played at four times the speed). Watch `energy`, `full` and `seeking` in the panel.*

## Design

![Diagram of the forager: the searcher plus an energy sensor and the units that track hunger](images/vehicle5-forager.svg)

### Energy

```yaml
energy:
  initial: 50
  max: 100
  consumption: 1           # per unit of distance traveled
  charge_from: light
  charge_gain: 2           # per second, per unit of light at the body center
```

Moving at 3 to 6 units per second uses 3 to 6 energy per second. Near the light, where it reads 5 or more, the forager gains 10 or more per second, so it recharges in a few seconds; far from it, it drains in about 15 to 25 seconds.

### Full until hungry

If the forager simply explored whenever its energy was high, it would leave the light as soon as it crossed the line, drop just below it, turn back, and hover at the edge. Instead, as with the moth's `burned`, a unit that feeds back into itself remembers being full:

- `charged` fires when the energy reaches 90.
- `hungry` fires when the energy is 30 or less. It has threshold -30 and an inhibitory input from `energy`, so its sum is `-energy`, which reaches -30 exactly when the energy is down to 30.
- `full` is switched on by `charged`, keeps itself on, and is switched off by `hungry`.
- `seeking` = `sees` AND NOT `full`: go to a light only when one is in sight and the forager is not full.

### Units added to the searcher

| Unit | Inputs | Threshold | Fires when |
|---|---|---|---|
| `charged` | `energy` | 90 | energy ≥ 90 |
| `hungry` | inhibitory `energy` | -30 | energy ≤ 30 |
| `full` | `charged`, `full` (itself), inhibitory `hungry` | 1 | from `charged` until `hungry` |
| `seeking` | `sees`, inhibitory `full` | 1 | `sees` AND NOT `full` |

`zig`, `zag`, `seek_left` and `seek_right` take `seeking` where the searcher has `sees`: the forager zigzags unless seeking, and steers to the light while seeking.

### Other differences from the searcher

- An `energy` sensor, drawn at `[0, -0.8]`.
- `sees` has threshold 3: a light is in sight within about 37 units, so a hungry forager finds it sooner.
- The motors have `gain` 3 and `max_speed` 6, for a wider zigzag.

## Definition and scenario

- `vehicles/vehicle5-forager.yaml`: the definition above.
- `scenarios/vehicle5-forager.yaml`: one forager with energy 50 in `worlds/one-light.yaml` (a light at `[60, 50]`), starting at `[10, 70]` with heading 0, `dt` 0.01.

## Acceptance criteria

All behavior criteria use the default scenario, run headless for 240 seconds, and must hold for each of seeds 0 to 4.

1. **Recharges again and again:** `full` turns on at least 3 times.
2. **Full until hungry:** every time `full` turns on, the energy is at least 90; every time it turns off, the energy is at most 30.
3. **Leaves when full:** every time the forager has been full and then becomes hungry, it went at least 40 units from the light while full, beyond the range at which it sees it.
4. **Ignores the light while full:** whenever `full` has been on for at least 0.15 s, `seek_left` and `seek_right` are off. (The change passes through `seeking` and then the seek units, two delays of 0.05 s, and the seek units' simultaneity window holds `seeking`'s earlier value for one more.)
5. **Logic:** given an energy level and chosen eye readings, once the units' delays have passed: `charged` fires exactly when the energy is at least 90 and `hungry` exactly when it is at most 30; `full` turns on with `charged`, stays on as the energy falls, and turns off with `hungry`; `seeking` fires exactly when `sees` is on and `full` is off.

## Out of scope

- Energy that limits movement (a forager with no energy left keeps moving).
- Several lights, or lights that run out.
