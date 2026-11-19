"""An input that cannot happen is refused, so a case (or, later, a snapshot) cannot hold one."""

import json
from typing import Any

import pytest
from pydantic import ValidationError

from domain_health.models import SnapshotInput
from tests.paths import CASES


def healthy() -> dict[str, Any]:
    raw: dict[str, Any] = json.loads(
        (CASES / "01-healthy-baseline.json").read_text(encoding="utf-8")
    )["input"]
    return raw


def test_the_healthy_input_is_accepted() -> None:
    SnapshotInput.model_validate(healthy())


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("sources", "open_rate_prev_pct"), None),  # old enough to have a previous open rate
        (("sources", "domain_age_days"), 40),  # too young to have one
        (
            ("sources", "blocklist"),
            {"listed": True, "listings_90d": 0, "days_since_delisted": None},
        ),
        (("sources", "blocklist"), {"listed": True, "listings_90d": 1, "days_since_delisted": 3}),
        (
            ("sources", "blocklist"),
            {"listed": False, "listings_90d": 1, "days_since_delisted": None},
        ),
        (("sources", "blocklist"), {"listed": False, "listings_90d": 0, "days_since_delisted": 9}),
        (("sources", "blocklist"), {"listed": False, "listings_90d": 1, "days_since_delisted": 91}),
        (("checks", "spf", "present"), False),  # absent, yet one record
        (("checks", "spf", "record_count"), 2),  # two records, yet a lookup count
        (("checks", "spf", "valid"), False),  # does not parse, yet a lookup count
        (("checks", "spf", "lookup_count"), None),  # valid, with no lookup count
        (("checks", "dmarc", "present"), False),  # absent, yet valid
        (("checks", "dmarc", "valid"), False),  # does not parse, yet a policy
        (("checks", "dmarc", "pct"), None),  # valid, with no pct
        (("checks", "dmarc", "policy"), None),  # valid, with no policy
    ],
)
def test_an_input_that_cannot_happen_is_refused(path: tuple[str, ...], value: object) -> None:
    raw = healthy()
    target = raw
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(ValidationError):
        SnapshotInput.model_validate(raw)
