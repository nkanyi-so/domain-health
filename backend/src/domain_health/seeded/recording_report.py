"""What the seeded recordings say, read against the rubric. Free.

`python -m domain_health.seeded.recording_report` prints the report the owner is shown before
the recordings are kept: per state, whether the three answers agreed, how many returned types
the rubric's bands call merely acceptable, any they call wrong, and any wording that says a rate
is elevated when it is under the rubric's line.

This module reads the rubric's table, so nothing the deployed service loads imports it.
"""

import asyncio
import re
import sys
from collections.abc import Mapping

from domain_health.evals.table import table_label
from domain_health.models import Frozen, SnapshotInput
from domain_health.risks import Risk
from domain_health.risks.model import ModelCall
from domain_health.risks.prompt import Prompt
from domain_health.seeded.recordings import (
    Agreement,
    State,
    _answers,
    agreement,
    recorded_runs,
    settings,
    states,
)
from domain_health.types import RiskType

# The lowest rate at which the rubric's bands list the type at all. Under it, the rubric does
# not call the rate elevated, so text that does is saying something false about the input.
RATE_LINES: dict[RiskType, tuple[str, float]] = {
    RiskType.COMPLAINT_RATE_ELEVATED: ("complaint_rate_pct", 0.08),
    RiskType.BOUNCE_RATE_ELEVATED: ("bounce_rate_pct", 1.5),
}
_SAYS_ELEVATED = re.compile(
    r"\b(above|elevated|over|exceed(s|ed|ing)?|high|higher|too many|excessive)\b", re.IGNORECASE
)


class StateReport(Frozen):
    client_id: str
    day_index: int
    agreement: Agreement
    # Of the kept answer (or, when the three disagree, of everything any of them returned).
    returned: list[RiskType]
    merely_acceptable: list[RiskType]
    wrong: list[RiskType]
    false_wording: list[str]


def false_wording(snapshot: SnapshotInput, risks: list[Risk]) -> list[str]:
    """Risks whose text says a rate is elevated when the input's rate is under the rubric's line."""
    flagged = []
    for risk in risks:
        if risk.type not in RATE_LINES:
            continue
        field, line = RATE_LINES[risk.type]
        value = float(getattr(snapshot.sources, field))
        if value < line and _SAYS_ELEVATED.search(f"{risk.title} {risk.why}"):
            flagged.append(
                f"{risk.type.value}: says elevated at {value:g}, under the line {line:g}"
            )
    return flagged


def report(found: list[State], runs: list[list[ModelCall]]) -> list[StateReport]:
    reports = []
    for state in found:
        verdict = agreement(state.snapshot, runs)
        answers = [answer for answer in _answers(state.snapshot, runs) if answer is not None]
        considered = answers[:1] if verdict == "agreed" else answers
        risks = [risk for answer in considered for risk in answer]
        types = list(dict.fromkeys(risk.type for risk in risks))
        label = table_label(state.snapshot)
        reports.append(
            StateReport(
                client_id=state.client_id,
                day_index=state.day_index,
                agreement=verdict,
                returned=types,
                merely_acceptable=[kind for kind in types if kind in label.acceptable],
                wrong=[kind for kind in types if kind in label.wrong],
                false_wording=list(dict.fromkeys(false_wording(state.snapshot, risks))),
            )
        )
    return reports


def lines(reports: list[StateReport], prompt: Prompt, model: str) -> list[str]:
    counts: Mapping[str, int] = {
        verdict: sum(r.agreement == verdict for r in reports)
        for verdict in ("agreed", "disagreed", "invalid", "missing")
    }
    out = [
        f"seeded recordings, {prompt.version} on {model}: {len(reports)} states, "
        f"{counts['agreed']} kept (three answers agree), {counts['disagreed']} disagree, "
        f"{counts['invalid']} invalid, {counts['missing']} missing",
        f"{'state':<30} {'answers':<10} returned  merely acceptable  wrong  false wording",
    ]
    for r in reports:
        name = f"{r.client_id} day {r.day_index}"
        out.append(
            f"{name:<30} {r.agreement:<10} {len(r.returned):>8}  {len(r.merely_acceptable):>17}  "
            f"{len(r.wrong):>5}  {len(r.false_wording):>13}"
        )
        out += [f"    merely acceptable: {kind.value}" for kind in r.merely_acceptable]
        out += [f"    WRONG by the bands: {kind.value}" for kind in r.wrong]
        out += [f"    FALSE WORDING: {text}" for text in r.false_wording]
    kept = [r for r in reports if r.agreement == "agreed"]
    out.append(
        f"in the kept answers: {sum(len(r.returned) for r in kept)} risks returned, "
        f"{sum(len(r.merely_acceptable) for r in kept)} of a type the bands call merely "
        f"acceptable, {sum(len(r.wrong) for r in kept)} wrong, "
        f"{sum(len(r.false_wording) for r in kept)} with false wording"
    )
    return out


def main() -> int:
    prompt, model = settings()
    found = asyncio.run(states())
    print("\n".join(lines(report(found, recorded_runs(prompt, model)), prompt, model)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
