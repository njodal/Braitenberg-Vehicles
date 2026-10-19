"""Vehicle 1 — Getting Around (specs/vehicle-01.md).

    python -m braitenberg.vehicle1 [world.yaml] [--headless --steps N] [--seed N]
"""

from braitenberg.sim import main

DEFAULT_WORLD = "vehicle1-hot-spot.yaml"

if __name__ == "__main__":
    main(DEFAULT_WORLD)
