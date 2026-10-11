#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=scripts/ci_e2e_helpers.sh
source "$(dirname "$0")/ci_e2e_helpers.sh"

echo "==> Ensure live remediation for test-app (DRY_RUN=false + allowlist)"
kc set env deployment/self-healing-controller -n self-healing \
  DRY_RUN=false \
  REMEDIATION_NAMESPACES=test-app \
  POD_FAILURE_THRESHOLD=1
wait_controller_rollout self-healing 120

echo "==> Inject crashlooping deployment crash-heal"
kc apply -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: crash-heal
  namespace: test-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: crash-heal
  template:
    metadata:
      labels:
        app: crash-heal
    spec:
      containers:
        - name: crash
          image: busybox:1.36
          command: ["/bin/sh", "-c", "exit 1"]
EOF

START=$(date +%s)
found=0
for _ in $(seq 1 36); do
  metrics=$(scrape_controller_metrics self-healing 8082)
  if echo "$metrics" | grep -E 'remediations_total\{[^}]*result="success"'; then
    found=1
    echo "$metrics" | grep -E 'remediations_total\{[^}]*result="success"' | head -1
    break
  fi
  logs=$(controller_logs self-healing 200)
  if echo "$logs" | grep -E 'Restarted pod: test-app/crash-heal' >/dev/null; then
    found=1
    echo "$logs" | grep -E 'Restarted pod: test-app/crash-heal' | head -1
    break
  fi
  sleep 5
done
END=$(date +%s)
echo "time_to_remediation_seconds=$((END-START))"
if [ "$found" -ne 1 ]; then
  echo "Demo remediation did not observe live success"
  scrape_controller_metrics self-healing 8082 || true
  controller_logs self-healing 200
  exit 1
fi
kc delete deployment crash-heal -n test-app --wait=true
echo "OK"
