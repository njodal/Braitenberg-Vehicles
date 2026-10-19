"""Worlds: arena, stimuli, vehicle placements and simulation settings.

Worlds are described in YAML files (see specs/worlds.md). `load_world` parses
and validates a file into the dataclasses below, applying defaults, so the rest
of the code never reads raw dictionaries.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from braitenberg.vehicle import VEHICLE_TYPES

EDGE_RULES = ("wrap", "bounce")


class WorldError(ValueError):
    """A world file is missing, malformed or inconsistent."""


@dataclass
class Arena:
    width: float
    height: float
    edges: str = "wrap"

    def contains(self, x: float, y: float) -> bool:
        return 0 <= x <= self.width and 0 <= y <= self.height

    def delta(self, dx, dy):
        """Displacement between two points, the shortest way around when wrapping."""
        if self.edges == "wrap":
            dx = (dx + self.width / 2) % self.width - self.width / 2
            dy = (dy + self.height / 2) % self.height - self.height / 2
        return dx, dy

    def apply_edges(self, vehicle) -> None:
        """Bring a vehicle that moved past an edge back into the arena."""
        if self.edges == "wrap":
            vehicle.x %= self.width
            vehicle.y %= self.height
            return
        if vehicle.x < 0 or vehicle.x > self.width:
            vehicle.x = -vehicle.x if vehicle.x < 0 else 2 * self.width - vehicle.x
            vehicle.heading = math.pi - vehicle.heading
        if vehicle.y < 0 or vehicle.y > self.height:
            vehicle.y = -vehicle.y if vehicle.y < 0 else 2 * self.height - vehicle.y
            vehicle.heading = -vehicle.heading


@dataclass
class Source:
    position: tuple[float, float]
    intensity: float
    falloff: float


@dataclass
class Stimulus:
    name: str
    sources: list[Source] = field(default_factory=list)


@dataclass
class VehiclePlacement:
    type: str
    position: tuple[float, float]
    heading: float  # radians (the file uses degrees)
    sensor: str
    params: Any     # the vehicle type's params dataclass


@dataclass
class SimulationSettings:
    dt: float = 0.05
    seed: int = 0


@dataclass
class World:
    name: str
    arena: Arena
    stimuli: dict[str, Stimulus]
    vehicles: list[VehiclePlacement]
    simulation: SimulationSettings = field(default_factory=SimulationSettings)
    description: str = ""

    def stimulus_at(self, name: str, x, y):
        """Value of a stimulus at a point, or at arrays of points."""
        total = 0.0
        for s in self.stimuli[name].sources:
            dx, dy = self.arena.delta(np.subtract(x, s.position[0]),
                                      np.subtract(y, s.position[1]))
            total = total + s.intensity / (1 + (dx * dx + dy * dy) / (s.falloff * s.falloff))
        if np.ndim(total) == 0 and np.ndim(x) > 0:
            total = np.zeros(np.broadcast(x, y).shape)
        return total


def load_world(path: str | Path) -> World:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text())
    except OSError as e:
        raise WorldError(f"{path}: cannot read file: {e.strerror}") from e
    except yaml.YAMLError as e:
        raise WorldError(f"{path}: invalid YAML: {e}") from e
    return _Parser(path).world(data)


class _Parser:
    def __init__(self, path: Path):
        self.path = path

    def error(self, key: str, message: str) -> WorldError:
        return WorldError(f"{self.path}: {key}: {message}")

    def mapping(self, value, key: str, required: set[str], optional: set[str]) -> dict:
        if not isinstance(value, dict):
            raise self.error(key or "(top level)", "must be a mapping")
        prefix = f"{key}." if key else ""
        for k in value:
            if k not in required | optional:
                raise self.error(prefix + str(k), "unknown key")
        for k in sorted(required):
            if k not in value:
                raise self.error(prefix + k, "missing required key")
        return value

    def number(self, value, key: str, positive: bool = False) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise self.error(key, "must be a number")
        if positive and value <= 0:
            raise self.error(key, "must be positive")
        return float(value)

    def string(self, value, key: str) -> str:
        if not isinstance(value, str):
            raise self.error(key, "must be a string")
        return value

    def point(self, value, key: str, arena: Arena) -> tuple[float, float]:
        if not isinstance(value, list) or len(value) != 2:
            raise self.error(key, "must be a list [x, y]")
        x, y = (self.number(v, key) for v in value)
        if not arena.contains(x, y):
            raise self.error(key, f"[{x:g}, {y:g}] is outside the arena")
        return x, y

    def world(self, data) -> World:
        data = self.mapping(data, "", {"name", "arena", "stimuli", "vehicles"},
                            {"description", "simulation"})
        arena = self.arena(data["arena"])
        stimuli = self.stimuli(data["stimuli"], arena)
        return World(
            name=self.string(data["name"], "name"),
            description=self.string(data.get("description", ""), "description"),
            arena=arena,
            stimuli=stimuli,
            vehicles=self.vehicles(data["vehicles"], arena, stimuli),
            simulation=self.simulation(data.get("simulation", {})),
        )

    def arena(self, data) -> Arena:
        data = self.mapping(data, "arena", {"width", "height"}, {"edges"})
        edges = self.string(data.get("edges", "wrap"), "arena.edges")
        if edges not in EDGE_RULES:
            raise self.error("arena.edges", f"must be one of {', '.join(EDGE_RULES)}")
        return Arena(self.number(data["width"], "arena.width", positive=True),
                     self.number(data["height"], "arena.height", positive=True),
                     edges)

    def stimuli(self, data, arena: Arena) -> dict[str, Stimulus]:
        if not isinstance(data, dict):
            raise self.error("stimuli", "must be a mapping")
        stimuli = {}
        for name, body in data.items():
            key = f"stimuli.{name}"
            body = self.mapping(body, key, {"sources"}, set())
            if not isinstance(body["sources"], list):
                raise self.error(f"{key}.sources", "must be a list")
            sources = []
            for i, s in enumerate(body["sources"]):
                skey = f"{key}.sources[{i}]"
                s = self.mapping(s, skey, {"position", "intensity", "falloff"}, set())
                sources.append(Source(self.point(s["position"], f"{skey}.position", arena),
                                      self.number(s["intensity"], f"{skey}.intensity"),
                                      self.number(s["falloff"], f"{skey}.falloff", positive=True)))
            stimuli[str(name)] = Stimulus(str(name), sources)
        return stimuli

    def vehicles(self, data, arena: Arena, stimuli: dict[str, Stimulus]) -> list[VehiclePlacement]:
        if not isinstance(data, list):
            raise self.error("vehicles", "must be a list")
        placements = []
        for i, v in enumerate(data):
            key = f"vehicles[{i}]"
            v = self.mapping(v, key, {"type", "position", "heading", "sensor"}, {"params"})
            vtype = self.string(v["type"], f"{key}.type")
            if vtype not in VEHICLE_TYPES:
                raise self.error(f"{key}.type", f"unknown vehicle type '{vtype}'")
            sensor = self.string(v["sensor"], f"{key}.sensor")
            if sensor not in stimuli:
                raise self.error(f"{key}.sensor", f"stimulus '{sensor}' is not defined in stimuli")
            placements.append(VehiclePlacement(
                type=vtype,
                position=self.point(v["position"], f"{key}.position", arena),
                heading=math.radians(self.number(v["heading"], f"{key}.heading")),
                sensor=sensor,
                params=self.params(v.get("params", {}), f"{key}.params",
                                   VEHICLE_TYPES[vtype].params_type),
            ))
        return placements

    def params(self, data, key: str, params_type):
        names = {f.name for f in dataclasses.fields(params_type)}
        data = self.mapping(data, key, set(), names)
        return params_type(**{k: self.number(v, f"{key}.{k}") for k, v in data.items()})

    def simulation(self, data) -> SimulationSettings:
        data = self.mapping(data, "simulation", set(), {"dt", "seed"})
        settings = SimulationSettings()
        if "dt" in data:
            settings.dt = self.number(data["dt"], "simulation.dt", positive=True)
        if "seed" in data:
            seed = data["seed"]
            if isinstance(seed, bool) or not isinstance(seed, int):
                raise self.error("simulation.seed", "must be an integer")
            settings.seed = seed
        return settings
