"""DKIM: probe a fixed list of common selectors and read each key's length from the key itself.

A domain's selectors cannot be listed from DNS, so a miss here means "not at a common selector",
and the fix says so. The length is the RSA modulus in the published key, not a guess from the
record's size.
"""

import asyncio
import base64
import binascii
from typing import NamedTuple

from domain_health.checks import DkimFinding, LookupFailedError
from domain_health.models import DkimCheck, DkimKey
from domain_health.resolver import Resolver, TxtStatus, normal_name

# Generic selector names in wide use. Twelve, probed at once.
SELECTORS: tuple[str, ...] = (
    "default",
    "dkim",
    "mail",
    "email",
    "smtp",
    "selector1",
    "selector2",
    "s1",
    "s2",
    "k1",
    "k2",
    "key1",
)

_SEQUENCE, _INTEGER, _BIT_STRING = 0x30, 0x02, 0x03


def tags(record: str) -> dict[str, str]:
    """A `name=value; name=value` list as a mapping. Whitespace inside a value is dropped."""
    found: dict[str, str] = {}
    for part in record.split(";"):
        name, sep, value = part.partition("=")
        if sep and name.strip():
            found.setdefault(name.strip().lower(), "".join(value.split()))
    return found


def _element(data: bytes, at: int) -> tuple[int, int, int]:
    """One DER element starting at `at`: its tag, and where its content starts and ends."""
    if at + 2 > len(data):
        raise ValueError("the key is cut short")
    tag, length, start = data[at], data[at + 1], at + 2
    if length & 0x80:
        size = length & 0x7F
        if not 1 <= size <= 4 or start + size > len(data):
            raise ValueError("the key has a length that cannot be read")
        length = int.from_bytes(data[start : start + size])
        start += size
    if start + length > len(data):
        raise ValueError("the key is cut short")
    return tag, start, start + length


def rsa_key_bits(der: bytes) -> int:
    """The modulus length of an RSA public key, in either of the two forms DKIM records hold."""
    tag, start, _ = _element(der, 0)
    if tag != _SEQUENCE:
        raise ValueError("not a public key")
    tag, inner_start, inner_end = _element(der, start)
    if tag == _SEQUENCE:
        # The usual form: an algorithm, then the bare key wrapped in a bit string.
        tag, bits_start, bits_end = _element(der, inner_end)
        if tag != _BIT_STRING:
            raise ValueError("not a public key")
        der = der[bits_start + 1 : bits_end]
        tag, start, _ = _element(der, 0)
        if tag != _SEQUENCE:
            raise ValueError("not a public key")
        tag, inner_start, inner_end = _element(der, start)
    if tag != _INTEGER:
        raise ValueError("not an RSA public key")
    return int.from_bytes(der[inner_start:inner_end]).bit_length()


class _Probe(NamedTuple):
    keys: list[DkimKey]
    other: list[str]
    problems: list[str]
    # The selector answered, and with nothing but revoked (empty) keys.
    only_revoked: bool


async def _probe(resolver: Resolver, domain: str, selector: str) -> _Probe:
    name = f"{selector}._domainkey.{domain}"
    answer = await resolver.txt(name)
    if answer.status is TxtStatus.TIMEOUT:
        raise LookupFailedError(f"the lookup of {name} did not answer")
    keys: list[DkimKey] = []
    other: list[str] = []
    unreadable = revoked = False
    for record in answer.records:
        found = tags(record)
        if "p" not in found:
            continue
        if not found["p"]:
            revoked = True
        elif found.get("k", "rsa").lower() != "rsa":
            other.append(selector)
        else:
            try:
                bits = rsa_key_bits(base64.b64decode(found["p"], validate=True))
                keys.append(DkimKey(selector=selector, key_bits=bits))
            except ValueError, binascii.Error:
                unreadable = True
    problems = [f"the key at selector {selector} has been revoked"] if revoked else []
    if unreadable:
        problems.append(f"the key at selector {selector} cannot be read")
    only_revoked = revoked and not (keys or other or unreadable)
    return _Probe(keys, other, problems, only_revoked)


async def check_dkim(resolver: Resolver, domain: str) -> DkimFinding:
    domain = normal_name(domain)
    probes = await asyncio.gather(*(_probe(resolver, domain, s) for s in SELECTORS))
    check = DkimCheck(
        selectors_probed=len(SELECTORS),
        keys=[key for probe in probes for key in probe.keys],
    )
    if all(probe.only_revoked for probe in probes):
        # A wildcard record: the domain publishes that no selector of its signs mail.
        problems = ["every selector probed answers with a revoked (empty) key"]
    else:
        problems = [problem for probe in probes for problem in probe.problems]
    return DkimFinding(
        check=check,
        other_keys=tuple(selector for probe in probes for selector in probe.other),
        problems=tuple(problems),
    )
