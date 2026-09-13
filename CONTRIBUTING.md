# Contributing

```bash
git clone <this repo> && cd resistentia
pip install -e ".[dev]"
pytest -q
ruff check src tests
```

Two rules specific to this project.

**Every borrowed mechanism must earn its keep.** A concept taken from immunology stays
only if it produces a design rule or a testable prediction that would not otherwise have
been chosen. Vocabulary alone is not a contribution and will be removed.

**No claim stronger than the evidence.** The kinetics module is a model. Say so where
it matters, and keep the free parameters visible rather than buried.

Regime thresholds are engineering defaults. If your domain needs different ones, that is
a finding worth an issue, not a fork.
