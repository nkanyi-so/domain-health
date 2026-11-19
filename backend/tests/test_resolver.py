import pytest

from domain_health.resolver import (
    MAX_RECORD_CHARS,
    MAX_RECORDS_PER_NAME,
    CountingResolver,
    QueryBudgetSpentError,
    TxtStatus,
    live,
)
from domain_health.resolver.fixture import FixtureResolver, load_zone
from domain_health.resolver.live import LiveResolver
from tests.dns_fixtures import FIXTURES, run


def test_a_name_in_the_zone_answers_with_its_records() -> None:
    resolver = FixtureResolver({"a.example": ["one", "two"]})

    answer = run(resolver.txt("A.Example."))

    assert answer.status is TxtStatus.RECORDS
    assert answer.records == ("one", "two")


def test_a_name_not_in_the_zone_does_not_exist() -> None:
    answer = run(FixtureResolver({}).txt("a.example"))

    assert answer.status is TxtStatus.NO_SUCH_NAME
    assert answer.records == ()


def test_a_named_timeout_never_answers() -> None:
    resolver = FixtureResolver({"a.example": ["one"]}, timeouts=["a.example"])

    assert run(resolver.txt("a.example")).status is TxtStatus.TIMEOUT


def test_an_answer_at_the_limits_is_given_whole() -> None:
    records = ["x" * MAX_RECORD_CHARS] * MAX_RECORDS_PER_NAME

    answer = run(FixtureResolver({"a.example": records}).txt("a.example"))

    assert answer.status is TxtStatus.RECORDS
    assert answer.records == tuple(records)


@pytest.mark.parametrize(
    "records",
    [["x"] * (MAX_RECORDS_PER_NAME + 1), ["fine", "x" * (MAX_RECORD_CHARS + 1)]],
    ids=["one record too many", "one record too long"],
)
def test_an_answer_over_a_limit_is_too_large_and_never_cut(records: list[str]) -> None:
    answer = run(FixtureResolver({"a.example": records}).txt("a.example"))

    assert answer.status is TxtStatus.TOO_LARGE
    assert answer.records == ()


def test_the_live_resolver_holds_an_answer_to_the_same_limits() -> None:
    many = _Answer([_Rdata(b"x") for _ in range(MAX_RECORDS_PER_NAME + 1)])
    long = _Answer([_Rdata(b"x" * 255, b"y" * (MAX_RECORD_CHARS - 254))])

    assert run(LiveResolver(resolver=_FakeDns(many)).txt("example.com")).status is (
        TxtStatus.TOO_LARGE
    )
    assert run(LiveResolver(resolver=_FakeDns(long)).txt("example.com")).status is (
        TxtStatus.TOO_LARGE
    )


def test_a_later_zone_file_replaces_a_name_from_an_earlier_one() -> None:
    zones = FIXTURES / "zones"

    zone = load_zone([zones / "_services.json", zones / "harbourlight-books.json"])

    assert "_spf.mailbarrow.example" in zone
    assert "_dmarc.harbourlight-books.example" in zone


def test_the_counting_resolver_refuses_the_lookup_after_the_last_allowed() -> None:
    inner = FixtureResolver({"a.example": ["one"]})
    counting = CountingResolver(inner, limit=2)

    run(counting.txt("a.example"))
    run(counting.txt("a.example"))
    with pytest.raises(QueryBudgetSpentError):
        run(counting.txt("a.example"))

    assert counting.queries == 2
    assert len(inner.asked) == 2


class _Rdata:
    def __init__(self, *strings: bytes) -> None:
        self._strings = strings

    @property
    def strings(self) -> tuple[bytes, ...]:
        return self._strings


class _Answer:
    def __init__(self, rrset: list[_Rdata] | None) -> None:
        self._rrset = rrset

    @property
    def rrset(self) -> list[_Rdata] | None:
        return self._rrset


class _FakeDns:
    """Stands in for the DNS library's resolver: answers, or raises what it is given."""

    def __init__(self, outcome: _Answer | Exception) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, object]] = []

    async def resolve(
        self,
        qname: str,
        rdtype: str,
        *,
        tcp: bool,
        lifetime: float,
        search: bool,
        raise_on_no_answer: bool,
    ) -> _Answer:
        self.calls.append(
            {"qname": qname, "rdtype": rdtype, "tcp": tcp, "lifetime": lifetime, "search": search}
        )
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def test_the_live_resolver_asks_for_txt_only_with_a_two_second_limit() -> None:
    fake = _FakeDns(_Answer([_Rdata(b"v=spf1 ", b"-all")]))

    answer = run(LiveResolver(resolver=fake).txt("example.com"))

    assert answer.status is TxtStatus.RECORDS
    # A record sent as several strings is one record.
    assert answer.records == ("v=spf1 -all",)
    assert fake.calls == [
        {"qname": "example.com", "rdtype": "TXT", "tcp": False, "lifetime": 2.0, "search": False}
    ]


def test_the_live_resolver_reads_a_name_with_no_txt_record_as_no_records() -> None:
    answer = run(LiveResolver(resolver=_FakeDns(_Answer(None))).txt("example.com"))

    assert answer.status is TxtStatus.RECORDS
    assert answer.records == ()


def test_the_live_resolver_tells_no_such_name_from_no_answer_in_time() -> None:
    # The DNS library's own errors, named by the one module allowed to import it.
    outcomes = {live.NO_SUCH_NAME_ERROR(): TxtStatus.NO_SUCH_NAME}
    outcomes |= {error(): TxtStatus.TIMEOUT for error in live.NO_ANSWER_ERRORS}
    assert len(outcomes) == 3

    for error, expected in outcomes.items():
        answer = run(LiveResolver(resolver=_FakeDns(error)).txt("example.com"))
        assert answer.status is expected, type(error).__name__


def test_the_live_resolver_reads_text_that_cannot_be_a_name_as_no_such_name() -> None:
    # Silence would make a check "unavailable"; a name that cannot exist publishes nothing.
    assert len(live.NOT_A_NAME_ERRORS) == 2
    for error in live.NOT_A_NAME_ERRORS:
        answer = run(LiveResolver(resolver=_FakeDns(error())).txt("bad..name.example.org"))
        assert answer.status is TxtStatus.NO_SUCH_NAME, error.__name__


def test_the_real_library_refuses_a_malformed_name_before_any_lookup() -> None:
    # The library's own resolver, no fake: these names fail while the name is parsed, so
    # nothing is sent anywhere.
    for name in ("bad..name.example.org", "a" * 64 + ".example.org", ".".join(["a" * 60] * 5)):
        assert run(LiveResolver().txt(name)).status is TxtStatus.NO_SUCH_NAME, name


def test_the_live_resolver_replaces_bytes_that_are_not_text() -> None:
    fake = _FakeDns(_Answer([_Rdata(b"v=spf1 \xff -all")]))

    answer = run(LiveResolver(resolver=fake).txt("example.com"))

    assert answer.records == ("v=spf1 � -all",)
