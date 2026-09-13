"""Metrics computed from a response log. These are what the regimes are read from."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


def episodes(firing: Sequence[bool]) -> list[tuple[int, int]]:
    """Contiguous runs of firing, as half-open [start, end) index pairs."""
    out, start = [], None
    for i, f in enumerate(firing):
        if f and start is None:
            start = i
        elif not f and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(firing)))
    return out


@dataclass
class ResponseMetrics:
    n: int
    duty_cycle: float          # fraction of time the response was active
    n_episodes: int
    mean_dwell: float          # mean episode length, in samples
    max_dwell: float
    termination_rate: float    # fraction of episodes that ended before the log did
    flip_rate: float           # transitions per sample — oscillation
    coverage: float            # fraction of true-positive intervals with any response
    false_dwell: float         # fraction of time active while nothing was wrong

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def response_metrics(firing: Sequence[bool],
                     truth: Sequence[bool] | None = None) -> ResponseMetrics:
    """
    firing  did the system have an active response at this sample
    truth   optional ground truth: was something actually wrong at this sample

    ``coverage`` and ``false_dwell`` require truth; without it they are NaN and
    only the shape of the response is measured. That still identifies
    non-termination and oscillation, which is most of the value.
    """
    n = len(firing)
    if n == 0:
        raise ValueError("empty log")
    eps = episodes(firing)
    lens = [b - a for a, b in eps]
    duty = sum(lens) / n
    # An episode still open at the end of the log has not failed to terminate if
    # the distress it answers is also still open. Only a response that outlives
    # its cause is a termination failure.
    still_warranted = bool(truth) and bool(truth[-1]) if truth is not None else False
    terminated = sum(1 for a, b in eps if b < n or still_warranted)
    flips = sum(1 for i in range(1, n) if firing[i] != firing[i - 1])
    if truth is None:
        cov = fd = float("nan")
    else:
        if len(truth) != n:
            raise ValueError("truth must be the same length as firing")
        t_eps = episodes(truth)
        hit = sum(1 for a, b in t_eps if any(firing[a:b]))
        cov = hit / len(t_eps) if t_eps else float("nan")
        clear = [i for i in range(n) if not truth[i]]
        fd = (sum(1 for i in clear if firing[i]) / len(clear)) if clear else float("nan")
    return ResponseMetrics(
        n=n, duty_cycle=duty, n_episodes=len(eps),
        mean_dwell=(sum(lens) / len(lens)) if lens else 0.0,
        max_dwell=float(max(lens)) if lens else 0.0,
        termination_rate=(terminated / len(eps)) if eps else float("nan"),
        flip_rate=flips / n, coverage=cov, false_dwell=fd,
    )
