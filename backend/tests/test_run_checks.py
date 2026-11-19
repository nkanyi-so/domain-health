import asyncio

import pytest

from domain_health.checks import LookupFailedError, SpfFinding, Unavailable
from domain_health.checks.run import CHECK_SECONDS, run_checks
from domain_health.resolver import (
    MAX_QUERIES_PER_DOMAIN,
    CountingResolver,
    TxtAnswer,
    TxtStatus,
)
from domain_health.resolver.fixture import FixtureResolver
from tests.dns_fixtures import dkim_record, run

D = "shop.example"
ZONE = {
    D: ["v=spf1 ip4:192.0.2.1 -all"],
    f"k1._domainkey.{D}": [dkim_record(2048)],
    f"_dmarc.{D}": ["v=DMARC1; p=reject"],
}


def test_the_three_checks_give_the_shape_the_model_receives() -> None:
    results = run(run_checks(FixtureResolver(ZONE), D.upper() + "."))

    assert results.domain == D
    assert results.unavailable == []
    checks = results.model_input()
    assert checks.spf.all_qualifier == "-all"
    assert [key.key_bits for key in checks.dkim.keys] == [2048]
    assert checks.dmarc.policy == "reject"


def test_one_check_that_cannot_be_made_does_not_stop_the_others() -> None:
    results = run(run_checks(FixtureResolver(ZONE, timeouts=[f"_dmarc.{D}"]), D))

    assert results.unavailable == ["dmarc"]
    assert isinstance(results.dmarc, Unavailable)
    assert "_dmarc.shop.example did not answer" in results.dmarc.reason
    assert isinstance(results.spf, SpfFinding)
    with pytest.raises(LookupFailedError):
        results.model_input()


class _Slow:
    async def txt(self, name: str) -> TxtAnswer:
        await asyncio.sleep(30)
        return TxtAnswer(status=TxtStatus.RECORDS)


def test_a_check_has_eight_seconds_and_says_so_when_it_runs_out() -> None:
    assert CHECK_SECONDS == 8.0

    results = run(run_checks(_Slow(), D, check_seconds=0.01))

    assert results.unavailable == ["spf", "dkim", "dmarc"]
    assert isinstance(results.spf, Unavailable)
    assert results.spf.reason == "the check took longer than 0.01 seconds"


def test_one_domain_never_costs_more_than_forty_lookups() -> None:
    assert MAX_QUERIES_PER_DOMAIN == 40
    # The worst a zone can do: an SPF record that walks to the limit, a DMARC walk of four names.
    zone = {"a.b.c.shop.example": ["v=spf1 include:hop1.example -all"]}
    for hop in range(1, 30):
        zone[f"hop{hop}.example"] = [f"v=spf1 include:hop{hop + 1}.example -all"]
    counting = CountingResolver(FixtureResolver(zone))

    results = run(run_checks(counting, "a.b.c.shop.example"))

    assert results.unavailable == []
    # 11 for SPF, 12 selectors, 4 names for DMARC.
    assert counting.queries == 27


def test_past_the_budget_a_check_is_unavailable_not_wrong() -> None:
    counting = CountingResolver(FixtureResolver(ZONE), limit=5)

    results = run(run_checks(counting, D))

    assert counting.queries == 5
    assert "dkim" in results.unavailable
    assert isinstance(results.dkim, Unavailable)
    assert results.dkim.reason == "more than 5 DNS lookups"


def test_no_record_a_zone_can_publish_makes_the_checks_raise() -> None:
    """DNS answers are untrusted. Whatever a zone holds, each check answers or is unavailable."""
    hostile = [
        "",
        " ",
        ";",
        "=",
        "v=",
        "p=",
        "v=spf1",
        "v=spf1 ",
        "v=spf1 a:",
        "v=spf1 ip4:",
        "v=spf1 ip6:::/200",
        "v=spf1 include:" + "a." * 200,
        "v=spf1 redirect=%",
        "v=spf1 " + "mx " * 500,
        "v=DMARC1",
        "v=DMARC1;",
        "v=DMARC1; p",
        "v=DMARC1; p=; pct=",
        "v=DMARC1; pct=-1; p=none",
        "v=DMARC1; pct=99999999999999999999999; p=none",
        "v=DKIM1",
        "v=DKIM1; p=MAMCAQA=",
        "v=DKIM1; p=MAICAA==",
        "v=DKIM1; p=MAA=",
        "v=DKIM1; p=MA==",
        "v=DKIM1; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQ==",
        "v=DKIM1; p=AwEA",
        "v=DKIM1; k=; p=AAAA",
        "v=DKIM1; s=; p=AAAA",
        "v=DKIM1; k=ed25519; p=",
        "k=rsa; p=" + "A" * 4000,
        "\x00\x01\x02",
        "\ud7ff" * 50,
    ]
    names = [D, f"_dmarc.{D}", *(f"{selector}._domainkey.{D}" for selector in ("mail", "k1"))]
    for record in hostile:
        for other in ("", "v=spf1 -all", "v=DMARC1; p=none", dkim_record(2048)):
            zone = {name: [record, other] if other else [record] for name in names}

            results = run(run_checks(FixtureResolver(zone), D))

            assert results.unavailable == [], repr(record)


def test_a_busy_top_name_with_the_spf_record_last_is_read_whole() -> None:
    tokens = [f"site-verification=token{n}" for n in range(60)]
    zone = ZONE | {D: [*tokens, "v=spf1 ip4:192.0.2.1 -all"]}

    results = run(run_checks(FixtureResolver(zone), D))

    assert results.unavailable == []
    assert results.model_input().spf.present is True


def test_an_answer_too_large_to_read_makes_the_check_unavailable_not_wrong() -> None:
    tokens = [f"site-verification=token{n}" for n in range(100)]
    one_spf_then_too_many = ZONE | {D: ["v=spf1 -all", *tokens, "v=spf1 +all"]}
    spf_last = ZONE | {D: [*tokens, "v=spf1 -all"]}
    too_long = ZONE | {D: ["v=spf1 " + "ip4:192.0.2.1 " * 400 + "+all"]}
    include_too_large = ZONE | {D: ["v=spf1 include:big.example -all"], "big.example": tokens * 2}

    for zone in (one_spf_then_too_many, spf_last, too_long, include_too_large):
        results = run(run_checks(FixtureResolver(zone), D))

        # Not "no SPF record", not a valid record, not a broken one: not checked.
        assert results.unavailable == ["spf"]
        assert isinstance(results.spf, Unavailable)
        assert results.spf.reason.endswith("gave more text than a check reads")


def test_a_selector_or_a_dmarc_name_that_answers_too_much_is_unavailable_too() -> None:
    flood = ["x"] * 101

    dkim = run(run_checks(FixtureResolver(ZONE | {f"mail._domainkey.{D}": flood}), D))
    dmarc = run(run_checks(FixtureResolver(ZONE | {f"_dmarc.{D}": flood}), D))

    assert dkim.unavailable == ["dkim"]
    assert dmarc.unavailable == ["dmarc"]
