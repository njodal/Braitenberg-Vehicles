"""Acceptance criteria of specs/modules.md."""

import copy
import re
from pathlib import Path

import pytest

from braitenberg.definition import load_definition
from braitenberg.vehicle import Vehicle
from braitenberg.yamlfile import ConfigError
from conftest import read, run_python

WANDER = Path(__file__).parent.parent / "modules" / "wander.yaml"


def vehicle(modules=None, units=(), actuator_inputs=("wander.left",)):
    """A vehicle with one sensor 'eye' that includes the wander module."""
    if modules is None:
        modules = [{"module": {"name": "wander", "file": str(WANDER), "position": [0, -0.5],
                               "inputs": {"enable": "eye", "hold": []}}}]
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
    d["modules"][0]["module"]["inputs"]["hold"] = ["busy", "eye"]
    v = load_definition(write(d))
    units = {u.name: u for u in v.units}
    assert all(u.type == "threshold" for u in v.units)
    assert [(c.source, c.sign) for c in units["wander.left"].inputs] == [("wander.go_left", 1)]
    assert [(c.source, c.sign) for c in units["wander.tick"].inputs] == [
        ("wander.both", 1), ("wander.was", -1), ("eye", 1), ("busy", -1), ("eye", -1)]
    assert all(units[f"wander.{n}"].module == "wander" for n in ("left", "tick"))
    assert v.modules == {"wander": ("Wander", (0, -0.5))}


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


def test_held_it_never_fires(write):
    d = vehicle(units=[{"name": "busy", "type": "threshold", "threshold": 0, "inputs": []}])
    d["modules"][0]["module"]["inputs"]["hold"] = "busy"
    v = Vehicle(load_definition(write(d)), 50, 50, 0, dt=0.01)
    assert not any(any(s) for s in outputs(v, 10_000, eye=1.0).values())


# 4. Two copies
def test_two_copies(write):
    modules = [{"module": {"name": name, "file": str(WANDER), "inputs": {"enable": "eye", "hold": hold}}}
               for name, hold in (("a", []), ("b", "a.left"))]
    v = load_definition(write(vehicle(modules, actuator_inputs=("a.left", "b.right"))))
    units = {u.name: u for u in v.units}
    assert {"a.left", "a.right", "b.left", "b.right"} <= set(units)
    assert [c.source for c in units["a.tick"].inputs] == ["a.both", "a.was", "eye"]
    assert [c.source for c in units["b.tick"].inputs] == ["b.both", "b.was", "eye", "a.left"]


# 5. Private units
def test_only_outputs_can_be_named(write, tmp_path):
    module = read(WANDER)
    module["units"].append({"unit": {"name": "inner", "type": "threshold", "threshold": 1,
                                     "inputs": [{"input": {"from": "left"}}]}})
    path = write(module, "inner.yaml")
    d = vehicle([{"module": {"name": "wander", "file": str(path),
                             "inputs": {"enable": "eye", "hold": []}}}],
                actuator_inputs=("wander.inner",))
    with pytest.raises(ConfigError, match="'wander.inner' is not an output of module 'wander'"):
        load_definition(write(d))


# 6. Validation
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
                             "inputs": {"enable": "eye", "hold": []}}}])
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
    (including(inputs={"enable": "eye"}), "modules[0].module.inputs.hold", None),
    (including(inputs={"enable": "eye", "hold": [], "extra": "eye"}), "modules[0].module.inputs.extra", None),
    (including(inputs={"enable": "nose", "hold": []}), ".input.from", "'nose'"),
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


# 7. Diagram
def test_diagram_draws_a_module_as_one_part(write):
    v = Vehicle(load_definition(write(vehicle())), 50, 50, 0, dt=0.01)
    v.think({"eye": 1.0})
    d = v.diagram()
    parts = {p.name: p for p in d.parts}
    assert parts["wander"].kind == "module" and parts["wander"].shape == (11,)
    assert parts["wander"].position == (0, -0.5) and parts["wander"].label == "module Wander"
    assert not any(name.startswith("wander.") for name in parts)
    # Only the wires that cross its edge: from eye in, and from left out to the motor.
    crossing = sorted((w.source, w.target) for w in d.wires if "wander" in (w.source, w.target))
    assert crossing == [("eye", "wander"), ("wander", "motor")]
    out = next(w for w in d.wires if w.source == "wander")
    assert out.source_index == (9,)       # left is the module's tenth unit


# 8. Headless
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
