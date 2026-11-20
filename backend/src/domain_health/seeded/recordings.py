"""The seeded clients' recorded model output: where it is and which of it is kept.

`make record` (paid, `record.py`) asks the live model three times for every state of every
seeded client and saves each answer under `backend/fixtures/recordings/<prompt version>/<model>/
run-<n>/`. Everything here is free and reads those files.

A state's answer is kept only when its three answers are valid and agree on their first five
risk types, in order. The deployed worker replays the kept answers and nothing else: a state
whose answers disagree has no recording to replay, so its snapshot says "risks unavailable".

The deployed service imports this module, so it does not import the rubric's table: what the
recordings say against the rubric is `recording_report.py`'s.
"""

import asyncio
import tomllib
from datetime import date
from pathlib import Path
from typing import Literal

from domain_health.models import Frozen, SnapshotInput
from domain_health.risks import Risk
from domain_health.risks.model import (
    ModelCall,
    RecordedRiskModel,
    RisksUnavailableError,
    input_hash,
    load_calls,
    risks_from,
)
from domain_health.risks.prompt import Prompt, load_prompt
from domain_health.seeded import FIXTURES, SeededClient, load_clients, snapshot_input

REPO = FIXTURES.parents[1]
RECORDINGS = FIXTURES / "recordings"
FIRST = 5
# Three answers for every state, as the eval runs have three for every case.
RUNS = 3


def run_folder(recordings: Path, prompt_version: str, model: str, run: int) -> Path:
    """The same layout as the eval recordings: version, model, run."""
    return recordings / prompt_version / model / f"run-{run}"


Agreement = Literal["agreed", "disagreed", "invalid", "missing"]


class State(Frozen):
    """One day of one seeded client's cycle: what the model is asked about."""

    client_id: str
    day_index: int
    note: str
    snapshot: SnapshotInput


async def states(clients: list[SeededClient] | None = None) -> list[State]:
    """Every state of every seeded client, in the order of client id and day."""
    found = []
    for client in clients if clients is not None else load_clients():
        for index, day in enumerate(client.cycle):
            # Any date that lands on this day of the cycle gives the same input.
            on = date.fromordinal(len(client.cycle) * 100_000 + index)
            found.append(
                State(
                    client_id=client.id,
                    day_index=index,
                    note=day.note,
                    snapshot=await snapshot_input(client, on),
                )
            )
    return found


def settings(repo: Path = REPO) -> tuple[Prompt, str]:
    """The prompt version in use and the model, as `evals/settings.toml` names them."""
    config = tomllib.loads((repo / "evals" / "settings.toml").read_text(encoding="utf-8"))
    prompt = load_prompt(repo / "prompts" / f"{config['prompt']}.md")
    return prompt, str(config["model"])


def recorded_runs(
    prompt: Prompt, model: str, recordings: Path = RECORDINGS
) -> list[list[ModelCall]]:
    """The calls of each of the three runs that were made with this exact text of the prompt."""
    runs = []
    for number in range(1, RUNS + 1):
        folder = run_folder(recordings, prompt.version, model, number)
        calls = load_calls(folder) if folder.is_dir() else []
        runs.append([call for call in calls if call.prompt_sha256 == prompt.sha256])
    return runs


def _answers(snapshot: SnapshotInput, runs: list[list[ModelCall]]) -> list[list[Risk] | None]:
    """Each run's validated answer for this input: a list, or None when missing or invalid."""
    wanted = input_hash(snapshot)
    answers: list[list[Risk] | None] = []
    for calls in runs:
        call = next((call for call in calls if call.input_hash == wanted), None)
        try:
            answers.append(None if call is None else risks_from(snapshot, call))
        except RisksUnavailableError:
            answers.append(None)
    return answers


def agreement(snapshot: SnapshotInput, runs: list[list[ModelCall]]) -> Agreement:
    wanted = input_hash(snapshot)
    if any(all(call.input_hash != wanted for call in calls) for calls in runs):
        return "missing"
    answers = _answers(snapshot, runs)
    if any(answer is None for answer in answers):
        return "invalid"
    firsts = {tuple(risk.type for risk in (answer or [])[:FIRST]) for answer in answers}
    return "agreed" if len(firsts) == 1 else "disagreed"


def kept_calls(found: list[State], runs: list[list[ModelCall]]) -> list[ModelCall]:
    """The first run's call for every state whose three answers agree. Nothing else is replayed."""
    kept = []
    for state in found:
        if agreement(state.snapshot, runs) == "agreed":
            wanted = input_hash(state.snapshot)
            kept.append(next(call for call in runs[0] if call.input_hash == wanted))
    return kept


def recorded_model(
    repo: Path = REPO, recordings: Path = RECORDINGS
) -> tuple[RecordedRiskModel, Prompt, str]:
    """The model the deployed worker is built with: the kept answers, replayed."""
    prompt, model = settings(repo)
    kept = kept_calls(asyncio.run(states()), recorded_runs(prompt, model, recordings))
    return RecordedRiskModel(prompt, model, kept), prompt, model
