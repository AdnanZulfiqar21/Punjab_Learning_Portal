"""P18.S2.T3 (EXPOSURE-01): a CycloneDX 1.5 component inventory of the runtime (production) dependencies.

Inputs come from the package managers themselves, so nothing new is installed:
  uv export --frozen --no-dev --no-hashes --no-emit-project  (Python, from apps/api)
  pnpm list -r --prod --json --depth Infinity                (JavaScript workspace)

python tools/sbom.py --python requirements.txt --node pnpm.json -o sbom.cdx.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

REQ = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?==([^\s;]+)")


def python_components(text: str) -> dict[str, dict[str, str]]:
    out = {}
    for line in text.splitlines():
        m = REQ.match(line.strip())
        if m:
            name = re.sub(r"[-_.]+", "-", m.group(1)).lower()
            purl = f"pkg:pypi/{name}@{m.group(2)}"
            out[purl] = {"type": "library", "name": name, "version": m.group(2), "purl": purl}
    return out


def node_components(projects: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    out = {}
    stack = [d for p in projects for d in (p.get("dependencies") or {}).items()]
    while stack:  # iterative: deep trees never hit the recursion limit
        name, info = stack.pop()
        version = str(info.get("version", ""))
        if version and not version.startswith(("link:", "file:", "workspace:")):
            purl = f"pkg:npm/{quote(name, safe='/')}@{version}".replace("pkg:npm/@", "pkg:npm/%40")
            out[purl] = {"type": "library", "name": name, "version": version, "purl": purl}
        stack.extend((info.get("dependencies") or {}).items())
    return out


def build(python_text: str, node_projects: list[dict[str, Any]]) -> dict[str, Any]:
    components = {**python_components(python_text), **node_components(node_projects)}
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {"component": {"type": "application", "name": "punjab-learning-portal"}},
        "components": [components[k] for k in sorted(components)],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", required=True)
    ap.add_argument("--node", required=True)
    ap.add_argument("-o", "--output", required=True)
    a = ap.parse_args()
    bom = build(Path(a.python).read_text(encoding="utf-8"), json.loads(Path(a.node).read_text(encoding="utf-8")))
    Path(a.output).write_text(json.dumps(bom, indent=1) + "\n", encoding="utf-8")
    kinds = {"pypi": 0, "npm": 0}
    for c in bom["components"]:
        kinds[c["purl"].split("/")[0].split(":")[1]] += 1
    print(f"SBOM: {kinds['pypi']} Python and {kinds['npm']} JavaScript runtime components -> {a.output}")


if __name__ == "__main__":
    main()
