"""The prompt is a versioned file: `prompts/risks-v<number>.md`. A change is a new version."""

import hashlib
import re
from pathlib import Path

from domain_health.models import Frozen

VERSION_FILE = re.compile(r"risks-v(\d+)\.md")


class Prompt(Frozen):
    version: str  # the file's name without its ending: risks-v1
    text: str
    sha256: str  # of the text, so that an edited file is not mistaken for the version recorded


def load_prompt(path: Path) -> Prompt:
    text = path.read_text(encoding="utf-8")
    return Prompt(
        version=path.stem, text=text, sha256=hashlib.sha256(text.encode("utf-8")).hexdigest()
    )


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
