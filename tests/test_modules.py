"""Acceptance criteria of specs/modules.md."""

import copy
import re
from pathlib import Path

import pytest

from braitenberg.definition import load_definition
from braitenberg.diagram import definition_svg
from braitenberg.vehicle import Vehicle
from braitenberg.yamlfile import ConfigError
from conftest import read, run_python

WANDER = Path(__file__).parent.parent / "modules" / "wander.yaml"
PURSUE = Path(__file__).parent.parent / "modules" / "pursue.yaml"
BOREDOM = Path(__file__).parent.parent / "modules" / "boredom.yaml"


def vehicle(modules=None, units=(), actuator_inputs=("wander.left",)):
    """A vehicle with one sensor 'eye' that includes the wander module."""
    if modules is None:
        modules = [{"module": {"name": "wander", "file": str(WANDER), "position": [0, -0.5],
                               "inputs": {"enable": "eye"}}}]
    return {
        "general": {"type": "9", "name": "Test", "size": 4},
        "sensors": [{"sensor": {"name": "eye", "type": "light", "position": [0, 0.8]}}],
        "actuators": [{"actuator": {"name": "motor", "type": "motor", "position": [0, -0.8],
                                    "inputs": [{"input": {"from": s}} for s in actuator_inputs]}}],
        "units": [{"unit": u} for u in units],
        "modules": modules,
    }


def outputs(v, steps, eye):
    out = {"wander.left": [], "wander.right": []}
    for _ in range(steps):
        v.think({"eye": eye})
        for name in out:
            out[name].append(v.unit_outputs[name])
    return out


def starts(series):
    """The steps at which a unit's output comes on."""
    return [t for t in range(1, len(series)) if series[t] and not series[t - 1]]


# 1. Loading
def test_loading(write):
    d = vehicle(units=[{"name": "busy", "type": "threshold", "threshold": 1,
                        "inputs": [{"input": {"from": "eye"}}]}])
    d["modules"][0]["module"]["inputs"]["enable"] = ["busy", "eye"]
    v = load_definition(write(d))
    units = {u.name: u for u in v.units}
    assert all(u.type == "threshold" for u in v.units)
    assert [(c.source, c.sign) for c in units["wander.left"].inputs] == [("wander.go_left", 1)]
    assert [(c.source, c.sign) for c in units["wander.tick"].inputs] == [
        ("wander.both", 1), ("wander.was", -1), ("busy", 1), ("eye", 1)]
    assert all(units[f"wander.{n}"].module == "wander" for n in ("left", "tick"))
    use = v.modules["wander"]
    assert (use.title, use.position) == ("Wander", (0, -0.5))
    assert (use.inputs, use.outputs) == (["enable"], ["left", "right"])


# 2. Same as by hand: tests/test_vehicle8.py, test_arrays_are_a_shorthand, writes the hunter's
# module out by hand too.


# 3. On and off
def test_enabled_it_fires(write):
    v = Vehicle(load_definition(write(vehicle())), 50, 50, 0, dt=0.01)
    out = outputs(v, 30_000, eye=1.0)                 # 300 s
    left, right = starts(out["wander.left"]), starts(out["wander.right"])
    assert 100 <= len(left) + len(right) <= 160       # a pulse every 2 to 3 s
    assert 0.4 <= len(left) / (len(left) + len(right)) <= 0.6
    times = sorted(left + right)
    assert min(b - a for a, b in zip(times, times[1:])) >= 100   # at least 1 s apart
    pulse = out["wander.left"][left[0]:].index(0)
    assert 40 <= pulse <= 50                          # about 0.4 s


def test_turns_follow_no_short_rhythm(write):
    v = Vehicle(load_definition(write(vehicle())), 50, 50, 0, dt=0.01)
    out = outputs(v, 30_000, eye=1.0)
    sides = sorted([(t, "L") for t in starts(out["wander.left"])] +
                   [(t, "R") for t in starts(out["wander.right"])])
    pattern = "".join(side for _, side in sides)
    # No repeating block of up to 8 turns covers the whole sequence.
    assert all(pattern != (pattern[:n] * len(pattern))[:len(pattern)] for n in range(1, 9))


def test_not_enabled_it_never_fires(write):
    v = Vehicle(load_definition(write(vehicle())), 50, 50, 0, dt=0.01)
    assert not any(any(s) for s in outputs(v, 10_000, eye=0.0).values())


def test_with_no_sources_it_never_fires(write):
    d = vehicle()
    d["modules"][0]["module"]["inputs"]["enable"] = []
    v = Vehicle(load_definition(write(d)), 50, 50, 0, dt=0.01)
    assert not any(any(s) for s in outputs(v, 10_000, eye=1.0).values())


# 4. The boredom module
def bored_vehicle(write):
    d = {"general": {"type": "9", "name": "Test", "size": 4},
         "sensors": [{"sensor": {"name": n, "type": "light", "position": [0, 0.8]}}
                     for n in ("eye", "moving")],
         "actuators": [{"actuator": {"name": "motor", "type": "motor", "position": [0, -0.8],
                                     "inputs": [{"input": {"from": "boredom.bored"}}]}}],
         "modules": [{"module": {"name": "boredom", "file": str(BOREDOM),
                                 "inputs": {"seen": "eye", "busy": "moving"}}}]}
    return Vehicle(load_definition(write(d)), 50, 50, 0, dt=0.01)


@pytest.mark.parametrize("length", [0.05, 0.3, 1.0, 3.0])
def test_bored_after_nothing_seen_for_a_while(write, length):
    v = bored_vehicle(write)
    seen_from, seen_to = 5.0, 5.0 + length
    bored = []
    for step in range(round((seen_to + 5) / 0.01)):
        t = step * 0.01
        v.think({"eye": 1.0 if seen_from <= t < seen_to else 0.0, "moving": 0.0})
        bored.append((t, v.unit_outputs["boredom.bored"]))
    assert bored[round(4.9 / 0.01)][1] == 1                  # bored before anything was seen
    # Off within a delay of seeing something, and on again 3.2 s after the last of it.
    assert not any(b for t, b in bored if seen_from + 0.06 <= t < seen_to)
    after = [t for t, b in bored if t >= seen_to and b]
    assert after and 3.2 <= after[0] - seen_to <= 3.3


def test_busy_stops_boredom(write):
    v = bored_vehicle(write)
    out = []
    for step in range(800):
        moving = 1.0 if 400 <= step < 600 else 0.0
        v.think({"eye": 0.0, "moving": moving})
        out.append(v.unit_outputs["boredom.bored"])
    assert out[399] == 1 and not any(out[410:600]) and out[700] == 1


# 5. The pursue module
def pursuer(write):
    sensors = ["on_left", "ahead", "on_right", "close"]
    d = {"general": {"type": "9", "name": "Test", "size": 4},
         "sensors": [{"sensor": {"name": n, "type": "light", "position": [0, 0.8]}} for n in sensors],
         "actuators": [{"actuator": {"name": "motor", "type": "motor", "position": [0, -0.8],
                                     "inputs": [{"input": {"from": f"pursue.{o}"}}
                                                for o in ("turn_left", "turn_right", "forward")]}}],
         "modules": [{"module": {"name": "pursue", "file": str(PURSUE),
                                 "inputs": dict(zip(["left", "ahead", "right", "near"], sensors))}}]}
    return Vehicle(load_definition(write(d)), 50, 50, 0, dt=0.01)


def commands(v, steps=100, **readings):
    """Which of pursue's outputs come on within `steps` steps of steady readings."""
    seen = set()
    for _ in range(steps):
        v.think({n: readings.get(n, 0.0) for n in ("on_left", "ahead", "on_right", "close")})
        seen |= {o for o in ("turn_left", "turn_right", "forward") if v.unit_outputs[f"pursue.{o}"]}
    return seen


@pytest.mark.parametrize("readings, expected", [
    ({"on_left": 1.0}, {"turn_left"}),
    ({"on_right": 1.0}, {"turn_right"}),
    ({"ahead": 1.0}, {"forward"}),
    ({"ahead": 1.0, "on_left": 1.0}, {"forward"}),       # ahead wins over a side
    ({"ahead": 1.0, "close": 1.0}, set()),               # near: no lunge
    ({}, set()),
])
def test_pursue(write, readings, expected):
    assert commands(pursuer(write), **readings) == expected


def test_pursue_turns_are_short_and_lunges_long(write):
    for name, reading, output in (("turn", "on_left", "turn_left"), ("lunge", "ahead", "forward")):
        v = pursuer(write)
        on = []
        for step in range(100):
            v.think({n: 1.0 if (n == reading and step == 0) else 0.0
                     for n in ("on_left", "ahead", "on_right", "close")})
            on.append(v.unit_outputs[f"pursue.{output}"])
        lasts = sum(on) * 0.01
        assert lasts == pytest.approx(0.1 if name == "turn" else 0.3, abs=0.02)


# 6. Two copies
def test_two_copies(write):
    modules = [{"module": {"name": name, "file": str(WANDER), "inputs": {"enable": enable}}}
               for name, enable in (("a", "eye"), ("b", "a.left"))]
    v = load_definition(write(vehicle(modules, actuator_inputs=("a.left", "b.right"))))
    units = {u.name: u for u in v.units}
    assert {"a.left", "a.right", "b.left", "b.right"} <= set(units)
    assert [c.source for c in units["a.tick"].inputs] == ["a.both", "a.was", "eye"]
    assert [c.source for c in units["b.tick"].inputs] == ["b.both", "b.was", "a.left"]


# 7. Private units
def test_only_outputs_can_be_named(write, tmp_path):
    module = read(WANDER)
    module["units"].append({"unit": {"name": "inner", "type": "threshold", "threshold": 1,
                                     "inputs": [{"input": {"from": "left"}}]}})
    path = write(module, "inner.yaml")
    d = vehicle([{"module": {"name": "wander", "file": str(path),
                             "inputs": {"enable": "eye"}}}],
                actuator_inputs=("wander.inner",))
    with pytest.raises(ConfigError, match="'wander.inner' is not an output of module 'wander'"):
        load_definition(write(d))


# 8. Validation
def module_change(change):
    def apply(module):
        change(module)
        return module
    return apply


def drop(key):
    return module_change(lambda m: m.pop(key))


def unit_input(source):
    return module_change(lambda m: m["units"][0]["unit"]["inputs"][0]["input"].update({"from": source}))


MODULE_ERRORS = [
    (drop("module"), "module"),
    (drop("outputs"), "outputs"),
    (drop("units"), "units"),
    (module_change(lambda m: m.update(extra=1)), "extra"),
    (module_change(lambda m: m.update(inputs=["enable"])), "inputs"),
    (module_change(lambda m: m["inputs"].update({"Bad": "x"})), "inputs.Bad"),
    (module_change(lambda m: m["inputs"].update({"fast": "x"})), "units[0].unit.name"),
    (module_change(lambda m: m.update(outputs=["middle"])), "outputs[0]"),
    (module_change(lambda m: m.update(outputs=[])), "outputs"),
    (unit_input("eye"), "units[0].unit.inputs[0].input.from"),
    (unit_input("enable[0]"), "units[0].unit.inputs[0].input.from"),
    (unit_input("other.left"), "units[0].unit.inputs[0].input.from"),
    (module_change(lambda m: m["units"][0]["unit"].pop("threshold")), "units[0].unit.threshold"),
    (module_change(lambda m: m["units"][0]["unit"].update(position=[0, 0])), "units[0].unit.position"),
]


@pytest.mark.parametrize("change, key", MODULE_ERRORS)
def test_module_file_validation(write, change, key):
    path = write(change(read(WANDER)), "module.yaml")
    d = vehicle([{"module": {"name": "wander", "file": str(path),
                             "inputs": {"enable": "eye"}}}])
    with pytest.raises(ConfigError, match=re.escape(f"module.yaml: {key}")):
        load_definition(write(d))


def including(**changes):
    def apply(d):
        d["modules"][0]["module"].update(changes)
        for k, v in changes.items():
            if v is None:
                del d["modules"][0]["module"][k]
        return d
    return apply


DEFINITION_ERRORS = [
    (including(name="Wander"), "modules[0].module.name", None),
    (including(name="eye"), "modules[0].module.name", None),
    (including(file=None), "modules[0].module.file", None),
    (including(file="missing.yaml"), "missing.yaml", None),
    (including(colour="red"), "modules[0].module.colour", None),
    (including(inputs={}), "modules[0].module.inputs.enable", None),
    (including(inputs={"enable": "eye", "hold": "eye"}), "modules[0].module.inputs.hold", None),
    (including(inputs={"enable": "nose"}), ".input.from", "'nose'"),
    (including(position=[1.2, 0]), "modules[0].module.position", "outside the body"),
    (lambda d: d, "inputs[0].input.from", "'other' is not a module"),
]


@pytest.mark.parametrize("change, key, detail", DEFINITION_ERRORS)
def test_including_validation(write, change, key, detail):
    actuator_inputs = ("other.left",) if detail and "other" in detail else ("wander.left",)
    d = change(vehicle(actuator_inputs=actuator_inputs))
    with pytest.raises(ConfigError) as error:
        load_definition(write(d, "vehicle.yaml"))
    assert key in str(error.value)
    if detail:
        assert detail in str(error.value)


# 9. Diagram
def test_diagram_draws_a_module_as_a_box(write):
    d = vehicle(units=[{"name": "busy", "type": "threshold", "threshold": 1,
                        "inputs": [{"input": {"from": "eye"}}]}])
    d["modules"][0]["module"]["inputs"]["enable"] = ["busy", "eye"]
    v = Vehicle(load_definition(write(d)), 50, 50, 0, dt=0.01)
    v.think({"eye": 1.0})
    diagram = v.diagram()
    parts = {p.name: p for p in diagram.parts}
    box = parts["wander"]
    assert (box.kind, box.position, box.label) == ("module", (0, -0.5), "module Wander")
    assert (box.inputs, box.outputs) == (["enable"], ["left", "right"])
    assert len(box.level) == 2 and all(0 <= level <= 1 for level in box.level)
    assert not any(name.startswith("wander.") for name in parts)
    # Only the wires that cross its edge, each at its port.
    crossing = sorted((w.source, w.source_port or "", w.target, w.target_port or "")
                      for w in diagram.wires if "wander" in (w.source, w.target))
    assert crossing == [("busy", "", "wander", "enable"), ("eye", "", "wander", "enable"),
                        ("wander", "left", "motor", "")]


def test_svg_draws_a_module_as_a_box(write):
    svg = definition_svg(load_definition(write(vehicle())))
    assert all(f">{port}<" in svg for port in ("enable", "left", "right"))
    assert ">module Wander<" in svg


# 10. Headless
def test_modules_never_import_pygame():
    result = run_python(f"""
import sys
from braitenberg.definition import load_definition
load_definition({str(Path(__file__).parent.parent / "vehicles" / "vehicle8-hunter.yaml")!r})
assert "pygame" not in sys.modules
print("ok")
""")
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
