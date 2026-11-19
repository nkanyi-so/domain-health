"""DMARC: present, parses, policy, subdomain policy, percentage.

A name with no record of its own inherits a parent's, so the lookup walks up from the name towards
its two-label parent, four names at most: for a deeper name, the nearest three and that parent.
What is reported is the policy that applies to the name that was asked about.
"""

import re
from typing import get_args

from domain_health.checks import DmarcFinding, LookupFailedError
from domain_health.checks.dkim import tags
from domain_health.models import DmarcCheck, DmarcPolicy
from domain_health.resolver import Resolver, TxtStatus, normal_name

MAX_NAMES_TRIED = 4
_PCT = re.compile(r"[0-9]{1,3}")
_POLICIES: tuple[str, ...] = get_args(DmarcPolicy)

_MISSING = DmarcCheck(present=False, valid=None, policy=None, subdomain_policy=None, pct=None)
_INVALID = DmarcCheck(present=True, valid=False, policy=None, subdomain_policy=None, pct=None)


class DmarcSyntaxError(ValueError):
    pass


def is_dmarc(record: str) -> bool:
    """A DMARC record opens with the tag `v=DMARC1`, exactly that value (in either case).
    Anything else, `v=DMARC10` included, is not a DMARC record, and receivers pass over it."""
    name, _, value = record.split(";")[0].partition("=")
    return name.strip().lower() == "v" and value.strip().upper() == "DMARC1"


def _policy(name: str, value: str) -> DmarcPolicy:
    for policy in get_args(DmarcPolicy):
        if value.lower() == policy:
            return policy  # type: ignore[no-any-return]
    raise DmarcSyntaxError(f"{name}={value} is not one of {', '.join(_POLICIES)}")


def parse(record: str) -> tuple[DmarcPolicy, DmarcPolicy | None, int]:
    """The policy, the subdomain policy if one is set, and the percentage (100 when unset)."""
    if not record.isascii():
        # The standard's records are ASCII; digits and letters from other scripts are not read.
        raise DmarcSyntaxError("the record holds a character outside ASCII")
    for part in record.split(";"):
        if part.strip() and "=" not in part:
            raise DmarcSyntaxError(f"cannot read {part.strip()!r}")
    found = tags(record)
    if "p" not in found:
        raise DmarcSyntaxError("the record has no policy (p=)")
    policy = _policy("p", found["p"])
    subdomain = _policy("sp", found["sp"]) if "sp" in found else None
    pct = 100
    if "pct" in found:
        if not _PCT.fullmatch(found["pct"]) or int(found["pct"]) > 100:
            raise DmarcSyntaxError(f"pct={found['pct']} is not a number from 0 to 100")
        pct = int(found["pct"])
    return policy, subdomain, pct


def _names(domain: str) -> list[str]:
    labels = domain.split(".")
    parents = [".".join(labels[i:]) for i in range(len(labels) - 1)]
    if len(parents) > MAX_NAMES_TRIED:
        # A deep name skips the middle, never the two-label parent, where the policy usually is.
        return [*parents[: MAX_NAMES_TRIED - 1], parents[-1]]
    return parents


async def check_dmarc(resolver: Resolver, domain: str) -> DmarcFinding:
    domain = normal_name(domain)
    for name in _names(domain):
        answer = await resolver.txt(f"_dmarc.{name}")
        if answer.status is TxtStatus.TIMEOUT:
            raise LookupFailedError(f"the lookup of _dmarc.{name} did not answer")
        records = [record for record in answer.records if is_dmarc(record)]
        if not records:
            continue
        if len(records) > 1:
            problem = f"{len(records)} DMARC records at _dmarc.{name}: receivers ignore them all"
            return DmarcFinding(check=_INVALID, found_at=name, problems=(problem,))
        try:
            policy, subdomain, pct = parse(records[0])
        except DmarcSyntaxError as error:
            return DmarcFinding(
                check=_INVALID, record=records[0], found_at=name, problems=(str(error),)
            )
        if name != domain:
            # Inherited: the parent's subdomain policy, where it sets one, is this name's policy.
            policy, subdomain = subdomain or policy, None
        check = DmarcCheck(
            present=True, valid=True, policy=policy, subdomain_policy=subdomain, pct=pct
        )
        return DmarcFinding(check=check, record=records[0], found_at=name)
    return DmarcFinding(check=_MISSING)
