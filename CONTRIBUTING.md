# Contributing to Folklore

Thanks for helping. Folklore is small and friendly to first-time contributors.

## Set up

```bash
git clone https://github.com/your-org/folklore
cd folklore
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q
folklore demo
```

Everything runs offline. You do not need a GitHub token or an AI service to work on
Folklore; the bundled demo data and the tests cover the whole pipeline.

## Find something to work on

- [docs/good-first-issues.md](docs/good-first-issues.md) lists starter tasks.
- Issues labelled `good first issue` or `help wanted`.
- Comment on an issue before starting so a maintainer can assign it to you and nobody
  duplicates work.

## Where things live

| File | Stage |
|---|---|
| `folklore/mine.py`, `folklore/github.py` | Read review history from GitHub |
| `folklore/filters.py` | Keep maintainer feedback, drop noise |
| `folklore/embed.py`, `folklore/cluster.py` | Group similar feedback, weigh evidence |
| `folklore/distill.py`, `folklore/llm.py` | Phrase rules, pick examples, detection patterns |
| `folklore/sanitize.py` | Keep untrusted text out of agent instructions |
| `folklore/publish.py` | Write and validate the Agent Skill |
| `folklore/report.py` | The HTML report |
| `folklore/enforce.py` | Pre-review hints for PRs |
| `scripts/make_demo_data.py` | The demo dataset (edit this, then re-run it) |

## Pull request checklist

- `ruff check .` and `ruff format .` pass.
- `pytest -q` passes, and new behaviour has a test.
- If you changed the pipeline, run `folklore demo` and look at the report.
- Keep PRs focused: one change per PR is easier to review.

## House rules (yes, Folklore has its own folklore)

- Keep the report palette free of blue. `tests/test_report.py` checks it.
- Generated text never includes contributor names.
- Anything copied from a pull request goes through `sanitize.py` first.
- Prefer a deterministic check over an LLM call when both would work.
- No new runtime dependency without discussing it in an issue first.

## Code of conduct

Be kind and assume good intent. We follow the
[Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
Report problems privately to the maintainers.
