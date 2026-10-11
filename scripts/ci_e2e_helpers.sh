#!/usr/bin/env bash
# Shared helpers for self-healing controller e2e steps in CI.
# Sourced by workflow steps; not intended to be executed directly.
# shellcheck shell=bash

kc() {
  if command -v minikube >/dev/null 2>&1 && minikube status >/dev/null 2>&1; then
    minikube kubectl -- "$@"
  else
    kubectl "$@"
  fi
}

# Wait for Deployment rollout and for all replicas to be Ready on the new ReplicaSet.
wait_controller_rollout() {
  local ns="${1:-self-healing}"
  local timeout="${2:-120}"
  local deploy="${3:-self-healing-controller}"

  echo "Waiting for ${ns}/${deploy} rollout (timeout=${timeout}s)..."
  kc rollout status "deployment/${deploy}" -n "$ns" --timeout="${timeout}s"

  local deadline=$((SECONDS + timeout))
  while ((SECONDS < deadline)); do
    local desired updated available
    desired=$(kc get deploy "$deploy" -n "$ns" -o jsonpath='{.spec.replicas}')
    updated=$(kc get deploy "$deploy" -n "$ns" -o jsonpath='{.status.updatedReplicas}')
    available=$(kc get deploy "$deploy" -n "$ns" -o jsonpath='{.status.availableReplicas}')
    desired=${desired:-0}
    updated=${updated:-0}
    available=${available:-0}

    local terminating
    terminating=$(kc get pods -n "$ns" -l "app=${deploy}" -o jsonpath='{range .items[*]}{.metadata.deletionTimestamp}{"\n"}{end}' \
      | grep -c . || true)

    if [[ "$updated" == "$desired" && "$available" == "$desired" && "${terminating:-0}" -eq 0 ]]; then
      echo "Deployment ${ns}/${deploy} fully rolled out (replicas=${desired})"
      return 0
    fi
    sleep 2
  done

  echo "Timed out waiting for fully ready rollout of ${ns}/${deploy}" >&2
  kc get deploy "$deploy" -n "$ns" -o wide >&2 || true
  kc get rs -n "$ns" -l "app=${deploy}" -o wide >&2 || true
  kc get pods -n "$ns" -l "app=${deploy}" -o wide >&2 || true
  return 1
}

# Resolve the current Lease holder pod name (empty if none / not ready).
controller_leader_pod() {
  local ns="${1:-self-healing}"
  local lease="${2:-self-healing-controller}"
  local holder
  holder=$(kc get lease "$lease" -n "$ns" -o jsonpath='{.spec.holderIdentity}' 2>/dev/null || true)
  if [[ -z "$holder" ]]; then
    return 0
  fi
  if kc get pod "$holder" -n "$ns" >/dev/null 2>&1; then
    echo "$holder"
  fi
}

PF_PID=""
PF_PORT=""
PF_NS=""
PF_TARGET=""

stop_controller_port_forward() {
  if [[ -n "${PF_PID:-}" ]]; then
    kill "$PF_PID" 2>/dev/null || true
    wait "$PF_PID" 2>/dev/null || true
  fi
  PF_PID=""
  PF_TARGET=""
  if [[ -n "${PF_PORT:-}" ]]; then
    pkill -f "port-forward.*${PF_PORT}:8080" 2>/dev/null || true
  fi
}

# Prefer the Lease holder; fall back to the Service. Re-resolves on restart.
start_controller_port_forward() {
  local ns="${1:-self-healing}"
  local local_port="${2:-8080}"
  local svc="${3:-self-healing-controller}"

  stop_controller_port_forward
  PF_NS="$ns"
  PF_PORT="$local_port"

  local leader target log
  leader=$(controller_leader_pod "$ns" "$svc" || true)
  if [[ -n "$leader" ]]; then
    target="pod/${leader}"
  else
    target="svc/${svc}"
  fi
  PF_TARGET="$target"

  log="/tmp/pf-controller-${local_port}.log"
  : >"$log"
  echo "Port-forwarding ${target} -> localhost:${local_port}" >&2
  kc port-forward -n "$ns" "$target" "${local_port}:8080" >"$log" 2>&1 &
  PF_PID=$!

  for _ in $(seq 1 40); do
    if ! kill -0 "$PF_PID" 2>/dev/null; then
      echo "Port-forward exited early; re-resolving target..." >&2
      cat "$log" >&2 || true
      leader=$(controller_leader_pod "$ns" "$svc" || true)
      if [[ -n "$leader" ]]; then
        target="pod/${leader}"
      else
        target="svc/${svc}"
      fi
      PF_TARGET="$target"
      kc port-forward -n "$ns" "$target" "${local_port}:8080" >"$log" 2>&1 &
      PF_PID=$!
    fi
    if curl -sf "http://127.0.0.1:${local_port}/health" >/dev/null 2>&1; then
      # Prefer leader metrics when available.
      if curl -sf "http://127.0.0.1:${local_port}/metrics" 2>/dev/null | grep -q 'self_healing_is_leader 1'; then
        echo "Port-forward ready on leader via ${PF_TARGET}"
        return 0
      fi
      # Health works but not leader yet — keep waiting a bit for election, then accept.
      if [[ $_ -gt 15 ]]; then
        echo "Port-forward ready via ${PF_TARGET} (leader metric not yet visible)"
        return 0
      fi
    fi
    sleep 1
  done

  echo "Failed to establish port-forward on localhost:${local_port}" >&2
  cat "$log" >&2 || true
  return 1
}

ensure_controller_port_forward() {
  local ns="${1:-${PF_NS:-self-healing}}"
  local local_port="${2:-${PF_PORT:-8080}}"

  if [[ -z "${PF_PID:-}" ]] || ! kill -0 "$PF_PID" 2>/dev/null; then
    start_controller_port_forward "$ns" "$local_port"
    return $?
  fi
  if ! curl -sf "http://127.0.0.1:${local_port}/health" >/dev/null 2>&1; then
    start_controller_port_forward "$ns" "$local_port"
    return $?
  fi
  # If we are not on the leader, rebind — remediations only exist there.
  if ! curl -sf "http://127.0.0.1:${local_port}/metrics" 2>/dev/null | grep -q 'self_healing_is_leader 1'; then
    start_controller_port_forward "$ns" "$local_port"
    return $?
  fi
  return 0
}

# Scrape /metrics from every controller pod via exec (leader + followers).
# Remediations are recorded only on the Lease holder; Service PF can miss them.
scrape_controller_metrics() {
  local ns="${1:-self-healing}"
  local local_port="${2:-8080}"
  local pod metrics=""
  local pods
  pods=$(kc get pods -n "$ns" -l app=self-healing-controller -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || true)
  for pod in $pods; do
    metrics+=$(kc exec -n "$ns" "$pod" -- python -c \
      'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8080/metrics", timeout=5).read().decode())' \
      2>/dev/null || true)
    metrics+=$'\n'
  done
  if [[ -n "${metrics//[[:space:]]/}" ]]; then
    printf '%s' "$metrics"
    return 0
  fi
  # Fallback: port-forward path
  ensure_controller_port_forward "$ns" "$local_port" >/dev/null 2>&1 || true
  curl -sf "http://127.0.0.1:${local_port}/metrics" 2>/dev/null || true
}

# Logs from all controller replicas (deploy/ picks a random pod and can miss the leader).
controller_logs() {
  local ns="${1:-self-healing}"
  local tail_lines="${2:-200}"
  kc logs -n "$ns" -l app=self-healing-controller --all-containers=true --prefix=true --tail="$tail_lines" 2>/dev/null \
    || true
}

# Events emitted by brake/refusal paths (API-visible, not scrape-dependent).
controller_brake_events() {
  local ns="${1:-test-app}"
  kc get events -n "$ns" --field-selector reason=RemediationBrakeEngaged \
    -o custom-columns=LAST:.lastTimestamp,NAME:.involvedObject.name,MSG:.message --no-headers 2>/dev/null \
    || true
}

# True when the workload pod is detectable as a crash loop by the controller rules:
# CrashLoopBackOff waiting reason OR restartCount >= POD_FAILURE_THRESHOLD (default 3).
workload_is_crashlooping() {
  local ns="$1"
  local label="$2"
  local threshold="${3:-3}"
  local restarts reason
  restarts=$(kc get pods -n "$ns" -l "$label" \
    -o jsonpath='{.items[0].status.containerStatuses[0].restartCount}' 2>/dev/null || true)
  reason=$(kc get pods -n "$ns" -l "$label" \
    -o jsonpath='{.items[0].status.containerStatuses[0].state.waiting.reason}' 2>/dev/null || true)
  if [[ "$reason" == "CrashLoopBackOff" ]]; then
    return 0
  fi
  if [[ -n "${restarts:-}" && "$restarts" -ge "$threshold" ]]; then
    return 0
  fi
  return 1
}

wait_until_timeout() {
  local timeout_s="$1"
  local predicate="$2"
  local deadline=$((SECONDS + timeout_s))
  while ((SECONDS < deadline)); do
    if "$predicate"; then
      return 0
    fi
    sleep 5
  done
  return 1
}
