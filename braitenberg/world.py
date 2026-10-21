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
class Schedule:
    """On during [on_at, off_at) of every period of simulated seconds; wraps when on_at > off_at."""

    period: float
    on_at: float
    off_at: float

    def active(self, time: float) -> bool:
        c = time % self.period
        if self.on_at < self.off_at:
            return self.on_at <= c < self.off_at
        return c >= self.on_at or c < self.off_at


@dataclass
class Source:
    position: tuple[float, float]
    intensity: float
    falloff: float
    schedule: Schedule | None = None
    radius: float | None = None   # a source with a radius is a thing cameras see (specs/camera.md)
    height: float | None = None   # of that thing, standing on the ground

    def active(self, time: float | None) -> bool:
        """Whether the source is on at `time`; with no time given, every source counts as on."""
        return self.schedule is None or time is None or self.schedule.active(time)


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

    def stimulus_at(self, name: str, x, y, time: float | None = None,
                    heading: float | None = None, field_of_view: float = 360.0):
        """Value of a stimulus at a point, or at arrays of points.

        `time` leaves out sources that are off at that time. A `field_of_view` below 360
        degrees (for a single point, with `heading` in radians) leaves out sources outside
        that cone around the heading.
        """
        total = 0.0
        for s in self.stimuli[name].sources:
            if not s.active(time):
                continue
            dx, dy = self.arena.delta(np.subtract(x, s.position[0]),
                                      np.subtract(y, s.position[1]))
            if field_of_view < 360 and not self.in_view(-dx, -dy, heading, field_of_view):
                continue
            total = total + s.intensity / (1 + (dx * dx + dy * dy) / (s.falloff * s.falloff))
        if np.ndim(total) == 0 and np.ndim(x) > 0:
            total = np.zeros(np.broadcast(x, y).shape)
        return total


    @staticmethod
    def in_view(dx: float, dy: float, heading: float, field_of_view: float) -> bool:
        """Whether direction (dx, dy) is within field_of_view / 2 degrees of heading."""
        if dx == 0 and dy == 0:
            return True
        off = (math.atan2(dy, dx) - heading + math.pi) % (2 * math.pi) - math.pi
        return abs(math.degrees(off)) <= field_of_view / 2

    def things(self, stimulus: str, time: float | None) -> list[tuple[float, float, float, float, float]]:
        """The things cameras can see, as (x, y, radius, height, brightness for `stimulus`).

        Sources with the same position, radius and height are one thing, lit in several stimuli.
        """
        things: dict[tuple, float] = {}
        for name, st in self.stimuli.items():
            for s in st.sources:
                if s.radius is None:
                    continue
                key = (*s.position, s.radius, s.height)
                lit = s.intensity if name == stimulus and s.active(time) else 0.0
                things[key] = things.get(key, 0.0) + lit
        return [(*key, brightness) for key, brightness in things.items()]

    def active_sources(self, time: float | None) -> tuple:
        """Which sources are on, stimulus by stimulus (to tell when the field changes)."""
        return tuple(s.active(time) for st in self.stimuli.values() for s in st.sources)


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

    def schedule(self, data, key: str) -> Schedule:
        # Not 'on'/'off': YAML reads those as booleans.
        data = self.mapping(data, key, {"period", "on_at", "off_at"})
        period = self.number(data["period"], f"{key}.period", positive=True)
        on_at, off_at = (self.number(data[k], f"{key}.{k}") for k in ("on_at", "off_at"))
        for k, v in (("on_at", on_at), ("off_at", off_at)):
            if not 0 <= v <= period:
                raise self.error(f"{key}.{k}", "must be between 0 and period")
        if on_at == off_at:
            raise self.error(f"{key}.off_at", "must differ from on_at")
        return Schedule(period, on_at, off_at)

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
                s = self.mapping(s, skey, {"position", "intensity", "falloff"},
                                 {"schedule", "radius", "height"})
                source = Source(self.point(s["position"], f"{skey}.position", arena),
                                self.number(s["intensity"], f"{skey}.intensity"),
                                self.number(s["falloff"], f"{skey}.falloff", positive=True),
                                self.schedule(s["schedule"], f"{skey}.schedule")
                                if "schedule" in s else None)
                if "radius" in s:
                    source.radius = self.number(s["radius"], f"{skey}.radius", positive=True)
                    source.height = (self.number(s["height"], f"{skey}.height", positive=True)
                                     if "height" in s else 2 * source.radius)
                elif "height" in s:
                    raise self.error(f"{skey}.height", "a height needs a radius")
                sources.append(source)
            stimuli[str(name)] = Stimulus(str(name), sources)
        return stimuli
