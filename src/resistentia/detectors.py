"""
Negative selection: learn what normal looks like, then detect everything else.

Conventional exception management is a threat library — rules enumerate what is
wrong, so anything unenumerated is invisible. Negative selection inverts it:
candidate detectors are generated at random, every one that matches normal
operation is discarded, and the survivors cover the complement. What remains
detects anomalies nobody wrote a rule for.

The classical objection is that this scales badly with dimension. Run it on an
embedding rather than on raw features and the dimension is yours to choose.
"""
from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass, field


def _dist(a: Sequence[float], b: Sequence[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b, strict=True)) ** 0.5


@dataclass
class NegativeSelection:
    """
    self_radius   how close to a normal sample still counts as normal. Leave it as
                  None and it is calibrated from the data to hit ``target_fpr``,
                  which is strongly recommended: a guessed radius silently produces
                  either no detectors or a high false-positive rate, and the failure
                  is invisible until you look at held-out normal data.
    target_fpr    tolerated rate of flagging normal operation, used for calibration
    n_detectors   how many survivors to keep
    max_tries     give up after this many rejected candidates
    seed          reproducibility
    bounds        explicit per-dimension sampling limits. Supply these when the
                  feature space has real physical limits; otherwise a box is
                  inferred from the sample and padded.

        ns = NegativeSelection(self_radius=0.12).fit(normal_samples)
        ns.predict(x)        # True == anomalous
        ns.anomaly_score(x)  # 0 at the edge of self, rising outward
    """
    self_radius: float | None = None
    n_detectors: int = 200
    target_fpr: float = 0.05
    max_tries: int = 100_000
    seed: int | None = 0
    bounds: list[tuple[float, float]] | None = None
    detectors: list[tuple[list[float], float]] = field(default_factory=list)
    _lo: list[float] = field(default_factory=list, repr=False)
    _hi: list[float] = field(default_factory=list, repr=False)
    _self: list[Sequence[float]] = field(default_factory=list, repr=False)

    def fit(self, self_samples: Sequence[Sequence[float]]) -> NegativeSelection:
        if not self_samples:
            raise ValueError("need at least one sample of normal operation")
        d = len(self_samples[0])
        if any(len(s) != d for s in self_samples):
            raise ValueError("all samples must have the same dimension")
        rng = random.Random(self.seed)
        self._self = [list(s) for s in self_samples]
        if self.self_radius is None:
            self.self_radius = self._calibrate(rng)
        self._lo = [min(s[i] for s in self_samples) for i in range(d)]
        self._hi = [max(s[i] for s in self_samples) for i in range(d)]
        span = [max(high - low, 1e-9)
                for low, high in zip(self._lo, self._hi, strict=True)]
        # Widen the sampling box so detectors can sit outside the observed
        # envelope. The margin must exceed self_radius, or a tightly clustered
        # self-set leaves nowhere for a survivor to land.
        if self.bounds is not None:
            if len(self.bounds) != d:
                raise ValueError("bounds must have one pair per dimension")
            lo = [b[0] for b in self.bounds]
            hi = [b[1] for b in self.bounds]
        else:
            pad = [max(0.25 * s, 3.0 * self.self_radius) for s in span]
            lo = [low - m for low, m in zip(self._lo, pad, strict=True)]
            hi = [high + m for high, m in zip(self._hi, pad, strict=True)]
        self.detectors = []
        tries = 0
        while len(self.detectors) < self.n_detectors and tries < self.max_tries:
            tries += 1
            c = [rng.uniform(lo[i], hi[i]) for i in range(d)]
            nearest = min(_dist(c, s) for s in self._self)
            if nearest <= self.self_radius:
                continue                      # matches self — discard, as thymus does
            self.detectors.append((c, nearest - self.self_radius))
        if not self.detectors:
            raise RuntimeError(
                "no detector survived negative selection: self_radius is too large "
                "for this sample, or normal operation fills the space")
        return self

    def _calibrate(self, rng: random.Random) -> float:
        """
        Choose self_radius so that a stated fraction of UNSEEN normal points fall
        outside it. Held out rather than in-sample, because an in-sample radius is
        optimistic by construction and the optimism grows with dimension — which is
        exactly where negative selection is known to fail.
        """
        pts = self._self
        if len(pts) < 8:                       # too few to hold anything out
            near = [min(_dist(p, q) for q in pts if q is not p) for p in pts] \
                   if len(pts) > 1 else [0.0]
            return max(sorted(near)[-1], 1e-9)
        idx = list(range(len(pts)))
        rng.shuffle(idx)
        cut = max(4, int(0.7 * len(idx)))
        train = [pts[i] for i in idx[:cut]]
        held = [pts[i] for i in idx[cut:]]
        d = sorted(min(_dist(h, t) for t in train) for h in held)
        q = min(int(math.ceil((1.0 - self.target_fpr) * len(d))) - 1, len(d) - 1)
        return max(d[max(q, 0)], 1e-9)

    def anomaly_score(self, x: Sequence[float]) -> float:
        """0.0 inside self; grows with distance from the nearest normal sample."""
        if not self._self:
            raise RuntimeError("call fit() first")
        return max(min(_dist(x, s) for s in self._self) - self.self_radius, 0.0)

    def matches(self, x: Sequence[float]) -> int:
        """How many surviving detectors this point activates."""
        return sum(1 for c, r in self.detectors if _dist(x, c) <= r)

    def predict(self, x: Sequence[float]) -> bool:
        return self.anomaly_score(x) > 0.0
