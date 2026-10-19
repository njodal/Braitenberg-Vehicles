"""Acceptance criteria of specs/worlds.md."""

import math
import subprocess
import sys

import pytest

from braitenberg.sim import Simulation, load_with_overrides, parse_args
from braitenberg.vehicle import Vehicle1Params
from braitenberg.world import WorldError, load_world
from conftest import DEFAULT_WORLD, REPO


# 1. Round trip
def test_loads_example_world():
    world = load_world(DEFAULT_WORLD)
    assert world.name == "Hot spot"
    assert world.description == "One heat source in the middle of the arena."
    assert (world.arena.width, world.arena.height, world.arena.edges) == (100, 100, "wrap")
    assert list(world.stimuli) == ["temperature"]
    source = world.stimuli["temperature"].sources[0]
    assert (source.position, source.intensity, source.falloff) == ((50, 50), 10, 15)
    [v] = world.vehicles
    assert (v.type, v.position, v.heading, v.sensor) == ("vehicle1", (20, 20), 0, "temperature")
    assert v.params == Vehicle1Params(gain=1.0, noise_std=0.3)
    assert (world.simulation.dt, world.simulation.seed) == (0.05, 0)


def test_heading_is_read_in_degrees(world_data, write_world):
    world_data["vehicles"][0]["heading"] = 90
    world = load_world(write_world(world_data))
    assert world.vehicles[0].heading == pytest.approx(math.pi / 2)


# 2. Defaults
def test_defaults(world_data, write_world):
    del world_data["arena"]["edges"]
    del world_data["simulation"]
    del world_data["vehicles"][0]["params"]
    world = load_world(write_world(world_data))
    assert world.arena.edges == "wrap"
    assert (world.simulation.dt, world.simulation.seed) == (0.05, 0)
    assert world.vehicles[0].params == Vehicle1Params()


# 3. Validation: each error names the file and the key
def remove(path):
    def change(data):
        *parents, last = path
        for k in parents:
            data = data[k]
        del data[last]
    return change


def set_value(path, value):
    def change(data):
        *parents, last = path
        for k in parents:
            data = data[k]
        data[last] = value
    return change


@pytest.mark.parametrize("change, key", [
    (remove(["arena"]), "arena"),
    (remove(["arena", "width"]), "arena.width"),
    (remove(["stimuli", "temperature", "sources", 0, "falloff"]),
     "stimuli.temperature.sources[0].falloff"),
    (set_value(["arena", "width"], "wide"), "arena.width"),
    (set_value(["simulation", "seed"], 1.5), "simulation.seed"),
    (set_value(["arena", "edges"], "sticky"), "arena.edges"),
    (set_value(["stimuli", "temperature", "sources", 0, "falof"], 15),
     "stimuli.temperature.sources[0].falof"),
    (set_value(["colour"], "blue"), "colour"),
    (set_value(["stimuli", "temperature", "sources", 0, "position"], [150, 50]),
     "stimuli.temperature.sources[0].position"),
    (set_value(["vehicles", 0, "position"], [20, -1]), "vehicles[0].position"),
    (set_value(["vehicles", 0, "sensor"], "light"), "vehicles[0].sensor"),
    (set_value(["vehicles", 0, "type"], "vehicle99"), "vehicles[0].type"),
    (set_value(["vehicles", 0, "params", "gian"], 2), "vehicles[0].params.gian"),
])
def test_validation_errors(world_data, write_world, change, key):
    change(world_data)
    path = write_world(world_data)
    with pytest.raises(WorldError) as excinfo:
        load_world(path)
    message = str(excinfo.value)
    assert str(path) in message
    assert key in message


def test_invalid_yaml_names_file(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("arena: [unclosed")
    with pytest.raises(WorldError, match="broken.yaml"):
        load_world(path)


# 4. Field values
def test_field_value_at_source_and_at_falloff():
    world = load_world(DEFAULT_WORLD)
    assert world.stimulus_at("temperature", 50, 50) == pytest.approx(10)
    assert world.stimulus_at("temperature", 50 + 15, 50) == pytest.approx(5)


def test_empty_sources_is_zero_everywhere(world_data, write_world):
    world_data["stimuli"]["temperature"]["sources"] = []
    world = load_world(write_world(world_data))
    assert world.stimulus_at("temperature", 30, 70) == 0
    assert (world.stimulus_at("temperature", [1, 2], [3, 4]) == 0).all()


# 5. Wrapped distance
def test_wrapped_distance(world_data, write_world):
    world_data["stimuli"]["temperature"]["sources"][0]["position"] = [98, 50]
    world = load_world(write_world(world_data))
    # x = 2 is 4 units from the source the short way around.
    assert world.stimulus_at("temperature", 2, 50) == pytest.approx(
        world.stimulus_at("temperature", 94, 50))

    world_data["arena"]["edges"] = "bounce"
    bounded = load_world(write_world(world_data, "bounded.yaml"))
    assert bounded.stimulus_at("temperature", 2, 50) < world.stimulus_at("temperature", 2, 50)


# 6. Seed override
def test_seed_override():
    args = parse_args([str(DEFAULT_WORLD), "--seed", "7"], DEFAULT_WORLD.name)
    world = load_with_overrides(args)
    assert world.simulation.seed == 7

    def final_pose():
        sim = Simulation(world)
        sim.run(500)
        v = sim.vehicles[0]
        return v.x, v.y, v.heading

    assert final_pose() == final_pose()


def test_default_world_argument():
    args = parse_args([], DEFAULT_WORLD.name)
    assert load_with_overrides(args).name == "Hot spot"


# 7. Headless
def test_headless_run_never_imports_pygame():
    code = (
        "import sys\n"
        "from braitenberg.sim import main\n"
        "main('vehicle1-hot-spot.yaml', ['--headless', '--steps', '100'])\n"
        "assert 'pygame' not in sys.modules, 'pygame was imported'\n"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=REPO,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "100 steps" in result.stdout
