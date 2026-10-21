"""Acceptance criteria of specs/camera.md."""

import copy
import math
import time

import numpy as np
import pytest

from braitenberg.definition import load_definition
from braitenberg.diagram import definition_svg
from braitenberg.scenario import quick_scenario
from braitenberg.sim import Simulation
from braitenberg.vehicle import Vehicle
from braitenberg.world import load_world
from braitenberg.yamlfile import ConfigError
from conftest import run_python

# The criteria's camera: at the body center, 120 x 60 degrees in 12 x 6 pixels of 10 degrees.
CAMERA = {"columns": 12, "rows": 6, "vertical_field_of_view": 60, "height": 1, "samples": 9}


def world(*things, edges="bounce", extra=None):
    """A world with `things`, each (x, y, radius, height, intensity, stimulus)."""
    stimuli = {"light": {"sources": []}, "red": {"sources": []}}
    for x, y, radius, height, intensity, stimulus in things:
        source = {"position": [x, y], "intensity": intensity, "falloff": 15}
        if radius is not None:
            source["radius"] = radius
        if height is not None:
            source["height"] = height
        stimuli[stimulus]["sources"].append(source)
    for stimulus, source in extra or []:
        stimuli[stimulus]["sources"].append(source)
    return {"name": "Test", "arena": {"width": 100, "height": 100, "edges": edges},
            "stimuli": stimuli}


def watcher(camera=None, stimulus="light", appearance=None, response=None, size=4, fov=120,
            extra_sensors=()):
    sensor = {"name": "retina", "type": stimulus, "position": [0, 0], "field_of_view": fov,
              "camera": {**CAMERA, **(camera or {})}}
    if response:
        sensor["response"] = response
    d = {"general": {"type": "8", "name": "Watcher", "size": size},
         "sensors": [{"sensor": sensor}, *({"sensor": s} for s in extra_sensors)],
         "actuators": [{"actuator": {"name": "motor", "type": "motor", "position": [0, -0.5],
                                     "inputs": []}}]}
    if appearance:
        d["appearance"] = appearance
    return d


def see(write, things=(), camera=None, at=(50, 50, 90), others=(), edges="bounce", **kwargs):
    """The image the watcher's camera reads after one step, as a rows x columns array."""
    sim = simulation(write, things, camera, at, others, edges, **kwargs)
    sim.step()
    return np.array(sim.vehicles[0].sensor_readings["retina"])


def simulation(write, things=(), camera=None, at=(50, 50, 90), others=(), edges="bounce",
               extra=None, **kwargs):
    world_path = write(world(*things, edges=edges, extra=extra), "world.yaml")
    paths, starts = [write(watcher(camera, **kwargs), "watcher.yaml")], [",".join(map(str, at))]
    for i, (definition, start) in enumerate(others):
        paths.append(write(definition, f"other{i}.yaml"))
        starts.append(",".join(map(str, start)))
    return Simulation(quick_scenario(world_path, paths, starts))


def ahead(distance, azimuth=0.0, at=(50, 50, 90)):
    """A point `distance` away from `at`, `azimuth` degrees to the left of its heading."""
    a = math.radians(at[2] + azimuth)
    return at[0] + distance * math.cos(a), at[1] + distance * math.sin(a)


def seen(image, threshold=0.0):
    """(rows, columns) where something brighter than `threshold` is seen."""
    rows, columns = np.nonzero(image > threshold)
    return sorted(set(rows.tolist())), sorted(set(columns.tolist()))


def prey(appearance=None, speed=0.0, size=4, height=None):
    d = {"general": {"type": "8", "name": "Other", "size": size},
         "sensors": [],
         "actuators": [{"actuator": {"name": "motor", "type": "motor", "position": [0, -0.5],
                                     "base_speed": speed, "inputs": []}}]}
    if height:
        d["general"]["height"] = height
    if appearance:
        d["appearance"] = appearance
    return d


# 1. Loading
def test_loading(write):
    w = load_world(write(world((50, 70, 1.5, 3, 10, "light"), (20, 20, None, None, 10, "light"),
                               (70, 70, 2, None, 10, "light"))))
    lamp, point, default = w.stimuli["light"].sources
    assert (lamp.radius, lamp.height) == (1.5, 3)
    assert point.radius is None and point.height is None
    assert default.height == 4                      # 2 * radius
    d = watcher(camera={"rows": 2, "columns": 3, "vertical_field_of_view": 10}, appearance={"red": 5})
    del d["sensors"][0]["sensor"]["camera"]["height"], d["sensors"][0]["sensor"]["camera"]["samples"]
    d["general"]["size"] = 3
    d["units"] = [{"unit": {"name": "u", "type": "threshold", "threshold": 1,
                            "inputs": [{"input": {"from": "retina[1, 0:2]"}}]}}]
    v = load_definition(write(d))
    cam = v.sensors[0].camera
    assert (cam.rows, cam.columns, cam.vertical_field_of_view) == (2, 3, 10)
    assert (cam.direction, cam.tilt, cam.range, cam.samples) == (0, 0, math.inf, 3)
    assert cam.height == v.general.height == 1.5    # the vehicle's height: size / 2
    assert v.appearance == {"red": 5}
    assert [c.source for c in v.units[0].inputs] == ["retina[1, 0]", "retina[1, 1]"]


# 2. Columns
@pytest.mark.parametrize("azimuth, columns", [(0, [5, 6]), (56, [0]), (-56, [11]), (180, [])])
def test_columns(write, azimuth, columns):
    image = see(write, [(*ahead(10, azimuth), 1, 2, 10, "light")])
    assert seen(image)[1] == columns


def test_direction_turns_the_view(write):
    image = see(write, [(*ahead(10, 90), 1, 2, 10, "light")], camera={"direction": 90})
    assert seen(image)[1] == [5, 6]


# 3. Rows
def test_rows(write):
    assert seen(see(write, [(*ahead(45), 1, 2, 10, "light")]))[0] == [2, 3]   # around the horizon
    assert 4 in seen(see(write, [(*ahead(5), 1, 2, 10, "light")]))[0]       # base lower when near
    assert 0 in seen(see(write, [(*ahead(11), 1, 30, 10, "light")]))[0]     # a tall thing
    image = see(write, [(*ahead(45), 1, 2, 10, "light")], camera={"tilt": -25})
    assert seen(image)[0] == [0]                                            # the horizon at the top


# 4. Coverage
def test_coverage(write):
    image = see(write, [(*ahead(13, 5), 5, 30, 10, "light")])
    assert image[2, 5] == 10          # the whole pixel is inside the thing
    assert image[0, 0] == 0           # nothing there
    partial = image[(image > 0) & (image < 10)]
    assert len(partial)
    # A partly covered pixel reads the brightness times the share of lines of sight that meet it.
    assert np.allclose(partial * 81 / 10, np.round(partial * 81 / 10))


def test_one_sample_reads_the_middle_line_of_sight(write):
    image = see(write, [(*ahead(13, 5), 5, 30, 10, "light")], camera={"samples": 1})
    assert set(np.unique(image)) <= {0, 10}


# 5. Size, not dimming
def test_size_not_dimming(write):
    far = see(write, [(*ahead(45, 5), 5, 30, 10, "light")])
    near = see(write, [(*ahead(15, 5), 5, 30, 10, "light")])
    assert far[2, 5] == near[2, 5] == 10
    assert len(seen(far)[1]) < len(seen(near)[1])


# 6. Hiding
def test_nearer_thing_hides_farther_one(write):
    tall = (*ahead(30), 8, 30, 10, "light")
    assert see(write, [tall])[3, 5] > 0
    image = see(write, [(*ahead(10), 2, 1.5, 10, "red"), tall])
    assert image[3, 5] == 0           # below the horizon: the short (red, so dark) thing in front
    assert image[1, 5] == 10          # above it: the tall thing behind sticks out


def test_camera_above_a_thing_sees_its_top(write):
    image = see(write, [(*ahead(5), 3, 2, 10, "light")], camera={"height": 3, "tilt": -45})
    assert image[0, 5] == 10 and image[0, 6] == 10


def test_ground_hides_nothing_standing_on_it(write):
    image = see(write, [(*ahead(20), 1, 2, 10, "light")], camera={"tilt": -30})
    assert image.max() > 0 and image[-1].max() == 0   # the bottom rows see dark ground


def test_range(write):
    things = [(*ahead(25), 1, 2, 10, "light")]
    assert see(write, things, camera={"range": 20}).max() == 0
    assert see(write, things, camera={"range": 30}).max() > 0
    # Beyond range, it hides nothing: the red one behind is not hidden from a red camera either.


def test_camera_inside_a_thing(write):
    image = see(write, [(50, 50, 5, 3, 7, "light")])
    assert np.all(image == 7)


# 7. Brightness
def test_sees_only_its_stimulus(write):
    red_in_front = [(*ahead(10), 2, 3, 10, "red"), (*ahead(20), 4, 3, 10, "light")]
    assert see(write, red_in_front)[2:4, 5:7].max() == 0          # the red lamp hides the white one
    assert see(write, red_in_front, stimulus="red")[2:4, 5:7].max() == 10


def test_coincident_sources_are_one_thing(write):
    both = [(*ahead(10), 2, 3, 10, "red"), (*ahead(10), 2, 3, 10, "light")]
    assert see(write, both).max() == 10
    assert see(write, both, stimulus="red").max() == 10


def test_switched_off_lamp_is_dark_and_hides(write):
    x, y = ahead(10)
    off = {"position": [x, y], "intensity": 10, "falloff": 15, "radius": 2, "height": 3,
           "schedule": {"period": 10, "on_at": 5, "off_at": 10}}
    image = see(write, [(*ahead(20), 4, 3, 10, "light")], extra=[("light", off)])
    assert image[2:4, 5:7].max() == 0


# 8. Vehicles
def test_sees_other_vehicles(write):
    x, y = ahead(10)
    image = see(write, others=[(prey({"light": 6}, height=10), (x, y, 0))])
    assert image.max() == 6
    dark = see(write, [(*ahead(20), 4, 3, 10, "light")], others=[(prey(), (x, y, 0))])
    assert dark[2:4, 5:7].max() == 0                       # dark, but hiding the lamp behind


def test_never_sees_itself(write):
    assert see(write, appearance={"light": 10}).max() == 0


def test_other_sensors_do_not_sense_an_appearance(write):
    eye = {"name": "eye", "type": "light", "position": [0, 0.9]}
    sim = simulation(write, others=[(prey({"light": 10}), (*ahead(3), 0))], extra_sensors=[eye])
    sim.step()
    assert sim.vehicles[0].sensor_readings["eye"] == 0


def test_vehicles_see_each_other_whatever_their_order(write):
    a, b = (50, 50, 90), (*ahead(10), 270)
    one = simulation(write, at=a, others=[(watcher(appearance={"light": 3}), b)], appearance={"light": 5})
    two = simulation(write, at=b, others=[(watcher(appearance={"light": 5}), a)], appearance={"light": 3})
    one.step(), two.step()
    assert np.array_equal(one.vehicles[0].sensor_readings["retina"],
                          two.vehicles[1].sensor_readings["retina"])
    assert np.array_equal(one.vehicles[1].sensor_readings["retina"],
                          two.vehicles[0].sensor_readings["retina"])
    assert one.vehicles[0].sensor_readings["retina"].max() > 0


# 9. Wrap
def test_wrap(write):
    image = see(write, [(97, 50, 1, 2, 10, "light")], at=(3, 50, 180), edges="wrap")
    assert seen(image)[1] == [5, 6]


# 10. Response
def test_step_response_per_pixel(write):
    sim = simulation(write, [(*ahead(13, 5), 5, 30, 10, "light")],
                     response={"type": "step", "at": 5, "height": 2})
    sim.step()
    v = sim.vehicles[0]
    reading = v.sensor_readings["retina"]
    for r in range(6):
        for c in range(12):
            assert v.sensor_values[f"retina[{r}, {c}]"] == (2 if reading[r, c] >= 5 else 0)


# 11. Pixel inputs
def pixel_watcher(inputs):
    d = watcher()
    d["units"] = [{"unit": {"name": "left_half", "type": "threshold", "threshold": 1,
                            "inputs": [{"input": i} for i in inputs]}}]
    return d


def test_pixel_inputs(write):
    one = load_definition(write(pixel_watcher([{"from": "retina[2, 3]"}])))
    assert [c.source for c in one.units[0].inputs] == ["retina[2, 3]"]
    block = load_definition(write(pixel_watcher([{"from": "retina[:, 0:6]", "type": "inhibitory",
                                                  "strength": 0.9}])))
    inputs = block.units[0].inputs
    assert [c.source for c in inputs] == [f"retina[{r}, {c}]" for r in range(6) for c in range(6)]
    assert all(c.sign == -1 and c.strength == 0.9 for c in inputs)


@pytest.mark.parametrize("azimuth, fires", [(30, 1), (-30, 0)])
def test_unit_summing_the_left_half(write, azimuth, fires):
    d = pixel_watcher([{"from": "retina[:, 0:6]"}])
    sim = simulation(write, [(*ahead(10, azimuth), 2, 3, 10, "light")])
    sim.vehicles[0] = Vehicle(load_definition(write(d, "left.yaml")), 50, 50, math.radians(90),
                              dt=sim.dt)
    sim.run(5)
    assert sim.vehicles[0].unit_outputs["left_half"] == fires


# 12. Validation
WORLD_ERRORS = [
    ({"radius": -1}, "radius"),
    ({"radius": "big"}, "radius"),
    ({"radius": 1, "height": 0}, "height"),
    ({"height": 3}, "height"),
]


@pytest.mark.parametrize("change, key", WORLD_ERRORS)
def test_world_validation(write, change, key):
    w = world()
    w["stimuli"]["light"]["sources"].append({"position": [50, 50], "intensity": 1, "falloff": 1,
                                             **change})
    with pytest.raises(ConfigError) as e:
        load_world(write(w))
    assert f"sources[0].{key}" in str(e.value) and "file.yaml" in str(e.value)


def camera_change(**changes):
    def change(d):
        d["sensors"][0]["sensor"]["camera"].update(changes)
    return change


def sensor_change(**changes):
    def change(d):
        sensor = d["sensors"][0]["sensor"]
        sensor.update(changes)
        for k in [k for k, v in changes.items() if v is None]:
            del sensor[k]
    return change


def remove(path):
    def change(d):
        holder = d
        for k in path[:-1]:
            holder = holder[k]
        del holder[path[-1]]
    return change


def inputs(*sources):
    def change(d):
        d["units"] = [{"unit": {"name": "u", "type": "threshold", "threshold": 1,
                                "inputs": [{"input": {"from": s}} for s in sources]}}]
    return change


def appearance(value):
    def change(d):
        d["appearance"] = value
    return change


DEFINITION_ERRORS = [
    (appearance(["red"]), "appearance"),
    (appearance({"red": -1}), "appearance.red"),
    (appearance({"red": "bright"}), "appearance.red"),
    (camera_change(zoom=2), "camera.zoom"),
    (remove(["sensors", 0, "sensor", "camera", "columns"]), "camera.columns"),
    (remove(["sensors", 0, "sensor", "camera", "rows"]), "camera.rows"),
    (remove(["sensors", 0, "sensor", "camera", "vertical_field_of_view"]),
     "camera.vertical_field_of_view"),
    (camera_change(columns=0), "camera.columns"),
    (camera_change(rows=2.5), "camera.rows"),
    (camera_change(samples=-1), "camera.samples"),
    (camera_change(vertical_field_of_view=200), "camera.vertical_field_of_view"),
    (camera_change(direction=200), "camera.direction"),
    (camera_change(tilt=70), "camera.tilt"),
    (camera_change(height=0), "camera.height"),
    (camera_change(range=-5), "camera.range"),
    (remove(["sensors", 0, "sensor", "field_of_view"]), "field_of_view"),
    (sensor_change(type="energy", field_of_view=None), "camera"),
    (inputs("retina"), "from"),
    (inputs("retina[3]"), "from"),
    (inputs("retina[0, 12]"), "from"),
    (inputs("retina[0, 3:3]"), "from"),
    (inputs("retina[0, 2:20]"), "from"),
    (inputs("retina[0, x]"), "from"),
    (inputs("retina(0, 1)"), "from"),
    (inputs("u[0]"), "from"),
]


@pytest.mark.parametrize("change, key", DEFINITION_ERRORS)
def test_definition_validation(write, change, key):
    d = watcher()
    change(d)
    with pytest.raises(ConfigError) as e:
        load_definition(write(d))
    assert key in str(e.value) and "file.yaml" in str(e.value)


def test_sensor_that_is_not_a_camera_cannot_be_indexed(write):
    d = watcher(extra_sensors=[{"name": "eye", "type": "light", "position": [0, 0.9]}])
    inputs("eye[0]")(d)
    with pytest.raises(ConfigError, match="cannot be indexed"):
        load_definition(write(d))


def test_appearance_must_be_a_stimulus_of_the_world(write):
    w = write(world(), "world.yaml")
    with pytest.raises(ConfigError, match="appearance 'blue'"):
        quick_scenario(w, [write(watcher(appearance={"blue": 1}))])


# 13. Nothing else changes
def test_radius_does_not_change_the_field(write):
    plain = load_world(write(world((50, 50, None, None, 10, "light")), "plain.yaml"))
    thing = load_world(write(world((50, 50, 3, 5, 10, "light")), "thing.yaml"))
    xs, ys = np.meshgrid(np.linspace(0, 100, 11), np.linspace(0, 100, 11))
    assert np.array_equal(plain.stimulus_at("light", xs, ys), thing.stimulus_at("light", xs, ys))


def test_sources_without_radius_are_not_seen(write):
    assert see(write, [(*ahead(10), None, None, 10, "light")]).max() == 0


# 14. Diagram
def test_diagram(write):
    d = pixel_watcher([{"from": "retina[1, 2]"}, {"from": "retina[0, 0:2]"}])
    sim = simulation(write, [(*ahead(13, 5), 5, 30, 10, "light")])
    sim.vehicles[0] = Vehicle(load_definition(write(d, "d.yaml")), 50, 50, math.radians(90),
                              dt=sim.dt)
    sim.step()
    diagram = sim.vehicles[0].diagram()
    camera = next(p for p in diagram.parts if p.kind == "camera")
    assert camera.shape == (6, 12)
    assert len(camera.level) == 6 and all(len(row) == 12 for row in camera.level)
    assert all(0 <= level <= 1 for row in camera.level for level in row)
    assert camera.value[2][5] == 10
    assert [w.source_index for w in diagram.wires] == [(1, 2), (0, 0), (0, 1)]
    svg = definition_svg(load_definition(write(d, "d.yaml")))
    assert svg.count('stroke-width="0.5"') == 72            # one cell per pixel
    assert svg.count("marker-end") == 1 + 2                  # one arrow, and the legend's two
    assert ">retina[1, 2], retina[0, 0:2]<" in svg           # labeled with the inputs as written


def test_renderer_draws_things_and_camera_views(write):
    sim_world = write(world((*ahead(10), 2, 3, 10, "light")), "world.yaml")
    path = write(watcher(), "watcher.yaml")
    code = f"""
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
from braitenberg.render import Renderer
from braitenberg.scenario import quick_scenario
pygame.init()
renderer = Renderer(quick_scenario({str(sim_world)!r}, [{str(path)!r}], ["50,50,90"]))
renderer.show_views = True
renderer.advance(3)
surface = pygame.Surface(renderer.window_size)
renderer.draw(surface)
print("ok")
"""
    result = run_python(code)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


# 15. Headless and fast
def test_camera_never_imports_pygame(write):
    sim_world = write(world((*ahead(10), 2, 3, 10, "light")), "world.yaml")
    path = write(watcher(), "watcher.yaml")
    result = run_python(f"""
import sys
from braitenberg.scenario import quick_scenario
from braitenberg.sim import Simulation
sim = Simulation(quick_scenario({str(sim_world)!r}, [{str(path)!r}], ["50,50,90"]))
sim.run(5)
print("pygame" in sys.modules)
""")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"


def test_fast(write):
    things = [(10 + 8 * k, 20 + 6 * k, 1.5, 3, 10, "light") for k in range(10)]
    camera = {"rows": 8, "columns": 16, "samples": 3}
    others = [(watcher(camera, appearance={"light": 10}), (20 + 20 * k, 60, 30 * k))
              for k in range(3)]
    sim = simulation(write, things, camera, others=others, appearance={"light": 10})
    start = time.perf_counter()
    sim.run(round(60 / sim.dt))
    assert time.perf_counter() - start < 5
