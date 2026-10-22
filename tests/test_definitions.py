"""Acceptance criteria of specs/vehicle-definition.md."""

import math
import re

import numpy as np
import pytest

from braitenberg.definition import Connection, load_definition
from braitenberg.scenario import load_scenario
from braitenberg.sim import Simulation
from braitenberg.vehicle import Vehicle
from braitenberg.yamlfile import ConfigError
from conftest import VEHICLE1, VEHICLE1_SCENARIO, VEHICLE2B, read, run_python


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
    (mutate("general", "width", value=0), "general.width"),
    (mutate("general", "length", value=-2), "general.length"),
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
    (mutate("units", value=[{"unit": {"name": "u", "type": "threshold", "threshold": 1,
                                      "inputs": wrap(["left_eye"]), "delay": 0}}]),
     "units[0].unit.delay"),
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
def outputs_over(v, unit, readings, sensor="eye"):
    """A unit's visible output after each step, feeding one reading per step."""
    result = []
    for r in readings:
        v.think({sensor: r})
        result.append(v.unit_outputs[unit])
    return result


def test_threshold_unit_fires_at_threshold_one_delay_later(write):
    unit = {"name": "detector", "type": "threshold", "threshold": 2, "inputs": ["eye"]}
    v = vehicle_from(one_sensor_vehicle({"inputs": ["detector"]}, [unit]), write)
    speeds = []
    for reading in (1.9, 2.0, 5, 0, 0):
        v.think({"eye": reading})
        speeds.append(v.motor_speeds["motor"])
    # With the default delay 0.05 and dt 0.05, the output follows the input one step later.
    assert speeds == [0, 0, 1, 1, 0]


def test_unit_chain_adds_one_delay_per_unit(write):
    units = [{"name": "a", "type": "threshold", "threshold": 1, "inputs": ["eye"]},
             {"name": "b", "type": "threshold", "threshold": 1, "inputs": ["a"]}]
    v = vehicle_from(one_sensor_vehicle({"inputs": ["b"]}, units), write)
    history = []
    for reading in (1, 0, 0, 0, 0):
        v.think({"eye": reading})
        history.append((v.unit_outputs["a"], v.unit_outputs["b"]))
    # a turns on one step after the sensor, b one step after a.
    assert history == [(0, 0), (1, 0), (0, 1), (0, 0), (0, 0)]


@pytest.mark.parametrize("delay, dt, steps", [(0.05, 0.05, 1), (0.1, 0.05, 2), (0.05, 0.01, 5),
                                              (0.01, 0.05, 1)])
def test_delay_is_rounded_to_steps(write, delay, dt, steps):
    unit = {"name": "a", "type": "threshold", "threshold": 1, "inputs": ["eye"], "delay": delay}
    v = Vehicle(load_definition(write(one_sensor_vehicle({"inputs": ["a"]}, [unit]))),
                50, 50, 0, dt=dt)
    outputs = outputs_over(v, "a", [1] + [0] * 8, sensor="eye")
    assert outputs.index(1) == steps


def test_self_loop_keeps_firing(write):
    unit = {"name": "memory", "type": "threshold", "threshold": 1, "inputs": ["eye", "memory"]}
    v = vehicle_from(one_sensor_vehicle({"inputs": ["memory"]}, [unit]), write)
    assert outputs_over(v, "memory", (0, 0, 1, 0, 0, 0)) == [0, 0, 0, 1, 1, 1]


def test_self_loop_holds_with_a_longer_delay(write):
    unit = {"name": "memory", "type": "threshold", "threshold": 1, "inputs": ["eye", "memory"]}
    v = Vehicle(load_definition(write(one_sensor_vehicle({"inputs": ["memory"]}, [unit]))),
                50, 50, 0, dt=0.01)
    outputs = outputs_over(v, "memory", [1] + [0] * 30)
    first = outputs.index(1)
    # A one-step input pulse latches: after one delay of settling, the memory stays on.
    assert all(outputs[first + 5:])


def two_sensor_vehicle(unit):
    return {
        "general": {"type": "5", "name": "Test", "size": 4},
        "sensors": [{"sensor": {"name": n, "type": "light", "position": [x, 0.8]}}
                    for n, x in (("eye", -0.5), ("nose", 0.5))],
        "actuators": [{"actuator": {"name": "motor", "type": "motor", "position": [0, -0.8],
                                    "inputs": wrap([unit["name"]])}}],
        "units": [{"unit": {**unit, "inputs": wrap(unit["inputs"])}}],
    }


@pytest.mark.parametrize("gap, fires", [(0, True), (1, True), (4, True), (5, False), (8, False)])
def test_inputs_less_than_a_delay_apart_count_as_simultaneous(write, gap, fires):
    unit = {"name": "both", "type": "threshold", "threshold": 2, "inputs": ["eye", "nose"]}
    v = Vehicle(load_definition(write(two_sensor_vehicle(unit))), 50, 50, 0, dt=0.01)  # 5-step delay
    outputs = []
    for step in range(30):
        v.think({"eye": 1.0 if step == 0 else 0.0, "nose": 1.0 if step == gap else 0.0})
        outputs.append(v.unit_outputs["both"])
    assert any(outputs) == fires


@pytest.mark.parametrize("inhibited", [False, True])
def test_inhibition_within_the_window_still_counts(write, inhibited):
    unit = {"name": "u", "type": "threshold", "threshold": 1,
            "inputs": ["eye", {"from": "nose", "type": "inhibitory"}]}
    v = Vehicle(load_definition(write(two_sensor_vehicle(unit))), 50, 50, 0, dt=0.01)  # 5-step delay
    outputs = []
    for step in range(15):
        # A one-step excitation at step 3; optionally a one-step inhibition at step 0.
        v.think({"eye": 1.0 if step == 3 else 0.0,
                 "nose": 1.0 if inhibited and step == 0 else 0.0})
        outputs.append(v.unit_outputs["u"])
    on = [i for i, o in enumerate(outputs) if o]
    if inhibited:
        # Both are held for 5 steps, so they overlap at steps 3-4: the unit stays off for
        # those, and fires only for the rest of the excitation's window (steps 5-7), 5 later.
        assert on == [10, 11, 12]
    else:
        assert on == [8, 9, 10, 11, 12]


def test_inhibitory_input_lowers_the_sum(write):
    units = [{"name": "u", "type": "threshold", "threshold": 1,
              "inputs": ["eye", "eye", {"from": "eye", "type": "inhibitory"}]}]
    v = vehicle_from(one_sensor_vehicle({"inputs": ["u"]}, units), write)
    # 1 + 1 - 1 = 1 reaches the threshold; 0.9 + 0.9 - 0.9 = 0.9 does not.
    assert outputs_over(v, "u", (1.0, 1.0, 0.9, 0.9)) == [0, 1, 1, 0]


@pytest.mark.parametrize("strength, fires", [(0.7, 0), (0.71, 1), (1.0, 1), (0.0, 0)])
def test_only_connections_above_0_7_are_active(write, strength, fires):
    units = [{"name": "u", "type": "threshold", "threshold": 1,
              "inputs": [{"from": "eye", "strength": strength}]}]
    v = vehicle_from(one_sensor_vehicle({"inputs": ["u"]}, units), write)
    assert outputs_over(v, "u", (5.0, 5.0))[-1] == fires


def test_threshold_zero_fires_alone_until_inhibited(write):
    units = [{"name": "idle", "type": "threshold", "threshold": 0,
              "inputs": [{"from": "eye", "type": "inhibitory"}]}]
    v = vehicle_from(one_sensor_vehicle({"inputs": ["idle"]}, units), write)
    # Outputs start at 0; the unit's own firing shows one delay later.
    assert outputs_over(v, "idle", (0, 0, 0.5, 3, 0, 0)) == [0, 1, 1, 0, 0, 1]


def test_negative_threshold_fires_until_inhibition_is_strong_enough(write):
    units = [{"name": "idle", "type": "threshold", "threshold": -2,
              "inputs": [{"from": "eye", "type": "inhibitory"}]}]
    v = vehicle_from(one_sensor_vehicle({"inputs": ["idle"]}, units), write)
    assert outputs_over(v, "idle", (0, 1, 2, 3, 3)) == [0, 1, 1, 1, 0]


def test_inhibitory_example_from_the_spec(write):
    units = [{"name": "detector", "type": "threshold", "threshold": 2, "inputs": ["eye"]},
             {"name": "idle", "type": "threshold", "threshold": 0,
              "inputs": [{"from": "detector", "type": "inhibitory"}]}]
    v = vehicle_from(one_sensor_vehicle({"inputs": ["idle"], "gain": 3}, units), write)
    speeds = []
    for reading in (0, 3, 3, 3, 0, 0, 0):
        v.think({"eye": reading})
        speeds.append(v.motor_speeds["motor"])
    # The motor stops 2 steps (0.1 s) after the light reaches 2, and restarts 2 steps after
    # it drops. It is also still at 0 in the first step, before idle's first output appears.
    assert speeds == [0, 3, 3, 0, 0, 0, 3]


# Movement
def test_faster_right_wheel_turns_left():
    v = Vehicle(load_definition(VEHICLE2B), 50, 50, 0)
    v.motor_speeds = {"left_motor": 1.0, "right_motor": 3.0}
    v.move(0.05, np.random.default_rng(0))
    a = 0.5 * v.half_width
    assert v.speed == 2.0
    assert v.turn_rate == pytest.approx((3.0 - 1.0) / (2 * a))


def test_body_shape(write):
    d = one_sensor_vehicle()
    square = load_definition(write(d))
    assert square.general.length == square.general.width == square.general.size
    d["general"].update(width=6, length=2)
    v = Vehicle(load_definition(write(d)), 50, 50, math.pi / 2)   # facing +y
    assert v.body_to_world(1, 1) == pytest.approx((53, 51))
    assert v.body_to_world(-1, -1) == pytest.approx((47, 49))


def test_turning_uses_the_width(write):
    d = read(VEHICLE2B)
    d["general"].update(width=6, length=2)
    v = Vehicle(load_definition(write(d)), 50, 50, 0)
    v.motor_speeds = {"left_motor": 1.0, "right_motor": 3.0}
    v.move(0.05, np.random.default_rng(0))
    a = 0.5 * 3      # the motors sit at x = ±0.5
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


# 10. Field of view
def fov_vehicle(write, field_of_view=None):
    sensor = {"name": "eye", "type": "light", "position": [0, 0.8]}
    if field_of_view is not None:
        sensor["field_of_view"] = field_of_view
    data = one_sensor_vehicle()
    data["sensors"][0]["sensor"] = sensor
    return load_definition(write(data))


@pytest.mark.parametrize("light_at, seen_with_90", [
    ((70, 50), True),     # straight ahead
    ((70, 60), True),     # 26 degrees to the left
    ((60, 70), False),    # 63 degrees to the left: outside a 90 degree cone
    ((30, 50), False),    # behind
])
def test_field_of_view(write, light_at, seen_with_90):
    from braitenberg.scenario import quick_scenario
    from conftest import ONE_LIGHT
    world = read(ONE_LIGHT)
    world["stimuli"]["light"]["sources"][0]["position"] = list(light_at)
    world_path = write(world, "light.yaml")
    readings = {}
    for fov in (None, 90):
        definition_path = write(read_definition_dict(fov_vehicle(write, fov)), f"v{fov}.yaml")
        sim = Simulation(quick_scenario(world_path, [definition_path], ["50,50,0"]))
        v = sim.vehicles[0]
        [(name, stimulus, x, y)] = v.sensor_points()
        readings[fov] = sim.world.stimulus_at(stimulus, x, y, 0.0, v.heading,
                                              v.definition.sensors[0].field_of_view)
    assert readings[None] > 0
    assert readings[90] == (pytest.approx(readings[None]) if seen_with_90 else 0)


def read_definition_dict(definition):
    """A loaded definition back to the dict form, for writing to a scenario."""
    s = definition.sensors[0]
    sensor = {"name": s.name, "type": s.type, "position": list(s.position)}
    if s.field_of_view != 360:
        sensor["field_of_view"] = s.field_of_view
    data = one_sensor_vehicle()
    data["sensors"][0]["sensor"] = sensor
    return data


@pytest.mark.parametrize("field_of_view", [0, -10, 400])
def test_field_of_view_validation(write, field_of_view):
    with pytest.raises(ConfigError, match=r"sensors\[0\]\.sensor\.field_of_view"):
        fov_vehicle(write, field_of_view)


# 13. Random units
def random_vehicle(write, **unit):
    unit = {"name": "itch", "type": "random", "rate": 2, "delay": 0.1, "threshold": 1,
            "inputs": ["eye"], **unit}
    return Vehicle(load_definition(write(two_sensor_vehicle(unit))), 50, 50, 0, dt=0.01)


def itch_outputs(v, steps, eye=1.0, seed=0):
    rng = np.random.default_rng(seed)
    outputs = []
    for _ in range(steps):
        v.think({"eye": eye, "nose": 0.0}, rng)
        outputs.append(v.unit_outputs["itch"])
    return outputs


def test_random_unit_fires_at_its_rate(write):
    outputs = itch_outputs(random_vehicle(write), 100_000)   # 1000 s
    # Each firing lasts its delay, 10 steps; one may start right as another ends.
    runs, n = [], 0
    for o in outputs:
        if o:
            n += 1
        elif n:
            runs.append(n)
            n = 0
    assert all(n % 10 == 0 for n in runs)
    starts = sum(runs) // 10
    quiet = outputs.count(0) * 0.01 + starts * 0.01          # steps it could start in
    assert starts / quiet == pytest.approx(2, rel=0.1)


def test_random_unit_waits_for_its_inputs(write):
    assert not any(itch_outputs(random_vehicle(write), 10_000, eye=0.0))


def test_random_unit_is_repeatable(write):
    assert itch_outputs(random_vehicle(write), 5000, seed=3) == \
        itch_outputs(random_vehicle(write), 5000, seed=3)
    assert itch_outputs(random_vehicle(write), 5000, seed=3) != \
        itch_outputs(random_vehicle(write), 5000, seed=4)


@pytest.mark.parametrize("unit, key", [
    ({"rate": None}, "units[0].unit.rate"),
    ({"rate": 0}, "units[0].unit.rate"),
    ({"type": "threshold"}, "units[0].unit.rate"),
])
def test_random_unit_validation(write, unit, key):
    unit = {"name": "itch", "type": "random", "rate": 2, "threshold": 1, "inputs": ["eye"], **unit}
    if unit["rate"] is None:
        del unit["rate"]
    with pytest.raises(ConfigError, match=re.escape(key)):
        load_definition(write(two_sensor_vehicle(unit)))
