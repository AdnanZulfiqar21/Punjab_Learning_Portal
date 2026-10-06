"""Write the OpenAPI document used to generate web/mobile client types (P01.S3.T1 contract-drift check).

    uv run python -m portal_api.export_openapi ../../packages/contracts/openapi.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from portal_api.main import create_app


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
    spec = create_app().openapi()
    out.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(spec.get('paths', {}))} paths)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
