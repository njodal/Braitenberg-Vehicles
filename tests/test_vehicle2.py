"""Acceptance criteria of specs/vehicle-02.md."""

import math

import pytest

from braitenberg.scenario import load_scenario
from braitenberg.sim import Simulation
from conftest import FEAR_AND_AGGRESSION


# 1. Steering
@pytest.mark.parametrize("seed", range(5))
def test_fear_turns_away_and_aggression_hits(seed):
    scenario = load_scenario(FEAR_AND_AGGRESSION)
    scenario.simulation.seed = seed
    sim = Simulation(scenario)
    light = scenario.world.stimuli["light"].sources[0].position
    arena = scenario.world.arena

    def distance(v):
        return math.hypot(*arena.delta(v.x - light[0], v.y - light[1]))

    fear, aggression = sim.vehicles
    fear_start = distance(fear)
    closest = distance(aggression)
    for _ in range(600):
        sim.step()
        closest = min(closest, distance(aggression))
    assert distance(fear) > fear_start
    assert closest < aggression.half_length
