"""What the seeded recordings say, read against the rubric. Free.

`python -m domain_health.seeded.recording_report` prints the report the owner is shown before
the recordings are kept: per state, whether the three answers agreed, how many returned types
the rubric's bands call merely acceptable, any they call wrong, and any wording that says a value
is over a rubric line it is not over (a rate elevated, volume spiked, a domain new).

This module reads the rubric's table, so nothing the deployed service loads imports it.
"""

import asyncio
import re
import sys
from collections.abc import Callable, Mapping
from typing import Literal

from pydantic import ConfigDict

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


class Line(Frozen):
    """One risk type's line in the rubric: where its bands start to list the type at all.

    Off the listed side of it, the rubric does not say the thing the type's name says, so text
    that says it is saying something false about the input.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    # What is measured, in words, for the report.
    what: str
    line: float
    # The type is listed from the line up (a rate, a ratio), or only below it (a domain's age).
    listed: Literal["at or above", "below"]
    # Words that claim the input is on the listed side.
    says: re.Pattern[str]


def _ratio(snapshot: SnapshotInput) -> float:
    now, before = snapshot.sources.volume_7d, snapshot.sources.volume_prev_7d
    # The rubric's own rule: a previous week of 0 with mail this week counts as 2.0.
    return now / before if before else (2.0 if now else 0.0)


def _fall(snapshot: SnapshotInput) -> float | None:
    previous = snapshot.sources.open_rate_prev_pct
    if not previous:
        return None
    return (previous - snapshot.sources.open_rate_pct) / previous


def _lookups(snapshot: SnapshotInput) -> float | None:
    count = snapshot.checks.spf.lookup_count
    return None if count is None else float(count)


# What each line measures. None means the input has nothing to measure, and nothing is flagged.
VALUES: dict[RiskType, Callable[[SnapshotInput], float | None]] = {
    RiskType.COMPLAINT_RATE_ELEVATED: lambda snapshot: snapshot.sources.complaint_rate_pct,
    RiskType.BOUNCE_RATE_ELEVATED: lambda snapshot: snapshot.sources.bounce_rate_pct,
    RiskType.VOLUME_SPIKE: _ratio,
    RiskType.ENGAGEMENT_DECLINING: _fall,
    RiskType.SPF_NEAR_LOOKUP_LIMIT: _lookups,
    RiskType.NEW_DOMAIN_VOLUME: lambda snapshot: float(snapshot.sources.domain_age_days),
}

_ELEVATED = re.compile(
    r"\b(above|elevated|over|exceed(s|ed|ing)?|high|higher|too many|excessive)\b", re.IGNORECASE
)
# Every risk type whose rubric bands turn on a number. The other seven turn on a state (a
# policy, a qualifier, a listing, a grade), which the text cannot be over or under.
LINES: dict[RiskType, Line] = {
    RiskType.COMPLAINT_RATE_ELEVATED: Line(
        what="complaint rate, %", line=0.08, listed="at or above", says=_ELEVATED
    ),
    RiskType.BOUNCE_RATE_ELEVATED: Line(
        what="bounce rate, %", line=1.5, listed="at or above", says=_ELEVATED
    ),
    RiskType.VOLUME_SPIKE: Line(
        what="this week's volume over last week's",
        line=1.5,
        listed="at or above",
        says=re.compile(
            r"\b(spik\w*|surg\w*|jump\w*|sharp\w*|doubl\w*|tripl\w*|sudden\w*|soar\w*)\b",
            re.IGNORECASE,
        ),
    ),
    RiskType.ENGAGEMENT_DECLINING: Line(
        what="fall in the open rate, as a share",
        line=0.10,
        listed="at or above",
        says=re.compile(
            r"\b(declin\w*|fall\w*|fell|drop\w*|sharp\w*|down|slid\w*|slump\w*|lower)\b",
            re.IGNORECASE,
        ),
    ),
    RiskType.SPF_NEAR_LOOKUP_LIMIT: Line(
        what="SPF lookups",
        line=8,
        listed="at or above",
        says=re.compile(r"\b(near\w*|close|approach\w*|almost|nearly|just under)\b", re.IGNORECASE),
    ),
    RiskType.NEW_DOMAIN_VOLUME: Line(
        what="domain age, days",
        line=90,
        listed="below",
        says=re.compile(r"\b(new|newly|young|recent|recently|fresh|brand)\b", re.IGNORECASE),
    ),
}


def off_the_line(kind: RiskType, snapshot: SnapshotInput) -> float | None:
    """The input's value when it is on the side of the line where the bands do not list the
    type; None when the type has no line, the input has no value, or it is on the listed side."""
    if kind not in LINES:
        return None
    value = VALUES[kind](snapshot)
    if value is None:
        return None
    rule = LINES[kind]
    listed = value >= rule.line if rule.listed == "at or above" else value < rule.line
    return None if listed else value


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
    """Risks whose text says what the type's name says (a rate is elevated, volume has spiked,
    the domain is new) when the input is on the side of the rubric's line where it is not so."""
    flagged = []
    for risk in risks:
        value = off_the_line(risk.type, snapshot)
        if value is None:
            continue
        rule = LINES[risk.type]
        said = rule.says.search(f"{risk.title} {risk.why}")
        if said:
            flagged.append(
                f'{risk.type.value}: says "{said.group(0)}" with {rule.what} at {value:g}; '
                f"the rubric lists the type only {rule.listed} {rule.line:g}"
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
