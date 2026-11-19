"""The language model behind one interface, and the record of one call to it.

`RiskModel.rank` gives a validated ranked list or raises `RisksUnavailableError`. Three
implementations: live (`openai_model.py`, the only module that imports the model's library),
recorded (replays committed calls) and fixture (scripted, for tests).
"""

import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Literal, Protocol

from domain_health.models import Frozen, SnapshotInput
from domain_health.risks import InvalidOutputError, Risk, validate
from domain_health.risks.prompt import Prompt

CallStatus = Literal["completed", "refused", "incomplete", "error"]


class RisksUnavailableError(Exception):
    """The model gave nothing usable for this input: no call, a failed one, or invalid output."""


class RiskModel(Protocol):
    async def rank(self, snapshot: SnapshotInput) -> list[Risk]: ...


def input_hash(snapshot: SnapshotInput) -> str:
    """One input, one hash: the same data gives the same hash on any machine."""
    canonical = json.dumps(snapshot.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def user_message(snapshot: SnapshotInput) -> str:
    """Exactly what the model is sent for one client on one day: the input, and nothing else."""
    return snapshot.model_dump_json(indent=2)


class ModelCall(Frozen):
    """One call to the live model, as recorded: what was asked, what came back, what it cost."""

    prompt_version: str
    prompt_sha256: str
    model: str
    reasoning_effort: str
    temperature: float | None
    input_hash: str
    status: CallStatus
    # The model's text exactly as it came back; null when there was none. Validated at every use.
    output_text: str | None
    detail: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    recorded_at: str


def call_key(prompt_version: str, model: str, input_hash_: str) -> str:
    """What a recording is looked up by: the prompt version, the model and the input."""
    joined = "\n".join((prompt_version, model, input_hash_))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def risks_from(snapshot: SnapshotInput, call: ModelCall) -> list[Risk]:
    """A recorded or live call as a validated list, or `RisksUnavailableError` saying why."""
    if call.status != "completed" or call.output_text is None:
        raise RisksUnavailableError(f"the model call was {call.status}")
    try:
        return validate(snapshot, call.output_text)
    except InvalidOutputError as error:
        raise RisksUnavailableError(f"invalid output dropped: {error}") from error


def load_calls(folder: Path) -> list[ModelCall]:
    """Every recorded call in a folder, in file-name order."""
    return [
        ModelCall.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(folder.glob("*.json"))
    ]


class RecordingExistsError(Exception):
    """There is already an answer recorded for this input in this run. It is not replaced."""


def save_call(folder: Path, call: ModelCall) -> Path:
    """Write one recording. An answer already recorded is evidence and is never overwritten;
    only a call that failed before the model answered (status "error") may be replaced."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{call.input_hash[:16]}.json"
    if path.exists():
        existing = ModelCall.model_validate_json(path.read_text(encoding="utf-8"))
        if existing.status != "error":
            raise RecordingExistsError(f"{path.name} in {folder.name} already holds an answer")
    path.write_text(call.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


class RecordedRiskModel:
    """Replays committed calls. Makes no call of its own and needs no key."""

    def __init__(self, prompt: Prompt, model: str, calls: Iterable[ModelCall]) -> None:
        self._prompt = prompt
        self._model = model
        self._calls = {
            call_key(call.prompt_version, call.model, call.input_hash): call
            for call in calls
            # A recording made with another text of this prompt version is not this prompt's.
            if call.prompt_sha256 == prompt.sha256
        }

    def recorded(self, snapshot: SnapshotInput) -> ModelCall | None:
        key = call_key(self._prompt.version, self._model, input_hash(snapshot))
        return self._calls.get(key)

    async def rank(self, snapshot: SnapshotInput) -> list[Risk]:
        call = self.recorded(snapshot)
        if call is None:
            raise RisksUnavailableError("no recording for this input, prompt version and model")
        return risks_from(snapshot, call)


class FixtureRiskModel:
    """Scripted output for tests: the text to answer with, by domain. Validated like any other."""

    def __init__(self, outputs: Mapping[str, str]) -> None:
        self._outputs = dict(outputs)
        self.seen: list[SnapshotInput] = []

    async def rank(self, snapshot: SnapshotInput) -> list[Risk]:
        self.seen.append(snapshot)
        if snapshot.domain not in self._outputs:
            raise RisksUnavailableError("no scripted output for this domain")
        try:
            return validate(snapshot, self._outputs[snapshot.domain])
        except InvalidOutputError as error:
            raise RisksUnavailableError(f"invalid output dropped: {error}") from error
