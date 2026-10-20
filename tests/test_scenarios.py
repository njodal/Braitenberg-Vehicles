"""Acceptance criteria of specs/scenarios.md."""

import math

import pytest

from braitenberg.scenario import load_scenario, quick_scenario
from braitenberg.sim import Simulation, parse_args, scenario_from_args
from braitenberg.yamlfile import ConfigError
from conftest import (FEAR_AND_AGGRESSION, HOT_SPOT, ONE_LIGHT, VEHICLE1, VEHICLE1_SCENARIO,
                      VEHICLE2A, VEHICLE2B, read, run_python)


# 1. Load
def test_loads_example_scenario():
    s = load_scenario(FEAR_AND_AGGRESSION)
    assert s.name == "Fear and aggression"
    assert s.world.name == "One light"
    assert [p.definition.general.name for p in s.vehicles] == ["Fear", "Aggression"]
    assert [p.position for p in s.vehicles] == [(35, 44), (35, 56)]
    assert [p.heading for p in s.vehicles] == [0, 0]
    assert [p.label for p in s.vehicles] == ["Fear #0", "Aggression #1"]
    assert (s.simulation.dt, s.simulation.seed) == (0.05, 0)


def test_label_and_defaults(write):
    data = {"name": "Test", "world": str(ONE_LIGHT),
            "vehicles": [{"vehicle": {"definition": str(VEHICLE2B), "position": [10, 10],
                                      "heading": 90, "label": "aggressor"}}]}
    s = load_scenario(write(data))
    assert s.vehicles[0].label == "aggressor"
    assert s.vehicles[0].heading == pytest.approx(math.pi / 2)
    assert (s.simulation.dt, s.simulation.seed) == (0.05, 0)


# 2. Relative paths
def test_loads_from_any_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_scenario(FEAR_AND_AGGRESSION).world.name == "One light"


# 3. Shared definitions
def test_vehicles_sharing_a_definition_are_independent(write):
    data = {"name": "Twins", "world": str(ONE_LIGHT), "vehicles": [
        {"vehicle": {"definition": str(VEHICLE2B), "position": [20, 20], "heading": 0}},
        {"vehicle": {"definition": str(VEHICLE2B), "position": [20, 80], "heading": 0}}]}
    sim = Simulation(load_scenario(write(data)))
    a, b = sim.vehicles
    assert a.definition is b.definition
    sim.run(100)
    before = (b.x, b.y, b.heading)
    a.x += 10
    a.heading += 1
    assert (b.x, b.y, b.heading) == before


# 4. Quick form
def test_quick_form_equals_scenario_file():
    quick = quick_scenario(HOT_SPOT, [VEHICLE1], ["20,20,0"])
    file = load_scenario(VEHICLE1_SCENARIO)
    assert quick.world == file.world
    assert quick.simulation == file.simulation
    [q], [f] = quick.vehicles, file.vehicles
    assert (q.definition, q.position, q.heading) == (f.definition, f.position, f.heading)


def test_quick_form_default_starts():
    s = quick_scenario(ONE_LIGHT, [VEHICLE2A, VEHICLE2B])
    assert [p.position for p in s.vehicles] == [
        pytest.approx((20, 100 / 3)), pytest.approx((20, 200 / 3))]
    assert [p.heading for p in s.vehicles] == [0, 0]


def test_quick_form_from_command_line():
    args = parse_args(["--world", str(ONE_LIGHT), "--vehicle", str(VEHICLE2A),
                       "--vehicle", str(VEHICLE2B), "--start", "10,20,90"])
    s = scenario_from_args(args)
    assert s.vehicles[0].position == (10, 20)
    assert s.vehicles[0].heading == pytest.approx(math.pi / 2)
    assert s.vehicles[1].position == pytest.approx((20, 200 / 3))


@pytest.mark.parametrize("argv", [
    [],
    ["--world", str(ONE_LIGHT)],
    [str(FEAR_AND_AGGRESSION), "--world", str(ONE_LIGHT)],
])
def test_command_line_needs_scenario_or_world_and_vehicle(argv):
    with pytest.raises(SystemExit):
        parse_args(argv)


# 5. Validation
def scenario_data(**vehicle):
    return {"name": "Test", "world": str(ONE_LIGHT),
            "vehicles": [{"vehicle": {"definition": str(VEHICLE2B), "position": [20, 20],
                                      "heading": 0, **vehicle}}]}


def test_missing_world_file(write):
    data = scenario_data()
    data["world"] = "nowhere.yaml"
    path = write(data)
    with pytest.raises(ConfigError, match=r"world: .*nowhere\.yaml: file not found") as e:
        load_scenario(path)
    assert str(path) in str(e.value)


def test_missing_definition_file(write):
    path = write(scenario_data(definition="nothing.yaml"))
    with pytest.raises(ConfigError, match=r"vehicles\[0\]\.vehicle\.definition: .*nothing\.yaml"):
        load_scenario(path)


def test_invalid_referenced_file_names_both_files(write):
    broken = read(VEHICLE2B)
    del broken["general"]["size"]
    broken_path = write(broken, "broken.yaml")
    path = write(scenario_data(definition=str(broken_path)))
    with pytest.raises(ConfigError) as e:
        load_scenario(path)
    message = str(e.value)
    for part in (str(path), "vehicles[0].vehicle.definition", str(broken_path), "general.size"):
        assert part in message


def test_position_outside_arena(write):
    path = write(scenario_data(position=[150, 20]))
    with pytest.raises(ConfigError, match=r"vehicles\[0\]\.vehicle\.position.*outside the arena"):
        load_scenario(path)


def test_sensor_not_in_world(write):
    data = scenario_data()
    data["world"] = str(HOT_SPOT)  # temperature only; vehicle 2b reads light
    path = write(data)
    with pytest.raises(ConfigError) as e:
        load_scenario(path)
    message = str(e.value)
    for part in (str(path), "vehicles[0].vehicle.definition", "left_eye", "light", str(HOT_SPOT)):
        assert part in message


@pytest.mark.parametrize("change, key", [
    (lambda d: d.pop("world"), "world"),
    (lambda d: d.update(colour="red"), "colour"),
    (lambda d: d["vehicles"].append({"definition": str(VEHICLE2B)}), "vehicles[1]"),
    (lambda d: d["vehicles"][0]["vehicle"].pop("heading"), "vehicles[0].vehicle.heading"),
    (lambda d: d.update(simulation={"seed": 1.5}), "simulation.seed"),
])
def test_validation_errors(write, change, key):
    data = scenario_data()
    change(data)
    path = write(data)
    with pytest.raises(ConfigError) as e:
        load_scenario(path)
    assert str(path) in str(e.value)
    assert key in str(e.value)


def test_quick_form_errors_name_the_option():
    with pytest.raises(ConfigError, match="--world"):
        quick_scenario("nowhere.yaml", [VEHICLE1])
    with pytest.raises(ConfigError, match="--vehicle"):
        quick_scenario(HOT_SPOT, [VEHICLE2B])  # reads light, world has temperature
    with pytest.raises(ConfigError, match="--start"):
        quick_scenario(HOT_SPOT, [VEHICLE1], ["20,20"])


# 6. Seed override
def test_seed_override():
    s = scenario_from_args(parse_args([str(FEAR_AND_AGGRESSION), "--seed", "7"]))
    assert s.simulation.seed == 7

    def final_poses():
        sim = Simulation(s)
        sim.run(500)
        return [(v.x, v.y, v.heading) for v in sim.vehicles]

    assert final_poses() == final_poses()


# 7. Headless
@pytest.mark.parametrize("argv", [
    [str(FEAR_AND_AGGRESSION)],
    ["--world", str(ONE_LIGHT), "--vehicle", str(VEHICLE2A)],
])
def test_headless_run_never_imports_pygame(argv):
    code = (
        "import sys\n"
        "from braitenberg.sim import main\n"
        f"main({argv + ['--headless', '--steps', '100']!r})\n"
        "assert 'pygame' not in sys.modules, 'pygame was imported'\n"
    )
    result = run_python(code)
    assert result.returncode == 0, result.stderr
    assert "100 steps" in result.stdout
