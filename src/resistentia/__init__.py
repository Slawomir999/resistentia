"""
resistentia — response termination for autonomous systems.

Activation is solved. Termination is not. Alerting stacks, monitoring systems and
agent loops all have a path that starts a response and no path that ends one.
This library supplies the missing organ: a suppressor.

Derived from immunoregulation, where a response is ended by an active negative
signal rather than by the disappearance of the stimulus, and where a pathogen
signature without a distress context produces tolerance instead of immunity.

Origin: S. Wyciślak, "Koncepcja rezystencji polskich przedsiębiorstw w warunkach
działania na rynku międzynarodowym", Akademia Ekonomiczna w Krakowie, 2003 —
where the layered response architecture and the three response pathologies
(immunodeficiency, hypersensitivity, autodestruction) were first set out.
"""
from .controller import ResponseController, ControllerConfig, ControllerState
from .signals import SignalWindow, fuse
from .detectors import NegativeSelection
from .metrics import episodes, response_metrics, ResponseMetrics
from .regimes import Regime, classify, RegimeReport, analyse_log
from . import kinetics

__version__ = "0.1.0"
__all__ = [
    "ResponseController", "ControllerConfig", "ControllerState",
    "SignalWindow", "fuse", "NegativeSelection",
    "episodes", "response_metrics", "ResponseMetrics",
    "Regime", "classify", "RegimeReport", "analyse_log", "kinetics",
]
