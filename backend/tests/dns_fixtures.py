"""Helpers for tests that need DNS data: a zone resolver, keys of a chosen length, and `run`."""

import asyncio
import base64
from collections.abc import Coroutine

from tests.paths import BACKEND

FIXTURES = BACKEND / "fixtures"


def run[T](coroutine: Coroutine[object, object, T]) -> T:
    return asyncio.run(coroutine)


def _der(tag: int, content: bytes) -> bytes:
    size = len(content)
    if size < 0x80:
        return bytes([tag, size]) + content
    length = size.to_bytes((size.bit_length() + 7) // 8)
    return bytes([tag, 0x80 | len(length)]) + length + content


def _integer(value: int) -> bytes:
    # A leading zero byte keeps a number with its top bit set positive, as real keys have it.
    return _der(0x02, value.to_bytes(value.bit_length() // 8 + 1))


def rsa_public_key(bits: int, *, bare: bool = False) -> str:
    """A well-formed RSA public key with a modulus of exactly `bits` bits, in base64.

    It is the right shape and length, not a key anyone could use: the modulus is not a product
    of primes. `bare` gives the older form with no algorithm wrapper.
    """
    modulus = (1 << (bits - 1)) | 0x10001
    key = _der(0x30, _integer(modulus) + _integer(65537))
    if not bare:
        rsa_oid = bytes.fromhex("06092a864886f70d0101010500")
        key = _der(0x30, _der(0x30, rsa_oid) + _der(0x03, b"\x00" + key))
    return base64.b64encode(key).decode("ascii")


def dkim_record(bits: int, *, bare: bool = False) -> str:
    return f"v=DKIM1; k=rsa; p={rsa_public_key(bits, bare=bare)}"
