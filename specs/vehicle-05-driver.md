# Vehicle 5 — Driver (traffic light)

## Summary

A fourth example of Vehicle 5 ([vehicle-05.md](vehicle-05.md)): a vehicle that **stops at a red traffic light** and goes on when it turns green.

The driver only moves in a straight line, at a constant speed, along a road with a traffic light beside it. It has two color sensors, one for red and one for green. If the light is green, it carries on at the same speed. If it is red, the driver stops a short distance before it and waits; when the light turns green again, it moves on. Once it has passed the light, the light no longer matters to it, until it comes around to it again.

It needs two features of the simulator: sources that switch on and off on a schedule ([worlds.md](worlds.md), *Schedules*), for the traffic light, and sensors that only see ahead ([vehicle-definition.md](vehicle-definition.md), *Field of view*), so that the driver ignores the light once it is behind it.

![Driver: it stops before the traffic light while it is red and goes on when it turns green](images/vehicle5-driver.gif)

*The default scenario, first 60 seconds (played at four times the speed). The road loops, so the driver comes back to the light on every lap: it stops at red (about 3 s), goes on at green (8 s), passes on green on the next lap (30 s), and stops again (48 s). Below the road, `red on` / `green on` shows the light's state; in the panel, `red_close` and `go` take turns.*

## World

`worlds/traffic-light.yaml`: a road 100 units long and 20 wide (`edges: wrap`, so the driver comes back to the light on every lap), with a traffic light at `[50, 13]`, 3 units to the side of the road's center line. The light is two sources at the same place, one per stimulus:

| Stimulus | Intensity | Falloff | Schedule |
|---|---|---|---|
| `red` | 10 | 15 | `{period: 16, on_at: 0, off_at: 8}`: red for the first 8 s of every 16 s |
| `green` | 10 | 15 | `{period: 16, on_at: 8, off_at: 16}`: green for the other 8 s |

Exactly one of the two is on at any time. A 16-second cycle (rather than, say, 12) makes the driver's arrivals alternate between red and green: a lap takes 20 seconds, and after waiting for green it arrives back 4 seconds into the next green phase. With a 12-second cycle it would arrive at red every time.

## Design

![Diagram of the driver: two color sensors, three units and one motor](images/vehicle5-driver.svg)

### Parts

- **Body:** `size` 4, `noise_std` 0, so it keeps to a straight line.
- **Sensors:** `red_eye` (reads `red`) at `[-0.3, 0.9]` and `green_eye` (reads `green`) at `[0.3, 0.9]`, side by side at the front, both with `field_of_view` 90: they see the light while it is ahead, up to 45° to either side, and not once the driver has passed it.
- **Motor:** a single `motor` on the center line, `[0, -0.8]`, so the driver never turns. `base_speed` 0, `gain` 5 and `max_speed` 5: it runs at 5 while it gets a signal, and stops dead without one.

### Units

| Unit | Inputs | Threshold | Fires when | Role |
|---|---|---|---|---|
| `red_close` | `red_eye` | 8 | the red light reads 8 or more: it is on, ahead, and about 7 units away or closer | Time to stop |
| `green_ahead` | `green_eye` | 1 | a green light is in sight ahead | Clear to go |
| `go` | inhibitory `red_close`, `green_ahead` | 0 | always, unless `red_close` is on and `green_ahead` is off | Drive |

The motor's only input is `go`. With threshold 0, `go` fires on its own: the driver moves unless something stops it. A close red light stops it. A green light ahead keeps it going even if, for some reason, a red one also reads close, so green always wins. With a working traffic light only one color is on at a time, so `go` is simply "not a red light close ahead".

### Seeing the light is not stopping for it

The driver stops **close to** a red light, not as soon as it sees it. Its red eye picks the light up from far away, but the reading is low there and grows as the driver gets closer. `red_close` only fires when the reading reaches 8; until then `go` stays on and the driver keeps going at full speed. Then it brakes at once, since the motor goes straight from 5 to 0.

| Driver's center before the light | `red_eye` reading | Stops? |
|---|---|---|
| 40 units | 1.3 | no, keeps going at 5 |
| 25 units | 2.9 | no |
| 15 units | 5.6 | no |
| 10 units | 7.6 | no |
| 8.4 units | 8.2 | **yes**: `red_close` fires and `go` turns off |

In the default scenario the driver starts 25 units before the light with the light already red. It covers the next 17 units at full speed, in 3.4 seconds, and stops 8.4 units before the light. The stopping distance is set by `red_close`'s threshold: a lower threshold would stop it earlier, farther from the light. Slowing down gradually as a red light gets closer, rather than braking at the line, is out of scope.

### Timing

Every unit has the default delay of 0.05 s. When the red light reaches the threshold, `red_close` turns on 0.05 s later and `go` turns off 0.05 s after that: the driver stops 0.1 s after crossing the stopping line, half a unit further on at 5 units per second. When the light turns green, `red_close` turns off and `green_ahead` on 0.05 s later, and `go` turns on again within another 0.1 s (its simultaneity window still holds the last `red_close` briefly).

If the light turns red when the driver is already within the stopping distance but has not yet passed it, the driver stops where it is, close to the light. Deciding to carry on in that case, like a driver who cannot stop in time on amber, is left for later.

With these values the driver comes to rest between about 7.5 and 8.5 units before the light.

## Definition and scenario

- `vehicles/vehicle5-driver.yaml`: the definition above.
- `scenarios/vehicle5-driver.yaml`: one driver on `worlds/traffic-light.yaml`, at `[25, 10]` with heading 0 (driving toward the light along the road's center line), `dt` 0.01. With these values its first arrival at the light is during a red phase and later arrivals fall in both phases.

## Acceptance criteria

All criteria use the default scenario, run headless for 120 seconds of simulated time (the driver has no noise, so one run covers them).

1. **Stops at red:** every time the driver comes to a stop, the red light is on, and the driver's center is between 5 and 9 units before the light along the road.
2. **Waits while red:** once stopped, the driver stays stopped until the light turns green.
3. **Goes on green:** within 0.15 s after the light turns green, a stopped driver is moving again at full speed.
4. **Does not stop on green:** every time the driver passes the light while it is green, its speed stays at 5.
5. **Ignores the light behind it:** after the driver has passed the light, it does not stop again until it comes back around to the light on its next lap, even when the light turns red behind it.
6. **One speed:** the driver's speed is always either 0 or 5.
7. **Logic:** once the units' delays have passed, `red_close` fires exactly when `red_eye` reads 8 or more, `green_ahead` exactly when `green_eye` reads 1 or more, and `go` exactly when `red_close` is off or `green_ahead` is on.

## Out of scope

- An amber phase and the decision to go on when it is too late to stop.
- Slowing down gradually as a red light gets closer (the driver brakes at once at the stopping line).
- Several traffic lights, other vehicles on the road, and turning.
