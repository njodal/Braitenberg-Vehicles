"""Acceptance criteria of specs/worlds.md."""

import pytest

from braitenberg.world import load_world
from braitenberg.yamlfile import ConfigError
from conftest import HOT_SPOT, read


# 1. Round trip
def test_loads_example_world():
    world = load_world(HOT_SPOT)
    assert world.name == "Hot spot"
    assert world.description == "One heat source in the middle of the arena."
    assert (world.arena.width, world.arena.height, world.arena.edges) == (100, 100, "wrap")
    assert list(world.stimuli) == ["temperature"]
    source = world.stimuli["temperature"].sources[0]
    assert (source.position, source.intensity, source.falloff) == ((50, 50), 10, 15)


# 2. Defaults
def test_default_edges(write):
    data = read(HOT_SPOT)
    del data["arena"]["edges"]
    assert load_world(write(data)).arena.edges == "wrap"


# 3. Validation: each error names the file and the key
def remove(*path):
    def change(data):
        *parents, last = path
        for k in parents:
            data = data[k]
        del data[last]
    return change


def set_value(*path, value):
    def change(data):
        *parents, last = path
        for k in parents:
            data = data[k]
        data[last] = value
    return change


@pytest.mark.parametrize("change, key", [
    (remove("arena"), "arena"),
    (remove("arena", "width"), "arena.width"),
    (remove("stimuli", "temperature", "sources", 0, "falloff"),
     "stimuli.temperature.sources[0].falloff"),
    (set_value("arena", "width", value="wide"), "arena.width"),
    (set_value("arena", "edges", value="sticky"), "arena.edges"),
    (set_value("stimuli", "temperature", "sources", 0, "falof", value=15),
     "stimuli.temperature.sources[0].falof"),
    (set_value("colour", value="blue"), "colour"),
    (set_value("vehicles", value=[]), "vehicles"),  # vehicles belong in scenarios
    (set_value("stimuli", "temperature", "sources", 0, "position", value=[150, 50]),
     "stimuli.temperature.sources[0].position"),
])
def test_validation_errors(write, change, key):
    data = read(HOT_SPOT)
    change(data)
    path = write(data)
    with pytest.raises(ConfigError) as excinfo:
        load_world(path)
    assert str(path) in str(excinfo.value)
    assert key in str(excinfo.value)


def test_invalid_yaml_names_file(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("arena: [unclosed")
    with pytest.raises(ConfigError, match="broken.yaml"):
        load_world(path)


# 4. Field values
def test_field_value_at_source_and_at_falloff():
    world = load_world(HOT_SPOT)
    assert world.stimulus_at("temperature", 50, 50) == pytest.approx(10)
    assert world.stimulus_at("temperature", 50 + 15, 50) == pytest.approx(5)


def test_empty_sources_is_zero_everywhere(write):
    data = read(HOT_SPOT)
    data["stimuli"]["temperature"]["sources"] = []
    world = load_world(write(data))
    assert world.stimulus_at("temperature", 30, 70) == 0
    assert (world.stimulus_at("temperature", [1, 2], [3, 4]) == 0).all()


# 5. Wrapped distance
def test_wrapped_distance(write):
    data = read(HOT_SPOT)
    data["stimuli"]["temperature"]["sources"][0]["position"] = [98, 50]
    world = load_world(write(data))
    # x = 2 is 4 units from the source the short way around.
    assert world.stimulus_at("temperature", 2, 50) == pytest.approx(
        world.stimulus_at("temperature", 94, 50))

    data["arena"]["edges"] = "bounce"
    bounded = load_world(write(data, "bounded.yaml"))
    assert bounded.stimulus_at("temperature", 2, 50) < world.stimulus_at("temperature", 2, 50)
