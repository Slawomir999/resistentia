"""Signal fusion. Three channels, fused over a temporal window."""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass


def fuse(danger: float, pamp: float, safe: float,
         w_pamp: float = 1.5, w_pamp_direct: float = 0.35,
         w_safe: float = 0.8) -> float:
    """
    Fuse three channels into a single activation drive.

    danger  distress in the protected system — the thing you actually care about
    pamp    an unambiguous threat signature (a known-bad pattern)
    safe    positive evidence that conditions are benign

    The governing rule, taken from danger theory: a threat SIGNATURE without a
    distress CONTEXT induces tolerance, not immunity. So ``pamp`` MULTIPLIES the
    danger channel rather than adding to it. A signature on its own contributes
    only ``w_pamp_direct``, which should be small.

    This is the single line that separates this from threshold alerting, and it is
    why a system built on it does not fire on a dramatic but harmless event.
    """
    return danger * (1.0 + w_pamp * pamp) + w_pamp_direct * pamp - w_safe * safe


@dataclass
class SignalWindow:
    """Rolling mean over a fixed number of samples. Immune recognition is a
    temporal correlation, not an instantaneous test."""
    size: int

    def __post_init__(self) -> None:
        if self.size < 1:
            raise ValueError("window size must be >= 1")
        self._buf: deque[float] = deque(maxlen=self.size)
        self._sum = 0.0

    def push(self, x: float) -> float:
        if len(self._buf) == self._buf.maxlen:
            self._sum -= self._buf[0]
        self._buf.append(x)
        self._sum += x
        return self._sum / len(self._buf)

    @property
    def value(self) -> float:
        return self._sum / len(self._buf) if self._buf else 0.0

    def reset(self) -> None:
        self._buf.clear()
        self._sum = 0.0
