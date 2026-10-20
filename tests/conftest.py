import copy
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
HOT_SPOT = REPO / "worlds" / "hot-spot.yaml"
ONE_LIGHT = REPO / "worlds" / "one-light.yaml"
VEHICLE1 = REPO / "vehicles" / "vehicle1.yaml"
VEHICLE2A = REPO / "vehicles" / "vehicle2a-fear.yaml"
VEHICLE2B = REPO / "vehicles" / "vehicle2b-aggression.yaml"
VEHICLE3A = REPO / "vehicles" / "vehicle3a-love.yaml"
VEHICLE3B = REPO / "vehicles" / "vehicle3b-explorer.yaml"
VEHICLE4A = REPO / "vehicles" / "vehicle4a-orbiter.yaml"
VEHICLE4B = REPO / "vehicles" / "vehicle4b-decider.yaml"
VEHICLE5 = REPO / "vehicles" / "vehicle5-moth.yaml"
SEARCHER = REPO / "vehicles" / "vehicle5-searcher.yaml"
TWO_LIGHTS = REPO / "worlds" / "two-lights.yaml"
VEHICLE1_SCENARIO = REPO / "scenarios" / "vehicle1-hot-spot.yaml"
FEAR_AND_AGGRESSION = REPO / "scenarios" / "vehicle2-fear-and-aggression.yaml"
LOVE_AND_EXPLORER = REPO / "scenarios" / "vehicle3-love-and-explorer.yaml"
ORBITER_AND_DECIDER = REPO / "scenarios" / "vehicle4-orbiter-and-decider.yaml"
MOTH = REPO / "scenarios" / "vehicle5-moth.yaml"
SEARCHER_SCENARIO = REPO / "scenarios" / "vehicle5-searcher.yaml"


def read(path: Path):
    """A repo YAML file as a dict, to tweak and write back in tests."""
    return copy.deepcopy(yaml.safe_load(path.read_text()))


@pytest.fixture
def write(tmp_path):
    """Write a dict to a YAML file in a temporary folder and return its path."""
    def write(data, name="file.yaml"):
        path = tmp_path / name
        path.write_text(yaml.safe_dump(data, sort_keys=False))
        return path
    return write


def run_python(code: str) -> subprocess.CompletedProcess:
    """Run code in a fresh interpreter from the repo root (to check pygame is not imported)."""
    return subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True)
