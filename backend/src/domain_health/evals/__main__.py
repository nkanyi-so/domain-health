"""`make eval`: scores the committed recordings for the prompt version in use.

The version in use is the one the settings file names (`prompt = "risks-v3"`); with no such line
it is the newest version file. Other versions recorded on the same model are reported beside it.

Free: it reads recordings and makes no call. Until a prompt exists there is nothing to measure,
and that is said and is not a failure. Once a prompt file exists this must score it or fail: it
never reports "nothing to measure" for a prompt it cannot score. With `--strict` a missed bar is
a failure too.
"""

import argparse
import sys
import tomllib
from collections.abc import Mapping
from pathlib import Path

from domain_health.evals.cases import EvalCase, load_cases
from domain_health.evals.report import (
    NoRecordingsError,
    lines,
    load_runs,
    other_version,
    results_for,
    table_report,
)
from domain_health.evals.scoring import load_bars
from domain_health.risks.prompt import load_prompt, prompt_versions, unversioned

NOTHING = "no prompt yet: nothing to measure"
__all__ = ["NOTHING", "main", "prompt_versions"]


def settings(evals: Path) -> dict[str, object]:
    """Which model the committed results are for, and how it was called."""
    return tomllib.loads((evals / "settings.toml").read_text(encoding="utf-8"))


def _has_recordings(path: Path, cases: Mapping[str, EvalCase], evals: Path) -> bool:
    """Whether some model has three whole runs recorded with this exact text of the prompt."""
    prompt = load_prompt(path)
    folder = evals / "recordings" / prompt.version
    for model in sorted(item.name for item in folder.iterdir()) if folder.is_dir() else []:
        try:
            load_runs(cases, prompt, model, evals / "recordings")
        except NoRecordingsError:
            continue
        return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="make eval")
    parser.add_argument("--prompts", type=Path, required=True, help="the folder of prompt versions")
    parser.add_argument("--evals", type=Path, help="the folder of cases, bars and recordings")
    parser.add_argument("--strict", action="store_true", help="exit non-zero on a missed bar")
    parser.add_argument("--version", help="score this prompt version, not the newest")
    parser.add_argument("--model", help="score this model's recordings, not the settings file's")
    parser.add_argument(
        "--table-report", action="store_true", help="also print each table case's result"
    )
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
    if args.evals is None:
        print("a prompt exists: say where the cases and recordings are (--evals)", file=sys.stderr)
        return 1
    try:
        config = settings(args.evals)
    except OSError as error:
        print(f"the settings file was not read: {error}", file=sys.stderr)
        return 1
    wanted = args.version or config.get("prompt")
    chosen = [path for path in versions if wanted in (None, path.stem)]
    if not chosen:
        print(f"no prompt version named {wanted}", file=sys.stderr)
        return 1
    prompt = load_prompt(chosen[-1])
    in_use = args.version is None and args.model is None
    try:
        model = args.model or str(config["model"])
        cases = load_cases(args.evals / "cases")
        runs, calls, drops = load_runs(cases, prompt, model, args.evals / "recordings")
    except (NoRecordingsError, OSError, KeyError) as error:
        print(f"{prompt.version} was not scored: {error}", file=sys.stderr)
        return 1
    others = []
    for path in versions if in_use else []:
        if path.stem == prompt.version:
            continue
        other = load_prompt(path)
        try:
            other_runs, _, _ = load_runs(cases, other, model, args.evals / "recordings")
        except NoRecordingsError:
            continue  # recorded on another model, or not at all: strict mode says which
        others.append(other_version(cases, other, other_runs))
    bars = load_bars(args.evals / "bars.toml")
    results = results_for(cases, prompt, model, runs, calls, bars, others)
    print("\n".join(lines(results)))
    if args.table_report:
        print("table cases:")
        print("\n".join(f"  {line}" for line in table_report(cases, runs, drops)))
    if in_use:
        # The results file is for the prompt version in use on the settings file's model.
        (args.evals / "results.json").write_text(
            results.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
    if not args.strict:
        return 0
    # Strict also holds every other version file to its recordings: a version edited after it was
    # run no longer has any that match it.
    unmatched = [
        path.stem
        for path in versions
        if path.stem != prompt.version and not _has_recordings(path, cases, args.evals)
    ]
    if unmatched:
        print(f"no recordings match the prompt text of: {', '.join(unmatched)}", file=sys.stderr)
        return 1
    return 0 if results.all_bars_met else 1


if __name__ == "__main__":
    raise SystemExit(main())
