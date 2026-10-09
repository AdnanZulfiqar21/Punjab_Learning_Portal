"""Reproducible learner-journey load generator (roadmap P20.S1.T2; LOAD-01).

    uv run python -m loadtest.practice_journey --target http://127.0.0.1:8100 --users 20 --duration 60 \
        --grade 11 --subject physics --chapter <chapter-id> --report load-report.json

Each virtual user is a distinct technical account working through a realistic practice journey:

1. sign in (development identity adapter, or a pre-issued token from `--tokens-file`);
2. read the catalogue and start the free trial;
3. build a practice test and start it;
4. save answers one at a time with think time, changing some answers;
5. submit and read the result.

Arrivals are spread over `--ramp` seconds and think time is random within a range. The JSON report records the
endpoint mix, per-endpoint latency percentiles (p50/p95/p99), status counts, error rate, arrival model, concurrency,
duration and target. The environment description (hardware, database size, cost) is added by the person running it.

**Safety:**
* Only `localhost`/`127.0.0.1` targets are accepted unless `--allow-remote` is given.
* A target whose runtime role is `production` is always refused.
* Accounts are technical fixtures with recognisable emails (`load-<run>-<n>@example.invalid`). Nothing here is
  academic content.
Real qualification runs (P20.S2) need the hosting environment (BLOCKERS B03).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import statistics
import sys
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_rng = random.Random()  # noqa: S311 - simulated think time and answer choices, not security
PASSWORD = "load-fixture-pass-1"  # noqa: S105 - development identity adapter fixture only


@dataclass
class Recorder:
    latencies: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    statuses: dict[str, dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    errors: list[str] = field(default_factory=list)

    def add(self, name: str, ms: float, status: int | str) -> None:
        self.latencies[name].append(ms)
        self.statuses[name][str(status)] += 1


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile (p in 0..100) of a non-empty list."""
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, math.ceil(p / 100 * len(ordered)) - 1))
    return round(ordered[k], 1)


def report(rec: Recorder, meta: dict[str, Any]) -> dict[str, Any]:
    endpoints: dict[str, dict[str, Any]] = {}
    total = failures = 0
    for name, values in sorted(rec.latencies.items()):
        st = dict(rec.statuses[name])
        n = len(values)
        bad = sum(c for s, c in st.items() if not s.isdigit() or int(s) >= 500)
        total += n
        failures += bad
        endpoints[name] = {
            "requests": n,
            "p50_ms": percentile(values, 50),
            "p95_ms": percentile(values, 95),
            "p99_ms": percentile(values, 99),
            "mean_ms": round(statistics.fmean(values), 1),
            "statuses": st,
        }
    return {
        **meta,
        "requests": total,
        "server_or_transport_failures": failures,
        "error_rate": round(failures / total, 4) if total else 0.0,
        "endpoint_mix": {k: round(v["requests"] / total, 3) for k, v in endpoints.items()} if total else {},
        "endpoints": endpoints,
        "sample_errors": rec.errors[:20],
    }


async def _call(client: Any, rec: Recorder, name: str, method: str, url: str, **kw: Any) -> Any:
    started = time.perf_counter()
    try:
        r = await client.request(method, url, **kw)
    except Exception as e:  # transport failure: counted, never hidden
        rec.add(name, (time.perf_counter() - started) * 1000, type(e).__name__)
        rec.errors.append(f"{name}: {type(e).__name__}: {e}"[:300])
        return None
    rec.add(name, (time.perf_counter() - started) * 1000, r.status_code)
    if r.status_code >= 500:
        rec.errors.append(f"{name}: HTTP {r.status_code}")
    return r


async def journey(client: Any, rec: Recorder, args: argparse.Namespace, n: int, token: str | None) -> None:
    run = args.run_id
    if token is None:
        email = f"load-{run}-{n}@example.invalid"
        await _call(
            client, rec, "register", "POST", "/v1/dev-auth/register", json={"email": email, "password": PASSWORD}
        )
        r = await _call(client, rec, "token", "POST", "/v1/dev-auth/token", json={"email": email, "password": PASSWORD})
        if r is None or r.status_code != 200:
            return
        token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    await _call(client, rec, "catalogue", "GET", "/v1/catalogue")
    await _call(client, rec, "trial", "POST", "/v1/me/trial", headers=h)
    form_req = {
        "grade": args.grade,
        "subject": args.subject,
        "chapter_ids": [args.chapter],
        "question_count": args.questions,
    }
    r = await _call(
        client,
        rec,
        "form",
        "POST",
        "/v1/practice/forms",
        headers={**h, "Idempotency-Key": uuid.uuid4().hex},
        json=form_req,
    )
    if r is None or r.status_code != 201:
        return
    r = await _call(client, rec, "start", "POST", f"/v1/practice/forms/{r.json()['id']}/attempt", headers=h)
    if r is None or r.status_code != 200:
        return
    attempt = r.json()
    revision: dict[int, int] = defaultdict(int)
    for item in attempt["items"]:
        for _ in range(2 if _rng.random() < 0.3 else 1):  # some learners change their answer
            await asyncio.sleep(_rng.uniform(*args.think))
            pos = item["position"]
            revision[pos] += 1
            op = {
                "op_id": str(uuid.uuid4()),
                "position": pos,
                "revision": revision[pos],
                "option_id": _rng.choice(item["options"])["id"],
            }
            await _call(
                client, rec, "save", "POST", f"/v1/attempts/{attempt['id']}/answers", headers=h, json={"ops": [op]}
            )
    await _call(
        client,
        rec,
        "submit",
        "POST",
        f"/v1/attempts/{attempt['id']}/submit",
        headers=h,
        json={"idempotency_key": uuid.uuid4().hex, "ops": []},
    )
    await _call(client, rec, "result", "GET", f"/v1/attempts/{attempt['id']}/result", headers=h)


async def main_async(args: argparse.Namespace) -> dict[str, Any]:
    import httpx2

    rec = Recorder()
    tokens: list[str] = []
    if args.tokens_file:
        with open(args.tokens_file, encoding="utf-8") as f:
            tokens = [t.strip() for t in f if t.strip()]
    limits = httpx2.Limits(max_connections=args.users * 2)
    async with httpx2.AsyncClient(base_url=args.target, timeout=args.timeout, limits=limits) as client:
        cfg = await client.get("/v1/runtime-config")
        role = cfg.json().get("role") if cfg.status_code == 200 else None
        if role == "production":
            raise SystemExit("refusing: the target reports role=production")
        started = time.perf_counter()
        deadline = started + args.duration

        async def user(n: int) -> None:
            await asyncio.sleep(args.ramp * n / max(args.users, 1))  # linear ramp-up arrival model
            while time.perf_counter() < deadline:
                await journey(client, rec, args, n, tokens[n % len(tokens)] if tokens else None)
                if tokens:
                    continue
                n += args.users  # a new account per journey with the development adapter

        await asyncio.gather(*(user(i) for i in range(args.users)))
        elapsed = time.perf_counter() - started
    return report(
        rec,
        {
            "tool": "loadtest.practice_journey",
            "run_id": args.run_id,
            "target": args.target,
            "target_role": role,
            "users": args.users,
            "ramp_s": args.ramp,
            "duration_s": round(elapsed, 1),
            "think_s": list(args.think),
            "arrival_model": "closed loop, linear ramp-up, uniform think time",
            "environment": "fill in: hardware, database size, region, cost",
        },
    )


def parse(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--target", default="http://127.0.0.1:8100")
    p.add_argument("--users", type=int, default=10)
    p.add_argument("--duration", type=float, default=60)
    p.add_argument("--ramp", type=float, default=10)
    p.add_argument("--think", type=float, nargs=2, default=(1.0, 4.0), metavar=("MIN", "MAX"))
    p.add_argument("--timeout", type=float, default=30)
    p.add_argument("--grade", type=int, required=True)
    p.add_argument("--subject", required=True)
    p.add_argument("--chapter", required=True)
    p.add_argument("--questions", type=int, default=10)
    p.add_argument("--tokens-file", help="Pre-issued access tokens, one per line (non-development targets)")
    p.add_argument("--allow-remote", action="store_true", help="Allow a non-local target (never production)")
    p.add_argument("--report", default="load-report.json")
    p.add_argument("--run-id", default=uuid.uuid4().hex[:8])
    args = p.parse_args(argv)
    host = urlparse(args.target).hostname or ""
    if host not in LOCAL_HOSTS and not args.allow_remote:
        p.error("non-local target: pass --allow-remote (and never point this at production)")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse(argv)
    out = asyncio.run(main_async(args))
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({k: out[k] for k in ("requests", "error_rate", "duration_s")}))
    return 0 if out["error_rate"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
