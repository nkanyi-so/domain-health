import pytest

from domain_health.checks import LookupFailedError
from domain_health.checks.spf import SpfSyntaxError, check_spf, is_spf, parse
from domain_health.resolver.fixture import FixtureResolver
from tests.dns_fixtures import run

D = "shop.example"


def spf(zone: dict[str, list[str]], timeouts: list[str] | None = None):  # type: ignore[no-untyped-def]
    return run(check_spf(FixtureResolver(zone, timeouts or []), D))


def test_no_spf_record() -> None:
    found = spf({D: ["some-other-txt=1"]})

    assert found.check.present is False
    assert found.check.record_count == 0
    assert (found.check.valid, found.check.lookup_count, found.check.all_qualifier) == (
        None,
        None,
        None,
    )


def test_a_domain_that_does_not_exist_has_no_spf_record() -> None:
    assert spf({}).check.present is False


def test_two_spf_records_are_counted_and_not_read() -> None:
    found = spf({D: ["v=spf1 -all", "v=spf1 ~all"]})

    assert found.check.record_count == 2
    assert found.check.valid is None
    assert len(found.records) == 2


def test_a_record_that_only_starts_like_spf_is_not_one() -> None:
    assert not is_spf("v=spf10 -all")
    assert is_spf("V=SPF1 -all")
    assert is_spf("v=spf1")


def test_a_plain_valid_record() -> None:
    found = spf({D: ["v=spf1 ip4:198.51.100.0/24 ip6:2001:db8::/32 -all"]})

    assert found.check.valid is True
    assert found.check.lookup_count == 0
    assert found.check.all_qualifier == "-all"
    assert found.problems == ()


@pytest.mark.parametrize(
    ("ending", "qualifier"),
    [("-all", "-all"), ("~all", "~all"), ("?all", "?all"), ("+all", "+all"), ("all", "+all")],
)
def test_how_the_record_ends(ending: str, qualifier: str) -> None:
    assert spf({D: [f"v=spf1 mx {ending}"]}).check.all_qualifier == qualifier


def test_a_record_with_no_all_ends_in_nothing() -> None:
    found = spf({D: ["v=spf1 mx"]})

    assert found.check.valid is True
    assert found.check.all_qualifier is None


@pytest.mark.parametrize(
    "record",
    [
        "v=spf1 ipv4:198.51.100.7 -all",
        "v=spf1 ip4:not-an-address -all",
        "v=spf1 ip4:2001:db8::1 -all",
        "v=spf1 ip4 -all",
        "v=spf1 include -all",
        "v=spf1 include: -all",
        "v=spf1 a: -all",
        "v=spf1 all:example.com",
        "v=spf1 redirect=a.example redirect=b.example",
        "v=spf1 redirect=",
        "v=spf1 mx/abc -all",
        "v=spf1 !all",
        "v=spf1 include:bad..name.example.org -all",
        "v=spf1 include:.example.org -all",
        "v=spf1 include:" + "a" * 64 + ".example.org -all",
        "v=spf1 include:" + ".".join(["a" * 60] * 5) + " -all",
        "v=spf1 include:na\x1b[2Jme.example.org -all",
        "v=spf1 redirect=bad..name.example.org",
        "v=spf1 exists:bad..name.example.org -all",
        "v=spf1 a:bad..name.example.org -all",
        "v=spf1 mx:spa$ce.example.org -all",
        # Letters outside ASCII that fold into ASCII ones: a long s, the Kelvin sign, a dotless i.
        "v=spf1 include:\u017f.example.org -all",
        "v=spf1 include:\u212a.example.org -all",
        "v=spf1 include:\u0131.example.org -all",
        "v=spf1 redirect=\u017fpf.example.org",
        "v=spf1 \u212ax -all",
        "v=spf1 a:b\u00fccher.example.org -all",
        "v=spf1 mx\t-all",
        "v=spf1 include:one.example\n-all",
    ],
)
def test_a_record_that_does_not_parse(record: str) -> None:
    with pytest.raises(SpfSyntaxError):
        parse(record)

    found = spf({D: [record]})

    assert found.check.valid is False
    assert (found.check.lookup_count, found.check.all_qualifier) == (None, None)
    assert len(found.problems) == 1


def test_each_term_that_costs_a_lookup_is_counted_once() -> None:
    zone = {
        D: ["v=spf1 a mx ptr exists:%{i}.bl.example include:one.example ip4:192.0.2.1 -all"],
        "one.example": ["v=spf1 ip4:192.0.2.2 -all"],
    }

    assert spf(zone).check.lookup_count == 5


def test_lookups_inside_nested_includes_are_counted() -> None:
    zone = {
        D: ["v=spf1 include:one.example include:two.example -all"],
        "one.example": ["v=spf1 include:deep.example a -all"],
        "deep.example": ["v=spf1 mx -all"],
        "two.example": ["v=spf1 ip4:192.0.2.2 -all"],
    }

    # Two includes, then inside the first: an include, an a, and inside that an mx.
    assert spf(zone).check.lookup_count == 5


def chain(length: int) -> dict[str, list[str]]:
    """`length` includes one inside the next: the record costs exactly `length` lookups."""
    zone = {D: ["v=spf1 include:hop1.example -all"]}
    for hop in range(1, length):
        zone[f"hop{hop}.example"] = [f"v=spf1 include:hop{hop + 1}.example -all"]
    zone[f"hop{length}.example"] = ["v=spf1 ip4:192.0.2.1 -all"]
    return zone


def test_a_chain_of_ten_lookups_is_at_the_limit_and_not_over() -> None:
    found = spf(chain(10))

    assert found.check.valid is True
    assert found.check.lookup_count == 10
    assert found.problems == ()


def test_a_chain_of_eleven_lookups_is_over_the_limit() -> None:
    found = spf(chain(11))

    assert found.check.valid is True
    assert found.check.lookup_count == 11
    assert found.check.all_qualifier == "-all"
    assert found.problems == ("more than 10 DNS lookups",)


def test_a_longer_chain_also_reads_as_eleven_and_stops_looking() -> None:
    resolver = FixtureResolver(chain(30))

    found = run(check_spf(resolver, D))

    assert found.check.lookup_count == 11
    # The domain and the ten hops inside the limit: nothing past the point the limit is passed.
    assert len(resolver.asked) == 11


def test_an_include_loop_is_over_the_limit() -> None:
    zone = {
        D: ["v=spf1 include:one.example -all"],
        "one.example": ["v=spf1 include:two.example -all"],
        "two.example": ["v=spf1 include:one.example -all"],
    }
    resolver = FixtureResolver(zone)

    found = run(check_spf(resolver, D))

    assert found.check.valid is True
    assert found.check.lookup_count == 11
    assert "include loop: shop.example > one.example > two.example > one.example" in found.problems
    assert len(resolver.asked) == 3


def test_a_record_that_includes_itself_is_a_loop() -> None:
    found = spf({D: [f"v=spf1 include:{D} -all"]})

    assert found.check.lookup_count == 11


def test_the_same_include_twice_side_by_side_is_not_a_loop() -> None:
    zone = {
        D: ["v=spf1 include:one.example include:one.example -all"],
        "one.example": ["v=spf1 ip4:192.0.2.2 -all"],
    }

    found = spf(zone)

    assert found.check.lookup_count == 2
    assert found.problems == ()


def test_a_redirect_costs_a_lookup_and_gives_the_record_its_ending() -> None:
    zone = {
        D: ["v=spf1 redirect=_spf.host.example"],
        "_spf.host.example": ["v=spf1 include:net.host.example ~all"],
        "net.host.example": ["v=spf1 ip4:192.0.2.0/24 -all"],
    }
    resolver = FixtureResolver(zone)

    found = run(check_spf(resolver, D))

    assert found.check.lookup_count == 2
    assert found.check.all_qualifier == "~all"
    assert len(resolver.asked) == 3


def test_a_redirect_behind_an_all_is_never_followed() -> None:
    resolver = FixtureResolver({D: ["v=spf1 -all redirect=nowhere.example"]})

    found = run(check_spf(resolver, D))

    assert found.check.lookup_count == 0
    assert found.check.all_qualifier == "-all"
    assert resolver.asked == [D]


@pytest.mark.parametrize(
    "target",
    [[], ["v=spf1 -all", "v=spf1 ~all"], ["v=spf1 bogus -all"]],
    ids=["no record", "two records", "does not parse"],
)
def test_an_include_that_cannot_be_read_breaks_the_record(target: list[str]) -> None:
    found = spf({D: ["v=spf1 include:one.example -all"], "one.example": target})

    assert found.check.valid is False
    assert "one.example" in found.problems[0]


def test_an_include_with_a_macro_is_counted_and_not_looked_up() -> None:
    resolver = FixtureResolver({D: ["v=spf1 include:%{d}._spf.host.example -all"]})

    found = run(check_spf(resolver, D))

    assert found.check.valid is True
    assert found.check.lookup_count == 1
    assert resolver.asked == [D]


def test_a_lookup_that_does_not_answer_is_not_read_as_no_record() -> None:
    with pytest.raises(LookupFailedError):
        spf({}, timeouts=[D])

    with pytest.raises(LookupFailedError):
        spf({D: ["v=spf1 include:one.example -all"]}, timeouts=["one.example"])


def test_a_name_that_cannot_be_a_name_is_never_looked_up() -> None:
    resolver = FixtureResolver({D: ["v=spf1 include:bad..name.example.org -all"]})

    found = run(check_spf(resolver, D))

    assert found.check.valid is False
    assert found.problems == ("include names something that is not a domain",)
    assert resolver.asked == [D]


def test_no_problem_line_repeats_text_from_a_record_that_does_not_parse() -> None:
    hostile = "\x1b[2J" + "x" * 3000
    for record in (
        f"v=spf1 {hostile} -all",
        f"v=spf1 include:{hostile} -all",
        f"v=spf1 a:{hostile}",
    ):
        found = spf({D: [record]})

        assert found.check.valid is False
        assert all("\x1b" not in problem and len(problem) < 100 for problem in found.problems)


def test_terms_behind_all_cost_nothing_and_are_never_followed() -> None:
    resolver = FixtureResolver(
        {D: ["v=spf1 ip4:192.0.2.0/24 -all include:gone.example.org a mx exists:x.example.org"]}
    )

    found = run(check_spf(resolver, D))

    assert found.check.valid is True
    assert found.check.lookup_count == 0
    assert found.check.all_qualifier == "-all"
    assert found.problems == ()
    assert resolver.asked == [D]


def test_eleven_includes_behind_all_are_not_over_the_limit() -> None:
    includes = " ".join(f"include:hop{n}.example.org" for n in range(11))

    found = spf({D: [f"v=spf1 mx -all {includes}"]})

    assert found.check.lookup_count == 1
    assert found.problems == ()


def test_an_include_behind_all_that_does_not_answer_does_not_stop_the_check() -> None:
    found = spf({D: ["v=spf1 -all include:slow.example.org"]}, timeouts=["slow.example.org"])

    assert found.check.valid is True


def test_a_term_behind_all_still_has_to_parse() -> None:
    assert spf({D: ["v=spf1 -all include:bad..name.example.org"]}).check.valid is False
    assert spf({D: ["v=spf1 -all bogus"]}).check.valid is False


def test_terms_behind_all_in_an_included_record_cost_nothing_either() -> None:
    zone = {
        D: ["v=spf1 include:one.example -all"],
        "one.example": ["v=spf1 ip4:192.0.2.2 -all include:gone.example mx"],
    }

    found = spf(zone)

    assert found.check.valid is True
    assert found.check.lookup_count == 1
