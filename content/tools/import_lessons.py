"""Import the Biology XI figures and lessons (every chapter authored so far) into a running API as a content author (development only).

    python content/tools/import_lessons.py --api http://127.0.0.1:8100 [--email studio-author@example.com] [--dry-run]

What it does, in order:

1. Signs in through the development issuer (refused outside development/test roles). The password comes from
   PORTAL_IMPORT_PASSWORD or the dev-seed fixture password.
2. Zips content/lessons/xi/biology/figures/*.png with the manifest built from figures.json and commits it as a media pack
   (idempotent: an unchanged file is reported "unchanged", a changed file becomes the asset's next version).
3. Rewrites each lesson file's figure placeholders with the archived versions' IDs:
       "$asset": "<external_id>"        -> "asset_version_id": "<version id>"
       "$poster": "<external_id>"       -> "poster_asset_version_id": "<version id>"
       "$frames": "<external_id prefix>" -> "frames": [<version ids of prefix-01 .. prefix-NN, in order>]
       "$image": "<external_id>"        -> "image_asset_id": "<version id>"   (inside a fallback)
   and imports every English lesson as one batch, then every Roman Urdu variant (which names its English base) as a
   second batch. Each batch is a preview followed by a commit, so a lesson with an error stops its whole batch and
   nothing is committed. Two previews per run keep a whole book inside the API's preview rate limit.

Nothing here publishes anything. Publication still needs independent academic review (W01.S1.T3).
"""

from __future__ import annotations

import argparse
import copy
import io
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Any
from urllib import error, request

ROOT = Path(__file__).resolve().parents[2]
LESSONS = ROOT / "content" / "lessons" / "xi" / "biology"
FIGURES = LESSONS / "figures"
DEV_PASSWORD = "studio-fixture-pass-1"  # pragma: allowlist secret (dev-seed fixture, refused outside development/test)


def call(api: str, method: str, path: str, token: str | None = None, body: bytes | None = None, content_type: str | None = None) -> Any:
    req = request.Request(api + path, data=body, method=method)
    req.add_header("X-Portal-Client", "import-tool")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with request.urlopen(req, timeout=300) as res:
            raw = res.read()
            return json.loads(raw) if raw else None
    except error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise SystemExit(f"{method} {path} -> {e.code}: {detail[:2000]}") from None


def sign_in(api: str, email: str, password: str) -> str:
    out = call(api, "POST", "/v1/dev-auth/token", body=json.dumps({"email": email, "password": password}).encode(), content_type="application/json")
    return str(out["access_token"])


PACK_LIMIT = 200  # the API accepts at most 200 files per media pack


def media_pack(api: str, token: str, dry_run: bool) -> dict[str, str]:
    """Commit every figure in figures.json, in packs of at most PACK_LIMIT files; returns external_id -> version_id."""
    figures = json.loads((FIGURES / "figures.json").read_text(encoding="utf-8"))["items"]
    versions: dict[str, str] = {}
    for start in range(0, len(figures), PACK_LIMIT):
        chunk = figures[start : start + PACK_LIMIT]
        manifest = {
            "schema_version": 1,
            "kind": "media",
            "grade": 11,
            "subject": "biology",
            "items": [
                {"external_id": f["external_id"], "kind": f["kind"], "title": f["title"][:200], "file": f["file"], "provenance": f["provenance"]}
                for f in chunk
            ],
        }
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifest.json", json.dumps(manifest))
            for f in chunk:
                z.write(LESSONS / f["file"], f["file"])
        data = buf.getvalue()
        print(f"media pack {start // PACK_LIMIT + 1}: {len(chunk)} files, {len(data) / 1e6:.1f} MB")
        out = call(api, "POST", f"/v1/studio/assets/manifest?commit={'false' if dry_run else 'true'}", token, data, "application/zip")
        bad = [e for e in out["entries"] if e["errors"]]
        for e in bad:
            print("  error", e["external_id"], e["errors"])
        if bad:
            raise SystemExit("media pack has errors; nothing imported")
        print("  ", out["counts"])
        versions.update({e["external_id"]: e["version_id"] for e in out["entries"] if e.get("version_id")})
    return versions


def resolve(block: dict[str, Any], versions: dict[str, str], frames_per_turn: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in block.items():
        if key == "$asset":
            out["asset_version_id"] = versions[value]
        elif key == "$poster":
            out["poster_asset_version_id"] = versions[value]
        elif key == "$frames":
            out["frames"] = [versions[f"{value}-{n:02d}"] for n in range(1, frames_per_turn + 1)]
        elif key == "$image":
            out["image_asset_id"] = versions[value]
        elif key == "fallback" and isinstance(value, dict):
            out["fallback"] = resolve(value, versions, frames_per_turn)
        else:
            out[key] = value
    return out


def import_batch(api: str, token: str, paths: list[Path], name: str, versions: dict[str, str], frames_per_turn: int, dry_run: bool) -> None:
    """Import several lesson files as one batch (one preview), so a whole book stays inside the preview rate limit."""
    if not paths:
        return
    items: list[dict[str, Any]] = []
    for path in paths:
        doc = copy.deepcopy(json.loads(path.read_text(encoding="utf-8")))
        for item in doc["items"]:
            item["body"]["blocks"] = [resolve(b, versions, frames_per_turn) for b in item["body"]["blocks"]]
            items.append(item)
    body = json.dumps({"schema_version": 1, "kind": "lesson", "items": items}).encode()
    batch = call(api, "POST", f"/v1/studio/imports?format=json&filename={name}", token, body, "application/json")
    rows = batch["rows"]
    for r in rows:
        if r["errors"]:
            print("  error", name, r["external_id"], r["errors"])
    if any(r["errors"] for r in rows):
        raise SystemExit(f"{name}: errors; nothing committed")
    actions: dict[str, int] = {}
    for r in rows:
        actions[r["action"]] = actions.get(r["action"], 0) + 1
    if dry_run:
        print(f"  {name}: preview ok {actions} (dry run, discarded)")
        call(api, "POST", f"/v1/studio/imports/{batch['id']}/discard", token)
        return
    done = call(api, "POST", f"/v1/studio/imports/{batch['id']}/commit", token)
    print(f"  {name}: {done['status']} {actions} ({len(rows)} lessons)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8100")
    ap.add_argument("--email", default="studio-author@example.com")
    ap.add_argument("--dry-run", action="store_true", help="preview everything; commit nothing")
    ap.add_argument("--chapter", type=int, help="import only this chapter's lessons (the API allows 30 previews an hour)")
    ap.add_argument("--only", help="comma-separated topic numbers to import, e.g. 2.8,2.9 (both languages)")
    args = ap.parse_args()
    token = sign_in(args.api, args.email, os.environ.get("PORTAL_IMPORT_PASSWORD", DEV_PASSWORD))
    versions = media_pack(args.api, token, args.dry_run)
    if args.dry_run:
        print("dry run: lesson placeholders can't be resolved without archived versions; stopping after the pack preview")
        return 0
    frames = int(json.loads((FIGURES / "figures.json").read_text(encoding="utf-8"))["frames_per_turn"])
    stem = f"c11-bio-ch{args.chapter}" if args.chapter else "c11-bio-ch*"
    english = sorted(
        p for p in LESSONS.glob(f"{stem}-*.json") if not p.name.endswith("-ru.json") and not p.name.endswith("coverage.json")
    )
    roman = sorted(LESSONS.glob(f"{stem}-*-ru.json"))
    if args.only:
        wanted = {t.strip() for t in args.only.split(",")}
        english = [p for p in english if p.stem.rsplit("-", 1)[-1] in wanted]
        roman = [p for p in roman if p.stem[: -len("-ru")].rsplit("-", 1)[-1] in wanted]
    print(f"lessons: {len(english)} English, {len(roman)} Roman Urdu")
    tag = f"ch{args.chapter}" if args.chapter else "all"
    import_batch(args.api, token, english, f"c11-bio-{tag}-en.json", versions, frames, args.dry_run)
    import_batch(args.api, token, roman, f"c11-bio-{tag}-ru.json", versions, frames, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
