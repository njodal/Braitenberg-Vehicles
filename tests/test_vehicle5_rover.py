"""Acceptance criteria of specs/vehicle-05-rover.md."""

import copy
import itertools
import math

import pytest

from braitenberg.definition import load_definition
from braitenberg.scenario import load_scenario, quick_scenario
from braitenberg.sim import Simulation
from braitenberg.vehicle import Vehicle
from braitenberg.world import to_surface
from conftest import REPO

ROVER = REPO / "vehicles" / "vehicle5-rover.yaml"
ROOM = REPO / "worlds" / "room.yaml"
ROVER_SCENARIO = REPO / "scenarios" / "vehicle5-rover.yaml"
SENSORS = ("ir_left_front", "ir_front_left", "ir_front_right", "ir_right_front")


def corners(v):
    c, s = math.cos(v.heading), math.sin(v.heading)
    return [(v.x + a * c + b * s, v.y + a * s - b * c)
            for a, b in ((v.half_length, v.half_width), (v.half_length, -v.half_width),
                         (-v.half_length, -v.half_width), (-v.half_length, v.half_width))]


def collide(a, b) -> bool:
    """Whether two bodies overlap: no side of either separates them."""
    ca, cb = corners(a), corners(b)
    for poly in (ca, cb):
        for i in range(4):
            (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % 4]
            nx, ny = y1 - y0, x0 - x1
            pa = [nx * x + ny * y for x, y in ca]
            pb = [nx * x + ny * y for x, y in cb]
            if max(pa) < min(pb) or max(pb) < min(pa):
                return False
    return True


def watch(sim, seconds):
    """Run, counting touches (an obstacle pushing a rover back) and collisions between rovers."""
    touches = collisions = 0
    block = sim.world.block

    def counted(v):
        nonlocal touches
        touched = block(v)
        touches += touched
        return touched

    sim.world.block = counted
    visited = set()
    while sim.time < seconds:
        sim.step()
        for v in sim.vehicles:
            visited.add((int(v.x // 5), int(v.y // 5)))
        collisions += sum(collide(a, b) for a, b in itertools.combinations(sim.vehicles, 2)
                          if math.hypot(a.x - b.x, a.y - b.y) < 6)
    return touches, collisions, visited


def scenario(seed):
    s = load_scenario(ROVER_SCENARIO)
    s.simulation.seed = seed
    return s


# 1. Touches nothing, and 3. Explores
@pytest.mark.parametrize("seed", range(5))
def test_explores_without_touching_anything(seed):
    sim = Simulation(scenario(seed))
    touches, collisions, visited = watch(sim, 120)
    assert touches == 0 and collisions == 0
    free = [(i, j) for i in range(20) for j in range(20)
            if min(to_surface(5 * i + 2.5 - o.position[0], 5 * j + 2.5 - o.position[1],
                              o.width / 2, o.length / 2, o.heading)[2]
                   for o in sim.world.obstacles) > 2]
    assert len(visited & set(free)) >= 0.4 * len(free)


# 2. Nor in a crowd
def crowd(seed):
    corners_ = ["15,15,45", "85,85,225", "15,85,-45", "85,15,135"]
    s = quick_scenario(ROOM, [ROVER] * 4, corners_)
    s.simulation.dt, s.simulation.seed = 0.01, seed
    return Simulation(s)


def test_crowd():
    touches, collisions, _ = watch(crowd(0), 120)
    assert touches == 0 and collisions == 0


@pytest.mark.slow
@pytest.mark.parametrize("seed", range(1, 10))
def test_crowd_more_seeds(seed):
    touches, collisions, _ = watch(crowd(seed), 120)
    assert touches == 0 and collisions == 0


# 4. Hard cases
@pytest.mark.parametrize("starts", [
    ["50,85,90"],                      # straight at the top wall
    ["85,85,45"],                      # into the top right corner
    ["10,90,0", "40,90,180"],          # two rovers straight at each other
    ["40,60,0", "62,60,180"],          # the same, either side of the middle wall
])
def test_hard_cases(starts):
    s = quick_scenario(ROOM, [ROVER] * len(starts), starts)
    s.simulation.dt = 0.01
    rover = copy.deepcopy(s.vehicles[0].definition)
    rover.general.noise_std = 0
    for p in s.vehicles:
        p.definition = rover
    sim = Simulation(s)
    touches, collisions, _ = watch(sim, 15)
    assert touches == 0 and collisions == 0
    assert any(v.unit_outputs for v in sim.vehicles)


# 5. Deciding
def rover():
    return Vehicle(load_definition(ROVER), 0, 0, 0, dt=0.01)


def feel(v, left, right, steps=20):
    """Hold the readings: `left` on each left sensor and `right` on each right one."""
    for _ in range(steps):
        v.think(dict(zip(SENSORS, (left, left, right, right))))
    return v.unit_outputs


def test_near():
    assert feel(rover(), 0.375, 0.375)["near"] == 1        # 1.5 together
    assert feel(rover(), 0.37, 0.37)["near"] == 0


def test_turns_away_and_keeps_to_its_decision():
    v = rover()
    out = feel(v, 0.5, 1.0)                                 # closer on the right
    assert out["turn_left"] == 1 and out["turn_right"] == 0
    out = feel(v, 1.0, 0.5)                                 # now closer on the left, still near
    assert out["turn_left"] == 1 and out["turn_right"] == 0
    out = feel(v, 0, 0, steps=30)                           # clear: within 0.3 s
    assert out["turn_left"] == 0 and out["turn_right"] == 0
    out = feel(v, 1.0, 0.5)                                 # decided afresh
    assert out["turn_right"] == 1 and out["turn_left"] == 0


def test_straight_ahead_turns_left():
    out = feel(rover(), 1.0, 1.0)
    assert out["tie"] == 1 and out["turn_left"] == 1 and out["turn_right"] == 0


# 6. Wanders only when clear
def test_wander_is_enabled_only_when_clear():
    d = load_definition(ROVER)
    enabled_by = {c.source for u in d.units if u.name.startswith("wander.") for c in u.inputs
                  if not c.source.startswith("wander.")}
    assert enabled_by == {"clear"}
    v = rover()
    assert feel(v, 0, 0)["clear"] == 1
    assert feel(v, 1, 1)["clear"] == 0
