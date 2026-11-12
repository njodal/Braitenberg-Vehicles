# Vehicle 13 — Foresight: once bitten

**Status:** specified, not implemented. The values below are starting points, to be tuned on seeds 0 to 4 (see *Timing*).

## Summary

Braitenberg's chapter on Vehicle 13 ("Foresight") asks how a vehicle can act toward a goal, which lies in the future, without an effect coming before its cause. His answer: it acts on what it **expects** to happen, and the expectation is there now. All it takes is stored sequences of events, which the Ergotrix wires of Vehicle 11 ([vehicle-11.md](vehicle-11.md)) already are, played back faster than the world plays them. A brain that does that is a **predictor**.

A predictor learns from statistics: a sequence seen many times gets a strong wire, one seen once does not. That is the right thing most of the time, and the wrong thing for a rare event that matters. His example: most green vehicles are peaceful, but now and then one is vicious. A vehicle that waited for the statistics would keep being attacked, so it should take the one decisive experience seriously and treat every green vehicle as bad.

His device for this, the book's figure 21, has four parts:

- **R**, the realistic half brain, which receives only fresh input from the senses.
- **P**, the predicting half brain, fed by R, in which the Ergotrix wires learn and predict.
- **A short-term memory**, a chain of two delay elements fed by R: an echo of the last two moments.
- **D**, the Darwinian evaluator, which judges what happens as good or bad. It is a Vehicle 6, selected for avoiding danger and seeking advantage, with its motors taken away: the wire that went to the forward motor now means "good", the one that went to the backward motor "bad".

Normally R feeds P. When D signals something very unpleasant (or very pleasant), two switches turn: P is cut off from R and fed from the end of the short-term memory instead, and its output goes back into the memory's start. The moments just before the event go round this loop, over and over, until D calms down. Each turn is one more pairing for P's Ergotrix wires, so a sequence met once is learned as if it had been met many times. The internal reverberation "turns them into high-frequency events in the inner workings of the brain".

From outside, Braitenberg says, the vehicle then seems to avoid certain places and vehicles, and to have an irrational affection for others, until one finds the single event behind each. Every Vehicle 13 builds its own character from the particular experiences of its early life.

This spec builds that device into one vehicle, the **once-bitten** vehicle, and puts it among green vehicles: four peaceful **grazers** and one **bully** that rams it. All five look the same. Bitten once, it learns that green comes before pain, and from then on it flees from every green vehicle that comes close, grazers included.

It needs no new kind of part: threshold units, unit delays and Ergotrix wires are enough.

## From the book to the vehicle

| Book | Here |
|---|---|
| The realistic half brain R | `r_green` and `r_hurt`: a green vehicle has come close; it has been touched |
| The predicting half brain P | `p_green` and `p_hurt`, with an Ergotrix wire `p_green → p_hurt` |
| The two delay elements d | `echo1_` and `echo2_` for each of green and hurt, each one moment long |
| The Darwinian evaluator D | `touched` and `upset`: being rammed is bad, and upsets it for a while |
| The two switches | Gate units, opened by `calm` or by `upset` |
| The predictor's output | `p_hurt` makes the vehicle `afraid`: it turns away from green and runs |

Only bad events are built. Pleasant ones, which would give it its "irrational affection", work the same way with a D that signals good, and are left for later (see *Out of scope*).

## The world

`worlds/green-field.yaml`: a 100 × 100 arena with `edges: wrap` and three stimuli:

| Stimulus | Sources | Meaning |
|---|---|---|
| `green` | none | The color of the grazers and the bully, seen by cameras only |
| `blue` | none | The color of the once-bitten vehicle, which the bully's camera looks for |
| `proximity` | none; `surfaces` with `intensity` 10, `falloff` 2 | Nearness of other vehicles' bodies ([worlds.md](worlds.md), *The proximity field*): 10 inside one |

Nothing shines and there are no obstacles. Vehicles do not block each other, so a bully that rams the once-bitten vehicle drives through it; contact is what it feels.

## The other vehicles

### The grazer

`vehicles/vehicle13-grazer.yaml`: the Vehicle 9 walker ([vehicle-09.md](vehicle-09.md)) with a different color and a reflex to keep clear. `size` 4, `height` 2, `noise_std` 0.8, two motors with `base_speed` 2. Its `appearance` is `green: 10` and `blue: 0`.

Two infrared sensors at `[-0.6, 0.9]` and `[0.6, 0.9]`, reading `proximity`, with `field_of_view` 90, are wired to the motor on their own side, as Vehicle 2a's fear ([vehicle-02.md](vehicle-02.md)): something close on the left speeds up the left wheel and turns it away to the right. So a grazer never touches anything: it is peaceful by construction.

### The bully

`vehicles/vehicle13-bully.yaml`: the Vehicle 9 chaser, green. `size` 4, `height` 2, `noise_std` 0.3, `appearance` `green: 10` and `blue: 0`, exactly as the grazer looks. Its camera sees `blue`: 18 columns of 5° across 90°, one row, `range` 25, `response: {type: step, at: 1}`, wired crossed to the motors, as the chaser's, so that it turns toward the once-bitten vehicle and drives at it. `base_speed` 2, up to 4: faster than the once-bitten vehicle wanders, slower than it runs. It has no infrared sensors, so nothing stops it from ramming.

While the once-bitten vehicle is out of its camera's range, the bully wanders on its noise like a grazer. When it has rammed and driven through, it turns back and comes again.

## The once-bitten vehicle

### Parts

- **Body:** `size` 4, `height` 2, `noise_std` 0.2. Its `appearance` is `blue: 10`, for the bully, and `green: 0`.
- **Camera:** `eye` at `[0, 0]`, `type: green`, `field_of_view` 360, `columns` 24 (15° each), `rows` 1, `vertical_field_of_view` 20, `height` 1, `range` 30. It sees all around: columns 0 to 11 are the left half, from behind to straight ahead, and 12 to 23 the right half.
- **Infrared:** `ir_left` and `ir_right`, as the grazer's, and wired to the motors the same way, so it does not run into grazers either.
- **Touch:** `skin` at `[0, 0]`, reading `proximity`, seeing all around. It reads 5 when another body just touches its own, 2 units from its center, and 10 when the other body covers its center: what a bully that drives through it does.
- **Motors:** `left_motor` at `[-0.5, -0.8]` and `right_motor` at `[0.5, -0.8]`, `base_speed` 1.5, `max_speed` 6.

### Units

The units are in five groups. Each name ending in `_X` is written twice, once for `green` and once for `hurt`.

#### The senses and R

| Unit | Inputs | Threshold | Delay | Fires when |
|---|---|---|---|---|
| `green_near` | `eye[0, :]` | about 9, tuned | 0.05 | a green vehicle within about 12 units |
| `touched` | `skin` | 8 | 0.05 | another body overlaps its own, within 1 unit of its center |
| `was_green`, `was_hurt` | `green_near`, `touched` | 1 | 0.5 | the same, half a second late |
| `r_green` | `green_near`, inhibitory `was_green` | 1 | 0.05 | a green vehicle **has just come** close: a pulse of about 0.5 s |
| `r_hurt` | `touched`, inhibitory `was_hurt` | 1 | 0.05 | it **has just been** touched |

R is made of **onsets**, not states. A green vehicle that stays close is one event, not a long one: the Ergotrix rule learns from onsets ([vehicle-11.md](vehicle-11.md), *Why onsets*), and the short-term memory below has room for a pulse, not for a state that lasts.

#### D, the Darwinian evaluator

| Unit | Inputs | Threshold | Delay | Fires when |
|---|---|---|---|---|
| `upset` | `touched`, itself, inhibitory `calm_down` | 1 | 0.3 | from 0.35 s after a touch, for `U` seconds |
| `calm_down` | `upset` | 1 | `U` = 20 | `upset` has been on for `U` seconds |
| `calm` | inhibitory `upset` | 0 | 0.05 | whenever it is not upset |

`upset` holds itself on until `calm_down` turns it off, the Vehicle 9 pattern for a step of fixed length ([vehicle-09.md](vehicle-09.md), *Fleeing*). D is not learned. It is the "important, ancient, intuitive knowledge" that Braitenberg gives the vehicle ready-made: being rammed is bad. Its delay is longer than R's on purpose: the switches must turn only after the touch has entered the short-term memory (see *Timing*).

`calm_down` stays on for a while after `upset` goes off, so a second touch soon after the first does not upset it again. One upset per encounter is what the vehicle needs.

#### The switches

| Unit | Inputs | Threshold | Delay | Fires when |
|---|---|---|---|---|
| `w_X` | `r_X`, `calm` | 2 | 0.05 | R's event, while calm: **from the world** |
| `e_X` | `echo2_X`, `upset` | 2 | 0.05 | the end of the memory, while upset: **from the echo** |
| `l_X` | `p_X`, `upset` | 2 | 0.05 | P's output, while upset: **round the loop** |

Each is an AND of a signal and a switch, so `calm` and `upset` together are the two switches of figure 21, thrown at once.

#### The short-term memory and P

| Unit | Inputs | Threshold | Delay | Fires when |
|---|---|---|---|---|
| `echo1_was_X` | `w_X`, `l_X` | 1 | 0.05 | `echo1_X`'s input, a moment late |
| `echo1_X` | `w_X`, `l_X`, inhibitory `echo1_was_X` | 1 | `T` = 2.5 | a short pulse, one moment (`T`) after an event, from the world or from P |
| `echo2_was_X` | `echo1_X` | 1 | 0.05 | `echo2_X`'s input, a moment late |
| `echo2_X` | `echo1_X`, inhibitory `echo2_was_X` | 1 | `T` = 2.5 | a short pulse, two moments after it |
| `p_green` | `w_green`, `e_green` | 1 | 0.3 | green comes, in the world or in the echo |
| `p_hurt` | `w_hurt`, `e_hurt`; **Ergotrix** from `p_green`, strength 0, `within` 5, `learn` 0.25, `forget` 0.02 | 1 | 0.3 | hurt comes, in the world or in the echo, or, once learned, green comes |

So the memory is fed from the world while calm (`w_X`), and from P while upset (`l_X`); P is fed from the world while calm (`w_X`), and from the end of the memory while upset (`e_X`). While upset, `echo1 → echo2 → e → p → l → echo1` is a closed loop, which goes round in `2T + 0.4` s, 5.4 s.

Each echo unit is a **delay element**: its `was` copy stops it as soon as it starts, so whatever the length of what comes in, it gives out a pulse of about 0.05 s, `T` later. That is what keeps the loop going (see *Timing*).

The Ergotrix wire learns only from `p_hurt`'s fixed inputs, `w_hurt` and `e_hurt`, never from its own predictions ([vehicle-11.md](vehicle-11.md), *Why fixed inputs only*). An echo of hurt is a fixed input: as far as the wire can tell, it is hurt coming after green again.

#### Fleeing

| Unit | Inputs | Threshold | Delay | Fires when |
|---|---|---|---|---|
| `afraid` | `p_hurt`, itself, inhibitory `brave` | 1 | 0.05 | from when hurt is predicted, for about 2 s |
| `brave` | `afraid` | 1 | 2 | `afraid` has been on for 2 s |
| `green_left` | `eye[0, 0:12]` | about 2, tuned | 0.05 | something green on the left, within range |
| `green_right` | `eye[0, 12:24]` | the same | 0.05 | something green on the right |
| `away_left` | `green_left`, `afraid` | 2 | 0.05 | afraid, with green on the left |
| `away_right` | `green_right`, `afraid` | 2 | 0.05 | afraid, with green on the right |
| `strolling` | inhibitory `afraid` | 0 | 0.05 | not afraid |

The module `wander` ([modules.md](modules.md), *The wander module*), enabled by `strolling`, turns it now and then while it is not afraid.

Both motors have `gain` 0.5. `left_motor` takes `away_left` three times, `afraid` three times, `wander.right` three times and `ir_left`; `right_motor` the same on the other side. So it wanders at 1.5; when afraid it runs at 3 straight on, and at 4.5 on the wheel on the green side, which turns it away from the green vehicle. Green on both sides, it runs straight. Infrared adds up to 5 to the wheel on the side of something close.

A vehicle that is upset relives the event: each echo of hurt fires `p_hurt`, and makes it afraid again. Braitenberg does not say what D does to the motors; here it does nothing directly, and the vehicle runs only from what P predicts.

### How it behaves

- **Before it is bitten,** green means nothing. Grazers come close and go, and each one fires `r_green` and `p_green`; the wire starts a wait, no hurt comes within 5 s, and it loses `forget`, which leaves it at 0.
- **Bitten.** The bully comes into range and drives at it. `green_near` turns on when it is about 12 units away, and stays on. One to four seconds later it touches: `r_hurt` fires, `p_hurt` follows `p_green` within the wait, and the wire gains 0.25, its one real pairing. Then `upset` turns on and the switches turn.
- **Reverberation.** The loop holds what happened in the last 5 s or so: green coming, then hurt. Every 5.4 s, `p_green` turns on, then `p_hurt` the same 1 to 4 s later: one more pairing each turn, with no green vehicle in sight. In 20 s of upset it goes round three times, and the wire reaches 1.
- **Once learned,** a green vehicle coming close fires `p_green`, and `p_hurt` one delay later, 0.3 s: the vehicle expects to be hurt, and is running from it about 0.85 s after the green vehicle came within 12 units, while the bully is still 7 units away or more. It does that for grazers too, which have never hurt it. It **foresees** a ramming that, for a grazer, would never come.
- **Forgetting.** Every grazer it runs from is a prediction that failed: `p_green` fires and no hurt follows, so the wire loses 0.02. It stays above 0.7 for at least 15 such encounters. With the bully still about, it is bitten again now and then, and relearns. Like the wary moth of Vehicle 7 ([vehicle-07.md](vehicle-07.md)), it checks its rule only by running into the exceptions.
- **Without reverberation** (the control, with `upset` never firing), one bite gives one pairing, 0.25, and grazers' failed predictions wear it down between bites. The bully has to ram it several times, each time with green coming close first, before the wire passes 0.7, if it ever does.

### Timing

The values of `T`, `U`, `learn` and the thresholds of `green_near` are tied together by four constraints. The values above meet them on paper and are to be checked on seeds 0 to 4.

1. **The event fits in the memory.** When the switches turn, the loop keeps what is in `echo1` and `echo2` at that moment, and loses what has already passed through them into P. So green must have come close less than about `2T` before the touch, minus D's delay: with `T` 2.5, up to about 4.6 s. The bully closes in at 2.5 to 5.5 units a second, depending on which way the vehicle is going, so from 12 units it touches in 1.4 to 4.4 s.
2. **The touch is in the memory before the switches turn.** `r_hurt` reaches `echo1_hurt` about 0.15 s after the touch; `upset` turns the switches at 0.35 s.
3. **Pulses must not fill the loop.** A unit counts an input for its whole delay ([vehicle-definition.md](vehicle-definition.md), *Units*), so a pulse that goes through a unit with delay `T` comes out `T` longer. With plain units, a pulse would grow by the loop's whole length each turn and soon be on all the time, with no onsets left to learn from. One sharpened unit per loop is not enough either: its `was` copy, counted for its whole delay, keeps it from firing again until the long pulse that comes back has been off for a while, which it never is. So both echo units are sharpened, and each gives out a pulse of about 0.05 s; P and the gates widen it to about 0.45 s, far shorter than the loop. An echo unit cannot fire again for about `T` after it fires, which is less than the loop's 5.4 s.
4. **Enough turns.** One real pairing must not be enough (`learn` 0.25 ≤ 0.7), and one pairing plus the turns while upset must be (`U` / 5.4 s, three turns, 1.0 > 0.7). And `within`, 5 s, must be longer than the gap between green and hurt, in the world and in the loop, for the pairings to count.

There is a tension between the first constraint and foresight: the farther away `green_near` sees a green vehicle, the earlier the vehicle can run, but the longer the memory has to be. Braitenberg's remedy, a predictor that plays back faster than the world, is what makes foresight cheap here: the prediction takes one unit delay, 0.3 s, however long the real sequence took.

### Diagram and panel

As for the Vehicle 11 cautious driver ([vehicle-11.md](vehicle-11.md), *Diagram and panel*). The units are placed in four rows, from front to back: R and D; the switches; the memory and P, with the loop drawn as a ring; and fleeing. Watch `upset` light up after a bite, and the pulses go round `echo1`, `echo2` and `p` while `p_green->p_hurt  E` climbs in steps, one per turn.

## Definitions, world and scenarios

- `vehicles/vehicle13-once-bitten.yaml`: the once-bitten vehicle, `general.type` `"13"`, named *Once bitten (learns from one bad encounter)*.
- `vehicles/vehicle13-grazer.yaml` and `vehicles/vehicle13-bully.yaml`: the green vehicles.
- `worlds/green-field.yaml`: the world above.
- `scenarios/vehicle13-once-bitten.yaml`: the once-bitten vehicle at `[50, 50]`, heading 90; four grazers at `[25, 25]`, `[75, 25]`, `[25, 75]` and `[75, 75]`, with headings 45, 135, 315 and 225; the bully at `[10, 90]`, heading 0, far enough that the once-bitten vehicle meets grazers before the bully finds it; `dt` 0.01.
- `specs/images/vehicle13-once-bitten.svg` and `specs/images/vehicle13-once-bitten.gif`: the diagram and a recording.

```
python -m braitenberg scenarios/vehicle13-once-bitten.yaml
python -m braitenberg.diagram vehicles/vehicle13-once-bitten.yaml --out specs/images/vehicle13-once-bitten.svg
python -m braitenberg.record scenarios/vehicle13-once-bitten.yaml --seconds 120 --every 0.25 --speed 8 --scale 0.5 --out specs/images/vehicle13-once-bitten.gif
```

## Related specs

- [vehicle-11.md](vehicle-11.md): the Ergotrix wire, and the split between what is seen and what is expected.
- [vehicle-12.md](vehicle-12.md): trains of thought, sequences that run inside the brain with the senses silent; its open question on thinking that erases memory.
- [vehicle-06.md](vehicle-06.md): selection, which in the book makes D.
- [vehicle-09.md](vehicle-09.md): the walker and the chaser that the grazer and the bully are built from, and the pattern for steps of fixed length.
- [camera.md](camera.md): the eye, and vehicles' colors.
- [worlds.md](worlds.md): the proximity field, which gives touch.

## Acceptance criteria

Criteria 1 to 6 use the default scenario, run headless for 300 s, and must hold for each of seeds 0 to 4. A **bite** is an onset of `touched`. The **wire** is `p_green → p_hurt`. A **control** is the same once-bitten definition without `touched` among `upset`'s inputs, so that it is never upset and never reverberates.

1. **Grazers are harmless:** in the default scenario without the bully, the once-bitten vehicle is never touched, the wire stays at 0, and `afraid` never fires.
2. **Learns from one bite:** the wire is at 0 until the first bite, and exceeds 0.7 before `upset` goes off after it, with no second bite in between.
3. **Reverberation:** while `upset` is on after the first bite, `e_green` and `e_hurt` each turn on at least twice, every onset of `e_hurt` comes 0.5 to 5 s after an onset of `e_green`, and `w_green` and `w_hurt` never fire: P learns from the echo alone.
4. **The control does not:** in the control, the wire is at most 0.25 after the first bite and does not exceed 0.7 in the 30 s that follow.
5. **Fears every green vehicle:** after the wire first exceeds 0.7, and for the next 60 s, `afraid` turns on within 1 s after at least 80% of the onsets of `r_green` while `calm` is on; at least one of them is for a grazer (the nearest green vehicle is a grazer), and in the 3 s after it the distance to that grazer grows.
6. **Fewer bites:** over seeds 0 to 4 together, from each seed's first bite to the end of the run, the once-bitten vehicle is bitten at most half as often as the control.
7. **The switches:** with chosen unit outputs, while `calm` is on, `r_green` fires `p_green` and `echo1_green`, and `echo2_green` fires neither; while `upset` is on, `r_green` fires neither, `echo2_green` fires `p_green`, and `p_green` fires `echo1_green`.
8. **The loop:** with `upset` held on and a single pulse put into `echo1_green` and, 2 s later, into `echo1_hurt`, `p_green` and `p_hurt` each turn on once per turn of the loop, every 5.4 ± 0.3 s, the same 2 ± 0.3 s apart, for as long as `upset` is on; they stop when it goes off.
9. **Remembers:** after the wire first exceeds 0.7, it stays above 0.7 for at least 15 onsets of `r_green` with no bite in between.
10. **Headless and fast:** loading and running the scenario never imports pygame, and 300 simulated seconds run headless in under 30 s.

## Out of scope

- **The comparator.** Braitenberg also gives the vehicle two half brains connected point to point by inhibition, so that what is seen and what was predicted cancel out and only the **discrepancies** stand out, and a rule, "when in doubt, believe the sensors", that switches the predictor off when they disagree (figure 20). Here P never contradicts R about the same moment: it predicts hurt, and R says whether it came. A vehicle whose predictor runs ahead several steps, and has to be checked against what then comes, needs them.
- **Following what is hidden.** Braitenberg's other example: a Vehicle 13 that follows a moving object, and when it disappears behind an obstacle heads for where it will show up again. That needs a predictor of positions, not of events.
- **Several outcomes at once.** A good predictor keeps several possible outcomes in mind in parallel, as a driver does in a street where children are playing.
- **Speeding up on demand.** A predictor that plays back faster only when needed, for example in danger. Here it is always fast: an active Ergotrix wire fires its destination one unit delay after its source ([vehicle-11.md](vehicle-11.md), *Out of scope*).
- **Pleasant events.** A D that signals good, and reverberation that makes the vehicle seek what came before it: the "irrational affection". It needs a second output of D and a behavior to approach, and is built the same way.
- **Meditation.** Mnemotrix wires that grow while an idea stays on and recruit new elements into it, the first of the three influences on a vehicle's mental state in the chapter.
- **D by selection.** D here is written by hand. Evolving it with Vehicle 6 is left for later.
- **Character.** Several once-bitten vehicles in one field, each meeting the bully at a different time, or not at all, and each ending up with a different fear.
