"""Acceptance criteria of specs/vehicle-09.md: mirror images, the symmetry detector, the shy vehicle."""

import copy
import math
import time

import pytest

from braitenberg.definition import load_definition
from braitenberg.diagram import definition_svg
from braitenberg.scenario import load_scenario, quick_scenario
from braitenberg.sim import Simulation
from braitenberg.vehicle import Vehicle
from braitenberg.yamlfile import ConfigError
from conftest import REPO, read, run_python

SHY = REPO / "vehicles" / "vehicle9-shy.yaml"
WALKER = REPO / "vehicles" / "vehicle9-walker.yaml"
OPEN_FIELD = REPO / "worlds" / "open-field.yaml"
SHY_SCENARIO = REPO / "scenarios" / "vehicle9-shy.yaml"
SHY_AT = (50, 30, 90)


@pytest.fixture
def still_walker(write):
    """A walker that does not move."""
    d = read(WALKER)
    d["general"]["noise_std"] = 0
    for a in d["actuators"]:
        a["actuator"]["base_speed"] = 0
    return write(d, "still-walker.yaml")


@pytest.fixture
def watcher(write):
    """The shy vehicle with its motors disconnected: it never moves."""
    d = read(SHY)
    for a in d["actuators"]:
        a["actuator"]["inputs"] = []
    return write(d, "watcher.yaml")


def ahead(distance, azimuth=0.0):
    """A point `distance` away from the shy vehicle, `azimuth` degrees to the left of its heading."""
    a = math.radians(SHY_AT[2] + azimuth)
    return SHY_AT[0] + distance * math.cos(a), SHY_AT[1] + distance * math.sin(a)


def facing(azimuth=0.0, turned=0.0):
    """The heading, in degrees, of a vehicle at `azimuth` that faces the shy vehicle, turned by
    `turned` degrees."""
    return SHY_AT[2] + azimuth + 180 + turned


def simulation(shy, *others):
    """A simulation in the open field: `shy` at SHY_AT, and others as (path, x, y, heading)."""
    paths = [str(shy)] + [str(p) for p, *_ in others]
    starts = [",".join(map(str, SHY_AT))] + [f"{x},{y},{h}" for _, x, y, h in others]
    return Simulation(quick_scenario(str(OPEN_FIELD), paths, starts))


def symmetric(watcher, *others, steps=20):
    sim = simulation(watcher, *others)
    sim.run(steps)
    return bool(sim.vehicles[0].unit_outputs["symmetric"])


# 1. Mirror images
def mirror_vehicle(source, array=(4,)):
    return {
        "general": {"type": "9", "name": "Mirror", "size": 4},
        "sensors": [{"sensor": {"name": "eye", "type": "light", "position": [0, 0.8],
                                "field_of_view": 60,
                                "camera": {"columns": 6, "rows": 1, "vertical_field_of_view": 8}}}],
        "actuators": [{"actuator": {"name": "motor", "type": "motor", "position": [0, -0.8],
                                    "inputs": []}}],
        "units": [{"unit": {"name": "m", "type": "threshold", "threshold": 1,
                            "array": list(array) if len(array) > 1 else array[0],
                            "inputs": [{"input": {"from": source}}]}}],
    }


def test_mirror_images(write):
    d = load_definition(write(mirror_vehicle("eye[0, 5-i]")))
    assert [[c.source for c in u.inputs] for u in d.units] == [
        ["eye[0, 5]"], ["eye[0, 4]"], ["eye[0, 3]"], ["eye[0, 2]"]]
    # Outside the camera: left out for that element only.
    d = load_definition(write(mirror_vehicle("eye[0, 2-i]")))
    assert [[c.source for c in u.inputs] for u in d.units] == [
        ["eye[0, 2]"], ["eye[0, 1]"], ["eye[0, 0]"], []]


@pytest.mark.parametrize("change", [
    lambda d: d["units"][0]["unit"].pop("array"),          # k - i outside an array
    lambda d: d["units"][0]["unit"]["inputs"][0]["input"].update({"from": "eye[0, 5-j]"}),
])
def test_mirror_validation(write, change):
    d = mirror_vehicle("eye[0, 5-i]")
    change(d)
    with pytest.raises(ConfigError, match=r"units\[0\]\.unit\.inputs\[0\]\.input\.from"):
        load_definition(write(d))


# 2. Symmetry
@pytest.mark.parametrize("distance", [10, 15, 20])
@pytest.mark.parametrize("turned, seen", [
    (0, True), (5, True), (-5, True),
    (180, False), (90, False), (-90, False),
    (45, False), (-45, False), (60, False), (-60, False),
])
def test_symmetry(watcher, still_walker, distance, turned, seen):
    walker = (still_walker, *ahead(distance), facing(turned=turned))
    assert symmetric(watcher, walker) == seen


# 3. The middle only
def test_only_the_middle_counts(watcher, still_walker):
    walker = (still_walker, *ahead(15), facing())
    aside = (still_walker, *ahead(15, 25), facing(25, 90))
    assert symmetric(watcher, walker, aside)


# 4. Watching
def bearing(sim, shy, other):
    dx, dy = sim.world.arena.delta(other.x - shy.x, other.y - shy.y)
    return math.degrees((math.atan2(dy, dx) - shy.heading + math.pi) % (2 * math.pi) - math.pi)


def test_watching(still_walker):
    sim = simulation(SHY, (still_walker, *ahead(15, 20), facing(20, 90)))
    shy, walker = sim.vehicles
    sim.run(100)
    bearings = []
    for _ in range(300):
        sim.step()
        bearings.append(bearing(sim, shy, walker))
        assert not shy.unit_outputs["fleeing"]
    assert max(abs(b) for b in bearings) < 10


# 5. Fleeing
def test_fleeing(still_walker):
    sim = simulation(SHY, (still_walker, *ahead(15), facing()))
    shy, walker = sim.vehicles
    heading = shy.heading
    start = None
    while sim.time < 6:
        sim.step()
        if start is None and shy.unit_outputs["turn_away"]:
            start, at_start = sim.time, math.hypot(walker.x - shy.x, walker.y - shy.y)
        if start is not None and sim.time - start == pytest.approx(1.5, abs=0.005):
            turned = abs(math.degrees(shy.heading - heading))
            assert 150 <= turned <= 190
        if start is not None and sim.time - start == pytest.approx(3.2, abs=0.005):
            gained = math.hypot(walker.x - shy.x, walker.y - shy.y) - at_start
            assert 8 <= gained <= 15
        if start is not None and sim.time - start == pytest.approx(4.5, abs=0.005):
            off = (math.degrees(shy.heading - heading) + 180) % 360 - 180
            assert abs(off) <= 30
            return
    pytest.fail("never fled")


# 6. The scenario
def flights_and_closeness(seed, flee=True):
    scenario = load_scenario(SHY_SCENARIO)
    scenario.simulation.seed = seed
    if not flee:
        d = copy.deepcopy(scenario.vehicles[0].definition)
        for u in d.units:
            if u.name == "turn_away":
                u.inputs = [c for c in u.inputs if c.source != "symmetric"]
        scenario.vehicles[0].definition = d
    sim = Simulation(scenario)
    shy, chaser = sim.vehicles[:2]
    flights = right = touches = 0
    close = 0.0
    was = touching = 0
    while sim.time < 60:
        sim.step()
        if shy.unit_outputs["turn_away"] and not was:
            flights += 1
            for other in sim.vehicles[1:]:
                dx, dy = sim.world.arena.delta(shy.x - other.x, shy.y - other.y)
                off = abs((math.atan2(dy, dx) - other.heading + math.pi) % (2 * math.pi) - math.pi)
                if math.degrees(off) < 25 and math.hypot(dx, dy) < 32:
                    right += 1
                    break
        was = shy.unit_outputs["turn_away"]
        distance = math.hypot(*sim.world.arena.delta(chaser.x - shy.x, chaser.y - shy.y))
        touches += distance < 4.5 and not touching
        touching = distance < 4.5
        close += sim.dt if distance < 6 else 0
    return flights, right, touches, close


@pytest.mark.slow
def test_the_scenario():
    flights = right = touches = close = brave_touches = brave_close = 0
    for seed in range(10):
        f, r, t, c = flights_and_closeness(seed)
        flights, right, touches, close = flights + f, right + r, touches + t, close + c
        _, _, t, c = flights_and_closeness(seed, flee=False)
        brave_touches, brave_close = brave_touches + t, brave_close + c
    assert flights and right / flights >= 0.9
    assert touches < brave_touches / 2 and close < brave_close / 2


# 7. Diagram
def test_diagram():
    v = Vehicle(load_definition(SHY), 0, 0, 0, dt=0.01)
    parts = {p.name: p for p in v.diagram().parts}
    assert parts["odd_left"].shape == (4, 4) and parts["odd_right"].shape == (4, 4)
    svg = definition_svg(load_definition(SHY))
    assert ">retina[i, j+8]<" in svg and ">retina[i, 15-j]<" in svg


# 8. Headless and fast
def test_headless():
    result = run_python(f"""
import sys
from braitenberg.scenario import load_scenario
from braitenberg.sim import Simulation
Simulation(load_scenario({str(SHY_SCENARIO)!r})).run(10)
assert "pygame" not in sys.modules
print("ok")
""")
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_fast():
    sim = Simulation(load_scenario(SHY_SCENARIO))
    start = time.perf_counter()
    sim.run(6000)
    assert time.perf_counter() - start < 10
