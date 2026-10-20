"""Acceptance criteria of specs/vehicle-diagram.md."""

import pytest

from braitenberg.definition import load_definition
from braitenberg.scenario import load_scenario
from braitenberg.sim import Simulation
from braitenberg.vehicle import Vehicle
from conftest import (FEAR_AND_AGGRESSION, LOVE_AND_EXPLORER, ORBITER_AND_DECIDER, VEHICLE1,
                      VEHICLE1_SCENARIO, run_python)


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
                                      ORBITER_AND_DECIDER])
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
