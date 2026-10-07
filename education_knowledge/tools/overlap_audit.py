"""Measure verbatim overlap between tracked repo text and the textbook text layers (12-word shingles)."""
import re, glob, subprocess, collections, json, sys
W = 12
tok = lambda s: re.findall(r"[a-z0-9]+", s.lower())
src = set()
for f in glob.glob("education_knowledge/source_text/*.txt"):
    t = tok(open(f, encoding="utf-8").read())
    for i in range(len(t) - W + 1):
        src.add(hash(tuple(t[i:i + W])))
files = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split("\n")
files = [f for f in files if re.search(r"\.(md|json|txt|py|ts|tsx)$", f) and not f.startswith(("apps/", "packages/", "Road Map/"))]
report = []
for f in files:
    try: t = tok(open(f, encoding="utf-8").read())
    except Exception: continue
    best = run = 0; hits = 0; worst_at = 0
    for i in range(len(t) - W + 1):
        if hash(tuple(t[i:i + W])) in src:
            hits += 1; run += 1
            if run > best: best, worst_at = run, i
        else:
            run = 0
    if t:
        report.append((best + W - 1 if best else 0, hits, len(t), f, " ".join(t[max(0, worst_at - best + 1): worst_at + W][:60])))
report.sort(reverse=True)
print(f"{len(src)} source shingles; {len(report)} tracked files scanned")
for longest, hits, n, f, sample in report[:15]:
    print(f"longest_run={longest:4d} words  shingle_hits={hits:6d}/{n:7d}  {f}")
    if longest >= 40: print("     e.g.:", sample[:300])
json.dump([r[:4] for r in report], open(sys.argv[1], "w"))
