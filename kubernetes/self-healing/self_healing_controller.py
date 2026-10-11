#!/usr/bin/env python3
"""
Self-Healing Infrastructure Controller with Bounded Remediation

This controller monitors Kubernetes cluster for failures and automatically
responds with bounded remediation: per-workload budgets/cooldowns, namespace
caps, dry-run mode, and approval gates for dangerous operations.
"""

import logging
import os
import socket
import subprocess
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Set, Tuple

import requests
from flask import Flask, Response, jsonify
from kubernetes.client.rest import ApiException
from kubernetes.leaderelection import electionconfig, leaderelection
from kubernetes.leaderelection.leaderelectionrecord import LeaderElectionRecord
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    generate_latest,
)

from kubernetes import client, config, watch

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Prometheus metrics
remediations_total = Counter(
    "remediations_total",
    "Total number of remediation actions",
    ["namespace", "action", "result"],
)
remediation_skips_total = Counter(
    "remediation_skips_total",
    "Total number of skipped remediation attempts",
    ["namespace", "reason"],
)
brake_engaged = Gauge(
    "brake_engaged",
    "Whether the remediation brake is currently engaged",
    ["namespace", "reason"],
)
remediation_budget_remaining = Gauge(
    "remediation_budget_remaining",
    "Remaining remediation budget for a namespace",
    ["namespace"],
)
workload_budget_remaining = Gauge(
    "workload_budget_remaining",
    "Remaining remediation budget for a workload owner",
    ["namespace", "workload"],
)
is_leader_gauge = Gauge(
    "self_healing_is_leader",
    "Whether this replica currently holds the leader lease",
)

CONTROLLER_OWNER_KINDS = frozenset(
    {
        "ReplicaSet",
        "StatefulSet",
        "DaemonSet",
        "Job",
        "ReplicationController",
        "Deployment",
    }
)


@dataclass
class RemediationConfig:
    """Configuration for bounded remediation"""

    budget_per_namespace: int
    budget_per_workload: int
    budget_window_seconds: int
    cooldown_seconds: int
    dry_run: bool
    require_approval_for_dangerous: bool
    pod_delete_grace_period_seconds: Optional[int]
    slack_brake_rate_limit_seconds: int


class RemediationBudget:
    """Tracks remediation budget within a sliding window"""

    def __init__(self, max_count: int, window_seconds: int):
        self.max_count = max_count
        self.window_seconds = window_seconds
        self.remediations: deque = deque()

    def can_remediate(self) -> bool:
        """Check if remediation is allowed within budget"""
        self._cleanup_old_entries()
        return len(self.remediations) < self.max_count

    def record_remediation(self):
        """Record a new remediation action"""
        self._cleanup_old_entries()
        self.remediations.append(datetime.now())

    def remaining(self) -> int:
        """Get remaining budget"""
        self._cleanup_old_entries()
        return max(0, self.max_count - len(self.remediations))

    def _cleanup_old_entries(self):
        """Remove entries outside the sliding window"""
        cutoff = datetime.now() - timedelta(seconds=self.window_seconds)
        while self.remediations and self.remediations[0] < cutoff:
            self.remediations.popleft()


class ObjectCooldown:
    """Tracks per-workload cooldown periods"""

    def __init__(self, cooldown_seconds: int):
        self.cooldown_seconds = cooldown_seconds
        self.last_remediation: Dict[str, datetime] = {}

    def can_remediate(self, obj_key: str) -> bool:
        """Check if object is off cooldown"""
        if obj_key not in self.last_remediation:
            return True
        elapsed = (datetime.now() - self.last_remediation[obj_key]).total_seconds()
        return elapsed >= self.cooldown_seconds

    def record_remediation(self, obj_key: str):
        """Record remediation for an object"""
        self.last_remediation[obj_key] = datetime.now()

    def last_timestamp(self, obj_key: str) -> Optional[datetime]:
        """Return last remediation timestamp if present"""
        return self.last_remediation.get(obj_key)


class LeaseLock:
    """Leader-election lock backed by coordination.k8s.io/Lease."""

    def __init__(self, name: str, namespace: str, identity: str):
        self.api_instance = client.CoordinationV1Api()
        self.name = name
        self.namespace = namespace
        self.identity = str(identity)
        self.lease_reference = None
        self.lock_record = {
            "holderIdentity": None,
            "leaseDurationSeconds": None,
            "acquireTime": None,
            "renewTime": None,
        }

    def get(self, name, namespace):
        try:
            lease = self.api_instance.read_namespaced_lease(name, namespace)
            self.lease_reference = lease
            spec = lease.spec
            if spec is None or not spec.holder_identity:
                return True, None
            record = LeaderElectionRecord(
                spec.holder_identity,
                str(spec.lease_duration_seconds) if spec.lease_duration_seconds is not None else None,
                spec.acquire_time.isoformat() if spec.acquire_time else None,
                spec.renew_time.isoformat() if spec.renew_time else None,
            )
            return True, record
        except ApiException as e:
            return False, e

    def create(self, name, namespace, election_record):
        body = client.V1Lease(
            metadata=client.V1ObjectMeta(name=name),
            spec=self._to_lease_spec(election_record),
        )
        try:
            self.api_instance.create_namespaced_lease(namespace, body)
            return True
        except ApiException as e:
            logger.info("Failed to create lease lock: %s", e)
            return False

    def update(self, name, namespace, updated_record):
        try:
            self.lease_reference.spec = self._to_lease_spec(updated_record)
            self.api_instance.replace_namespaced_lease(
                name=name,
                namespace=namespace,
                body=self.lease_reference,
            )
            return True
        except ApiException as e:
            logger.info("Failed to update lease lock: %s", e)
            return False

    @staticmethod
    def _parse_lease_time(value):
        """Parse lease timestamps; Kubernetes MicroTime requires a timezone offset."""
        if value is None:
            return None
        if isinstance(value, datetime):
            dt = value
        else:
            text = str(value).strip().replace("Z", "+00:00")
            # leaderelection passes str(datetime) with a space separator
            dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    def _to_lease_spec(self, election_record: LeaderElectionRecord):
        duration = None
        if election_record.lease_duration is not None:
            duration = int(election_record.lease_duration)
        return client.V1LeaseSpec(
            holder_identity=election_record.holder_identity,
            lease_duration_seconds=duration,
            acquire_time=self._parse_lease_time(election_record.acquire_time),
            renew_time=self._parse_lease_time(election_record.renew_time),
        )


class SelfHealingController:
    def __init__(self):
        """Initialize the Self-Healing Controller"""
        self.config = self._load_config()
        self.remediation_config = self._load_remediation_config()
        self.k8s_client = self._init_kubernetes_client()
        self.apps_v1 = client.AppsV1Api()
        self.coordination_v1 = client.CoordinationV1Api()
        self.running = True
        self.is_leader = False
        self._state_lock = threading.RLock()
        self._watch_threads_started = False
        self.last_pod_event_at: Optional[datetime] = None
        self.last_node_event_at: Optional[datetime] = None
        self._slack_last_sent: Dict[str, datetime] = {}

        self.namespace_budgets: Dict[str, RemediationBudget] = defaultdict(
            lambda: RemediationBudget(
                self.remediation_config.budget_per_namespace,
                self.remediation_config.budget_window_seconds,
            )
        )
        self.workload_budgets: Dict[str, RemediationBudget] = defaultdict(
            lambda: RemediationBudget(
                self.remediation_config.budget_per_workload,
                self.remediation_config.budget_window_seconds,
            )
        )
        self.object_cooldown = ObjectCooldown(self.remediation_config.cooldown_seconds)

        self.approved_dangerous_actions: Set[str] = set()
        self.identity = os.getenv("POD_NAME") or f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
        self.lease_namespace = os.getenv("POD_NAMESPACE", "self-healing")
        self.lease_name = os.getenv("LEADER_ELECTION_LEASE_NAME", "self-healing-controller")

    def _load_config(self):
        """Load configuration from environment variables"""
        return {
            "pod_failure_threshold": int(os.getenv("POD_FAILURE_THRESHOLD", 3)),
            "pod_restart_timeout": int(os.getenv("POD_RESTART_TIMEOUT", 300)),
            "node_failure_threshold": int(os.getenv("NODE_FAILURE_THRESHOLD", 2)),
            "node_unreachable_timeout": int(os.getenv("NODE_UNREACHABLE_TIMEOUT", 600)),
            "helm_rollback_enabled": os.getenv("HELM_ROLLBACK_ENABLED", "true").lower() == "true",
            "helm_rollback_timeout": int(os.getenv("HELM_ROLLBACK_TIMEOUT", 300)),
            "node_cordon_enabled": os.getenv("NODE_CORDON_ENABLED", "true").lower() == "true",
            "slack_notifications_enabled": os.getenv("SLACK_NOTIFICATIONS_ENABLED", "false").lower() == "true",
            "slack_webhook_url": os.getenv("SLACK_WEBHOOK_URL", ""),
            "slack_channel": os.getenv("SLACK_CHANNEL", "#alerts"),
            "prometheus_enabled": os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true",
            "prometheus_url": os.getenv(
                "PROMETHEUS_URL", "http://prometheus-service.monitoring.svc.cluster.local:9090"
            ),
            "leader_election_enabled": os.getenv("LEADER_ELECTION_ENABLED", "true").lower() == "true",
        }

    def _load_remediation_config(self) -> RemediationConfig:
        """Load remediation brake configuration"""
        grace_raw = os.getenv("POD_DELETE_GRACE_PERIOD_SECONDS", "30")
        grace_period = None if grace_raw.lower() in {"", "none", "default"} else int(grace_raw)
        return RemediationConfig(
            budget_per_namespace=int(os.getenv("REMEDIATION_BUDGET_PER_NAMESPACE", 10)),
            budget_per_workload=int(os.getenv("REMEDIATION_BUDGET_PER_WORKLOAD", 3)),
            budget_window_seconds=int(os.getenv("REMEDIATION_BUDGET_WINDOW_SECONDS", 300)),
            cooldown_seconds=int(os.getenv("REMEDIATION_COOLDOWN_SECONDS", 60)),
            dry_run=os.getenv("DRY_RUN", "false").lower() == "true",
            require_approval_for_dangerous=os.getenv("REQUIRE_APPROVAL_FOR_DANGEROUS", "true").lower() == "true",
            pod_delete_grace_period_seconds=grace_period,
            slack_brake_rate_limit_seconds=int(os.getenv("SLACK_BRAKE_RATE_LIMIT_SECONDS", 60)),
        )

    def _init_kubernetes_client(self):
        """Initialize Kubernetes client"""
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()

        return client.CoreV1Api()

    def start_monitoring(self):
        """Start monitoring the cluster for failures"""
        logger.info("Starting Self-Healing Controller with bounded remediation...")
        logger.info(f"Configuration: {self.config}")
        logger.info(f"Remediation Config: {self.remediation_config}")

        if self.remediation_config.dry_run:
            logger.warning("DRY RUN MODE ENABLED - No actual remediation will be performed")

        self._start_health_server()

        if self.config["leader_election_enabled"]:
            while self.running:
                self._run_leader_election()
                if self.running:
                    logger.info("Leader election ended; retrying acquisition")
                    time.sleep(2)
        else:
            self._on_started_leading()
            while self.running:
                time.sleep(1)

    def _run_leader_election(self):
        """Block in leader election; run watches only while holding the lease."""

        def on_started():
            self._on_started_leading()
            while self.running and self.is_leader:
                time.sleep(1)

        def on_stopped():
            logger.warning("Lost leadership; pausing remediation watches")
            self.is_leader = False
            is_leader_gauge.set(0)

        lock = LeaseLock(self.lease_name, self.lease_namespace, self.identity)
        cfg = electionconfig.Config(
            lock,
            lease_duration=15,
            renew_deadline=10,
            retry_period=2,
            onstarted_leading=on_started,
            onstopped_leading=on_stopped,
        )
        logger.info(
            "Starting leader election identity=%s lease=%s/%s",
            self.identity,
            self.lease_namespace,
            self.lease_name,
        )
        leaderelection.LeaderElection(cfg).run()

    def _on_started_leading(self):
        """Called when this replica becomes leader."""
        logger.info("Acquired leadership identity=%s", self.identity)
        self.is_leader = True
        is_leader_gauge.set(1)
        if not self._watch_threads_started:
            self._start_pod_watch()
            self._start_node_watch()
            self._watch_threads_started = True

    def _start_pod_watch(self):
        """Start watching pods using Kubernetes watch API"""

        def watch_pods():
            resource_version = None
            while self.running:
                if self.config["leader_election_enabled"] and not self.is_leader:
                    time.sleep(1)
                    continue
                try:
                    w = watch.Watch()
                    logger.info(f"Starting pod watch from resource_version={resource_version}")

                    for event in w.stream(
                        self.k8s_client.list_pod_for_all_namespaces,
                        resource_version=resource_version,
                        timeout_seconds=300,
                    ):
                        if not self.running:
                            break
                        if self.config["leader_election_enabled"] and not self.is_leader:
                            break

                        event_type = event["type"]
                        pod = event["object"]
                        resource_version = pod.metadata.resource_version
                        self.last_pod_event_at = datetime.now()

                        if event_type in ["ADDED", "MODIFIED"]:
                            if self._should_skip_pod(pod):
                                continue

                            if self._is_pod_failing(pod):
                                self._handle_pod_failure(pod)
                            elif self._is_pod_crash_looping(pod):
                                self._handle_crash_looping_pod(pod)

                except client.exceptions.ApiException as e:
                    if e.status == 410:
                        logger.warning("Resource version too old, resetting watch")
                        resource_version = None
                    else:
                        logger.error(f"API exception in pod watch: {e}")
                        time.sleep(10)
                except Exception as e:
                    logger.error(f"Error in pod watch: {e}")
                    time.sleep(10)

        thread = threading.Thread(target=watch_pods, daemon=True, name="pod-watch")
        thread.start()
        logger.info("Pod watch started")

    def _start_node_watch(self):
        """Start watching nodes using Kubernetes watch API"""

        def watch_nodes():
            resource_version = None
            while self.running:
                if self.config["leader_election_enabled"] and not self.is_leader:
                    time.sleep(1)
                    continue
                try:
                    w = watch.Watch()
                    logger.info(f"Starting node watch from resource_version={resource_version}")

                    for event in w.stream(
                        self.k8s_client.list_node,
                        resource_version=resource_version,
                        timeout_seconds=300,
                    ):
                        if not self.running:
                            break
                        if self.config["leader_election_enabled"] and not self.is_leader:
                            break

                        event_type = event["type"]
                        node = event["object"]
                        resource_version = node.metadata.resource_version
                        self.last_node_event_at = datetime.now()

                        if event_type in ["ADDED", "MODIFIED"]:
                            if self._is_node_failing(node):
                                self._handle_node_failure(node)

                except client.exceptions.ApiException as e:
                    if e.status == 410:
                        logger.warning("Resource version too old, resetting watch")
                        resource_version = None
                    else:
                        logger.error(f"API exception in node watch: {e}")
                        time.sleep(10)
                except Exception as e:
                    logger.error(f"Error in node watch: {e}")
                    time.sleep(10)

        thread = threading.Thread(target=watch_nodes, daemon=True, name="node-watch")
        thread.start()
        logger.info("Node watch started")

    def _start_health_server(self):
        """Start health check server with Prometheus metrics"""
        app = Flask(__name__)

        @app.route("/health")
        def health():
            return jsonify({"status": "healthy", "running": self.running, "identity": self.identity})

        @app.route("/ready")
        def ready():
            # All replicas report ready so multi-replica Deployments can roll out;
            # only the lease holder runs remediation watches.
            status = "ready" if self.running else "not_ready"
            code = 200 if status == "ready" else 503
            return (
                jsonify(
                    {
                        "status": status,
                        "running": self.running,
                        "is_leader": self.is_leader,
                        "watches_started": self._watch_threads_started,
                        "last_pod_event_at": self.last_pod_event_at.isoformat() if self.last_pod_event_at else None,
                        "last_node_event_at": self.last_node_event_at.isoformat() if self.last_node_event_at else None,
                    }
                ),
                code,
            )

        @app.route("/metrics")
        def metrics():
            return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

        def run_server():
            app.run(host="0.0.0.0", port=8080)

        thread = threading.Thread(target=run_server, daemon=True, name="health-server")
        thread.start()
        logger.info("Health server started on port 8080")

    def _should_skip_pod(self, pod):
        """Check if pod should be skipped"""
        namespace = pod.metadata.namespace
        pod_name = pod.metadata.name

        if namespace in ["kube-system", "monitoring", "chaos-engineering", "self-healing"]:
            return True

        if pod_name.startswith("self-healing-controller-"):
            return True

        if pod.metadata.deletion_timestamp:
            return True

        return False

    def _is_pod_failing(self, pod):
        """Check if pod is in a terminal failed state.

        Ready=False alone is not a failure: new pods are unready while they start.
        """
        if pod.status.phase in ["Failed", "Unknown"]:
            return True
        return False

    def _is_pod_crash_looping(self, pod):
        """Check if pod is crash looping"""
        if pod.status.container_statuses:
            for container in pod.status.container_statuses:
                waiting = getattr(container.state, "waiting", None)
                if waiting is not None and getattr(waiting, "reason", None) == "CrashLoopBackOff":
                    return True
                if container.restart_count > self.config["pod_failure_threshold"]:
                    return True
        return False

    def _resolve_owner(self, pod) -> Optional[Tuple[str, str, str]]:
        """Resolve controlling owner for a pod.

        Returns (namespace, kind, name) for a controller-owned pod, or None for bare pods.
        Walks ReplicaSet -> Deployment when possible.
        """
        owner_refs = pod.metadata.owner_references or []
        controller_refs = [ref for ref in owner_refs if getattr(ref, "controller", False)]
        refs = controller_refs or owner_refs
        if not refs:
            return None

        ref = refs[0]
        kind = ref.kind
        name = ref.name
        namespace = pod.metadata.namespace

        if kind not in CONTROLLER_OWNER_KINDS:
            return None

        if kind == "ReplicaSet":
            try:
                rs = self.apps_v1.read_namespaced_replica_set(name, namespace)
                rs_owners = rs.metadata.owner_references or []
                for rs_ref in rs_owners:
                    if rs_ref.kind == "Deployment" and getattr(rs_ref, "controller", True):
                        return namespace, "Deployment", rs_ref.name
            except ApiException as e:
                logger.warning("Failed to resolve ReplicaSet owner for %s/%s: %s", namespace, name, e)
            return namespace, "ReplicaSet", name

        return namespace, kind, name

    def _workload_key(self, namespace: str, kind: str, name: str) -> str:
        return f"{namespace}/{kind}/{name}"

    def _can_remediate(self, namespace: str, workload_key: str, action: str) -> tuple[bool, Optional[str]]:
        """Check if remediation is allowed (namespace cap + workload budget + cooldown)"""
        with self._state_lock:
            ns_budget = self.namespace_budgets[namespace]
            if not ns_budget.can_remediate():
                reason = f"budget_exhausted:namespace={namespace}"
                brake_engaged.labels(namespace=namespace, reason="budget_exhausted").set(1)
                remediation_budget_remaining.labels(namespace=namespace).set(0)
                return False, reason

            wl_budget = self.workload_budgets[workload_key]
            if not wl_budget.can_remediate():
                reason = f"budget_exhausted:workload={workload_key}"
                brake_engaged.labels(namespace=namespace, reason="workload_budget_exhausted").set(1)
                workload_budget_remaining.labels(namespace=namespace, workload=workload_key).set(0)
                return False, reason

            if not self.object_cooldown.can_remediate(workload_key):
                reason = f"cooldown_active:workload={workload_key}"
                brake_engaged.labels(namespace=namespace, reason="cooldown_active").set(1)
                return False, reason

            brake_engaged.labels(namespace=namespace, reason="none").set(0)
            remediation_budget_remaining.labels(namespace=namespace).set(ns_budget.remaining())
            workload_budget_remaining.labels(namespace=namespace, workload=workload_key).set(wl_budget.remaining())
            return True, None

    def _record_attempt(self, namespace: str, workload_key: str):
        """Consume namespace/workload budget and reset cooldown for a real remediation attempt."""
        with self._state_lock:
            self.namespace_budgets[namespace].record_remediation()
            self.workload_budgets[workload_key].record_remediation()
            self.object_cooldown.record_remediation(workload_key)
            remediation_budget_remaining.labels(namespace=namespace).set(self.namespace_budgets[namespace].remaining())
            workload_budget_remaining.labels(namespace=namespace, workload=workload_key).set(
                self.workload_budgets[workload_key].remaining()
            )

    def _record_outcome(self, namespace: str, action: str, result: str):
        """Record metrics for an outcome without consuming budget or cooldown."""
        remediations_total.labels(namespace=namespace, action=action, result=result).inc()

    def _record_remediation(self, namespace: str, workload_key: str, action: str, result: str):
        """Record a real remediation attempt (budget + cooldown + metrics)."""
        self._record_attempt(namespace, workload_key)
        self._record_outcome(namespace, action, result)

    def _record_brake(self, namespace: str, workload_key: str, action: str, reason: str):
        """Record brake engagement without consuming budget or resetting cooldown."""
        self._record_outcome(namespace, action, "brake_engaged")
        remediation_skips_total.labels(namespace=namespace, reason="brake_engaged").inc()
        self._emit_event(
            namespace=namespace,
            involved_name=workload_key.split("/")[-1],
            involved_kind=workload_key.split("/")[1] if workload_key.count("/") >= 2 else "Pod",
            reason="RemediationBrakeEngaged",
            message=f"Brake engaged for {action} on {workload_key}: {reason}",
            type_="Warning",
        )

    def _is_dangerous_action(self, action: str) -> bool:
        """Check if action requires approval"""
        return action in ["node_drain", "node_cordon"]

    def _consume_approval(self, obj_key: str, action: str, annotation_key: str) -> bool:
        """Consume a single-use approval annotation after a successful check."""
        approval_key = f"{obj_key}:{action}"
        try:
            node_name = obj_key.split("/")[1]
            node = self.k8s_client.read_node(node_name)
            annotations = dict(node.metadata.annotations or {})
            if annotations.get(annotation_key) == "true":
                annotations.pop(annotation_key, None)
                self.k8s_client.patch_node(
                    name=node_name,
                    body={"metadata": {"annotations": {annotation_key: None}}},
                )
                self.approved_dangerous_actions.discard(approval_key)
                return True
        except Exception as e:
            logger.error(f"Error consuming approval for {obj_key}: {e}")
        return False

    def _check_approval(self, obj_key: str, action: str) -> bool:
        """Check if dangerous action has been approved (single-use)."""
        if not self.remediation_config.require_approval_for_dangerous:
            return True

        approval_key = f"{obj_key}:{action}"
        annotation_map = {
            "node_drain": "self-healing.justrunme.com/approve-drain",
            "node_cordon": "self-healing.justrunme.com/approve-cordon",
        }
        annotation_key = annotation_map.get(action)
        if not annotation_key:
            return False

        try:
            node = self.k8s_client.read_node(obj_key.split("/")[1])
            annotations = node.metadata.annotations or {}
            if annotations.get(annotation_key) == "true":
                self.approved_dangerous_actions.add(approval_key)
                return True
        except Exception as e:
            logger.error(f"Error checking approval for {obj_key}: {e}")
            return False

        return False

    def _emit_event(
        self,
        namespace: str,
        involved_name: str,
        involved_kind: str,
        reason: str,
        message: str,
        type_: str = "Normal",
    ):
        """Emit a Kubernetes event best-effort."""
        try:
            now = datetime.utcnow()
            event = client.CoreV1Event(
                metadata=client.V1ObjectMeta(
                    name=f"self-healing.{uuid.uuid4().hex[:12]}",
                    namespace=namespace,
                ),
                involved_object=client.V1ObjectReference(
                    kind=involved_kind,
                    name=involved_name,
                    namespace=namespace,
                ),
                reason=reason,
                message=message[:1024],
                type=type_,
                source=client.V1EventSource(component="self-healing-controller"),
                first_timestamp=now,
                last_timestamp=now,
                count=1,
            )
            self.k8s_client.create_namespaced_event(namespace, event)
        except Exception as e:
            logger.debug("Failed to emit event %s: %s", reason, e)

    def _handle_pod_failure(self, pod):
        """Handle pod failure by attempting recovery"""
        pod_name = pod.metadata.name
        namespace = pod.metadata.namespace
        owner = self._resolve_owner(pod)
        if owner is None:
            self._skip_unowned_pod(pod, "restart_pod")
            return

        ns, kind, name = owner
        workload_key = self._workload_key(ns, kind, name)

        can_remediate, reason = self._can_remediate(namespace, workload_key, "restart_pod")
        if not can_remediate:
            logger.warning(f"BRAKE ENGAGED: Cannot remediate {workload_key} - {reason}")
            self._send_slack_notification(
                f"Brake Engaged: {pod_name}",
                f"Cannot remediate pod {pod_name} in {namespace}: {reason}",
                rate_key=f"brake:{workload_key}",
            )
            self._record_brake(namespace, workload_key, "restart_pod", reason or "unknown")
            return

        logger.warning(f"Pod failure detected: {namespace}/{pod_name} owner={workload_key}")

        if self.remediation_config.dry_run:
            logger.info(f"DRY RUN: Would restart pod {namespace}/{pod_name}")
            self._send_slack_notification(
                f"DRY RUN: Pod Failure: {pod_name}",
                f"Would restart pod {pod_name} in namespace {namespace}",
            )
            self._record_remediation(namespace, workload_key, "restart_pod", "dry_run")
            return

        self._send_slack_notification(
            f"Pod Failure: {pod_name}", f"Pod {pod_name} in namespace {namespace} has failed. Attempting recovery..."
        )

        success = self._restart_pod(pod)
        result = "success" if success else "failure"
        self._record_remediation(namespace, workload_key, "restart_pod", result)

        if success and self._is_helm_managed_pod(pod):
            self._handle_helm_pod_failure(pod)

    def _handle_crash_looping_pod(self, pod):
        """Handle crash looping pod"""
        pod_name = pod.metadata.name
        namespace = pod.metadata.namespace
        owner = self._resolve_owner(pod)
        if owner is None:
            self._skip_unowned_pod(pod, "restart_crash_loop")
            return

        ns, kind, name = owner
        workload_key = self._workload_key(ns, kind, name)

        can_remediate, reason = self._can_remediate(namespace, workload_key, "restart_crash_loop")
        if not can_remediate:
            logger.warning(f"BRAKE ENGAGED: Cannot remediate crash loop {workload_key} - {reason}")
            self._send_slack_notification(
                f"Brake Engaged: {pod_name}",
                f"Cannot remediate crash loop {pod_name} in {namespace}: {reason}",
                rate_key=f"brake:{workload_key}",
            )
            self._record_brake(namespace, workload_key, "restart_crash_loop", reason or "unknown")
            return

        logger.warning(f"Crash looping pod detected: {namespace}/{pod_name} owner={workload_key}")

        if self.remediation_config.dry_run:
            logger.info(f"DRY RUN: Would restart crash looping pod {namespace}/{pod_name}")
            self._record_remediation(namespace, workload_key, "restart_crash_loop", "dry_run")
            return

        self._send_slack_notification(
            f"Crash Looping Pod: {pod_name}",
            f"Pod {pod_name} in namespace {namespace} is crash looping. Attempting recovery...",
        )

        success = self._restart_pod(pod)
        result = "success" if success else "failure"
        self._record_remediation(namespace, workload_key, "restart_crash_loop", result)

    def _skip_unowned_pod(self, pod, action: str):
        """Never delete bare pods; emit event + metrics."""
        namespace = pod.metadata.namespace
        pod_name = pod.metadata.name
        logger.info("Skipping bare pod %s/%s (no controller owner)", namespace, pod_name)
        self._record_outcome(namespace, action, "skipped_unowned")
        remediation_skips_total.labels(namespace=namespace, reason="unowned").inc()
        self._emit_event(
            namespace=namespace,
            involved_name=pod_name,
            involved_kind="Pod",
            reason="RemediationSkippedUnowned",
            message=f"Skipping {action}: pod has no controller owner",
            type_="Warning",
        )

    def _restart_pod(self, pod) -> bool:
        """Restart a controller-owned pod with a graceful deletion (no force-delete)."""
        try:
            kwargs = {
                "name": pod.metadata.name,
                "namespace": pod.metadata.namespace,
            }
            grace = self.remediation_config.pod_delete_grace_period_seconds
            if grace is not None:
                kwargs["grace_period_seconds"] = grace
            self.k8s_client.delete_namespaced_pod(**kwargs)
            logger.info(
                "Restarted pod: %s/%s (grace_period_seconds=%s)",
                pod.metadata.namespace,
                pod.metadata.name,
                grace,
            )
            return True
        except ApiException as e:
            if e.status == 404:
                logger.info(f"Pod {pod.metadata.name} already deleted")
                return True
            else:
                logger.error(f"Failed to restart pod {pod.metadata.name}: {e}")
                return False

    def _is_helm_managed_pod(self, pod) -> bool:
        """Return True only for pods that are actually managed by a Helm release."""
        labels = pod.metadata.labels or {}
        annotations = pod.metadata.annotations or {}

        if labels.get("app.kubernetes.io/managed-by") != "Helm":
            return False

        release_name = annotations.get("meta.helm.sh/release-name") or labels.get("app.kubernetes.io/instance")
        if not release_name:
            return False

        release_ns = annotations.get("meta.helm.sh/release-namespace") or pod.metadata.namespace
        return self._helm_release_exists(release_ns, release_name)

    def _helm_release_exists(self, namespace: str, release_name: str) -> bool:
        """Verify a Helm v3 release secret exists for the given release."""
        try:
            secrets = self.k8s_client.list_namespaced_secret(
                namespace,
                label_selector=f"owner=helm,name={release_name}",
            )
            for secret in secrets.items or []:
                if secret.type == "helm.sh/release.v1":
                    return True
                if (secret.metadata.name or "").startswith(f"sh.helm.release.v1.{release_name}."):
                    return True
        except ApiException as e:
            logger.warning("Failed to list Helm secrets for %s/%s: %s", namespace, release_name, e)

        try:
            secrets = self.k8s_client.list_namespaced_secret(namespace)
            prefix = f"sh.helm.release.v1.{release_name}."
            for secret in secrets.items or []:
                if (secret.metadata.name or "").startswith(prefix) and secret.type == "helm.sh/release.v1":
                    return True
        except ApiException as e:
            logger.warning("Failed to verify Helm release %s/%s: %s", namespace, release_name, e)
        return False

    def _handle_helm_pod_failure(self, pod):
        """Handle failure of Helm-managed pod"""
        if not self.config["helm_rollback_enabled"]:
            return

        labels = pod.metadata.labels or {}
        annotations = pod.metadata.annotations or {}
        release_name = annotations.get("meta.helm.sh/release-name") or labels.get("app.kubernetes.io/instance")
        if not release_name:
            return

        namespace = annotations.get("meta.helm.sh/release-namespace") or pod.metadata.namespace
        if not self._helm_release_exists(namespace, release_name):
            logger.info("Skipping Helm rollback; no release secret for %s/%s", namespace, release_name)
            self._record_outcome(namespace, "helm_rollback", "skipped_not_helm")
            remediation_skips_total.labels(namespace=namespace, reason="not_helm_release").inc()
            return

        helm_key = self._workload_key(namespace, "HelmRelease", release_name)

        can_remediate, reason = self._can_remediate(namespace, helm_key, "helm_rollback")
        if not can_remediate:
            logger.warning(f"BRAKE ENGAGED: Cannot rollback {release_name} - {reason}")
            self._record_brake(namespace, helm_key, "helm_rollback", reason or "unknown")
            return

        logger.info(f"Attempting Helm rollback for release: {release_name}")

        if self.remediation_config.dry_run:
            logger.info(f"DRY RUN: Would rollback Helm release {release_name}")
            self._record_remediation(namespace, helm_key, "helm_rollback", "dry_run")
            return

        try:
            result = subprocess.run(
                ["helm", "rollback", release_name, "--namespace", namespace],
                capture_output=True,
                text=True,
                timeout=self.config["helm_rollback_timeout"],
            )

            if result.returncode == 0:
                logger.info(f"Successfully rolled back Helm release: {release_name}")
                self._send_slack_notification(
                    f"Helm Rollback: {release_name}",
                    f"Successfully rolled back Helm release {release_name} in namespace {namespace}",
                )
                self._record_remediation(namespace, helm_key, "helm_rollback", "success")
            else:
                logger.error(f"Failed to rollback Helm release {release_name}: {result.stderr}")
                self._send_slack_notification(
                    f"Helm Rollback Failed: {release_name}",
                    f"Failed to rollback Helm release {release_name}: {result.stderr}",
                )
                self._record_remediation(namespace, helm_key, "helm_rollback", "failure")
        except subprocess.TimeoutExpired:
            logger.error(f"Helm rollback timed out for release: {release_name}")
            self._send_slack_notification(
                f"Helm Rollback Timeout: {release_name}", f"Helm rollback timed out for release {release_name}"
            )
            self._record_remediation(namespace, helm_key, "helm_rollback", "timeout")
        except Exception as e:
            logger.error(f"Unexpected error during Helm rollback: {e}")
            self._record_remediation(namespace, helm_key, "helm_rollback", "error")

    def _is_node_failing(self, node):
        """Check if node is in a failed state"""
        if node.status.conditions:
            for condition in node.status.conditions:
                if condition.type == "Ready" and condition.status == "False":
                    return True
        return False

    def _handle_node_failure(self, node):
        """Handle NotReady nodes via cordon (kured reboot trigger removed as unreliable)."""
        node_name = node.metadata.name
        node_key = f"node/{node_name}"
        namespace = "kube-system"
        workload_key = self._workload_key(namespace, "Node", node_name)

        if not self.config["node_cordon_enabled"]:
            logger.info("Node cordon disabled; skipping NotReady handling for %s", node_name)
            return

        can_remediate, reason = self._can_remediate(namespace, workload_key, "node_cordon")
        if not can_remediate:
            logger.warning(f"BRAKE ENGAGED: Cannot cordon node {node_name} - {reason}")
            self._record_brake(namespace, workload_key, "node_cordon", reason or "unknown")
            return

        if self._is_dangerous_action("node_cordon"):
            if not self._check_approval(node_key, "node_cordon"):
                logger.warning(f"APPROVAL REQUIRED: Node cordon for {node_name} requires approval annotation")
                self._send_slack_notification(
                    f"Approval Required: {node_name}",
                    f"Node {node_name} cordon requires annotation: " f"self-healing.justrunme.com/approve-cordon=true",
                    rate_key=f"approval:{node_key}",
                )
                self._record_outcome(namespace, "node_cordon", "approval_required")
                remediation_skips_total.labels(namespace=namespace, reason="approval_required").inc()
                self._emit_event(
                    namespace=namespace,
                    involved_name=node_name,
                    involved_kind="Node",
                    reason="RemediationApprovalRequired",
                    message="Node cordon requires approve-cordon annotation",
                    type_="Warning",
                )
                return

        logger.warning(f"Node failure detected: {node_name}")

        if self.remediation_config.dry_run:
            logger.info(f"DRY RUN: Would cordon node {node_name}")
            self._record_remediation(namespace, workload_key, "node_cordon", "dry_run")
            return

        self._send_slack_notification(f"Node Failure: {node_name}", f"Node {node_name} is NotReady. Cordoning node...")

        success = self._cordon_node(node)
        if success:
            self._consume_approval(node_key, "node_cordon", "self-healing.justrunme.com/approve-cordon")
        result = "success" if success else "failure"
        self._record_remediation(namespace, workload_key, "node_cordon", result)

    def _cordon_node(self, node) -> bool:
        """Cordon a NotReady node so the scheduler stops placing new pods on it."""
        try:
            self.k8s_client.patch_node(
                name=node.metadata.name,
                body={"spec": {"unschedulable": True}},
            )
            logger.info("Cordoned node: %s", node.metadata.name)
            self._emit_event(
                namespace="default",
                involved_name=node.metadata.name,
                involved_kind="Node",
                reason="NodeCordoned",
                message="Node cordoned due to Ready=False",
                type_="Warning",
            )
            return True
        except ApiException as e:
            logger.error(f"Failed to cordon node {node.metadata.name}: {e}")
            return False

    def _send_slack_notification(self, title, message, rate_key: Optional[str] = None):
        """Send notification to Slack (optionally rate-limited per key)."""
        if not self.config["slack_notifications_enabled"] or not self.config["slack_webhook_url"]:
            return

        if rate_key:
            with self._state_lock:
                last = self._slack_last_sent.get(rate_key)
                if last is not None:
                    elapsed = (datetime.now() - last).total_seconds()
                    if elapsed < self.remediation_config.slack_brake_rate_limit_seconds:
                        return
                self._slack_last_sent[rate_key] = datetime.now()

        payload = {
            "channel": self.config["slack_channel"],
            "text": f"*{title}*\n{message}",
            "username": "Self-Healing Controller",
            "icon_emoji": ":robot_face:",
        }

        try:
            response = requests.post(self.config["slack_webhook_url"], json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("Slack notification sent successfully")
            else:
                logger.error(f"Failed to send Slack notification: {response.status_code}")
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")

    def get_metrics(self):
        """Get metrics for monitoring"""
        return {
            "running": self.running,
            "dry_run": self.remediation_config.dry_run,
            "budget_per_namespace": self.remediation_config.budget_per_namespace,
            "budget_per_workload": self.remediation_config.budget_per_workload,
            "cooldown_seconds": self.remediation_config.cooldown_seconds,
            "is_leader": self.is_leader,
        }

    def stop(self):
        """Stop the controller"""
        self.running = False
        self.is_leader = False
        is_leader_gauge.set(0)
        logger.info("Self-Healing Controller stopped")


def main():
    """Main function to start the Self-Healing Controller"""
    controller = SelfHealingController()

    try:
        controller.start_monitoring()

        while controller.running:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
        controller.stop()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        controller.stop()


if __name__ == "__main__":
    main()
