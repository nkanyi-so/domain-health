"""`/api/*`: what the frontend's server may ask, and everything that is refused."""

import asyncio
import dataclasses
from datetime import timedelta

import pytest
from pydantic import ValidationError

from domain_health.app import create_app
from domain_health.domain_name import Refusal
from domain_health.settings import Settings
from domain_health.store import LIVE_PER_DAY, SHARED, day_counter
from domain_health.store.memory import MemoryStore
from tests.app_fixtures import (
    ADMIN,
    NOW,
    PROXY_SECRET,
    SESSION,
    VISITOR,
    Built,
    ZoneResolver,
    at,
    build,
    machine,
)
from tests.dns_fixtures import run
from tests.test_worker import output

CLIENT = "brindle-and-oak"
DOMAIN = f"{CLIENT}.example"
DAY = NOW.date().isoformat()
ADDRESS = {"X-Client-Address": "203.0.113.7"}
ZONE = {
    "example.com": ["v=spf1 -all"],
    "_dmarc.example.com": ["v=DMARC1; p=reject"],
}


def with_a_day(count: int = 7) -> Built:
    built = build(outputs={DOMAIN: output(count)})
    assert built.client.post(f"/internal/worker/{CLIENT}", headers=machine()).status_code == 200
    return built


def risk(built: Built, index: int) -> str:
    page = built.client.get(f"/api/clients/{CLIENT}/snapshot", headers=ADMIN).json()
    ranked: list[dict[str, str]] = page["snapshot"]["ranked"]
    return ranked[index]["id"]


ROUTES = [
    ("get", "/api/clients", None),
    ("get", f"/api/clients/{CLIENT}/snapshot", None),
    ("post", f"/api/clients/{CLIENT}/handled", {"day": DAY, "risk_id": "x"}),
    ("post", f"/api/clients/{CLIENT}/reopen", {"day": DAY, "risk_id": "x"}),
    ("post", "/api/live-check", {"domain": "example.com"}),
]


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-Actor": "admin"},
        {"X-Proxy-Secret": "", "X-Actor": "admin"},
        {"X-Proxy-Secret": PROXY_SECRET + "x", "X-Actor": "admin"},
        {"X-Proxy-Secret": PROXY_SECRET[:-1], "X-Actor": "admin"},
        machine(),
    ],
    ids=["nothing", "no secret", "empty", "longer", "shorter", "a machine token"],
)
def test_every_api_route_refuses_a_call_without_the_proxy_secret(
    method: str, path: str, body: dict[str, str] | None, headers: dict[str, str]
) -> None:
    built = with_a_day()

    response = built.client.request(method, path, json=body, headers={**headers, **ADDRESS})

    assert response.status_code == 401
    assert built.resolver.asked == []


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
@pytest.mark.parametrize("actor", [None, "", "visitor", "sandbox:", "sandbox:short", "Admin"])
def test_every_api_route_refuses_a_call_with_no_actor(
    method: str, path: str, body: dict[str, str] | None, actor: str | None
) -> None:
    built = with_a_day()
    headers = {"X-Proxy-Secret": PROXY_SECRET, **ADDRESS}
    if actor is not None:
        headers["X-Actor"] = actor

    response = built.client.request(method, path, json=body, headers=headers)

    assert response.status_code == 400
    assert built.resolver.asked == []


def test_the_client_list_names_all_twelve_and_summarises_today() -> None:
    built = with_a_day()

    body = built.client.get("/api/clients", headers=VISITOR).json()

    assert body["day"] == DAY
    assert len(body["clients"]) == 12
    by_id = {client["id"]: client for client in body["clients"]}
    assert by_id[CLIENT]["domain"] == DOMAIN
    assert by_id[CLIENT]["seeded"] is True
    today = by_id[CLIENT]["today"]
    assert (today["risks_visible"], today["risks_handled"], today["risks_status"]) == (
        5,
        0,
        "ranked",
    )
    # A client the worker has not run today has no summary: the page says "no snapshot today".
    assert by_id["copperkettle-kitchen"]["today"] is None


def test_a_snapshot_is_read_for_today_or_a_named_day() -> None:
    built = with_a_day()

    page = built.client.get(f"/api/clients/{CLIENT}/snapshot", headers=VISITOR).json()

    assert page["id"] == CLIENT
    assert page["scope"] == "sandbox"
    assert page["snapshot"]["day"] == DAY
    assert len(page["snapshot"]["visible"]) == 5
    assert page["snapshot"]["model_source"] == "recorded"
    assert page["handled"] == {}
    same = built.client.get(f"/api/clients/{CLIENT}/snapshot?day={DAY}", headers=VISITOR)
    assert same.json() == page


def test_what_is_not_there_is_not_found() -> None:
    client = with_a_day().client

    assert client.get("/api/clients/nobody/snapshot", headers=ADMIN).status_code == 404
    path = f"/api/clients/{CLIENT}/snapshot"
    assert client.get(f"{path}?day=2026-02-01", headers=ADMIN).status_code == 404
    assert client.get(f"{path}?day=yesterday", headers=ADMIN).status_code == 422
    assert client.get("/api/clients/..%2F..%2Fsandboxes/snapshot", headers=ADMIN).status_code == 404


def test_a_visitors_click_is_their_own_and_an_admins_is_shared() -> None:
    built = with_a_day()
    first, second = risk(built, 0), risk(built, 1)
    other = {"X-Proxy-Secret": PROXY_SECRET, "X-Actor": f"sandbox:{'b' * 32}"}
    path = f"/api/clients/{CLIENT}"

    clicked = built.client.post(
        f"{path}/handled", json={"day": DAY, "risk_id": first}, headers=VISITOR
    )

    assert clicked.status_code == 200
    visible = [item["id"] for item in clicked.json()["snapshot"]["visible"]]
    assert first not in visible
    assert len(visible) == 5
    assert list(clicked.json()["handled"]) == [first]
    for headers in (ADMIN, other):
        seen = built.client.get(f"{path}/snapshot", headers=headers).json()
        assert seen["handled"] == {}
        assert seen["snapshot"]["visible"][0]["id"] == first

    built.client.post(f"{path}/handled", json={"day": DAY, "risk_id": second}, headers=ADMIN)

    shared = built.client.get(f"{path}/snapshot", headers=ADMIN).json()
    assert shared["scope"] == "shared"
    assert list(shared["handled"]) == [second]
    mine = built.client.get(f"{path}/snapshot", headers=VISITOR).json()
    assert list(mine["handled"]) == [first]

    reopened = built.client.post(
        f"{path}/reopen", json={"day": DAY, "risk_id": first}, headers=VISITOR
    )
    assert reopened.json()["handled"] == {}
    assert reopened.json()["snapshot"]["visible"][0]["id"] == first


def test_a_click_survives_the_next_daily_run() -> None:
    built = with_a_day()
    first = risk(built, 0)
    path = f"/api/clients/{CLIENT}"
    built.client.post(f"{path}/handled", json={"day": DAY, "risk_id": first}, headers=ADMIN)

    assert built.client.post(f"/internal/worker/{CLIENT}", headers=machine()).status_code == 200

    seen = built.client.get(f"{path}/snapshot", headers=ADMIN).json()
    assert first not in [item["id"] for item in seen["snapshot"]["visible"]]
    assert [item["id"] for item in seen["snapshot"]["suppressed"]] == [first]


@pytest.mark.parametrize("action", ["handled", "reopen"])
def test_a_click_that_names_no_real_risk_or_day_is_refused(action: str) -> None:
    built = with_a_day()
    path = f"/api/clients/{CLIENT}/{action}"
    real = risk(built, 0)

    def post(body: object, client_path: str = path) -> int:
        return built.client.post(client_path, json=body, headers=ADMIN).status_code

    assert post({"day": DAY, "risk_id": "made_up:" + DOMAIN}) == 422
    assert post({"day": DAY, "risk_id": real + " "}) == 422
    assert post({"day": DAY, "risk_id": "x" * 201}) == 422
    assert post({"day": "2026-02-01", "risk_id": real}) == 404
    assert post({"day": "soon", "risk_id": real}) == 422
    assert post({"risk_id": real}) == 422
    assert post([]) == 422
    assert post({"day": DAY, "risk_id": real}, f"/api/clients/nobody/{action}") == 404
    seen = built.client.get(f"/api/clients/{CLIENT}/snapshot", headers=ADMIN).json()
    assert seen["handled"] == {}


def live(
    built: Built, domain: str = "example.com", address: str = "203.0.113.7"
) -> tuple[int, dict]:  # type: ignore[type-arg]
    response = built.client.post(
        "/api/live-check",
        json={"domain": domain},
        headers={**VISITOR, "X-Client-Address": address},
    )
    return response.status_code, response.json()


def test_a_typed_domain_gets_checks_and_fixes_and_no_risks() -> None:
    built = build(resolver=ZoneResolver(ZONE))

    status, body = live(built, " Example.COM. ")

    assert status == 200
    assert body["domain"] == "example.com"
    assert body["cached"] is False
    assert body["checks"]["spf"]["check"]["all_qualifier"] == "-all"
    assert body["checks"]["dmarc"]["check"]["policy"] == "reject"
    assert [fix["type"] for fix in body["fixes"]] == ["dkim_missing"]
    assert "risks" not in body
    assert "ranked" not in body
    assert 0 < body["queries"] <= 40
    assert all(name.endswith("example.com") for name in built.resolver.asked)


REFUSED_INPUT = {
    "192.0.2.10": Refusal.IP_ADDRESS,
    "[2001:db8::1]": Refusal.IP_ADDRESS,
    "localhost": Refusal.RESERVED,
    "intranet": Refusal.INTERNAL,
    "mail": Refusal.SINGLE_LABEL,
    "a" * 60
    + "."
    + "b" * 60
    + "."
    + "c" * 60
    + "."
    + "d" * 60
    + "."
    + "e" * 20
    + ".com": Refusal.TOO_LONG,
    "shop.example": Refusal.RESERVED,
    "printer.local": Refusal.INTERNAL,
    "https://example.com": Refusal.SCHEME,
    "example.com/path": Refusal.PATH,
    "example.com:8080": Refusal.PORT,
}


@pytest.mark.parametrize("typed", list(REFUSED_INPUT))
def test_what_is_not_a_public_domain_name_is_refused_before_any_lookup(typed: str) -> None:
    built = build(resolver=ZoneResolver(ZONE))

    status, body = live(built, typed)

    assert status == 422
    assert body["detail"]["refused"] == REFUSED_INPUT[typed].name.lower()
    assert built.resolver.asked == []
    assert isinstance(built.store, MemoryStore)
    assert built.store.documents == 0


def test_a_live_check_without_an_address_to_limit_by_is_not_made() -> None:
    built = build(resolver=ZoneResolver(ZONE))

    for headers in (
        VISITOR,
        {**VISITOR, "X-Client-Address": " "},
        {**VISITOR, "X-Client-Address": "9" * 65},
        {**VISITOR, "X-Client-Address": "not-an-address"},
        {**VISITOR, "X-Client-Address": "203.0.113.7, 198.51.100.4"},
        {**VISITOR, "X-Client-Address": "203.0.113.7:4431"},
        {**VISITOR, "X-Client-Address": "2001:db8::7%eth0"},
    ):
        response = built.client.post(
            "/api/live-check", json={"domain": "example.com"}, headers=headers
        )
        assert response.status_code == 400
    assert built.resolver.asked == []


def test_the_sixth_check_from_one_address_in_ten_minutes_is_refused() -> None:
    built = build(resolver=ZoneResolver(ZONE))
    names = [f"site-{n}.example.com" for n in range(7)]

    statuses = [live(built, name)[0] for name in names[:6]]

    assert statuses == [200, 200, 200, 200, 200, 429]
    asked_before = len(built.resolver.asked)
    status, body = live(built, names[6])
    assert (status, body["detail"]) == (429, {"refused": "rate_limited"})
    assert len(built.resolver.asked) == asked_before
    # Another address is not held back by this one, and ten minutes later neither is this one.
    assert live(built, names[6], address="198.51.100.4")[0] == 200
    later = at(built, NOW + timedelta(minutes=10))
    assert live(later, "later.example.com")[0] == 200


def test_ten_checks_at_once_from_one_address_give_at_most_five() -> None:
    built = build(resolver=ZoneResolver(ZONE))
    address = "203.0.113.7"

    async def fire() -> list[object]:
        from domain_health.app import address_key

        return await asyncio.gather(
            *(built.store.take_live_check_slot(address_key(address), NOW) for _ in range(10))
        )

    given = run(fire())

    assert sum(slot == "taken" for slot in given) == 5
    assert sum(slot == "rate_limited" for slot in given) == 5


def test_with_the_days_counter_at_200_the_next_check_is_refused() -> None:
    built = build(resolver=ZoneResolver(ZONE))
    assert isinstance(built.store, MemoryStore)
    built.store.counters[day_counter(NOW)] = LIVE_PER_DAY - 1

    assert live(built, "one.example.com")[0] == 200
    status, body = live(built, "two.example.com", address="198.51.100.4")

    assert (status, body["detail"]) == (429, {"refused": "daily_cap"})
    assert built.store.counters[day_counter(NOW)] == LIVE_PER_DAY
    # The next UTC day starts a new count.
    tomorrow = at(built, NOW + timedelta(days=1))
    assert live(tomorrow, "two.example.com", address="198.51.100.4")[0] == 200


def test_a_repeat_within_ten_minutes_is_served_from_the_cache_and_costs_nothing() -> None:
    built = build(resolver=ZoneResolver(ZONE))
    first_status, first = live(built)
    asked = len(built.resolver.asked)
    assert isinstance(built.store, MemoryStore)
    counted = dict(built.store.counters)

    for _ in range(8):
        status, again = live(built)
        assert status == 200
        assert again["cached"] is True
        assert again["checks"] == first["checks"]

    assert first_status == 200
    assert len(built.resolver.asked) == asked
    assert built.store.counters == counted
    # After ten minutes it is looked up again.
    later = at(built, NOW + timedelta(minutes=10))
    assert live(later)[1]["cached"] is False


def test_a_seeded_domain_cannot_be_typed() -> None:
    status, body = live(build(), DOMAIN)

    assert (status, body["detail"]["refused"]) == (422, "reserved")


def test_shared_state_is_only_changed_by_the_admin_actor() -> None:
    built = with_a_day()
    first = risk(built, 0)

    built.client.post(
        f"/api/clients/{CLIENT}/handled", json={"day": DAY, "risk_id": first}, headers=VISITOR
    )

    shared = run(built.store.read_day(SHARED, CLIENT, NOW.date(), NOW))
    assert shared is not None
    assert shared.handled == {}
    assert SESSION in VISITOR["X-Actor"]


def test_the_app_is_not_built_with_an_empty_proxy_secret() -> None:
    """An empty secret would equal an absent header and let every call through."""
    deps = dataclasses.replace(build().deps, proxy_secret="")

    with pytest.raises(ValueError, match="proxy secret"):
        create_app(deps)


@pytest.mark.parametrize("secret", ["", "short", "x" * 31])
def test_the_service_does_not_start_with_a_short_proxy_secret(
    monkeypatch: pytest.MonkeyPatch, secret: str
) -> None:
    for name, value in {
        "GCP_PROJECT_ID": "demo-project",
        "SERVICE_URL": "https://service.example",
        "INVOKER_EMAIL": "invoker@demo-project.example",
        "PROXY_SECRET": secret,
    }.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)

    monkeypatch.setenv("PROXY_SECRET", "x" * 32)
    assert Settings(_env_file=None).proxy_secret.get_secret_value() == "x" * 32


def test_one_address_written_two_ways_is_one_visitor() -> None:
    built = build(resolver=ZoneResolver(ZONE))
    # The third is another address in the same /64: one visitor's network.
    spellings = ["2001:db8::7", "2001:0db8:0000:0000:0000:0000:0000:0007", " 2001:DB8::abcd:1 "]

    codes = [live(built, f"site-{n}.example.com", spellings[n % 3])[0] for n in range(6)]

    assert codes == [200] * 5 + [429]


def test_an_ipv4_address_inside_an_ipv6_one_is_the_same_visitor() -> None:
    built = build(resolver=ZoneResolver(ZONE))
    spellings = ["203.0.113.7", "::ffff:203.0.113.7"]

    codes = [live(built, f"site-{n}.example.com", spellings[n % 2])[0] for n in range(6)]

    assert codes == [200] * 5 + [429]
    # Another /64 and another IPv4 address are other visitors.
    assert live(built, "other-a.example.com", "2001:db8:0:1::7")[0] == 200
    assert live(built, "other-b.example.com", "203.0.113.8")[0] == 200
