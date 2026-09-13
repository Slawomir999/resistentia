# RTS-1 — Response Termination Specification

**Version** 0.1 (draft) · **Status** open for comment · **Licence** CC BY 4.0

---

## 1. Scope

This specification defines a portable format for the **response log** of an automated
or semi-automated system, and the **regime signatures** that may be computed from it.

It applies to any system that observes a stream and can enter and leave an active
response state: alerting and monitoring stacks, exception-management platforms,
industrial control, clinical decision support, and autonomous or semi-autonomous
agents acting on operational systems.

It is deliberately narrow. It specifies how to *describe* and *diagnose* a response
system. It does not specify how one should be built. A conforming system may use any
internal mechanism.

## 2. Motivation

Systems that act are routinely evaluated on whether they act correctly. They are almost
never evaluated on whether they **stop**. The consequences are familiar and unmeasured:
alerts nobody closes, escalations that outlive their cause, automated responses that
persist after the condition has cleared, and operators who learn to ignore a channel
that is permanently lit.

The omission is structural rather than accidental. A threshold rule has an activation
condition and no termination condition; nothing in its design has a place to put one.
Naming termination as a first-class property, with a defined measurement, is the
precondition for improving it.

## 3. Terminology

The key words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are to be interpreted as in
RFC 2119.

| term | definition |
|---|---|
| **sample** | one observation of the system at a point in time |
| **firing** | the response was active during that sample |
| **episode** | a maximal contiguous run of firing samples |
| **termination** | an episode that ends while the log continues |
| **warranted** | at that sample, a condition existed that the response should answer |
| **duty cycle** | fraction of samples in which the response was firing |
| **coverage** | fraction of warranted intervals containing at least one firing sample |
| **false dwell** | fraction of unwarranted samples in which the response was firing |
| **flip rate** | transitions between firing and not-firing, per sample |

## 4. The response log

A response log is a time-ordered sequence of records at a stated, constant interval.

Each record MUST contain:

| field | type | meaning |
|---|---|---|
| `t` | number or RFC 3339 string | sample time |
| `firing` | boolean | the response was active during this sample |

Each record SHOULD contain, where determinable:

| field | type | meaning |
|---|---|---|
| `truth` | boolean | a condition warranting response existed during this sample |

Each record MAY contain:

| field | type | meaning |
|---|---|---|
| `activation` | number ≥ 0 | internal activation level |
| `suppression` | number ≥ 0 | internal termination pressure, where one exists |
| `subject` | string | the entity the response concerns |
| `class` | string | response type or channel |

Line-delimited JSON is the RECOMMENDED interchange form.

```json
{"t": "2026-09-13T07:00:00Z", "firing": false, "truth": false}
{"t": "2026-09-13T07:15:00Z", "firing": true,  "truth": true}
```

`truth` is frequently unavailable at the time of logging and MAY be attached
retrospectively from outcome records — an incident register, a release or rejection
decision, a post-mortem. Retrospective attachment MUST be disclosed alongside any
reported metric.

## 5. Derived metrics

Given a log of `n` samples, a conforming implementation MUST compute:

```
duty_cycle       = |{i : firing[i]}| / n
n_episodes       = number of maximal contiguous firing runs
termination_rate = |{e : e ends before n, or truth[n-1] is true}| / n_episodes
flip_rate        = |{i > 0 : firing[i] ≠ firing[i-1]}| / n
```

and, where `truth` is present:

```
coverage    = |{warranted intervals containing a firing sample}| / |warranted intervals|
false_dwell = |{i : firing[i] ∧ ¬truth[i]}| / |{i : ¬truth[i]}|
```

**Note on the final episode.** An episode still open at the end of the log MUST be
counted as terminated when `truth` is true at the final sample. A response that remains
active because its cause remains active has not failed to terminate. Only a response
that outlives its cause is a termination failure. Implementations that omit this
adjustment will report false positives on every log that ends mid-incident.

## 6. Regimes

A conforming implementation MUST assign exactly one regime, evaluated in this order.
Default thresholds are given; an implementation MAY override any of them and MUST
report the values used.

| # | regime | condition | default |
|---|---|---|---|
| 0 | `immunodeficient` | no episodes, and `truth` contains a warranted sample | — |
| 0 | `undetermined` | no episodes, and `truth` absent or never warranted | — |
| 1 | `nonterminating` | `termination_rate < θ_term` | θ_term = 0.70 |
| 2 | `autoreactive` | `truth` present and never warranted, while `duty_cycle > 0` | — |
| 3 | `autoreactive` | `coverage < θ_cov` **and** `false_dwell > θ_false` | θ_false = 0.15 |
| 3 | `immunodeficient` | `coverage < θ_cov` otherwise | θ_cov = 0.80 |
| 4 | `hypersensitive` | `duty_cycle / warranted_fraction > θ_ratio` | θ_ratio = 2.0 |
| 5 | `hypersensitive` | `flip_rate > θ_flip`, if not already classified | θ_flip = 0.05 |
| — | `healthy` | none of the above | — |

The ordering is deliberate. A system that never stands down is reported as
non-terminating even when its coverage is perfect, because a response that cannot end
is not a response but a state.

Thresholds are engineering defaults, not findings. A domain in which sustained response
is normal — continuous process control, life support — SHOULD raise θ_term and say so.

## 7. Conformance

**Level 0 — Log.** Emits a response log satisfying §4 with the required fields.

**Level 1 — Diagnosable.** Level 0, plus `truth` attached for at least one bounded
evaluation window, plus the §5 metrics published for that window.

**Level 2 — Terminating.** Level 1, plus: for each response class, a documented
termination condition that is not merely the negation of the activation condition, and
a measured `termination_rate` at or above θ_term over the evaluation window.

Level 2 is the point of the specification. A system reaches it only by having an answer
to the question *what makes this response end*, which most systems presently do not.

## 8. Reference implementation

`resistentia` (Python, MIT). Conformance to this specification does not require it.

## 9. Security and privacy

A response log describes what a system noticed and when it stopped looking. Published
without care it discloses detection coverage and blind spots. Logs SHOULD be aggregated
or delayed before publication, and `subject` SHOULD be pseudonymised.

## 10. Open questions

- Whether `θ_term` should be fixed or derived from the distribution of warranted
  interval lengths in the domain.
- How to express a graded response, where firing is not boolean but has intensity.
- Whether coverage should be interval-weighted rather than interval-counted, so a long
  missed incident weighs more than a short one.
- Whether the regimes are exhaustive. They were derived from three pathologies in a
  2003 dissertation, and a fourth and fifth were added while implementing. There is no
  argument that the list is closed.

## 11. Provenance

The three original regimes — immunodeficiency, hypersensitivity, autodestruction — were
tabulated as organisational disease entities, with etiology, symptoms at three levels
and a three-phase course, in:

> S. Wyciślak, *Koncepcja rezystencji polskich przedsiębiorstw w warunkach działania na
> rynku międzynarodowym*, Akademia Ekonomiczna w Krakowie, 2003, Tables 4.3–4.5.

`nonterminating` and `undetermined` were added here. The underlying immunological
account of response termination by an active negative signal, and of tolerance to a
threat signature presented without a distress context, follows danger theory and its
algorithmic treatments.

---

*Comments and conforming implementations are welcome. Open an issue.*
