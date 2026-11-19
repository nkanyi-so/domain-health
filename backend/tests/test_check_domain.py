import pytest

from domain_health import check_domain
from domain_health.check_domain import check, fixes_for, main
from domain_health.checks.run import run_checks
from domain_health.domain_name import DomainRefusedError
from domain_health.resolver.fixture import FixtureResolver
from domain_health.types import FixType
from tests.dns_fixtures import dkim_record, run

D = "shop.example.org"
ZONE = {
    D: ["v=spf1 include:_spf.host.example.org +all"],
    "_spf.host.example.org": ["v=spf1 ip4:192.0.2.0/24 -all"],
    f"k1._domainkey.{D}": [dkim_record(2048)],
}


def test_the_output_names_each_check_what_it_found_and_the_fixes() -> None:
    # 2 for SPF and its include, 12 selectors, 2 names for DMARC.
    out = run(check(FixtureResolver(ZONE), f"  {D.upper()} "))

    assert out.splitlines()[0] == "shop.example.org: live DNS checks (16 TXT lookups)"
    assert "one record, parses, 1 of 10 DNS lookups, ends in +all" in out
    assert "2048-bit RSA key at selector k1" in out
    assert "DMARC\n  no record" in out
    assert "Fixes (2)" in out
    assert "spf_plus_all [dns] Replace +all" in out
    assert "dmarc_missing [dns] Publish a DMARC record" in out
    assert "No risks for a typed domain" in out


def test_a_refused_name_costs_no_lookup() -> None:
    resolver = FixtureResolver(ZONE)

    with pytest.raises(DomainRefusedError):
        run(check(resolver, "https://shop.example.org/"))

    assert resolver.asked == []


def test_the_command_refuses_before_it_builds_a_resolver(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_lookups(*args: object, **kwargs: object) -> None:
        raise AssertionError("a refused name must not reach the checks")

    monkeypatch.setattr(check_domain, "check", no_lookups)

    assert main(["192.0.2.1"]) == 2
    assert main(["shop.example"]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "refused: 192.0.2.1 is an IP address, not a domain name" in captured.err
    assert "refused: shop.example is a reserved name" in captured.err


def test_a_check_that_could_not_be_made_gives_no_fix_and_says_so() -> None:
    resolver = FixtureResolver(ZONE, timeouts=[D, f"_dmarc.{D}"])

    results = run(run_checks(resolver, D))
    out = run(check(FixtureResolver(ZONE, timeouts=[D, f"_dmarc.{D}"]), D))

    # No SPF or DMARC fix: silence is not a missing record.
    assert [fix.type for fix in fixes_for(results)] == []
    assert "SPF\n  could not be checked: the lookup of shop.example.org did not answer" in out
    assert "Fixes (0, from the checks that could be made)" in out


def test_a_typed_domain_never_gets_a_seeded_fix() -> None:
    results = run(run_checks(FixtureResolver({}), D))

    found = [fix.type for fix in fixes_for(results)]

    assert found == [FixType.SPF_MISSING, FixType.DKIM_MISSING, FixType.DMARC_MISSING]


def test_no_line_of_the_output_carries_raw_or_endless_dns_text() -> None:
    hostile = "\x1b[2J" + "x" * 3000
    zones = [
        {D: [f"v=spf1 include:{hostile} -all"]},
        {D: ["v=spf1 include:gone.example.org -all"]},
        {D: [f"v=spf1 {hostile}"]},
        {f"_dmarc.{D}": [f"v=DMARC1; p={hostile}"]},
        {f"_dmarc.{D}": [f"v=DMARC1; p=none; sp={hostile}"]},
        {f"_dmarc.{D}": [f"v=DMARC1; p=none; pct={hostile}"]},
        {f"_dmarc.{D}": [f"v=DMARC1; p=none; {hostile}"]},
        {f"k1._domainkey.{D}": [f"v=DKIM1; p={hostile}"]},
    ]
    for zone in zones:
        out = run(check(FixtureResolver(zone), D))

        assert "\x1b" not in out
        # Everything above the fix list can carry DNS text; the fix list is the rules' own words.
        findings = out.split("\nFixes (")[0].splitlines()
        assert max(len(line) for line in findings) <= 2 + 120 + 3
        assert "problem: " in out


def test_dns_text_is_shown_as_one_plain_cut_line() -> None:
    hostile = "v=spf1 -all \x1b[31m\nFixes (0)\n" + "x" * 500
    out = run(check(FixtureResolver({D: [hostile]}), D))

    shown = next(line for line in out.splitlines() if line.strip().startswith("v=spf1"))
    assert "\x1b" not in out
    assert shown.endswith("...")
    assert len(shown.strip()) == 123
    assert out.count("\nFixes (") == 1
