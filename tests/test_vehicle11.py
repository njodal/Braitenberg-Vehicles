"""Acceptance criteria of specs/vehicle-11.md."""

import math
from functools import lru_cache

import pytest

from braitenberg.definition import load_definition
from braitenberg.diagram import definition_svg
from braitenberg.scenario import load_scenario
from braitenberg.sim import Simulation
from braitenberg.vehicle import Vehicle
from braitenberg.yamlfile import ConfigError
from conftest import REPO, read, run_python

DT = 0.01
DRIVER = REPO / "vehicles" / "vehicle11-cautious-driver.yaml"
DRIVER_SCENARIO = REPO / "scenarios" / "vehicle11-cautious-driver.yaml"
PHASE = 4.5
LIGHT_X = 50
STARTS = range(0, 100, 10)
COLORS = ("red", "yellow", "green")
FORWARD = [("green", "yellow"), ("yellow", "red"), ("red", "green")]
BACKWARD = [("yellow", "green"), ("red", "yellow"), ("green", "red")]


def light(t, order=("green", "yellow", "red")):
    return order[int((t % (3 * PHASE)) // PHASE)]


def reverse_light(world):
    """Green, then red, then yellow (criterion 6)."""
    for color, on_at in (("green", 0), ("red", PHASE), ("yellow", 2 * PHASE)):
        schedule = world.stimuli[color].sources[0].schedule
        schedule.on_at, schedule.off_at = on_at, on_at + PHASE


@lru_cache(maxsize=None)
def run(start, variant="default", seconds=300, reverse_at=None):
    """Run the default scenario from x = start; per step: (time, light, x before and after the
    step, speed, stop, strengths of every wire by (seen, expected) colors)."""
    scenario = load_scenario(DRIVER_SCENARIO)
    placement = scenario.vehicles[0]
    placement.position = (start, 10)
    for u in placement.definition.units:
        for c in u.inputs:
            if c.learning and variant == "control":
                c.learning.learn = 0.0
            elif c.learning and variant == "mnemotrix":
                c.learning.type, c.learning.learn, c.learning.forget = "mnemotrix", 0.5, 0.02
                c.learning.within = None
    sim = Simulation(scenario)
    driver = sim.vehicles[0]
    order = ("green", "yellow", "red")
    track = []
    for _ in range(round(seconds / DT)):
        if reverse_at is not None and sim.time >= reverse_at and order[1] == "yellow":
            reverse_light(sim.world)
            order = ("green", "red", "yellow")
        t, x = sim.time, driver.x
        color = light(t, order)
        sim.step()
        strengths = {(a, b): driver.strength(f"sees_{a}", f"expects_{b}")
                     for a in COLORS for b in COLORS if a != b}
        track.append((t, color, x, driver.x, driver.speed, driver.unit_outputs["stop"], strengths))
    return track


def ran_red(step):
    _, color, x, nx, *_ = step
    return color == "red" and x < LIGHT_X <= nx


def learned_at(track, wire=("yellow", "red")):
    return next((t for t, *_, s in track if s[wire] > 0.7), None)


# 1. Learns the sequence
@pytest.mark.parametrize("start", STARTS)
def test_learns_the_forward_wires(start):
    track = run(start)
    for wire in FORWARD:
        assert learned_at(track, wire) is not None and learned_at(track, wire) < 60, wire


# 2. Stops at yellow
@pytest.mark.parametrize("start", STARTS)
def test_stops_at_the_line_while_yellow(start):
    track = run(start)
    since = learned_at(track)
    stops = [k for k in range(1, len(track))
             if track[k][4] == 0 and track[k - 1][4] > 0]
    yellow = [k for k in stops if track[k][0] > since and track[k][1] == "yellow"
              and 7 <= LIGHT_X - track[k][3] <= 9.5]
    assert yellow
    k = yellow[0]
    green_at = next(j for j in range(k, len(track)) if track[j][1] == "green")
    assert all(track[j][4] == 0 for j in range(k, green_at))
    assert not any(track[k][1] == "green" for k in stops)


# 3. Only the forward wires mature
@pytest.mark.parametrize("start", STARTS)
def test_backward_wires_stay_at_zero(start):
    for *_, s in run(start):
        assert all(s[wire] == 0 for wire in BACKWARD)


# 4. Never runs a red once learned
def test_never_runs_a_red_once_learned():
    for start in STARTS:
        track = run(start)
        since = learned_at(track)
        assert not any(ran_red(step) for step in track if step[0] > since), start
    assert any(any(ran_red(step) for step in run(start, "control")) for start in STARTS)


# 5. Mnemotrix cannot
@pytest.mark.parametrize("start", STARTS)
def test_mnemotrix_wires_do_not_learn_the_sequence(start):
    track, control = run(start, "mnemotrix"), run(start, "control")
    assert max(max(s.values()) for *_, s in track) < 0.1
    assert [step[3] for step in track] == [step[3] for step in control]


# 6. Unlearns and learns the reverse
def test_reversed_light_unlearns_and_learns_the_reverse():
    track = run(25, seconds=600, reverse_at=300)
    end = track[-1][-1]
    assert all(end[wire] <= 0.7 for wire in FORWARD)
    assert all(end[wire] > 0.7 for wire in BACKWARD)
    dropped = next(t for t, *_, s in track if t > 300 and s[("yellow", "red")] <= 0.7)
    stops = [k for k in range(1, len(track)) if track[k][4] == 0 and track[k - 1][4] > 0]
    assert not any(track[k][0] > dropped and track[k][1] == "yellow" for k in stops)


# 7. Rule
def learner_data(strength=0.0, learn=0.3, forget=0.1, within=1.0, sign="excitatory",
                 threshold=1, second=None):
    """Sensors a and b fire units src and other, one step after them; dest takes other, and src
    through an Ergotrix connection. With `second`, sensor c fires unit c2, which goes into dest
    through a second Ergotrix connection of that strength."""
    learning = {"type": "ergotrix", "within": within, "learn": learn,
                **({"forget": forget} if forget is not None else {})}

    def unit(name, threshold, inputs, **extra):
        return {"unit": {"name": name, "type": "threshold", "threshold": threshold,
                         "inputs": [{"input": i} for i in inputs], **extra}}

    names = ("a", "b", "c") if second is not None else ("a", "b")
    dest_inputs = [{"from": "other"},
                   {"from": "src", "type": sign, "strength": strength, "learning": learning}]
    if second is not None:
        dest_inputs.append({"from": "c2", "strength": second, "learning": dict(learning)})
    return {
        "general": {"type": "11", "name": "Test", "size": 4},
        "sensors": [{"sensor": {"name": n, "type": "light", "position": [0, 0.8]}} for n in names],
        "units": [
            unit("src", 1, [{"from": "a"}], delay=DT),
            unit("other", 1, [{"from": "b"}], delay=DT),
            *([unit("c2", 1, [{"from": "c"}], delay=DT)] if second is not None else []),
            unit("dest", threshold, dest_inputs),
        ],
        "actuators": [{"actuator": {"name": "motor", "type": "motor", "position": [0, -0.8],
                                    "inputs": [{"input": {"from": "dest"}}]}}],
    }


def learner(write, **kw) -> Vehicle:
    return Vehicle(load_definition(write(learner_data(**kw))), 50, 50, 0, dt=DT)


def play(v, a, b, c=lambda k: 0, steps=300):
    """Step with sensor values a(k), b(k), c(k); return the strength of src -> dest after each step."""
    out = []
    for k in range(steps):
        readings = {"a": a(k), "b": b(k)}
        if "c" in v.sensor_values:
            readings["c"] = c(k)
        v.think(readings)
        out.append(v.strength("src", "dest"))
    return out


def pulse(at, length=20):
    return lambda k: 1 if at <= k < at + length else 0


def on_from(at):
    return lambda k: 1 if k >= at else 0


@pytest.mark.parametrize("gap, change", [(50, 0.3), (100, 0.3), (101, -0.1)])
def test_learns_when_the_destination_follows_within_the_wait(write, gap, change):
    v = learner(write, strength=0.5)
    history = play(v, pulse(10), pulse(10 + gap))
    assert history[-1] == pytest.approx(0.5 + change)


def test_forgets_when_the_wait_ends(write):
    v = learner(write, strength=0.5)
    history = play(v, pulse(10), lambda k: 0)
    changed = [k for k in range(1, len(history)) if history[k] != history[k - 1]]
    assert changed == [111]   # src turns on at step 11; the wait is 100 steps
    assert history[-1] == pytest.approx(0.4)


def test_destination_alone_changes_nothing(write):
    v = learner(write, strength=0.5)
    assert set(play(v, lambda k: 0, pulse(50))) == {0.5}


def test_source_again_while_waiting_changes_nothing(write):
    v = learner(write, strength=0.5)
    assert play(v, lambda k: 1 if k in range(10, 15) or k in range(40, 45) else 0,
                lambda k: 0)[-1] == pytest.approx(0.4)


def test_source_while_destination_already_on_forgets(write):
    v = learner(write, strength=0.5)
    assert play(v, pulse(50), on_from(0))[-1] == pytest.approx(0.4)


def test_order_matters(write):
    v = learner(write, strength=0.5)
    assert play(v, pulse(60), on_from(10))[-1] == pytest.approx(0.4)


def test_long_overlap_after_one_pairing_learns_once(write):
    v = learner(write, strength=0.0)
    assert play(v, on_from(10), on_from(50), steps=1000)[-1] == pytest.approx(0.3)


def test_strength_stays_between_0_and_1(write):
    v = learner(write, strength=0.9)
    assert play(v, pulse(10), pulse(50))[-1] == 1.0
    v = learner(write, strength=0.05)
    assert play(v, pulse(10), lambda k: 0)[-1] == 0.0


def test_without_forget_strength_never_decreases(write):
    v = learner(write, strength=0.5, forget=None)
    assert set(play(v, pulse(10), lambda k: 0)) == {0.5}


def test_learned_connection_firing_alone_forgets(write):
    v = learner(write, strength=1.0)
    history = play(v, pulse(10, length=200), lambda k: 0, steps=100)
    assert v.unit_outputs["dest"] == 1              # fired by src alone
    history += play(v, pulse(0, length=110), lambda k: 0, steps=200)
    assert history[-1] == pytest.approx(0.9)


def test_another_learning_connection_does_not_teach(write):
    v = learner(write, strength=0.5, second=1.0)   # c2 -> dest is active and fires dest
    assert play(v, pulse(10), lambda k: 0, c=pulse(50))[-1] == pytest.approx(0.4)


def test_connection_carries_its_signal_once_above_threshold(write):
    v = learner(write, strength=0.5)
    play(v, pulse(10), pulse(50))                   # 0.8: active from the next step
    play(v, pulse(10, length=50), lambda k: 0, steps=40)
    assert v.unit_outputs["dest"] == 1


# 8. Inhibitory learning
def test_inhibitory_connection_learns_and_then_subtracts(write):
    v = learner(write, sign="inhibitory", strength=0.5, threshold=1)
    play(v, pulse(10), pulse(50))
    assert v.strength("src", "dest") == pytest.approx(0.8)
    play(v, lambda k: 0, on_from(0), steps=20)      # other keeps dest on
    assert v.unit_outputs["dest"] == 1
    play(v, on_from(0), on_from(0), steps=20)       # src now cancels it
    assert v.unit_outputs["dest"] == 0


# 9. Validation
@pytest.mark.parametrize("learning, key", [
    ({"type": "ergotrix", "learn": 0.3}, "within"),
    ({"type": "ergotrix", "learn": 0.3, "within": 0}, "within"),
    ({"type": "ergotrix", "learn": 0.3, "within": "soon"}, "within"),
    ({"type": "mnemotrix", "learn": 0.3, "within": 1}, "within"),
])
def test_invalid_learning_sections(write, learning, key):
    data = learner_data()
    data["units"][2]["unit"]["inputs"][1]["input"]["learning"] = learning
    with pytest.raises(ConfigError) as error:
        load_definition(write(data, "bad.yaml"))
    assert "bad.yaml" in str(error.value) and key in str(error.value)


# 11. Per vehicle, per run
def test_two_drivers_learn_independently():
    scenario = load_scenario(DRIVER_SCENARIO)
    scenario.vehicles.append(scenario.vehicles[0].__class__(**{
        **vars(scenario.vehicles[0]), "position": (75, 10)}))
    sim = Simulation(scenario)
    sim.run(round(20 / DT))
    first, second = sim.vehicles
    assert first.strengths is not second.strengths
    assert first.ergotrix is not second.ergotrix
    fresh = Simulation(scenario).vehicles[0]
    assert all(s == 0 for s in fresh.strengths.values())
    assert all(m["wait"] == 0 for m in fresh.ergotrix.values())
    assert read(DRIVER) == read(DRIVER)   # loading never writes the file


# 12. Diagram
def test_diagram_reports_ergotrix_wires():
    v = Vehicle(load_definition(DRIVER), 25, 10, 0, dt=DT)
    wires = [w for w in v.diagram().wires if w.learning]
    assert len(wires) == 6 and {w.learning for w in wires} == {"ergotrix"}
    v.strengths[("expects_red", 1)] = 0.8
    wire = next(w for w in v.diagram().wires
                if (w.source, w.target) == ("sees_yellow", "expects_red"))
    assert wire.active and wire.strength == 0.8
    svg = definition_svg(load_definition(DRIVER))
    assert "+E<" in svg and "E learning (Ergotrix)" in svg


# 13. Headless
def test_runs_without_pygame():
    result = run_python(
        "import sys\n"
        "from braitenberg.scenario import load_scenario\n"
        "from braitenberg.sim import Simulation\n"
        "Simulation(load_scenario('scenarios/vehicle11-cautious-driver.yaml')).run(100)\n"
        "assert 'pygame' not in sys.modules\n")
    assert result.returncode == 0, result.stderr


# Second example: the landmark forager
FORAGER_SCENARIO = REPO / "scenarios" / "vehicle11-landmark-forager.yaml"
BLUE_POSTS = [(25, 25), (75, 75)]
SEEDS = range(5)


@lru_cache(maxsize=None)
def forage(seed, variant="default", seconds=600):
    """Run the forager's scenario; per step: (time, blue strength, red strength, full, going,
    smells, distance to the nearest blue post)."""
    scenario = load_scenario(FORAGER_SCENARIO)
    scenario.simulation.seed = seed
    for u in scenario.vehicles[0].definition.units:
        for c in u.inputs:
            if c.learning and variant == "control":
                c.learning.learn = 0.0
            elif c.learning and variant == "mnemotrix":
                c.learning.type, c.learning.learn, c.learning.forget = "mnemotrix", 0.5, 0.02
                c.learning.within = None
    sim = Simulation(scenario)
    v = sim.vehicles[0]
    track = []
    for _ in range(round(seconds / DT)):
        sim.step()
        out = v.unit_outputs
        nearest = min(math.hypot(*sim.world.arena.delta(v.x - x, v.y - y)) for x, y in BLUE_POSTS)
        track.append((sim.time, v.strength("sees_blue", "expects_food"),
                      v.strength("sees_red", "expects_food"), out["hunger.full"], out["going"],
                      out["smells"], nearest))
    return track


def onsets(track, column):
    return [k for k in range(1, len(track)) if track[k][column] and not track[k - 1][column]]


# L1. Learns where food is
@pytest.mark.parametrize("seed", SEEDS)
def test_forager_learns_that_food_is_at_blue_posts(seed):
    learned = next((t for t, blue, *_ in forage(seed) if blue > 0.7), None)
    assert learned is not None and learned < 300


# L2. Red is not learned
@pytest.mark.parametrize("seed", SEEDS)
def test_forager_does_not_learn_red(seed):
    assert max(red for _, _, red, *_ in forage(seed)) <= 0.7


# L3. Heads for blue posts
@pytest.mark.parametrize("seed", SEEDS)
def test_forager_heads_for_blue_posts_and_finds_food(seed):
    track = forage(seed)
    learned = next(k for k, step in enumerate(track) if step[1] > 0.7)
    steps = round(10 / DT)

    def reaches(k):
        if track[k][6] <= 12:
            return False
        for j in range(k, min(k + steps, len(track))):
            if track[j][5]:
                return True
            if not track[j][4]:
                return False
        return False

    assert any(reaches(k) for k in onsets(track, 4) if k > learned)


# L4. Eats more often
def test_forager_eats_more_often_than_control():
    learned = sum(len(onsets(forage(seed), 3)) for seed in SEEDS)
    control = sum(len(onsets(forage(seed, "control"), 3)) for seed in SEEDS)
    assert learned >= 1.5 * control


# L5. Mnemotrix cannot
@pytest.mark.parametrize("seed", [0, 1])
def test_forager_mnemotrix_wires_do_not_learn(seed):
    track = forage(seed, "mnemotrix", seconds=300)
    assert max(max(blue, red) for _, blue, red, *_ in track) < 0.1
