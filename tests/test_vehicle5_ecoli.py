"""Acceptance criteria of specs/vehicle-05-ecoli.md."""

import copy
import math

import numpy as np
import pytest

from braitenberg.definition import load_definition
from braitenberg.diagram import definition_svg
from braitenberg.scenario import load_scenario
from braitenberg.sim import Simulation
from braitenberg.vehicle import Vehicle
from conftest import REPO

ECOLI = REPO / "vehicles" / "vehicle5-ecoli.yaml"
ECOLI_SCENARIO = REPO / "scenarios" / "vehicle5-ecoli.yaml"
FOOD = (100, 100)


def run(seed, seconds, habituation=True, noise_std=None):
    """Distance to the food at every step, and how many times `tumble` came on."""
    s = load_scenario(ECOLI_SCENARIO)
    s.simulation.seed = seed
    ecoli = copy.deepcopy(s.vehicles[0].definition)
    if not habituation:
        ecoli.sensors[0].habituation = None
    if noise_std is not None:
        ecoli.general.noise_std = noise_std
    s.vehicles[0].definition = ecoli
    sim = Simulation(s)
    v = sim.vehicles[0]
    distances, tumbles, was = [], 0, 0
    while sim.time < seconds - 1e-9:
        sim.step()
        distances.append(math.hypot(v.x - FOOD[0], v.y - FOOD[1]))
        tumbles += v.unit_outputs["tumble"] > was
        was = v.unit_outputs["tumble"]
    return np.array(distances), tumbles


def arrival(distances, dt=0.01):
    """Seconds until the first step within 20 of the food, or None."""
    near = np.flatnonzero(distances < 20)
    return near[0] * dt if len(near) else None


# 1. Finds the food, and 2. Stays there
@pytest.mark.parametrize("seed", range(5))
def test_finds_the_food_and_stays(seed):
    distances, _ = run(seed, 300)
    t = arrival(distances)
    assert t is not None and t <= 120
    assert distances[round(t / 0.01):].max() <= 30


# 3. Needs habituation
@pytest.mark.parametrize("seed", range(5))
def test_needs_habituation(seed):
    distances, tumbles = run(seed, 300, habituation=False)
    assert (distances < 20).mean() < 0.1
    assert tumbles <= 1


# 4. Running and tumbling
def ecoli():
    d = load_definition(ECOLI)
    d.general.noise_std = 0
    return Vehicle(d, 50, 50, 0, dt=0.01)


def smell(v, nose, seconds):
    """Hold the nose's output at `nose`: the tumble and heading at every step."""
    v.definition.sensors[0].habituation = None    # so the reading is the output
    tumble, heading = [], []
    for _ in range(round(seconds / 0.01)):
        v.think({"nose": nose})
        v.move(0.01, np.random.default_rng(0))
        tumble.append(v.unit_outputs["tumble"])
        heading.append(v.heading)
    return np.array(tumble), np.array(heading)


def test_runs_while_better():
    v = ecoli()
    smell(v, 0.01, 1.5)                      # past the tumble it starts with
    tumble, heading = smell(v, 0.01, 5)
    assert v.unit_outputs["better"] == 1
    assert tumble.max() == 0 and np.ptp(heading) == 0


def test_tumbles_while_not_better():
    tumble, heading = smell(ecoli(), 0.009, 6)
    starts = np.flatnonzero(np.diff(tumble) > 0) + 1
    assert starts[0] * 0.01 == pytest.approx(0.5, abs=0.02)
    ons = [len(run_) for run_ in np.split(tumble, np.flatnonzero(np.diff(tumble)) + 1) if run_[0]]
    offs = np.diff(starts) * 0.01 - 0.5
    assert all(n * 0.01 == pytest.approx(0.5, abs=0.02) for n in ons)
    assert offs == pytest.approx(1.0, abs=0.02)
    for a, b in zip(starts, starts[1:]):
        assert heading[b - 1] - heading[a - 1] == pytest.approx(1.5, abs=0.01)


# 5. Without noise
def test_finds_the_food_without_noise():
    paths = [run(seed, 120, noise_std=0)[0] for seed in (0, 1)]
    t = arrival(paths[0])
    assert t is not None and t <= 120
    assert np.array_equal(paths[0], paths[1])


def test_diagram_shows_the_habituated_nose():
    assert "nutrient, habituates 0.5 s" in definition_svg(load_definition(ECOLI))
