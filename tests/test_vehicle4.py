"""Acceptance criteria of specs/vehicle-04.md."""

import math

import pytest

from braitenberg.scenario import load_scenario
from braitenberg.sim import Simulation
from conftest import ORBITER_AND_DECIDER

STEPS = 3000


def run(seed):
    """Run the default scenario; return per-step distances and angles to the light, and motor speeds."""
    scenario = load_scenario(ORBITER_AND_DECIDER)
    scenario.simulation.seed = seed
    sim = Simulation(scenario)
    lx, ly = sim.world.stimuli["light"].sources[0].position
    orbiter, decider = sim.vehicles
    track = {"orbiter_distance": [], "orbiter_angle": [], "decider_distance": [],
             "decider_speeds": set()}
    for _ in range(STEPS):
        sim.step()
        dx, dy = sim.world.arena.delta(orbiter.x - lx, orbiter.y - ly)
        track["orbiter_distance"].append(math.hypot(dx, dy))
        track["orbiter_angle"].append(math.atan2(dy, dx))
        track["decider_distance"].append(
            math.hypot(*sim.world.arena.delta(decider.x - lx, decider.y - ly)))
        track["decider_speeds"].update(decider.motor_speeds.values())
    return sim, track


# 1. Orbiter circles the source
@pytest.mark.parametrize("seed", range(5))
def test_orbiter_circles_the_light(seed):
    _, track = run(seed)
    half = STEPS // 2
    distances = track["orbiter_distance"][half:]
    assert 15 <= min(distances) and max(distances) <= 25
    angles = track["orbiter_angle"][half:]
    swept = sum((b - a + math.pi) % (2 * math.pi) - math.pi for a, b in zip(angles, angles[1:]))
    assert abs(math.degrees(swept)) >= 720


# 2. Decider keeps out
@pytest.mark.parametrize("seed", range(5))
def test_decider_keeps_out_of_the_circle(seed):
    _, track = run(seed)
    closest = min(track["decider_distance"])
    assert 18 <= closest <= 22


# 3. Decisions are abrupt
@pytest.mark.parametrize("seed", range(5))
def test_decider_motor_speeds_jump(seed):
    sim, track = run(seed)
    motor = sim.vehicles[1].definition.actuators[0]
    assert track["decider_speeds"] == {motor.base_speed, motor.base_speed + motor.gain}
