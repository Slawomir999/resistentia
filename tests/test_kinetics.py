import math, pytest
from resistentia import kinetics as K


def test_mkt_of_constant_trace_is_that_temperature():
    assert K.mean_kinetic_temperature([7.0] * 50) == pytest.approx(7.0, abs=1e-9)


def test_mkt_exceeds_arithmetic_mean_for_a_varying_trace():
    trace = [2.0] * 50 + [12.0] * 50
    assert K.mean_kinetic_temperature(trace) > sum(trace) / len(trace)


def test_calibration_reproduces_the_stated_shelf_life():
    ea = 120_000.0
    a = K.calibrate_pre_exponential(ref_temp_c=5, ea=ea, fraction_remaining=0.9, after=720)
    p = K.integrate_potency([5.0] * 720, dt=1.0, ea=ea, pre_exponential=a)
    assert p[-1] == pytest.approx(0.9, abs=1e-6)


def test_degradation_is_monotone_and_faster_when_warmer():
    ea = 120_000.0
    a = K.calibrate_pre_exponential(ref_temp_c=5, ea=ea, fraction_remaining=0.9, after=720)
    cold = K.integrate_potency([4.0] * 240, 1.0, ea, a)
    warm = K.integrate_potency([9.0] * 240, 1.0, ea, a)
    assert all(x >= y for x, y in zip(cold, cold[1:]))
    assert warm[-1] < cold[-1]


def test_burn_ratio_above_one_predicts_a_breach_and_the_prediction_holds():
    ea, spec = 120_000.0, 0.90
    a = K.calibrate_pre_exponential(ref_temp_c=5, ea=ea, fraction_remaining=0.9, after=720)
    p0, temp, horizon = 0.945, 7.7, 240.0
    br = K.burn_ratio(p0, temp, spec, horizon, ea, a)
    final = K.integrate_potency([temp] * int(horizon), 1.0, ea, a, initial=p0)[-1]
    assert br > 1.0
    assert final < spec          # the signal was right


def test_burn_ratio_below_one_predicts_survival_and_the_prediction_holds():
    ea, spec = 120_000.0, 0.90
    a = K.calibrate_pre_exponential(ref_temp_c=5, ea=ea, fraction_remaining=0.9, after=720)
    p0, temp, horizon = 0.945, 4.0, 240.0
    assert K.burn_ratio(p0, temp, spec, horizon, ea, a) < 1.0
    assert K.integrate_potency([temp] * int(horizon), 1.0, ea, a, initial=p0)[-1] > spec


def test_exhausted_budget_is_infinite_burn():
    assert math.isinf(K.burn_ratio(0.89, 4.0, 0.90, 10.0, 120_000.0, 1.0))
