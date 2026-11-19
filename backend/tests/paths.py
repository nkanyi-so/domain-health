"""Where the repository's shared files are, for tests that read them."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
EVALS = REPO / "evals"
CASES = EVALS / "cases"
RUBRIC = EVALS / "RUBRIC.md"
BARS = EVALS / "bars.toml"
