"""Real DNS. The only module that imports the DNS library.

Reached only from the live check of a typed domain and `make check-domain`; seeded clients never
come here. TXT lookups only: no address is ever resolved and nothing is ever connected to.
"""

from collections.abc import Iterable
from typing import Protocol

import dns.asyncresolver
import dns.exception
import dns.name
import dns.resolver

from domain_health.resolver import TxtAnswer, TxtStatus, capped

QUERY_SECONDS = 2.0

# The library's errors this module tells apart, named here so that a test can raise them without
# importing the library itself.
NO_SUCH_NAME_ERROR: type[Exception] = dns.resolver.NXDOMAIN
# Text that cannot be a DNS name at all (an empty label, a label or a name too long).
NOT_A_NAME_ERRORS: tuple[type[Exception], ...] = (dns.exception.SyntaxError, dns.name.NameTooLong)
NO_ANSWER_ERRORS: tuple[type[Exception], ...] = (
    dns.resolver.LifetimeTimeout,
    dns.resolver.NoNameservers,
)


class TxtRdata(Protocol):
    @property
    def strings(self) -> tuple[bytes, ...]: ...


class DnsAnswer(Protocol):
    @property
    def rrset(self) -> Iterable[TxtRdata] | None: ...


class DnsResolver(Protocol):
    """The one call this module makes on the DNS library's resolver."""

    async def resolve(
        self,
        qname: str,
        rdtype: str,
        *,
        tcp: bool,
        lifetime: float,
        search: bool,
        raise_on_no_answer: bool,
    ) -> DnsAnswer: ...


class LiveResolver:
    def __init__(
        self,
        *,
        query_seconds: float = QUERY_SECONDS,
        tcp: bool = False,
        resolver: DnsResolver | None = None,
    ) -> None:
        self._query_seconds = query_seconds
        # UDP by default; TCP is the fallback if a host does not let UDP out (decision 0006).
        self._tcp = tcp
        self._resolver: DnsResolver = resolver or dns.asyncresolver.Resolver()

    async def txt(self, name: str) -> TxtAnswer:
        try:
            answer = await self._resolver.resolve(
                name,
                "TXT",
                tcp=self._tcp,
                lifetime=self._query_seconds,
                search=False,
                raise_on_no_answer=False,
            )
        except (NO_SUCH_NAME_ERROR, *NOT_A_NAME_ERRORS):
            # No such name, or text that cannot be a name: either way nothing is published there.
            return TxtAnswer(status=TxtStatus.NO_SUCH_NAME)
        except dns.exception.DNSException:
            # A timeout, or servers that fail or refuse: either way there is no answer to read,
            # and the check must not take silence for "no record".
            return TxtAnswer(status=TxtStatus.TIMEOUT)
        records = [
            b"".join(rdata.strings).decode("utf-8", errors="replace")
            for rdata in (answer.rrset or [])
        ]
        return TxtAnswer(status=TxtStatus.RECORDS, records=capped(records))
