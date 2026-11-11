import whatsapp_taskwarrior


def test_version():
    assert whatsapp_taskwarrior.__version__


def test_agent_skill_is_shared():
    """One skill for every agent: Claude Code's copy is a link to skills/, not a second file."""
    from pathlib import Path

    import pytest

    root = Path(__file__).resolve().parent.parent
    skill = root / "skills" / "whatsapp-taskwarrior" / "SKILL.md"
    if not skill.exists():
        pytest.skip("skills/ is not part of this source tree (e.g. the Nix package build)")
    assert skill.read_text(encoding="utf-8").startswith("---\nname: whatsapp-taskwarrior\n")
    link = root / ".claude" / "skills" / "whatsapp-taskwarrior"
    assert link.is_symlink() and (link / "SKILL.md").resolve() == skill.resolve()
