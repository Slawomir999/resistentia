"""
The four failure regimes of a response system.

These are not categories applied by judgement. They are regions of the
controller's parameter space, and each leaves a distinct signature in the
response log — which means an existing alerting system can be diagnosed from
its own history, without instrumenting anything new.

  HEALTHY          responds to real distress, and ends the response
  IMMUNODEFICIENT  misses real distress: coverage low, duty cycle low
  HYPERSENSITIVE   over-responds: duty cycle far above what the truth warrants
  NONTERMINATING   responses start and never end: termination rate low
  AUTOREACTIVE     fires when nothing is wrong: false dwell high

Thresholds are defaults, not laws. Override them for your domain and say so.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from math import isnan
from typing import Sequence
from .metrics import response_metrics, ResponseMetrics


class Regime(str, Enum):
    HEALTHY = "healthy"
    IMMUNODEFICIENT = "immunodeficient"
    HYPERSENSITIVE = "hypersensitive"
    NONTERMINATING = "nonterminating"
    AUTOREACTIVE = "autoreactive"
    UNDETERMINED = "undetermined"


@dataclass
class Thresholds:
    min_coverage: float = 0.80          # below this, distress is being missed
    min_termination: float = 0.70       # below this, responses do not end
    max_false_dwell: float = 0.15       # above this, firing on a clear system
    hypersensitivity_ratio: float = 2.0 # duty cycle vs. fraction of time truly wrong
    max_flip_rate: float = 0.05         # above this, oscillation


@dataclass
class RegimeReport:
    regime: Regime
    metrics: ResponseMetrics
    findings: list[str] = field(default_factory=list)
    thresholds: Thresholds = field(default_factory=Thresholds)

    def __str__(self) -> str:
        m = self.metrics
        lines = [f"regime: {self.regime.value}",
                 f"  duty cycle       {m.duty_cycle:.3f}",
                 f"  episodes         {m.n_episodes}",
                 f"  termination rate {m.termination_rate:.3f}",
                 f"  flip rate        {m.flip_rate:.4f}"]
        if not isnan(m.coverage):
            lines += [f"  coverage         {m.coverage:.3f}",
                      f"  false dwell      {m.false_dwell:.3f}"]
        lines += ["  " + f for f in self.findings]
        return "\n".join(lines)


def classify(firing: Sequence[bool], truth: Sequence[bool] | None = None,
             thresholds: Thresholds | None = None) -> RegimeReport:
    """
    Diagnose a response log. Ordered by severity: a system that never stands down
    is reported as non-terminating even if its coverage is perfect, because a
    response that cannot end is not a response, it is a state.
    """
    th = thresholds or Thresholds()
    m = response_metrics(firing, truth)
    findings: list[str] = []
    regime = Regime.HEALTHY

    if m.n_episodes == 0:
        findings.append("no response at any point in the log")
        regime = Regime.IMMUNODEFICIENT if (truth is not None and any(truth)) \
            else Regime.UNDETERMINED
        return RegimeReport(regime, m, findings, th)

    if not isnan(m.termination_rate) and m.termination_rate < th.min_termination:
        findings.append(
            f"termination rate {m.termination_rate:.2f} below {th.min_termination:.2f} "
            "— responses begin and do not end")
        regime = Regime.NONTERMINATING
    elif truth is not None:
        true_frac = sum(1 for t in truth if t) / len(truth)
        if true_frac == 0.0:
            # Nothing was ever wrong, and it responded anyway. It is reacting to
            # itself: its model of its own normal has drifted.
            findings.append(
                f"active for {m.false_dwell:.0%} of a log in which nothing was wrong "
                "— the system is reacting to itself")
            regime = Regime.AUTOREACTIVE
        elif not isnan(m.coverage) and m.coverage < th.min_coverage:
            # It fires, but not at the real thing. Whether that reads as too
            # little or as misdirected depends on how much it fires when clear.
            if not isnan(m.false_dwell) and m.false_dwell > th.max_false_dwell:
                findings.append(
                    f"coverage {m.coverage:.2f} while active for {m.false_dwell:.0%} of "
                    "the clear time — responding, but not to what is wrong")
                regime = Regime.AUTOREACTIVE
            else:
                findings.append(
                    f"coverage {m.coverage:.2f} below {th.min_coverage:.2f} "
                    "— real distress went unanswered")
                regime = Regime.IMMUNODEFICIENT
        elif m.duty_cycle / true_frac > th.hypersensitivity_ratio:
            findings.append(
                f"duty cycle {m.duty_cycle:.2f} is {m.duty_cycle/true_frac:.1f}x the "
                "fraction of time anything was wrong — response out of proportion")
            regime = Regime.HYPERSENSITIVE

    if m.flip_rate > th.max_flip_rate:
        findings.append(f"flip rate {m.flip_rate:.3f} — the response oscillates")
        if regime is Regime.HEALTHY:
            regime = Regime.HYPERSENSITIVE
    if regime is Regime.HEALTHY:
        findings.append("responds to distress and stands down")
    return RegimeReport(regime, m, findings, th)


def analyse_log(events: Sequence[dict], firing_key: str = "firing",
                truth_key: str | None = "truth",
                thresholds: Thresholds | None = None) -> RegimeReport:
    """
    Diagnose an existing alerting system from its own log.

    ``events`` is any sequence of dicts, one per sample, each carrying at least a
    boolean ``firing``. If a ``truth`` key is present it is used; if not, the
    shape of the response is still enough to detect non-termination and
    oscillation. This is the zero-adoption-cost entry point: point it at what you
    already have.
    """
    firing = [bool(e[firing_key]) for e in events]
    truth = None
    if truth_key and events and truth_key in events[0]:
        truth = [bool(e.get(truth_key, False)) for e in events]
    return classify(firing, truth, thresholds)
