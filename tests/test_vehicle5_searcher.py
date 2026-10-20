"""Acceptance criteria of specs/vehicle-05-searcher.md."""

import math

import pytest

from braitenberg.definition import load_definition
from braitenberg.scenario import load_scenario, quick_scenario
from braitenberg.sim import Simulation
from braitenberg.vehicle import Vehicle
from conftest import SEARCHER, SEARCHER_SCENARIO

DT = 0.01


def dark_run(write, steps=4000):
    """The searcher alone in a world without light, without noise; per-step headings and units."""
    world = write({"name": "Dark", "arena": {"width": 100, "height": 100},
                   "stimuli": {"light": {"sources": []}}}, "dark.yaml")
    scenario = quick_scenario(world, [SEARCHER], ["50,50,0"])
    scenario.simulation.dt = DT
    scenario.vehicles[0].definition.general.noise_std = 0
    sim = Simulation(scenario)
    v = sim.vehicles[0]
    track = []
    for _ in range(steps):
        sim.step()
        track.append((math.degrees(v.heading), dict(v.unit_outputs)))
    return track[300:]          # after the first 3 seconds


def cycles(values):
    """Indices where a 0/1 signal turns on."""
    return [i for i in range(1, len(values)) if values[i] and not values[i - 1]]


# 1. Zigzag
def test_zigzags_without_drifting(write):
    track = dark_run(write)
    starts = cycles([units["osc_b"] for _, units in track])
    assert len(starts) >= 5
    swings = []
    for a, b in zip(starts, starts[1:]):
        headings = [h for h, _ in track[a:b]]
        swings.append((round(min(headings), 6), round(max(headings), 6)))
    # Every cycle swings over the same range of headings: no drift.
    assert len(set(swings)) == 1
    low, high = swings[0]
    assert high - low >= 30


# 2. Even turns
def test_oscillator_turns_evenly(write):
    track = dark_run(write)
    b = [units["osc_b"] for _, units in track]
    c = [units["osc_c"] for _, units in track]
    starts = cycles(b)
    first, last = starts[0], starts[-1]           # whole cycles only
    b_only = sum(x and not y for x, y in zip(b[first:last], c[first:last]))
    c_only = sum(y and not x for x, y in zip(b[first:last], c[first:last]))
    assert b_only > 0
    assert abs(b_only - c_only) <= 0.02 * b_only
    assert all(x or y for x, y in zip(b, c))


# 3. Finds the light
@pytest.mark.parametrize("seed", range(5))
def test_finds_the_light(seed):
    scenario = load_scenario(SEARCHER_SCENARIO)
    scenario.simulation.seed = seed
    sim = Simulation(scenario)
    v = sim.vehicles[0]
    lx, ly = sim.world.stimuli["light"].sources[0].position
    for _ in range(round(30 / DT)):
        sim.step()
        if math.hypot(*sim.world.arena.delta(v.x - lx, v.y - ly)) < 2:
            return
    pytest.fail("did not reach the light within 30 seconds")


# 4. Straight to the light
@pytest.mark.parametrize("seed", range(5))
def test_no_zigzag_while_the_light_is_in_sight(seed):
    scenario = load_scenario(SEARCHER_SCENARIO)
    scenario.simulation.seed = seed
    sim = Simulation(scenario)
    v = sim.vehicles[0]
    sees_for = 0
    for _ in range(round(20 / DT)):
        sim.step()
        sees_for = sees_for + 1 if v.unit_outputs["sees"] else 0
        if sees_for * DT >= 0.1:
            assert not v.unit_outputs["zig"] and not v.unit_outputs["zag"]
    assert sees_for > 0       # it did see the light


# 5. Logic
def settle(v, left, right, steps=50):
    for _ in range(steps):
        v.think({"left_eye": left, "right_eye": right})
    return v.unit_outputs


@pytest.mark.parametrize("left, right, sees", [(1, 1, 0), (1.99, 1.99, 0), (2, 2, 1), (3.5, 0.5, 1)])
def test_sees(left, right, sees):
    assert settle(Vehicle(load_definition(SEARCHER), 0, 0, 0, dt=DT), left, right)["sees"] == sees


@pytest.mark.parametrize("left, right", [(1.0, 1.0), (3.0, 3.0), (3.5, 2.5), (2.5, 3.5), (1.2, 1.0)])
def test_zig_zag_and_seek(left, right):
    v = Vehicle(load_definition(SEARCHER), 0, 0, 0, dt=DT)
    settle(v, left, right, steps=200)
    history = []
    for _ in range(300):        # long enough for the oscillator to take turns
        out = settle(v, left, right, steps=1)
        history.append(dict(out))
    final = history[-1]
    sees = final["sees"]
    assert sees == (left + right >= 4)
    if sees:
        assert not any(h["zig"] or h["zag"] for h in history)
        assert final["seek_left"] == final["left_brighter"]
        assert final["seek_right"] == final["right_brighter"]
    else:
        assert not any(h["seek_left"] or h["seek_right"] for h in history)
        assert any(h["zig"] for h in history) and any(h["zag"] for h in history)
