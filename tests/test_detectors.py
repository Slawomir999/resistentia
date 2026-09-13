import pytest

from resistentia import NegativeSelection


def _normal():
    return [[0.5 + 0.01*i, 0.5 - 0.01*i] for i in range(-5, 6)]


def test_normal_operation_is_not_flagged():
    ns = NegativeSelection(self_radius=0.15, n_detectors=50).fit(_normal())
    assert not ns.predict([0.5, 0.5])
    assert ns.anomaly_score([0.5, 0.5]) == 0.0


def test_a_point_far_from_normal_is_flagged_though_no_rule_described_it():
    ns = NegativeSelection(self_radius=0.15, n_detectors=50).fit(_normal())
    assert ns.predict([3.0, -2.0])
    assert ns.anomaly_score([3.0, -2.0]) > ns.anomaly_score([0.6, 0.45])


def test_every_surviving_detector_is_outside_self():
    ns = NegativeSelection(self_radius=0.15, n_detectors=40).fit(_normal())
    assert len(ns.detectors) > 0
    for centre, radius in ns.detectors:
        assert radius > 0
        assert ns.anomaly_score(centre) > 0


def test_results_are_reproducible_under_a_seed():
    a = NegativeSelection(self_radius=0.15, n_detectors=30, seed=42).fit(_normal())
    b = NegativeSelection(self_radius=0.15, n_detectors=30, seed=42).fit(_normal())
    assert a.detectors == b.detectors


def test_it_refuses_rather_than_pretends_when_self_fills_the_space():
    """Within hard bounds that normal operation already covers, no detector can
    survive. The library says so instead of returning an empty defence."""
    with pytest.raises(RuntimeError):
        NegativeSelection(self_radius=1.0, n_detectors=5, max_tries=500,
                          bounds=[(0.4, 0.6), (0.4, 0.6)]).fit(_normal())


def test_explicit_bounds_are_respected():
    ns = NegativeSelection(self_radius=0.05, n_detectors=20,
                           bounds=[(-2.0, 2.0), (-2.0, 2.0)]).fit(_normal())
    for centre, _ in ns.detectors:
        assert all(-2.0 <= c <= 2.0 for c in centre)


def test_ragged_input_is_rejected():
    with pytest.raises(ValueError):
        NegativeSelection().fit([[0.1, 0.2], [0.3]])
