from folklore.cli import main
from folklore.config import Config
from folklore.mine import mine


class FakeGitHub:
    def closed_pulls(self, repo, limit):
        return [{"number": 7, "created_at": "2026-09-01T00:00:00Z", "user": {"login": "sam"}}]

    def review_comments(self, repo, since=None, limit=None):
        return [
            {
                "id": 1,
                "pull_request_url": "https://api.github.com/repos/o/r/pulls/7",
                "body": "Use the logger.",
                "user": {"login": "maya"},
                "author_association": "MEMBER",
                "path": "a.ts",
                "diff_hunk": "@@ -1 +1 @@\n+x",
                "created_at": "2026-09-02T00:00:00Z",
                "html_url": "u1",
            },
            {
                "id": 2,
                "pull_request_url": "https://api.github.com/repos/o/r/pulls/99",
                "body": "other PR",
                "user": {"login": "maya"},
                "author_association": "MEMBER",
            },
        ]

    def reviews(self, repo, number):
        return [
            {
                "id": 3,
                "body": "Please add a changeset.",
                "user": {"login": "devon"},
                "author_association": "OWNER",
                "submitted_at": "2026-09-03T00:00:00Z",
                "html_url": "u3",
            },
            {"id": 4, "body": "", "user": {"login": "devon"}},
        ]


def test_mine_maps_github_payloads():
    comments = mine(FakeGitHub(), "o/r", max_prs=10)
    assert [(c.id, c.kind, c.pr_author) for c in comments] == [
        (1, "inline", "sam"),
        (3, "review", "sam"),
    ]


def test_demo_and_reject_commands(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["demo", "--out", "out"]) == 0
    assert (tmp_path / "out" / "report.html").exists()
    assert (tmp_path / "out" / "skills" / "widgetkit-folklore" / "SKILL.md").exists()
    assert main(["init", "--repo", "o/r"]) == 0
    assert main(["reject", "dont-use-lodash-native-methods"]) == 0
    assert main(["reject", "dont-use-lodash-native-methods"]) == 0
    cfg = Config.load(tmp_path / ".folklore.yml")
    assert cfg.repo == "o/r" and cfg.rejected_rules == ["dont-use-lodash-native-methods"]


def test_check_diff_command(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["demo", "--out", "out"])
    diff = tmp_path / "d.patch"
    diff.write_text(
        "diff --git a/packages/core/src/x.ts b/packages/core/src/x.ts\n+++ b/packages/core/src/x.ts\n"
        "@@ -1 +1,2 @@\n+console.log('hi');\n"
    )
    rules = "out/skills/widgetkit-folklore/assets/rules.json"
    assert main(["check-diff", "--rules", rules, "--diff", str(diff), "--strict"]) == 1
    assert "logger" in capsys.readouterr().out


class FakePRClient:
    """Stands in for GitHubClient in check-pr."""

    posted: list = []

    def __init__(self, token=""):
        pass

    def pull(self, repo, number):
        return {"labels": [{"name": "folklore"}], "draft": False}

    def pull_files(self, repo, number):
        return [
            {
                "filename": "packages/core/src/a.ts",
                "status": "modified",
                "patch": "@@ -1 +1,2 @@\n ctx\n+console.log('x');",
            },
            {"filename": "old.ts", "status": "removed", "patch": "@@ -1 +0,0 @@\n-console.log(1);"},
        ]

    def issue_comments(self, repo, number):
        return []

    def create_issue_comment(self, repo, number, body):
        FakePRClient.posted.append(body)


def test_check_pr_posts_one_comment(tmp_path, monkeypatch):
    import folklore.cli as cli

    monkeypatch.chdir(tmp_path)
    main(["demo", "--out", "out"])
    monkeypatch.setattr(cli, "GitHubClient", FakePRClient)
    rules = "out/skills/widgetkit-folklore/assets/rules.json"
    assert main(["check-pr", "--repo", "example-org/widgetkit", "--pr", "5", "--rules", rules]) == 0
    assert len(FakePRClient.posted) == 1
    body = FakePRClient.posted[0]
    assert (
        "folklore:pre-review" in body
        and "packages/core/src/a.ts:2" in body
        and "old.ts" not in body
    )
