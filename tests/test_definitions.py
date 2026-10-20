"""Acceptance criteria of specs/vehicle-definition.md."""

import math

import numpy as np
import pytest

from braitenberg.definition import Connection, load_definition
from braitenberg.scenario import load_scenario
from braitenberg.sim import Simulation
from braitenberg.vehicle import Vehicle
from braitenberg.yamlfile import ConfigError
from conftest import (FEAR_AND_AGGRESSION, VEHICLE1, VEHICLE1_SCENARIO, VEHICLE2B, read,
                      run_python)


def vehicle_from(data, write, name="vehicle.yaml") -> Vehicle:
    return Vehicle(load_definition(write(data, name)), 50, 50, 0)


def wrap(inputs):
    """Inputs written compactly in tests (a name, or a dict of fields), wrapped in `- input:`."""
    return [{"input": {"from": i} if isinstance(i, str) else i} for i in inputs]


def one_sensor_vehicle(actuator=None, units=()):
    """A definition with one sensor 'eye' and the given motor and units (compact inputs)."""
    motor = {"name": "motor", "type": "motor", "position": [0, -0.8], "inputs": ["eye"],
             **(actuator or {})}
    return {
        "general": {"type": "5", "name": "Test", "size": 4},
        "sensors": [{"sensor": {"name": "eye", "type": "light", "position": [0, 0.8]}}],
        "actuators": [{"actuator": {**motor, "inputs": wrap(motor["inputs"])}}],
        "units": [{"unit": {**u, "inputs": wrap(u["inputs"])}} for u in units],
    }


# 1. Vehicle 1 unchanged
def test_vehicle1_matches_original_implementation():
    scenario = load_scenario(VEHICLE1_SCENARIO)
    scenario.vehicles[0].definition.sensors[0].position = (0.0, 0.0)
    sim = Simulation(scenario)

    # The original Vehicle 1: one reading at the body center drives the speed.
    world, dt = scenario.world, scenario.simulation.dt
    rng = np.random.default_rng(scenario.simulation.seed)
    x, y, heading = 20.0, 20.0, 0.0
    for _ in range(3000):
        reading = float(world.stimulus_at("temperature", x, y))
        speed = min(0.0 + 1.0 * reading, 5.0)
        heading += 0.3 * math.sqrt(dt) * rng.standard_normal()
        x += speed * math.cos(heading) * dt
        y += speed * math.sin(heading) * dt
        x, y = x % 100, y % 100

        sim.step()
        v = sim.vehicles[0]
        assert (v.x, v.y, v.heading) == (x, y, heading)


# 2. Inputs
def test_actuator_input_defaults_type_and_strength(write):
    data = one_sensor_vehicle({"inputs": ["eye", {"from": "eye", "type": "inhibitory"},
                                          {"from": "eye", "strength": 0.3}]})
    definition = load_definition(write(data))
    assert definition.actuators[0].inputs == [
        Connection("eye", 1, 1.0), Connection("eye", -1, 1.0), Connection("eye", 1, 0.3)]


def test_unit_input_defaults_type_and_strength(write):
    unit = {"name": "u", "type": "threshold", "threshold": 1, "inputs": [
        "eye",
        {"from": "eye", "type": "inhibitory"},
        {"from": "eye", "type": "excitatory", "strength": 0.5},
        {"from": "eye", "strength": 0.9},
    ]}
    inputs = load_definition(write(one_sensor_vehicle(units=[unit]))).units[0].inputs
    assert [(c.sign, c.strength, c.active) for c in inputs] == [
        (1, 1, True), (-1, 1, True), (1, 0.5, False), (1, 0.9, True)]


# 3. Validation
def mutate(*path, value=None, delete=False):
    def change(data):
        *parents, last = path
        for k in parents:
            data = data[k]
        if delete:
            del data[last]
        else:
            data[last] = value
    return change


SENSOR0 = ("sensors", 0, "sensor")
ACTUATOR0 = ("actuators", 0, "actuator")


@pytest.mark.parametrize("change, key", [
    (mutate("general", "size", delete=True), "general.size"),
    (mutate("general", "size", value="big"), "general.size"),
    (mutate("general", "colour", value="red"), "general.colour"),
    (mutate(*SENSOR0, "range", value=3), "sensors[0].sensor.range"),
    (mutate("sensors", 0, value={"actuator": {}}), "sensors[0]"),
    (mutate("sensors", 1, "sensor", "name", value="left_eye"), "sensors[1].sensor.name"),
    (mutate(*SENSOR0, "name", value="Left Eye"), "sensors[0].sensor.name"),
    (mutate(*ACTUATOR0, "inputs", value=wrap(["nose"])), "actuators[0].actuator.inputs[0]"),
    (mutate(*ACTUATOR0, "inputs", value=wrap(["right_motor"])), "actuators[0].actuator.inputs[0]"),
    (mutate(*ACTUATOR0, "inputs", value=["left_eye"]), "actuators[0].actuator.inputs[0]"),
    (mutate(*ACTUATOR0, "inputs", value=[{"from": "left_eye"}]), "actuators[0].actuator.inputs[0]"),
    (mutate(*ACTUATOR0, "inputs", value=[{"input": {"type": "inhibitory"}}]),
     "actuators[0].actuator.inputs[0].input.from"),
    (mutate(*SENSOR0, "position", value=[1.5, 0]), "sensors[0].sensor.position"),
    (mutate(*ACTUATOR0, "type", value="propeller"), "actuators[0].actuator.type"),
    (mutate("units", value=[{"unit": {"name": "u", "type": "mnemotrix", "threshold": 1,
                                      "inputs": wrap(["left_eye"])}}]), "units[0].unit.type"),
    (mutate("actuators", value=[]), "actuators"),
    (mutate(*SENSOR0, "response", value={"type": "sigmoid"}), "sensors[0].sensor.response.type"),
    (mutate(*SENSOR0, "response", value={"at": 4}), "sensors[0].sensor.response.type"),
    (mutate(*SENSOR0, "response", value={"type": "peak", "at": 4}), "sensors[0].sensor.response.width"),
    (mutate(*SENSOR0, "response", value={"type": "peak", "at": 4, "width": 0}),
     "sensors[0].sensor.response.width"),
    (mutate(*SENSOR0, "response", value={"type": "step", "at": 4, "width": 1}),
     "sensors[0].sensor.response.width"),
    (mutate(*SENSOR0, "response", value={"type": "linear", "at": 4}), "sensors[0].sensor.response.at"),
    (mutate("units", value=[{"unit": {"name": "u", "type": "threshold", "threshold": 1,
                                      "inputs": wrap([{"from": "left_eye", "weight": 2}])}}]),
     "units[0].unit.inputs[0].input.weight"),
    (mutate("units", value=[{"unit": {"name": "u", "type": "threshold", "threshold": 1,
                                      "inputs": wrap([{"from": "left_eye", "type": "calming"}])}}]),
     "units[0].unit.inputs[0].input.type"),
    (mutate("units", value=[{"unit": {"name": "u", "type": "threshold", "threshold": 1,
                                      "inputs": wrap([{"from": "left_eye", "strength": 1.5}])}}]),
     "units[0].unit.inputs[0].input.strength"),
    (mutate(*ACTUATOR0, "inputs", value=wrap([{"from": "left_eye", "weight": 2}])),
     "actuators[0].actuator.inputs[0].input.weight"),
    (mutate(*ACTUATOR0, "inputs", value=wrap([{"from": "left_eye", "type": "calming"}])),
     "actuators[0].actuator.inputs[0].input.type"),
    (mutate(*ACTUATOR0, "inputs", value=wrap([{"from": "left_eye", "strength": -0.1}])),
     "actuators[0].actuator.inputs[0].input.strength"),
])
def test_validation_errors(write, change, key):
    data = read(VEHICLE2B)
    change(data)
    path = write(data)
    with pytest.raises(ConfigError) as excinfo:
        load_definition(path)
    assert str(path) in str(excinfo.value)
    assert key in str(excinfo.value)


def test_duplicate_name_error_names_both_places(write):
    data = read(VEHICLE2B)
    data["actuators"][1]["actuator"]["name"] = "left_eye"
    with pytest.raises(ConfigError) as excinfo:
        load_definition(write(data))
    assert "actuators[1].actuator.name" in str(excinfo.value)
    assert "sensors[0].sensor.name" in str(excinfo.value)


# 4. Steering
@pytest.mark.parametrize("seed", range(5))
def test_fear_turns_away_and_aggression_hits(seed):
    scenario = load_scenario(FEAR_AND_AGGRESSION)
    scenario.simulation.seed = seed
    sim = Simulation(scenario)
    light = scenario.world.stimuli["light"].sources[0].position
    arena = scenario.world.arena

    def distance(v):
        return math.hypot(*arena.delta(v.x - light[0], v.y - light[1]))

    fear, aggression = sim.vehicles
    fear_start = distance(fear)
    closest = distance(aggression)
    for _ in range(600):
        sim.step()
        closest = min(closest, distance(aggression))
    assert distance(fear) > fear_start
    assert closest < aggression.half_size


# 5. Inhibition
def test_inhibitory_connection_slows_motor(write):
    data = one_sensor_vehicle({"inputs": [{"from": "eye", "type": "inhibitory"}], "base_speed": 5})
    v = vehicle_from(data, write)
    speeds = []
    for reading in (0, 1, 2, 4):
        v.think({"eye": reading})
        speeds.append(v.motor_speeds["motor"])
    assert speeds == [5, 4, 3, 1]
    v.think({"eye": 10})
    assert v.motor_speeds["motor"] == 0  # motors do not run backwards


def test_inactive_input_does_not_move_motor(write):
    data = one_sensor_vehicle({"inputs": [{"from": "eye", "strength": 0.7}], "base_speed": 1})
    v = vehicle_from(data, write)
    v.think({"eye": 4})
    assert v.motor_speeds["motor"] == 1


# 6. Threshold units
def test_threshold_unit_fires_at_threshold(write):
    unit = {"name": "detector", "type": "threshold", "threshold": 2, "inputs": ["eye"]}
    v = vehicle_from(one_sensor_vehicle({"inputs": ["detector"]}, [unit]), write)
    for reading, fires in [(1.9, 0), (2.0, 1), (5, 1), (0, 0)]:
        v.think({"eye": reading})
        assert v.unit_outputs["detector"] == fires
        assert v.motor_speeds["motor"] == fires


def test_unit_chain_delays_by_one_step_per_unit_link(write):
    units = [{"name": "a", "type": "threshold", "threshold": 1, "inputs": ["eye"]},
             {"name": "b", "type": "threshold", "threshold": 1, "inputs": ["a"]}]
    v = vehicle_from(one_sensor_vehicle({"inputs": ["b"]}, units), write)
    history = []
    for reading in (1, 0, 0, 0):
        v.think({"eye": reading})
        history.append((v.unit_outputs["a"], v.unit_outputs["b"]))
    # a responds in the same step as the sensor, b one step after a.
    assert history == [(1, 0), (0, 1), (0, 0), (0, 0)]


def test_self_loop_keeps_firing(write):
    unit = {"name": "memory", "type": "threshold", "threshold": 1, "inputs": ["eye", "memory"]}
    v = vehicle_from(one_sensor_vehicle({"inputs": ["memory"]}, [unit]), write)
    outputs = []
    for reading in (0, 0, 1, 0, 0, 0):
        v.think({"eye": reading})
        outputs.append(v.unit_outputs["memory"])
    assert outputs == [0, 0, 1, 1, 1, 1]


def test_inhibitory_input_lowers_the_sum(write):
    units = [{"name": "u", "type": "threshold", "threshold": 1,
              "inputs": ["eye", "eye", {"from": "eye", "type": "inhibitory"}]}]
    v = vehicle_from(one_sensor_vehicle({"inputs": ["u"]}, units), write)
    v.think({"eye": 1.0})   # 1 + 1 - 1 = 1 reaches the threshold
    assert v.unit_outputs["u"] == 1
    v.think({"eye": 0.9})   # 0.9 + 0.9 - 0.9 = 0.9 does not
    assert v.unit_outputs["u"] == 0


@pytest.mark.parametrize("strength, fires", [(0.7, 0), (0.71, 1), (1.0, 1), (0.0, 0)])
def test_only_connections_above_0_7_are_active(write, strength, fires):
    units = [{"name": "u", "type": "threshold", "threshold": 1,
              "inputs": [{"from": "eye", "strength": strength}]}]
    v = vehicle_from(one_sensor_vehicle({"inputs": ["u"]}, units), write)
    v.think({"eye": 5.0})
    assert v.unit_outputs["u"] == fires


def test_threshold_zero_fires_alone_until_inhibited(write):
    units = [{"name": "idle", "type": "threshold", "threshold": 0,
              "inputs": [{"from": "eye", "type": "inhibitory"}]}]
    v = vehicle_from(one_sensor_vehicle({"inputs": ["idle"]}, units), write)
    outputs = []
    for reading in (0, 0, 0.5, 3, 0):
        v.think({"eye": reading})
        outputs.append(v.unit_outputs["idle"])
    assert outputs == [1, 1, 0, 0, 1]


def test_negative_threshold_fires_until_inhibition_is_strong_enough(write):
    units = [{"name": "idle", "type": "threshold", "threshold": -2,
              "inputs": [{"from": "eye", "type": "inhibitory"}]}]
    v = vehicle_from(one_sensor_vehicle({"inputs": ["idle"]}, units), write)
    outputs = []
    for reading in (0, 1, 2, 3):
        v.think({"eye": reading})
        outputs.append(v.unit_outputs["idle"])
    assert outputs == [1, 1, 1, 0]


def test_inhibitory_example_from_the_spec(write):
    units = [{"name": "detector", "type": "threshold", "threshold": 2, "inputs": ["eye"]},
             {"name": "idle", "type": "threshold", "threshold": 0,
              "inputs": [{"from": "detector", "type": "inhibitory"}]}]
    v = vehicle_from(one_sensor_vehicle({"inputs": ["idle"], "gain": 3}, units), write)
    speeds = []
    for reading in (0, 3, 3, 3, 0, 0):
        v.think({"eye": reading})
        speeds.append(v.motor_speeds["motor"])
    # detector's output reaches idle one step later, in both directions.
    assert speeds == [3, 3, 0, 0, 0, 3]


# Movement
def test_faster_right_wheel_turns_left():
    v = Vehicle(load_definition(VEHICLE2B), 50, 50, 0)
    v.motor_speeds = {"left_motor": 1.0, "right_motor": 3.0}
    v.move(0.05, np.random.default_rng(0))
    a = 0.5 * v.half_size
    assert v.speed == 2.0
    assert v.turn_rate == pytest.approx((3.0 - 1.0) / (2 * a))


def test_sensors_sit_on_the_body():
    v = Vehicle(load_definition(VEHICLE2B), 50, 50, math.pi / 2)  # facing +y
    points = {name: (x, y) for name, _, x, y in v.sensor_points()}
    # Facing +y, the left eye is toward -x and both eyes are ahead (+y).
    assert points["left_eye"] == pytest.approx((50 - 0.9 * 2, 50 + 0.9 * 2))
    assert points["right_eye"] == pytest.approx((50 + 0.9 * 2, 50 + 0.9 * 2))


# 7. Diagram
def test_diagram_from_definition(write):
    unit = {"name": "detector", "type": "threshold", "threshold": 2,
            "inputs": ["eye", {"from": "detector", "type": "inhibitory"}]}
    v = vehicle_from(one_sensor_vehicle({"inputs": ["detector"], "gain": 3}, [unit]),
                     write)
    d = v.diagram()
    assert [(p.kind, p.name) for p in d.parts] == [
        ("sensor", "eye"), ("unit", "detector"), ("motor", "motor")]
    assert [(w.source, w.target, w.sign) for w in d.wires] == [
        ("eye", "detector", 1), ("detector", "detector", -1), ("detector", "motor", 1)]


def test_diagram_marks_inactive_connections(write):
    unit = {"name": "u", "type": "threshold", "threshold": 1,
            "inputs": [{"from": "eye", "strength": 0.5}, "eye"]}
    v = vehicle_from(one_sensor_vehicle({"inputs": ["u"]}, [unit]), write)
    v.think({"eye": 5.0})
    weak, strong = v.diagram().wires[:2]
    assert (weak.active, weak.level) == (False, 0.0)
    assert strong.active and strong.level > 0


def test_diagram_of_vehicle_2b_is_crossed():
    d = Vehicle(load_definition(VEHICLE2B), 0, 0, 0).diagram()
    assert {(w.source, w.target) for w in d.wires} == {
        ("right_eye", "left_motor"), ("left_eye", "right_motor")}
    assert d.subtitle == "Vehicle 2b: Aggression"


# 8. Responses
def response_vehicle(write, response):
    data = one_sensor_vehicle()
    if response is not None:
        data["sensors"][0]["sensor"]["response"] = response
    return vehicle_from(data, write)


def outputs(v, readings):
    result = []
    for r in readings:
        v.think({"eye": r})
        result.append(v.sensor_values["eye"])
    return result


def test_linear_response_is_the_reading(write):
    v = response_vehicle(write, None)
    assert outputs(v, [0, 1.5, 7]) == [0, 1.5, 7]
    assert response_vehicle(write, {"type": "linear"}).definition.sensors[0].response.type == "linear"


def test_peak_response(write):
    v = response_vehicle(write, {"type": "peak", "at": 4, "width": 1.5, "height": 2})
    at_peak, one_width_below, one_width_above, far = outputs(v, [4, 2.5, 5.5, 20])
    assert at_peak == 2
    assert one_width_below == pytest.approx(2 * math.exp(-0.5))
    assert one_width_above == pytest.approx(2 * math.exp(-0.5))
    assert far < 1e-6


def test_step_response(write):
    v = response_vehicle(write, {"type": "step", "at": 4})
    assert outputs(v, [0, 3.999, 4, 10]) == [0, 0, 1, 1]


def test_motor_uses_response_output_and_keeps_the_reading(write):
    v = response_vehicle(write, {"type": "step", "at": 4, "height": 0.5})
    v.think({"eye": 6})
    assert v.sensor_readings["eye"] == 6
    assert v.motor_speeds["motor"] == 0.5


# 9. Headless
def test_definition_never_imports_pygame():
    code = (
        "import sys\n"
        "from braitenberg.definition import load_definition\n"
        "from braitenberg.vehicle import Vehicle\n"
        f"v = Vehicle(load_definition({str(VEHICLE1)!r}), 50, 50, 0)\n"
        "v.step({'sensor': 3.0}, 0.05, __import__('numpy').random.default_rng(0))\n"
        "v.diagram()\n"
        "assert 'pygame' not in sys.modules, 'pygame was imported'\n"
    )
    result = run_python(code)
    assert result.returncode == 0, result.stderr
