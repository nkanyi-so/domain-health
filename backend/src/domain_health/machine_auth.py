"""Who may call `/internal/*`: Google's scheduler and task queue, as this project's invoker.

The caller sends a Google-signed OIDC token. It is accepted only if all of these hold: the
signature verifies against Google's current keys, it has not expired, its issuer is Google, its
audience is this service's URL, and its email is the invoker service account's, verified. The
verification is this module's; a test signs tokens with a local key against a fake key set.

The only module that imports the Google auth library and fetches Google's keys.
"""

import time
from collections.abc import Mapping
from typing import Protocol

import httpx2
from google.auth import exceptions as google_errors
from google.auth import jwt

GOOGLE_ISSUERS = frozenset({"https://accounts.google.com", "accounts.google.com"})
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v1/certs"
KEYS_FRESH_SECONDS = 3600.0
FETCH_SECONDS = 5.0


class MachineRefusedError(Exception):
    """The caller is not this project's invoker. The reason is logged, never sent back."""


class KeySet(Protocol):
    async def certs(self) -> Mapping[str, str]:
        """The signer's current certificates, by key ID."""
        ...


class StaticKeySet:
    """A fixed set of certificates. For tests."""

    def __init__(self, certs: Mapping[str, str]) -> None:
        self._certs = dict(certs)

    async def certs(self) -> Mapping[str, str]:
        return self._certs


class GoogleKeySet:
    """Google's signing certificates, fetched over HTTPS and kept for an hour."""

    def __init__(self) -> None:
        self._certs: dict[str, str] = {}
        self._fetched_at = float("-inf")

    async def certs(self) -> Mapping[str, str]:
        if time.monotonic() - self._fetched_at > KEYS_FRESH_SECONDS:
            async with httpx2.AsyncClient(timeout=FETCH_SECONDS) as client:
                response = await client.get(GOOGLE_CERTS_URL)
            response.raise_for_status()
            self._certs = {str(kid): str(pem) for kid, pem in response.json().items()}
            self._fetched_at = time.monotonic()
        return self._certs


def bearer_token(authorization: str | None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise MachineRefusedError("no bearer token")
    return token.strip()


async def verify(token: str, *, keys: KeySet, audience: str, invoker_email: str) -> None:
    """Return if the token is the invoker's for this service. Otherwise `MachineRefusedError`."""
    try:
        certs = await keys.certs()
        # Checks the signature against the certificate the token names (against every current
        # one if it names none), the expiry and the audience. A token that names a key that is
        # not in the set is refused.
        claims: Mapping[str, object] = jwt.decode(token, certs=certs, audience=audience)  # type: ignore[no-untyped-call]
    except (ValueError, google_errors.GoogleAuthError, httpx2.HTTPError) as error:
        raise MachineRefusedError(f"the token did not verify: {type(error).__name__}") from error
    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise MachineRefusedError("the token is not from Google")
    if claims.get("email") != invoker_email or claims.get("email_verified") is not True:
        raise MachineRefusedError("the token is not the invoker service account's")
