"""The three checks for one domain, each with its own time limit."""

import asyncio
from collections.abc import Awaitable, Callable

from domain_health.checks import CheckResults, LookupFailedError, Unavailable
from domain_health.checks.dkim import check_dkim
from domain_health.checks.dmarc import check_dmarc
from domain_health.checks.spf import check_spf
from domain_health.resolver import QueryBudgetSpentError, Resolver, normal_name

CHECK_SECONDS = 8.0


async def _within_limits[Finding](
    check: Callable[[Resolver, str], Awaitable[Finding]],
    resolver: Resolver,
    domain: str,
    seconds: float,
) -> Finding | Unavailable:
    try:
        async with asyncio.timeout(seconds):
            return await check(resolver, domain)
    except TimeoutError:
        return Unavailable(reason=f"the check took longer than {seconds:g} seconds")
    except (LookupFailedError, QueryBudgetSpentError) as error:
        return Unavailable(reason=str(error))


async def run_checks(
    resolver: Resolver, domain: str, *, check_seconds: float = CHECK_SECONDS
) -> CheckResults:
    """Run SPF, DKIM and DMARC side by side. A check that cannot be made says so; it never
    reports a missing record it did not look for."""
    domain = normal_name(domain)
    spf, dkim, dmarc = await asyncio.gather(
        _within_limits(check_spf, resolver, domain, check_seconds),
        _within_limits(check_dkim, resolver, domain, check_seconds),
        _within_limits(check_dmarc, resolver, domain, check_seconds),
    )
    return CheckResults(domain=domain, spf=spf, dkim=dkim, dmarc=dmarc)
