from resistentia import Regime, analyse_log, classify, episodes, response_metrics


def test_episodes_are_half_open_runs():
    assert episodes([False, True, True, False, True]) == [(1, 3), (4, 5)]
    assert episodes([]) == []


def test_healthy_responds_and_stands_down():
    truth  = [False]*10 + [True]*10 + [False]*30 + [True]*10 + [False]*30
    firing = [False]*11 + [True]*10 + [False]*29 + [True]*10 + [False]*30
    r = classify(firing, truth)
    assert r.regime is Regime.HEALTHY


def test_silence_through_real_distress_is_immunodeficiency():
    truth  = [False]*20 + [True]*40 + [False]*40
    r = classify([False]*100, truth)
    assert r.regime is Regime.IMMUNODEFICIENT


def test_a_response_that_never_ends_is_flagged_even_with_perfect_coverage():
    truth  = [False]*10 + [True]*10 + [False]*80
    firing = [False]*10 + [True]*90
    r = classify(firing, truth)
    assert r.regime is Regime.NONTERMINATING


def test_firing_on_a_clear_system_is_autoreactivity():
    truth  = [False]*100
    firing = [False]*20 + [True]*30 + [False]*50
    r = classify(firing, truth)
    assert r.regime is Regime.AUTOREACTIVE


def test_disproportionate_response_is_hypersensitivity():
    truth  = [False]*45 + [True]*10 + [False]*45
    firing = [False]*20 + [True]*50 + [False]*30
    r = classify(firing, truth)
    assert r.regime is Regime.HYPERSENSITIVE


def test_oscillation_is_caught_without_ground_truth():
    firing = [i % 2 == 0 for i in range(100)]
    r = classify(firing)
    assert r.regime is Regime.HYPERSENSITIVE
    assert any("oscillat" in f for f in r.findings)


def test_shape_alone_detects_non_termination():
    r = classify([False]*10 + [True]*90)
    assert r.regime is Regime.NONTERMINATING


def test_analyse_log_reads_dicts_and_survives_a_missing_truth_key():
    ev = [{"firing": False} for _ in range(10)] + [{"firing": True} for _ in range(90)]
    assert analyse_log(ev).regime is Regime.NONTERMINATING


def test_metrics_are_sane():
    m = response_metrics([False, True, True, False], [False, True, True, False])
    assert m.duty_cycle == 0.5 and m.n_episodes == 1
    assert m.termination_rate == 1.0 and m.coverage == 1.0


def test_a_response_still_open_because_the_problem_is_still_open_is_not_a_failure():
    """A sustained breach warrants a sustained response. Only a response that
    outlives its cause counts as a failure to terminate."""
    truth  = [False]*10 + [True]*90
    firing = [False]*12 + [True]*88
    r = classify(firing, truth)
    assert r.regime is not Regime.NONTERMINATING
    assert r.metrics.termination_rate == 1.0


def test_a_response_that_outlives_its_cause_is_still_caught():
    truth  = [False]*10 + [True]*10 + [False]*80
    firing = [False]*10 + [True]*90
    assert classify(firing, truth).regime is Regime.NONTERMINATING
