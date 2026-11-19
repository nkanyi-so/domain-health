"""`make eval`: scores the committed recordings for the current prompt version.

Until a prompt exists there is nothing to measure, and that is said and is not a failure. Once a
prompt file exists this must score it or fail: it never reports "nothing to measure" for a prompt
it cannot score.
"""

import argparse
import sys
from pathlib import Path

NOTHING = "no prompt yet: nothing to measure"


def prompt_versions(folder: Path) -> list[Path]:
    return sorted(folder.glob("risks-v*.md")) if folder.is_dir() else []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="make eval")
    parser.add_argument("--prompts", type=Path, required=True, help="the folder of prompt versions")
    parser.add_argument("--strict", action="store_true", help="exit non-zero on a missed bar")
    args = parser.parse_args(argv)

    versions = prompt_versions(args.prompts)
    if not versions:
        print(NOTHING)
        return 0
    print(
        f"{versions[-1].name} exists but the scorer is not built yet (Phase 2): nothing was scored",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
