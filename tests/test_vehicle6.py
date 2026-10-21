"""Acceptance criteria of specs/vehicle-06.md."""

import copy
import csv

import numpy as np
import pytest
import yaml

from braitenberg.definition import load_definition
from braitenberg.evolve import (Start, ancestor_genome, apply_genome, best_definition_data,
                                copy_genome, evolve, load_evolution, trial, write_results)
from braitenberg.world import load_world
from braitenberg.yamlfile import ConfigError
from conftest import FORAGER, ONE_LIGHT, REPO, read, run_python

FORAGER_EVOLUTION = REPO / "evolutions" / "forager.yaml"
FAR_LIGHTS = REPO / "worlds" / "far-lights.yaml"


def small(**changes):
    """A small evolution of the forager that runs in seconds."""
    data = {
        "name": "Small",
        "ancestor": str(FORAGER),
        "world": str(ONE_LIGHT),
        "population": 6,
        "survivors": 2,
        "generations": 3,
        "seed": 1,
        "trials": {"count": 2, "duration": 20, "dt": 0.05, "validation": 2},
        "genes": [
            {"gene": {"name": "sees", "targets": ["units.sees.threshold"],
                      "min": 0.5, "max": 8, "sigma": 0.5}},
            {"gene": {"name": "gain", "targets": ["actuators.left_motor.gain",
                                                  "actuators.right_motor.gain"],
                      "min": 0, "max": 5, "sigma": 0.3}},
        ],
    }
    data.update(changes)
    return data


# 1. Load

def test_load_example():
    e = load_evolution(FORAGER_EVOLUTION)
    assert e.ancestor.general.name == "Forager"
    assert e.world.name == "Far lights"
    assert (e.population, e.survivors, e.generations, e.seed, e.rate) == (20, 5, 30, 0, 0.3)
    assert (e.trials.count, e.trials.duration, e.trials.dt, e.trials.validation) == (5, 300, 0.01, 20)
    genes = {g.name: g for g in e.genes}
    assert list(genes) == ["sees", "brighter", "charged", "hungry", "rhythm", "gain",
                           "base_speed", "max_speed"]
    assert [g.start for g in e.genes] == [3, 0.05, 90, -30, 0.3, 3, 3, 6]
    assert [str(t) for t in genes["rhythm"].targets] == [
        "units.osc_a.delay", "units.osc_b.delay", "units.osc_c.delay"]


def test_far_lights_world():
    w = load_world(FAR_LIGHTS)
    assert (w.arena.width, w.arena.height, w.arena.edges) == (200, 200, "wrap")
    assert [s.position for s in w.stimuli["light"].sources] == [(50, 50), (150, 150)]


# 2. Validation

def gene(**changes):
    g = {"name": "g", "targets": ["units.sees.threshold"], "min": 0.5, "max": 8, "sigma": 0.5}
    g.update(changes)
    return {"gene": g}


@pytest.mark.parametrize("changes, key", [
    ({"name": None}, "name"),
    ({"extra": 1}, "extra"),
    ({"ancestor": "missing.yaml"}, "ancestor"),
    ({"world": "missing.yaml"}, "world"),
    ({"world": str(REPO / "worlds" / "hot-spot.yaml")}, "ancestor"),
    ({"population": 1}, "population"),
    ({"survivors": 6}, "survivors"),
    ({"survivors": 0}, "survivors"),
    ({"trials": {"count": 0, "duration": 10}}, "trials.count"),
    ({"trials": {"count": 1, "duration": -1}}, "trials.duration"),
    ({"mutation": {"rate": 1.5}}, "mutation.rate"),
    ({"start": "best"}, "start"),
    ({"genes": []}, "genes"),
    ({"genes": [{"name": "g"}]}, "genes[0]"),
    ({"genes": [gene(), gene()]}, "genes[1].gene.name"),
    ({"genes": [gene(targets=["units.nobody.threshold"])]}, "genes[0].gene.targets[0]"),
    ({"genes": [gene(targets=["units.sees.inputs"])]}, "genes[0].gene.targets[0]"),
    ({"genes": [gene(targets=["energy.consumption"])]}, "genes[0].gene.targets[0]"),
    ({"genes": [gene(targets=["sensors.left_eye.response.at"])]}, "genes[0].gene.targets[0]"),
    ({"genes": [gene(min=8, max=8)]}, "genes[0].gene.min"),
    ({"genes": [gene(sigma=0)]}, "genes[0].gene.sigma"),
    ({"genes": [gene(targets=["units.sees.threshold", "units.charged.threshold"],
                     max=100)]}, "genes[0].gene.targets"),
    ({"genes": [gene(min=5)]}, "genes[0].gene.targets"),
])
def test_validation(write, changes, key):
    path = write(small(**changes))
    with pytest.raises(ConfigError) as e:
        load_evolution(path)
    assert str(path) in str(e.value)
    assert key in str(e.value)


def test_sensor_response_gene(write, tmp_path):
    data = read(FORAGER)
    data["sensors"][0]["sensor"]["response"] = {"type": "peak", "at": 4, "width": 1.5}
    ancestor = write(data, "ancestor.yaml")
    e = load_evolution(write(small(ancestor=str(ancestor), genes=[
        gene(targets=["sensors.left_eye.response.at"], min=1, max=8)])))
    assert e.genes[0].start == 4
    assert apply_genome(e, (5.0,)).sensors[0].response.at == 5.0


# 3. Genomes

def test_apply_genome(write):
    e = load_evolution(write(small()))
    d = apply_genome(e, (2.5, 4.0))
    expected = copy.deepcopy(e.ancestor)
    next(u for u in expected.units if u.name == "sees").threshold = 2.5
    for a in expected.actuators:
        a.gain = 4.0
    assert d == expected
    assert apply_genome(e, ancestor_genome(e)) == e.ancestor
    assert next(u for u in e.ancestor.units if u.name == "sees").threshold == 3  # untouched


# 4. Copying

def test_copying():
    e = load_evolution(FORAGER_EVOLUTION)
    rng = np.random.default_rng(0)
    first = ancestor_genome(e)
    assert copy_genome(e.genes, first, 0.0, rng) == first
    copies = np.array([copy_genome(e.genes, first, 1.0, rng) for _ in range(4000)])
    for i, g in enumerate(e.genes):
        assert copies[:, i].min() >= g.min and copies[:, i].max() <= g.max
    assert (copies != np.array(first)).all()
    # sees starts at 3 in [0.5, 8] with sigma 0.5: far from its limits.
    changes = copies[:, 0] - first[0]
    assert abs(changes.mean()) < 0.03
    assert abs(changes.std() - 0.5) < 0.03
    # rate 0.3: about 30% of the genes change.
    copies = np.array([copy_genome(e.genes, first, 0.3, rng) for _ in range(2000)])
    assert abs((copies != np.array(first)).mean() - 0.3) < 0.02


# 5. Trials

def walker(write, consumption):
    """A vehicle that drives straight at speed 2, with 10 energy and nothing to recharge it."""
    data = {
        "general": {"type": "6", "name": "Walker", "size": 4},
        "sensors": [],
        "energy": {"initial": 10, "max": 10, "consumption": consumption},
        "actuators": [{"actuator": {"name": "motor", "type": "motor", "position": [0, -0.8],
                                    "inputs": [], "base_speed": 2}}],
    }
    return load_definition(write(data, "walker.yaml"))


def test_trial_ends_when_energy_runs_out(write):
    world = load_world(ONE_LIGHT)
    start = Start((10, 10), 0.0, 0)
    t = trial(walker(write, 1), world, start, duration=60, dt=0.01)
    assert t == pytest.approx(10 / (1 * 2), abs=0.01)
    assert trial(walker(write, 0), world, start, duration=60, dt=0.01) == 60


def test_trial_time_is_the_step_where_energy_reaches_zero(write):
    world = load_world(ONE_LIGHT)
    t = trial(walker(write, 1), world, Start((10, 10), 0.0, 0), duration=60, dt=0.3)
    # 0.6 energy per step: 10 is used up during step 17, at t = 5.1.
    assert t == pytest.approx(17 * 0.3)


# 6. Selection, 7. Determinism, 10. Results

@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    folder = tmp_path_factory.mktemp("evolution")
    path = folder / "small.yaml"
    path.write_text(yaml.safe_dump(small()))
    e = load_evolution(path)
    results = {}
    for workers in (1, 3):
        result = evolve(e, workers)
        out = folder / f"out{workers}"
        write_results(result, out)
        results[workers] = (result, out)
    return e, results


def test_selection(runs):
    e, results = runs
    result, _ = results[1]
    assert len(result.generations) == e.generations + 1
    first = result.generations[0]
    assert sorted(m.genome for m in first).count(ancestor_genome(e)) >= 1
    assert all(m.parent is None for m in first)
    for prev, gen in zip(result.generations, result.generations[1:]):
        assert len(gen) == e.population
        survivors = prev[:e.survivors]
        survivor_genomes = [m.genome for m in survivors]
        kept = [m for m in gen if m.genome in survivor_genomes and m.parent ==
                survivor_genomes.index(m.genome)]
        assert len(kept) >= e.survivors
        parents = sorted(m.parent for m in gen)
        expected = list(range(e.survivors)) + [i % e.survivors
                                               for i in range(e.population - e.survivors)]
        assert parents == sorted(expected)
        assert gen[0].survival >= prev[0].survival
        assert [m.survival for m in gen] == sorted((m.survival for m in gen), reverse=True)
        for m in gen:
            assert m.parent < e.survivors


def test_determinism(runs):
    _, results = runs
    (a, out_a), (b, out_b) = results[1], results[3]
    assert (out_a / "log.csv").read_text() == (out_b / "log.csv").read_text()
    assert (out_a / "best.yaml").read_text() == (out_b / "best.yaml").read_text()
    assert a.validation == b.validation


def test_results(runs):
    e, results = runs
    result, out = results[1]
    for name in ("log.csv", "best.yaml", "summary.yaml", "survival.png", "genes.png"):
        assert (out / name).stat().st_size > 0
    best = load_definition(out / "best.yaml")
    expected = apply_genome(e, result.best.genome)
    assert best.general.type == "6"
    assert best.general.name == "Forager (evolved)"
    best.general, best.path = expected.general, expected.path
    assert best == expected
    rows = list(csv.DictReader(open(out / "log.csv")))
    assert len(rows) == e.population * (e.generations + 1)
    last = [r for r in rows if int(r["generation"]) == e.generations]
    summary = yaml.safe_load((out / "summary.yaml").read_text())
    top = next(r for r in last if r["rank"] == "0")
    assert summary["survival"]["best"] == float(top["survival"])
    assert summary["best_genome"] == {g.name: float(top[g.name]) for g in e.genes}
    assert summary["generations"] == e.generations
    assert set(summary["validation_survival"]) == {"ancestor", "best"}


def test_best_definition_data_keeps_the_file_format(runs):
    _, results = runs
    result, _ = results[1]
    data = best_definition_data(result)
    assert list(data) == list(read(FORAGER))
    assert data["units"][0]["unit"]["name"] == "osc_a"


# 8. It works

@pytest.mark.slow
def test_evolved_forager_lasts_twice_as_long(tmp_path):
    e = load_evolution(FORAGER_EVOLUTION)
    result = evolve(e, workers=8)
    assert result.validation["best"] >= 2 * result.validation["ancestor"]


def test_committed_evolved_forager():
    """The committed vehicle is the forager with the evolution's genes changed, nothing else."""
    e = load_evolution(FORAGER_EVOLUTION)
    evolved = load_definition(REPO / "vehicles" / "vehicle6-forager.yaml")
    assert evolved.general.type == "6"
    genome = []
    for g in e.genes:
        values = {getattr(t_part, t.key) for t in g.targets
                  for t_part in [next(p for p in getattr(evolved, t.section) if p.name == t.name)]}
        assert len(values) == 1
        genome.append(values.pop())
    expected = apply_genome(e, tuple(genome))
    evolved.general, evolved.path = expected.general, expected.path
    assert evolved == expected


# 9. Random start

def test_random_start(write):
    e = load_evolution(write(small(start="random", generations=0)))
    assert e.start == "random"
    a, b = evolve(e), evolve(e)
    first = a.generations[0]
    assert len(first) == e.population
    assert all(m.parent is None for m in first)
    assert all(m.genome != ancestor_genome(e) for m in first)
    for m in first:
        for g, v in zip(e.genes, m.genome):
            assert g.min <= v <= g.max
    assert sorted(m.genome for m in first) == sorted(m.genome for m in b.generations[0])
    e.seed += 1
    c = evolve(e)
    assert sorted(m.genome for m in first) != sorted(m.genome for m in c.generations[0])
    assert a.ancestor_survival > 0



def test_random_example():
    e = load_evolution(REPO / "evolutions" / "forager-random.yaml")
    assert e.start == "random"
    assert e.genes == load_evolution(FORAGER_EVOLUTION).genes


# 11. Headless

def test_headless():
    r = run_python(
        "import sys\n"
        "from braitenberg.evolve import load_evolution, evolve\n"
        "e = load_evolution('evolutions/forager.yaml')\n"
        "e.population, e.survivors, e.generations = 2, 1, 1\n"
        "e.trials.count, e.trials.duration, e.trials.dt, e.trials.validation = 1, 2, 0.05, 0\n"
        "evolve(e)\n"
        "assert 'pygame' not in sys.modules\n")
    assert r.returncode == 0, r.stderr

