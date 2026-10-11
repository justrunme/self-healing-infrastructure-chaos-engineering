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

PF_PID=""
PF_PORT=""
PF_NS=""

stop_controller_port_forward() {
  if [[ -n "${PF_PID:-}" ]]; then
    kill "$PF_PID" 2>/dev/null || true
    wait "$PF_PID" 2>/dev/null || true
  fi
  PF_PID=""
  if [[ -n "${PF_PORT:-}" ]]; then
    pkill -f "port-forward.*${PF_PORT}:8080" 2>/dev/null || true
  fi
}

# Port-forward to the Service (not a fixed pod). Restarts cleanly on demand.
start_controller_port_forward() {
  local ns="${1:-self-healing}"
  local local_port="${2:-8080}"
  local svc="${3:-self-healing-controller}"

  stop_controller_port_forward
  PF_NS="$ns"
  PF_PORT="$local_port"

  local log="/tmp/pf-controller-${local_port}.log"
  : >"$log"
  kc port-forward -n "$ns" "svc/${svc}" "${local_port}:8080" >"$log" 2>&1 &
  PF_PID=$!

  for _ in $(seq 1 40); do
    if ! kill -0 "$PF_PID" 2>/dev/null; then
      echo "Port-forward exited early; restarting..." >&2
      cat "$log" >&2 || true
      kc port-forward -n "$ns" "svc/${svc}" "${local_port}:8080" >"$log" 2>&1 &
      PF_PID=$!
    fi
    if curl -sf "http://127.0.0.1:${local_port}/health" >/dev/null 2>&1; then
      echo "Port-forward ready: svc/${svc} -> localhost:${local_port}"
      return 0
    fi
    sleep 1
  done

  echo "Failed to establish port-forward to svc/${svc} on localhost:${local_port}" >&2
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
  return 0
}

# Scrape /metrics with PF auto-restart. Prints body to stdout; never fails the shell.
scrape_controller_metrics() {
  local ns="${1:-self-healing}"
  local local_port="${2:-8080}"
  ensure_controller_port_forward "$ns" "$local_port" >/dev/null 2>&1 || true
  curl -sf "http://127.0.0.1:${local_port}/metrics" 2>/dev/null || true
}

controller_logs() {
  local ns="${1:-self-healing}"
  local tail_lines="${2:-200}"
  kc logs -n "$ns" deploy/self-healing-controller --all-containers=true --tail="$tail_lines" 2>/dev/null \
    || kc logs -n "$ns" -l app=self-healing-controller --tail="$tail_lines" 2>/dev/null \
    || true
}

# Wait until a predicate function returns 0, re-scraping metrics with bounded timeout.
# Usage: wait_until_timeout <seconds> <shell function name>
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
