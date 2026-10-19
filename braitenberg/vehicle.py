"""Vehicle bodies, sensors and motors.

Vehicles know nothing about the world: the simulation reads the stimulus at the
sensor, hands the value to the vehicle and applies the arena's edge rule after
the vehicle moves.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass

import numpy as np


@dataclass
class Part:
    """A sensor, motor or other component, in body coordinates (+y forward, [-1, 1])."""

    kind: str
    name: str
    position: tuple[float, float]
    label: str
    value: float
    level: float  # activity in [0, 1]


@dataclass
class Wire:
    source: str  # Part names
    target: str
    sign: int    # +1 excitatory, -1 inhibitory
    level: float


@dataclass
class Diagram:
    """A vehicle's structure and live signals, for the diagram panel (specs/vehicle-diagram.md)."""

    parts: list[Part]
    wires: list[Wire]
    params: dict[str, float]


def clamp01(x: float) -> float:
    return min(max(x, 0.0), 1.0)


@dataclass
class Vehicle1Params:
    """Tunable values of Vehicle 1 (see specs/vehicle-01.md)."""

    gain: float = 1.0
    base_speed: float = 0.0
    max_speed: float = 5.0
    noise_std: float = 0.3


class Vehicle1:
    """One sensor wired directly to one motor: the more stimulus, the faster."""

    params_type = Vehicle1Params

    def __init__(self, x: float, y: float, heading: float, sensor: str,
                 params: Vehicle1Params | None = None):
        self.x = x
        self.y = y
        self.heading = heading  # radians, 0 = +x, counterclockwise
        self.sensor = sensor    # name of the stimulus the sensor reads
        self.params = params or Vehicle1Params()
        self.sensor_value = 0.0
        self.speed = 0.0

    def sensor_position(self) -> tuple[float, float]:
        # The body is a point, so the sensor at its front reads at the body position.
        return self.x, self.y

    def motor_speed(self, sensor_value: float) -> float:
        p = self.params
        return min(p.base_speed + p.gain * sensor_value, p.max_speed)

    def step(self, sensor_value: float, dt: float, rng: np.random.Generator) -> None:
        self.sensor_value = sensor_value
        self.speed = self.motor_speed(sensor_value)
        if self.params.noise_std:
            self.heading += self.params.noise_std * math.sqrt(dt) * rng.standard_normal()
        self.x += self.speed * math.cos(self.heading) * dt
        self.y += self.speed * math.sin(self.heading) * dt

    def diagram(self) -> Diagram:
        p = self.params
        saturation = (p.max_speed - p.base_speed) / p.gain if p.gain > 0 else math.inf
        sensor_level = clamp01(self.sensor_value / saturation) if saturation > 0 else 1.0
        motor_level = clamp01(self.speed / p.max_speed) if p.max_speed > 0 else 0.0
        return Diagram(
            parts=[
                Part("sensor", "sensor", (0.0, 0.8), self.sensor, self.sensor_value, sensor_level),
                Part("motor", "motor", (0.0, -0.8), "speed", self.speed, motor_level),
            ],
            wires=[Wire("sensor", "motor", +1, sensor_level)],
            params=dataclasses.asdict(p),
        )


# Vehicle types that world files may name in `vehicles[].type`.
VEHICLE_TYPES = {
    "vehicle1": Vehicle1,
}
