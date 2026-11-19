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

from domain_health.checks import SpfFinding, records_at
from domain_health.models import AllQualifier, SpfCheck
from domain_health.resolver import Resolver, normal_name

LOOKUP_LIMIT = 10
OVER_LIMIT = LOOKUP_LIMIT + 1

# The standard's grammar (RFC 7208, section 12), piece by piece, with the two rules its prose
# adds (section 7.3): a macro's digit is never zero, and the letters c, r and t belong to
# explanation text only, never to a name.
_MACRO_SHAPE = r"%\{{[{letters}](?:[1-9][0-9]*)?r?[.\-+,/_=]*\}}|%%|%_|%-"
_MACRO = _MACRO_SHAPE.format(letters="slodiphv")
_LITERAL = r"[\x21-\x24\x26-\x7e]"
# What a name is made of, and what the value of a modifier nobody defined may hold.
_MACRO_STRING = re.compile(rf"(?:{_MACRO}|{_LITERAL})*", re.IGNORECASE | re.ASCII)
_ANY_MACRO_STRING = re.compile(
    rf"(?:{_MACRO_SHAPE.format(letters='slodiphcrtv')}|{_LITERAL})*", re.IGNORECASE | re.ASCII
)
_TOP_LABEL = r"[a-z0-9]*[a-z][a-z0-9]*|[a-z0-9]+-[a-z0-9\-]*[a-z0-9]"
# A name ends in a dot and a top label (with at most one more dot), or in a macro.
_DOMAIN_END = re.compile(rf"(?:\.(?:{_TOP_LABEL})\.?|{_MACRO})$", re.IGNORECASE | re.ASCII)
_MODIFIER = re.compile(r"([a-z][a-z0-9_.\-]*)=(.*)", re.IGNORECASE | re.ASCII)
_MECHANISM = re.compile(r"([+\-~?]?)([a-z][a-z0-9]*)(.*)", re.IGNORECASE | re.ASCII)
_V4_LENGTH, _V6_LENGTH = r"/(0|[1-9][0-9]?)", r"/(0|[1-9][0-9]{0,2})"
# What may follow `a` or `mx`: a name, then a prefix length for each kind of address.
_NAME_AND_LENGTHS = re.compile(rf"(?::(.*?))?(?:{_V4_LENGTH})?(?:/{_V6_LENGTH})?")
_ADDRESS_AND_LENGTH = re.compile(r":([^/]*)(?:/(0|[1-9][0-9]{0,2}))?")
# A name another record is looked up at: dot-separated labels of letters, digits, "-" and "_".
_TARGET_LABEL = re.compile(r"[a-z0-9_\-]{1,63}", re.IGNORECASE | re.ASCII)
_MAX_LENGTH = {4: 32, 6: 128}
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
    """A record is SPF when it is exactly `v=spf1` or starts with that and a space."""
    text = record.lower()
    return text == "v=spf1" or text.startswith("v=spf1 ")


def _target(term: str, value: str | None) -> str:
    """The domain a term names, or `SpfSyntaxError`.

    The value has to fit the standard's grammar for a name: its macros well formed, and its end
    either a top label or a macro. A name with a macro in it depends on the message and is never
    looked up here. Any other name also has to be one DNS can hold (no empty label, 63 characters
    a label, 253 in all): a term that names anything else can be used by no receiver.
    """
    if not value or not _MACRO_STRING.fullmatch(value) or not _DOMAIN_END.search(value):
        raise SpfSyntaxError(f"{term} names something that is not a domain")
    if "%" in value:
        return value
    name = value.removesuffix(".").lower()
    if len(name) > 253 or not all(_TARGET_LABEL.fullmatch(label) for label in name.split(".")):
        raise SpfSyntaxError(f"{term} names something that is not a domain")
    return name


def _length(kind: str, text: str | None, version: int) -> None:
    if text is not None and int(text) > _MAX_LENGTH[version]:
        raise SpfSyntaxError(f"{kind} has a prefix length over {_MAX_LENGTH[version]}")


def _network(kind: str, rest: str) -> None:
    version = 4 if kind == "ip4" else 6
    parts = _ADDRESS_AND_LENGTH.fullmatch(rest)
    if not parts:
        raise SpfSyntaxError(f"{kind} needs an address")
    try:
        address = ipaddress.ip_address(parts.group(1))
    except ValueError as error:
        raise SpfSyntaxError(f"{kind} needs an address") from error
    if address.version != version or "%" in parts.group(1):
        raise SpfSyntaxError(f"{kind} needs an address of its own kind")
    _length(kind, parts.group(2), version)


def _mechanism(name: str, rest: str) -> str | None:
    """Check one mechanism's argument against the grammar; give back the name it includes."""
    if name == "all":
        if rest:
            raise SpfSyntaxError("all takes no value")
    elif name in ("ip4", "ip6"):
        _network(name, rest)
    elif name in ("include", "exists"):
        target = _target(name, rest[1:] if rest.startswith(":") else None)
        return target if name == "include" else None
    elif name in ("a", "mx"):
        parts = _NAME_AND_LENGTHS.fullmatch(rest)
        if not parts:
            raise SpfSyntaxError(f"cannot read what follows {name}")
        if parts.group(1) is not None:
            _target(name, parts.group(1))
        _length(name, parts.group(2), 4)
        _length(name, parts.group(3), 6)
    elif name == "ptr":
        if rest:
            _target(name, rest[1:] if rest.startswith(":") else None)
    else:
        raise SpfSyntaxError("a mechanism that does not exist")
    return None


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
    for term in [term for term in record.split(" ") if term][1:]:
        modifier = _MODIFIER.fullmatch(term)
        if modifier:
            name, value = modifier.group(1).lower(), modifier.group(2)
            if name in ("redirect", "exp"):
                if name in seen_modifiers:
                    raise SpfSyntaxError(f"{name}= appears more than once")
                seen_modifiers.add(name)
                target = _target(f"{name}=", value)
                if name == "redirect":
                    redirect = target
            elif not _ANY_MACRO_STRING.fullmatch(value):
                raise SpfSyntaxError("a modifier with a value that cannot be read")
            continue
        mechanism = _MECHANISM.fullmatch(term)
        if not mechanism:
            raise SpfSyntaxError("cannot read one of the terms")
        qualifier, name, rest = mechanism.groups()
        name = name.lower()
        included = _mechanism(name, rest)
        # A receiver never reaches a term behind `all`. It still has to parse, but it costs no
        # lookup and nothing it names is followed.
        if all_qualifier is not None:
            continue
        if name == "all":
            all_qualifier = _QUALIFIERS[qualifier or "+"]
        if included is not None:
            includes.append(included)
        if name in _COSTS_A_LOOKUP:
            lookups += 1
    # A redirect is only followed when no `all` ends the record first.
    if all_qualifier is not None:
        redirect = None
    elif redirect is not None:
        lookups += 1
    return Record(lookups, tuple(includes), redirect, all_qualifier)


async def _spf_records(resolver: Resolver, name: str) -> list[str]:
    records = records_at(name, await resolver.txt(name))
    return [record for record in records if is_spf(record)]


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
