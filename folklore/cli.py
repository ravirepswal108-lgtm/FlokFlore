"""Command-line interface: `folklore <command>`."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from . import __version__
from .analyze import analyze, load_analysis, rules_from_analysis, save_analysis
from .config import CONFIG_FILE, Config, write_default_config
from .enforce import MARKER, check, parse_patch, parse_unified_diff, render_comment
from .github import GitHubClient, GitHubError
from .llm import LLMError, OpenAICompatClient
from .mine import load_comments, mine, save_comments
from .models import Rule
from .publish import publish, skill_name, update_agents_md, validate_skill
from .report import write_report

WORK_DIR = Path(".folklore")
COMMENTS = WORK_DIR / "comments.jsonl"
ANALYSIS = WORK_DIR / "analysis.json"
REPORT = WORK_DIR / "report.html"


def say(msg: str) -> None:
    print(msg, file=sys.stderr)


def fail(msg: str, code: int = 1) -> int:
    say(f"error: {msg}")
    return code


def _token() -> str:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""


def _now(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _summary(analysis: dict) -> None:
    s = analysis["stats"]
    say(
        f"Read {s['feedback_total']} pieces of feedback, kept {s['feedback_kept']}, "
        f"found {s['clusters']} recurring patterns and {s['rules']} rules "
        f"({s['stale']} stale, {s['discarded']} set aside, {s['rejected']} rejected)."
    )
    for i, rule in enumerate(analysis["rules"], 1):
        ev = rule["evidence"]
        say(
            f"  {i:2}. {rule['title']}  [{', '.join(rule['scope'])}]  {ev['comments']}× in {ev['prs']} PRs"
        )


# -- commands -------------------------------------------------------------------------


def cmd_init(args) -> int:
    if Path(args.config).exists() and not args.force:
        return fail(f"{args.config} already exists (use --force to overwrite)")
    write_default_config(args.config, args.repo or "")
    say(f"Wrote {args.config}. Edit it, then run: folklore run")
    return 0


def cmd_mine(args) -> int:
    cfg = Config.load(args.config)
    repo = args.repo or cfg.repo
    if not repo:
        return fail("say which repository to read: --repo owner/name")
    client = GitHubClient(_token())
    try:
        comments = mine(client, repo, args.max_prs or cfg.max_prs, cfg.include_review_bodies, say)
    except GitHubError as exc:
        return fail(str(exc))
    save_comments(comments, args.out)
    say(f"Saved {len(comments)} comments to {args.out}")
    return 0


def _analyze(args, cfg: Config, comments_path: Path, repo: str) -> dict:
    comments = load_comments(comments_path)
    analysis = analyze(comments, cfg, now=_now(getattr(args, "now", None)), repo=repo)
    save_analysis(analysis, args.analysis)
    return analysis


def cmd_analyze(args) -> int:
    cfg = Config.load(args.config)
    if not Path(args.comments).exists():
        return fail(f"{args.comments} not found; run `folklore mine` first")
    try:
        analysis = _analyze(args, cfg, Path(args.comments), args.repo or cfg.repo)
    except LLMError as exc:
        return fail(str(exc))
    _summary(analysis)
    say(f"Saved analysis to {args.analysis}")
    return 0


def cmd_report(args) -> int:
    if not Path(args.analysis).exists():
        return fail(f"{args.analysis} not found; run `folklore analyze` first")
    path = write_report(load_analysis(args.analysis), args.out, standalone=not args.fragment)
    say(f"Wrote report to {path}")
    return 0


def _publish(analysis: dict, skills_dir: str, agents_md: bool) -> int:
    repo = analysis.get("repo") or "project"
    rules = rules_from_analysis(analysis)
    if not rules:
        say("No rules to publish.")
        return 0
    skill_dir = publish(rules, repo, skills_dir, analysis.get("generated_at"))
    problems = validate_skill(skill_dir)
    if problems:
        for p in problems:
            say(f"  invalid: {p}")
        return fail("the generated skill does not pass the Agent Skills spec")
    say(f"Wrote {skill_dir}/SKILL.md with {len(rules)} rules (valid Agent Skill)")
    if agents_md:
        update_agents_md("AGENTS.md", skill_dir)
        say("Updated AGENTS.md with a pointer to the skill")
    return 0


def cmd_publish(args) -> int:
    if not Path(args.analysis).exists():
        return fail(f"{args.analysis} not found; run `folklore analyze` first")
    return _publish(load_analysis(args.analysis), args.skills_dir, args.agents_md)


def cmd_run(args) -> int:
    cfg = Config.load(args.config)
    repo = args.repo or cfg.repo
    if args.comments:
        comments_path = Path(args.comments)
    else:
        if not repo:
            return fail("say which repository to read: --repo owner/name")
        rc = cmd_mine(
            argparse.Namespace(config=args.config, repo=repo, max_prs=args.max_prs, out=COMMENTS)
        )
        if rc:
            return rc
        comments_path = COMMENTS
    try:
        analysis = _analyze(args, cfg, comments_path, repo)
    except LLMError as exc:
        return fail(str(exc))
    _summary(analysis)
    write_report(analysis, args.report)
    say(f"Wrote report to {args.report}")
    if args.no_publish:
        return 0
    return _publish(analysis, args.skills_dir, args.agents_md)


def cmd_demo(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    data = resources.files("folklore").joinpath("data/demo_comments.jsonl")
    with resources.as_file(data) as path:
        comments = load_comments(path)
    cfg = Config.load(args.config) if Path(args.config).exists() else Config()
    analysis = analyze(comments, cfg, now=_now("2026-10-15"), repo="example-org/widgetkit")
    save_analysis(analysis, out / "analysis.json")
    report = write_report(analysis, out / "report.html")
    skill_dir = publish(
        rules_from_analysis(analysis),
        "example-org/widgetkit",
        out / "skills",
        analysis["generated_at"],
    )
    problems = validate_skill(skill_dir)
    _summary(analysis)
    say(f"Report: {report}")
    say(
        f"Skill:  {skill_dir}/SKILL.md ({'valid' if not problems else 'INVALID: ' + '; '.join(problems)})"
    )
    say(
        "This demo uses a fictional repository; run `folklore run --repo owner/name` on a real one."
    )
    return 0 if not problems else 1


def cmd_validate(args) -> int:
    problems = validate_skill(args.skill_dir)
    if problems:
        for p in problems:
            say(f"  {p}")
        return fail(f"{args.skill_dir} is not a valid Agent Skill")
    say(f"{args.skill_dir} is a valid Agent Skill")
    return 0


def cmd_reject(args) -> int:
    path = Path(args.config)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    cfg = Config.load(path)
    if args.rule_id in cfg.rejected_rules:
        say(f"{args.rule_id} is already rejected")
        return 0
    entry = f"  - {args.rule_id}"
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("rejected_rules:"):
            if line.strip().endswith("[]"):
                lines[i] = "rejected_rules:"
            lines.insert(i + 1, entry)
            break
    else:
        lines += ["", "rejected_rules:", entry]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    say(f"Rejected {args.rule_id}. It will not be proposed again; re-run `folklore analyze`.")
    return 0


def _load_rules(path: str) -> list[Rule]:
    import json

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Rule.from_dict(r) for r in data.get("rules", [])]


def _llm_client(cfg: Config) -> OpenAICompatClient | None:
    if cfg.enforce_mode != "llm" or cfg.llm.provider != "openai":
        return None
    try:
        return OpenAICompatClient(cfg.llm)
    except LLMError as exc:
        say(f"warning: {exc}; using deterministic checks only")
        return None


def cmd_check_diff(args) -> int:
    cfg = Config.load(args.config)
    rules = _load_rules(args.rules)
    diff = sys.stdin.read() if args.diff == "-" else Path(args.diff).read_text(encoding="utf-8")
    hints = check(rules, parse_unified_diff(diff), cfg, _llm_client(cfg))
    if not hints:
        say("No known review conventions are broken by this diff.")
        return 0
    print(render_comment(hints, repo=args.repo or cfg.repo).replace(MARKER + "\n", ""))
    return 1 if args.strict else 0


def cmd_check_pr(args) -> int:
    cfg = Config.load(args.config)
    repo = args.repo or cfg.repo
    if not repo:
        return fail("say which repository: --repo owner/name")
    rules = _load_rules(args.rules)
    client = GitHubClient(_token())
    try:
        pr = client.pull(repo, args.pr)
        labels = {label["name"] for label in pr.get("labels", [])}
        if cfg.require_label and cfg.require_label not in labels:
            say(f"Skipping: PR #{args.pr} does not have the '{cfg.require_label}' label")
            return 0
        if pr.get("draft") and not args.include_drafts:
            say(f"Skipping: PR #{args.pr} is a draft")
            return 0
        files = {
            f["filename"]: parse_patch(f["filename"], f.get("patch", ""))
            for f in client.pull_files(repo, args.pr)
            if f.get("status") != "removed"
        }
        hints = check(rules, files, cfg, _llm_client(cfg))
        skill_path = f"skills/{skill_name(repo)}/SKILL.md"
        body = render_comment(hints, repo, skill_path) if hints else ""
        if args.dry_run:
            print(body or "No hints for this pull request.")
            return 0
        existing = next(
            (c for c in client.issue_comments(repo, args.pr) if MARKER in (c.get("body") or "")),
            None,
        )
        if body and existing:
            client.update_issue_comment(repo, existing["id"], body)
            say(f"Updated the pre-review comment on #{args.pr} ({len(hints)} hints)")
        elif body:
            client.create_issue_comment(repo, args.pr, body)
            say(f"Posted a pre-review comment on #{args.pr} ({len(hints)} hints)")
        elif existing:
            client.delete_issue_comment(repo, existing["id"])
            say(f"Removed the old pre-review comment on #{args.pr}; nothing to flag now")
        else:
            say(f"Nothing to flag on #{args.pr}")
    except GitHubError as exc:
        return fail(str(exc))
    return 0


# -- parser ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="folklore",
        description="Turn a project's unwritten code-review rules into an Agent Skill.",
    )
    parser.add_argument("--version", action="version", version=f"folklore {__version__}")
    parser.add_argument(
        "--config", default=CONFIG_FILE, help="config file (default: .folklore.yml)"
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    p = sub.add_parser("init", help="write a starter .folklore.yml")
    p.add_argument("--repo", help="owner/name")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("mine", help="download review feedback from GitHub")
    p.add_argument("--repo", help="owner/name")
    p.add_argument("--max-prs", type=int, help="closed PRs to read (default from config: 300)")
    p.add_argument("--out", default=COMMENTS, type=Path)
    p.set_defaults(func=cmd_mine)

    p = sub.add_parser("analyze", help="filter, cluster and distill mined feedback into rules")
    p.add_argument("--repo", help="owner/name (for links and naming)")
    p.add_argument("--comments", default=COMMENTS, type=Path)
    p.add_argument("--analysis", default=ANALYSIS, type=Path)
    p.add_argument("--now", help="reference time for recency, e.g. 2026-10-15 (default: now)")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("report", help="write the HTML report for maintainers")
    p.add_argument("--analysis", default=ANALYSIS, type=Path)
    p.add_argument("--out", default=REPORT, type=Path)
    p.add_argument("--fragment", action="store_true", help="omit <html>/<head>/<body> wrappers")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("publish", help="write the Agent Skill (skills/<repo>-folklore/)")
    p.add_argument("--analysis", default=ANALYSIS, type=Path)
    p.add_argument("--skills-dir", default="skills")
    p.add_argument("--agents-md", action="store_true", help="add a pointer to AGENTS.md")
    p.set_defaults(func=cmd_publish)

    p = sub.add_parser("run", help="mine, analyze, report and publish in one go")
    p.add_argument("--repo", help="owner/name")
    p.add_argument("--max-prs", type=int)
    p.add_argument("--comments", help="use an existing comments file instead of mining")
    p.add_argument("--analysis", default=ANALYSIS, type=Path)
    p.add_argument("--report", default=REPORT, type=Path)
    p.add_argument("--skills-dir", default="skills")
    p.add_argument("--agents-md", action="store_true")
    p.add_argument("--no-publish", action="store_true", help="stop after the report")
    p.add_argument("--now", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("demo", help="run everything on the bundled example data (no token needed)")
    p.add_argument("--out", default="folklore-demo")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("validate", help="check a skill directory against the Agent Skills spec")
    p.add_argument("skill_dir")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("reject", help="mark a proposed rule as not a real convention")
    p.add_argument("rule_id")
    p.set_defaults(func=cmd_reject)

    p = sub.add_parser("check-diff", help="check a local diff against the rules")
    p.add_argument("--rules", required=True, help="path to assets/rules.json")
    p.add_argument("--diff", default="-", help="diff file, or - for stdin (default)")
    p.add_argument("--repo", help="owner/name, for PR links")
    p.add_argument("--strict", action="store_true", help="exit 1 when a hint is found")
    p.set_defaults(func=cmd_check_diff)

    p = sub.add_parser("check-pr", help="post pre-review hints on a pull request")
    p.add_argument("--repo", help="owner/name")
    p.add_argument("--pr", type=int, required=True)
    p.add_argument(
        "--rules", required=True, help="path to assets/rules.json (from the base branch)"
    )
    p.add_argument("--dry-run", action="store_true", help="print the comment instead of posting")
    p.add_argument("--include-drafts", action="store_true")
    p.set_defaults(func=cmd_check_pr)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
