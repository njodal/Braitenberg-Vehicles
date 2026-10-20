# Braitenberg-Vehicles
An implementation of the Vehicles described in the book [Vehicles](https://en.wikipedia.org/wiki/Braitenberg_vehicle) by Valentino Braitenberg, specially the most advanced ones

While there are many implementations of Braitenberg's Vehicles, almost all of them stop at Vehicle 4 (the simplest ones, which connect sensors directly to actuators). The goal of this repo is to implement Vehicles 5 and beyond, the ones that have a 'nervous system' between the sensors and the actuators.

## Examples

### Vehicle 5 — A moth that learns not to get burned

![The moth flies to the left light and gets burned; later it comes back toward the same light but turns away well before reaching it](specs/images/vehicle5-moth.gif)

The moth is drawn to light and steers toward it. When it gets too close it gets burned: a *pain* unit fires and switches on a *burned* unit that feeds back into itself, so it stays on for good. From then on the same vehicle keeps its distance from every light. Its behavior depends on its history, which no vehicle without a nervous system can do. In the panel on the right you can watch `pain` and `burned` light up at the moment of the burn.

The whole brain is nine threshold units, described in [vehicles/vehicle5-moth.yaml](vehicles/vehicle5-moth.yaml):

![Diagram of the moth: two eyes, nine threshold units and two motors](specs/images/vehicle5-moth.svg)

```
python -m braitenberg scenarios/vehicle5-moth.yaml
```

See [specs/vehicle-05.md](specs/vehicle-05.md) for the design.

## Running

Requires Python 3.11 or later.

```
pip install -e ".[dev]"
python -m braitenberg scenarios/vehicle1-hot-spot.yaml        # opens a window
python -m braitenberg scenarios/vehicle2-fear-and-aggression.yaml
python -m braitenberg scenarios/vehicle3-love-and-explorer.yaml
python -m braitenberg scenarios/vehicle4-orbiter-and-decider.yaml
python -m braitenberg scenarios/vehicle5-moth.yaml
python -m braitenberg --world worlds/one-light.yaml --vehicle vehicles/vehicle2b-aggression.yaml
python -m braitenberg scenarios/vehicle1-hot-spot.yaml --headless --steps 100000
pytest
```

A simulation is built from three kinds of YAML files: worlds (`worlds/`), vehicle definitions (`vehicles/`) and scenarios that combine them (`scenarios/`). See [specs/scenarios.md](specs/scenarios.md).

## Images for the specs

```
python -m braitenberg.diagram vehicles/vehicle5-moth.yaml --out specs/images/vehicle5-moth.svg
python -m braitenberg.record scenarios/vehicle5-moth.yaml --seconds 40 --out specs/images/vehicle5-moth.gif
```

`diagram` draws a vehicle definition as an SVG. `record` plays a scenario without a window and saves it as a GIF (needs `pip install -e ".[record]"`).
