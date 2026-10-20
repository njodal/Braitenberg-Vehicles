"""Acceptance criteria of specs/vehicle-01.md, for vehicles/vehicle1.yaml."""

import math

import numpy as np
import pytest

from braitenberg.scenario import load_scenario, quick_scenario
from braitenberg.sim import Simulation
from conftest import HOT_SPOT, VEHICLE1, VEHICLE1_SCENARIO, read, run_python


def vehicle1_variant(write, **motor):
    """vehicles/vehicle1.yaml with some motor values or noise_std changed."""
    data = read(VEHICLE1)
    if "noise_std" in motor:
        data["general"]["noise_std"] = motor.pop("noise_std")
    data["actuators"][0]["actuator"].update(motor)
    return write(data, "vehicle1.yaml")


# 1. Speed follows stimulus
def test_speed_follows_stimulus():
    sim = Simulation(quick_scenario(HOT_SPOT, [VEHICLE1, VEHICLE1], ["55,50,0", "90,50,0"]))
    starts = [(v.x, v.y) for v in sim.vehicles]
    sim.step()
    near, far = (math.dist(s, (v.x, v.y)) for s, v in zip(starts, sim.vehicles))
    assert near > far > 0
    assert sim.vehicles[0].speed > sim.vehicles[1].speed


def test_speed_is_capped(write):
    path = vehicle1_variant(write, gain=100, max_speed=3)
    sim = Simulation(quick_scenario(HOT_SPOT, [path], ["50,50,0"]))
    sim.step()
    assert sim.vehicles[0].speed == 3


# 2. No stimulus, no motion
def test_no_stimulus_no_motion(write):
    world = read(HOT_SPOT)
    world["stimuli"]["temperature"]["sources"] = []
    sim = Simulation(quick_scenario(write(world, "cold.yaml"), [VEHICLE1], ["20,20,0"]))
    sim.run(1000)
    v = sim.vehicles[0]
    assert (v.x, v.y) == (20, 20)


# 3. Straight line without noise
def test_straight_line_without_noise(write):
    path = vehicle1_variant(write, noise_std=0)
    sim = Simulation(quick_scenario(HOT_SPOT, [path], ["20,20,30"]))
    sim.run(5000)
    assert sim.vehicles[0].heading == pytest.approx(math.radians(30))


# 4. Lingers where it is cold
@pytest.mark.parametrize("seed", range(5))
def test_lingers_where_it_is_cold(seed):
    scenario = load_scenario(VEHICLE1_SCENARIO)
    scenario.simulation.seed = seed
    sim = Simulation(scenario)
    total = 0.0
    steps = 100_000
    for _ in range(steps):
        sim.step()
        total += sim.vehicles[0].sensor_values["sensor"]
    time_average = total / steps

    world = scenario.world
    n = 200
    xs = (np.arange(n) + 0.5) * world.arena.width / n
    ys = (np.arange(n) + 0.5) * world.arena.height / n
    gx, gy = np.meshgrid(xs, ys)
    arena_average = world.stimulus_at("temperature", gx, gy).mean()

    assert time_average < arena_average


# 5. Reproducible
def test_reproducible():
    scenario = load_scenario(VEHICLE1_SCENARIO)

    def trajectory():
        sim = Simulation(scenario)
        points = []
        for _ in range(2000):
            sim.step()
            v = sim.vehicles[0]
            points.append((v.x, v.y, v.heading))
        return points

    assert trajectory() == trajectory()


def test_different_seeds_differ():
    a, b = load_scenario(VEHICLE1_SCENARIO), load_scenario(VEHICLE1_SCENARIO)
    b.simulation.seed = 1
    sa, sb = Simulation(a), Simulation(b)
    sa.run(200)
    sb.run(200)
    assert (sa.vehicles[0].x, sa.vehicles[0].y) != (sb.vehicles[0].x, sb.vehicles[0].y)


# 6. Headless
def test_runs_headless_from_the_command_line():
    code = (
        "import sys, runpy\n"
        f"sys.argv = ['braitenberg', {str(VEHICLE1_SCENARIO)!r}, '--headless', '--steps', '200']\n"
        "runpy.run_module('braitenberg', run_name='__main__')\n"
        "assert 'pygame' not in sys.modules, 'pygame was imported'\n"
    )
    result = run_python(code)
    assert result.returncode == 0, result.stderr
    assert "Vehicle 1 in a hot spot: 200 steps" in result.stdout


# Edge rules
def test_wrap_edges(write):
    path = vehicle1_variant(write, base_speed=5, noise_std=0)
    sim = Simulation(quick_scenario(HOT_SPOT, [path], ["99.9,50,0"]))
    sim.step()
    assert 0 <= sim.vehicles[0].x < 1


def test_bounce_edges(write):
    world = read(HOT_SPOT)
    world["arena"]["edges"] = "bounce"
    path = vehicle1_variant(write, base_speed=5, noise_std=0)
    sim = Simulation(quick_scenario(write(world, "bounce.yaml"), [path], ["99.9,50,0"]))
    sim.step()
    v = sim.vehicles[0]
    assert 99 < v.x <= 100
    assert math.cos(v.heading) == pytest.approx(-1)
