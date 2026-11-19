"""`make check-domain DOMAIN=<name>`: the three checks over real DNS, and the fix list.

Free. No model, no key, no seeded data: a typed domain has no reputation or sending figures, so it
gets fixes and no risks.
"""

import argparse
import asyncio
import sys

from domain_health.checks import (
    CheckResults,
    DkimFinding,
    DmarcFinding,
    SpfFinding,
    Unavailable,
)
from domain_health.checks.run import run_checks
from domain_health.domain_name import DomainRefusedError, public_domain
from domain_health.models import Fix
from domain_health.resolver import CountingResolver, Resolver
from domain_health.rules import fix_list

# DNS answers are untrusted: shown as text, one line each, cut short.
SHOWN_CHARS = 120


def _shown(record: str) -> str:
    text = "".join(ch if ch.isprintable() else "?" for ch in record)
    return text if len(text) <= SHOWN_CHARS else text[:SHOWN_CHARS] + "..."


def _spf_lines(found: SpfFinding | Unavailable) -> list[str]:
    if isinstance(found, Unavailable):
        return [_shown(f"could not be checked: {found.reason}")]
    check = found.check
    if check.record_count == 0:
        lines = ["no record"]
    elif check.record_count > 1:
        lines = [f"{check.record_count} records (there must be one)"]
    elif not check.valid:
        lines = ["one record, and it does not parse"]
    else:
        ending = check.all_qualifier or "no all"
        lines = [f"one record, parses, {check.lookup_count} of 10 DNS lookups, ends in {ending}"]
    return (
        lines
        + [_shown(f"problem: {p}") for p in found.problems]
        + [_shown(r) for r in found.records]
    )


def _dkim_lines(found: DkimFinding | Unavailable) -> list[str]:
    if isinstance(found, Unavailable):
        return [_shown(f"could not be checked: {found.reason}")]
    check = found.check
    lines = [f"{key.key_bits}-bit RSA key at selector {key.selector}" for key in check.keys]
    lines += [f"a key that is not RSA at selector {selector}" for selector in found.other_keys]
    if not lines:
        lines = [f"no key at any of the {check.selectors_probed} common selectors probed"]
    return lines + [_shown(f"problem: {p}") for p in found.problems]


def _dmarc_lines(found: DmarcFinding | Unavailable) -> list[str]:
    if isinstance(found, Unavailable):
        return [_shown(f"could not be checked: {found.reason}")]
    check = found.check
    if not check.present:
        lines = ["no record"]
    elif not check.valid:
        lines = ["a record, and it does not parse"]
    else:
        subdomains = check.subdomain_policy or "the same"
        lines = [f"policy {check.policy}, subdomains {subdomains}, {check.pct}% of mail"]
    if found.found_at:
        lines.append(_shown(f"found at _dmarc.{found.found_at}"))
    lines += [_shown(f"problem: {p}") for p in found.problems]
    return lines + ([_shown(found.record)] if found.record else [])


def fixes_for(results: CheckResults) -> list[Fix]:
    """The fix list for a typed domain: DNS fixes only, and only for checks that were made."""
    spf, dkim, dmarc = results.spf, results.dkim, results.dmarc
    return fix_list(
        None if isinstance(spf, Unavailable) else spf.check,
        None if isinstance(dkim, Unavailable) else dkim.check,
        None if isinstance(dmarc, Unavailable) else dmarc.check,
        None,
        other_dkim_keys=0 if isinstance(dkim, Unavailable) else len(dkim.other_keys),
    )


def render(results: CheckResults, fixes: list[Fix], queries: int) -> str:
    lines = [f"{results.domain}: live DNS checks ({queries} TXT lookups)", ""]
    sections = (
        ("SPF", _spf_lines(results.spf)),
        ("DKIM", _dkim_lines(results.dkim)),
        ("DMARC", _dmarc_lines(results.dmarc)),
    )
    for title, body in sections:
        lines.append(title)
        lines += [f"  {line}" for line in body]
        lines.append("")
    if results.unavailable:
        lines.append(f"Fixes ({len(fixes)}, from the checks that could be made)")
    else:
        lines.append(f"Fixes ({len(fixes)})")
    lines += [f"  {fix.type.value} [{fix.source}] {fix.instruction}" for fix in fixes]
    lines += ["", "No risks for a typed domain: it has no reputation or sending data."]
    return "\n".join(lines)


async def check(resolver: Resolver, typed: str) -> str:
    """Validate first, then look up. A refused name costs no lookup at all."""
    domain = public_domain(typed)
    counting = CountingResolver(resolver)
    results = await run_checks(counting, domain)
    return render(results, fixes_for(results), counting.queries)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="make check-domain", description=__doc__)
    parser.add_argument("domain")
    parser.add_argument("--tcp", action="store_true", help="look up over TCP instead of UDP")
    args = parser.parse_args(argv)
    try:
        public_domain(args.domain)
    except DomainRefusedError as refused:
        print(f"refused: {_shown(args.domain)} is {refused}", file=sys.stderr)
        return 2
    # Imported here so that only this path, after validation, ever builds the live resolver.
    from domain_health.resolver.live import LiveResolver

    print(asyncio.run(check(LiveResolver(tcp=args.tcp), args.domain)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
