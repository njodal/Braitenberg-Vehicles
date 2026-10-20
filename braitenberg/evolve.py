"""Vehicle 6: tune a vehicle's numbers by selection (specs/vehicle-06.md).

    python -m braitenberg.evolve evolutions/forager.yaml --generations 5 --workers 8

Each vehicle is tried alone; a trial ends when its energy reaches 0, and how long
it lasted is all that selection looks at. The best are kept and copied with
small errors. This module must not import pygame; matplotlib is imported only to
write the plots.
"""

from __future__ import annotations

import argparse
import copy
import csv
import math
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

from braitenberg.definition import RESPONSE_FIELDS, VehicleDefinition, load_definition
from braitenberg.scenario import Placement, Scenario, SimulationSettings, check_fit
from braitenberg.sim import Simulation
from braitenberg.world import World, load_world
from braitenberg.yamlfile import ConfigError, Parser, read_yaml

# What a gene may set: section -> allowed keys. Sensors are reached through their response.
GENE_KEYS = {
    "units": ("threshold", "delay"),
    "actuators": ("gain", "base_speed", "max_speed"),
    "sensors": ("at", "width", "height"),
}


@dataclass
class Target:
    section: str   # units | actuators | sensors
    name: str      # the part's name
    key: str       # e.g. threshold; for sensors, a field of the response

    def __str__(self) -> str:
        middle = ".response" if self.section == "sensors" else ""
        return f"{self.section}.{self.name}{middle}.{self.key}"


@dataclass
class Gene:
    name: str
    targets: list[Target]
    min: float
    max: float
    sigma: float
    start: float   # the targets' value in the ancestor


@dataclass
class Trials:
    count: int
    duration: float
    dt: float = 0.05
    validation: int = 0


@dataclass
class Evolution:
    path: Path
    name: str
    ancestor: VehicleDefinition
    world: World
    population: int
    survivors: int
    generations: int
    trials: Trials
    genes: list[Gene]
    seed: int = 0
    rate: float = 0.3
    description: str = ""


@dataclass
class Start:
    position: tuple[float, float]
    heading: float  # radians
    seed: int       # simulation seed, for the vehicle's noise


@dataclass
class Member:
    """A vehicle of a generation."""

    genome: tuple[float, ...]
    parent: int | None = None   # rank in the previous generation
    survival: float = 0.0


@dataclass
class Result:
    evolution: Evolution
    generations: list[list[Member]] = field(default_factory=list)  # each ranked, best first
    validation: dict[str, float] = field(default_factory=dict)     # ancestor, best

    @property
    def best(self) -> Member:
        return self.generations[-1][0]


# --- loading ---

def load_evolution(path: str | Path) -> Evolution:
    path = Path(path).resolve()
    return _EvolutionParser(path).evolution(read_yaml(path))


def part(definition: VehicleDefinition, target: Target):
    """The object holding a target's value: a unit, an actuator or a sensor's response."""
    for p in getattr(definition, target.section):
        if p.name == target.name:
            return p.response if target.section == "sensors" else p
    raise KeyError(target.name)


class _EvolutionParser(Parser):
    def referenced(self, value, key: str, loader):
        try:
            return loader(self.relative_path(value, key))
        except ConfigError as e:
            raise self.error(key, f"in referenced file: {e}") from e

    def count(self, value, key: str, minimum: int) -> int:
        n = self.integer(value, key)
        if n < minimum:
            raise self.error(key, f"must be at least {minimum}")
        return n

    def evolution(self, data) -> Evolution:
        data = self.mapping(data, "", {"name", "ancestor", "world", "population", "survivors",
                                       "generations", "trials", "genes"},
                            {"description", "seed", "mutation"})
        ancestor = self.referenced(data["ancestor"], "ancestor", load_definition)
        world = self.referenced(data["world"], "world", load_world)
        center = (world.arena.width / 2, world.arena.height / 2)
        try:
            check_fit(Scenario("", world, [Placement(ancestor, center, 0.0, "")]),
                      lambda i: ("ancestor", "ancestor"))
        except ConfigError as e:
            raise ConfigError(f"{self.path}: {e}") from e
        population = self.count(data["population"], "population", 2)
        survivors = self.count(data["survivors"], "survivors", 1)
        if survivors >= population:
            raise self.error("survivors", "must be less than population")
        mutation = self.mapping(data.get("mutation", {}), "mutation", set(), {"rate"})
        rate = self.number(mutation.get("rate", 0.3), "mutation.rate")
        if not 0 <= rate <= 1:
            raise self.error("mutation.rate", "must be between 0 and 1")
        genes = [self.gene(body, key, ancestor)
                 for key, body in self.items(data["genes"], "genes", "gene")]
        if not genes:
            raise self.error("genes", "at least one gene is needed")
        seen: dict[str, str] = {}
        for (key, _), g in zip(self.items(data["genes"], "genes", "gene"), genes):
            if g.name in seen:
                raise self.error(f"{key}.name", f"'{g.name}' is already used by {seen[g.name]}")
            seen[g.name] = f"{key}.name"
        return Evolution(
            path=self.path,
            name=self.string(data["name"], "name"),
            description=self.string(data.get("description", ""), "description"),
            ancestor=ancestor,
            world=world,
            population=population,
            survivors=survivors,
            generations=self.count(data["generations"], "generations", 0),
            trials=self.trials(data["trials"]),
            genes=genes,
            seed=self.integer(data.get("seed", 0), "seed"),
            rate=rate,
        )

    def trials(self, data) -> Trials:
        data = self.mapping(data, "trials", {"count", "duration"}, {"dt", "validation"})
        return Trials(self.count(data["count"], "trials.count", 1),
                      self.number(data["duration"], "trials.duration", positive=True),
                      self.number(data.get("dt", 0.05), "trials.dt", positive=True),
                      self.count(data.get("validation", 0), "trials.validation", 0))

    def target(self, value, key: str, ancestor: VehicleDefinition) -> Target:
        text = self.string(value, key)
        bits = text.split(".")
        section = bits[0]
        if section == "sensors" and len(bits) == 4 and bits[2] == "response":
            bits = [bits[0], bits[1], bits[3]]
        elif section == "sensors" or len(bits) != 3:
            raise self.error(key, f"'{text}' must be units.<name>.<key>, actuators.<name>.<key> "
                                  "or sensors.<name>.response.<key>")
        if section not in GENE_KEYS:
            raise self.error(key, f"'{text}': only units, actuators and sensor responses "
                                  "can be genes")
        target = Target(*bits)
        if target.key not in GENE_KEYS[section]:
            raise self.error(key, f"'{text}': '{target.key}' cannot be a gene "
                                  f"(allowed: {', '.join(GENE_KEYS[section])})")
        try:
            holder = part(ancestor, target)
        except KeyError:
            raise self.error(key, f"'{text}': the ancestor has no {section[:-1]} "
                                  f"'{target.name}'") from None
        if section == "sensors":
            required, optional = RESPONSE_FIELDS[holder.type]
            if target.key not in required | set(optional):
                raise self.error(key, f"'{text}': a {holder.type} response has no '{target.key}'")
        return target

    def gene(self, data, key: str, ancestor: VehicleDefinition) -> Gene:
        data = self.mapping(data, key, {"name", "targets", "min", "max", "sigma"})
        name = self.string(data["name"], f"{key}.name")
        if not isinstance(data["targets"], list) or not data["targets"]:
            raise self.error(f"{key}.targets", "must be a non-empty list")
        targets = [self.target(t, f"{key}.targets[{i}]", ancestor)
                   for i, t in enumerate(data["targets"])]
        lo = self.number(data["min"], f"{key}.min")
        hi = self.number(data["max"], f"{key}.max")
        if not lo < hi:
            raise self.error(f"{key}.min", "must be less than max")
        sigma = self.number(data["sigma"], f"{key}.sigma", positive=True)
        values = [getattr(part(ancestor, t), t.key) for t in targets]
        if any(v != values[0] for v in values):
            raise self.error(f"{key}.targets", "must all start with the same value in the "
                                               "ancestor, but they are "
                             + ", ".join(f"{t} = {v:g}" for t, v in zip(targets, values)))
        if not lo <= values[0] <= hi:
            raise self.error(f"{key}.targets", f"start at {values[0]:g}, outside [{lo:g}, {hi:g}]")
        return Gene(name, targets, lo, hi, sigma, values[0])


# --- genomes and copying ---

def ancestor_genome(evolution: Evolution) -> tuple[float, ...]:
    return tuple(g.start for g in evolution.genes)


def apply_genome(evolution: Evolution, genome) -> VehicleDefinition:
    """A copy of the ancestor with each gene's targets set to the gene's value."""
    definition = copy.deepcopy(evolution.ancestor)
    for gene, value in zip(evolution.genes, genome):
        for t in gene.targets:
            setattr(part(definition, t), t.key, float(value))
    return definition


def copy_genome(genes: list[Gene], genome, rate: float, rng: np.random.Generator):
    """A copy with errors: each gene changes with probability `rate`, then is clipped."""
    result = []
    for gene, value in zip(genes, genome):
        if rng.random() < rate:
            value = min(max(value + rng.normal(0.0, gene.sigma), gene.min), gene.max)
        result.append(float(value))
    return tuple(result)


# --- trials ---

def draw_starts(world: World, n: int, rng: np.random.Generator, first_seed: int = 0) -> list[Start]:
    starts = []
    for k in range(n):
        x = rng.uniform(0, world.arena.width)
        y = rng.uniform(0, world.arena.height)
        heading = rng.uniform(0, 2 * math.pi)
        starts.append(Start((float(x), float(y)), float(heading), first_seed + k))
    return starts


def trial(definition: VehicleDefinition, world: World, start: Start,
          duration: float, dt: float) -> float:
    """Survival time: when the energy reached 0, or `duration` if it never did."""
    scenario = Scenario("trial", world, [Placement(definition, start.position, start.heading, "")],
                        SimulationSettings(dt, start.seed))
    sim = Simulation(scenario)
    v = sim.vehicles[0]
    for _ in range(max(1, round(duration / dt))):
        sim.step()
        if v.energy is not None and v.energy <= 0:
            return sim.time
    return duration


def _trial(args) -> float:
    return trial(*args)


class Evaluator:
    """Mean survival over a fixed set of starts, cached per genome, optionally in parallel."""

    def __init__(self, evolution: Evolution, starts: list[Start], pool=None):
        self.evolution = evolution
        self.starts = starts
        self.pool = pool
        self.cache: dict[tuple, float] = {}

    def __call__(self, genomes) -> list[float]:
        new = list(dict.fromkeys(g for g in genomes if g not in self.cache))
        t = self.evolution.trials
        tasks = [(apply_genome(self.evolution, g), self.evolution.world, s, t.duration, t.dt)
                 for g in new for s in self.starts]
        times = list(self.pool.map(_trial, tasks, chunksize=1)) if self.pool \
            else [_trial(task) for task in tasks]
        n = len(self.starts)
        for i, g in enumerate(new):
            self.cache[g] = float(np.mean(times[i * n:(i + 1) * n]))
        return [self.cache[g] for g in genomes]


def ranked(members: list[Member]) -> list[Member]:
    return sorted(members, key=lambda m: -m.survival)  # stable: ties keep their order


def evolve(evolution: Evolution, workers: int = 1, report=None) -> Result:
    """Run every generation and the validation trials; `report(g, members)` after each."""
    rng = np.random.default_rng(evolution.seed)
    t = evolution.trials
    starts = draw_starts(evolution.world, t.count, rng)
    validation = draw_starts(evolution.world, t.validation, rng, first_seed=t.count)
    pool = ProcessPoolExecutor(workers) if workers > 1 else None
    try:
        evaluate = Evaluator(evolution, starts, pool)
        result = Result(evolution)
        first = ancestor_genome(evolution)
        members = [Member(first)] + [Member(copy_genome(evolution.genes, first, evolution.rate, rng))
                                     for _ in range(evolution.population - 1)]
        for g in range(evolution.generations + 1):
            if g > 0:
                survivors = result.generations[-1][:evolution.survivors]
                members = [Member(m.genome, parent=r) for r, m in enumerate(survivors)]
                for i in range(evolution.population - evolution.survivors):
                    r = i % evolution.survivors
                    members.append(Member(copy_genome(evolution.genes, survivors[r].genome,
                                                      evolution.rate, rng), parent=r))
            for m, s in zip(members, evaluate([m.genome for m in members])):
                m.survival = s
            result.generations.append(ranked(members))
            if report:
                report(g, result.generations[-1])
        if validation:
            check = Evaluator(evolution, validation, pool)
            ancestor, best = check([first, result.best.genome])
            result.validation = {"ancestor": ancestor, "best": best}
    finally:
        if pool:
            pool.shutdown()
    return result


# --- results ---

class _FlowDumper(yaml.SafeDumper):
    """Writes short lists of numbers, such as positions, on one line."""


def _represent_list(dumper, data):
    flow = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in data)
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=flow)


_FlowDumper.add_representer(list, _represent_list)


def best_definition_data(result: Result, generation: int | None = None) -> dict:
    """The ancestor's file with the best genome applied, as YAML data."""
    evolution = result.evolution
    generation = len(result.generations) - 1 if generation is None else generation
    data = read_yaml(evolution.ancestor.path)
    general = data["general"]
    general["type"] = "6"
    general["name"] = f"{general['name']} (evolved)"
    general["description"] = (f"{evolution.ancestor.general.name} evolved by "
                              f"{evolution.path.name}, seed {evolution.seed}, "
                              f"generation {generation}.")
    for gene, value in zip(evolution.genes, result.generations[generation][0].genome):
        for t in gene.targets:
            for item in data[t.section]:
                body = item[t.section[:-1]]
                if body["name"] == t.name:
                    (body["response"] if t.section == "sensors" else body)[t.key] = float(value)
    return data


def write_results(result: Result, out: Path) -> None:
    evolution = result.evolution
    out.mkdir(parents=True, exist_ok=True)
    names = [g.name for g in evolution.genes]
    with open(out / "log.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["generation", "rank", "parent", "survival", *names])
        for g, members in enumerate(result.generations):
            for r, m in enumerate(members):
                w.writerow([g, r, "" if m.parent is None else m.parent, repr(m.survival),
                            *(repr(v) for v in m.genome)])
    (out / "best.yaml").write_text(yaml.dump(best_definition_data(result), Dumper=_FlowDumper,
                                             sort_keys=False, allow_unicode=True))
    first = ancestor_genome(evolution)
    ancestor_survival = next(m.survival for m in result.generations[0] if m.genome == first)
    summary = {
        "evolution": evolution.name,
        "file": evolution.path.name,
        "seed": evolution.seed,
        "generations": len(result.generations) - 1,
        "best_genome": dict(zip(names, result.best.genome)),
        "ancestor_genome": dict(zip(names, first)),
        "survival": {"ancestor": ancestor_survival, "best": result.best.survival},
    }
    if result.validation:
        summary["validation_survival"] = dict(result.validation)
    (out / "summary.yaml").write_text(yaml.dump(summary, Dumper=_FlowDumper, sort_keys=False))
    plot(result, ancestor_survival, out)


def plot(result: Result, ancestor_survival: float, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    evolution = result.evolution
    gens = range(len(result.generations))
    ink, muted, accent, grid = "#1f2328", "#6e7781", "#0969da", "#d8dee4"

    def style(ax):
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(muted)
        ax.tick_params(colors=muted, labelsize=8)
        ax.grid(axis="y", color=grid, linewidth=0.6)
        ax.set_axisbelow(True)

    fig, ax = plt.subplots(figsize=(7, 3.6))
    style(ax)
    best = [m[0].survival for m in result.generations]
    mean = [float(np.mean([x.survival for x in m])) for m in result.generations]
    ax.plot(gens, best, color=accent, linewidth=2, label="best")
    ax.plot(gens, mean, color=accent, linewidth=1, alpha=0.45, label="mean")
    ax.axhline(ancestor_survival, color=muted, linewidth=1, linestyle="--", label="ancestor")
    ax.set_xlabel("generation", color=ink, fontsize=9)
    ax.set_ylabel("survival (s)", color=ink, fontsize=9)
    ax.set_ylim(0, evolution.trials.duration * 1.02)
    ax.set_title(f"{evolution.name}: survival", color=ink, fontsize=10, loc="left")
    ax.legend(frameon=False, fontsize=8, labelcolor=ink)
    fig.tight_layout()
    fig.savefig(out / "survival.png", dpi=120)
    plt.close(fig)

    n = len(evolution.genes)
    cols = min(n, 4)
    rows = math.ceil(n / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(2.4 * cols, 1.9 * rows), squeeze=False,
                             sharex=True)
    for i, gene in enumerate(evolution.genes):
        ax = axes[i // cols][i % cols]
        style(ax)
        for g, members in enumerate(result.generations):
            values = [m.genome[i] for m in members[:evolution.survivors]]
            ax.scatter([g] * len(values), values, s=6, color=accent, alpha=0.35, linewidths=0)
        ax.plot(gens, [m[0].genome[i] for m in result.generations], color=accent, linewidth=1.4)
        ax.axhline(gene.start, color=muted, linewidth=0.8, linestyle="--")
        ax.set_ylim(gene.min, gene.max)
        ax.set_title(gene.name, color=ink, fontsize=9, loc="left")
    for j in range(n, rows * cols):
        axes[j // cols][j % cols].axis("off")
    fig.supxlabel("generation", color=ink, fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "genes.png", dpi=120)
    plt.close(fig)


# --- command line ---

def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m braitenberg.evolve",
        description="Tune a vehicle's numbers by selection (Vehicle 6).")
    parser.add_argument("evolution", help="evolution file")
    parser.add_argument("--generations", type=int, help="override generations")
    parser.add_argument("--seed", type=int, help="override seed")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1,
                        help="processes to run trials in (default: the number of CPUs)")
    parser.add_argument("--out", help="output folder (default: runs/<evolution file name>/)")
    args = parser.parse_args(argv)
    try:
        evolution = load_evolution(args.evolution)
    except ConfigError as e:
        raise SystemExit(f"error: {e}")
    if args.generations is not None:
        evolution.generations = args.generations
    if args.seed is not None:
        evolution.seed = args.seed
    out = Path(args.out) if args.out else Path("runs") / evolution.path.stem

    def report(g, members):
        genome = ", ".join(f"{gene.name} {v:.3g}" for gene, v in zip(evolution.genes, members[0].genome))
        mean = np.mean([m.survival for m in members])
        print(f"generation {g:3d}: best {members[0].survival:6.1f} s, mean {mean:6.1f} s | {genome}",
              flush=True)

    result = evolve(evolution, args.workers, report)
    if result.validation:
        print(f"validation: ancestor {result.validation['ancestor']:.1f} s, "
              f"best {result.validation['best']:.1f} s")
    write_results(result, out)
    print(f"results in {out}")


if __name__ == "__main__":
    main()
