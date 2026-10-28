"""Obstacles and the proximity field (specs/worlds.md, criteria 7 to 12) and a sensor's
direction (specs/vehicle-definition.md, criterion 13)."""

import math

import numpy as np
import pytest

from braitenberg.definition import load_definition
from braitenberg.scenario import quick_scenario
from braitenberg.sim import Simulation
from braitenberg.world import load_world
from braitenberg.yamlfile import ConfigError
from conftest import ONE_LIGHT, read, run_python

WALL = {"position": [50, 50], "length": 20, "width": 2, "heading": 90}   # runs up and down


def world(*boxes, surfaces=True, edges="bounce"):
    stimulus = {"sources": []}
    if surfaces:
        stimulus["surfaces"] = {"intensity": 10, "falloff": 2}
    return {"name": "Test", "arena": {"width": 100, "height": 100, "edges": edges},
            "stimuli": {"proximity": stimulus, "light": {"sources": []}},
            "obstacles": [{"box": dict(b)} for b in boxes]}


def vehicle(sensors=(), speed=0.0, size=4, noise=0.0):
    return {"general": {"type": "5", "name": "Test", "size": size, "noise_std": noise},
            "sensors": [{"sensor": {"name": f"ir{i}", "type": "proximity", **s}}
                        for i, s in enumerate(sensors)],
            "actuators": [{"actuator": {"name": n, "type": "motor", "position": [x, -0.5],
                                        "base_speed": speed, "inputs": []}}
                          for n, x in (("left", -0.5), ("right", 0.5))]}


def simulation(write, w, vehicles):
    """`vehicles` is a list of (definition dict, "x,y,heading")."""
    paths = [write(d, f"v{i}.yaml") for i, (d, _) in enumerate(vehicles)]
    return Simulation(quick_scenario(write(w, "world.yaml"), paths, [s for _, s in vehicles]))


def reading(write, w, sensor, at, others=()):
    sim = simulation(write, w, [(vehicle([sensor]), at), *others])
    sim.step()
    return sim.vehicles[0].sensor_readings["ir0"]


# 7. Obstacles load
def test_obstacles_load(write):
    w = load_world(write(world({"position": [30, 60], "length": 20, "width": 1, "heading": 90,
                                "height": 3, "appearance": {"light": 9}},
                               {"position": [70, 40], "length": 6, "width": 6})))
    wall, block = w.obstacles
    assert (wall.position, wall.length, wall.width, wall.height) == ((30, 60), 20, 1, 3)
    assert wall.heading == pytest.approx(math.pi / 2)
    assert wall.faces("light") == (9, 9, 9, 9, 9)
    assert (block.heading, block.height, block.faces("light")) == (0, 2, (5, 5, 5, 5, 5))
    assert w.stimuli["proximity"].surfaces.intensity == 10
    assert load_world(ONE_LIGHT).obstacles == []


# 8. Proximity field
def test_proximity_field(write):
    w = load_world(write(world(WALL)))
    at = lambda x, y: w.stimulus_at("proximity", x, y)
    assert at(51, 50) == 10                     # on the surface
    assert at(50, 55) == 10                     # inside
    assert at(53, 52) == pytest.approx(5)       # falloff beside a long side
    assert at(50, 62) == pytest.approx(5)       # falloff beyond an end
    assert at(60, 50) == pytest.approx(10 / (1 + (9 / 2) ** 2))
    without = load_world(write(world(WALL, surfaces=False), "plain.yaml"))
    assert without.stimulus_at("proximity", 53, 52) == 0


# 9. Vehicles in the field
def test_vehicles_in_the_field(write):
    w = world()
    other = (vehicle(), "60,50,90")           # a 4 x 4 body: its left side at x = 58
    sensor = {"position": [0, 0]}
    assert reading(write, w, sensor, "56,50,0", [other]) == pytest.approx(5)
    # The same, with the other vehicle first in the scenario.
    sim = simulation(write, w, [other, (vehicle([sensor]), "56,50,0")])
    sim.step()
    assert sim.vehicles[1].sensor_readings["ir0"] == pytest.approx(5)
    assert reading(write, w, sensor, "56,50,0") == 0          # alone: never its own body
    as_obstacle = world({"position": [60, 50], "length": 4, "width": 4})
    assert reading(write, as_obstacle, sensor, "56,50,0") == pytest.approx(5)


# 10. Field of view
@pytest.mark.parametrize("direction, sees", [(0, True), (180, False), (-90, False)])
def test_field_of_view_on_surfaces(write, direction, sees):
    sensor = {"position": [0, 0], "field_of_view": 60, "direction": direction}
    value = reading(write, world(WALL), sensor, "45,50,0")      # the wall straight ahead
    assert (value > 0) == sees


# 11. Blocking
def drive(write, start, seconds=6):
    sim = simulation(write, world(WALL), [(vehicle(speed=3), start)])
    v = sim.vehicles[0]
    headings, gaps = [], []
    from braitenberg.world import to_surface
    o = sim.world.obstacles[0]
    while sim.time < seconds:
        sim.step()
        headings.append(v.heading)
        gaps.append(float(to_surface(v.x - o.position[0], v.y - o.position[1],
                                     o.width / 2, o.length / 2, o.heading)[2]))
    return v, headings, gaps


def test_stops_against_a_wall(write):
    v, headings, gaps = drive(write, "30,50,0")
    assert min(gaps) == pytest.approx(2)             # its disc just touches the wall
    assert v.x == pytest.approx(47) and v.y == pytest.approx(50)
    assert set(headings) == {0.0}


def test_slides_along_a_wall(write):
    v, headings, gaps = drive(write, "36,40,45", seconds=7)
    assert min(gaps) >= 2 - 1e-9
    assert v.x == pytest.approx(47) and v.y > 53     # against the wall, further up than it met it
    assert set(headings) == {math.radians(45)}


def test_disc_is_the_larger_side(write):
    d = vehicle(speed=3)
    d["general"].update(length=6, width=2)
    sim = simulation(write, world(WALL), [(d, "30,50,0")])
    sim.run(600)
    assert sim.vehicles[0].x == pytest.approx(46)    # 49 - 3: the disc's radius is half of 6


# 12. Nothing else changes
def test_worlds_without_obstacles_are_unchanged(write):
    w = load_world(ONE_LIGHT)
    xs, ys = np.meshgrid(np.linspace(0, 100, 5), np.linspace(0, 100, 5))
    data = read(ONE_LIGHT)
    data["obstacles"] = []
    again = load_world(write(data))
    assert np.array_equal(w.stimulus_at("light", xs, ys), again.stimulus_at("light", xs, ys))


# Validation
def obstacle(**change):
    box = dict(WALL, **change)
    return {k: v for k, v in box.items() if v is not None}


@pytest.mark.parametrize("box, key", [
    (obstacle(position=[150, 50]), "obstacles[0].box.position"),
    (obstacle(length=None), "obstacles[0].box.length"),
    (obstacle(width=0), "obstacles[0].box.width"),
    (obstacle(height=-1), "obstacles[0].box.height"),
    (obstacle(colour=3), "obstacles[0].box.colour"),
    (obstacle(appearance={"light": {"side": 3}}), "obstacles[0].box.appearance.light.side"),
])
def test_obstacle_validation(write, box, key):
    with pytest.raises(ConfigError) as e:
        load_world(write(world(box)))
    assert key in str(e.value) and "file.yaml" in str(e.value)


def test_obstacles_must_be_wrapped(write):
    w = world()
    w["obstacles"] = [WALL]
    with pytest.raises(ConfigError, match=r"obstacles\[0\]"):
        load_world(write(w))


@pytest.mark.parametrize("surfaces, key", [
    ({"intensity": 10}, "surfaces.falloff"),
    ({"intensity": 10, "falloff": 0}, "surfaces.falloff"),
    ({"intensity": 10, "falloff": 2, "range": 3}, "surfaces.range"),
])
def test_surfaces_validation(write, surfaces, key):
    w = world()
    w["stimuli"]["proximity"]["surfaces"] = surfaces
    with pytest.raises(ConfigError, match=f"proximity.{key}"):
        load_world(write(w))


# specs/vehicle-definition.md, 13. Direction
@pytest.mark.parametrize("direction, light_at, seen", [
    (90, (50, 70), True),     # 90 degrees to the left
    (90, (70, 50), False),    # straight ahead
    (-90, (50, 30), True),    # 90 degrees to the right
    (-90, (50, 70), False),
])
def test_direction(write, direction, light_at, seen):
    w = read(ONE_LIGHT)
    w["stimuli"]["light"]["sources"][0]["position"] = list(light_at)
    eye = {"name": "eye", "type": "light", "position": [0, 0]}
    plain = vehicle()
    plain["sensors"] = [{"sensor": eye}]
    turned = vehicle()
    turned["sensors"] = [{"sensor": {**eye, "field_of_view": 60, "direction": direction}}]
    values = []
    for d in (plain, turned):
        sim = Simulation(quick_scenario(write(w, "w.yaml"), [write(d, "d.yaml")], ["50,50,0"]))
        sim.step()
        values.append(sim.vehicles[0].sensor_readings["eye"])
    assert values[0] > 0
    assert values[1] == (pytest.approx(values[0]) if seen else 0)


@pytest.mark.parametrize("sensor, message", [
    ({"direction": 200, "field_of_view": 60}, "from -180 to 180"),
    ({"direction": 30}, "needs a field_of_view"),
])
def test_direction_validation(write, sensor, message):
    d = vehicle([{"position": [0, 0], **sensor}])
    with pytest.raises(ConfigError, match=rf"sensors\[0\]\.sensor\.direction: .*{message}"):
        load_definition(write(d))


def test_camera_cannot_have_a_direction(write):
    d = vehicle()
    d["sensors"] = [{"sensor": {"name": "c", "type": "light", "position": [0, 0], "field_of_view": 90,
                                "direction": 10,
                                "camera": {"rows": 1, "columns": 4, "vertical_field_of_view": 5}}}]
    with pytest.raises(ConfigError, match="camera.direction"):
        load_definition(write(d))


def test_renderer_draws_obstacles(write):
    w = write(world(WALL), "world.yaml")
    v = write(vehicle([{"position": [0.9, 0.9], "field_of_view": 60, "direction": 18}], speed=3),
              "v.yaml")
    result = run_python(f"""
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
from braitenberg.render import Renderer
from braitenberg.scenario import quick_scenario
pygame.init()
renderer = Renderer(quick_scenario({str(w)!r}, [{str(v)!r}], ["30,50,0"]))
renderer.advance(100)
renderer.draw(pygame.Surface(renderer.window_size))
print("ok")
""")
    assert result.returncode == 0, result.stderr
