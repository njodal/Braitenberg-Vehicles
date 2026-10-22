"""Acceptance criteria of specs/vehicle-08.md: arrays of units, Braitenberg's circuits, the hunter."""

import copy
import math
import re
import time

import numpy as np
import pytest

from braitenberg.definition import load_definition
from braitenberg.diagram import definition_svg
from braitenberg.scenario import load_scenario, quick_scenario
from braitenberg.sim import Simulation
from braitenberg.vehicle import Vehicle
from braitenberg.yamlfile import ConfigError
from conftest import REPO, read, run_python

HUNTER = REPO / "vehicles" / "vehicle8-hunter.yaml"
PREY = REPO / "vehicles" / "vehicle8-prey.yaml"
STILL_LAMPS = REPO / "worlds" / "still-lamps.yaml"
HUNTER_SCENARIO = REPO / "scenarios" / "vehicle8-hunter.yaml"
MOVES = ("moves_left", "moves_ahead", "moves_right")   # movement seen, by region


def hunter_scenario(seed=0, hunter=None, prey=None):
    scenario = load_scenario(HUNTER_SCENARIO)
    scenario.simulation.seed = seed
    if hunter is not None:
        scenario.vehicles[0].definition = hunter
    if prey is not None:
        scenario.vehicles[1].definition = prey
    return scenario


def distance(sim, a, b):
    return math.hypot(*sim.world.arena.delta(b.x - a.x, b.y - a.y))


def watcher(write):
    """The hunter with its motors disconnected: it never moves."""
    d = read(HUNTER)
    for a in d["actuators"]:
        a["actuator"]["inputs"] = []
    return write(d, "watcher.yaml")


def lit(v, array, n):
    return [j for j in range(n) if v.unit_outputs[f"{array}[{j}]"]]


def mini(write, units, columns, rows=1):
    """A vehicle whose camera's pixels are set by hand, with `units`."""
    d = {"general": {"type": "8", "name": "Bench", "size": 4},
         "sensors": [{"sensor": {"name": "retina", "type": "light", "position": [0, 0.9],
                                 "field_of_view": 180, "response": {"type": "step", "at": 0.5},
                                 "camera": {"columns": columns, "rows": rows,
                                            "vertical_field_of_view": 10}}}],
         "actuators": [{"actuator": {"name": "motor", "type": "motor", "position": [0, -0.5],
                                     "inputs": []}}],
         "units": [{"unit": {"type": "threshold", **u}} for u in units]}
    return Vehicle(load_definition(write(d, "bench.yaml")), 0, 0, 0, dt=0.01)


def array(name, n, threshold, *inputs, delay=None):
    unit = {"name": name, "threshold": threshold, "array": n,
            "inputs": [{"input": {"from": f} if isinstance(f, str) else
                        {"from": f[0], "type": "inhibitory"}} for f in inputs]}
    if delay:
        unit["delay"] = delay
    return unit


# 1. Arrays
def test_arrays_expand_into_elements():
    d = load_definition(HUNTER)
    assert d.arrays == {"object": (3, 23), "lump": (23,), "front": (23,), "slow": (23,),
                        "right": (22,), "left": (22,)}
    names = [u.name for u in d.units]
    assert [n for n in names if n.startswith("lump[")] == [f"lump[{i}]" for i in range(23)]
    assert names.count("object[0, 0]") == 1 and "object[2, 22]" in names
    units = {u.name: u for u in d.units}
    assert [c.source for c in units["object[1, 4]"].inputs] == [
        "retina[1, 4]", "retina[1, 5]", "retina[2, 4]", "retina[2, 5]"]
    assert [c.source for c in units["lump[3]"].inputs] == ["object[0, 3]", "object[1, 3]",
                                                           "object[2, 3]"]
    # lump[i-1] falls outside for front[0], and only there.
    assert [c.source for c in units["front[0]"].inputs] == ["lump[0]", "acting"]
    assert [c.source for c in units["front[5]"].inputs] == ["lump[5]", "lump[4]", "acting"]
    assert units["slow[7]"].delay == 0.3 and units["slow[7]"].threshold == 1


def written_out(write):
    """The hunter with every element of its arrays written out by hand, as front_3 etc."""
    d = load_definition(HUNTER)
    rename = lambda name: re.sub(r"\[(\d+)(?:, (\d+))?\]",
                                lambda m: "_" + "_".join(g for g in m.groups() if g), name)
    source = lambda name: name if name.startswith("retina") else rename(name)
    data = read(HUNTER)
    data["units"] = [{"unit": {"name": rename(u.name), "type": u.type, "threshold": u.threshold,
                               "delay": u.delay, **({"rate": u.rate} if u.type == "random" else {}),
                               "inputs": [{"input": {"from": source(c.source),
                                                     "type": "excitatory" if c.sign > 0
                                                     else "inhibitory"}} for c in u.inputs]}}
                     for u in d.units]
    return load_definition(write(data, "by-hand.yaml"))


def test_arrays_are_a_shorthand(write):
    runs = []
    for hunter in (load_definition(HUNTER), written_out(write)):
        sim = Simulation(hunter_scenario(0, hunter))
        sim.run(1500)
        runs.append([(v.x, v.y, v.heading) for v in sim.vehicles])
    assert runs[0] == runs[1]


# 2. Validation
def unit_with(**changes):
    def change(d):
        d["units"][0]["unit"].update(changes)
    return change


def first_input(source):
    def change(d):
        d["units"][1]["unit"]["inputs"][0]["input"]["from"] = source
    return change


def actuator_input(source):
    def change(d):
        d["actuators"][0]["actuator"]["inputs"][0]["input"]["from"] = source
    return change


ERRORS = [
    (unit_with(array=0), "units[0].unit.array"),
    (unit_with(array=[3, 0]), "units[0].unit.array"),
    (unit_with(array=[1, 2, 3]), "units[0].unit.array"),
    (unit_with(array="many"), "units[0].unit.array"),
    (actuator_input("lump[i]"), "inputs[0].input.from"),            # i outside an array
    (first_input("object[j, i]"), "units[1].unit.inputs[0].input.from"),  # j in a 1-D array
    (first_input("object[:, 2*i]"), "units[1].unit.inputs[0].input.from"),
    (first_input("object[i]"), "units[1].unit.inputs[0].input.from"),     # wrong number
    (first_input("object"), "units[1].unit.inputs[0].input.from"),        # no index
    (first_input("object[:, 30]"), "units[1].unit.inputs[0].input.from"),
    (first_input("object[0:5, i]"), "units[1].unit.inputs[0].input.from"),
]


@pytest.mark.parametrize("change, key", ERRORS)
def test_validation(write, change, key):
    d = read(HUNTER)
    change(d)
    with pytest.raises(ConfigError) as e:
        load_definition(write(d))
    assert key in str(e.value) and "file.yaml" in str(e.value)


# 3. Object detectors, with the image of the object detector figure
FIGURE_IMAGE = np.zeros((4, 24))
FIGURE_IMAGE[0:4, 2:6] = 10
for r, c in [(0, 8), (2, 9), (3, 11), (1, 7), (3, 0)]:
    FIGURE_IMAGE[r, c] = 10


def test_object_detectors(write):
    v = Vehicle(load_definition(watcher(write)), 0, 0, 0, dt=0.01)
    for _ in range(20):
        v.think({"retina": FIGURE_IMAGE})
    objects = {(r, c) for r in range(3) for c in range(23) if v.unit_outputs[f"object[{r}, {c}]"]}
    assert objects == {(r, c) for r in range(3) for c in (2, 3, 4)}
    assert lit(v, "lump", 23) == [2, 3, 4]


# 4. Lateral inhibition, with the row of the lateral inhibition figure
def test_lateral_inhibition(write):
    row = np.array([[1, 1, 0, 0, 1, 1, 1, 1, 1, 0, 0, 1, 0, 0, 0]], dtype=float)
    v = mini(write, [array("spot", 15, 1, "retina[0, i]", ("retina[0, i-1]",), ("retina[0, i+1]",)),
                     array("front", 15, 1, "retina[0, i]", ("retina[0, i-1]",))], 15)
    for _ in range(10):
        v.think({"retina": row})
    assert lit(v, "spot", 15) == [11]
    assert lit(v, "front", 15) == [0, 4, 11]


# 5. Direction
def detectors(write, columns=2):
    """Movement detectors fed by the pixels, standing in for front."""
    return mini(write, [array("slow", columns, 1, "retina[0, i]", delay=0.3),
                        array("right", columns - 1, 2, "slow[i]", "retina[0, i+1]"),
                        array("left", columns - 1, 2, "slow[i+1]", "retina[0, i]")], columns)


def passing(v, order, T):
    """A point in the first column of `order` for T seconds, then in the second; what fires."""
    fired = set()
    steps = round(T / v.dt)
    for k in range(50 + 2 * steps + 150):
        image = np.zeros((1, 2))
        if 50 <= k < 50 + steps:
            image[0, order[0]] = 1
        elif 50 + steps <= k < 50 + 2 * steps:
            image[0, order[1]] = 1
        v.think({"retina": image})
        fired |= {name for name in ("right[0]", "left[0]") if v.unit_outputs[name]}
    return fired


@pytest.mark.parametrize("T", [0.2, 0.3, 0.5, 1, 2, 5])
def test_detects_movement_in_its_direction(write, T):
    assert passing(detectors(write), (0, 1), T) == {"right[0]"}
    assert passing(detectors(write), (1, 0), T) == {"left[0]"}


@pytest.mark.parametrize("T", [0.05, 0.1])
def test_too_fast_is_not_seen(write, T):
    assert passing(detectors(write), (0, 1), T) == set()


# 6. Why movement detectors need points
def test_movement_detectors_need_points(write):
    v = mini(write, [array("slow_raw", 3, 1, "retina[0, i]", delay=0.3),
                     array("right_raw", 2, 2, "slow_raw[i]", "retina[0, i+1]"),
                     array("left_raw", 2, 2, "slow_raw[i+1]", "retina[0, i]"),
                     array("front", 3, 1, "retina[0, i]", ("retina[0, i-1]",)),
                     array("slow", 3, 1, "front[i]", delay=0.3),
                     array("right", 2, 2, "slow[i]", "front[i+1]"),
                     array("left", 2, 2, "slow[i+1]", "front[i]")], 3)
    fired = set()
    for _ in range(200):
        v.think({"retina": np.array([[1.0, 1.0, 0.0]])})   # a still thing two columns wide
        fired |= {n for n in ("right_raw[0]", "left_raw[0]", "right[0]", "left[0]")
                  if v.unit_outputs[n]}
    assert fired == {"right_raw[0]", "left_raw[0]"}


# 7. Things crossing the watcher's view
def crossing(write, direction, prey_size=3, seconds=16, world=STILL_LAMPS):
    """A prey crossing 12 units ahead of the watcher at speed 3; when each detector first fires."""
    prey = read(PREY)
    prey["general"].update(noise_std=0, size=prey_size)
    for a in prey["actuators"]:
        a["actuator"]["base_speed"] = 3
    start = "26,52,0" if direction == "right" else "74,52,180"
    sim = Simulation(quick_scenario(world, [watcher(write), write(prey, "prey.yaml")],
                                    ["50,40,90", start]))
    first = {}
    objects = 0
    while sim.time < seconds:
        sim.step()
        v = sim.vehicles[0]
        objects += sum(v.unit_outputs[f"lump[{j}]"] for j in range(23))
        for name in ("right", "left"):
            for j in lit(v, name, 22):
                first.setdefault((name, j), sim.time)
    return first, objects


@pytest.mark.parametrize("direction, other", [("right", "left"), ("left", "right")])
def test_thing_crossing(write, direction, other):
    first, _ = crossing(write, direction)
    assert not any(name == other for name, _ in first)
    times = [t for (name, j), t in sorted(first.items(), key=lambda item: item[0][1])]
    assert len(times) >= 8
    order = times if direction == "right" else times[::-1]
    assert order == sorted(order)             # column after column, in the direction it moves


def test_small_thing_is_ignored(write):
    first, objects = crossing(write, "right", prey_size=0.4)
    assert objects == 0 and first == {}


def test_lamp_switching_on_is_not_movement(write):
    w = read(STILL_LAMPS)
    w["stimuli"]["light"]["sources"].append({"position": [50, 52], "intensity": 10, "falloff": 15,
                                             "radius": 1.5, "height": 3,
                                             "schedule": {"period": 10, "on_at": 3, "off_at": 8}})
    sim = Simulation(quick_scenario(write(w, "world.yaml"), [watcher(write)], ["50,40,90"]))
    seen = 0
    while sim.time < 20:
        sim.step()
        v = sim.vehicles[0]
        seen += sum(v.unit_outputs[f"lump[{j}]"] for j in range(23))
        assert not lit(v, "right", 22) and not lit(v, "left", 22)
    assert seen > 0


def test_nothing_fires_in_a_still_world(write):
    sim = Simulation(quick_scenario(STILL_LAMPS, [watcher(write)], ["40,30,60"]))
    while sim.time < 20:
        sim.step()
        v = sim.vehicles[0]
        assert not lit(v, "right", 22) and not lit(v, "left", 22)


# 8. Still world
@pytest.mark.parametrize("seed", range(5))
def test_hunter_wanders_when_nothing_moves(seed):
    prey = copy.deepcopy(load_definition(PREY))
    prey.general.noise_std = 0
    for a in prey.actuators:
        a.base_speed = 0
    sim = Simulation(hunter_scenario(seed, prey=prey))
    hunter = sim.vehicles[0]
    path, headings, seen = 0.0, set(), 0
    while sim.time < 60:
        x, y = hunter.x, hunter.y
        sim.step()
        path += math.hypot(hunter.x - x, hunter.y - y)
        headings.add(round(math.degrees(hunter.heading) / 10))
        seen += any(hunter.unit_outputs[k] for k in MOVES)
    assert seen == 0                      # it never mistakes its own movement for the world's
    assert 5 < path < 30                  # slowly: less than half a unit per second
    assert len(headings) > 6              # in changing directions


# 9. Hunts
@pytest.mark.parametrize("seed", range(5))
def test_hunts(seed):
    sim = Simulation(hunter_scenario(seed))
    hunter, prey = sim.vehicles
    while sim.time < 120:
        sim.step()
        if distance(sim, hunter, prey) < 8:
            return
    pytest.fail("never came within 8 units of the prey")


# 10. Holding still to look
def prey_out_of_view(sim, hunter, prey):
    """Whether the prey is out of range, or wholly behind the hunter's camera."""
    arena = sim.world.arena
    if math.hypot(*arena.delta(prey.x - hunter.x, prey.y - hunter.y)) > 30:
        return True
    _, cx, cy = hunter.cameras()[0]
    ahead = math.cos(hunter.heading), math.sin(hunter.heading)
    corners = [prey.body_to_world(bx, by) for bx in (-1, 1) for by in (-1, 1)]
    return all(dx * ahead[0] + dy * ahead[1] < 0
               for dx, dy in (arena.delta(x - cx, y - cy) for x, y in corners))


def out_of_view_reactions(hunter_definition, seed):
    """Seconds, in 60 s, in which the hunter sees movement while its prey has been out of view
    for more than 0.3 s, the time a signal takes from the retina to `moves_left` and the like."""
    sim = Simulation(hunter_scenario(seed, hunter_definition))
    hunter, prey = sim.vehicles
    total, out_since = 0.0, None
    while sim.time < 60:
        sim.step()
        out = prey_out_of_view(sim, hunter, prey)
        out_since = (out_since if out_since is not None else sim.time) if out else None
        if any(hunter.unit_outputs[k] for k in MOVES) and out and sim.time - out_since > 0.3:
            total += sim.dt
    return total


def test_holding_still_to_look():
    hunter = load_definition(HUNTER)
    seeing = copy.deepcopy(hunter)
    for u in seeing.units:
        if u.array == "front":
            u.inputs = [c for c in u.inputs if c.source != "acting"]
    assert sum(out_of_view_reactions(hunter, seed) for seed in range(5)) == 0
    assert sum(out_of_view_reactions(seeing, seed) for seed in range(5)) >= 4


# 11. Diagram
def test_diagram():
    v = Vehicle(load_definition(HUNTER), 0, 0, 0, dt=0.01)
    v.think({"retina": FIGURE_IMAGE})
    d = v.diagram()
    parts = {p.name: p for p in d.parts}
    assert parts["front"].kind == "array" and parts["front"].shape == (23,)
    assert len(parts["front"].value) == 23 and len(parts["object"].level) == 3
    assert all(0 <= level <= 1 for level in parts["right"].level)
    wire = next(w for w in d.wires if w.target == "front" and w.label == "lump[i-1]")
    assert wire.source == "lump" and wire.sign == -1
    assert wire.source_index == (wire.target_index[0] - 1,)
    svg = definition_svg(load_definition(HUNTER))
    for label in ("lump[i-1]", "object[:, i]", "slow[i+1]",
                  "retina[i, j], retina[i, j+1], retina[i+1, j], retina[i+1, j+1]"):
        assert svg.count(f">{label}<") == 1                # one arrow for the whole array


def test_diagram_never_imports_pygame():
    result = run_python(f"""
import sys
from braitenberg.definition import load_definition
from braitenberg.diagram import definition_svg
from braitenberg.vehicle import Vehicle
Vehicle(load_definition({str(HUNTER)!r}), 0, 0, 0).diagram()
definition_svg(load_definition({str(HUNTER)!r}))
print("pygame" in sys.modules)
""")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"


def test_renderer_draws_the_hunter():
    result = run_python(f"""
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
from braitenberg.render import Renderer
from braitenberg.scenario import load_scenario
pygame.init()
renderer = Renderer(load_scenario({str(HUNTER_SCENARIO)!r}))
renderer.show_views = True
renderer.advance(300)
surface = pygame.Surface(renderer.window_size)
renderer.draw(surface)
print(renderer.window_size)
""")
    assert result.returncode == 0, result.stderr


# 12. Headless and fast
def test_fast():
    sim = Simulation(hunter_scenario(0))
    start = time.perf_counter()
    sim.run(round(60 / sim.dt))
    assert time.perf_counter() - start < 15
