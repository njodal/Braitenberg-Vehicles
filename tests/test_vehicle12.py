"""Acceptance criteria of specs/vehicle-12.md."""

import copy
import math
from functools import lru_cache

import numpy as np
import pytest

from braitenberg.definition import load_definition
from braitenberg.diagram import bundles, definition_svg
from braitenberg.scenario import load_scenario
from braitenberg.sim import Simulation
from braitenberg.vehicle import Vehicle
from braitenberg.yamlfile import ConfigError
from conftest import MOTH, REPO, run_python

DT = 0.05
DREAMER = REPO / "vehicles" / "vehicle12-daydreamer.yaml"
SCENARIOS = {variant: REPO / "scenarios" / f"vehicle12-daydreamer{suffix}.yaml"
             for variant, suffix in (("daydreamer", ""), ("flooded", "-flooded"),
                                     ("silent", "-silent"))}
SEEDS = range(5)
IDEAS = [f"idea_{k}" for k in range(8)]
PREDECESSORS = {k: {(k - 1) % 8, (k - 3) % 8} for k in range(8)}


def wrap(inputs):
    return [{"input": {"from": i} if isinstance(i, str) else i} for i in inputs]


def test_vehicle(units, sensors=("eye",), control=None):
    """A definition with light sensors, the given units (compact inputs) and a control."""
    units = [{"unit": {"type": "threshold", **u, "inputs": wrap(u.get("inputs", []))}}
             for u in units]
    if control is not None:
        units.append({"unit": {"name": "c", "type": "threshold_control",
                               **{"target": 0, "rate": 1, **control},
                               "inputs": wrap(control.get("inputs", []))}})
    return {
        "general": {"type": "12", "name": "Test", "size": 4},
        "sensors": [{"sensor": {"name": s, "type": "light", "position": [0, 0.8]}}
                    for s in sensors],
        "actuators": [{"actuator": {"name": "motor", "type": "motor", "position": [0, -0.8],
                                    "inputs": wrap(["u"])}}],
        "units": units,
    }


test_vehicle.__test__ = False   # a helper, not a test


def vehicle(data, write, seed=0) -> Vehicle:
    return Vehicle(load_definition(write(data)), 50, 50, 0, dt=DT, seed=seed)


def set_offset(v, value: float, control: str = "c") -> None:
    """Make a control's offset `value`, already visible to its units."""
    k = v.unit_names.index(control)
    v.offsets[k] = value
    v.activations[:, k] = value


def step(v, readings=None, n=1):
    for _ in range(n):
        v.step(readings or {"eye": 1.0}, DT, np.random.default_rng(0))


# 1. Unchanged without control
def test_vehicle_without_control_keeps_its_thresholds():
    sim = Simulation(load_scenario(MOTH))
    v = sim.vehicles[0]
    base = np.array([u.threshold for u in v.definition.units])
    assert all(j == 0 for j in v.jitters.values())
    for _ in range(200):
        sim.step()
        assert (v.effective_thresholds == base).all()


# 2. Effective threshold
@pytest.mark.parametrize("threshold, offset, fires", [
    (1, 0.0, True), (1, 0.05, False), (2, 0.0, False), (2, -1.0, True)])
def test_effective_threshold(write, threshold, offset, fires):
    v = vehicle(test_vehicle([{"name": "u", "threshold": threshold, "inputs": ["eye"]}],
                             control={"controls": ["u"]}), write)
    set_offset(v, offset)
    step(v, n=2)
    assert v.unit_outputs["u"] == (1.0 if fires else 0.0)


# 3. Firing on its own
def test_unit_fires_on_its_own_once_the_offset_reaches_minus_its_threshold(write):
    v = vehicle(test_vehicle([{"name": "u", "threshold": 1}],
                             control={"controls": ["u"], "target": 1, "rate": 1}), write)
    fired_at = None
    for n in range(40):
        step(v)
        if v.unit_outputs["u"] and fired_at is None:
            fired_at = n
            offset_then = v.unit_outputs["c"]
    # The offset falls 0.05 per step; the unit fires once it reaches -1, one delay later.
    assert fired_at is not None and offset_then == pytest.approx(-1.0, abs=0.06)


# 4. The rule
def test_offset_rises_and_falls_without_limits(write):
    sensors = ("a", "b", "c1", "d")
    v = vehicle(test_vehicle([{"name": "u", "threshold": 1, "inputs": ["a"]}], sensors,
                             control={"controls": ["u"], "target": 2, "rate": 0.5,
                                      "inputs": list(sensors)}), write)
    k = v.unit_names.index("c")
    on, off = dict.fromkeys(sensors, 1.0), dict.fromkeys(sensors, 0.0)
    for _ in range(100):
        before = v.offsets[k]
        step(v, on)
        assert v.offsets[k] - before == pytest.approx(0.05)
    assert v.offsets[k] == pytest.approx(5.0)
    for _ in range(300):
        before = v.offsets[k]
        step(v, off)
        assert v.offsets[k] - before == pytest.approx(-0.05)
    assert v.offsets[k] == pytest.approx(-10.0)


# 5. Delay
def test_offset_reaches_units_after_its_delay(write):
    v = vehicle(test_vehicle([{"name": "u", "threshold": 1, "inputs": ["eye"]}],
                             control={"controls": ["u"], "target": 1, "rate": 1,
                                      "delay": 0.1}), write)
    k = v.unit_names.index("c")
    step(v)
    computed = v.offsets[k]
    assert computed == pytest.approx(-0.05) and v.unit_outputs["c"] == 0
    step(v)
    assert v.unit_outputs["c"] == 0
    step(v)
    assert v.unit_outputs["c"] == pytest.approx(computed)


# 6. Learning uses the base threshold
def learner(learning, control):
    units = [{"name": "s", "threshold": 1, "inputs": ["a"]},
             {"name": "u", "threshold": 1,
              "inputs": ["b", {"from": "s", "strength": 0, "learning": learning}]}]
    return test_vehicle(units, ("a", "b"),
                        control={"controls": ["u"], "target": 1, "rate": 2, "jitter": 0.4}
                        if control else None)


@pytest.mark.parametrize("learning", [
    {"type": "mnemotrix", "learn": 0.5, "forget": 0.1},
    {"type": "ergotrix", "learn": 0.3, "forget": 0.1, "within": 1}])
def test_learning_ignores_offset_and_jitter(write, learning):
    with_control = vehicle(learner(learning, True), write)
    without = Vehicle(load_definition(write(learner(learning, False), "plain.yaml")),
                      50, 50, 0, dt=DT)
    moved = False
    for n in range(600):
        readings = {"a": float(n % 40 < 10), "b": float(n % 40 in range(5, 20))}
        step(with_control, readings)
        step(without, readings)
        moved |= abs(with_control.unit_outputs["c"]) > 1
        assert with_control.strength("s", "u") == without.strength("s", "u")
    assert moved and without.strength("s", "u") > 0


# 7. No explosion
def ideas_on(v) -> int:
    return int(sum(v.unit_outputs[name] for name in IDEAS))


def test_ideas_flood_without_control():
    assert max(run("flooded", 0)["on"]) == 8


@pytest.mark.parametrize("seed", SEEDS)
def test_control_holds_a_flooding_network(seed):
    scenario = load_scenario(SCENARIOS["daydreamer"])
    scenario.simulation.seed = seed
    for u in scenario.vehicles[0].definition.units:
        if u.name in IDEAS:
            u.threshold = 1.0
    sim = Simulation(scenario)
    on = []
    for _ in range(round(120 / DT)):
        sim.step()
        if sim.time > 10:
            on.append(ideas_on(sim.vehicles[0]))
    assert max(on) <= 3 and 0.5 <= np.mean(on) <= 1.5


# 8. No extinction
@pytest.mark.parametrize("seed", SEEDS)
def test_ideas_fire_again_after_a_reset(seed):
    scenario = load_scenario(SCENARIOS["daydreamer"])
    scenario.simulation.seed = seed
    sim = Simulation(scenario)
    sim.run(round(60 / DT))
    v = sim.vehicles[0]
    v.activations[:] = 0
    v.offsets[:] = 0
    v.history[:] = -np.inf
    sim.step()
    assert ideas_on(v) == 0
    start = sim.time
    while ideas_on(v) == 0 and sim.time - start < 5:
        sim.step()
    assert ideas_on(v) > 0


# 9. Jitter
def test_jitter(write):
    data = test_vehicle([{"name": "u", "threshold": 1, "inputs": ["eye"], "array": 50}],
                        control={"controls": ["u"], "jitter": 0.3})
    data["actuators"][0]["actuator"]["inputs"] = wrap(["u[0]"])
    first, again, other = (vehicle(data, write, seed) for seed in (7, 7, 8))
    jitters = [first.jitters[f"u[{i}]"] for i in range(50)]
    assert all(-0.3 <= j <= 0.3 for j in jitters) and len(set(jitters)) == 50
    assert first.jitters == again.jitters and first.jitters != other.jitters
    before = dict(first.jitters)
    step(first, n=50)
    assert first.jitters == before
    data["units"][-1]["unit"]["jitter"] = 0
    assert all(j == 0 for j in vehicle(data, write).jitters.values())


def test_two_vehicles_in_a_scenario_get_different_jitter():
    scenario = load_scenario(SCENARIOS["daydreamer"])
    scenario.vehicles.append(copy.copy(scenario.vehicles[0]))
    first, second = Simulation(scenario).vehicles
    assert first.jitters != second.jitters
    assert first.jitters == Simulation(scenario).vehicles[0].jitters


# 10. Validation
def control_data(**changes):
    data = test_vehicle([{"name": "u", "threshold": 1, "inputs": ["eye"]},
                         {"name": "w", "threshold": 1, "inputs": ["eye"]}],
                        control={"controls": ["u"]})
    unit = data["units"][-1]["unit"]
    for key, value in changes.items():
        if value is None:
            unit.pop(key, None)
        else:
            unit[key] = value
    return data


@pytest.mark.parametrize("changes, key", [
    ({"controls": None}, "controls"),
    ({"controls": []}, "controls"),
    ({"controls": ["nothing"]}, "controls[0]"),
    ({"controls": ["eye"]}, "controls[0]"),
    ({"controls": ["c"]}, "controls[0]"),
    ({"target": -1}, "target"),
    ({"rate": 0}, "rate"),
    ({"delay": 0}, "delay"),
    ({"jitter": -0.1}, "jitter"),
    ({"threshold": 1}, "threshold"),
    ({"array": 3}, "array"),
    ({"inputs": wrap([{"from": "u", "learning": {"type": "mnemotrix", "learn": 1}}])},
     "learning"),
])
def test_invalid_controls(write, changes, key):
    with pytest.raises(ConfigError) as error:
        load_definition(write(control_data(**changes), "bad.yaml"))
    assert "bad.yaml" in str(error.value) and key in str(error.value)


def test_a_unit_has_one_control(write):
    data = control_data()
    second = copy.deepcopy(data["units"][-1])
    second["unit"]["name"] = "c2"
    data["units"].append(second)
    with pytest.raises(ConfigError) as error:
        load_definition(write(data, "bad.yaml"))
    assert "units[3].unit.controls[0]" in str(error.value)


@pytest.mark.parametrize("part", ["actuator", "unit", "control"])
def test_nothing_takes_a_control_as_input(write, part):
    data = control_data()
    if part == "actuator":
        data["actuators"][0]["actuator"]["inputs"] = wrap(["c"])
    elif part == "unit":
        data["units"][1]["unit"]["inputs"] = wrap(["c"])
    else:
        data["units"][-1]["unit"]["inputs"] = wrap(["c"])
    with pytest.raises(ConfigError) as error:
        load_definition(write(data, "bad.yaml"))
    assert "bad.yaml" in str(error.value) and "inputs[0].input.from" in str(error.value)


# 11. Display
def test_diagram_shows_the_control():
    v = Vehicle(load_definition(DREAMER), 0, 0, 0)
    diagram = v.diagram()
    control = next(p for p in diagram.parts if p.kind == "control")
    assert control.name == "caudate"
    idea = next(p for p in diagram.parts if p.name == "idea_0")
    assert idea.threshold == 2 and idea.effective == 2 + v.jitters["idea_0"]
    for name in IDEAS:
        assert any(w.control and (w.source, w.target) == ("caudate", name) for w in diagram.wires)
        assert any(not w.control and (w.source, w.target) == (name, "caudate")
                   for w in diagram.wires)
    # Drawn, each pair is one dashed line with an arrowhead at each end.
    drawn = bundles(diagram.wires)
    assert all(w.watched for w in drawn if w.control)
    assert not any((w.source, w.target) == ("idea_0", "caudate") for w in drawn)
    svg = definition_svg(load_definition(DREAMER))
    assert "<polygon" in svg and "θ" in svg and "watches and moves thresholds" in svg
    assert svg.count('marker-start="url(#arrow-ctrl)"') == 8


def test_renderer_draws_the_daydreamer():
    code = (
        "import os, sys\n"
        "os.environ['SDL_VIDEODRIVER'] = 'dummy'\n"
        "import pygame\n"
        "pygame.init()\n"
        "from braitenberg.scenario import load_scenario\n"
        "from braitenberg.render import Renderer\n"
        f"r = Renderer(load_scenario({str(SCENARIOS['daydreamer'])!r}))\n"
        "screen = pygame.display.set_mode(r.window_size)\n"
        "for _ in range(3):\n"
        "    r.advance(100)\n"
        "    r.draw(screen)\n"
    )
    result = run_python(code)
    assert result.returncode == 0, result.stderr


# 12. Headless
def test_runs_without_pygame():
    result = run_python(
        "import sys\n"
        "from braitenberg.scenario import load_scenario\n"
        "from braitenberg.sim import Simulation\n"
        "Simulation(load_scenario('scenarios/vehicle12-daydreamer.yaml')).run(100)\n"
        "assert 'pygame' not in sys.modules\n")
    assert result.returncode == 0, result.stderr


# 13 to 18. The daydreamer
@lru_cache(maxsize=None)
def run(variant: str, seed: int, seconds: float = 120) -> dict:
    """Per step: ideas on, onsets, wake's output, motor speeds, heading, position."""
    scenario = load_scenario(SCENARIOS[variant])
    scenario.simulation.seed = seed
    sim = Simulation(scenario)
    v = sim.vehicles[0]
    record = {"time": [], "on": [], "onsets": [], "along": [], "wake": [], "motors": [],
              "heading": [], "distance": 0.0}
    previous, recent = [0.0] * 8, []
    for _ in range(round(seconds / DT)):
        x, y = v.x, v.y
        sim.step()
        outputs = [v.unit_outputs[name] for name in IDEAS]
        for k in range(8):
            if outputs[k] and not previous[k]:
                record["onsets"].append((sim.time, k))
                record["along"].append(any(r[p] for r in recent[-round(1 / DT):]
                                           for p in PREDECESSORS[k]))
        recent.append(previous)
        previous = outputs
        record["time"].append(sim.time)
        record["on"].append(int(sum(outputs)))
        record["wake"].append(v.unit_outputs["wake"])
        record["motors"].append((v.motor_speeds["left_motor"], v.motor_speeds["right_motor"]))
        record["heading"].append(v.heading)
        record["distance"] += math.hypot(v.x - x, v.y - y) if abs(v.x - x) < 50 else 0.0
    return record


def after(record, key, t=10):
    return [value for time, value in zip(record["time"], record[key]) if time > t]


@pytest.mark.parametrize("variant", SCENARIOS)
def test_wake_sends_one_pulse(variant):
    wake = run(variant, 0)["wake"]
    onsets = [i for i in range(1, len(wake)) if wake[i] and not wake[i - 1]]
    assert len(onsets) == 1 and onsets[0] * DT < 2


@pytest.mark.parametrize("seed", SEEDS)
def test_flooded_drives_straight(seed):
    record = run("flooded", seed)
    assert all(on == 8 for on in after(record, "on"))
    assert all(left == right for left, right in after(record, "motors"))
    headings = after(record, "heading")
    assert max(headings) == min(headings)


@pytest.mark.parametrize("seed", SEEDS)
def test_silent_never_moves(seed):
    record = run("silent", seed)
    assert not record["onsets"] and record["distance"] == 0


@pytest.mark.parametrize("seed", SEEDS)
def test_daydreamer_thinks_in_the_dark(seed):
    record = run("daydreamer", seed)
    assert record["onsets"][-1][0] > 115
    assert len({k for _, k in record["onsets"]}) >= 4
    assert max(after(record, "on")) <= 3
    assert record["distance"] > 80
    assert len({round(math.degrees(h) / 10) % 36 for h in after(record, "heading")}) > 20


@pytest.mark.parametrize("seed", SEEDS)
def test_trains_follow_the_wires(seed):
    along = run("daydreamer", seed)["along"]
    assert sum(along) / len(along) >= 0.7


def test_same_seed_same_thoughts():
    assert run("daydreamer", 0, 30)["onsets"] == run.__wrapped__("daydreamer", 0, 30)["onsets"]
