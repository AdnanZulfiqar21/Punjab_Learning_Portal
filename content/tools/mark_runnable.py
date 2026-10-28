"""CODE-RUNNER-01: mark which Roman Urdu program listings get the reader's "Run karein" button.

A listing is marked `"runnable": true` only when it really is a program: it runs in a fresh Python process within
5 seconds, ends without an error and prints something. A syntax outline ("if condition: ... else: ..."), a lone
function or a fragment that needs another file never gets the button. Programs that would need something the browser
runner does not have (windows, the network, other processes) are left unmarked too. `input()` is fed the answer "5".

    python content/tools/mark_runnable.py            # mark every *-ru.json lesson
    python content/tools/mark_runnable.py --check    # exit 1 if any mark is out of date (CI-style)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

LESSONS = Path(__file__).resolve().parent.parent / "lessons"
# Not in the browser runner (Pyodide serves the standard library only, with no windows, sockets or processes).
UNAVAILABLE = re.compile(
    r"^\s*(?:import|from)\s+"
    r"(turtle|tkinter|socket|subprocess|multiprocessing|threading|requests|numpy|pandas|matplotlib)\b",
    re.M,
)
ANSWERS = "5\n" * 20


def runs_cleanly(code: str) -> bool:
    if UNAVAILABLE.search(code):
        return False
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "program.py"
        script.write_text(code, encoding="utf-8")
        try:
            # The textbook's own listings, run in an empty temporary folder with an isolated interpreter.
            done = subprocess.run(  # noqa: S603
                [sys.executable, "-I", str(script)],
                input=ANSWERS,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")},
                timeout=5,
                cwd=tmp,
            )
        except subprocess.TimeoutExpired:
            return False
    return done.returncode == 0 and done.stdout.strip() != ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="report out-of-date marks; change nothing")
    args = ap.parse_args()
    stale: list[str] = []
    marked = total = 0
    for path in sorted(LESSONS.rglob("*-ru.json")):
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        changed = False
        for item in data.get("items", []):
            for block in item.get("body", {}).get("blocks", []):
                if block.get("type") != "code" or block.get("language", "python") != "python":
                    continue
                total += 1
                want = runs_cleanly(block["text"])
                marked += want
                if bool(block.get("runnable")) != want:
                    stale.append(f"{path.name}: {block['text'].splitlines()[0][:60]!r} -> {want}")
                    if want:
                        block["runnable"] = True
                    else:
                        block.pop("runnable", None)
                    changed = True
        if changed and not args.check:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    state = "out of date" if args.check else "changed"
    print(f"{marked} of {total} Python listings runnable; {len(stale)} mark(s) {state}")
    for line in stale:
        print("  " + line)
    return 1 if args.check and stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
