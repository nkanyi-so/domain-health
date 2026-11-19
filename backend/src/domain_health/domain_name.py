"""Is the typed text a public domain name? Decided before any lookup is made.

The text is only ever used as a DNS query name. Anything that is not plainly a public host name is
refused with a reason; nothing is repaired or guessed.
"""

import ipaddress
import re
from enum import StrEnum

MAX_NAME_CHARS = 253
MAX_LABEL_CHARS = 63

_SCHEME = re.compile(r"^[a-z][a-z0-9+.\-]*://", re.IGNORECASE | re.ASCII)
_PORT = re.compile(r":\d*$")
_LABEL = re.compile(r"[a-z0-9]([a-z0-9\-]*[a-z0-9])?")

# Special-use names that are never a public sending domain. The three documentation domains
# (example.com, .net, .org) are real zones that answer, and are allowed.
RESERVED_SUFFIXES = ("example", "test", "invalid", "localhost", "onion", "alt")
INTERNAL_SUFFIXES = (
    "local",
    "internal",
    "lan",
    "home",
    "corp",
    "intranet",
    "localdomain",
    "private",
    "arpa",
)


class Refusal(StrEnum):
    IP_ADDRESS = "an IP address, not a domain name"
    SINGLE_LABEL = "a single label: a domain name has at least two parts"
    TOO_LONG = "longer than 253 characters"
    RESERVED = "a reserved name that no one can send mail from"
    INTERNAL = "an internal name, not a public domain"
    SCHEME = "a web address: leave out the scheme and give the domain only"
    PATH = "a web address: leave out the path and give the domain only"
    PORT = "a domain with a port: give the domain only"
    NOT_A_NAME = "not a domain name"


class DomainRefusedError(ValueError):
    def __init__(self, reason: Refusal) -> None:
        super().__init__(reason.value)
        self.reason = reason


def _is_ip(text: str) -> bool:
    try:
        ipaddress.ip_address(text.strip("[]"))
    except ValueError:
        return False
    return True


def public_domain(text: str) -> str:
    """The name in lower case with no trailing dot, or `DomainRefusedError` saying why not."""
    name = text.strip()
    if not name.isascii():
        # Before any lower-casing: some letters outside ASCII lower-case into ASCII ones.
        raise DomainRefusedError(Refusal.NOT_A_NAME)
    if _SCHEME.match(name):
        raise DomainRefusedError(Refusal.SCHEME)
    if _is_ip(name):
        raise DomainRefusedError(Refusal.IP_ADDRESS)
    if any(mark in name for mark in "/?#"):
        raise DomainRefusedError(Refusal.PATH)
    if _PORT.search(name):
        raise DomainRefusedError(Refusal.PORT)
    name = name.removesuffix(".").lower()
    if len(name) > MAX_NAME_CHARS:
        raise DomainRefusedError(Refusal.TOO_LONG)
    labels = name.split(".")
    if not all(len(label) <= MAX_LABEL_CHARS and _LABEL.fullmatch(label) for label in labels):
        raise DomainRefusedError(Refusal.NOT_A_NAME)
    if all(label.isdecimal() for label in labels):
        raise DomainRefusedError(Refusal.IP_ADDRESS)
    if labels[-1] in RESERVED_SUFFIXES:
        raise DomainRefusedError(Refusal.RESERVED)
    if labels[-1] in INTERNAL_SUFFIXES:
        raise DomainRefusedError(Refusal.INTERNAL)
    if len(labels) == 1:
        raise DomainRefusedError(Refusal.SINGLE_LABEL)
    if labels[-1].isdecimal():
        raise DomainRefusedError(Refusal.NOT_A_NAME)
    return name
