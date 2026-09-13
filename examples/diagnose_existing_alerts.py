"""
Zero-adoption-cost entry point: diagnose an alerting system you already run.

No new instrumentation. Feed it the log you already have — one record per
sample, each with a boolean saying whether an alert was active. Ground truth is
optional; without it the shape of the response still exposes non-termination and
oscillation, which is most of what is wrong with most alerting.

    python examples/diagnose_existing_alerts.py
"""
from resistentia import analyse_log

logs = {
    "team A — pager": (
        [{"firing": False, "truth": False}] * 40 +
        [{"firing": True,  "truth": True}] * 12 +
        [{"firing": False, "truth": False}] * 48
    ),
    "team B — 'the alert nobody closes'": (
        [{"firing": False, "truth": False}] * 10 +
        [{"firing": True,  "truth": True}] * 8 +
        [{"firing": True,  "truth": False}] * 82
    ),
    "team C — flapping threshold": (
        [{"firing": i % 2 == 0, "truth": False} for i in range(100)]
    ),
    "team D — silent through an outage": (
        [{"firing": False, "truth": False}] * 30 +
        [{"firing": False, "truth": True}] * 30 +
        [{"firing": False, "truth": False}] * 40
    ),
}

for name, log in logs.items():
    print(f"\n=== {name} ===")
    print(analyse_log(log))
