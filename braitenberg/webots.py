"""Run a vehicle definition on Webots' e-puck (specs/webots.md).

This module does not import Webots: the controller in webots/controllers/braitenberg/
creates the robot and hands it to `run`, so the adapter can be tested with a stand-in.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from braitenberg.definition import VehicleDefinition, load_definition
from braitenberg.vehicle import Vehicle
from braitenberg.yamlfile import ConfigError

REPO = Path(__file__).resolve().parent.parent
# The e-puck's light sensors: their angle from the front, + to the right, in degrees,
# from their positions in Webots' e-puck model.
LIGHT_SENSORS = {"ls0": 18.4, "ls1": 48.7, "ls2": 90.0, "ls3": 153.4,
                 "ls4": -153.4, "ls5": -90.0, "ls6": -48.7, "ls7": -18.4}
DARK = 4095.0   # a light sensor's raw value in the dark; 0 in full light
WHEELS = ("left wheel motor", "right wheel motor")
LIGHT_SCALE = 10.0
MAX_WHEEL_SPEED = 6.28   # rad/s, the e-puck's top speed


def angle_difference(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


class EpuckBrain:
    """A vehicle's network with the e-puck's sensors and wheels as its body."""

    def __init__(self, definition: VehicleDefinition, dt: float, light_scale: float = LIGHT_SCALE,
                 max_wheel_speed: float = MAX_WHEEL_SPEED):
        self.definition = definition
        self.light_scale = light_scale
        self.max_wheel_speed = max_wheel_speed
        self.devices = self.map_sensors(definition)   # definition sensor -> e-puck light sensor
        self.left, self.right = self.map_motors(definition)
        self.top_speed = max(self.left.max_speed, self.right.max_speed)
        self.vehicle = Vehicle(definition, 0.0, 0.0, 0.0, dt=dt)

    @staticmethod
    def map_sensors(definition: VehicleDefinition) -> dict[str, str]:
        g = definition.general
        devices = {}
        for s in definition.sensors:
            if s.type != "light" or s.camera:
                kind = "camera" if s.camera else f"'{s.type}' sensor"
                raise ConfigError(f"{definition.path}: sensor {s.name}: the e-puck has no {kind}; "
                                  "only light sensors can run on it")
            x, y = s.position
            angle = math.degrees(math.atan2(x * g.width, y * g.length))
            devices[s.name] = min(LIGHT_SENSORS, key=lambda d: angle_difference(LIGHT_SENSORS[d], angle))
        return devices

    @staticmethod
    def map_motors(definition: VehicleDefinition):
        motors = definition.actuators
        left = [a for a in motors if a.position[0] < 0]
        right = [a for a in motors if a.position[0] > 0]
        if len(motors) != 2 or len(left) != 1 or len(right) != 1:
            raise ConfigError(f"{definition.path}: actuators: the e-puck needs two motors, "
                              "one on each side of the body")
        return left[0], right[0]

    def reading(self, raw: float) -> float:
        return self.light_scale * (1.0 - min(max(raw, 0.0), DARK) / DARK)

    def step(self, raw: dict[str, float]) -> tuple[float, float]:
        """From the light sensors' raw values, by device name, to the wheel speeds (rad/s)."""
        self.vehicle.think({name: self.reading(raw[device]) for name, device in self.devices.items()})
        speeds = self.vehicle.motor_speeds
        scale = self.max_wheel_speed / self.top_speed if self.top_speed > 0 else 0.0
        return speeds[self.left.name] * scale, speeds[self.right.name] * scale


def run(robot, definition: VehicleDefinition, light_scale: float = LIGHT_SCALE,
        max_wheel_speed: float = MAX_WHEEL_SPEED) -> None:
    """Drive a Webots robot (an e-puck) with a vehicle definition until the simulation ends."""
    timestep = int(robot.getBasicTimeStep())
    brain = EpuckBrain(definition, timestep / 1000.0, light_scale, max_wheel_speed)
    sensors = {name: robot.getDevice(name) for name in sorted(set(brain.devices.values()))}
    for sensor in sensors.values():
        sensor.enable(timestep)
    wheels = [robot.getDevice(name) for name in WHEELS]
    for wheel in wheels:
        wheel.setPosition(float("inf"))   # velocity control
        wheel.setVelocity(0.0)
    while robot.step(timestep) != -1:
        speeds = brain.step({name: sensor.getValue() for name, sensor in sensors.items()})
        for wheel, speed in zip(wheels, speeds):
            wheel.setVelocity(speed)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run a vehicle definition on Webots' e-puck.")
    parser.add_argument("definition", help="vehicle definition, relative to the repo root")
    parser.add_argument("--light-scale", type=float, default=LIGHT_SCALE,
                        help="the reading in full light (default: %(default)s)")
    parser.add_argument("--max-wheel-speed", type=float, default=MAX_WHEEL_SPEED,
                        help="wheel speed, in rad/s, at a motor's top speed (default: %(default)s)")
    return parser.parse_args(argv)


def main(robot, argv=None) -> None:
    args = parse_args(argv)
    run(robot, load_definition(REPO / args.definition), args.light_scale, args.max_wheel_speed)
