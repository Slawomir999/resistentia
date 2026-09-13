"""The controller: an activation stock and a lagged suppressor stock."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable, Sequence
from .signals import SignalWindow, fuse


@dataclass
class ControllerConfig:
    """
    gain         how hard the system responds to drive
    tau          suppressor lag, in the same time unit as dt. Long tau means the
                 brake arrives late, which is the signature of hypersensitivity.
    suppression  strength of the negative signal. Zero means the response has no
                 way to end. Conventional alerting has no analogue of this term.
    decay        passive decay of activation
    fire         activation level at which the response is considered active
    window       samples over which signals are fused
    """
    gain: float = 1.0
    tau: float = 8.0
    suppression: float = 1.2
    decay: float = 0.25
    fire: float = 0.30
    window: int = 24

    def __post_init__(self) -> None:
        if self.tau <= 0:
            raise ValueError("tau must be > 0")
        for name in ("gain", "suppression", "decay", "fire"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be >= 0")


@dataclass
class ControllerState:
    t: float = 0.0
    activation: float = 0.0
    suppression: float = 0.0
    drive: float = 0.0
    firing: bool = False


@dataclass
class ResponseController:
    """
    Stateful, streaming. One ``step`` per observation.

        ctl = ResponseController()
        for danger, pamp, safe in stream:
            s = ctl.step(danger=danger, pamp=pamp, safe=safe, dt=0.25)
            if s.firing:
                escalate()

    Nothing here is domain-specific. ``danger`` is whatever your system's
    distress signal is: projected SLO breach, queue growth, error budget burn,
    remaining shelf life. See ``resistentia.kinetics`` for one worked domain.
    """
    config: ControllerConfig = field(default_factory=ControllerConfig)
    state: ControllerState = field(default_factory=ControllerState)
    _wd: SignalWindow = field(init=False, repr=False)
    _wp: SignalWindow = field(init=False, repr=False)
    _ws: SignalWindow = field(init=False, repr=False)

    def __post_init__(self) -> None:
        n = self.config.window
        self._wd, self._wp, self._ws = SignalWindow(n), SignalWindow(n), SignalWindow(n)

    def reset(self) -> None:
        self.state = ControllerState()
        for w in (self._wd, self._wp, self._ws):
            w.reset()

    def step(self, danger: float, pamp: float = 0.0, safe: float = 0.0,
             dt: float = 1.0) -> ControllerState:
        if dt <= 0:
            raise ValueError("dt must be > 0")
        c, s = self.config, self.state
        d = fuse(self._wd.push(danger), self._wp.push(pamp), self._ws.push(safe))
        a_prev, s_prev = s.activation, s.suppression
        a = a_prev + (c.gain * max(d, 0.0)
                      - c.decay * a_prev
                      - c.suppression * s_prev * a_prev) * dt
        sup = s_prev + ((a_prev - s_prev) / c.tau) * dt
        s.t += dt
        s.activation = max(a, 0.0)
        s.suppression = max(sup, 0.0)
        s.drive = d
        s.firing = s.activation > c.fire
        return s

    def run(self, danger: Sequence[float], pamp: Sequence[float] | None = None,
            safe: Sequence[float] | None = None, dt: float = 1.0
            ) -> list[ControllerState]:
        """Batch convenience. Returns a copy of the state at each step."""
        n = len(danger)
        pamp = pamp if pamp is not None else [0.0] * n
        safe = safe if safe is not None else [0.0] * n
        if not (len(pamp) == len(safe) == n):
            raise ValueError("danger, pamp and safe must be the same length")
        self.reset()
        out = []
        for i in range(n):
            st = self.step(danger[i], pamp[i], safe[i], dt)
            out.append(ControllerState(st.t, st.activation, st.suppression,
                                       st.drive, st.firing))
        return out
