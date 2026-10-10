# Results

Measured from CI run [`38062111574`](https://github.com/justrunme/self-healing-infrastructure-chaos-engineering/actions/runs/38062111574) (branch `main`, job **Self-Healing Controller Tests**, 2026-10-10).

## Fault inject → detect → remediate

| Step | Timestamp (UTC) | Detail |
| --- | --- | --- |
| Fault injected | 15:09:42.951Z | CrashLoop deployment `crash-heal` in `test-app` (`busybox` `exit 1`) |
| Remediation recorded | 15:10:03.081Z | `remediations_total{action="restart_crash_loop",namespace="test-app",result="success"} 1.0` |
| **Time to remediation** | **20.1 s** | wall clock between inject and success metric |

## Remediation brake

| Check | Result |
| --- | --- |
| Budget | `REMEDIATION_BUDGET_PER_NAMESPACE=2` |
| Brake engaged | yes (`budget_exhausted` / `result="brake_engaged"`) |
| Observed at | 15:10:19.447Z |

Job log: [Self-Healing Controller Tests](https://github.com/justrunme/self-healing-infrastructure-chaos-engineering/actions/runs/38062111574/job/114242926259).
