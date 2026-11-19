import base64

import pytest

from domain_health.checks import LookupFailedError
from domain_health.checks.dkim import SELECTORS, check_dkim, rsa_key_bits
from domain_health.resolver.fixture import FixtureResolver
from tests.dns_fixtures import FIXTURES, dkim_record, rsa_public_key, run

D = "shop.example"


def at(selector: str) -> str:
    return f"{selector}._domainkey.{D}"


def test_twelve_selectors_are_probed_and_none_names_a_company() -> None:
    assert len(SELECTORS) == 12
    assert len(set(SELECTORS)) == 12

    resolver = FixtureResolver({})
    found = run(check_dkim(resolver, D))

    assert found.check.selectors_probed == 12
    assert found.check.keys == []
    assert sorted(resolver.asked) == sorted(at(s) for s in SELECTORS)


@pytest.mark.parametrize("bits", [512, 768, 1024, 2048, 4096])
@pytest.mark.parametrize("bare", [False, True], ids=["wrapped", "bare"])
def test_the_key_length_is_read_from_the_key(bits: int, bare: bool) -> None:
    key = base64.b64decode(rsa_public_key(bits, bare=bare))

    assert rsa_key_bits(key) == bits


def test_real_keys_made_by_a_key_tool_read_at_their_length() -> None:
    # The seeded zones hold public keys generated at 2,048, 1,024 and 512 bits.
    zones = FIXTURES / "zones"
    expected = {
        ("harbourlight-books", "k1"): 2048,
        ("oakhaven-outfitters", "s1"): 1024,
        ("copperkettle-kitchen", "mail"): 512,
    }
    for (zone, selector), bits in expected.items():
        import json

        records = json.loads((zones / f"{zone}.json").read_text())
        record = records[f"{selector}._domainkey.{zone}.example"][0]
        key = base64.b64decode(record.split("p=")[1])
        assert rsa_key_bits(key) == bits


def test_keys_found_at_two_selectors() -> None:
    zone = {at("k1"): [dkim_record(2048)], at("s2"): [dkim_record(1024)]}

    found = run(check_dkim(FixtureResolver(zone), D))

    assert {(key.selector, key.key_bits) for key in found.check.keys} == {
        ("k1", 2048),
        ("s2", 1024),
    }
    assert found.problems == ()


def test_a_key_split_by_spaces_and_a_record_with_no_version_still_read() -> None:
    key = rsa_public_key(2048)
    zone = {at("mail"): [f"k=rsa; p={key[:60]} {key[60:]}"]}

    found = run(check_dkim(FixtureResolver(zone), D))

    assert [key.key_bits for key in found.check.keys] == [2048]


def test_a_revoked_key_is_not_a_key() -> None:
    found = run(check_dkim(FixtureResolver({at("k1"): ["v=DKIM1; p="]}), D))

    assert found.check.keys == []
    assert found.problems == ("the key at selector k1 has been revoked",)


def test_a_wildcard_of_revoked_keys_is_said_once() -> None:
    zone = {at(selector): ["v=DKIM1; p="] for selector in SELECTORS}

    found = run(check_dkim(FixtureResolver(zone), D))

    assert found.check.keys == []
    assert found.problems == ("every selector probed answers with a revoked (empty) key",)


@pytest.mark.parametrize(
    "value",
    ["not-base64!!", "AAAA", base64.b64encode(b"\x30\x82\xff\xff\x02").decode()],
    ids=["not base64", "not a key", "cut short"],
)
def test_a_key_that_cannot_be_read_is_a_problem_and_not_a_key(value: str) -> None:
    found = run(check_dkim(FixtureResolver({at("k1"): [f"v=DKIM1; p={value}"]}), D))

    assert found.check.keys == []
    assert found.problems == ("the key at selector k1 cannot be read",)


def test_eleven_revoked_selectors_and_one_unreadable_key_are_each_said() -> None:
    zone = {at(selector): ["v=DKIM1; p="] for selector in SELECTORS[:-1]}
    zone[at(SELECTORS[-1])] = ["v=DKIM1; p=AAAA"]

    found = run(check_dkim(FixtureResolver(zone), D))

    assert len(found.problems) == 12
    assert f"the key at selector {SELECTORS[-1]} cannot be read" in found.problems
    assert not any(problem.startswith("every selector") for problem in found.problems)


def test_revoked_keys_at_half_the_selectors_are_not_every_selector() -> None:
    zone = {at(selector): ["v=DKIM1; p=", "v=DKIM1; p="] for selector in SELECTORS[:6]}

    found = run(check_dkim(FixtureResolver(zone), D))

    # Two revoked records at one selector are said once, and nothing is said of the other six.
    assert found.problems == tuple(
        f"the key at selector {selector} has been revoked" for selector in SELECTORS[:6]
    )


def test_a_revoked_key_beside_a_live_one_does_not_hide_the_live_one() -> None:
    zone = {at(selector): ["v=DKIM1; p="] for selector in SELECTORS}
    zone[at("k1")] = ["v=DKIM1; p=", dkim_record(2048)]

    found = run(check_dkim(FixtureResolver(zone), D))

    assert [key.selector for key in found.check.keys] == ["k1"]
    assert len(found.problems) == 12


def test_a_key_that_is_not_rsa_is_found_and_has_no_rsa_length() -> None:
    zone = {at("k1"): ["v=DKIM1; k=ed25519; p=11qYAYKxCrfVS/7TyWQHOg7hcvPapiMlrwIaaPcHURo="]}

    found = run(check_dkim(FixtureResolver(zone), D))

    assert found.check.keys == []
    assert found.other_keys == ("k1",)


def test_a_record_of_another_version_is_not_a_key() -> None:
    key = rsa_public_key(2048)

    found = run(check_dkim(FixtureResolver({at("k1"): [f"v=DKIM2; k=rsa; p={key}"]}), D))

    assert found.check.keys == []
    assert found.other_keys == ()


def test_a_version_tag_that_is_not_first_makes_the_record_no_key() -> None:
    key = rsa_public_key(2048)

    found = run(check_dkim(FixtureResolver({at("k1"): [f"k=rsa; v=DKIM1; p={key}"]}), D))

    assert found.check.keys == []


def test_a_key_type_that_does_not_exist_is_not_a_key() -> None:
    key = rsa_public_key(2048)

    found = run(check_dkim(FixtureResolver({at("k1"): [f"v=DKIM1; k=dsa; p={key}"]}), D))

    assert found.check.keys == []
    assert found.other_keys == ()
    assert found.problems == ("the key at selector k1 cannot be read",)


@pytest.mark.parametrize(
    "record",
    [
        "v=DKIM1; k=ed25519; p=!!!notakey",
        "k=ed25519; p=abc",
        "v=DKIM1; k=ed25519; p=AAAA",
        "v=DKIM1; k=ed25519; p=" + rsa_public_key(1024),
        "v=DKIM1; k=r sa; p=" + rsa_public_key(2048),
        "v=DKIM1; s=other; p=" + rsa_public_key(2048),
        "v=DKIM1; p=MAMCAQA=",
        "v=DKIM1; p=MAICAA==",
        "v=DKIM1; p=MAA=",
    ],
    ids=[
        "not base64",
        "too short",
        "three bytes",
        "not 32 bytes",
        "a broken type",
        "not for email",
        "a modulus of zero",
        "an empty modulus",
        "an empty key",
    ],
)
def test_a_record_no_receiver_could_use_is_not_a_key(record: str) -> None:
    found = run(check_dkim(FixtureResolver({at("mail"): [record]}), D))

    assert found.check.keys == []
    assert found.other_keys == ()
    assert found.problems == ("the key at selector mail cannot be read",)


@pytest.mark.parametrize("services", ["*", "email", "other:email", " email "])
def test_a_key_for_email_or_for_everything_is_a_key(services: str) -> None:
    zone = {at("mail"): [f"v=DKIM1; s={services}; p={rsa_public_key(2048)}"]}

    found = run(check_dkim(FixtureResolver(zone), D))

    assert [key.key_bits for key in found.check.keys] == [2048]


def test_a_txt_record_that_is_not_a_key_is_ignored() -> None:
    found = run(check_dkim(FixtureResolver({at("k1"): ["hello"]}), D))

    assert found.check.keys == []
    assert found.problems == ()


def test_one_selector_that_does_not_answer_makes_the_check_unknown() -> None:
    resolver = FixtureResolver({at("k1"): [dkim_record(2048)]}, timeouts=[at("s1")])

    with pytest.raises(LookupFailedError):
        run(check_dkim(resolver, D))
