import pytest

from domain_health.checks import LookupFailedError
from domain_health.checks.dmarc import check_dmarc
from domain_health.resolver.fixture import FixtureResolver
from tests.dns_fixtures import run

D = "shop.example"


def dmarc(*records: str, domain: str = D, at: str = D):  # type: ignore[no-untyped-def]
    return run(check_dmarc(FixtureResolver({f"_dmarc.{at}": list(records)}), domain))


def test_no_record() -> None:
    found = run(check_dmarc(FixtureResolver({}), D))

    check = found.check
    assert (check.present, check.valid, check.policy, check.subdomain_policy, check.pct) == (
        False,
        None,
        None,
        None,
        None,
    )


def test_a_txt_record_that_is_not_dmarc_is_no_record() -> None:
    assert dmarc("v=spf1 -all").check.present is False


@pytest.mark.parametrize("policy", ["none", "quarantine", "reject"])
def test_the_policy_is_read_and_the_percentage_defaults_to_100(policy: str) -> None:
    found = dmarc(f"v=DMARC1; p={policy}; rua=mailto:reports@shop.example")

    assert found.check.valid is True
    assert found.check.policy == policy
    assert found.check.subdomain_policy is None
    assert found.check.pct == 100
    assert found.found_at == D


def test_the_subdomain_policy_and_the_percentage_are_read() -> None:
    found = dmarc("v=DMARC1;p=REJECT;sp=none;pct=25")

    assert (found.check.policy, found.check.subdomain_policy, found.check.pct) == (
        "reject",
        "none",
        25,
    )


@pytest.mark.parametrize(
    "record",
    [
        "v=DMARC1; p=monitor",
        "v=DMARC1; rua=mailto:reports@shop.example",
        "v=DMARC1; p=none; sp=maybe",
        "v=DMARC1; p=none; pct=150",
        "v=DMARC1; p=none; pct=half",
        "v=DMARC1; p=none; quarantine",
    ],
    ids=["unknown policy", "no policy", "bad sp", "pct over 100", "pct not a number", "stray word"],
)
def test_a_record_that_does_not_parse(record: str) -> None:
    found = dmarc(record)

    check = found.check
    assert (check.present, check.valid) == (True, False)
    assert (check.policy, check.subdomain_policy, check.pct) == (None, None, None)
    assert len(found.problems) == 1


def test_two_dmarc_records_do_not_parse() -> None:
    found = dmarc("v=DMARC1; p=none", "v=DMARC1; p=reject")

    assert (found.check.present, found.check.valid) == (True, False)


def test_a_subdomain_inherits_its_parents_subdomain_policy() -> None:
    found = dmarc("v=DMARC1; p=reject; sp=quarantine", domain="mail.shop.example")

    assert found.check.policy == "quarantine"
    assert found.check.subdomain_policy is None
    assert found.found_at == D


def test_a_subdomain_inherits_the_policy_when_no_subdomain_policy_is_set() -> None:
    assert dmarc("v=DMARC1; p=reject", domain="mail.shop.example").check.policy == "reject"


@pytest.mark.parametrize("depth", [1, 2, 3, 4, 5, 8])
def test_a_name_of_any_depth_inherits_the_two_label_parents_policy(depth: int) -> None:
    name = ".".join([*"abcdefgh"[:depth], D])

    found = dmarc("v=DMARC1; p=reject", domain=name)

    assert found.check.present is True
    assert found.check.policy == "reject"
    assert found.found_at == D


def test_the_walk_up_always_ends_at_the_two_label_parent_and_asks_four_names_at_most() -> None:
    resolver = FixtureResolver({})

    run(check_dmarc(resolver, "a.b.c.d.e.shop.example"))

    assert resolver.asked == [
        "_dmarc.a.b.c.d.e.shop.example",
        "_dmarc.b.c.d.e.shop.example",
        "_dmarc.c.d.e.shop.example",
        "_dmarc.shop.example",
    ]

    resolver = FixtureResolver({})
    run(check_dmarc(resolver, "mail.shop.example"))
    assert resolver.asked == ["_dmarc.mail.shop.example", "_dmarc.shop.example"]


def test_a_lookup_that_does_not_answer_is_not_read_as_no_record() -> None:
    with pytest.raises(LookupFailedError):
        run(check_dmarc(FixtureResolver({}, timeouts=[f"_dmarc.{D}"]), D))
