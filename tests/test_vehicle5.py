"""Acceptance criteria of specs/vehicle-05.md."""

import math
from functools import lru_cache

import pytest

from braitenberg.definition import load_definition
from braitenberg.scenario import load_scenario, quick_scenario
from braitenberg.sim import Simulation
from braitenberg.vehicle import Vehicle
from conftest import MOTH, ONE_LIGHT, VEHICLE5

DT = 0.01
STEPS = 20_000          # 200 simulated seconds
DELAY = 5               # 0.05 s units at dt 0.01


@lru_cache(maxsize=None)
def run(seed):
    """Run the default scenario; return per-step (distance to the nearest light, unit outputs)."""
    scenario = load_scenario(MOTH)
    scenario.simulation.seed = seed
    sim = Simulation(scenario)
    moth = sim.vehicles[0]
    lights = [s.position for s in sim.world.stimuli["light"].sources]
    track = []
    for _ in range(STEPS):
        sim.step()
        distance = min(math.hypot(*sim.world.arena.delta(moth.x - lx, moth.y - ly))
                       for lx, ly in lights)
        track.append((distance, dict(moth.unit_outputs)))
    return track


def burn_step(track):
    return next(i for i, (_, units) in enumerate(track) if units["burned"])


# 1. Drawn to light
@pytest.mark.parametrize("seed", range(5))
def test_gets_burned_early(seed):
    track = run(seed)
    assert burn_step(track) * DT <= 75


# 2. Remembers
@pytest.mark.parametrize("seed", range(5))
def test_burn_is_remembered(seed):
    track = run(seed)
    after = track[burn_step(track):]
    assert all(units["burned"] for _, units in after)
    # It stays on also while far from every light, with no pain.
    assert any(not units["pain"] and distance > 20 for distance, units in after)


# 3. Avoids light after
@pytest.mark.parametrize("seed", range(5))
def test_avoids_light_after_the_burn(seed):
    track = run(seed)
    burned = burn_step(track)
    assert min(d for d, _ in track[:burned]) < 10
    later = [d for d, _ in track[burned + round(10 / DT):]]
    assert min(later) >= 15
    assert min(later) < 25      # it keeps its distance, but does come back near a light


# 4. Logic
def moth():
    return Vehicle(load_definition(VEHICLE5), 50, 50, 0, dt=DT)


def settle(v, left, right, steps=5 * DELAY):
    """Hold the readings until every unit has settled (chains of delays and windows included)."""
    for _ in range(steps):
        v.think({"left_eye": left, "right_eye": right})
    return v.unit_outputs


def burn(v):
    settle(v, 10, 10)                       # both eyes 10: sum 20 reaches pain's 18
    assert v.unit_outputs["burned"] == 1
    return v


@pytest.mark.parametrize("left, right, expected", [
    (3.0, 3.0, (0, 0)), (3.04, 3.0, (0, 0)), (3.051, 3.0, (1, 0)), (3.0, 3.06, (0, 1)),
    (6.0, 2.0, (1, 0)),
])
def test_which_eye_is_brighter(left, right, expected):
    out = settle(moth(), left, right)
    assert (out["left_brighter"], out["right_brighter"]) == expected


@pytest.mark.parametrize("left, right, near", [(2.5, 2.5, 0), (4.99, 4.99, 0), (5.0, 5.0, 1), (8, 3, 1)])
def test_near(left, right, near):
    assert settle(moth(), left, right)["near"] == near


@pytest.mark.parametrize("burned", [False, True])
@pytest.mark.parametrize("left, right", [(4.0, 3.0), (3.0, 4.0), (3.0, 3.0),     # far: sum below 10
                                         (6.0, 5.0), (5.0, 6.0), (5.5, 5.5)])    # near
def test_seek_and_flee(burned, left, right):
    v = burn(moth()) if burned else moth()
    out = settle(v, left, right)
    lb, rb, near = out["left_brighter"], out["right_brighter"], out["near"]
    assert near == (left + right >= 10)
    assert out["seek_left"] == (lb and not burned)
    assert out["seek_right"] == (rb and not burned)
    assert out["flee_left"] == (lb and burned and near)
    assert out["flee_right"] == (rb and burned and near)


def test_burned_waits_for_pain_then_stays():
    v = moth()
    for left, right in [(1, 1), (5, 5), (8.9, 8.9)]:       # sums below 18
        assert settle(v, left, right)["burned"] == 0
    burn(v)
    for left, right in [(0, 0), (1, 1), (3, 0)]:
        assert settle(v, left, right, steps=100)["burned"] == 1


# 5. Simultaneity
@pytest.mark.parametrize("gap, fires", [(0, True), (1, True), (4, True), (5, False), (7, False)])
def test_pain_adds_eye_signals_less_than_a_delay_apart(gap, fires):
    v = moth()
    pain = []
    for step in range(30):
        # Each eye alone reads 10, below pain's 18; together, 20.
        v.think({"left_eye": 10.0 if step == 0 else 0.0, "right_eye": 10.0 if step == gap else 0.0})
        pain.append(v.unit_outputs["pain"])
    assert any(pain) == fires


# 6. Delays
def first(values, condition):
    return next(i for i, v in enumerate(values) if condition(v))


def test_burn_reaches_the_motors_three_delays_later():
    v = moth()
    settle(v, 1.0, 1.0)
    history = []
    for _ in range(40):
        # Very close to a light on the left: pain and left_brighter.
        v.think({"left_eye": 10.2, "right_eye": 10.0})
        history.append((dict(v.unit_outputs), dict(v.motor_speeds)))
    # A change at step 0 shows after one delay (step 5), two (10) and three (15).
    assert first(history, lambda h: h[0]["pain"]) == DELAY
    assert first(history, lambda h: h[0]["burned"]) == 2 * DELAY
    # Fleeing from light on the left speeds up the left motor (turn right).
    assert first(history, lambda h: h[1]["left_motor"] == 6) == 3 * DELAY


def test_steering_reaches_the_motors_two_delays_later():
    v = moth()
    settle(v, 3.0, 3.0)
    speeds = []
    for _ in range(30):
        v.think({"left_eye": 3.5, "right_eye": 3.0})   # light now on the left
        speeds.append(v.motor_speeds["right_motor"])    # seeking it speeds up the right motor
    assert first(speeds, lambda s: s == 6) == 2 * DELAY


# 7. History matters
def test_burned_and_unburned_moths_steer_opposite_ways():
    # Both start 13 units from the single light at [60, 50] (within near), 27 degrees to their right.
    scenario = quick_scenario(ONE_LIGHT, [VEHICLE5, VEHICLE5], ["72,55,230", "72,55,230"])
    scenario.simulation.dt = DT
    sim = Simulation(scenario)
    unburned, burned = sim.vehicles
    burn(burned)
    burned.x, burned.y, burned.heading = unburned.x, unburned.y, unburned.heading

    def distance(v):
        return math.hypot(*sim.world.arena.delta(v.x - 60, v.y - 50))

    def angle_to_light(v):
        dx, dy = sim.world.arena.delta(60 - v.x, 50 - v.y)
        return abs((math.atan2(dy, dx) - v.heading + math.pi) % (2 * math.pi) - math.pi)

    start_angle, start_distance = angle_to_light(unburned), distance(unburned)
    sim.run(50)         # half a second: one turns toward the light, the other away
    assert angle_to_light(unburned) < start_angle < angle_to_light(burned)
    sim.run(100)        # 1.5 seconds in all: one is closer, the other farther
    assert distance(unburned) < start_distance < distance(burned)
