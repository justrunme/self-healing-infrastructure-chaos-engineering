#!/usr/bin/env bash
# Port-forward to the self-healing controller Lease holder (not a follower).
set -euo pipefail

NAMESPACE="${1:-self-healing}"
LOCAL_PORT="${2:-8080}"
LEASE_NAME="${3:-self-healing-controller}"

holder=""
for _ in $(seq 1 45); do
  holder=$(kubectl get lease "$LEASE_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.holderIdentity}' 2>/dev/null || true)
  if [[ -n "$holder" ]]; then
    if kubectl get pod "$holder" -n "$NAMESPACE" >/dev/null 2>&1; then
      break
    fi
  fi
  holder=""
  sleep 2
done

if [[ -z "$holder" ]]; then
  echo "No leader lease holder found in ${NAMESPACE}/${LEASE_NAME}" >&2
  kubectl get lease -n "$NAMESPACE" >&2 || true
  kubectl get pods -n "$NAMESPACE" -o wide >&2 || true
  exit 1
fi

echo "Port-forwarding to leader pod ${holder} on localhost:${LOCAL_PORT}" >&2
kubectl port-forward -n "$NAMESPACE" "pod/${holder}" "${LOCAL_PORT}:8080"
