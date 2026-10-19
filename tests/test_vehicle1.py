"""Acceptance criteria of specs/vehicle-01.md."""

import math
import subprocess
import sys

import numpy as np
import pytest

from braitenberg.sim import Simulation
from braitenberg.world import load_world
from conftest import DEFAULT_WORLD, REPO


def vehicle_at(position, heading=0, **params):
    return {"type": "vehicle1", "position": position, "heading": heading,
            "sensor": "temperature", "params": params}


# 1. Speed follows stimulus
def test_speed_follows_stimulus(world_data, write_world):
    world_data["vehicles"] = [vehicle_at([55, 50], noise_std=0),
                              vehicle_at([90, 50], noise_std=0)]
    sim = Simulation(load_world(write_world(world_data)))
    starts = [(v.x, v.y) for v in sim.vehicles]
    sim.step()
    near, far = (math.dist(s, (v.x, v.y)) for s, v in zip(starts, sim.vehicles))
    assert near > far > 0
    assert sim.vehicles[0].speed > sim.vehicles[1].speed


def test_speed_is_capped(world_data, write_world):
    world_data["vehicles"] = [vehicle_at([50, 50], gain=100, max_speed=3)]
    sim = Simulation(load_world(write_world(world_data)))
    sim.step()
    assert sim.vehicles[0].speed == 3


# 2. No stimulus, no motion
def test_no_stimulus_no_motion(world_data, write_world):
    world_data["stimuli"]["temperature"]["sources"] = []
    sim = Simulation(load_world(write_world(world_data)))
    sim.run(1000)
    v = sim.vehicles[0]
    assert (v.x, v.y) == (20, 20)


# 3. Straight line without noise
def test_straight_line_without_noise(world_data, write_world):
    world_data["vehicles"] = [vehicle_at([20, 20], heading=30, noise_std=0)]
    sim = Simulation(load_world(write_world(world_data)))
    sim.run(5000)
    assert sim.vehicles[0].heading == pytest.approx(math.radians(30))


# 4. Lingers where it is cold
@pytest.mark.parametrize("seed", range(5))
def test_lingers_where_it_is_cold(seed):
    world = load_world(DEFAULT_WORLD)
    world.simulation.seed = seed
    sim = Simulation(world)
    total = 0.0
    steps = 100_000
    for _ in range(steps):
        sim.step()
        total += sim.vehicles[0].sensor_value
    time_average = total / steps

    n = 200
    xs = (np.arange(n) + 0.5) * world.arena.width / n
    ys = (np.arange(n) + 0.5) * world.arena.height / n
    gx, gy = np.meshgrid(xs, ys)
    arena_average = world.stimulus_at("temperature", gx, gy).mean()

    assert time_average < arena_average


# 5. Reproducible
def test_reproducible():
    world = load_world(DEFAULT_WORLD)

    def trajectory():
        sim = Simulation(world)
        points = []
        for _ in range(2000):
            sim.step()
            v = sim.vehicles[0]
            points.append((v.x, v.y, v.heading))
        return points

    assert trajectory() == trajectory()


def test_different_seeds_differ():
    a, b = load_world(DEFAULT_WORLD), load_world(DEFAULT_WORLD)
    b.simulation.seed = 1
    sa, sb = Simulation(a), Simulation(b)
    sa.run(200)
    sb.run(200)
    assert (sa.vehicles[0].x, sa.vehicles[0].y) != (sb.vehicles[0].x, sb.vehicles[0].y)


# 6. Headless: the vehicle module runs without importing pygame
def test_vehicle1_module_runs_headless():
    code = (
        "import sys, runpy\n"
        "sys.argv = ['vehicle1', '--headless', '--steps', '200']\n"
        "runpy.run_module('braitenberg.vehicle1', run_name='__main__')\n"
        "assert 'pygame' not in sys.modules, 'pygame was imported'\n"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=REPO,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "Hot spot: 200 steps" in result.stdout


# Edge rules
def test_wrap_edges(world_data, write_world):
    world_data["vehicles"] = [vehicle_at([99.9, 50], heading=0, base_speed=5, noise_std=0)]
    sim = Simulation(load_world(write_world(world_data)))
    sim.step()
    assert 0 <= sim.vehicles[0].x < 1


def test_bounce_edges(world_data, write_world):
    world_data["arena"]["edges"] = "bounce"
    world_data["vehicles"] = [vehicle_at([99.9, 50], heading=0, base_speed=5, noise_std=0)]
    sim = Simulation(load_world(write_world(world_data)))
    sim.step()
    v = sim.vehicles[0]
    assert 99 < v.x <= 100
    assert math.cos(v.heading) == pytest.approx(-1)
