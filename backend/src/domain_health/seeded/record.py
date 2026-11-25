"""`make record`: the live model's answers for every state of every seeded client. Paid.

Three calls for each state, with the prompt version in use (`evals/settings.toml`), every one
through the spend ledger first. Each answer is saved exactly as it came. An answer already
recorded is never asked for again, so running the command twice costs nothing the second time;
only a call that failed before the model answered is made again.

It prints the report of `recordings.py` at the end. Which answers are kept is decided there, by
code, from the files.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from domain_health.evals.cases import load_cases
from domain_health.evals.live import (
    LOCK_FILE,
    STOPPED,
    _key_is_set,
    _OnlyOneRun,
    record_runs,
    refuse_an_edited_prompt,
)
from domain_health.models import SnapshotInput
from domain_health.risks.ledger import Ledger, spend_cap
from domain_health.risks.model import input_hash, load_calls
from domain_health.risks.prompt import Prompt
from domain_health.risks.prompt_rules import problems_with
from domain_health.seeded.recording_report import lines, report
from domain_health.seeded.recordings import (
    RECORDINGS,
    REPO,
    RUNS,
    recorded_runs,
    run_folder,
    settings,
    states,
)


def still_to_record(
    inputs: list[SnapshotInput], prompt: Prompt, model: str, recordings: Path
) -> dict[int, list[SnapshotInput]]:
    """For each of the three runs, the inputs the model has not answered with this prompt text."""
    todo: dict[int, list[SnapshotInput]] = {}
    for number in range(1, RUNS + 1):
        folder = run_folder(recordings, prompt.version, model, number)
        calls = load_calls(folder) if folder.is_dir() else []
        answered = {
            call.input_hash
            for call in calls
            if call.prompt_sha256 == prompt.sha256 and call.status != "error"
        }
        missing = [snapshot for snapshot in inputs if input_hash(snapshot) not in answered]
        if missing:
            todo[number] = missing
    return todo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="make record")
    parser.add_argument("--spend-cap", type=Path, default=REPO / "evals" / "spend-cap.txt")
    parser.add_argument("--recordings", type=Path, default=RECORDINGS)
    args = parser.parse_args(argv)

    prompt, model = settings()
    evals = REPO / "evals"
    config_temperature = _temperature(evals)
    found = asyncio.run(states())
    inputs = list({input_hash(s.snapshot): s.snapshot for s in found}.values())
    broken = problems_with(
        prompt.text,
        (evals / "RUBRIC.md").read_text(encoding="utf-8"),
        [case.input for case in load_cases(evals / "cases").values()],
    )
    if broken:
        print(f"{prompt.version} breaks a rule for prompts, so it was not run:", file=sys.stderr)
        print("\n".join(f"  {problem}" for problem in broken), file=sys.stderr)
        return 1
    todo = still_to_record(inputs, prompt, model, args.recordings)
    if todo:
        if not _key_is_set():
            print("OPENAI_API_KEY is not set: put it in .env (see .env.example)", file=sys.stderr)
            return 1
        ledger = Ledger(evals / "ledger.jsonl", spend_cap(args.spend_cap))
        # Imported here: only the paid commands ever load the live model's module.
        from domain_health.risks.openai_model import OpenAIRiskModel, client_from_environment

        try:
            with _OnlyOneRun(evals / LOCK_FILE):
                refuse_an_edited_prompt(prompt, model, args.recordings)
                live = OpenAIRiskModel(
                    client_from_environment(),
                    prompt,
                    model,
                    ledger,
                    temperature=config_temperature,
                    purpose=f"record {prompt.version}",
                )
                before = ledger.spent()
                made = asyncio.run(
                    record_runs(
                        live.call,
                        todo,
                        lambda number: run_folder(args.recordings, prompt.version, model, number),
                        print,
                    )
                )
                print(
                    f"{made} call(s), ${ledger.spent() - before:.4f}; "
                    f"spent in all ${ledger.spent():.4f}"
                )
        except STOPPED as stopped:
            print(f"stopped: {stopped}", file=sys.stderr)
            return 1
    else:
        print(
            f"every state already has its {RUNS} answers for {prompt.version} on {model}: "
            "no call made"
        )
    print(
        "\n".join(
            lines(report(found, recorded_runs(prompt, model, args.recordings)), prompt, model)
        )
    )
    return 0


def _temperature(evals: Path) -> float | None:
    import tomllib

    config = tomllib.loads((evals / "settings.toml").read_text(encoding="utf-8"))
    return float(config["temperature"]) if "temperature" in config else None


if __name__ == "__main__":
    sys.exit(main())
