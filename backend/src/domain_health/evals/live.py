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
from domain_health.risks.model import ModelCall, input_hash, load_calls, save_call
from domain_health.risks.prompt import Prompt, load_prompt, prompt_versions

CONCURRENCY = 6
PROBE_PROMPT = Prompt(
    version="probe",
    text="Return an empty list of risks for whatever input you are given.",
    sha256="probe",
)


class _Caller(Protocol):
    async def call(self, snapshot: SnapshotInput) -> ModelCall: ...


class AlreadyRecordedError(Exception):
    """All three runs of this prompt version on this model are recorded. It is not run again."""


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
        await asyncio.gather(*(one(number, snapshot) for snapshot in inputs))
        say(f"run {number}: {len(inputs)} call(s) recorded")
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
        if args.probe:
            return asyncio.run(_probe(client, model, ledger, BAD_REQUEST_ERROR, OpenAIRiskModel))
        versions = prompt_versions(args.prompts)
        if not versions:
            print(free.NOTHING)
            return 1
        prompt = load_prompt(versions[-1])
        cases = load_cases(args.evals / "cases")
        todo = still_to_record(cases, prompt, model, args.evals / "recordings")
        if not todo:
            raise AlreadyRecordedError(
                f"{prompt.version} on {model} already has its {RUNS} runs recorded. An unchanged "
                "prompt is never run again: a change is a new version file."
            )
        live = OpenAIRiskModel(
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
    except (SpendCapError, AlreadyRecordedError) as stopped:
        print(f"stopped: {stopped}", file=sys.stderr)
        return 1
    scored = ["--prompts", str(args.prompts), "--evals", str(args.evals), "--table-report"]
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
