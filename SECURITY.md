# Security policy

Folklore copies text written by anyone who opens a pull request into files that coding
agents read as trusted instructions, and it runs as a GitHub Action with permission to
comment on pull requests. We take both seriously.

## Reporting a vulnerability

Please do not open a public issue. Use GitHub's private vulnerability reporting
("Security" tab → "Report a vulnerability") on this repository. We aim to reply within
seven days.

Especially welcome:

- A way to get instruction-like text from a pull request into a generated `SKILL.md` or
  reference file.
- A way for a pull request to change the rules it is checked against, or to run code in
  the pre-review workflow.
- A way to make the bot post attacker-controlled text.

## What Folklore does to stay safe

- Quoted code passes through `folklore/sanitize.py`: instruction-like lines are removed,
  code fences are neutralized, length is capped, and examples are labelled as data.
- Rule sources are attached by Folklore from the mined data, never by a model, and code a
  model picks must exist verbatim in the cited diff.
- The example workflow checks out the base branch only and reads the PR as a diff
  through the API. It never builds, installs or runs PR code.
- In LLM mode, model output is only accepted when it names an existing rule ID, changed
  file and added line. The comment text always comes from the rules file.

## Supported versions

Only the latest release receives security fixes.
