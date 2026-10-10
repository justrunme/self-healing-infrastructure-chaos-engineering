#!/usr/bin/env python3
import json, os, re, time
from pathlib import Path

cast = Path("docs/assets/chaos-remediation.cast")
ttr = None
if cast.exists():
    for line in cast.read_text(errors="replace").splitlines()[1:]:
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if len(ev) >= 3 and isinstance(ev[2], str) and "time_to_remediation_seconds=" in ev[2]:
            m = re.search(r"time_to_remediation_seconds=(\d+)", ev[2])
            if m:
                ttr = int(m.group(1))
payload = {
    "repo": "self-healing-infrastructure-chaos-engineering",
    "source_run": "https://github.com/%s/actions/runs/%s"
    % (os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_RUN_ID", "")),
    "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "metrics": {"time_to_remediation_seconds": ttr},
}
Path("docs/results.json").write_text(json.dumps(payload, indent=2) + "\n")
print(json.dumps(payload, indent=2))
