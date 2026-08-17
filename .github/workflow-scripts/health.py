#!/usr/bin/env python3
"""Report whether the external pinger is actually driving the watcher.

Usage:  python3 .github/workflow-scripts/health.py [hours]

Reads run history via `gh` and answers the three questions that matter:
is the pinger firing, is it firing at the interval you configured, and are
the runs it triggers succeeding. A dead pinger is invisible from the repo
otherwise — the backstop cron keeps producing green runs, just slowly.
"""

import datetime
import json
import statistics
import subprocess
import sys

REPO = "jkhatri23/internship-watcher-standalone"
FMT = "%Y-%m-%dT%H:%M:%SZ"
# Wider than the 2 min ping: anything longer is a gap, not a cadence sample.
MAX_PLAUSIBLE_GAP = 900


def parse(ts):
    return datetime.datetime.strptime(ts, FMT).replace(tzinfo=datetime.timezone.utc)


def main():
    hours = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    raw = subprocess.run(
        ["gh", "api", f"repos/{REPO}/actions/runs?per_page=100"],
        capture_output=True, text=True, check=True,
    ).stdout
    runs = json.loads(raw)["workflow_runs"]

    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(hours=hours)
    recent = [r for r in runs if parse(r["created_at"]) > cutoff]
    if not recent:
        sys.exit(f"no runs in the last {hours}h — pinger and cron are both dead")

    dispatched = sorted(
        (r for r in recent if r["event"] == "workflow_dispatch"),
        key=lambda r: r["created_at"],
    )
    scheduled = [r for r in recent if r["event"] == "schedule"]

    print(f"window: last {hours}h   runs: {len(recent)} "
          f"({len(dispatched)} dispatched, {len(scheduled)} scheduled)")

    gaps = []
    for a, b in zip(dispatched, dispatched[1:]):
        g = (parse(b["created_at"]) - parse(a["created_at"])).total_seconds()
        if g <= MAX_PLAUSIBLE_GAP:
            gaps.append(g)

    if gaps:
        med = statistics.median(gaps)
        print(f"ping gap:     median {med:.0f}s  min {min(gaps):.0f}s  "
              f"max {max(gaps):.0f}s  (n={len(gaps)})")
    else:
        med = None
        print("ping gap:     no consecutive dispatches — pinger looks DOWN")

    done = [r for r in recent if r["status"] == "completed"]
    durs = [(parse(r["updated_at"]) - parse(r["created_at"])).total_seconds()
            for r in done]
    if durs:
        print(f"run duration: median {statistics.median(durs):.0f}s  "
              f"max {max(durs):.0f}s")

    ok = sum(1 for r in done if r["conclusion"] == "success")
    bad = [r for r in done if r["conclusion"] == "failure"]
    print(f"outcomes:     {ok} success / {len(bad)} failure")
    for r in bad:
        print(f"  FAILED {r['created_at']}  {r['html_url']}")

    if med and durs:
        # On average a listing appears halfway through a ping interval.
        print(f"\n=> detection latency ~{med / 2 + statistics.median(durs):.0f}s "
              f"average, ~{med + max(durs):.0f}s worst case")

    last = parse(recent[0]["created_at"])
    age = (now - last).total_seconds()
    print(f"=> last run {age:.0f}s ago")
    if med and age > med * 3:
        print("   WARNING: no run in 3x the ping interval — check the pinger")


if __name__ == "__main__":
    main()
