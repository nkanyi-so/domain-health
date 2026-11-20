"""The app built from fakes, and machine tokens signed with a key made here.

No Google library and no network: a token is signed by hand (RS256) with a local key, and the
app is given that key's certificate as its key set, the way it is given Google's in production.
"""

import base64
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from functools import cache

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient

from domain_health.alerts import FakeAlerter
from domain_health.app import Deps, create_app
from domain_health.clock import FixedClock
from domain_health.machine_auth import StaticKeySet
from domain_health.resolver import Resolver, TxtAnswer, TxtStatus
from domain_health.risks.model import FixtureRiskModel
from domain_health.seeded import load_clients
from domain_health.store import SnapshotStore
from domain_health.store.memory import MemoryStore
from domain_health.tasks import FakeQueue
from domain_health.worker import ModelFacts

NOW = datetime(2026, 3, 1, 6, 30, tzinfo=UTC)
SERVICE_URL = "https://service.example"
INVOKER = "invoker@a-project.iam.gserviceaccount.com"
PROXY_SECRET = "a-proxy-secret-for-tests"  # noqa: S105
KEY_ID = "test-key-1"
SESSION = "a" * 32
ADMIN = {"X-Proxy-Secret": PROXY_SECRET, "X-Actor": "admin"}
VISITOR = {"X-Proxy-Secret": PROXY_SECRET, "X-Actor": f"sandbox:{SESSION}"}


@cache
def _key(name: str) -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@cache
def certificate(name: str = "trusted") -> str:
    """A self-signed certificate for a local key, in the form Google publishes its own."""
    key = _key(name)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "tests")])
    built = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime(2026, 1, 1, tzinfo=UTC))
        .not_valid_after(datetime(2036, 1, 1, tzinfo=UTC))
        .sign(key, hashes.SHA256())
    )
    return built.public_bytes(serialization.Encoding.PEM).decode("ascii")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def token(
    *,
    audience: str = SERVICE_URL,
    email: str = INVOKER,
    issuer: str = "https://accounts.google.com",
    expires_in: timedelta = timedelta(minutes=30),
    signed_by: str = "trusted",
    key_id: str | None = KEY_ID,
    email_verified: bool = True,
) -> str:
    """A token as Google's scheduler would send it, with any one part made wrong."""
    now = datetime.now(UTC)
    header: dict[str, object] = {"alg": "RS256", "typ": "JWT"}
    if key_id is not None:
        header["kid"] = key_id
    claims = {
        "iss": issuer,
        "aud": audience,
        "email": email,
        "email_verified": email_verified,
        "iat": int((now - timedelta(minutes=1)).timestamp()),
        "exp": int((now + expires_in).timestamp()),
    }
    signed = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(claims).encode())}"
    signature = _key(signed_by).sign(signed.encode("ascii"), padding.PKCS1v15(), hashes.SHA256())
    return f"{signed}.{_b64(signature)}"


def machine(**parts: object) -> dict[str, str]:
    return {"Authorization": f"Bearer {token(**parts)}"}  # type: ignore[arg-type]


class ZoneResolver:
    """Answers from a dict and counts the lookups, so a test can show DNS was never reached."""

    def __init__(self, records: dict[str, list[str]] | None = None) -> None:
        self.records = records or {}
        self.asked: list[str] = []

    async def txt(self, name: str) -> TxtAnswer:
        self.asked.append(name)
        if name in self.records:
            return TxtAnswer(status=TxtStatus.RECORDS, records=tuple(self.records[name]))
        return TxtAnswer(status=TxtStatus.NO_SUCH_NAME)


class Built:
    """An app and everything behind it, for a test to look at afterwards."""

    def __init__(self, deps: Deps, resolver: ZoneResolver) -> None:
        self.deps = deps
        self.resolver = resolver
        self.client = TestClient(create_app(deps))

    @property
    def store(self) -> SnapshotStore:
        return self.deps.store


def build(
    *,
    store: SnapshotStore | None = None,
    outputs: dict[str, str] | None = None,
    queue: FakeQueue | None = None,
    alerter: FakeAlerter | None = None,
    resolver: ZoneResolver | None = None,
    now: datetime = NOW,
) -> Built:
    resolver = resolver or ZoneResolver()
    live: Resolver = resolver
    deps = Deps(
        store=store or MemoryStore(),
        clock=FixedClock(now),
        clients=tuple(load_clients()),
        model=FixtureRiskModel(outputs or {}),
        facts=ModelFacts(prompt_version="risks-v0", model="a-model"),
        queue=queue or FakeQueue(),
        alerter=alerter or FakeAlerter(),
        keys=StaticKeySet({KEY_ID: certificate()}),
        live_resolver=lambda: live,
        proxy_secret=PROXY_SECRET,
        service_url=SERVICE_URL,
        invoker_email=INVOKER,
    )
    return Built(deps, resolver)


def at(built: Built, now: datetime) -> Built:
    """The same app and store at another time."""
    return Built(replace(built.deps, clock=FixedClock(now)), built.resolver)
