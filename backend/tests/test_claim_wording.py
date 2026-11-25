"""Pins the claim. The sentence lives in docs/EVALS.md as its one quoted line; every place that
shows it must match.
"""

import re
from pathlib import Path

from tests.paths import BACKEND, REPO

CLAIM_FILE = REPO / "docs" / "EVALS.md"
README = REPO / "README.md"
FRONTEND_CLAIM = REPO / "frontend" / "src" / "content" / "claim.ts"
REPORT_TEMPLATES = BACKEND / "src" / "domain_health" / "report" / "templates"


def claim() -> str:
    """The one quoted line in docs/EVALS.md."""
    quoted: list[str] = re.findall(
        r"^> (.+)$", CLAIM_FILE.read_text(encoding="utf-8"), re.MULTILINE
    )
    assert len(quoted) == 1, "docs/EVALS.md must hold exactly one quoted line: the claim"
    return quoted[0].strip()


def shown(path: Path) -> str:
    """A file's text with runs of whitespace as one space, so a wrapped line still matches."""
    return " ".join(path.read_text(encoding="utf-8").split())


def test_the_claim_is_one_sentence() -> None:
    sentence = claim()

    assert sentence.endswith(".")
    assert len(sentence) > 60


def test_the_readme_states_the_claim_once_it_exists() -> None:
    if README.exists():
        assert claim() in shown(README)


def test_the_page_states_the_claim_once_it_exists() -> None:
    if FRONTEND_CLAIM.exists():
        assert claim() in shown(FRONTEND_CLAIM)


def test_every_report_template_states_the_claim_once_any_exists() -> None:
    if REPORT_TEMPLATES.exists():
        templates = [p for p in sorted(REPORT_TEMPLATES.iterdir()) if p.is_file()]
        assert templates, "the report templates folder is empty"
        for template in templates:
            assert claim() in shown(template), template.name
