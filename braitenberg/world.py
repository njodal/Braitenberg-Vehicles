"""Worlds: the environment a simulation runs in, i.e. the arena and its stimuli.

Worlds are described in YAML files (see specs/worlds.md). Vehicles are placed in
a world by a scenario (specs/scenarios.md).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from braitenberg.yamlfile import Parser, read_yaml

EDGE_RULES = ("wrap", "bounce")


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
class World:
    name: str
    arena: Arena
    stimuli: dict[str, Stimulus]
    description: str = ""
    path: Path | None = None

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
    path = Path(path).resolve()
    return _WorldParser(path).world(read_yaml(path))


class _WorldParser(Parser):
    def point(self, value, key: str, arena: Arena) -> tuple[float, float]:
        x, y = self.pair(value, key)
        if not arena.contains(x, y):
            raise self.error(key, f"[{x:g}, {y:g}] is outside the arena")
        return x, y

    def world(self, data) -> World:
        data = self.mapping(data, "", {"name", "arena", "stimuli"}, {"description"})
        arena = self.arena(data["arena"])
        return World(
            name=self.string(data["name"], "name"),
            description=self.string(data.get("description", ""), "description"),
            arena=arena,
            stimuli=self.stimuli(data["stimuli"], arena),
            path=self.path,
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
            body = self.mapping(body, key, {"sources"})
            if not isinstance(body["sources"], list):
                raise self.error(f"{key}.sources", "must be a list")
            sources = []
            for i, s in enumerate(body["sources"]):
                skey = f"{key}.sources[{i}]"
                s = self.mapping(s, skey, {"position", "intensity", "falloff"})
                sources.append(Source(self.point(s["position"], f"{skey}.position", arena),
                                      self.number(s["intensity"], f"{skey}.intensity"),
                                      self.number(s["falloff"], f"{skey}.falloff", positive=True)))
            stimuli[str(name)] = Stimulus(str(name), sources)
        return stimuli
