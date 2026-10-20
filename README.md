# Braitenberg-Vehicles
An implementation of the Vehicles described in the book [Vehicles](https://en.wikipedia.org/wiki/Braitenberg_vehicle) by Valentino Braitenberg, specially the most advanced ones

While there are many implementations of Braitenberg's Vehicles, almost all of them stop at Vehicle 4 (the simplest ones, which connect sensors directly to actuators). The goal of this repo is to implement Vehicles 5 and beyond, the ones that have a 'nervous system' between the sensors and the actuators.

## Running

Requires Python 3.11 or later.

```
pip install -e ".[dev]"
python -m braitenberg scenarios/vehicle1-hot-spot.yaml        # opens a window
python -m braitenberg scenarios/vehicle2-fear-and-aggression.yaml
python -m braitenberg scenarios/vehicle3-love-and-explorer.yaml
python -m braitenberg scenarios/vehicle4-orbiter-and-decider.yaml
python -m braitenberg --world worlds/one-light.yaml --vehicle vehicles/vehicle2b-aggression.yaml
python -m braitenberg scenarios/vehicle1-hot-spot.yaml --headless --steps 100000
pytest
```

A simulation is built from three kinds of YAML files: worlds (`worlds/`), vehicle definitions (`vehicles/`) and scenarios that combine them (`scenarios/`). See [specs/scenarios.md](specs/scenarios.md).
