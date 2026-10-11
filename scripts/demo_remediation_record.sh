#!/usr/bin/env bash
set -euo pipefail
echo "==> Ensure live remediation for test-app (DRY_RUN=false + allowlist)"
minikube kubectl -- set env deployment/self-healing-controller -n self-healing \
  DRY_RUN=false \
  REMEDIATION_NAMESPACES=test-app
minikube kubectl -- rollout status deployment/self-healing-controller -n self-healing --timeout=90s
echo "==> Inject crashlooping deployment crash-heal"
minikube kubectl -- apply -f - <<'EOF'
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
minikube kubectl -- port-forward -n self-healing svc/self-healing-controller 8082:8080 >/tmp/pf.log 2>&1 &
PF=$!
trap 'kill $PF 2>/dev/null || true' EXIT
sleep 5
found=0
for _ in $(seq 1 24); do
  metrics=$(curl -sf http://localhost:8082/metrics || true)
  if echo "$metrics" | grep -E 'remediations_total\{[^}]*result="success"'; then
    found=1
    echo "$metrics" | grep -E 'remediations_total\{[^}]*result="success"' | head -1
    break
  fi
  sleep 5
done
END=$(date +%s)
echo "time_to_remediation_seconds=$((END-START))"
test "$found" -eq 1
minikube kubectl -- delete deployment crash-heal -n test-app --wait=true
echo "OK"
