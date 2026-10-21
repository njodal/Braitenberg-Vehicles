"""Acceptance criteria of specs/vehicle-07.md."""

import math
from functools import lru_cache

import pytest

from braitenberg.definition import load_definition
from braitenberg.scenario import load_scenario
from braitenberg.sim import Simulation
from braitenberg.vehicle import Vehicle
from braitenberg.yamlfile import ConfigError
from conftest import WARY_MOTH, WARY_MOTH_SCENARIO, read, run_python

DT = 0.01
HALF = 120              # the red lamp is hot for 120 s, then cold for 120 s
SECONDS = 5 * HALF      # hot, cold, hot, cold, hot
RED, WHITE = (70, 50), (30, 50)
SIGHT = 26              # sees_red: within about 26 units of the red lamp


def hot(t):
    return t % (2 * HALF) < HALF


@lru_cache(maxsize=None)
def run(seed, learn=None):
    """Run the default scenario; per step: (time, strength, pain, danger, distance to red, to white)."""
    scenario = load_scenario(WARY_MOTH_SCENARIO)
    scenario.simulation.seed = seed
    if learn is not None:
        danger = next(u for u in scenario.vehicles[0].definition.units if u.name == "danger")
        next(c for c in danger.inputs if c.learning).learning.learn = learn
    sim = Simulation(scenario)
    moth = sim.vehicles[0]

    def distance(p):
        return math.hypot(*sim.world.arena.delta(moth.x - p[0], moth.y - p[1]))

    track = []
    for _ in range(round(SECONDS / DT)):
        sim.step()
        out = moth.unit_outputs
        track.append((sim.time, moth.strength("sees_red", "danger"), out["pain"], out["danger"],
                      distance(RED), distance(WHITE)))
    return track


def unlearned_at(track):
    """End of the first cold phase in which the strength drops to 0.7 or below and the moth then
    comes within 4 units of the red lamp; None if there is none."""
    for k in range(SECONDS // (2 * HALF) + 1):
        start, end = (2 * k + 1) * HALF, (2 * k + 2) * HALF
        drop = next((t for t, s, *_ in track if start <= t < end and s <= 0.7), None)
        if drop is not None and any(drop <= t < end and red < 4 for t, *_, red, _ in track):
            return end
    return None


# 1. Learns from burns
@pytest.mark.parametrize("seed", range(5))
def test_learns_from_burns(seed):
    track = run(seed)
    first_burn = next(t for t, _, pain, *_ in track if pain)
    assert all(s == 0 for t, s, *_ in track if t < first_burn)
    learned = next(t for t, s, *_ in track if s > 0.7)
    assert learned < HALF


# 2. Avoids red before getting burned
@pytest.mark.parametrize("seed", range(5))
def test_turns_away_from_red_before_the_burn(seed):
    visits, visit = [], []
    for row in run(seed):
        if row[4] < SIGHT:
            visit.append(row)
        elif visit:
            visits.append(visit)
            visit = []
    assert any(v[0][1] > 0.7 and hot(v[0][0])
               and any(danger for *_, danger, _, _ in v) and not any(pain for _, _, pain, *_ in v)
               for v in visits)


def test_burned_less_than_a_moth_that_never_learns():
    def burned(track):
        return sum(DT for t, _, pain, *_ in track if pain and hot(t))
    learner = sum(burned(run(seed)) for seed in range(5))
    control = sum(burned(run(seed, learn=0.0)) for seed in range(5))
    assert learner <= 0.75 * control


# 3. Still drawn to the white lamp
@pytest.mark.parametrize("seed", range(5))
def test_visits_the_white_lamp_after_learning(seed):
    assert any(s > 0.7 and white < 8 for _, s, *_, white in run(seed))


# 4. Unlearns
@pytest.mark.parametrize("seed", range(5))
def test_unlearns_when_the_lamp_is_cold(seed):
    assert unlearned_at(run(seed)) is not None


# 5. Relearns
@pytest.mark.parametrize("seed", range(5))
def test_relearns_when_the_lamp_is_hot_again(seed):
    track = run(seed)
    end = unlearned_at(track)
    assert any(s > 0.7 and hot(t) for t, s, *_ in track if t >= end)


# 6. Rule
def learner_data(strength=0.0, learn=1.0, forget=0.5, sign="excitatory", threshold=1,
                 fast_sources=False, extra_learning=None):
    """Sensors a and b fire units src and other; dest takes other, and src through a Mnemotrix
    connection. With fast_sources, src and other have a one-step delay, so their outputs follow
    a and b with no widening."""
    learning = {"type": "mnemotrix", "learn": learn, **({"forget": forget} if forget is not None else {})}
    fast = {"delay": DT} if fast_sources else {}

    def unit(name, threshold, inputs, **extra):
        return {"unit": {"name": name, "type": "threshold", "threshold": threshold,
                         "inputs": [{"input": i} for i in inputs], **extra}}

    return {
        "general": {"type": "7", "name": "Test", "size": 4},
        "sensors": [{"sensor": {"name": n, "type": "light", "position": [0, 0.8]}}
                    for n in ("a", "b")],
        "units": [
            unit("src", 1, [{"from": "a"}], **fast),
            unit("other", 1, [{"from": "b"}], **fast),
            unit("dest", threshold, [{"from": "other"},
                                     {"from": "src", "type": sign, "strength": strength,
                                      "learning": extra_learning or learning}]),
        ],
        "actuators": [{"actuator": {"name": "motor", "type": "motor", "position": [0, -0.8],
                                    "inputs": [{"input": {"from": "dest"}}]}}],
    }


def learner(write, **kw) -> Vehicle:
    return Vehicle(load_definition(write(learner_data(**kw))), 50, 50, 0, dt=DT)


def hold(v, a, b, steps=30):
    for _ in range(steps):
        v.think({"a": a, "b": b})
    return v.strength("src", "dest")


def one_step(v, a, b):
    before = v.strength("src", "dest")
    v.think({"a": a, "b": b})
    return v.strength("src", "dest") - before


def test_learns_while_source_and_other_inputs_fire_together(write):
    v = learner(write, learn=1.0)
    hold(v, 1, 1, steps=20)
    assert one_step(v, 1, 1) == pytest.approx(1.0 * DT)


def test_forgets_while_source_fires_without_them(write):
    v = learner(write, strength=0.5, learn=1.0, forget=0.5)
    hold(v, 1, 0, steps=20)
    assert one_step(v, 1, 0) == pytest.approx(-0.5 * DT)


@pytest.mark.parametrize("b", [0, 1])
def test_unchanged_while_source_is_off(write, b):
    v = learner(write, strength=0.5)
    hold(v, 0, b, steps=20)
    assert one_step(v, 0, b) == 0


def test_strength_stays_between_0_and_1(write):
    v = learner(write, strength=0.99, learn=5.0)
    assert hold(v, 1, 1, steps=50) == 1.0
    v = learner(write, strength=0.01, forget=5.0)
    assert hold(v, 1, 0, steps=50) == 0.0


def test_strength_at_the_start_of_a_step_decides_whether_it_counts(write):
    v = learner(write, learn=0.0, forget=None)      # strength never changes on its own
    hold(v, 1, 0)
    v.strengths[("dest", 1)] = 0.71
    v.think({"a": 1, "b": 0})
    assert v.pending["dest"][-1] == 1               # src alone fires dest
    v.strengths[("dest", 1)] = 0.70
    v.think({"a": 1, "b": 0})
    assert v.pending["dest"][-1] == 0


def test_learned_connection_takes_over_after_crossing(write):
    v = learner(write, learn=1.0, forget=None)
    hold(v, 1, 1, steps=100)                        # learns past 0.7 while other fires dest
    assert v.strength("src", "dest") > 0.7
    hold(v, 1, 0, steps=30)                         # other stops: src alone keeps dest on
    assert v.unit_outputs["dest"] == 1


def test_connection_that_fires_its_target_alone_forgets(write):
    v = learner(write, strength=1.0, learn=1.0, forget=0.5)
    hold(v, 1, 0, steps=20)
    assert v.unit_outputs["dest"] == 1              # fired by src alone
    assert one_step(v, 1, 0) == pytest.approx(-0.5 * DT)


@pytest.mark.parametrize("gap, learns", [(0, True), (4, True), (5, False), (8, False)])
def test_inputs_less_than_a_delay_apart_count_together(write, gap, learns):
    # src and other follow a and b one step later, as one-step pulses; dest's window is 5 steps.
    v = learner(write, learn=1.0, forget=None, fast_sources=True)
    hold(v, 0, 0)
    for step in range(20):
        v.think({"a": 1 if step == 0 else 0, "b": 1 if step == gap else 0})
    assert (v.strength("src", "dest") > 0) == learns


def test_without_forget_strength_never_decreases(write):
    v = learner(write, strength=0.9, learn=1.0, forget=None)
    assert hold(v, 1, 0, steps=100) == 0.9


# 7. Inhibitory learning
def test_inhibitory_connection_learns_and_then_subtracts(write):
    # dest has threshold 0: with nothing active it fires on its own, so "other inputs" fire it.
    v = learner(write, sign="inhibitory", threshold=0, learn=1.0, forget=None)
    hold(v, 1, 0, steps=10)
    assert v.unit_outputs["dest"] == 1
    hold(v, 1, 0, steps=100)
    assert v.strength("src", "dest") > 0.7
    assert v.unit_outputs["dest"] == 0              # the learned inhibition stops it


# 8. Validation
def edit(data, change):
    change(data)
    return data


def dest_input(data):
    return data["units"][2]["unit"]["inputs"][1]["input"]


@pytest.mark.parametrize("change, key", [
    (lambda d: dest_input(d)["learning"].update(type="ergotrix"), "inputs[1].input.learning.type"),
    (lambda d: dest_input(d)["learning"].pop("learn"), "inputs[1].input.learning.learn"),
    (lambda d: dest_input(d)["learning"].pop("type"), "inputs[1].input.learning.type"),
    (lambda d: dest_input(d)["learning"].update(rate=1), "inputs[1].input.learning.rate"),
    (lambda d: dest_input(d)["learning"].update(learn=-1), "inputs[1].input.learning.learn"),
    (lambda d: dest_input(d)["learning"].update(forget=-0.1), "inputs[1].input.learning.forget"),
    (lambda d: dest_input(d)["learning"].update(learn="fast"), "inputs[1].input.learning.learn"),
    (lambda d: dest_input(d).update({"from": "a"}), "inputs[1].input.from"),
    (lambda d: dest_input(d).update({"from": "dest"}), "inputs[1].input.from"),
    (lambda d: d["actuators"][0]["actuator"]["inputs"][0]["input"].update(
        learning={"type": "mnemotrix", "learn": 1}), "actuators[0].actuator.inputs[0].input.learning"),
])
def test_validation(write, change, key):
    with pytest.raises(ConfigError) as e:
        load_definition(write(edit(learner_data(), change)))
    assert "file.yaml" in str(e.value) and key in str(e.value)


# 9. Fixed connections unchanged
def test_connections_without_learning_keep_their_strength(write):
    v = learner(write)
    hold(v, 1, 1, steps=100)
    assert v.strengths.keys() == {("dest", 1)}
    assert v.connection_strength("dest", 0) == 1.0


# 10. Per vehicle, per run
def test_each_vehicle_learns_on_its_own(write):
    definition = load_definition(write(learner_data(learn=1.0)))
    burned, untouched = (Vehicle(definition, 50, 50, 0, dt=DT) for _ in range(2))
    hold(burned, 1, 1, steps=50)
    hold(untouched, 0, 0, steps=50)
    assert burned.strength("src", "dest") > 0
    assert untouched.strength("src", "dest") == 0
    assert definition.units[2].inputs[1].strength == 0


def test_restarting_a_scenario_restores_strengths():
    scenario = load_scenario(WARY_MOTH_SCENARIO)
    text = WARY_MOTH.read_text()
    sim = Simulation(scenario)
    sim.run(round(30 / DT))                         # long enough to be burned and learn
    assert sim.vehicles[0].strength("sees_red", "danger") > 0
    assert Simulation(scenario).vehicles[0].strength("sees_red", "danger") == 0
    assert WARY_MOTH.read_text() == text


# 11. Diagram
def test_diagram_reports_strength_and_activity(write):
    v = learner(write, learn=1.0)
    for steps in (0, 30, 60, 30):
        hold(v, 1, 1, steps=steps)
        wire = next(w for w in v.diagram().wires if w.learning)
        assert (wire.source, wire.target, wire.learning) == ("src", "dest", "mnemotrix")
        assert wire.strength == v.strength("src", "dest")
        assert wire.active == (wire.strength > 0.7)
    fixed = [w for w in v.diagram().wires if not w.learning]
    assert all(w.strength == 1 and w.active for w in fixed)


def test_static_svg_marks_learning_wires():
    import xml.etree.ElementTree as ET

    from braitenberg.diagram import LEARNING, definition_svg

    root = ET.fromstring(definition_svg(load_definition(WARY_MOTH)))
    learning = [e for e in root.iter() if e.get("stroke") == LEARNING and e.get("marker-end")]
    assert len(learning) == 2                       # the wire and its legend entry
    assert learning[0].get("stroke-dasharray")      # starts inactive
    texts = [t.text for t in root.iter("{http://www.w3.org/2000/svg}text")]
    assert "+M" in texts and "M learning (Mnemotrix)" in texts


def test_renderer_draws_learning_wires():
    code = (
        "import os\n"
        "os.environ['SDL_VIDEODRIVER'] = 'dummy'\n"
        "import pygame\n"
        "pygame.init()\n"
        "from braitenberg.scenario import load_scenario\n"
        "from braitenberg.render import Renderer\n"
        f"r = Renderer(load_scenario({str(WARY_MOTH_SCENARIO)!r}))\n"
        "screen = pygame.display.set_mode(r.window_size)\n"
        "for _ in range(3):\n"
        "    r.advance(500)\n"
        "    r.draw(screen)\n"
    )
    result = run_python(code)
    assert result.returncode == 0, result.stderr


# 12. Headless
def test_learning_never_imports_pygame():
    code = (
        "import sys\n"
        "from braitenberg.scenario import load_scenario\n"
        "from braitenberg.sim import Simulation\n"
        f"sim = Simulation(load_scenario({str(WARY_MOTH_SCENARIO)!r}))\n"
        "sim.run(2000)\n"
        "sim.vehicles[0].diagram()\n"
        "assert 'pygame' not in sys.modules, 'pygame was imported'\n"
    )
    result = run_python(code)
    assert result.returncode == 0, result.stderr


def test_repo_definition_loads():
    definition = load_definition(WARY_MOTH)
    danger = next(u for u in definition.units if u.name == "danger")
    c = next(c for c in danger.inputs if c.learning)
    assert (c.source, c.strength, c.learning.type) == ("sees_red", 0.0, "mnemotrix")
    assert read(WARY_MOTH)["general"]["type"] == "7"
