"""Unit checks for the SBOM builder (P18.S2.T3, EXPOSURE-01). Synthetic package lists only."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import sbom


def test_inventory_is_deduplicated_sorted_and_skips_workspace_links() -> None:
    req = "FastAPI==0.200.0\nSQLAlchemy[asyncio]==2.1.0 ; python_version >= '3.13'\n# comment\n-e ./local\n"
    deep: dict = {"version": "1.0.0"}
    node = deep
    for i in range(3000):  # deeper than the recursion limit
        node["dependencies"] = {f"d{i}": {"version": "1.0.0"}}
        node = node["dependencies"][f"d{i}"]
    projects = [
        {
            "name": "web",
            "dependencies": {
                "@portal/contracts": {"version": "link:../../packages/contracts"},
                "@scope/pkg": {"version": "2.0.0"},
                "deep": deep,
            },
        },
        {"name": "mobile", "dependencies": {"@scope/pkg": {"version": "2.0.0"}}},
    ]
    bom = sbom.build(req, projects)
    purls = [c["purl"] for c in bom["components"]]
    assert purls == sorted(purls) and len(purls) == len(set(purls))
    assert "pkg:pypi/fastapi@0.200.0" in purls and "pkg:pypi/sqlalchemy@2.1.0" in purls
    assert "pkg:npm/%40scope/pkg@2.0.0" in purls and not any("contracts" in p for p in purls)
    assert sum(p.startswith("pkg:npm/d") for p in purls) == 3001  # "deep" plus d0..d2999
    assert bom["bomFormat"] == "CycloneDX" and bom["specVersion"] == "1.5"
