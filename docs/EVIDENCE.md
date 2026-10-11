# Evidence

Maps self-healing / chaos claims to CI proof. Status vocabulary: **Tested in CI** /
**Reference implementation** / **Simulated** / **Not yet**.

Timings below are copied from [docs/results.md](results.md) / [docs/results.json](results.json)
and the linked run only.

## Claim table

| Claim | Status | Scenario + environment | Real limits | Proof link | Negative tests |
| --- | --- | --- | --- | --- | --- |
| Fault inject → detect → remediate crash-loop (time to remediation) | Tested in CI | Job **Self-Healing Controller Tests**; CrashLoop deployment `crash-heal` in `test-app` (`busybox` `exit 1`) | CI runner + pipeline cluster from Terraform Deploy job — not a multi-AZ prod fleet; **20.1 s** is that run’s wall clock, not a contractual SLO for large clusters | Results run [38062111574](https://github.com/justrunme/self-healing-infrastructure-chaos-engineering/actions/runs/38062111574) · SHA `9c8e9e7dc3b95c5dc4a63e4809c0f010d1f63ead` · job [Self-Healing Controller Tests](https://github.com/justrunme/self-healing-infrastructure-chaos-engineering/actions/runs/38062111574/job/114242926259). Broader green pipeline example: [38089049033](https://github.com/justrunme/self-healing-infrastructure-chaos-engineering/actions/runs/38089049033) | Remediation success metric must appear; missing success fails the test path |
| Remediation brake / namespace budget exhaustion | Tested in CI | Same controller test job; `REMEDIATION_BUDGET_PER_NAMESPACE=2` | Budget/cooldown are controller settings in the test harness | Same results run — brake engaged (`budget_exhausted` / `result="brake_engaged"`) | Further remediations must be braked after budget |
| Terraform deploy + monitoring + integration + performance pipeline stages | Tested in CI | Workflow **Self-Healing Infrastructure CI/CD** jobs: Terraform Deploy, Monitoring Tests, Integration Tests, Performance Tests, etc. | Pipeline-defined scope; performance job is CI performance, not datacenter capacity proof | [38089049033](https://github.com/justrunme/self-healing-infrastructure-chaos-engineering/actions/runs/38089049033) · SHA `01707a2eb75f7c4b6ccd5959f975d603373f8048`. Latest green after remediation-safety merge: [38120835427](https://github.com/justrunme/self-healing-infrastructure-chaos-engineering/actions/runs/38120835427) · SHA `fda6cba4670b0c45365de9ec6d64909a604b2f2c` | Any stage failure fails the workflow |
| Chaos Mesh experiment suite as continuous prod chaos | Reference / Simulated | Chaos manifests and `scripts/test-chaos.sh` exist; CI includes chaos-related validation paths as wired in workflow | Lab/demo chaos ≠ ongoing production GameDay program | Prefer citing specific successful job logs when claiming a named experiment | Chaos test script failures fail local/CI when executed |
| Automatic node reboot via Kured in production fleets | Reference implementation | Kured manifests integrated in stack | Not evidenced as a measured node-reboot SLO in `docs/results.*` | — | Approval gates for dangerous node actions (product rule) |
| Multi-cluster remediation federation | Not yet | — | — | — | — |

## Not proven / out of scope

- Guaranteeing safe remediation on every proprietary workload without budgets/DRY_RUN
- Equating CI **20.1 s** time-to-remediation with large-cluster control-plane latency
- Unattended destructive node operations without approval annotations

## How to reproduce

```bash
./scripts/deploy-terraform.sh
./scripts/test-self-healing.sh
./scripts/test-chaos.sh
```

CI: `.github/workflows/ci-cd.yml`.
