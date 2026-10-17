# Starter tasks

Each task below is small enough for one pull request. Maintainers can copy them into
GitHub issues labelled `good first issue` (or `help wanted` for the larger ones).

## Good first issues

1. **Add more bot names to the filter.** Extend `KNOWN_BOTS` in `folklore/filters.py`
   with common review bots you have seen, and add a test case.
2. **More "LGTM" phrasings.** Add low-signal phrases in other languages (for example
   "बढ़िया", "pas mal", "sieht gut aus") to `_LOW_SIGNAL`, with tests.
3. **Language names for areas.** Extend `LANGUAGES` in `folklore/cluster.py` and
   `FENCE_LANG` in `folklore/publish.py` (Elixir, Dart, PHP, Scala, …).
4. **A `--json` flag for `check-diff`.** Print hints as JSON so editors and pre-commit
   hooks can use them.
5. **A pre-commit hook.** Add `.pre-commit-hooks.yaml` so projects can run
   `folklore check-diff` on staged changes.
6. **Report: copy a rule as Markdown.** Add a button in `report.py` that copies one rule
   as a Markdown snippet for issues and chats.
7. **Report: keyboard shortcuts.** Add `/` to focus search and `a` / `r` to approve or
   reject the focused rule in the dashboard, with a browser test.
8. **More injection patterns.** Add attack phrasings to `sanitize.py` with tests that
   prove ordinary code comments are not removed.
9. **Test fixture: a Python project.** Extend `tests/fixtures/make_synthetic_comments.py`
   with Python review conventions and add tests that expect them.
10. **Docs: a Windows quick start** in the README.

## Help wanted (bigger)

1. **GraphQL miner.** Fetch review threads (with their resolved state) through the
   GraphQL API to cut the number of requests on large repositories.
2. **Recover the fix from later commits.** When a comment has no suggestion block, find
   the next commit that touched the same lines and use it as the "after" example.
3. **Per-rule feedback.** Read 👍/👎 reactions on bot comments and retire rules that keep
   getting 👎.
4. **Linter export.** For rules with a detection pattern, generate an ESLint
   `no-restricted-syntax` / `no-restricted-imports` rule or a Ruff config snippet.
5. **GitLab support.** Mine merge-request discussions through the GitLab API.
6. **Evaluation set.** Hand-label clusters from three public repositories and add a script
   that reports precision, so clustering changes can be measured.
7. **Sentence-transformers embedder.** An optional local embedder (`pip install
   folklore-skills[local]`) for better offline clustering.
