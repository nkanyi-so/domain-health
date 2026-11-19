"""SPF: present, single, parses, how many DNS lookups it costs, and how it ends.

The count follows RFC 7208's limit of ten: `include`, `a`, `mx`, `ptr`, `exists` and `redirect`
each cost one, in the record and in every record it pulls in. Includes and redirects are followed
as TXT lookups; the other terms are counted and not resolved, because nothing here resolves an
address. Counting stops as soon as the limit is passed, so a loop and a long chain both read as
`OVER_LIMIT`: "more than ten".
"""

import ipaddress
import re
from dataclasses import dataclass, field
from typing import get_args

from domain_health.checks import LookupFailedError, SpfFinding
from domain_health.models import AllQualifier, SpfCheck
from domain_health.resolver import Resolver, TxtStatus, normal_name

LOOKUP_LIMIT = 10
OVER_LIMIT = LOOKUP_LIMIT + 1

_MODIFIER = re.compile(r"^([a-z][a-z0-9_.\-]*)=(.*)$", re.IGNORECASE | re.ASCII)
_MECHANISM = re.compile(r"^([+\-~?]?)([a-z0-9]+)(?::([^/]*))?(/.*)?$", re.IGNORECASE | re.ASCII)
# A name another record is looked up at: dot-separated labels of letters, digits, "-" and "_".
_TARGET_LABEL = re.compile(r"[a-z0-9_\-]{1,63}", re.IGNORECASE | re.ASCII)
_CIDR = re.compile(r"^(/\d{1,3})?(//\d{1,3})?$")
_COSTS_A_LOOKUP = {"include", "a", "mx", "ptr", "exists"}
_QUALIFIERS: dict[str, AllQualifier] = {q[0]: q for q in get_args(AllQualifier)}


class SpfSyntaxError(ValueError):
    pass


@dataclass(frozen=True)
class Record:
    """One parsed record: what it costs, what it pulls in, and how it ends."""

    lookups: int
    includes: tuple[str, ...]
    redirect: str | None
    all_qualifier: AllQualifier | None


@dataclass
class _Walk:
    count: int = 0
    problems: list[str] = field(default_factory=list)

    @property
    def over(self) -> bool:
        return self.count > LOOKUP_LIMIT


def is_spf(record: str) -> bool:
    text = record.strip().lower()
    return text == "v=spf1" or text.startswith("v=spf1 ")


def _target(term: str, value: str | None) -> str:
    """The domain a term names, or `SpfSyntaxError`. A name with a macro (%{...}) is left as is:
    it depends on the message, and is never looked up here."""
    if not value:
        raise SpfSyntaxError(f"{term} needs a domain")
    if "%" in value:
        return value
    name = normal_name(value)
    labels = name.split(".")
    if len(name) > 253 or not all(_TARGET_LABEL.fullmatch(label) for label in labels):
        raise SpfSyntaxError(f"{term} names something that is not a domain")
    return name


def _network(kind: str, value: str | None, cidr: str | None) -> None:
    try:
        if not value:
            raise ValueError("no address")
        network = ipaddress.ip_network(value + (cidr or ""), strict=False)
    except ValueError as error:
        raise SpfSyntaxError(f"{kind} needs an address: {error}") from error
    if network.version != (4 if kind == "ip4" else 6):
        raise SpfSyntaxError(f"{kind} holds an address of the other kind")


def parse(record: str) -> Record:
    """Parse one record's terms. Raises `SpfSyntaxError` with the reason in plain words."""
    lookups = 0
    includes: list[str] = []
    redirect: str | None = None
    all_qualifier: AllQualifier | None = None
    seen_modifiers: set[str] = set()
    if not record.isascii():
        # The standard's records are ASCII. A look-alike letter would otherwise be folded into a
        # different name from the one the record states.
        raise SpfSyntaxError("the record holds a character outside ASCII")
    # Terms are separated by spaces and nothing else; a tab or a line break is part of a term.
    for term in [term for term in record.strip().split(" ") if term][1:]:
        modifier = _MODIFIER.match(term)
        if modifier:
            name, value = modifier.group(1).lower(), modifier.group(2)
            if name in ("redirect", "exp"):
                if name in seen_modifiers:
                    raise SpfSyntaxError(f"{name}= appears more than once")
                seen_modifiers.add(name)
                target = _target(f"{name}=", value)
            if name == "redirect":
                redirect = target
            continue
        mechanism = _MECHANISM.match(term)
        if not mechanism:
            raise SpfSyntaxError("cannot read one of the terms")
        qualifier, name, value, cidr = mechanism.groups()
        name = name.lower()
        # A receiver never reaches a term behind `all`. It still has to parse, but it costs no
        # lookup and nothing it names is followed.
        reached = all_qualifier is None
        if name == "all":
            if value is not None or cidr:
                raise SpfSyntaxError("all takes no value")
            if all_qualifier is None:
                all_qualifier = _QUALIFIERS[qualifier or "+"]
        elif name in ("ip4", "ip6"):
            _network(name, value, cidr)
        elif name in ("include", "exists"):
            if cidr:
                raise SpfSyntaxError(f"{name} needs a domain")
            target = _target(name, value)
            if name == "include" and reached:
                includes.append(target)
        elif name in ("a", "mx", "ptr"):
            if not _CIDR.match(cidr or "") or (name == "ptr" and cidr):
                raise SpfSyntaxError(f"cannot read the term {name!r}")
            if value is not None:
                _target(name, value)
        else:
            raise SpfSyntaxError(f"unknown mechanism {name!r}")
        if name in _COSTS_A_LOOKUP and reached:
            lookups += 1
    # A redirect is only followed when no `all` ends the record first.
    if all_qualifier is not None:
        redirect = None
    elif redirect is not None:
        lookups += 1
    return Record(lookups, tuple(includes), redirect, all_qualifier)


async def _spf_records(resolver: Resolver, name: str) -> list[str]:
    answer = await resolver.txt(name)
    if answer.status is TxtStatus.TIMEOUT:
        raise LookupFailedError(f"the lookup of {name} did not answer")
    return [record for record in answer.records if is_spf(record)]


class _StopCountingError(Exception):
    """The limit is passed: nothing further needs to be looked up."""


async def _follow(
    resolver: Resolver, name: str, path: tuple[str, ...], walk: _Walk
) -> AllQualifier | None:
    """Read the one record at `name`, count it and what it pulls in; give back how it ends."""
    if name in path:
        walk.problems.append(f"include loop: {' > '.join((*path, name))}")
        walk.count = OVER_LIMIT
        raise _StopCountingError
    records = await _spf_records(resolver, name)
    if len(records) != 1:
        found = "no SPF record" if not records else f"{len(records)} SPF records"
        raise SpfSyntaxError(f"{name} has {found}")
    try:
        record = parse(records[0])
    except SpfSyntaxError as error:
        raise SpfSyntaxError(f"{name}: {error}") from error
    return await _count(resolver, record, (*path, name), walk)


async def _count(
    resolver: Resolver, record: Record, path: tuple[str, ...], walk: _Walk
) -> AllQualifier | None:
    walk.count += record.lookups
    if walk.over:
        walk.count = OVER_LIMIT
        raise _StopCountingError
    # A name with a macro in it (%{...}) depends on the message and cannot be looked up here.
    for target in record.includes:
        if "%" not in target:
            await _follow(resolver, target, path, walk)
    if record.redirect and "%" not in record.redirect:
        # With no `all` of its own, a record that redirects ends the way its target ends.
        return await _follow(resolver, record.redirect, path, walk)
    return record.all_qualifier


async def check_spf(resolver: Resolver, domain: str) -> SpfFinding:
    domain = normal_name(domain)
    records = tuple(await _spf_records(resolver, domain))
    if len(records) != 1:
        check = SpfCheck(
            present=bool(records),
            record_count=len(records),
            valid=None,
            lookup_count=None,
            all_qualifier=None,
        )
        return SpfFinding(check=check, records=records)

    def invalid(problem: str) -> SpfFinding:
        check = SpfCheck(
            present=True, record_count=1, valid=False, lookup_count=None, all_qualifier=None
        )
        return SpfFinding(check=check, records=records, problems=(problem,))

    try:
        top = parse(records[0])
    except SpfSyntaxError as error:
        return invalid(str(error))
    walk = _Walk()
    all_qualifier = top.all_qualifier
    try:
        all_qualifier = await _count(resolver, top, (domain,), walk)
    except _StopCountingError:
        pass
    except SpfSyntaxError as error:
        # A record this one pulls in is missing or broken: receivers fail the whole record.
        return invalid(str(error))
    if walk.over:
        walk.problems.append(f"more than {LOOKUP_LIMIT} DNS lookups")
    check = SpfCheck(
        present=True,
        record_count=1,
        valid=True,
        lookup_count=walk.count,
        all_qualifier=all_qualifier,
    )
    return SpfFinding(check=check, records=records, problems=tuple(walk.problems))
