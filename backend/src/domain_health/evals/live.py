"""`make eval-live`: three live runs of every eval case, recorded. Paid.

Every call goes through the spend ledger first. What comes back is written under
`evals/recordings/<prompt version>/<model>/run-<n>/` exactly as it came, and scored afterwards by
the same code as `make eval`. A prompt version whose three runs are already recorded is never
run again: a change to the prompt is a new version file.
"""

import argparse
import asyncio
import os
import sys
import tomllib
from collections.abc import Awaitable, Callable, Mapping
from datetime import date
from pathlib import Path
from typing import Protocol

from domain_health.evals import __main__ as free
from domain_health.evals.cases import EvalCase, load_cases
from domain_health.evals.report import RUNS, run_folder
from domain_health.models import SnapshotInput
from domain_health.risks.ledger import Ledger, SpendCapError, standing_cap
from domain_health.risks.model import (
    ModelCall,
    RecordingExistsError,
    input_hash,
    load_calls,
    save_call,
)
from domain_health.risks.prompt import Prompt, load_prompt, prompt_versions
from domain_health.risks.prompt_rules import problems_with

CONCURRENCY = 6
LOCK_FILE = ".eval-live.lock"
PROBE_PROMPT = Prompt(
    version="probe",
    text="Return an empty list of risks for whatever input you are given.",
    sha256="probe",
)


class _Caller(Protocol):
    async def call(self, snapshot: SnapshotInput) -> ModelCall: ...


class AlreadyRecordedError(Exception):
    """All three runs of this prompt version on this model are recorded. It is not run again."""


class PromptChangedError(Exception):
    """Recordings exist under this version's name for another text of the prompt."""


def refuse_an_edited_prompt(prompt: Prompt, model: str, recordings: Path) -> None:
    """A change to a prompt is a new version file. If anything is recorded under this version's
    name with another text, the file was edited after it was run: nothing is called, and the
    recordings stay as they are."""
    for number in range(1, RUNS + 1):
        folder = run_folder(recordings, prompt.version, model, number)
        calls = load_calls(folder) if folder.is_dir() else []
        if any(call.prompt_sha256 != prompt.sha256 for call in calls):
            raise PromptChangedError(
                f"{prompt.version} has recordings on {model} made with another text of the "
                "prompt. A changed prompt is a new version file; this one was not run."
            )


def refuse_a_prompt_already_run(prompt: Prompt, model: str, recordings: Path) -> None:
    """An unchanged prompt is never run again, under any name. If this exact text has recordings
    on this model under another version's name, the file is a copy: nothing is called."""
    for folder in sorted(recordings.glob(f"*/{model}/run-*")) if recordings.is_dir() else []:
        recorded_as = folder.parent.parent.name
        if recorded_as == prompt.version:
            continue
        if any(call.prompt_sha256 == prompt.sha256 for call in load_calls(folder)):
            raise PromptChangedError(
                f"{prompt.version} is a text already recorded on {model} as {recorded_as}. "
                "An unchanged prompt is never run again."
            )


class AnotherRunError(Exception):
    """Another paid run holds the lock. Two at once would each count spend alone."""


class _OnlyOneRun:
    """An exclusive lock file for the whole paid command: one run at a time counts the spend."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def __enter__(self) -> None:
        try:
            descriptor = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as error:
            raise AnotherRunError(
                f"{self._path.name} exists: another paid run is in progress, or one was killed. "
                "If none is running, delete that file and run again."
            ) from error
        os.close(descriptor)

    def __exit__(self, *exc: object) -> None:
        self._path.unlink(missing_ok=True)


# What stops the paid command with a plain message and no traceback.
STOPPED = (
    SpendCapError,
    AlreadyRecordedError,
    PromptChangedError,
    AnotherRunError,
    RecordingExistsError,
)


def still_to_record(
    cases: Mapping[str, EvalCase], prompt: Prompt, model: str, recordings: Path
) -> dict[int, list[SnapshotInput]]:
    """For each run, the inputs with no answer recorded for this exact prompt text.

    A call that failed before the model answered (status "error") left no answer, so it is still
    to record. Anything the model did answer, valid or not, is never asked again.
    """
    todo: dict[int, list[SnapshotInput]] = {}
    for number in range(1, RUNS + 1):
        folder = run_folder(recordings, prompt.version, model, number)
        calls = load_calls(folder) if folder.is_dir() else []
        answered = {
            call.input_hash
            for call in calls
            if call.prompt_sha256 == prompt.sha256 and call.status != "error"
        }
        missing = [case.input for case in cases.values() if input_hash(case.input) not in answered]
        if missing:
            todo[number] = missing
    return todo


async def record_runs(
    call: Callable[[SnapshotInput], Awaitable[ModelCall]],
    todo: Mapping[int, list[SnapshotInput]],
    folder_for: Callable[[int], Path],
    say: Callable[[str], None],
) -> int:
    """Make every call still to be made, a few at a time, saving each answer as it arrives.

    Only an input goes to `call`: never a case's label, note or name.
    """
    gate = asyncio.Semaphore(CONCURRENCY)
    made = 0

    async def one(number: int, snapshot: SnapshotInput) -> None:
        nonlocal made
        async with gate:
            recorded = await call(snapshot)
        save_call(folder_for(number), recorded)
        made += 1

    for number, inputs in todo.items():
        # Every call of the run is let finish and is saved, whatever happens to one of them: a
        # call cut off half way would be paid for and leave nothing behind.
        outcomes = await asyncio.gather(
            *(one(number, snapshot) for snapshot in inputs), return_exceptions=True
        )
        failed = [outcome for outcome in outcomes if isinstance(outcome, BaseException)]
        say(f"run {number}: {len(inputs) - len(failed)} call(s) recorded")
        if failed:
            raise failed[0]
    return made


def _key_is_set() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="make eval-live")
    parser.add_argument("--prompts", type=Path, required=True)
    parser.add_argument("--evals", type=Path, required=True)
    parser.add_argument("--standing", type=Path, required=True)
    parser.add_argument("--model", help="call this model, not the settings file's")
    parser.add_argument("--probe", action="store_true", help="one call: is temperature accepted")
    args = parser.parse_args(argv)

    config = tomllib.loads((args.evals / "settings.toml").read_text(encoding="utf-8"))
    model = args.model or str(config["model"])
    temperature = float(config["temperature"]) if "temperature" in config else None
    if not _key_is_set():
        print("OPENAI_API_KEY is not set: put it in .env (see .env.example)", file=sys.stderr)
        return 1
    ledger = Ledger(args.evals / "ledger.jsonl", standing_cap(args.standing))
    # Imported here: only the paid commands ever load the live model's module.
    from domain_health.risks.openai_model import (
        BAD_REQUEST_ERROR,
        OpenAIRiskModel,
        client_from_environment,
    )

    client = client_from_environment()
    try:
        with _OnlyOneRun(args.evals / LOCK_FILE):
            return _paid(
                args, client, model, temperature, ledger, BAD_REQUEST_ERROR, OpenAIRiskModel
            )
    except STOPPED as stopped:
        print(f"stopped: {stopped}", file=sys.stderr)
        return 1


def _paid(
    args: argparse.Namespace,
    client: object,
    model: str,
    temperature: float | None,
    ledger: Ledger,
    bad_request: type[Exception],
    build: Callable[..., _Caller],
) -> int:
    """Everything that can spend, under the lock."""
    if args.probe:
        return asyncio.run(_probe(client, model, ledger, bad_request, build))
    versions = prompt_versions(args.prompts)
    if not versions:
        print(free.NOTHING)
        return 1
    prompt = load_prompt(versions[-1])
    cases = load_cases(args.evals / "cases")
    broken = problems_with(
        prompt.text,
        (args.evals / "RUBRIC.md").read_text(encoding="utf-8"),
        [case.input for case in cases.values()],
    )
    if broken:
        # A prompt that breaks a rule for the paid runs is never paid for.
        print(f"{prompt.version} breaks a rule for prompts, so it was not run:", file=sys.stderr)
        print("\n".join(f"  {problem}" for problem in broken), file=sys.stderr)
        return 1
    refuse_an_edited_prompt(prompt, model, args.evals / "recordings")
    refuse_a_prompt_already_run(prompt, model, args.evals / "recordings")
    todo = still_to_record(cases, prompt, model, args.evals / "recordings")
    if not todo:
        raise AlreadyRecordedError(
            f"{prompt.version} on {model} already has its {RUNS} runs recorded. An unchanged "
            "prompt is never run again: a change is a new version file."
        )
    live = build(
        client, prompt, model, ledger, temperature=temperature, purpose=f"eval {prompt.version}"
    )
    before = ledger.spent()
    made = asyncio.run(
        record_runs(
            live.call,
            todo,
            lambda number: run_folder(args.evals / "recordings", prompt.version, model, number),
            print,
        )
    )
    print(
        f"{made} call(s) on {date.today().isoformat()}, ${ledger.spent() - before:.4f}; "
        f"spent in all ${ledger.spent():.4f}"
    )
    # Score the version that was just run. Where the settings file names another version as the
    # one in use, that says so and leaves the results file alone.
    scored = ["--prompts", str(args.prompts), "--evals", str(args.evals), "--table-report"]
    if free.settings(args.evals).get("prompt") not in (None, prompt.version):
        scored += ["--version", prompt.version]
    return free.main([*scored, *(["--model", args.model] if args.model else [])])


async def _probe(
    client: object,
    model: str,
    ledger: Ledger,
    bad_request: type[Exception],
    build: Callable[..., _Caller],
) -> int:
    """One call with temperature 0 and reasoning off, on a seeded client's input (not an eval
    case). Says whether the model accepts the parameter (decision 0002)."""
    from domain_health.seeded import load_clients, snapshot_input

    client_ = load_clients()[0]
    snapshot = await snapshot_input(client_, date(2026, 11, 19))
    live = build(client, PROBE_PROMPT, model, ledger, temperature=0.0, purpose="temperature probe")
    try:
        call = await live.call(snapshot)
    except bad_request as error:
        print(f"temperature with reasoning off on {model}: REFUSED ({type(error).__name__})")
        print(str(error)[:300])
        return 0
    print(f"temperature with reasoning off on {model}: ACCEPTED (call {call.status})")
    print(f"{call.input_tokens} tokens in, {call.output_tokens} out, ${call.cost_usd:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
