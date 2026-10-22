"""Acceptance criteria of specs/webots.md, with a stand-in for Webots' e-puck."""

import math
import re

import pytest

from braitenberg.definition import load_definition
from braitenberg.webots import DARK, LIGHT_SENSORS, WHEELS, EpuckBrain, run
from braitenberg.yamlfile import ConfigError
from conftest import (DRIVER, FORAGER, REPO, VEHICLE1, VEHICLE2A, VEHICLE2B, read, run_python)

WHEEL_RADIUS = 0.0205   # m
AXLE = 0.052            # m, between the wheels
SENSOR_RADIUS = 0.032   # m, from the center to a light sensor
SENSOR_HEIGHT = 0.033


class Sensor:
    def __init__(self):
        self.value = DARK
        self.period = None

    def enable(self, period):
        self.period = period

    def getValue(self):
        return self.value


class Wheel:
    def __init__(self):
        self.position = None
        self.velocity = None

    def setPosition(self, position):
        self.position = position

    def setVelocity(self, velocity):
        self.velocity = velocity


class Epuck:
    """A model e-puck: Webots' light sensor (4095 at irradiance 1, 0 at 2, cosine of the angle
    to the light) under one PointLight with attenuation 1 0 1, and differential drive.
    Webots axes: x forward at heading 0, y to the left."""

    def __init__(self, x, y, heading, lamp=None, intensity=3.0, steps=0, timestep=32):
        self.x, self.y, self.heading = x, y, heading
        self.lamp, self.intensity = lamp, intensity
        self.steps, self.timestep = steps, timestep
        self.devices = {name: Sensor() for name in LIGHT_SENSORS}
        self.devices.update({name: Wheel() for name in WHEELS})

    def getBasicTimeStep(self):
        return float(self.timestep)

    def getDevice(self, name):
        return self.devices[name]

    def irradiance(self, angle):
        """At the light sensor `angle` degrees right of the front."""
        a = self.heading - math.radians(angle)
        sx, sy = self.x + SENSOR_RADIUS * math.cos(a), self.y + SENSOR_RADIUS * math.sin(a)
        lx, ly, lz = self.lamp
        dx, dy, dz = lx - sx, ly - sy, lz - SENSOR_HEIGHT
        d = math.sqrt(dx * dx + dy * dy + dz * dz)
        cosine = max((dx * math.cos(a) + dy * math.sin(a)) / d, 0.0)
        return self.intensity * cosine / (1 + d * d)

    def step(self, timestep):
        if self.steps <= 0:
            return -1
        self.steps -= 1
        dt = timestep / 1000
        left, right = (self.devices[name].velocity for name in WHEELS)
        speed = WHEEL_RADIUS * (left + right) / 2
        self.heading += WHEEL_RADIUS * (right - left) / AXLE * dt
        self.x += speed * math.cos(self.heading) * dt
        self.y += speed * math.sin(self.heading) * dt
        if self.lamp:
            for name, angle in LIGHT_SENSORS.items():
                raw = DARK * (2 - self.irradiance(angle))
                self.devices[name].value = min(max(raw, 0.0), DARK)
        return 0


def brain(path, dt=0.032, **kwargs):
    return EpuckBrain(load_definition(path), dt, **kwargs)


def dark(**raw):
    return {name: raw.get(name, DARK) for name in LIGHT_SENSORS}


def test_light_sensor_angles_match_the_model():
    """The adapter's table is the model's: angles of the sensor positions in E-puck.proto."""
    positions = {"ls0": (0.03, -0.01), "ls1": (0.022, -0.025), "ls2": (0, -0.031),
                 "ls3": (-0.03, -0.015), "ls4": (-0.03, 0.015), "ls5": (0, 0.031),
                 "ls6": (0.022, 0.025), "ls7": (0.03, 0.01)}
    for name, (x, y) in positions.items():
        assert LIGHT_SENSORS[name] == pytest.approx(math.degrees(math.atan2(-y, x)), abs=0.1)


# 1. Sensor mapping
def test_eyes_read_the_nearest_sensors(write):
    assert brain(VEHICLE2B).devices == {"left_eye": "ls6", "right_eye": "ls1"}
    data = read(VEHICLE2B)
    data["sensors"][0]["sensor"]["position"] = [0, 1]
    data["sensors"][1]["sensor"]["position"] = [1, 0]
    devices = brain(write(data)).devices
    assert devices["left_eye"] in ("ls0", "ls7")
    assert devices["right_eye"] == "ls2"


# 2. Light readings
def test_raw_values_become_readings():
    b = brain(VEHICLE2B, light_scale=8)
    assert b.reading(DARK) == 0
    assert b.reading(0) == 8
    assert b.reading(DARK / 4) == pytest.approx(6)
    assert b.reading(DARK * 2) == 0   # clamped


# 3. Motors
def test_wheel_speeds_scale_motor_speeds():
    b = brain(VEHICLE2B, max_wheel_speed=5)
    left, right = b.step(dark(ls1=DARK / 2))   # right eye reads 5 of 10
    assert left == pytest.approx(5 * 5 / 10)    # crossed: the right eye drives the left motor
    assert right == 0
    left, right = b.step(dark(ls1=0, ls6=0))
    assert left == right == pytest.approx(5)    # a motor at its top speed


def test_more_light_on_the_right_makes_aggression_turn_right():
    left, right = brain(VEHICLE2B).step(dark(ls1=1000, ls6=3000))
    assert left > right


def test_left_motor_drives_the_left_wheel(write):
    data = read(VEHICLE2B)
    data["actuators"].reverse()   # the order in the file does not matter
    left, right = brain(write(data)).step(dark(ls1=1000, ls6=3000))
    assert left > right


# 4. Time
def test_dt_is_the_basic_time_step():
    robot = Epuck(0, 0, 0, steps=0, timestep=16)
    b = brain(VEHICLE2B, dt=robot.getBasicTimeStep() / 1000)
    assert b.vehicle.dt == 0.016


# 5. Unsupported vehicles
@pytest.mark.parametrize("path", [VEHICLE1, DRIVER, FORAGER, REPO / "vehicles" / "vehicle8-hunter.yaml"])
def test_vehicles_without_light_sensors_only_are_rejected(path):
    with pytest.raises(ConfigError, match="only light sensors"):
        brain(path)


def test_vehicles_need_one_motor_on_each_side(write):
    data = read(VEHICLE2B)
    data["actuators"][1]["actuator"]["position"] = [-0.5, -0.6]
    with pytest.raises(ConfigError, match="one on each side"):
        brain(write(data))


# 6. Controller loop
def test_run_enables_sensors_and_drives_wheels():
    robot = Epuck(0, 0, 0, lamp=(0.3, 0.0, 0.1), steps=5)
    run(robot, load_definition(VEHICLE2B))
    assert robot.devices["ls1"].period == robot.devices["ls6"].period == 32
    assert robot.devices["ls0"].period is None   # not used by the vehicle
    for name in WHEELS:
        assert robot.devices[name].position == math.inf
        assert robot.devices[name].velocity > 0
    assert robot.steps == 0


# 7. Headless
def test_adapter_imports_neither_pygame_nor_webots():
    result = run_python("import sys, braitenberg.webots; "
                        "print('pygame' in sys.modules, 'controller' in sys.modules)")
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["False", "False"]


# 8. Behavior
def drive(path, y):
    """Run a definition on a model e-puck 60 cm from a lamp, as in the test world."""
    lamp = (0.3, 0.0, 0.05)
    robot = Epuck(-0.3, y, 0, lamp=lamp, steps=900)
    run(robot, load_definition(path))
    dx, dy = lamp[0] - robot.x, lamp[1] - robot.y
    bearing = math.degrees(math.atan2(dy, dx) - robot.heading)
    return math.hypot(dx, dy), abs((bearing + 180) % 360 - 180)


def test_aggression_drives_up_to_the_lamp():
    distance, bearing = drive(VEHICLE2B, -0.12)
    assert distance < 0.15
    assert bearing < 30


def test_fear_turns_its_back_on_the_lamp():
    distance, bearing = drive(VEHICLE2A, 0.12)
    assert distance > 0.55
    assert bearing > 90


# 9. World file
def test_world_robots_run_accepted_definitions():
    worlds = sorted((REPO / "webots" / "worlds").glob("*.wbt"))
    assert worlds
    for world in worlds:
        text = world.read_text()
        robots = re.findall(r"E-puck \{(.*?)\n\}", text, re.S)
        assert robots, world
        for robot in robots:
            assert 'controller "braitenberg"' in robot
            definition = re.search(r'controllerArgs \[\s*"([^"]+)"', robot).group(1)
            brain(REPO / definition)
