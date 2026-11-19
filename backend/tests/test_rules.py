"""The rules engine, by itself and against the rubric's fix table on every eval case."""

import pytest

from domain_health.evals.cases import load_cases
from domain_health.evals.table import fix_types
from domain_health.models import (
    Blocklist,
    DkimCheck,
    DkimKey,
    DmarcCheck,
    Reputation,
    Sources,
    SpfCheck,
)
from domain_health.rules import INSTRUCTIONS, fix_list, source_of
from domain_health.types import FixType
from tests.paths import CASES


def spf(
    count: int = 1, valid: bool | None = True, lookups: int | None = 3, ending: str | None = "-all"
) -> SpfCheck:
    return SpfCheck.model_validate(
        {
            "present": count > 0,
            "record_count": count,
            "valid": valid,
            "lookup_count": lookups,
            "all_qualifier": ending,
        }
    )


def dkim(*bits: int) -> DkimCheck:
    keys = [DkimKey(selector=f"s{i}", key_bits=b) for i, b in enumerate(bits)]
    return DkimCheck(selectors_probed=12, keys=keys)


def dmarc(present: bool = True, valid: bool | None = True) -> DmarcCheck:
    ok = bool(present and valid)
    return DmarcCheck(
        present=present,
        valid=valid if present else None,
        policy="reject" if ok else None,
        subdomain_policy=None,
        pct=100 if ok else None,
    )


def sources(complaints: float = 0.02, bounces: float = 0.4, listed: bool = False) -> Sources:
    return Sources(
        reputation=Reputation(grade="high", previous_grade="high"),
        complaint_rate_pct=complaints,
        bounce_rate_pct=bounces,
        volume_7d=10_000,
        volume_prev_7d=10_000,
        open_rate_pct=30.0,
        open_rate_prev_pct=30.0,
        blocklist=Blocklist(
            listed=listed, listings_90d=1 if listed else 0, days_since_delisted=None
        ),
        domain_age_days=1000,
    )


def types(*args: object, **kwargs: int) -> list[FixType]:
    return [fix.type for fix in fix_list(*args, **kwargs)]  # type: ignore[arg-type]


def test_a_healthy_domain_has_no_fix() -> None:
    assert fix_list(spf(), dkim(2048), dmarc(), sources()) == []


# One fact, one fix: the data on the left gives exactly the fix on the right, and the data just
# on the other side of the line gives none.
ONE_FACT = [
    (FixType.SPF_MISSING, {"spf": spf(0, None, None, None)}),
    (FixType.SPF_MULTIPLE, {"spf": spf(2, None, None, None)}),
    (FixType.SPF_INVALID, {"spf": spf(1, False, None, None)}),
    (FixType.SPF_TOO_MANY_LOOKUPS, {"spf": spf(lookups=11)}),
    (FixType.SPF_PLUS_ALL, {"spf": spf(ending="+all")}),
    (FixType.DKIM_MISSING, {"dkim": dkim()}),
    (FixType.DKIM_WEAK_KEY, {"dkim": dkim(2048, 1023)}),
    (FixType.DMARC_MISSING, {"dmarc": dmarc(present=False)}),
    (FixType.DMARC_INVALID, {"dmarc": dmarc(valid=False)}),
    (FixType.BLOCKLIST_LISTED, {"sources": sources(listed=True)}),
    (FixType.COMPLAINT_RATE_OVER_LIMIT, {"sources": sources(complaints=0.30)}),
    (FixType.BOUNCE_RATE_OVER_LIMIT, {"sources": sources(bounces=5.0)}),
]
JUST_INSIDE: dict[str, list[object]] = {
    "spf": [spf(lookups=10), spf(ending="~all"), spf(ending="?all"), spf(ending=None)],
    "dkim": [dkim(1024), dkim(1024, 4096)],
    "dmarc": [dmarc()],
    "sources": [sources(complaints=0.29), sources(bounces=4.99)],
}


@pytest.mark.parametrize(("fix_type", "fault"), ONE_FACT, ids=[t.value for t, _ in ONE_FACT])
def test_each_fault_gives_its_one_fix(fix_type: FixType, fault: dict[str, object]) -> None:
    healthy: dict[str, object] = {
        "spf": spf(),
        "dkim": dkim(2048),
        "dmarc": dmarc(),
        "sources": sources(),
    }
    data = healthy | fault

    fixes = fix_list(data["spf"], data["dkim"], data["dmarc"], data["sources"])  # type: ignore[arg-type]

    assert [fix.type for fix in fixes] == [fix_type]
    assert fixes[0].source == source_of(fix_type)
    assert fixes[0].instruction == INSTRUCTIONS[fix_type]


def test_every_fix_type_has_a_rule_a_source_and_an_instruction() -> None:
    assert [t for t, _ in ONE_FACT] == list(FixType)
    assert set(INSTRUCTIONS) == set(FixType)
    assert all(text.endswith(".") and len(text) > 30 for text in INSTRUCTIONS.values())
    seeded = [t.value for t in FixType if source_of(t) == "seeded"]
    assert seeded == ["blocklist_listed", "complaint_rate_over_limit", "bounce_rate_over_limit"]


@pytest.mark.parametrize("name", list(JUST_INSIDE))
def test_a_value_on_the_right_side_of_the_line_gives_no_fix(name: str) -> None:
    for value in JUST_INSIDE[name]:
        healthy: dict[str, object] = {
            "spf": spf(),
            "dkim": dkim(2048),
            "dmarc": dmarc(),
            "sources": sources(),
        }
        data = healthy | {name: value}
        assert types(data["spf"], data["dkim"], data["dmarc"], data["sources"]) == []


def test_fixes_come_in_the_closed_lists_order_and_several_can_hold_at_once() -> None:
    found = types(
        spf(lookups=12, ending="+all"),
        dkim(512),
        dmarc(present=False),
        sources(complaints=0.5, bounces=9.0, listed=True),
    )

    assert found == [
        FixType.SPF_TOO_MANY_LOOKUPS,
        FixType.SPF_PLUS_ALL,
        FixType.DKIM_WEAK_KEY,
        FixType.DMARC_MISSING,
        FixType.BLOCKLIST_LISTED,
        FixType.COMPLAINT_RATE_OVER_LIMIT,
        FixType.BOUNCE_RATE_OVER_LIMIT,
    ]


def test_a_record_that_cannot_be_read_gives_one_fix_not_a_guess_about_its_contents() -> None:
    assert types(spf(2, None, None, None), None, None, None) == [FixType.SPF_MULTIPLE]
    assert types(spf(1, False, None, None), None, None, None) == [FixType.SPF_INVALID]


def test_what_is_not_known_gives_no_fix() -> None:
    # A check that could not be made, and a typed domain with no seeded sources.
    assert fix_list(None, None, None, None) == []
    assert types(None, dkim(), None, None) == [FixType.DKIM_MISSING]


def test_a_key_that_is_not_rsa_counts_as_a_key() -> None:
    assert types(None, dkim(), None, None, other_dkim_keys=1) == []
    assert types(None, dkim(512), None, None, other_dkim_keys=1) == [FixType.DKIM_WEAK_KEY]


def test_the_engine_gives_every_eval_case_the_fix_list_it_was_written_with() -> None:
    """The rules engine and the rubric's fix table are separate code; on all forty-eight cases
    they agree, and the engine's fixes are the case's own, wording included."""
    cases = load_cases(CASES)
    assert len(cases) == 48

    for name, case in cases.items():
        snapshot = case.input
        checks = snapshot.checks
        fixes = fix_list(checks.spf, checks.dkim, checks.dmarc, snapshot.sources)

        assert [fix.type for fix in fixes] == fix_types(snapshot), name
        assert fixes == snapshot.fixes, name
