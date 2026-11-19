"""`make eval`: scores the committed recordings for the current prompt version.

Until a prompt exists there is nothing to measure, and that is said and is not a failure. Once a
prompt file exists this must score it or fail: it never reports "nothing to measure" for a prompt
it cannot score.
"""

import argparse
import re
import sys
from pathlib import Path

NOTHING = "no prompt yet: nothing to measure"


VERSION_FILE = re.compile(r"risks-v(\d+)\.md")


def prompt_versions(folder: Path) -> list[Path]:
    """Prompt version files, oldest first by number, so v10 comes after v9."""
    if not folder.is_dir():
        return []
    numbered = [(m, path) for path in folder.iterdir() if (m := VERSION_FILE.fullmatch(path.name))]
    return [path for m, path in sorted(numbered, key=lambda pair: int(pair[0].group(1)))]


def unversioned(folder: Path) -> list[Path]:
    """Anything in the prompts folder that is not a version file."""
    if not folder.is_dir():
        return []
    return sorted(path for path in folder.iterdir() if path not in prompt_versions(folder))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="make eval")
    parser.add_argument("--prompts", type=Path, required=True, help="the folder of prompt versions")
    parser.add_argument("--strict", action="store_true", help="exit non-zero on a missed bar")
    args = parser.parse_args(argv)

    versions = prompt_versions(args.prompts)
    strays = unversioned(args.prompts)
    if strays:
        # A prompt under another name would otherwise be reported as "nothing to measure".
        names = ", ".join(path.name for path in strays)
        print(f"not a prompt version (expected risks-v<number>.md): {names}", file=sys.stderr)
        return 1
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
