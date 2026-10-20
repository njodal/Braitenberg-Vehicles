"""Acceptance criteria of specs/vehicle-05-forager.md."""

import math
from functools import lru_cache

import pytest

from braitenberg.definition import load_definition
from braitenberg.scenario import load_scenario
from braitenberg.sim import Simulation
from braitenberg.vehicle import Vehicle
from conftest import FORAGER, FORAGER_SCENARIO

DT = 0.01
STEPS = 24_000          # 240 seconds


@lru_cache(maxsize=None)
def run(seed):
    """Per-step (distance to the light, energy, unit outputs) for the default scenario."""
    scenario = load_scenario(FORAGER_SCENARIO)
    scenario.simulation.seed = seed
    sim = Simulation(scenario)
    v = sim.vehicles[0]
    lx, ly = sim.world.stimuli["light"].sources[0].position
    track = []
    for _ in range(STEPS):
        sim.step()
        track.append((math.hypot(*sim.world.arena.delta(v.x - lx, v.y - ly)), v.energy,
                      dict(v.unit_outputs)))
    return track


def switches(track):
    """Steps where `full` turns on, and where it turns off."""
    full = [units["full"] for _, _, units in track]
    on = [i for i in range(1, len(full)) if full[i] and not full[i - 1]]
    off = [i for i in range(1, len(full)) if full[i - 1] and not full[i]]
    return on, off


# 1. Recharges again and again
@pytest.mark.parametrize("seed", range(5))
def test_recharges_repeatedly(seed):
    on, _ = switches(run(seed))
    assert len(on) >= 3


# 2. Full until hungry
@pytest.mark.parametrize("seed", range(5))
def test_full_from_charged_until_hungry(seed):
    track = run(seed)
    on, off = switches(track)
    assert all(track[i][1] >= 90 for i in on)
    assert all(track[i][1] <= 30 for i in off)


# 3. Leaves when full
@pytest.mark.parametrize("seed", range(5))
def test_leaves_the_light_while_full(seed):
    track = run(seed)
    on, off = switches(track)
    for start in on:
        end = next((i for i in off if i > start), None)
        if end is None:
            continue            # still full when the run ends
        assert max(d for d, _, _ in track[start:end]) >= 40


# 4. Ignores the light while full
@pytest.mark.parametrize("seed", range(5))
def test_does_not_seek_while_full(seed):
    full_for = 0
    for _, _, units in run(seed):
        full_for = full_for + 1 if units["full"] else 0
        if full_for * DT >= 0.15:
            assert not units["seek_left"] and not units["seek_right"]


# 5. Logic
def forager(energy):
    v = Vehicle(load_definition(FORAGER), 0, 0, 0, dt=DT)
    v.energy = energy
    return v


def settle(v, left=0.0, right=0.0, steps=50):
    for _ in range(steps):
        v.think({"left_eye": left, "right_eye": right})
    return v.unit_outputs


@pytest.mark.parametrize("energy, charged, hungry", [(10, 0, 1), (30, 0, 1), (30.1, 0, 0), (60, 0, 0),
                                                     (89.9, 0, 0), (90, 1, 0), (100, 1, 0)])
def test_charged_and_hungry(energy, charged, hungry):
    out = settle(forager(energy))
    assert (out["charged"], out["hungry"]) == (charged, hungry)


def test_full_latches_from_charged_until_hungry():
    v = forager(95)
    assert settle(v)["full"] == 1
    for energy in (80, 60, 40, 31):
        v.energy = energy
        assert settle(v)["full"] == 1
    v.energy = 25
    assert settle(v)["full"] == 0
    v.energy = 60                       # not charged again yet
    assert settle(v)["full"] == 0


@pytest.mark.parametrize("energy, left, right, seeking", [
    (50, 3, 3, 1), (50, 1, 1, 0), (95, 3, 3, 0), (95, 1, 1, 0)])
def test_seeking(energy, left, right, seeking):
    assert settle(forager(energy), left, right)["seeking"] == seeking
