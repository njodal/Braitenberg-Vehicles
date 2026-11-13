"""Acceptance criteria of specs/vehicle-13.md."""

import math
import time
from functools import lru_cache

import numpy as np
import pytest

from braitenberg.definition import load_definition
from braitenberg.diagram import definition_svg
from braitenberg.scenario import load_scenario
from braitenberg.sim import Simulation
from braitenberg.vehicle import Vehicle
from conftest import REPO, run_python

DT = 0.01
ONCE_BITTEN = REPO / "vehicles" / "vehicle13-once-bitten.yaml"
SCENARIO = REPO / "scenarios" / "vehicle13-once-bitten.yaml"
SEEDS = range(5)
SECONDS = 300
BULLY = 4          # index of the bully among the other vehicles
WIRE = ("p_green", "p_hurt")
UNITS = ("touched", "r_green", "afraid", "upset", "calm", "e_green", "e_hurt", "w_green",
         "w_hurt")


def distance(a, b, size=100):
    dx = (a.x - b.x + size / 2) % size - size / 2
    dy = (a.y - b.y + size / 2) % size - size / 2
    return math.hypot(dx, dy)


def scenario(variant="default", seed=0):
    """The default scenario; "control" never gets upset, "grazers" has no bully."""
    s = load_scenario(SCENARIO)
    s.simulation.seed = seed
    if variant == "grazers":
        s.vehicles = s.vehicles[:BULLY + 1]
    if variant == "control":
        upset = next(u for u in s.vehicles[0].definition.units if u.name == "upset")
        upset.inputs = [c for c in upset.inputs if c.source != "touched"]
    return s


@lru_cache(maxsize=None)
def run(variant, seed, seconds=SECONDS):
    """Per step: time, the wire's strength, the outputs of UNITS, and the distance to each of
    the other vehicles."""
    sim = Simulation(scenario(variant, seed))
    v, others = sim.vehicles[0], sim.vehicles[1:]
    track = []
    for _ in range(round(seconds / DT)):
        sim.step()
        track.append((sim.time, v.strength(*WIRE), {n: v.unit_outputs[n] for n in UNITS},
                      [distance(v, o) for o in others]))
    return track


def onsets(track, unit):
    return [k for k in range(1, len(track))
            if track[k][2][unit] > 0 and track[k - 1][2][unit] <= 0]


def bites(track):
    return onsets(track, "touched")


def learned(track):
    """The step at which the wire first exceeds 0.7, or None."""
    return next((k for k, step in enumerate(track) if step[1] > 0.7), None)


def upset_end(track, k):
    """The first step from k on at which upset is off."""
    return next((j for j in range(k, len(track)) if track[j][2]["upset"] <= 0), len(track))


# 1. Grazers are harmless
@pytest.mark.slow
@pytest.mark.parametrize("seed", SEEDS)
def test_grazers_are_harmless(seed):
    track = run("grazers", seed)
    assert not bites(track)
    assert all(step[1] == 0 for step in track)
    assert not onsets(track, "afraid")


# 2. Learns from one bite
@pytest.mark.slow
@pytest.mark.parametrize("seed", SEEDS)
def test_learns_from_one_bite(seed):
    track = run("default", seed)
    first = bites(track)[0]
    assert all(step[1] == 0 for step in track[:first])
    upset_on = next(k for k in range(first, len(track)) if track[k][2]["upset"] > 0)
    k = learned(track)
    assert k is not None and first < k < upset_end(track, upset_on)


# 3. Reverberation
@pytest.mark.slow
@pytest.mark.parametrize("seed", SEEDS)
def test_learns_from_the_echo(seed):
    track = run("default", seed)
    upset_on = next(k for k in range(bites(track)[0], len(track)) if track[k][2]["upset"] > 0)
    end = upset_end(track, upset_on)
    green = [k for k in onsets(track, "e_green") if upset_on < k < end]
    hurt = [k for k in onsets(track, "e_hurt") if upset_on < k < end]
    assert len(green) >= 2 and len(hurt) >= 2
    for h in hurt:
        gap = (h - max(g for g in green if g < h)) * DT
        assert 0.25 <= gap <= 5
    # The switches have turned 0.2 s after upset: from then on nothing from the world.
    settled = upset_on + round(0.2 / DT)
    assert not any(track[k][2]["w_green"] or track[k][2]["w_hurt"] for k in range(settled, end))


# 4. The control does not
@pytest.mark.slow
@pytest.mark.parametrize("seed", SEEDS)
def test_control_does_not_learn_from_one_bite(seed):
    track = run("control", seed)
    first = bites(track)[0]
    assert track[first + round(1 / DT)][1] <= 0.25
    assert all(step[1] <= 0.7 for step in track[first:first + round(30 / DT)])


# 5. Fears every green vehicle
@pytest.mark.slow
@pytest.mark.parametrize("seed", SEEDS)
def test_fears_every_green_vehicle(seed):
    track = run("default", seed)
    since = learned(track)
    until = next((k for k in range(since, len(track)) if track[k][1] <= 0.7), len(track))
    meetings = [k for k in onsets(track, "r_green")
                if since < k < until and track[k][2]["calm"] > 0]
    feared = [k for k in meetings
              if any(step[2]["afraid"] > 0 for step in track[k:k + round(1 / DT)])]
    assert meetings and len(feared) >= 0.8 * len(meetings)
    ran = []
    for k in feared:
        nearest = int(np.argmin(track[k][3]))
        later = min(k + round(3 / DT), len(track) - 1)
        if nearest != BULLY and track[later][3][nearest] > track[k][3][nearest]:
            ran.append(k)
    assert ran


# 6. Fewer bites
@pytest.mark.slow
def test_bitten_half_as_often_as_the_control():
    def count(variant):
        total = 0
        for seed in SEEDS:
            b = bites(run(variant, seed))
            total += len(b)
        return total
    assert count("default") <= count("control") / 2


# 7. The switches
def once_bitten(learn=None):
    d = load_definition(ONCE_BITTEN)
    if learn is not None:
        p_hurt = next(u for u in d.units if u.name == "p_hurt")
        next(c for c in p_hurt.inputs if c.learning).learning.learn = learn
    return Vehicle(d, 50, 50, 0, dt=DT)


def force(v, outputs):
    """Make units' outputs at this step what `outputs` says, whatever they computed."""
    rows = len(v.activations)
    for name, value in outputs.items():
        k = v.unit_names.index(name)
        v.activations[(v.t - v.steps[k]) % rows, k] = value


NOTHING = {"eye": np.zeros((4, 24)), "ir_left": 0.0, "ir_right": 0.0, "skin": 0.0}


def play(v, seconds, forced=lambda t: {}, watch=()):
    """Step v for `seconds`, forcing outputs by time; returns the onset times of `watch`."""
    seen = {name: [] for name in watch}
    before = {name: 0.0 for name in watch}
    rng = np.random.default_rng(0)
    for n in range(round(seconds / DT)):
        t = n * DT
        force(v, forced(t))
        v.step(NOTHING, DT, rng)
        for name in watch:
            now = v.unit_outputs[name]
            if now > 0 and before[name] <= 0:
                seen[name].append(round(t, 2))
            before[name] = now
    return seen


def pulse(name, at, length=0.05):
    return lambda t: {name: 1.0} if at <= t < at + length else {}


def together(*fs):
    def forced(t):
        out = {}
        for f in fs:
            out.update(f(t))
        return out
    return forced


def held(name, value, until=math.inf):
    return lambda t: {name: value} if t < until else {}


WATCH = ("p_green", "echo1_green")


@pytest.mark.parametrize("upset", [0.0, 1.0])
def test_switches_from_the_world(upset):
    v = once_bitten(learn=0)
    seen = play(v, 4, together(held("upset", upset), pulse("r_green", 0.5, 0.3)), WATCH)
    if upset:
        assert seen == {"p_green": [], "echo1_green": []}
    else:
        assert seen["p_green"] and seen["echo1_green"]


@pytest.mark.parametrize("upset", [0.0, 1.0])
def test_switches_from_the_echo(upset):
    v = once_bitten(learn=0)
    seen = play(v, 4, together(held("upset", upset), pulse("echo2_green", 0.5)), WATCH)
    if upset:
        assert seen["p_green"] and seen["echo1_green"]   # P, and round the loop
    else:
        assert seen == {"p_green": [], "echo1_green": []}


def test_p_feeds_the_memory_only_while_upset():
    for upset in (0.0, 1.0):
        v = once_bitten(learn=0)
        seen = play(v, 4, together(held("upset", upset), pulse("p_green", 0.5, 0.3)), WATCH)
        assert bool(seen["echo1_green"]) == bool(upset)


# 8. The loop
def test_the_loop():
    v = once_bitten(learn=0)
    release = 30
    forced = together(held("upset", 1.0, release), pulse("echo1_green", 0.5),
                      pulse("echo1_hurt", 2.5))
    seen = play(v, release + 10, forced, ("p_green", "p_hurt"))
    green, hurt = seen["p_green"], seen["p_hurt"]
    assert len(green) >= 4 and len(green) == len(hurt)
    assert all(abs(b - a - 5.45) <= 0.3 for a, b in zip(green, green[1:]))
    assert all(abs(b - a - 5.45) <= 0.3 for a, b in zip(hurt, hurt[1:]))
    assert all(abs(h - g - 2) <= 0.3 for g, h in zip(green, hurt))
    assert green[-1] < release + 0.5 and hurt[-1] < release + 0.5


# 9. Remembers
@pytest.mark.slow
def test_remembers_for_fifteen_meetings():
    s = scenario("grazers", 0)
    sim = Simulation(s)
    v = sim.vehicles[0]
    k = next(j for j, c in enumerate(v.definition.units[v.unit_names.index("p_hurt")].inputs)
             if c.learning)
    v.strengths[("p_hurt", k)] = 1.0
    meetings, before = 0, 0.0
    while meetings < 15:
        sim.step()
        assert v.unit_outputs["touched"] == 0
        assert v.strength(*WIRE) > 0.7
        now = v.unit_outputs["r_green"]
        meetings += now > 0 and before <= 0
        before = now
        assert sim.time < 1200


# 10. Headless and fast
def test_runs_without_pygame():
    result = run_python(
        "import sys\n"
        "from braitenberg.scenario import load_scenario\n"
        "from braitenberg.sim import Simulation\n"
        "Simulation(load_scenario('scenarios/vehicle13-once-bitten.yaml')).run(100)\n"
        "assert 'pygame' not in sys.modules\n")
    assert result.returncode == 0, result.stderr


@pytest.mark.slow
def test_runs_faster_than_ten_times_real_time():
    sim = Simulation(load_scenario(SCENARIO))
    start = time.perf_counter()
    sim.run(round(SECONDS / DT))
    assert time.perf_counter() - start < 30


# Definitions and diagram
def test_definition_loads_with_its_parts():
    d = load_definition(ONCE_BITTEN)
    assert d.general.type == "13"
    assert d.general.name == "Once bitten (learns from one bad encounter)"
    p_hurt = next(u for u in d.units if u.name == "p_hurt")
    wire = next(c for c in p_hurt.inputs if c.learning)
    assert (wire.source, wire.strength, wire.learning.type) == ("p_green", 0, "ergotrix")


def test_diagram_draws_the_loop():
    svg = definition_svg(load_definition(ONCE_BITTEN))
    for name in ("echo1_green", "echo2_hurt", "p_green", "p_hurt", "upset", "afraid"):
        assert name in svg
