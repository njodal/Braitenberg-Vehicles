"""Acceptance criteria of specs/vehicle-diagram.md."""

import subprocess
import sys

import pytest

from braitenberg.sim import Simulation
from braitenberg.vehicle import Vehicle1, Vehicle1Params
from braitenberg.world import load_world
from conftest import DEFAULT_WORLD, REPO


def all_levels(diagram):
    return [p.level for p in diagram.parts] + [w.level for w in diagram.wires]


# 1. Structure
def test_vehicle1_structure():
    d = Vehicle1(0, 0, 0, "temperature").diagram()
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
    v = Vehicle1(0, 0, 0, "temperature")
    v.sensor_value, v.speed = 0.0, 0.0
    assert all_levels(v.diagram()) == [0, 0, 0]


@pytest.mark.parametrize("reading", [5.0, 50.0])
def test_levels_reach_one_when_motor_saturates(reading):
    v = Vehicle1(0, 0, 0, "temperature", Vehicle1Params(gain=1.0, max_speed=5.0))
    v.sensor_value, v.speed = reading, v.motor_speed(reading)
    assert all_levels(v.diagram()) == [1, 1, 1]


def test_levels_stay_in_range_during_a_run():
    sim = Simulation(load_world(DEFAULT_WORLD))
    for _ in range(2000):
        sim.step()
        assert all(0 <= level <= 1 for level in all_levels(sim.vehicles[0].diagram()))


# 3. Live
def test_diagram_reflects_current_state():
    sim = Simulation(load_world(DEFAULT_WORLD))
    sim.run(100)
    v = sim.vehicles[0]
    parts = {p.name: p for p in v.diagram().parts}
    assert parts["sensor"].value == v.sensor_value
    assert parts["motor"].value == v.speed
    assert parts["motor"].level == pytest.approx(v.speed / v.params.max_speed)


# 4. Headless
def test_diagram_never_imports_pygame():
    code = (
        "import sys\n"
        "from braitenberg.vehicle import Vehicle1\n"
        "Vehicle1(0, 0, 0, 'temperature').diagram()\n"
        "assert 'pygame' not in sys.modules, 'pygame was imported'\n"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=REPO,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


# 5. Renders, with SDL's dummy driver so no window opens
def test_renderer_draws_frame_with_panel(tmp_path):
    code = (
        "import os, sys\n"
        "os.environ['SDL_VIDEODRIVER'] = 'dummy'\n"
        "import pygame\n"
        "pygame.init()\n"
        "from braitenberg.world import load_world\n"
        "from braitenberg.render import Renderer, PANEL_WIDTH\n"
        f"r = Renderer(load_world({str(DEFAULT_WORLD)!r}))\n"
        "assert r.window_size == (r.size[0] + PANEL_WIDTH, r.size[1])\n"
        "screen = pygame.display.set_mode(r.window_size)\n"
        "r.advance(50)\n"
        "r.draw(screen)\n"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=REPO,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
