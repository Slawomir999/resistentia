"""
Independent verification, kept in the suite so it runs in CI.

These are not restatements of the implementation. Each checks the code against
something outside it: a closed-form solution, a defining equation, a held-out
sample, or an invariant that must hold for any correct implementation.
"""
import math
import random

import pytest

from resistentia import ControllerConfig, NegativeSelection, Regime, ResponseController, classify
from resistentia import kinetics as K
from resistentia.regimes import Thresholds

VALID = {r.value for r in Regime}


def test_mkt_satisfies_its_own_defining_equation():
    """MKT is defined by k(MKT) == mean(k(T_i)). Check the returned value obeys it."""
    rng = random.Random(1)
    for _ in range(300):
        T = [rng.uniform(-30, 60) for _ in range(rng.randint(2, 120))]
        ea = rng.uniform(40_000, 200_000)
        m = K.mean_kinetic_temperature(T, ea)
        lhs = math.exp(-ea / (K.R_GAS * (m + 273.15)))
        rhs = sum(math.exp(-ea / (K.R_GAS * (t + 273.15))) for t in T) / len(T)
        assert lhs == pytest.approx(rhs, rel=1e-11)


def test_mkt_never_below_the_arithmetic_mean():
    rng = random.Random(2)
    for _ in range(300):
        T = [rng.uniform(-20, 50) for _ in range(rng.randint(2, 80))]
        assert K.mean_kinetic_temperature(T) >= sum(T)/len(T) - 1e-9


def test_potency_integration_matches_the_closed_form():
    ea = 120_000.0
    a = K.calibrate_pre_exponential(ref_temp_c=5, ea=ea, fraction_remaining=0.9, after=720)
    for T in (-10, 0, 5, 15, 40):
        for dt in (0.05, 0.25, 4.0):
            n = int(240/dt)
            got = K.integrate_potency([T]*n, dt, ea, a, initial=0.945)[-1]
            exact = 0.945*math.exp(-K.arrhenius_rate(T, ea, a)*n*dt)
            assert got == pytest.approx(exact, rel=1e-12)


def test_burn_ratio_is_exact_under_constant_conditions():
    """Above 1.0 must mean breach and below 1.0 must mean survival, with no
    disagreement — not merely a conservative approximation."""
    rng = random.Random(3)
    for _ in range(3000):
        ea = rng.uniform(70e3, 160e3)
        a = K.calibrate_pre_exponential(ref_temp_c=5, ea=ea, fraction_remaining=0.9,
                                        after=rng.uniform(300, 2000))
        p0, T, H = rng.uniform(0.905, 0.99), rng.uniform(-5, 20), rng.uniform(24, 600)
        br = K.burn_ratio(p0, T, 0.90, H, ea, a)
        if math.isinf(br):
            continue
        final = p0*math.exp(-K.arrhenius_rate(T, ea, a)*H)
        assert (br > 1.0) == (final < 0.90), f"br={br} final={final}"


def test_controller_state_never_diverges_across_the_parameter_space():
    for gain in (0.05, 1, 9, 25):
        for tau in (0.5, 8, 200):
            for sup in (0, 1.2, 10):
                out = ResponseController(ControllerConfig(
                    gain=gain, tau=tau, suppression=sup, window=8)).run([2.0]*400, dt=0.25)
                for s in out:
                    assert 0 <= s.activation < 1e6 and 0 <= s.suppression < 1e6
                    assert not math.isnan(s.activation) and not math.isnan(s.suppression)


def test_steady_state_falls_monotonically_with_suppression():
    prev = None
    for sup in (0.0, 0.2, 0.5, 1.0, 2.0, 4.0):
        a = ResponseController(ControllerConfig(suppression=sup, window=8)
                               ).run([1.0]*600, dt=0.25)[-1].activation
        if prev is not None:
            assert a <= prev + 1e-9
        prev = a


@pytest.mark.parametrize("tau", [1, 4, 16, 64])
def test_response_ends_after_the_drive_stops(tau):
    out = ResponseController(ControllerConfig(tau=tau, window=8)
                             ).run([2.0]*200 + [0.0]*2000, dt=0.25)
    assert not out[-1].firing


def test_alarm_duration_converges_as_the_step_shrinks():
    prev, diffs = None, []
    for dt in (1.0, 0.5, 0.25, 0.125):
        d = [x for x in ([1.2]*200 + [0.0]*200) for _ in range(int(1/dt))]
        hrs = sum(s.firing for s in ResponseController(
            ControllerConfig(window=max(1, int(6/dt)))).run(d, dt=dt))*dt
        if prev is not None:
            diffs.append(abs(hrs - prev))
        prev = hrs
    assert diffs[-1] <= diffs[0]


@pytest.mark.parametrize("dim", [2, 5, 12])
def test_calibrated_detector_controls_false_positives_on_held_out_normal(dim):
    """The classical failure of negative selection is a radius that looks fine in
    sample and flags everything out of sample. Calibration must prevent that."""
    rng = random.Random(7)
    def pt(shift=0.0):
        return [rng.gauss(0, 1) + shift for _ in range(dim)]
    train = [pt() for _ in range(300)]
    held  = [pt() for _ in range(300)]
    anom  = [pt(shift=rng.choice([-4, 4])) for _ in range(300)]
    ns = NegativeSelection(n_detectors=120, target_fpr=0.05, seed=1).fit(train)
    fpr = sum(ns.predict(x) for x in held)/len(held)
    tpr = sum(ns.predict(x) for x in anom)/len(anom)
    assert fpr < 0.15, f"false-positive rate {fpr:.2%} at dimension {dim}"
    assert tpr > 0.85, f"true-positive rate {tpr:.2%} at dimension {dim}"


def test_classification_is_total_and_in_range_under_fuzzing():
    rng = random.Random(11)
    for _ in range(4000):
        n = rng.choice([1, 2, 5, 100, 500])
        f = [rng.random() < 0.5 for _ in range(n)]
        t = None if rng.random() < 0.3 else [rng.random() < 0.5 for _ in range(n)]
        th = Thresholds(min_coverage=rng.choice([0, 0.8, 1]),
                        min_termination=rng.choice([0, 0.7, 1]),
                        max_false_dwell=rng.choice([0, 0.15, 1]),
                        hypersensitivity_ratio=rng.choice([0.1, 2, 1e9]),
                        max_flip_rate=rng.choice([0, 0.05, 1]))
        r = classify(f, t, th)
        m = r.metrics
        assert r.regime.value in VALID
        assert 0 <= m.duty_cycle <= 1 and 0 <= m.flip_rate <= 1
        assert 0 <= m.n_episodes <= n
        for v in (m.termination_rate, m.coverage, m.false_dwell):
            assert math.isnan(v) or 0 <= v <= 1
