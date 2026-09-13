# resistentia

**Activation is solved. Termination is not.**

Alerting stacks, monitoring systems and agent loops all have a path that starts a
response. Almost none has a path that ends one. The result is the failure mode every
operations team knows and no framework names: alerts that are never closed, dashboards
red for months, agents that keep acting after the reason has passed.

Biology solved this. An immune response is not ended by the disappearance of the
stimulus — it is ended by an **active negative signal** from a suppressor population
that grows behind the response and shuts it down. `resistentia` supplies that missing
organ, as a small dependency-free library.

```bash
pip install resistentia
```

---

## The three things it does

### 1. Diagnose an alerting system you already run

No new instrumentation. Feed it the log you already have.

```python
from resistentia import analyse_log

print(analyse_log(my_alert_log))     # [{"firing": bool, "truth": bool}, ...]
```

```
regime: nonterminating
  duty cycle       0.900
  episodes         1
  termination rate 0.000
  coverage         1.000
  false dwell      0.891
  termination rate 0.00 below 0.70 — responses begin and do not end
```

Five regimes, read from the shape of the response rather than from opinion:

| regime | what it means | signature in the log |
|---|---|---|
| `healthy` | responds to distress, then stands down | high coverage, high termination |
| `immunodeficient` | misses real distress | low coverage, low duty cycle |
| `hypersensitive` | responds out of proportion | duty cycle ≫ time anything was wrong |
| `nonterminating` | responses start and never end | low termination rate |
| `autoreactive` | fires when nothing is wrong | high false dwell — the system is reacting to itself |

Ground truth is optional. Without it, non-termination and oscillation are still detected,
which is most of what is wrong with most alerting.

### 2. Run a controller that can stop

```python
from resistentia import ResponseController, ControllerConfig

ctl = ResponseController(ControllerConfig(gain=1.0, tau=8.0, suppression=1.2))

for danger, signature, safe in stream:
    s = ctl.step(danger=danger, pamp=signature, safe=safe, dt=0.25)
    if s.firing:
        escalate()
```

Two coupled stocks, one differential equation each:

```
dA/dt = gain · drive − decay · A − suppression · S · A
dS/dt = (A − S) / tau
```

`A` is activation. `S` is the suppressor, and it **lags** — which is why the response
does not die the instant the drive dips, and why a long `tau` with weak `suppression`
produces exactly the oscillating, never-closing behaviour of a badly tuned pager.

Set `suppression=0.0` and you have reproduced conventional alerting.

### 3. Fuse signals the way danger theory says to

```python
drive = danger · (1 + 1.5 · pamp) + 0.35 · pamp − 0.8 · safe
```

A threat **signature** without a distress **context** produces tolerance, not a
response. `pamp` *multiplies* the danger channel instead of adding to it. That one
line is the difference between a system that fires on every dramatic-but-harmless
event and one that does not, and it is not a rule you would arrive at from alerting
practice.

`danger` is whatever distress means in your system: projected SLO breach, error-budget
burn rate, queue growth, remaining shelf life.

---

## Also included

**Negative selection** (`NegativeSelection`) — the inversion of a threat library.
Generate candidate detectors at random, discard every one that matches normal
operation, keep the survivors. What remains detects anomalies nobody wrote a rule for.
When normal operation fills the space, it raises rather than returning an empty defence.

**Arrhenius kinetics** (`resistentia.kinetics`) — one worked domain where the general
problem is unmistakable: the observable variable is not the variable that decides the
outcome. Temperature is observable and reversible; accumulated damage is latent and
irreversible. Includes mean kinetic temperature and the **burn ratio**:

```
burn_ratio = time_left / (ln(P / spec) / k(T))
```

time you need against time you have. Above 1.0 means a breach is projected while
there is still time to act. Under constant conditions the prediction is exact.

---

## The demonstration

```bash
python examples/coldchain.py
```

One product, one ten-day lane, four temperature histories:

| lane | peak °C | MKT °C | arrives | verdict | threshold rule | resistentia |
|---|---|---|---|---|---|---|
| clean | 4.00 | 4.00 | 91.79% | pass | silent | silent |
| **chronic** | **7.70** | 7.05 | **89.72%** | **FAIL** | **silent** | alarm, 204 h lead |
| spiky | 15.00 | 4.28 | 91.58% | pass | 3.0 h | silent |
| wobble | 9.50 | 5.21 | 91.01% | pass | 40.0 h | 29.8 h |

The chronic lane never crosses the 8 °C alert limit and arrives out of specification. A
threshold rule is silent for its entire duration. The spiky lane crosses 15 °C four
times and arrives perfectly fine.

**This is a simulation.** Every number is a property of the model, not an empirical
finding. `Ea` is the model's key free parameter and must be measured per product. The
model is offered because it is falsifiable: run it against real logger traces and
release records and it will be wrong in a specific, reportable way.

---

## Verification

Passing tests written by the same person who wrote the code prove internal consistency,
not correctness. So the suite also checks the implementation against things outside it:

| what | against | result |
|---|---|---|
| Mean kinetic temperature | its own defining equation, `k(MKT) = mean k(Tᵢ)`, on random traces | agrees to 2×10⁻¹⁴ |
| Potency integration | the closed-form solution, and `scipy.solve_ivp` at `rtol=1e-11` | 4×10⁻⁸ relative |
| Burn ratio | the analytic outcome, 50,000 randomised constant-temperature cases | exact, no disagreement |
| Controller ODE | `scipy.solve_ivp` on identical forcing, 12 random parameter sets | 2.4% worst endpoint error at `dt=0.25` |
| Controller stability | 125-point parameter sweep | no NaN, negative or runaway state |
| Regime classifier | the independent JavaScript implementation in `docs/`, 4,000 random logs | identical regime and all six metrics to 1e-9 |
| Detector | held-out normal and unseen anomalies, dimensions 2 to 20 | 1.5–6.2% false positives against a 5% target, 100% detection |
| Robustness | 30,000 fuzzed inputs | no unhandled exception, no metric out of range |

Two defects were found this way and fixed:

- The burn ratio was a first-order approximation that over-warned near the boundary —
  117 disagreements in 20,000 cases, all in the safe direction, none missed. Replaced
  with the exact time-to-spec form.
- `NegativeSelection` shipped a guessed default radius, which produced a 35%
  false-positive rate at dimension 8 — the classical failure of negative selection.
  The radius is now calibrated from held-out normal data to a stated target rate.

## Specification

The response-log format and the regime signatures are specified separately in
[SPEC.md](SPEC.md) so that other implementations can conform without using this code.

---

## Provenance

The architecture is not new. It was set out in 2003, in Polish, in a doctoral
dissertation that applied immunology and clinical method to enterprise risk:

> S. Wyciślak, *Koncepcja rezystencji polskich przedsiębiorstw w warunkach działania na
> rynku międzynarodowym*, Akademia Ekonomiczna w Krakowie, Wydział Ekonomii, 2003.

That thesis defined **rezystencja** (Latin *resistentia*) as a property of the threat
rather than of the system — the non-susceptibility of a disturbing factor to the
countermeasures directed against it — described a layered response architecture, and
tabulated three response pathologies: immunodeficiency, hypersensitivity, autodestruction.
It declined to build the mathematics, on the grounds that the qualitative aspects
mattered more. This library is that declined step.

## Releasing

You do not need a local Python installation. `.github/workflows/release.yml` builds
and publishes to PyPI when you create a GitHub Release, using PyPI trusted publishing
— no API token is stored anywhere. One-time setup is three steps in a browser and is
documented at the top of that file.

## Licence

MIT.
