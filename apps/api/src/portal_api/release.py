"""Release manifest and migration compatibility rules (roadmap P17.S3.T2; RELEASE-01).

    python -m portal_api.release check       # fails (exit 1) when a migration breaks the rules below
    python -m portal_api.release manifest    # prints the JSON manifest for this build

**Migration rules.** Migrations run as a separate release step before the new code starts, so for a while the old code
runs against the new schema. Every migration must therefore be *expand-compatible*: it may add, but a migration that
drops or renames a table or column, or drops a constraint the old code relies on, must carry a
`# contract-migration: <reason>` line naming why the old code no longer needs it (normally a later release than the one
that stopped using it). Every migration needs a `downgrade`, and the chain has exactly one head. Migrations up to
`GRANDFATHERED_THROUGH` predate any deployment (B03) and are exempt.

**Manifest.** What a build contains, so a deployment can be compared and rolled back: the commit, the migration head,
hashes of the API contract, the derived catalogue and the lockfiles, the lesson schema and renderer versions, the
analytics event versions and the feature switches (all on by default; operators change them at runtime, audited).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

API_DIR = Path(__file__).resolve().parents[2]
REPO = API_DIR.parents[1]
MIGRATIONS = API_DIR / "migrations" / "versions"
# The last migration before these rules (analytics_event, 2026-10-10); an Alembic revision ID, not a credential.
GRANDFATHERED_THROUGH = "e8b2d6f4a193"  # pragma: allowlist secret

# Expand/contract: columns the code no longer uses but the schema still holds until a later contract migration drops
# them. `alembic check` ignores them meanwhile (migrations/env.py); each entry names why and when it goes.
RETIRING_COLUMNS = {
    ("student_profile", "preferences"): "MINIMISATION-01: a free-form store never written or read; drop next release",
}

DESTRUCTIVE = re.compile(r"op\.(drop_table|drop_column|rename_table)\(|new_column_name\s*=")
MARKER = re.compile(r"^#\s*contract-migration:\s*\S", re.M)


def check_migration_text(revision: str, source: str, *, grandfathered: bool) -> list[str]:
    problems = []
    if "def downgrade" not in source:
        problems.append(f"{revision}: no downgrade()")
    upgrade = source.split("def upgrade", 1)[1].split("def downgrade", 1)[0] if "def upgrade" in source else ""
    if not grandfathered and DESTRUCTIVE.search(upgrade) and not MARKER.search(source):
        problems.append(
            f"{revision}: drops or renames a table/column; old code may still use it. Split it (expand now, "
            "contract in a later release) or add '# contract-migration: <why the running code no longer needs it>'."
        )
    return problems


def _scripts() -> Any:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    return ScriptDirectory.from_config(cfg)


def check() -> list[str]:
    scripts = _scripts()
    heads = scripts.get_heads()
    problems = [] if len(heads) == 1 else [f"expected one migration head, found {heads}"]
    grandfathered = True
    for rev in reversed(list(scripts.walk_revisions())):  # oldest first
        source = Path(rev.path).read_text(encoding="utf-8")
        problems += check_migration_text(rev.revision, source, grandfathered=grandfathered)
        if rev.revision == GRANDFATHERED_THROUGH:
            grandfathered = False
    return problems


def _sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def manifest() -> dict[str, Any]:
    from portal_api.main import create_app
    from portal_api.modules.analytics.events import DICTIONARY
    from portal_api.modules.content import blocks
    from portal_api.modules.curriculum.importer import DEFAULT_CATALOGUE
    from portal_api.modules.system.operations import FEATURES

    commit = os.environ.get("GITHUB_SHA")
    if not commit:
        try:
            git = ["git", "rev-parse", "HEAD"]  # fixed arguments; git from PATH as in every developer and CI shell
            commit = subprocess.run(git, cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()  # noqa: S603
        except (OSError, subprocess.CalledProcessError):
            commit = None
    openapi = json.dumps(create_app().openapi(), sort_keys=True, separators=(",", ":")).encode()
    return {
        "manifest_version": 1,
        "git_commit": commit,
        "migration_head": _scripts().get_current_head(),
        "openapi_sha256": hashlib.sha256(openapi).hexdigest(),
        "catalogue_sha256": _sha(DEFAULT_CATALOGUE),
        "content_schema_version": blocks.CONTENT_SCHEMA_VERSION,
        "supported_renderer": blocks.SUPPORTED_RENDERER,
        "analytics_events": {name: spec.version for name, spec in DICTIONARY.items()},
        "feature_switches": {key: "on (runtime-switchable)" for key in FEATURES},
        "lockfiles": {"uv.lock": _sha(API_DIR / "uv.lock"), "pnpm-lock.yaml": _sha(REPO / "pnpm-lock.yaml")},
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if args[:1] == ["check"]:
        problems = check()
        for p in problems:
            print(p)
        print("migration rules: OK" if not problems else f"migration rules: {len(problems)} problem(s)")
        return 1 if problems else 0
    if args[:1] == ["manifest"]:
        print(json.dumps(manifest(), indent=2, sort_keys=True))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
