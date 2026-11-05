"""The CSCG traffic light experiment (experiments/cscg/README.md) still learns and predicts what it reports."""
import importlib.util
import sys
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("cscg", Path(__file__).parents[1] / "experiments/cscg/cscg.py")
cscg = sys.modules["cscg"] = importlib.util.module_from_spec(spec)  # dataclasses look the module up
spec.loader.exec_module(cscg)


@pytest.fixture(scope="module")
def fixed():
    return cscg.train(cscg.fixed_light(60))


def test_fixed_durations_learn_one_ring_of_twelve_clones(fixed):
    order = cscg.ring(fixed)
    assert "".join(fixed.name(s)[0] for s in order) == "VVVVVAAARRRR"
    assert all(p == pytest.approx(1) for p in fixed.edges().values())


def test_after_the_first_change_of_color_predictions_are_certain(fixed):
    preds = fixed.predict("VVVVVAAARRRR" * 2)
    assert preds[0]["A"] == pytest.approx(0.2)  # any of the 5 green clones may be the last
    expected = "VVVVAAARRRRV"
    assert [max(p, key=p.get) for p in preds[12:]] == list(expected)
    assert all(max(p.values()) == pytest.approx(1) for p in preds[12:])


def test_varying_durations_spread_the_change_over_the_ticks_it_happened():
    model = cscg.train(cscg.varying_light(150))
    preds = model.predict("VVVVVAAARRRR" + "VVVVVV")[12:]
    yellow = [p["A"] for p in preds]
    assert yellow[:3] == pytest.approx([0, 0, 0])  # green lasts at least 4
    assert 0 < yellow[3] < yellow[4] < 1  # it may end on the 4th or 5th tick
    assert yellow[5] == pytest.approx(1)  # and never lasts more than 6
