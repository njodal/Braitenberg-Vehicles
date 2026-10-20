"""Acceptance criteria of specs/vehicle-05-driver.md."""

from functools import lru_cache

import pytest

from braitenberg.definition import load_definition
from braitenberg.scenario import load_scenario, quick_scenario
from braitenberg.sim import Simulation
from braitenberg.vehicle import Vehicle
from conftest import DRIVER, DRIVER_SCENARIO, TRAFFIC_LIGHT, read

DT = 0.01
STEPS = 12_000          # 120 seconds
LIGHT_X = 50


@lru_cache(maxsize=None)
def run():
    """Per-step (time, x, speed, red on) for the default scenario. The driver has no noise."""
    sim = Simulation(load_scenario(DRIVER_SCENARIO))
    v = sim.vehicles[0]
    red = sim.world.stimuli["red"].sources[0]
    track = []
    for _ in range(STEPS):
        red_on = red.active(sim.time)      # the light as the sensors saw it this step
        sim.step()
        track.append((sim.time, v.x, v.speed, red_on))
    return track


def stops():
    """Indices where the driver comes to a stop."""
    track = run()
    return [i for i in range(1, len(track)) if track[i][2] == 0 and track[i - 1][2] > 0]


def before_light(x):
    return (LIGHT_X - x) % 100


# 1. Stops at red
def test_stops_before_red_light():
    track = run()
    assert len(stops()) >= 3
    for i in stops():
        _, x, _, red_on = track[i]
        assert red_on
        assert 5 <= before_light(x) <= 9


# 2. Waits while red, and 3. Goes on green
def test_waits_while_red_and_goes_on_green():
    track = run()
    for i in stops():
        j = next(k for k in range(i, len(track)) if not track[k][3])   # the light turns green
        assert all(speed == 0 for _, _, speed, _ in track[i:j])
        moving = next(k for k in range(j, len(track)) if track[k][2] > 0)
        assert (moving - j) * DT <= 0.15
        assert track[moving][2] == 5


# 4. Does not stop on green
def test_passes_green_light_at_full_speed():
    track = run()
    passes = [i for i in range(1, len(track)) if track[i - 1][1] < LIGHT_X <= track[i][1]]
    green_passes = []
    for i in passes:
        # Did it stop on the way in from 20 units before the light?
        start = next(k for k in range(i, -1, -1) if before_light(track[k][1]) >= 20 or k == 0)
        if all(speed > 0 for _, _, speed, _ in track[start:i]):
            green_passes.append(i)
            assert all(speed == 5 for _, _, speed, _ in track[start:i + 1])
    assert green_passes, "the scenario should include passing on green"


# 5. Ignores the light behind it
def test_ignores_light_behind():
    for i in stops():
        _, x, _, _ = run()[i]
        assert x < LIGHT_X          # every stop is before the light, never after passing it


@pytest.mark.parametrize("field_of_view, stops_behind", [(90, False), (None, True)])
def test_red_light_just_behind(write, field_of_view, stops_behind):
    # Start 2 units past the light while it is red: only eyes that look ahead ignore it.
    data = read(DRIVER)
    for item in data["sensors"]:
        if field_of_view is None:
            item["sensor"].pop("field_of_view")
    scenario = quick_scenario(TRAFFIC_LIGHT, [write(data, "driver.yaml")], ["52,10,0"])
    scenario.simulation.dt = DT
    sim = Simulation(scenario)
    sim.run(100)                # one second, all of it red
    assert (sim.vehicles[0].speed == 0) == stops_behind


# 6. One speed
def test_one_speed():
    assert {speed for _, _, speed, _ in run()} == {0, 5}


# 7. Logic
def settle(v, red, green, steps=30):
    for _ in range(steps):
        v.think({"red_eye": red, "green_eye": green})
    return v.unit_outputs


@pytest.mark.parametrize("red, green, red_close, green_ahead, go", [
    (0, 0, 0, 0, 1), (7.9, 0, 0, 0, 1), (8, 0, 1, 0, 0), (9, 0, 1, 0, 0),
    (0, 0.9, 0, 0, 1), (0, 1, 0, 1, 1), (9, 2, 1, 1, 1),
])
def test_logic(red, green, red_close, green_ahead, go):
    out = settle(Vehicle(load_definition(DRIVER), 0, 0, 0, dt=DT), red, green)
    assert (out["red_close"], out["green_ahead"], out["go"]) == (red_close, green_ahead, go)
