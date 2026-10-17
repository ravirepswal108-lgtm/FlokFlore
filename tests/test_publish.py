from folklore.publish import skill_name, update_agents_md, validate_skill


def test_skill_name_follows_spec():
    assert skill_name("Acme/Widget.Kit") == "widget-kit-folklore"
    assert skill_name("a/--weird__name--") == "weird-name-folklore"
    assert len(skill_name("a/" + "x" * 100)) <= 64


def _write(tmp_path, name, frontmatter, body="# Hi\n"):
    d = tmp_path / name
    d.mkdir()
    (d / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n{body}")
    return d


def test_validator_catches_problems(tmp_path):
    assert (
        validate_skill(
            _write(tmp_path, "ok-skill", "name: ok-skill\ndescription: Does X. Use when Y.")
        )
        == []
    )
    bad = validate_skill(_write(tmp_path, "Bad--Name", "name: Bad--Name\ndescription: ''"))
    assert any("lowercase" in p for p in bad) and any("description" in p for p in bad)
    mismatch = validate_skill(_write(tmp_path, "dir-a", "name: dir-b\ndescription: x"))
    assert any("directory name" in p for p in mismatch)
    missing = validate_skill(
        _write(tmp_path, "links", "name: links\ndescription: x", "[a](references/x.md)")
    )
    assert any("does not exist" in p for p in missing)


def test_agents_md_block_is_idempotent(tmp_path):
    path = tmp_path / "AGENTS.md"
    path.write_text("# Agents\n\nExisting notes.\n")
    update_agents_md(path, "skills/x-folklore")
    update_agents_md(path, "skills/x-folklore")
    text = path.read_text()
    assert text.count("folklore:start") == 1 and "Existing notes." in text
