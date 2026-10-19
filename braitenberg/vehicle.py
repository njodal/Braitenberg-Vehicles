"""Vehicle bodies, sensors and motors.

Vehicles know nothing about the world: the simulation reads the stimulus at the
sensor, hands the value to the vehicle and applies the arena's edge rule after
the vehicle moves.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


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


# Vehicle types that world files may name in `vehicles[].type`.
VEHICLE_TYPES = {
    "vehicle1": Vehicle1,
}
