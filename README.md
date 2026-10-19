# Braitenberg-Vehicles
An implementation of the Vehicles described in the book [Vehicles](https://en.wikipedia.org/wiki/Braitenberg_vehicle) by Valentino Braitenberg, specially the most advanced ones

While there are many implementations of Braitenberg's Vehicles, almost all of them stop at Vehicle 4 (the simplest ones, which connect sensors directly to actuators). The goal of this repo is to implement Vehicles 5 and beyond, the ones that have a 'nervous system' between the sensors and the actuators.

## Running

Requires Python 3.11 or later.

```
pip install -e ".[dev]"
python -m braitenberg.vehicle1                      # opens a window with the default world
python -m braitenberg.vehicle1 worlds/vehicle1-hot-spot.yaml --headless --steps 100000
pytest
```

Worlds are YAML files in `worlds/` (see [specs/worlds.md](specs/worlds.md)).
