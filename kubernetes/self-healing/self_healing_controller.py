#!/usr/bin/env python3
"""
Self-Healing Infrastructure Controller with Bounded Remediation

This controller monitors Kubernetes cluster for failures and automatically
responds with bounded remediation: budget limits, cooldowns, dry-run mode,
and approval gates for dangerous operations.
"""

import logging
import os
import subprocess
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, Set

import requests
from flask import Flask, Response, jsonify
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    generate_latest,
)

from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Prometheus metrics
remediations_total = Counter(
    "remediations_total",
    "Total number of remediation actions",
    ["namespace", "action", "result"],
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


@dataclass
class RemediationConfig:
    """Configuration for bounded remediation"""

    budget_per_namespace: int
    budget_window_seconds: int
    cooldown_seconds: int
    dry_run: bool
    require_approval_for_dangerous: bool


class RemediationBudget:
    """Tracks remediation budget per namespace within a sliding window"""

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
    """Tracks per-object cooldown periods"""

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


class SelfHealingController:
    def __init__(self):
        """Initialize the Self-Healing Controller"""
        self.config = self._load_config()
        self.remediation_config = self._load_remediation_config()
        self.k8s_client = self._init_kubernetes_client()
        self.apps_v1 = client.AppsV1Api()
        self.running = True

        self.namespace_budgets: Dict[str, RemediationBudget] = defaultdict(
            lambda: RemediationBudget(
                self.remediation_config.budget_per_namespace,
                self.remediation_config.budget_window_seconds,
            )
        )
        self.object_cooldown = ObjectCooldown(self.remediation_config.cooldown_seconds)

        self.approved_dangerous_actions: Set[str] = set()

    def _load_config(self):
        """Load configuration from environment variables"""
        return {
            "pod_failure_threshold": int(os.getenv("POD_FAILURE_THRESHOLD", 3)),
            "pod_restart_timeout": int(os.getenv("POD_RESTART_TIMEOUT", 300)),
            "node_failure_threshold": int(os.getenv("NODE_FAILURE_THRESHOLD", 2)),
            "node_unreachable_timeout": int(os.getenv("NODE_UNREACHABLE_TIMEOUT", 600)),
            "helm_rollback_enabled": os.getenv("HELM_ROLLBACK_ENABLED", "true").lower() == "true",
            "helm_rollback_timeout": int(os.getenv("HELM_ROLLBACK_TIMEOUT", 300)),
            "kured_integration_enabled": os.getenv("KURED_INTEGRATION_ENABLED", "true").lower() == "true",
            "slack_notifications_enabled": os.getenv("SLACK_NOTIFICATIONS_ENABLED", "false").lower() == "true",
            "slack_webhook_url": os.getenv("SLACK_WEBHOOK_URL", ""),
            "slack_channel": os.getenv("SLACK_CHANNEL", "#alerts"),
            "prometheus_enabled": os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true",
            "prometheus_url": os.getenv(
                "PROMETHEUS_URL", "http://prometheus-service.monitoring.svc.cluster.local:9090"
            ),
        }

    def _load_remediation_config(self) -> RemediationConfig:
        """Load remediation brake configuration"""
        return RemediationConfig(
            budget_per_namespace=int(os.getenv("REMEDIATION_BUDGET_PER_NAMESPACE", 10)),
            budget_window_seconds=int(os.getenv("REMEDIATION_BUDGET_WINDOW_SECONDS", 300)),
            cooldown_seconds=int(os.getenv("REMEDIATION_COOLDOWN_SECONDS", 60)),
            dry_run=os.getenv("DRY_RUN", "false").lower() == "true",
            require_approval_for_dangerous=os.getenv("REQUIRE_APPROVAL_FOR_DANGEROUS", "true").lower() == "true",
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
            logger.warning("🚨 DRY RUN MODE ENABLED - No actual remediation will be performed")

        self._start_pod_watch()
        self._start_node_watch()
        self._start_health_server()

    def _start_pod_watch(self):
        """Start watching pods using Kubernetes watch API"""

        def watch_pods():
            resource_version = None
            while self.running:
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

                        event_type = event["type"]
                        pod = event["object"]
                        resource_version = pod.metadata.resource_version

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

        thread = threading.Thread(target=watch_pods, daemon=True)
        thread.start()
        logger.info("Pod watch started")

    def _start_node_watch(self):
        """Start watching nodes using Kubernetes watch API"""

        def watch_nodes():
            resource_version = None
            while self.running:
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

                        event_type = event["type"]
                        node = event["object"]
                        resource_version = node.metadata.resource_version

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

        thread = threading.Thread(target=watch_nodes, daemon=True)
        thread.start()
        logger.info("Node watch started")

    def _start_health_server(self):
        """Start health check server with Prometheus metrics"""
        app = Flask(__name__)

        @app.route("/health")
        def health():
            return jsonify({"status": "healthy", "running": self.running})

        @app.route("/ready")
        def ready():
            return jsonify({"status": "ready", "running": self.running})

        @app.route("/metrics")
        def metrics():
            return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

        def run_server():
            app.run(host="0.0.0.0", port=8080)

        thread = threading.Thread(target=run_server, daemon=True)
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

    def _can_remediate(self, namespace: str, obj_key: str, action: str) -> tuple[bool, Optional[str]]:
        """Check if remediation is allowed (budget + cooldown)"""
        budget = self.namespace_budgets[namespace]
        if not budget.can_remediate():
            reason = f"budget_exhausted:namespace={namespace}"
            brake_engaged.labels(namespace=namespace, reason="budget_exhausted").set(1)
            remediation_budget_remaining.labels(namespace=namespace).set(0)
            return False, reason

        if not self.object_cooldown.can_remediate(obj_key):
            reason = f"cooldown_active:object={obj_key}"
            brake_engaged.labels(namespace=namespace, reason="cooldown_active").set(1)
            return False, reason

        brake_engaged.labels(namespace=namespace, reason="none").set(0)
        remediation_budget_remaining.labels(namespace=namespace).set(budget.remaining())
        return True, None

    def _record_remediation(self, namespace: str, obj_key: str, action: str, result: str):
        """Record a remediation action"""
        self.namespace_budgets[namespace].record_remediation()
        self.object_cooldown.record_remediation(obj_key)
        remediations_total.labels(namespace=namespace, action=action, result=result).inc()
        remediation_budget_remaining.labels(namespace=namespace).set(self.namespace_budgets[namespace].remaining())

    def _is_dangerous_action(self, action: str) -> bool:
        """Check if action requires approval"""
        return action in ["node_reboot", "node_drain"]

    def _check_approval(self, obj_key: str, action: str) -> bool:
        """Check if dangerous action has been approved"""
        if not self.remediation_config.require_approval_for_dangerous:
            return True

        approval_key = f"{obj_key}:{action}"
        if approval_key in self.approved_dangerous_actions:
            return True

        try:
            if action == "node_reboot":
                node = self.k8s_client.read_node(obj_key.split("/")[1])
                annotations = node.metadata.annotations or {}
                if annotations.get("self-healing.justrunme.com/approve-reboot") == "true":
                    self.approved_dangerous_actions.add(approval_key)
                    return True
            elif action == "node_drain":
                node = self.k8s_client.read_node(obj_key.split("/")[1])
                annotations = node.metadata.annotations or {}
                if annotations.get("self-healing.justrunme.com/approve-drain") == "true":
                    self.approved_dangerous_actions.add(approval_key)
                    return True
        except Exception as e:
            logger.error(f"Error checking approval for {obj_key}: {e}")
            return False

        return False

    def _handle_pod_failure(self, pod):
        """Handle pod failure by attempting recovery"""
        pod_name = pod.metadata.name
        namespace = pod.metadata.namespace
        pod_key = f"{namespace}/{pod_name}"

        can_remediate, reason = self._can_remediate(namespace, pod_key, "restart_pod")
        if not can_remediate:
            logger.warning(f"🛑 BRAKE ENGAGED: Cannot remediate {pod_key} - {reason}")
            self._send_slack_notification(
                f"🛑 Brake Engaged: {pod_name}",
                f"Cannot remediate pod {pod_name} in {namespace}: {reason}",
            )
            self._record_remediation(namespace, pod_key, "restart_pod", "brake_engaged")
            return

        logger.warning(f"Pod failure detected: {pod_key}")

        if self.remediation_config.dry_run:
            logger.info(f"🔍 DRY RUN: Would restart pod {pod_key}")
            self._send_slack_notification(
                f"🔍 DRY RUN: Pod Failure: {pod_name}",
                f"Would restart pod {pod_name} in namespace {namespace}",
            )
            self._record_remediation(namespace, pod_key, "restart_pod", "dry_run")
            return

        self._send_slack_notification(
            f"🚨 Pod Failure: {pod_name}", f"Pod {pod_name} in namespace {namespace} has failed. Attempting recovery..."
        )

        success = self._restart_pod(pod)
        result = "success" if success else "failure"
        self._record_remediation(namespace, pod_key, "restart_pod", result)

        if self._is_helm_managed_pod(pod):
            self._handle_helm_pod_failure(pod)

    def _handle_crash_looping_pod(self, pod):
        """Handle crash looping pod"""
        pod_name = pod.metadata.name
        namespace = pod.metadata.namespace
        pod_key = f"{namespace}/{pod_name}"

        can_remediate, reason = self._can_remediate(namespace, pod_key, "restart_crash_loop")
        if not can_remediate:
            logger.warning(f"🛑 BRAKE ENGAGED: Cannot remediate crash loop {pod_key} - {reason}")
            self._record_remediation(namespace, pod_key, "restart_crash_loop", "brake_engaged")
            return

        logger.warning(f"Crash looping pod detected: {pod_key}")

        if self.remediation_config.dry_run:
            logger.info(f"🔍 DRY RUN: Would restart crash looping pod {pod_key}")
            self._record_remediation(namespace, pod_key, "restart_crash_loop", "dry_run")
            return

        self._send_slack_notification(
            f"🔄 Crash Looping Pod: {pod_name}",
            f"Pod {pod_name} in namespace {namespace} is crash looping. Attempting recovery...",
        )

        success = self._restart_pod(pod)
        result = "success" if success else "failure"
        self._record_remediation(namespace, pod_key, "restart_crash_loop", result)

    def _restart_pod(self, pod) -> bool:
        """Restart a pod by deleting it"""
        try:
            self.k8s_client.delete_namespaced_pod(
                name=pod.metadata.name,
                namespace=pod.metadata.namespace,
                grace_period_seconds=0,
            )
            logger.info(f"Restarted pod: {pod.metadata.namespace}/{pod.metadata.name}")
            return True
        except ApiException as e:
            if e.status == 404:
                logger.info(f"Pod {pod.metadata.name} already deleted")
                return True
            else:
                logger.error(f"Failed to restart pod {pod.metadata.name}: {e}")
                return False

    def _is_helm_managed_pod(self, pod):
        """Check if pod is managed by Helm"""
        if pod.metadata.labels:
            return "app.kubernetes.io/managed-by" in pod.metadata.labels
        return False

    def _handle_helm_pod_failure(self, pod):
        """Handle failure of Helm-managed pod"""
        if not self.config["helm_rollback_enabled"]:
            return

        release_name = pod.metadata.labels.get("app.kubernetes.io/instance")
        if not release_name:
            return

        namespace = pod.metadata.namespace
        helm_key = f"{namespace}/helm-{release_name}"

        can_remediate, reason = self._can_remediate(namespace, helm_key, "helm_rollback")
        if not can_remediate:
            logger.warning(f"🛑 BRAKE ENGAGED: Cannot rollback {release_name} - {reason}")
            self._record_remediation(namespace, helm_key, "helm_rollback", "brake_engaged")
            return

        logger.info(f"Attempting Helm rollback for release: {release_name}")

        if self.remediation_config.dry_run:
            logger.info(f"🔍 DRY RUN: Would rollback Helm release {release_name}")
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
                    f"✅ Helm Rollback: {release_name}",
                    f"Successfully rolled back Helm release {release_name} in namespace {namespace}",
                )
                self._record_remediation(namespace, helm_key, "helm_rollback", "success")
            else:
                logger.error(f"Failed to rollback Helm release {release_name}: {result.stderr}")
                self._send_slack_notification(
                    f"❌ Helm Rollback Failed: {release_name}",
                    f"Failed to rollback Helm release {release_name}: {result.stderr}",
                )
                self._record_remediation(namespace, helm_key, "helm_rollback", "failure")
        except subprocess.TimeoutExpired:
            logger.error(f"Helm rollback timed out for release: {release_name}")
            self._send_slack_notification(
                f"⏰ Helm Rollback Timeout: {release_name}", f"Helm rollback timed out for release {release_name}"
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
        """Handle node failure by triggering reboot"""
        node_name = node.metadata.name
        node_key = f"node/{node_name}"

        can_remediate, reason = self._can_remediate("kube-system", node_key, "node_reboot")
        if not can_remediate:
            logger.warning(f"🛑 BRAKE ENGAGED: Cannot reboot node {node_name} - {reason}")
            self._record_remediation("kube-system", node_key, "node_reboot", "brake_engaged")
            return

        if self._is_dangerous_action("node_reboot"):
            if not self._check_approval(node_key, "node_reboot"):
                logger.warning(f"⚠️ APPROVAL REQUIRED: Node reboot for {node_name} requires approval annotation")
                self._send_slack_notification(
                    f"⚠️ Approval Required: {node_name}",
                    f"Node {node_name} reboot requires annotation: self-healing.justrunme.com/approve-reboot=true",
                )
                self._record_remediation("kube-system", node_key, "node_reboot", "approval_required")
                return

        logger.warning(f"Node failure detected: {node_name}")

        if self.remediation_config.dry_run:
            logger.info(f"🔍 DRY RUN: Would trigger reboot for node {node_name}")
            self._record_remediation("kube-system", node_key, "node_reboot", "dry_run")
            return

        self._send_slack_notification(
            f"🚨 Node Failure: {node_name}", f"Node {node_name} has failed. Triggering reboot..."
        )

        if self.config["kured_integration_enabled"]:
            success = self._trigger_node_reboot(node)
            result = "success" if success else "failure"
            self._record_remediation("kube-system", node_key, "node_reboot", result)

    def _trigger_node_reboot(self, node) -> bool:
        """Trigger node reboot using Kured"""
        try:
            self.k8s_client.patch_node(
                name=node.metadata.name, body={"metadata": {"annotations": {"weave.works/kured-node-lock": ""}}}
            )
            logger.info(f"Triggered reboot for node: {node.metadata.name}")
            return True
        except ApiException as e:
            logger.error(f"Failed to trigger reboot for node {node.metadata.name}: {e}")
            return False

    def _send_slack_notification(self, title, message):
        """Send notification to Slack"""
        if not self.config["slack_notifications_enabled"] or not self.config["slack_webhook_url"]:
            return

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
            "cooldown_seconds": self.remediation_config.cooldown_seconds,
        }

    def stop(self):
        """Stop the controller"""
        self.running = False
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
