"""
The worked demonstration: four cold-chain lanes, one product, ten days.

Shows the central claim — a threshold rule on the observable variable is silent
through the lane that actually fails, and fires on the lane that does not.

    python examples/coldchain.py
"""
from resistentia import ResponseController, ControllerConfig, classify
from resistentia import kinetics as K

DT, HOURS = 0.25, 240.0
N = int(HOURS / DT)
EA, SPEC, P0, LIMIT = 120_000.0, 0.90, 0.945, 8.0
A_PRE = K.calibrate_pre_exponential(ref_temp_c=5, ea=EA, fraction_remaining=0.9, after=720)

LANES = {
    "clean":   lambda i: 4.0,
    "chronic": lambda i: 7.7 if 30 <= i * DT < 220 else 4.0,          # never breaches 8.0
    "spiky":   lambda i: 15.0 if any(s <= i * DT < s + 0.75
                                     for s in (30, 80, 130, 180)) else 4.0,
    "wobble":  lambda i: 9.5 if any(s <= i * DT < s + 8
                                    for s in (25, 70, 115, 160, 205)) else 4.0,
}


def run(name):
    temps = [LANES[name](i) for i in range(N)]
    potency = K.integrate_potency(temps, DT, EA, A_PRE, initial=P0)
    ctl = ResponseController(ControllerConfig(window=int(6 / DT)))
    fired, truth = [], []
    for i, (t, p) in enumerate(zip(temps, potency)):
        br = K.burn_ratio(p, t, SPEC, HOURS - i * DT, EA, A_PRE)
        s = ctl.step(danger=min(max((br - 1.0) * 3.0, 0.0), 4.0),
                     pamp=1.0 if t > 12.0 else 0.0,
                     safe=1.0 if br < 0.6 else 0.0, dt=DT)
        fired.append(s.firing)
        truth.append(br > 1.0)          # ground truth: a breach is projected
    threshold = [t > LIMIT for t in temps]
    return temps, potency, fired, threshold, truth


print(f"{'lane':9}{'peak °C':>9}{'MKT °C':>8}{'arrives':>9}{'verdict':>9}"
      f"{'threshold':>11}{'resistentia':>13}{'lead h':>8}")
print("-" * 76)
for name in LANES:
    temps, potency, fired, threshold, truth = run(name)
    failed = potency[-1] < SPEC
    th_h = sum(threshold) * DT
    dg_h = sum(fired) * DT
    first = next((i * DT for i, f in enumerate(fired) if f), None)
    print(f"{name:9}{max(temps):9.2f}{K.mean_kinetic_temperature(temps):8.2f}"
          f"{potency[-1]*100:8.2f}%{('FAIL' if failed else 'pass'):>9}"
          f"{(f'{th_h:.1f} h' if th_h else 'silent'):>11}"
          f"{(f'{dg_h:.1f} h' if dg_h else 'silent'):>13}"
          f"{(f'{HOURS-first:.0f}' if first is not None else '—'):>8}")

print("\nThe chronic lane never crosses 8.0 °C and arrives out of specification.")
print("A threshold rule on temperature is silent for its entire duration.\n")
_, _, fired, _, truth = run("chronic")
print(classify(fired, truth))
