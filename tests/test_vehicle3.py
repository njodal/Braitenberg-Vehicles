"""Acceptance criteria of specs/vehicle-03.md."""

import math

import pytest

from braitenberg.definition import load_definition
from braitenberg.scenario import load_scenario
from braitenberg.sim import Simulation
from braitenberg.vehicle import Vehicle
from conftest import LOVE_AND_EXPLORER, VEHICLE3A, VEHICLE3B

STEPS = 2000


def run(seed):
    """Run the default scenario; return the simulation and the explorer's distance and speed per step."""
    scenario = load_scenario(LOVE_AND_EXPLORER)
    scenario.simulation.seed = seed
    sim = Simulation(scenario)
    explorer = sim.vehicles[1]
    distances, speeds = [], []
    for _ in range(STEPS):
        sim.step()
        distances.append(distance_to_light(sim, explorer))
        speeds.append(explorer.speed)
    return sim, distances, speeds


def light(sim):
    return sim.world.stimuli["light"].sources[0].position


def distance_to_light(sim, v):
    lx, ly = light(sim)
    return math.hypot(*sim.world.arena.delta(v.x - lx, v.y - ly))


def angle_to_light(sim, v):
    """Angle between the vehicle's heading and the direction to the light, in degrees."""
    lx, ly = light(sim)
    dx, dy = sim.world.arena.delta(lx - v.x, ly - v.y)
    diff = (math.atan2(dy, dx) - v.heading + math.pi) % (2 * math.pi) - math.pi
    return math.degrees(abs(diff))


def start_distance(index):
    sim = Simulation(load_scenario(LOVE_AND_EXPLORER))
    return distance_to_light(sim, sim.vehicles[index])


# 1. Love comes to rest near the source
@pytest.mark.parametrize("seed", range(5))
def test_love_comes_to_rest_facing_the_light(seed):
    sim, _, _ = run(seed)
    love = sim.vehicles[0]
    base_speed = love.definition.actuators[0].base_speed
    assert distance_to_light(sim, love) < start_distance(0) / 2
    assert love.speed < 0.1 * base_speed
    assert angle_to_light(sim, love) < 60


# 2. Explorer turns away
@pytest.mark.parametrize("seed", range(5))
def test_explorer_approaches_then_turns_away(seed):
    _, distances, _ = run(seed)
    closest = min(range(600), key=lambda k: distances[k])
    assert distances[closest] < start_distance(1)
    assert max(distances[closest:closest + 600]) >= distances[closest] + 20


# 3. Explorer never stops
@pytest.mark.parametrize("seed", range(5))
def test_explorer_never_stops(seed):
    sim, _, speeds = run(seed)
    base_speed = sim.vehicles[1].definition.actuators[0].base_speed
    assert min(speeds) >= 0.2 * base_speed


# 4. Inhibition
@pytest.mark.parametrize("path", [VEHICLE3A, VEHICLE3B])
@pytest.mark.parametrize("reading", [0, 2, 5, 8.3, 20])
def test_motor_speed_is_base_minus_gain_times_reading(path, reading):
    v = Vehicle(load_definition(path), 50, 50, 0)
    v.think({"left_eye": reading, "right_eye": reading})
    for a in v.definition.actuators:
        assert v.motor_speeds[a.name] == pytest.approx(max(a.base_speed - a.gain * reading, 0))


def test_wiring():
    for path, crossed in [(VEHICLE3A, False), (VEHICLE3B, True)]:
        d = load_definition(path)
        for a in d.actuators:
            [c] = a.inputs
            assert c.inhibitory
            same_side = c.source.split("_")[0] == a.name.split("_")[0]
            assert same_side != crossed
