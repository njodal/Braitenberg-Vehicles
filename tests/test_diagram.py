"""Acceptance criteria of specs/vehicle-diagram.md."""

import pytest

from braitenberg.definition import load_definition
from braitenberg.scenario import load_scenario
from braitenberg.sim import Simulation
from braitenberg.vehicle import Vehicle
from conftest import (FEAR_AND_AGGRESSION, LOVE_AND_EXPLORER, MOTH, ORBITER_AND_DECIDER, VEHICLE1,
                      VEHICLE1_SCENARIO, VEHICLE5, run_python)


def all_levels(diagram):
    return [p.level for p in diagram.parts] + [w.level for w in diagram.wires]


def vehicle1():
    return Vehicle(load_definition(VEHICLE1), 0, 0, 0)


# 1. Structure
def test_vehicle1_structure():
    d = vehicle1().diagram()
    assert sorted(p.kind for p in d.parts) == ["motor", "sensor"]
    [wire] = d.wires
    parts = {p.name: p for p in d.parts}
    assert parts[wire.source].kind == "sensor"
    assert parts[wire.target].kind == "motor"
    assert wire.sign == +1
    assert parts[wire.source].label == "temperature"
    for p in d.parts:
        assert all(-1 <= c <= 1 for c in p.position)


# 2. Levels
def test_levels_zero_without_stimulus():
    v = vehicle1()
    v.think({"sensor": 0.0})
    assert all_levels(v.diagram()) == [0, 0, 0]


@pytest.mark.parametrize("reading", [5.0, 50.0])
def test_levels_reach_one_when_motor_saturates(reading):
    v = vehicle1()  # gain 1, max_speed 5: saturates at a reading of 5
    v.think({"sensor": reading})
    assert all_levels(v.diagram()) == [1, 1, 1]


def test_levels_stay_in_range_during_a_run():
    sim = Simulation(load_scenario(FEAR_AND_AGGRESSION))
    for _ in range(1000):
        sim.step()
        for v in sim.vehicles:
            assert all(0 <= level <= 1 for level in all_levels(v.diagram()))


# 3. Live
def test_diagram_reflects_current_state():
    sim = Simulation(load_scenario(VEHICLE1_SCENARIO))
    sim.run(100)
    v = sim.vehicles[0]
    parts = {p.name: p for p in v.diagram().parts}
    assert parts["sensor"].value == v.sensor_values["sensor"]
    assert parts["motor"].value == v.motor_speeds["motor"]
    assert parts["motor"].level == pytest.approx(v.motor_speeds["motor"] / 5)


def test_title_is_the_vehicle_label():
    sim = Simulation(load_scenario(FEAR_AND_AGGRESSION))
    assert [v.diagram().title for v in sim.vehicles] == ["Fear #0", "Aggression #1"]


# 4. Headless
def test_diagram_never_imports_pygame():
    code = (
        "import sys\n"
        "from braitenberg.definition import load_definition\n"
        "from braitenberg.vehicle import Vehicle\n"
        f"Vehicle(load_definition({str(VEHICLE1)!r}), 0, 0, 0).diagram()\n"
        "assert 'pygame' not in sys.modules, 'pygame was imported'\n"
    )
    result = run_python(code)
    assert result.returncode == 0, result.stderr


# 5. Renders, with SDL's dummy driver so no window opens
@pytest.mark.parametrize("scenario", [VEHICLE1_SCENARIO, FEAR_AND_AGGRESSION, LOVE_AND_EXPLORER,
                                      ORBITER_AND_DECIDER, MOTH])
def test_renderer_draws_frame_with_panel(scenario):
    code = (
        "import os\n"
        "os.environ['SDL_VIDEODRIVER'] = 'dummy'\n"
        "import pygame\n"
        "pygame.init()\n"
        "from braitenberg.scenario import load_scenario\n"
        "from braitenberg.render import Renderer, PANEL_WIDTH\n"
        f"r = Renderer(load_scenario({str(scenario)!r}))\n"
        "assert r.window_size == (r.size[0] + PANEL_WIDTH, r.size[1])\n"
        "screen = pygame.display.set_mode(r.window_size)\n"
        "r.advance(50)\n"
        "for selected in range(len(r.sim.vehicles)):\n"
        "    r.selected = selected\n"
        "    r.draw(screen)\n"
    )
    result = run_python(code)
    assert result.returncode == 0, result.stderr


# 6. Static diagram
@pytest.mark.parametrize("path", [VEHICLE1, VEHICLE5])
def test_static_svg_diagram(path):
    import xml.etree.ElementTree as ET

    from braitenberg.diagram import EXCITATORY, INACTIVE, INHIBITORY, definition_svg

    definition = load_definition(path)
    svg = definition_svg(definition)
    root = ET.fromstring(svg)                       # well-formed
    texts = [t.text for t in root.iter("{http://www.w3.org/2000/svg}text")]
    for part in [*definition.sensors, *definition.units, *definition.actuators]:
        assert part.name in texts
    assert f"Vehicle {definition.general.type}: {definition.general.name}" in texts

    arrows = [e for e in root.iter() if e.get("marker-end") and e.get("stroke") != "white"]
    inputs = [c for part in [*definition.units, *definition.actuators] for c in part.inputs]
    legend = 2 + any(not c.active for c in inputs)
    assert len(arrows) == len(inputs) + legend
    wire_colors = sorted(e.get("stroke") for e in arrows[:len(inputs)])
    expected = sorted(INACTIVE if not c.active else EXCITATORY if c.sign > 0 else INHIBITORY
                      for c in inputs)
    assert wire_colors == expected


def test_static_diagram_never_imports_pygame(tmp_path):
    out = tmp_path / "moth.svg"
    code = (
        "import sys\n"
        "from braitenberg.diagram import main\n"
        f"main([{str(VEHICLE5)!r}, '--out', {str(out)!r}])\n"
        "assert 'pygame' not in sys.modules, 'pygame was imported'\n"
    )
    result = run_python(code)
    assert result.returncode == 0, result.stderr
    assert out.read_text().startswith("<svg")


# 7. Recording
def test_record_gif(tmp_path):
    pytest.importorskip("PIL")
    out = tmp_path / "moth.gif"
    code = (
        "from braitenberg.record import record\n"
        f"print(record({str(MOTH)!r}, {str(out)!r}, seconds=1.0, every=0.1))\n"
    )
    result = run_python(code)
    assert result.returncode == 0, result.stderr
    from PIL import Image
    assert Image.open(out).n_frames == 11      # 1 s at one frame per 0.1 s, plus the first
