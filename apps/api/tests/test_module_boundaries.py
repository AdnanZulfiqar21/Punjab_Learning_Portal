"""P01.S1.T2 (MODULES-01): the API's module boundaries, checked on the import graph (docs/architecture/modules.md).

Only module-level imports are checked. An import inside a function is the documented way to call across a layer
without creating an import-time dependency, so it is allowed; these rules stop the module-level structure from
eroding. No database is needed."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parents[1] / "src" / "portal_api"
CORE = {"config", "db", "errors", "days", "observability", "budget"}
ENTRY_POINTS = {"main", "export_openapi", "release"}  # assemble the app or describe it; nothing imports them
FOUNDATION = {"identity", "audit", "curriculum", "notifications", "access", "exports", "analytics", "system"}
FEATURES = {"content", "assessment", "written", "support", "help"}
# Module-level cycles that exist today; a new one fails. Each is broken at import time by import order and should go.
KNOWN_CYCLES = {frozenset({"audit", "identity"}), frozenset({"assessment", "written"})}


def _module(path: Path) -> str:
    parts = path.relative_to(ROOT.parent).with_suffix("").parts
    return ".".join(p for p in parts if p != "__init__")


def _owner(module: str) -> str:
    parts = module.split(".")
    if len(parts) >= 3 and parts[1] == "modules":
        return parts[2]
    return parts[1] if len(parts) > 1 else "portal_api"


def _module_level_imports() -> list[tuple[str, str]]:
    out = []
    for path in ROOT.rglob("*.py"):
        source = _module(path)
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.ImportFrom) and node.module:
                targets = [f"{node.module}.{a.name}" for a in node.names]
            elif isinstance(node, ast.Import):
                targets = [a.name for a in node.names]
            else:
                continue  # `if TYPE_CHECKING:` blocks and function bodies are not import-time dependencies
            out += [(source, t) for t in targets if t.startswith("portal_api.")]
    return out


IMPORTS = _module_level_imports()
ALL_IMPORTS = [
    (_module(p), (n.module or "") + "." + a.name if isinstance(n, ast.ImportFrom) else a.name)
    for p in ROOT.rglob("*.py")
    for n in ast.walk(ast.parse(p.read_text(encoding="utf-8")))
    if isinstance(n, ast.Import | ast.ImportFrom)
    for a in n.names
]


def test_the_graph_is_read() -> None:
    assert len(IMPORTS) > 300 and any(t.startswith("portal_api.modules.written") for _, t in IMPORTS)


def test_core_files_import_no_module_at_import_time() -> None:
    bad = [(s, t) for s, t in IMPORTS if _owner(s) in CORE and t.startswith("portal_api.modules.")]
    assert bad == []


def test_only_entry_points_import_the_app() -> None:
    bad = [(s, t) for s, t in ALL_IMPORTS if t.startswith("portal_api.main") and _owner(s) not in ENTRY_POINTS]
    assert bad == []


def test_routers_are_leaves() -> None:
    """Nothing outside a module imports its router: shared logic lives in the module's other files."""

    def is_router(target: str) -> bool:
        parts = target.split(".")
        return len(parts) >= 4 and parts[1] == "modules" and parts[3] in ("router", "review_router")

    bad = [(s, t) for s, t in ALL_IMPORTS if is_router(t) and _owner(s) not in ENTRY_POINTS and _owner(s) != _owner(t)]
    assert bad == []


def test_foundation_modules_do_not_import_features_at_import_time() -> None:
    bad = [(s, t) for s, t in IMPORTS if _owner(s) in FOUNDATION and _owner(t) in FEATURES]
    assert bad == []


def test_every_module_has_a_layer() -> None:
    present = {p.name for p in (ROOT / "modules").iterdir() if p.is_dir() and not p.name.startswith("__")}
    assert present == FOUNDATION | FEATURES, "add a new module to FOUNDATION or FEATURES (and to the document)"


def test_no_new_module_level_cycles() -> None:
    graph: dict[str, set[str]] = defaultdict(set)
    for s, t in IMPORTS:
        a, b = _owner(s), _owner(t)
        if a != b and a in FOUNDATION | FEATURES and b in FOUNDATION | FEATURES:
            graph[a].add(b)
    cycles = {frozenset({a, b}) for a in graph for b in graph[a] if a in graph.get(b, set())}
    assert cycles <= KNOWN_CYCLES, f"new import-time cycle(s): {sorted(map(sorted, cycles - KNOWN_CYCLES))}"
    longer = []  # cycles through three or more modules
    state: dict[str, int] = {}

    def visit(node: str, path: list[str]) -> None:
        state[node] = 1
        for nxt in graph.get(node, ()):
            if state.get(nxt) == 1 and len(path) - path.index(nxt) > 2:
                longer.append(path[path.index(nxt) :])
            elif nxt not in state:
                visit(nxt, [*path, nxt])
        state[node] = 2

    for start in list(graph):
        if start not in state:
            visit(start, [start])
    assert longer == []
