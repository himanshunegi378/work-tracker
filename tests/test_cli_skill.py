import json
from pathlib import Path

from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


def test_install_to_dir_then_noop_then_conflict(tmp_path):
    r = runner.invoke(app, ["--json", "install-skill", "--dir", str(tmp_path)])
    assert r.exit_code == 0, r.output
    dest = tmp_path / "samta-tracker" / "SKILL.md"
    assert json.loads(r.stdout)["status"] == "installed"
    assert dest.read_text().startswith("---\nname: samta-tracker")

    r = runner.invoke(app, ["--json", "install-skill", "--dir", str(tmp_path)])
    assert json.loads(r.stdout)["status"] == "up-to-date"

    dest.write_text("old")
    r = runner.invoke(app, ["install-skill", "--dir", str(tmp_path)])
    assert r.exit_code == 1 and dest.read_text() == "old"
    r = runner.invoke(app, ["--json", "install-skill", "--dir", str(tmp_path), "--force"])
    assert json.loads(r.stdout)["status"] == "updated"
    assert dest.read_text().startswith("---")


def test_default_user_and_project_locations(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["install-skill"]).exit_code == 0
    assert (tmp_path / "home/.claude/skills/samta-tracker/SKILL.md").exists()
    assert runner.invoke(app, ["install-skill", "--project"]).exit_code == 0
    assert (tmp_path / ".claude/skills/samta-tracker/SKILL.md").exists()


def test_print_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    r = runner.invoke(app, ["install-skill", "--print"])
    assert r.exit_code == 0 and "name: samta-tracker" in r.stdout
    assert not (tmp_path / ".claude").exists()


def test_packaged_skill_matches_the_source():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    assert (root / "skills/samta-tracker/SKILL.md").read_text() == (root / "src/cli/skill/SKILL.md").read_text(), \
        "run: python scripts/sync_skill.py"
