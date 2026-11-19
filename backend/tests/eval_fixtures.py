"""Helpers for tests of the model seam and the evals: scripted output and recorded calls."""

import json
from pathlib import Path

from domain_health.evals.cases import EvalCase
from domain_health.evals.report import RUNS, run_folder
from domain_health.models import SnapshotInput
from domain_health.risks.model import ModelCall, input_hash, save_call
from domain_health.risks.prompt import Prompt, load_prompt
from domain_health.types import RiskType

MODEL = "gpt-6-luna"


def output_text(*types: RiskType | str) -> str:
    risks = [
        {"type": str(risk), "title": "A title", "why": "A reason.", "evidence": ["fixes"]}
        for risk in types
    ]
    return json.dumps({"risks": risks})


def write_prompt(folder: Path, name: str = "risks-v1.md", text: str = "Rank the risks.") -> Prompt:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text, encoding="utf-8")
    return load_prompt(folder / name)


def recorded_call(
    prompt: Prompt,
    snapshot: SnapshotInput,
    text: str | None,
    *,
    model: str = MODEL,
    status: str = "completed",
) -> ModelCall:
    return ModelCall.model_validate(
        {
            "prompt_version": prompt.version,
            "prompt_sha256": prompt.sha256,
            "model": model,
            "reasoning_effort": "none",
            "temperature": 0.0,
            "input_hash": input_hash(snapshot),
            "status": status,
            "output_text": text,
            "input_tokens": 1000,
            "output_tokens": 100,
            "cost_usd": 0.00015,
            "latency_ms": 800,
            "recorded_at": "2026-11-19T12:00:00+00:00",
        }
    )


def record_as_labelled(
    recordings: Path, prompt: Prompt, cases: dict[str, EvalCase], *, model: str = MODEL
) -> None:
    """Three runs in which the model returns exactly what each case expects."""
    for number in range(1, RUNS + 1):
        folder = run_folder(recordings, prompt.version, model, number)
        for case in cases.values():
            text = output_text(*case.label.expected)
            save_call(folder, recorded_call(prompt, case.input, text, model=model))
