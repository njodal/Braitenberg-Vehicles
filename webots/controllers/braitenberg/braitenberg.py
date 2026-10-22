"""Webots controller: runs the vehicle definition named in controllerArgs (specs/webots.md)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))   # the repo root

from controller import Robot  # noqa: E402  (Webots' module, only available inside Webots)

from braitenberg.webots import main  # noqa: E402

main(Robot(), sys.argv[1:])
