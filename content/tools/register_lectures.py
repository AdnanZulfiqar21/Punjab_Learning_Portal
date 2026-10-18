"""Register finished lecture videos in a *development* API so the Lecture view can be tested on a phone.

    python content/tools/register_lectures.py --api http://127.0.0.1:8100 --production <Educational_Video_Production/.../Chapter_01> --videos <folder with the .mp4 files>

For every part folder with `lesson_metadata.json`, `storyboard/portal_storyboard.json` and `subtitles/captions_roman_urdu.srt`
it walks the portal's own lecture workflow with the dev-seed staff accounts:

1. a storyboard item on the part's topic, saved from `portal_storyboard.json` (scenes, claims, textbook page references),
   submitted, reviewed and published;
2. the approved narration voice (proposed and approved once, with the owner fixture);
3. the lecture record, its master (file name, SHA-256, size, duration read from the mp4), reviewed captions (the SRT
   converted to WebVTT and archived as a caption asset), chapter markers from the storyboard's scene times, submission,
   and a review by the reviewer fixture.

Everything is recorded in the development database only. **The reviewer fixture is not an academic reviewer**: the
"approved" status it produces is a technical test registration so the phone can play the video, never evidence that a
lecture passed academic review (the review notes say so). Re-running skips parts whose lecture already exists.
Point the API's `PORTAL_LECTURE_MEDIA_DIR` at the videos folder so the stream can find the masters.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys
from pathlib import Path
from typing import Any
from urllib import error, parse, request

DEV_PASSWORD = "studio-fixture-pass-1"  # pragma: allowlist secret (dev-seed fixture, refused outside development/test)
STORYBOARD_CHECKS = {c: True for c in ("accuracy", "sources", "pacing", "accessibility", "rights")}
LECTURE_CHECKS = {
    c: True
    for c in ("accuracy", "voice_text_alignment", "pacing", "spelling", "diagrams", "captions", "rights", "source_verification")
}
NOTE = (
    "Development test registration (content/tools/register_lectures.py): the production records were checked for "
    "shape only so the video can be played on a phone. This is not an academic review."
)


def call(api: str, method: str, path: str, token: str | None = None, body: Any = None, content_type: str | None = None, raw: bytes | None = None) -> Any:
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = request.Request(api + path, data=data, method=method)
    req.add_header("X-Portal-Client", "register-lectures")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if content_type or body is not None:
        req.add_header("Content-Type", content_type or "application/json")
    try:
        with request.urlopen(req, timeout=300) as res:
            out = res.read()
            return json.loads(out) if out else None
    except error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise SystemExit(f"{method} {path} -> {e.code}: {detail[:1500]}") from None


def token(api: str, email: str, password: str, mfa: bool = False) -> str:
    out = call(api, "POST", "/v1/dev-auth/token", body={"email": email, "password": password, "mfa": mfa})
    return str(out["access_token"])


def mp4_duration_s(path: Path) -> int:
    """Seconds from the mp4's movie header; a file without one is refused."""
    data = path.read_bytes() if path.stat().st_size < 64 * 1024 * 1024 else open(path, "rb").read(8 * 1024 * 1024)
    i = data.find(b"mvhd")
    if i < 0:
        raise SystemExit(f"{path.name}: no mvhd atom in the first part of the file")
    version = data[i + 4]
    if version == 1:
        timescale, duration = struct.unpack(">IQ", data[i + 24 : i + 36])
    else:
        timescale, duration = struct.unpack(">II", data[i + 16 : i + 24])
    return max(1, round(duration / timescale))


def srt_to_vtt(text: str) -> str:
    body = re.sub(r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", text.strip().replace("\r\n", "\n"))
    return "WEBVTT\n\n" + body + "\n"


def video_for(meta: dict[str, Any], videos: Path) -> Path:
    """`1.4_Classification_of_Kingdom_Animalia_Part_3.mp4` from the part's topic number, topic title and part."""
    base = f"{meta['topic']}_{re.sub(r'[^A-Za-z0-9-]+', '_', meta['topic_title']).strip('_')}"
    name = f"{base}_Part_{meta['part']}.mp4" if meta.get("part") else f"{base}.mp4"
    path = videos / name
    if not path.is_file():
        raise SystemExit(f"video not found for {meta['title']}: {path}")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:8100")
    ap.add_argument("--production", required=True, help="Chapter folder with Topic_* production records")
    ap.add_argument("--videos", required=True, help="Folder holding the finished .mp4 masters")
    args = ap.parse_args()
    pw = os.environ.get("PORTAL_IMPORT_PASSWORD", DEV_PASSWORD)
    author = token(args.api, "studio-author@example.com", pw)
    reviewer = token(args.api, "studio-reviewer@example.com", pw)
    publisher = token(args.api, "studio-publisher@example.com", pw, mfa=True)
    owner = token(args.api, "studio-owner@example.com", pw, mfa=True)
    videos = Path(args.videos)

    existing = {lec["title"]: lec for lec in call(args.api, "GET", "/v1/studio/lectures", author)}

    # One approved Roman Urdu voice for the series (the owner's narration record names the preset).
    voices = call(args.api, "GET", "/v1/studio/voices", author)
    voice = next((v for v in voices if v["name"] == "PLP Ustad (male) v1" and v["status"] == "approved"), None)
    if voice is None:
        voice = call(
            args.api,
            "POST",
            "/v1/studio/voices",
            author,
            {"name": "PLP Ustad (male) v1", "language": "roman_ur", "tool": "ElevenLabs eleven_v4", "voice_ref": "PLP-NARRATOR-A-EL-MALE", "notes": "Series voice from the narration records."},
        )
        voice = call(args.api, "POST", f"/v1/studio/voices/{voice['id']}/approve", owner, {"evidence": "Development registration: the narration record says the owner approved preset PLP-NARRATOR-A-EL-MALE on 2026-10-11."})
    print("voice:", voice["name"], voice["status"])

    parts = sorted(p for p in Path(args.production).glob("Topic_01_*") if (p / "lesson_metadata.json").is_file())
    for part in parts:
        meta = json.loads((part / "lesson_metadata.json").read_text(encoding="utf-8"))
        title = meta["title"]
        if title in existing:
            print(f"skip (exists, {existing[title]['status']}):", title)
            continue
        sb = json.loads((part / "storyboard" / "portal_storyboard.json").read_text(encoding="utf-8"))
        srt = (part / "subtitles" / "captions_roman_urdu.srt").read_text(encoding="utf-8")
        video = video_for(meta, videos)
        chapter_id, topic_id = meta["portal"]["chapter_id"], meta["portal"]["topic_id"]

        item = call(args.api, "POST", "/v1/studio/items", author, {"kind": "storyboard", "chapter_id": chapter_id, "topic_id": topic_id, "title": f"Storyboard: {title}"})
        current = call(args.api, "GET", f"/v1/studio/items/{item['id']}", author)
        call(args.api, "PUT", f"/v1/studio/items/{item['id']}/draft", author, {"revision": current["working"]["revision"], "body": sb["body"], "source_refs": sb["source_refs"]})
        call(args.api, "POST", f"/v1/studio/items/{item['id']}/submit", author, {})
        call(args.api, "POST", f"/v1/studio/items/{item['id']}/review", reviewer, {"decision": "approve", "comment": NOTE, "checklist": STORYBOARD_CHECKS})
        call(args.api, "POST", f"/v1/studio/items/{item['id']}/publish", publisher, {})

        lec = call(args.api, "POST", "/v1/studio/lectures", author, {"storyboard_item_id": item["id"], "narration_language": "roman_ur", "voice_id": voice["id"], "title": title})
        url = f"/v1/studio/lectures/{lec['id']}"
        data = video.read_bytes()
        master = {"filename": video.name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "duration_s": mp4_duration_s(video), "location": str(video.parent)}
        call(args.api, "PUT", f"{url}/master", author, master)

        asset = call(args.api, "POST", "/v1/studio/assets", author, {"kind": "caption", "title": f"Captions (Roman Urdu): {title}", "grade": 11, "subject": "biology"})
        q = parse.urlencode({"source": "Owner's production: subtitles/captions_roman_urdu.srt, converted to WebVTT", "author": "Punjab Learning Portal production", "licence": "Owner's own work"})
        version = call(args.api, "POST", f"/v1/studio/assets/{asset['id']}/versions?{q}", author, raw=srt_to_vtt(srt).encode("utf-8"), content_type="application/octet-stream")
        call(args.api, "PUT", f"{url}/captions", author, {"language": "roman_ur", "asset_version_id": version["id"]})

        scenes = sb["body"]["scenes"]
        markers = [{"scene_id": s["id"], "start_s": int(s["start_s"]), "label": (s.get("on_screen_text") or s.get("visual") or s["id"]).split("·")[0].strip()[:120]} for s in scenes]
        call(args.api, "PUT", f"{url}/markers", author, {"scenes": markers})
        call(args.api, "POST", f"{url}/submit", author, {})
        done = call(args.api, "POST", f"{url}/review", reviewer, {"decision": "approve", "checklist": LECTURE_CHECKS, "notes": NOTE})
        print(f"registered: {title} -> {done['status']} ({master['duration_s']} s, {len(markers)} markers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
