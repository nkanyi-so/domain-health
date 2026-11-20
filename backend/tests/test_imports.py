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
    "src/domain_health/risks/openai_model.py": {"openai"},
    "src/domain_health/store/firestore.py": {"google"},
    "src/domain_health/machine_auth.py": {"google", "httpx2"},
    "src/domain_health/cloud_tasks.py": {"google"},
    "src/domain_health/slack.py": {"httpx2"},
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
    allowed = {
        "src/domain_health/check_domain.py",
        # The deployed service's live-check route, which reaches it only after its limits.
        "src/domain_health/serve.py",
        "tests/test_resolver.py",
    }
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


def test_only_the_paid_commands_load_the_live_model() -> None:
    """Rule 3: the deployed service is built with the recorded model only. The live model's
    module is imported by the paid eval command alone (and by its own test), and there inside
    the function that runs after the key and the ledger are in hand."""
    allowed = {
        "src/domain_health/evals/live.py",
        "src/domain_health/seeded/record.py",
        "tests/test_openai_model.py",
    }
    importers = set()
    for path in python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [f"{node.module}.{alias.name}" for alias in node.names] + [node.module]
            if any(name.startswith("domain_health.risks.openai_model") for name in names):
                importers.add(path.relative_to(BACKEND).as_posix())

    assert importers == allowed

    for paid in ("evals/live.py", "seeded/record.py"):
        source = (BACKEND / "src/domain_health" / paid).read_text(encoding="utf-8")
        at_the_top = [
            node.module
            for node in ast.parse(source).body
            if isinstance(node, ast.ImportFrom) and node.module and "openai_model" in node.module
        ]
        assert at_the_top == [], paid


def test_the_deployed_service_never_loads_a_model_library_or_the_paid_commands() -> None:
    """Rule 3 again, from the other side: nothing the service imports at start-up, directly or
    through another module of this project, is the live model, a paid command or the rubric's
    table."""
    forbidden = (
        "domain_health.risks.openai_model",
        "domain_health.evals.live",
        "openai",
        # The rubric read as a table is the evals', never the pipeline's (decision 0010).
        "domain_health.evals.table",
        "domain_health.seeded.recording_report",
        "domain_health.seeded.record",
    )
    seen: set[str] = set()
    todo = ["domain_health.serve"]
    while todo:
        module = todo.pop()
        if module in seen:
            continue
        seen.add(module)
        relative = module.replace(".", "/")
        path = BACKEND / "src" / f"{relative}.py"
        if not path.exists():
            path = BACKEND / "src" / relative / "__init__.py"
        if not path.exists():
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module, *(f"{node.module}.{alias.name}" for alias in node.names)]
            for name in names:
                hit = any(name == bad or name.startswith(bad + ".") for bad in forbidden)
                assert not hit, f"{module} imports {name}"
                if name.startswith("domain_health"):
                    todo.append(name)
    assert "domain_health.seeded.recordings" in seen
