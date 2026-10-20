"""Energy and the energy sensor (specs/vehicle-definition.md, '5. Energy', criterion 9)."""

import math

import pytest

from braitenberg.definition import load_definition
from braitenberg.scenario import load_scenario, quick_scenario
from braitenberg.sim import Simulation
from braitenberg.yamlfile import ConfigError
from conftest import HOT_SPOT, ONE_LIGHT, read


def energy_vehicle(base_speed=3.0, **energy):
    return {
        "general": {"type": "1", "name": "Tank", "size": 4},
        "sensors": [{"sensor": {"name": "fuel", "type": "energy", "position": [0, 0]}}],
        "actuators": [{"actuator": {"name": "motor", "type": "motor", "position": [0, -0.8],
                                    "inputs": [{"input": {"from": "fuel", "strength": 0}}],
                                    "base_speed": base_speed}}],
        "energy": {"initial": 50, "max": 100, "consumption": 2, **energy},
    }


def dark_world(write):
    data = read(ONE_LIGHT)
    data["stimuli"]["light"]["sources"] = []
    return write(data, "dark.yaml")


def run(write, definition, world, start="50,50,0", steps=100):
    scenario = quick_scenario(world, [write(definition, "tank.yaml")], [start])
    sim = Simulation(scenario)
    v = sim.vehicles[0]
    path = 0.0
    for _ in range(steps):
        x, y = v.x, v.y
        sim.step()
        path += math.hypot(*sim.world.arena.delta(v.x - x, v.y - y))
    return v, path


def test_energy_drops_with_distance(write):
    v, path = run(write, energy_vehicle(), dark_world(write))
    assert path == pytest.approx(3.0 * 0.05 * 100)
    assert v.energy == pytest.approx(50 - 2 * path)


def test_no_energy_used_standing_still(write):
    v, _ = run(write, energy_vehicle(base_speed=0), dark_world(write))
    assert v.energy == 50


def test_energy_recharges_near_the_source(write):
    # Standing on the light (reading 10), gaining 1 per second per unit: +10 per second.
    v, _ = run(write, energy_vehicle(base_speed=0, charge_from="light"), ONE_LIGHT, start="60,50,0",
               steps=20)
    assert v.energy == pytest.approx(50 + 1 * 10 * 0.05 * 20)


@pytest.mark.parametrize("base_speed, charge, expected", [(5, None, 0), (0, "light", 100)])
def test_energy_stays_between_0_and_max(write, base_speed, charge, expected):
    extra = {"charge_from": charge} if charge else {}
    v, _ = run(write, energy_vehicle(base_speed=base_speed, **extra), ONE_LIGHT, start="60,50,0",
               steps=2000)
    assert v.energy == expected


def test_energy_sensor_reads_the_energy(write):
    v, _ = run(write, energy_vehicle(), dark_world(write), steps=10)
    before = v.energy
    v.think({})
    assert v.sensor_values["fuel"] == before


@pytest.mark.parametrize("change, key", [
    (lambda d: d.pop("energy"), "sensors[0].sensor.type"),
    (lambda d: d["energy"].update(initial=150), "energy.initial"),
    (lambda d: d["energy"].pop("max"), "energy.max"),
    (lambda d: d["energy"].update(consumption=-1), "energy.consumption"),
    (lambda d: d["energy"].update(charge_gain=-1), "energy.charge_gain"),
    (lambda d: d["energy"].update(battery=3), "energy.battery"),
])
def test_energy_validation(write, change, key):
    data = energy_vehicle()
    change(data)
    path = write(data, "tank.yaml")
    with pytest.raises(ConfigError, match=key.replace(".", r"\.").replace("[", r"\[").replace("]", r"\]")):
        load_definition(path)


def test_charge_from_must_be_in_the_world(write):
    path = write(energy_vehicle(charge_from="light"), "tank.yaml")
    with pytest.raises(ConfigError, match="charge_from"):
        quick_scenario(HOT_SPOT, [path])        # hot-spot has temperature, not light
