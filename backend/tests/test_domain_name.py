import pytest

from domain_health.domain_name import DomainRefusedError, Refusal, public_domain

# The eight refusals of the live-check input , one line
# each. The other two refusals, the rate limit and the daily cap, are tested with the API.
THE_EIGHT_REFUSALS = [
    pytest.param("192.0.2.10", Refusal.IP_ADDRESS, id="1 an IP address"),
    pytest.param("localserver", Refusal.SINGLE_LABEL, id="2 a single label"),
    pytest.param(
        ".".join(["a" * 60] * 5) + ".example.com", Refusal.TOO_LONG, id="3 over 253 characters"
    ),
    pytest.param("shop.example", Refusal.RESERVED, id="4 a reserved name"),
    pytest.param("mail.corp.internal", Refusal.INTERNAL, id="5 an internal name"),
    pytest.param("https://example.com", Refusal.SCHEME, id="6 a scheme"),
    pytest.param("example.com/contact", Refusal.PATH, id="7 a path"),
    pytest.param("example.com:8080", Refusal.PORT, id="8 a port"),
]


@pytest.mark.parametrize(("typed", "reason"), THE_EIGHT_REFUSALS)
def test_the_eight_refusals(typed: str, reason: Refusal) -> None:
    with pytest.raises(DomainRefusedError) as refused:
        public_domain(typed)

    assert refused.value.reason is reason


def test_there_are_eight_and_each_is_a_different_refusal() -> None:
    reasons = [param.values[1] for param in THE_EIGHT_REFUSALS]

    assert len(reasons) == 8
    assert len(set(reasons)) == 8


@pytest.mark.parametrize(
    ("typed", "reason"),
    [
        ("2001:db8::1", Refusal.IP_ADDRESS),
        ("[2001:db8::1]", Refusal.IP_ADDRESS),
        ("10.1.2", Refusal.IP_ADDRESS),
        ("localhost", Refusal.RESERVED),
        ("anything.test", Refusal.RESERVED),
        ("a.invalid", Refusal.RESERVED),
        ("hidden.onion", Refusal.RESERVED),
        ("printer.local", Refusal.INTERNAL),
        ("nas.lan", Refusal.INTERNAL),
        ("10.in-addr.arpa", Refusal.INTERNAL),
        ("router.home.arpa", Refusal.INTERNAL),
        ("ftp://example.com", Refusal.SCHEME),
        ("http://192.0.2.1/", Refusal.SCHEME),
        ("example.com/", Refusal.PATH),
        ("example.com?x=1", Refusal.PATH),
        ("example.com#top", Refusal.PATH),
        ("192.0.2.1:53", Refusal.PORT),
        ("example.com:", Refusal.PORT),
        ("", Refusal.NOT_A_NAME),
        ("   ", Refusal.NOT_A_NAME),
        ("exa mple.example.org", Refusal.NOT_A_NAME),
        ("user@example.com", Refusal.NOT_A_NAME),
        ("-bad.example.com", Refusal.NOT_A_NAME),
        ("bad-.example.com", Refusal.NOT_A_NAME),
        ("under_score.example.com", Refusal.NOT_A_NAME),
        ("double..dot.example.com", Refusal.NOT_A_NAME),
        (".example.com", Refusal.NOT_A_NAME),
        ("a" * 64 + ".example.com", Refusal.NOT_A_NAME),
        ("exämple.example.org", Refusal.NOT_A_NAME),
        ("example.com; rm -rf /", Refusal.PATH),
        ("example.123", Refusal.NOT_A_NAME),
        ("*.example.com", Refusal.NOT_A_NAME),
        # A line break inside the text must not carry a refused name past the checks.
        ("oakhaven-outfitters.example\n.", Refusal.NOT_A_NAME),
        ("a.localhost\n.", Refusal.NOT_A_NAME),
        ("foo\n.example.com", Refusal.NOT_A_NAME),
        ("exam\tple.example.org", Refusal.NOT_A_NAME),
        ("example.com\x00", Refusal.NOT_A_NAME),
        # The Kelvin sign lower-cases to an ordinary k; it is not one.
        ("\u212aa.example.com", Refusal.NOT_A_NAME),
        ("http\u017f://example.com", Refusal.NOT_A_NAME),
    ],
)
def test_other_things_that_are_not_a_public_domain_name(typed: str, reason: Refusal) -> None:
    with pytest.raises(DomainRefusedError) as refused:
        public_domain(typed)

    assert refused.value.reason is reason


@pytest.mark.parametrize(
    ("typed", "name"),
    [
        ("example.com", "example.com"),
        ("  Example.COM.  ", "example.com"),
        ("example.com\n", "example.com"),
        ("mail.shop.example.org", "mail.shop.example.org"),
        ("xn--bcher-kva.example.net", "xn--bcher-kva.example.net"),
        ("a-b.example.org", "a-b.example.org"),
        ("123.example.com", "123.example.com"),
        ("a" * 63 + ".example.com", "a" * 63 + ".example.com"),
    ],
)
def test_a_public_name_is_accepted_in_lower_case_with_no_trailing_dot(
    typed: str, name: str
) -> None:
    assert public_domain(typed) == name


def test_253_characters_is_accepted_and_254_is_not() -> None:
    longest = ".".join(["a" * 61, "a" * 61, "a" * 61, "a" * 55]) + ".example.com"
    one_more = "a" + longest

    assert len(longest) == 253
    assert public_domain(longest) == longest
    with pytest.raises(DomainRefusedError) as refused:
        public_domain(one_more)
    assert refused.value.reason is Refusal.TOO_LONG


def test_an_accepted_name_holds_nothing_but_letters_digits_hyphens_and_dots() -> None:
    import string

    allowed = set(string.ascii_lowercase + string.digits + "-.")
    for code in [*range(0x250), 0x212A, 0x2126, 0xFF41, 0x3002, 0xFF0E]:
        for typed in (
            f"exam{chr(code)}ple.example.org",
            f"example.com{chr(code)}",
            f"{chr(code)}a.example.com",
        ):
            try:
                name = public_domain(typed)
            except DomainRefusedError:
                continue
            assert set(name) <= allowed, repr(typed)
