import copy
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
DEFAULT_WORLD = REPO / "worlds" / "vehicle1-hot-spot.yaml"


@pytest.fixture
def world_data():
    """The default world as a dict, to tweak and write back in tests."""
    return copy.deepcopy(yaml.safe_load(DEFAULT_WORLD.read_text()))


@pytest.fixture
def write_world(tmp_path):
    """Write a world dict to a YAML file and return its path."""
    def write(data, name="world.yaml"):
        path = tmp_path / name
        path.write_text(yaml.safe_dump(data))
        return path
    return write
