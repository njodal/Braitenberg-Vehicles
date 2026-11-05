# A CSCG learns the traffic light

An experiment outside the simulator. It asks how a clone-structured cognitive graph (CSCG; George et al., *Clone-structured graph representations enable flexible learning and vicarious evaluation of cognitive maps*, Nature Communications 2021) would learn the sequence that the [Vehicle 11 cautious driver](../../specs/vehicle-11.md) learns with Ergotrix wires.

```
python experiments/cscg/cscg.py            # graphs and predictions as text
python experiments/cscg/cscg.py --plot     # also save predictions.png
```

## The setup

The input is the light seen one tick at a time: each color repeats for as long as it is on, as in `VVVVVAAARRRR` (V green, A yellow, R red). The world's light lasts 4.5 s per color, but here the durations differ, so that the graph has to learn each one.

A CSCG is a hidden Markov model in which each color has several hidden states, its *clones*, and a clone can only emit its own color. Here each color has 6 clones. Training learns only the transitions between clones: soft EM (Baum–Welch) and then Viterbi EM, which keeps the transitions sparse, as in the paper. 150 cycles are enough.

## What it learns

**Fixed durations** (`VVVVVAAARRRR` over and over). Of the 18 clones it uses exactly 12, in one ring, every transition with probability 1:

```mermaid
flowchart LR
  V1 --> V2 --> V3 --> V4 --> V5 --> A1 --> A2 --> A3 --> R1 --> R2 --> R3 --> R4 --> V1
  classDef V fill:#97C459,stroke:#444
  class V1,V2,V3,V4,V5 V
  classDef A fill:#EF9F27,stroke:#444
  class A1,A2,A3 A
  classDef R fill:#F09595,stroke:#444
  class R1,R2,R3,R4 R
```

Each clone stands for a color *and a time within it*: V3 is "green, third tick". The graph learned to count without a clock.

**Varying durations** (each color lasts one tick more or less, at random: green 4–6, yellow 2–4, red 3–5). It is still a ring, but with skips and side paths, so that the paths through each color are as long as the durations it saw:

```mermaid
flowchart LR
  V1 -- 0.70 --> V2
  V1 -- 0.30 --> V6
  V6 --> V2
  V2 -- 0.35 --> V4
  V2 -- 0.65 --> V3
  V3 --> V4
  V4 --> V5
  V5 --> A1
  A1 -- 0.67 --> A2
  A1 -- 0.33 --> A4
  A2 --> A3
  A3 -- 0.60 --> A4
  A3 -- 0.40 --> R1
  A4 --> R1
  R1 -- 0.76 --> R2
  R1 -- 0.24 --> R6
  R6 --> R5
  R2 --> R3
  R3 -- 0.49 --> R5
  R3 -- 0.51 --> R4
  R4 --> R5
  R5 --> V1
  classDef V fill:#97C459,stroke:#444
  class V1,V2,V3,V4,V5,V6 V
  classDef A fill:#EF9F27,stroke:#444
  class A1,A2,A3,A4 A
  classDef R fill:#F09595,stroke:#444
  class R1,R2,R3,R4,R5,R6 R
```

Clones are numbered in the order of the likeliest cycle; V6 and R6 are clones on a side path. Where along a color the skips fall is up to EM.

## What it predicts

Seeing the light tick by tick, the CSCG keeps a belief over its clones and from it the probability of each color on the next tick:

![Next-color probabilities, tick by tick](predictions.png)

- **First cycle.** It does not know yet which green tick it is on: seeing the first V, any of the 5 green clones may be the last, so yellow is 20% likely. Each V without a change rules one out (25%, 33%, 50%, 100%). The first change of color tells it where it is in the ring. Starting to look halfway through the green is the same: it is unsure only until the first change.
- **From the second cycle on** it is certain. On V4 it says green; on V5, yellow with 100%.
- **Varying durations.** The first ticks of each color are certain; doubt appears only where the duration varies, and grows with time, like a hazard function: yellow 25% on the 4th green tick and 75% on the 5th; green 24% on the 3rd red tick and 49% on the 4th.

## Compared with the Ergotrix wires

| | Ergotrix (Vehicle 11) | CSCG |
|---|---|---|
| Where the sequence lives | Wires between colors (`sees_green → expects_yellow`) | Clones of each color, i.e. the context |
| When the next color comes | Not known: `expects_yellow` comes on as soon as green is seen; the driver needs `at_line` to decide when to stop | Known: P(yellow on the next tick) rises as the green goes on |
| Aliased sequences such as V→A→R→A→V | One wire `sees_yellow → expects_X` cannot tell what follows yellow | Two yellow clones, one for each context |
| State | Units on or off | A probability distribution over clones |

The last row is why this stays an experiment: putting a CSCG in a vehicle needs a new kind of unit with a probabilistic state, not just new wires. It is closer to HTM's temporal memory, and to Braitenberg's Vehicle 12, than to the Ergotrix wire.
