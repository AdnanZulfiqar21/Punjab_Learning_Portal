"""SECURITY-HARDEN-01: every SQL statement is a constant with bound parameters (no SQL injection by construction).

An AST scan of the API source: the first argument of `text()`, `exec_driver_sql()` and `execute()` must be a string
literal or something that is not a string at all (a SQLAlchemy construct). `%` / `.format()` formatting or string
concatenation there fails the test, and so does an f-string unless every value it interpolates is in SAFE_NAMES (fixed
SQL fragments defined in the code) or an `int(...)` conversion.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "portal_api"
CALLS = {"text", "exec_driver_sql", "execute"}
# Module constants holding fixed SQL (modules/written/adjudication.py). Never request data.
SAFE_NAMES = {"_CANDIDATES"}


def _safe_value(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id in SAFE_NAMES
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "int"


def _dynamic_string(node: ast.AST) -> bool:
    if isinstance(node, ast.JoinedStr):
        return not all(_safe_value(v.value) for v in node.values if isinstance(v, ast.FormattedValue))
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return any(isinstance(side, (ast.Constant, ast.JoinedStr, ast.BinOp)) for side in (node.left, node.right))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("format", "join"):
        return isinstance(node.func.value, ast.Constant)
    return False


def test_sql_is_never_built_from_formatted_strings() -> None:
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        rel = path.relative_to(SRC).as_posix()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if name in CALLS and _dynamic_string(node.args[0]):
                offenders.append(f"{rel}:{node.lineno}")
    assert offenders == [], f"SQL built from a formatted string: {offenders}"


def test_the_scan_catches_injection_shapes() -> None:
    bad = [
        'text(f"select * from t where a = {q}")',
        'text("select " + q)',
        'text("select %s" % q)',
        'text("select {}".format(q))',
        'db.execute(f"delete from t where id = {i}")',
    ]
    good = [
        'text("select 1 where a = :a")',
        'text(f"with c as ({_CANDIDATES}) select 1")',
        'cur.execute(f"SET statement_timeout = {int(ms)}")',
        "db.execute(select(T))",
    ]

    def flagged(code: str) -> bool:
        call = ast.parse(code).body[0].value  # type: ignore[attr-defined]
        return _dynamic_string(call.args[0])

    assert [c for c in bad if not flagged(c)] == []
    assert [c for c in good if flagged(c)] == []
