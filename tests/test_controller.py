import pytest

from resistentia import ControllerConfig, ResponseController
from resistentia.signals import SignalWindow, fuse


def test_signature_without_context_does_not_drive_a_response():
    """Danger theory's central claim, as a unit test."""
    assert fuse(danger=0.0, pamp=1.0, safe=1.0) < 0.0          # tolerated
    assert fuse(danger=1.0, pamp=1.0, safe=0.0) > fuse(1.0, 0.0, 0.0)  # amplified


def test_window_is_a_rolling_mean():
    w = SignalWindow(3)
    for x in (1, 1, 1):
        w.push(x)
    assert w.value == pytest.approx(1.0)
    w.push(4)
    assert w.value == pytest.approx(2.0)


def test_sustained_distress_keeps_the_response_active():
    ctl = ResponseController(ControllerConfig(window=4))
    out = ctl.run([1.0] * 300, dt=0.25)
    assert out[-1].firing


def test_a_transient_response_terminates_by_itself():
    ctl = ResponseController(ControllerConfig(window=4))
    out = ctl.run([2.0] * 40 + [0.0] * 400, dt=0.25)
    assert any(s.firing for s in out[:80])      # it did respond
    assert not out[-1].firing                   # and it stood down


def test_without_suppression_the_response_runs_hotter():
    d = [1.0] * 400
    with_s = ResponseController(ControllerConfig(suppression=1.5, window=4)).run(d, dt=0.25)
    without = ResponseController(ControllerConfig(suppression=0.0, window=4)).run(d, dt=0.25)
    assert without[-1].activation > with_s[-1].activation * 1.5


def test_suppression_lags_activation():
    out = ResponseController(ControllerConfig(window=4)).run([1.0] * 200, dt=0.25)
    assert out[10].suppression < out[10].activation


def test_zero_gain_never_fires():
    out = ResponseController(ControllerConfig(gain=0.0)).run([5.0] * 200, dt=0.25)
    assert not any(s.firing for s in out)


def test_state_stays_non_negative():
    out = ResponseController().run([-3.0] * 100, dt=0.5)
    assert all(s.activation >= 0 and s.suppression >= 0 for s in out)


def test_invalid_configuration_is_rejected():
    with pytest.raises(ValueError):
        ControllerConfig(tau=0)
    with pytest.raises(ValueError):
        ControllerConfig(gain=-1)
    with pytest.raises(ValueError):
        ResponseController().step(danger=1.0, dt=0)


def test_run_is_reproducible_and_resets():
    ctl = ResponseController()
    a = ctl.run([1.0] * 50, dt=1.0)
    b = ctl.run([1.0] * 50, dt=1.0)
    assert [s.activation for s in a] == [s.activation for s in b]
