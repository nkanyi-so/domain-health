"""The change alert: one message when a deterministic check differs from yesterday's.

Only what rules and DNS decide is compared: the three checks' fields and the fix list. The
model's risks never raise an alert. The hosted demo sends nothing (`NullAlerter`).
"""

from typing import Protocol

from domain_health.checks import CheckResults, Unavailable
from domain_health.models import Fix
from domain_health.store import DayResult, Snapshot


class AlertError(Exception):
    """The message was not sent."""


class Alerter(Protocol):
    async def send(self, message: str) -> None: ...


class NullAlerter:
    async def send(self, message: str) -> None:
        return None


class FakeAlerter:
    def __init__(self, *, failing: bool = False) -> None:
        self.sent: list[str] = []
        self._failing = failing

    async def send(self, message: str) -> None:
        if self._failing:
            raise AlertError("the fake was told to fail")
        self.sent.append(message)


def _fields(results: CheckResults) -> dict[str, object]:
    """Each check's model-facing fields, flat, or "not checked" for one that could not be made."""
    flat: dict[str, object] = {}
    for name, found in (("spf", results.spf), ("dkim", results.dkim), ("dmarc", results.dmarc)):
        if isinstance(found, Unavailable):
            flat[name] = "not checked"
            continue
        for field, value in found.check.model_dump(mode="json").items():
            flat[f"{name}.{field}"] = value
    return flat


def _fix_types(fixes: list[Fix]) -> set[str]:
    return {fix.type.value for fix in fixes}


def changes(yesterday: Snapshot | None, today: DayResult) -> list[str]:
    """What differs between two days' deterministic results, in plain lines. Empty when nothing
    does, and when there is no yesterday to compare with."""
    if yesterday is None:
        return []
    before, after = _fields(yesterday.checks), _fields(today.checks)
    lines = [
        f"{field}: {before.get(field)!r} became {after.get(field)!r}"
        for field in sorted(before.keys() | after.keys())
        if before.get(field) != after.get(field)
    ]
    was, now = _fix_types(yesterday.fixes), _fix_types(today.fixes)
    lines += [f"new fix: {kind}" for kind in sorted(now - was)]
    lines += [f"fix no longer needed: {kind}" for kind in sorted(was - now)]
    return lines


def message(today: DayResult, lines: list[str]) -> str:
    """The alert's text. Check values come from DNS and are untrusted: they are shown with
    `repr`, on lines of their own, and the receiver renders plain text."""
    header = f"{today.domain}: {len(lines)} change(s) since yesterday ({today.day.isoformat()})"
    return "\n".join([header, *(f"- {line}" for line in lines)])
