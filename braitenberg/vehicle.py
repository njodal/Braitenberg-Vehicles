"""A vehicle built from a definition file (specs/vehicle-definition.md).

Vehicles know nothing about the world: the simulation reads the stimulus at each
sensor, hands the readings to the vehicle and applies the arena's edge rule
after the vehicle moves.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from braitenberg.definition import VehicleDefinition


@dataclass
class Part:
    """A sensor, actuator or unit, in body coordinates (+y forward, [-1, 1])."""

    kind: str     # sensor | motor | unit
    name: str
    position: tuple[float, float]
    label: str
    value: float
    level: float  # activity in [0, 1]


@dataclass
class Wire:
    source: str   # Part names
    target: str
    sign: int     # +1 excitatory, -1 inhibitory
    level: float
    active: bool = True  # connections with strength 0.7 or less carry no signal


@dataclass
class Diagram:
    """A vehicle's structure and live signals, for the diagram panel (specs/vehicle-diagram.md)."""

    title: str
    subtitle: str
    parts: list[Part]
    wires: list[Wire]
    params: dict[str, str]


def clamp01(x: float) -> float:
    return min(max(x, 0.0), 1.0)


class Vehicle:
    def __init__(self, definition: VehicleDefinition, x: float, y: float, heading: float,
                 label: str = ""):
        self.definition = definition
        self.label = label or definition.general.name
        self.x = x
        self.y = y
        self.heading = heading  # radians, 0 = +x, counterclockwise; body +y points this way
        self.half_size = definition.general.size / 2
        self.sensor_readings = {s.name: 0.0 for s in definition.sensors}  # stimulus at the sensor
        self.sensor_values = {s.name: 0.0 for s in definition.sensors}    # output after response
        self.unit_outputs = {u.name: 0.0 for u in definition.units}
        self.motor_speeds = {a.name: 0.0 for a in definition.actuators}
        self.speed = 0.0        # forward speed
        self.turn_rate = 0.0

    # --- geometry ---

    def body_to_world(self, bx: float, by: float) -> tuple[float, float]:
        """A point in body coordinates (+x right, +y forward) to arena coordinates."""
        c, s = math.cos(self.heading), math.sin(self.heading)
        # forward = (c, s), right = (s, -c)
        return (self.x + self.half_size * (by * c + bx * s),
                self.y + self.half_size * (by * s - bx * c))

    def sensor_points(self) -> list[tuple[str, str, float, float]]:
        """(sensor name, stimulus, x, y) for every sensor."""
        return [(s.name, s.type, *self.body_to_world(*s.position)) for s in self.definition.sensors]

    # --- signals ---

    def think(self, readings: dict[str, float]) -> None:
        """Update units and motors from this step's sensor readings (see 'Signal flow')."""
        self.sensor_readings = dict(readings)
        self.sensor_values = {s.name: s.response.output(readings[s.name])
                              for s in self.definition.sensors}
        previous = self.unit_outputs
        current = {}
        for u in self.definition.units:
            total = sum(c.sign * self.sensor_values.get(c.source, previous.get(c.source, 0.0))
                        for c in u.inputs if c.active)
            current[u.name] = 1.0 if total >= u.threshold else 0.0
        self.unit_outputs = current
        for a in self.definition.actuators:
            total = sum(c.sign * self.signal(c.source) for c in a.inputs if c.active)
            self.motor_speeds[a.name] = min(max(a.base_speed + a.gain * total, 0.0), a.max_speed)

    def signal(self, name: str) -> float:
        if name in self.sensor_values:
            return self.sensor_values[name]
        return self.unit_outputs[name]

    # --- movement ---

    def move(self, dt: float, rng: np.random.Generator) -> None:
        actuators = self.definition.actuators
        speeds = [self.motor_speeds[a.name] for a in actuators]
        xs = [a.position[0] * self.half_size for a in actuators]
        self.speed = sum(speeds) / len(speeds)
        sxx = sum(x * x for x in xs)
        self.turn_rate = sum(s * x for s, x in zip(speeds, xs)) / sxx if sxx > 0 else 0.0
        noise_std = self.definition.general.noise_std
        noise = noise_std * math.sqrt(dt) * rng.standard_normal() if noise_std else 0.0
        self.heading += self.turn_rate * dt + noise
        self.x += self.speed * math.cos(self.heading) * dt
        self.y += self.speed * math.sin(self.heading) * dt

    def step(self, readings: dict[str, float], dt: float, rng: np.random.Generator) -> None:
        self.think(readings)
        self.move(dt, rng)

    # --- diagram ---

    def diagram(self) -> Diagram:
        d = self.definition
        levels: dict[str, float] = {}
        parts = []
        for s in d.sensors:
            value = self.sensor_values[s.name]
            if s.response.type != "linear":
                ref = s.response.height  # nonlinear responses top out at their height
            else:
                ref = self.sensor_reference(s.name)
            levels[s.name] = clamp01(value / ref) if ref > 0 else (1.0 if value > 0 else 0.0)
            parts.append(Part("sensor", s.name, s.position, s.type, value, levels[s.name]))
        for u, position in zip(d.units, self.unit_layout()):
            value = self.unit_outputs[u.name]
            levels[u.name] = value
            parts.append(Part("unit", u.name, position, f"t={u.threshold:g}", value, value))
        for a in d.actuators:
            value = self.motor_speeds[a.name]
            level = clamp01(value / a.max_speed) if a.max_speed > 0 else 0.0
            parts.append(Part(a.type, a.name, a.position, a.type, value, level))
        wires = [Wire(c.source, target.name, c.sign, levels[c.source] if c.active else 0.0, c.active)
                 for target in [*d.units, *d.actuators] for c in target.inputs]
        return Diagram(
            title=self.label,
            subtitle=f"Vehicle {d.general.type}: {d.general.name}",
            parts=parts,
            wires=wires,
            params={"size": f"{d.general.size:g}", "noise_std": f"{d.general.noise_std:g}",
                    "speed": f"{self.speed:.2f}", "turn rate": f"{self.turn_rate:.2f}"},
        )

    def sensor_reference(self, name: str) -> float:
        """Reading at which the sensor's strongest excitatory target saturates or fires."""
        refs = []
        for a in self.definition.actuators:
            for c in a.inputs:
                if c.source == name and c.active and c.sign > 0 and a.gain > 0:
                    refs.append((a.max_speed - a.base_speed) / a.gain)
        for u in self.definition.units:
            for c in u.inputs:
                if c.source == name and c.active and c.sign > 0 and u.threshold > 0:
                    refs.append(u.threshold)
        return min(refs) if refs else 1.0

    def unit_layout(self) -> list[tuple[float, float]]:
        """Diagram positions of units: their own, or spread across the middle of the body."""
        units = self.definition.units
        n = len(units)
        return [u.position if u.position is not None
                else (-0.6 + 1.2 * (i + 0.5) / n, 0.0)
                for i, u in enumerate(units)]
