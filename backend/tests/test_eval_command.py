from pathlib import Path

import pytest

from domain_health.evals.__main__ import NOTHING, main


def test_with_no_prompt_there_is_nothing_to_measure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--prompts", str(tmp_path / "prompts")]) == 0
    assert capsys.readouterr().out.strip() == NOTHING


def test_strict_is_also_quiet_before_any_prompt(tmp_path: Path) -> None:
    assert main(["--prompts", str(tmp_path), "--strict"]) == 0


def test_a_prompt_that_cannot_be_scored_is_a_failure_not_a_pass(tmp_path: Path) -> None:
    (tmp_path / "risks-v1.md").write_text("a prompt", encoding="utf-8")

    assert main(["--prompts", str(tmp_path)]) == 1


def test_a_prompt_under_another_name_is_not_nothing_to_measure(tmp_path: Path) -> None:
    (tmp_path / "risks.md").write_text("a prompt", encoding="utf-8")

    assert main(["--prompts", str(tmp_path)]) == 1
    assert main(["--prompts", str(tmp_path), "--strict"]) == 1
