# Contributing to Folklore

Thanks for helping. Folklore is small and friendly to first-time contributors.

## Set up

```bash
git clone https://github.com/ravirepswal108-lgtm/FlokFlore
cd FlokFlore
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m playwright install chromium   # for the dashboard tests (optional; they skip without it)
pytest -q
```

The tests run offline on a synthetic fixture with known answers
(`tests/fixtures/synthetic_comments.jsonl`), so you don't need a token to work on Folklore.
To see real results, run it on a real repository:

```bash
export GITHUB_TOKEN=ghp_...   # read access to public repos is enough
folklore run --repo owner/name --no-publish
```

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
| `folklore/report.py` | The review dashboard (HTML, CSS and JS in one file) |
| `folklore/enforce.py` | Pre-review hints for PRs |
| `tests/fixtures/make_synthetic_comments.py` | The synthetic test fixture (edit, then re-run it) |

## Pull request checklist

- `ruff check .` and `ruff format .` pass.
- `pytest -q` passes, and new behaviour has a test.
- If you changed the pipeline, run it on a real repository and look at the report.
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
