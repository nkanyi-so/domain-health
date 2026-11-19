"""Rule 1 in CLAUDE.md: every outside system sits behind its one interface, so nothing outside
the implementation modules imports a DNS, model, Google Cloud or HTTP client library."""

import ast
from pathlib import Path

from tests.paths import BACKEND

OUTSIDE_SYSTEMS = (
    "dns",
    "openai",
    "google",
    "httpx",
    "httpx2",
    "requests",
    "aiohttp",
    "urllib3",
    "urllib.request",
    "http.client",
    "socket",
)

# The implementation modules, and what each one may import. Nothing else may import any of them.
ALLOWED: dict[str, set[str]] = {
    "src/domain_health/resolver/live.py": {"dns"},
    # Talks to the Firestore emulator on localhost with the standard library, until Phase 3
    # replaces it with the store's own emulator tests.
    "tests/test_emulator_smoke.py": {"urllib.request"},
}


def _system(module: str) -> str | None:
    for system in OUTSIDE_SYSTEMS:
        if module == system or module.startswith(system + "."):
            return system
    return None


def imported(source: str) -> set[str]:
    """Every outside system a piece of source imports, wherever in the file the import sits."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        modules: list[str] = []
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules = [node.module, *(f"{node.module}.{alias.name}" for alias in node.names)]
        elif (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "__import__") or (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
        ):
            modules = [str(arg.value) for arg in node.args[:1] if isinstance(arg, ast.Constant)]
        found |= {system for module in modules if (system := _system(module))}
    return found


def python_files() -> list[Path]:
    return sorted([*(BACKEND / "src").rglob("*.py"), *(BACKEND / "tests").rglob("*.py")])


def test_only_the_implementation_modules_import_an_outside_system() -> None:
    assert len(python_files()) > 20
    broken = {}
    for path in python_files():
        name = path.relative_to(BACKEND).as_posix()
        extra = imported(path.read_text(encoding="utf-8")) - ALLOWED.get(name, set())
        if extra:
            broken[name] = sorted(extra)

    assert broken == {}


def test_every_allowed_module_exists_and_uses_what_it_is_allowed() -> None:
    for name, systems in ALLOWED.items():
        assert imported((BACKEND / name).read_text(encoding="utf-8")) == systems, name


def test_the_scan_sees_every_way_of_importing() -> None:
    assert imported("import dns.resolver") == {"dns"}
    assert imported("from dns import asyncresolver") == {"dns"}
    assert imported("from google.cloud import firestore") == {"google"}
    assert imported("def f():\n    import openai") == {"openai"}
    assert imported("from urllib import request") == {"urllib.request"}
    assert imported("import urllib.request as r") == {"urllib.request"}
    assert imported("import importlib\nimportlib.import_module('httpx')") == {"httpx"}
    assert imported("__import__('socket')") == {"socket"}
    assert imported("import urllib.parse\nimport dnslike\nfrom . import dns") == set()


def test_only_the_live_check_builds_the_live_resolver() -> None:
    """Rule 5: seeded clients resolve through the fixture resolver only. The live resolver is
    imported by the typed-domain command alone (and by its own test)."""
    allowed = {"src/domain_health/check_domain.py", "tests/test_resolver.py"}
    importers = set()
    for path in python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [f"{node.module}.{alias.name}" for alias in node.names] + [node.module]
            if any(name.startswith("domain_health.resolver.live") for name in names):
                importers.add(path.relative_to(BACKEND).as_posix())

    assert importers == allowed
