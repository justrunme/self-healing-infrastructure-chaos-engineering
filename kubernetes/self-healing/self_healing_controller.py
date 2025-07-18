#!/usr/bin/env python3
"""
Self-Healing Infrastructure Controller

This controller monitors Kubernetes cluster for failures and automatically
responds by restarting pods, scaling applications, and performing rollbacks.
"""

import logging
import os
import subprocess
import time
import threading

import requests

from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class SelfHealingController:
    def __init__(self):
        """Initialize the Self-Healing Controller"""
        self.config = self._load_config()
        self.k8s_client = self._init_kubernetes_client()
        self.pod_failures = {}
        self.node_failures = {}
        self.helm_releases = {}
        self.running = True
        self.last_check = {}

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
            "chaos_engineering_enabled": os.getenv("CHAOS_ENGINEERING_ENABLED", "true").lower() == "true",
            "chaos_mesh_url": os.getenv(
                "CHAOS_MESH_URL", "http://chaos-mesh-controller-manager.chaos-engineering.svc.cluster.local:10080"
            ),
            "check_interval": int(os.getenv("CHECK_INTERVAL", 30)),  # Check every 30 seconds
        }

    def _init_kubernetes_client(self):
        """Initialize Kubernetes client"""
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()

        return client.CoreV1Api()

    def start_monitoring(self):
        """Start monitoring the cluster for failures"""
        logger.info("Starting Self-Healing Controller monitoring...")
        logger.info(f"Configuration: {self.config}")

        # Start monitoring threads
        self._start_pod_monitoring()
        self._start_node_monitoring()
        self._start_health_server()

    def _start_pod_monitoring(self):
        """Start pod monitoring in a separate thread"""
        def monitor_pods():
            while self.running:
                try:
                    self._check_pods()
                    time.sleep(self.config["check_interval"])
                except Exception as e:
                    logger.error(f"Error in pod monitoring: {e}")
                    time.sleep(10)

        thread = threading.Thread(target=monitor_pods, daemon=True)
        thread.start()
        logger.info("Pod monitoring started")

    def _start_node_monitoring(self):
        """Start node monitoring in a separate thread"""
        def monitor_nodes():
            while self.running:
                try:
                    self._check_nodes()
                    time.sleep(self.config["check_interval"] * 2)  # Check nodes less frequently
                except Exception as e:
                    logger.error(f"Error in node monitoring: {e}")
                    time.sleep(20)

        thread = threading.Thread(target=monitor_nodes, daemon=True)
        thread.start()
        logger.info("Node monitoring started")

    def _start_health_server(self):
        """Start health check server"""
        from flask import Flask, jsonify
        import threading

        app = Flask(__name__)

        @app.route('/health')
        def health():
            return jsonify({"status": "healthy", "running": self.running})

        @app.route('/ready')
        def ready():
            return jsonify({"status": "ready", "running": self.running})

        @app.route('/metrics')
        def metrics():
            return jsonify(self.get_metrics())

        def run_server():
            app.run(host='0.0.0.0', port=8080)

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        logger.info("Health server started on port 8080")

    def _check_pods(self):
        """Check all pods for failures"""
        try:
            pods = self.k8s_client.list_pod_for_all_namespaces()
            
            for pod in pods.items:
                # Skip system pods and self-healing controller pods
                if self._should_skip_pod(pod):
                    continue

                # Check for pod failures
                if self._is_pod_failing(pod):
                    self._handle_pod_failure(pod)
                elif self._is_pod_crash_looping(pod):
                    self._handle_crash_looping_pod(pod)

        except Exception as e:
            logger.error(f"Error checking pods: {e}")

    def _should_skip_pod(self, pod):
        """Check if pod should be skipped"""
        namespace = pod.metadata.namespace
        pod_name = pod.metadata.name

        # Skip system namespaces
        if namespace in ["kube-system", "monitoring", "chaos-engineering", "self-healing"]:
            return True

        # Skip self-healing controller pods
        if pod_name.startswith("self-healing-controller-"):
            return True

        # Skip pods that are being terminated
        if pod.metadata.deletion_timestamp:
            return True

        return False

    def _is_pod_failing(self, pod):
        """Check if pod is in a failed state"""
        if pod.status.phase in ["Failed", "Unknown"]:
            return True

        if pod.status.conditions:
            for condition in pod.status.conditions:
                if condition.type == "Ready" and condition.status == "False":
                    return True

        return False

    def _is_pod_crash_looping(self, pod):
        """Check if pod is crash looping"""
        if pod.status.container_statuses:
            for container in pod.status.container_statuses:
                if container.restart_count > self.config["pod_failure_threshold"]:
                    return True
        return False

    def _handle_pod_failure(self, pod):
        """Handle pod failure by attempting recovery"""
        pod_name = pod.metadata.name
        namespace = pod.metadata.namespace
        pod_key = f"{namespace}/{pod_name}"

        # Check if we've already handled this pod recently
        current_time = time.time()
        if pod_key in self.last_check:
            if current_time - self.last_check[pod_key] < 60:  # Wait 60 seconds between checks
                return

        self.last_check[pod_key] = current_time

        logger.warning(f"Pod failure detected: {pod_key}")

        # Send notification
        self._send_slack_notification(
            f"🚨 Pod Failure: {pod_name}", f"Pod {pod_name} in namespace {namespace} has failed. Attempting recovery..."
        )

        # Attempt pod restart
        self._restart_pod(pod)

        # Check if this is a Helm-managed pod
        if self._is_helm_managed_pod(pod):
            self._handle_helm_pod_failure(pod)

    def _handle_crash_looping_pod(self, pod):
        """Handle crash looping pod"""
        pod_name = pod.metadata.name
        namespace = pod.metadata.namespace
        pod_key = f"{namespace}/{pod_name}"

        # Check if we've already handled this pod recently
        current_time = time.time()
        if pod_key in self.last_check:
            if current_time - self.last_check[pod_key] < 60:  # Wait 60 seconds between checks
                return

        self.last_check[pod_key] = current_time

        logger.warning(f"Crash looping pod detected: {pod_key}")

        # Send notification
        self._send_slack_notification(
            f"🔄 Crash Looping Pod: {pod_name}",
            f"Pod {pod_name} in namespace {namespace} is crash looping. Attempting recovery...",
        )

        # Attempt pod restart
        self._restart_pod(pod)

    def _restart_pod(self, pod):
        """Restart a pod by deleting it"""
        try:
            self.k8s_client.delete_namespaced_pod(
                name=pod.metadata.name, 
                namespace=pod.metadata.namespace,
                grace_period_seconds=0  # Force delete immediately
            )
            logger.info(f"Restarted pod: {pod.metadata.namespace}/{pod.metadata.name}")
        except ApiException as e:
            if e.status == 404:
                logger.info(f"Pod {pod.metadata.name} already deleted")
            else:
                logger.error(f"Failed to restart pod {pod.metadata.name}: {e}")

    def _is_helm_managed_pod(self, pod):
        """Check if pod is managed by Helm"""
        if pod.metadata.labels:
            return "app.kubernetes.io/managed-by" in pod.metadata.labels
        return False

    def _handle_helm_pod_failure(self, pod):
        """Handle failure of Helm-managed pod"""
        if not self.config["helm_rollback_enabled"]:
            return

        # Extract Helm release name from pod labels
        release_name = pod.metadata.labels.get("app.kubernetes.io/instance")
        if not release_name:
            return

        logger.info(f"Attempting Helm rollback for release: {release_name}")

        # Perform Helm rollback
        try:
            result = subprocess.run(
                ["helm", "rollback", release_name, "--namespace", pod.metadata.namespace],
                capture_output=True,
                text=True,
                timeout=self.config["helm_rollback_timeout"],
            )

            if result.returncode == 0:
                logger.info(f"Successfully rolled back Helm release: {release_name}")
                self._send_slack_notification(
                    f"✅ Helm Rollback: {release_name}",
                    f"Successfully rolled back Helm release {release_name} in namespace {pod.metadata.namespace}",
                )
            else:
                logger.error(f"Failed to rollback Helm release {release_name}: {result.stderr}")
                self._send_slack_notification(
                    f"❌ Helm Rollback Failed: {release_name}",
                    f"Failed to rollback Helm release {release_name}: {result.stderr}",
                )
        except subprocess.TimeoutExpired:
            logger.error(f"Helm rollback timed out for release: {release_name}")
            self._send_slack_notification(
                f"⏰ Helm Rollback Timeout: {release_name}", f"Helm rollback timed out for release {release_name}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during Helm rollback: {e}")

    def _check_nodes(self):
        """Check all nodes for failures"""
        try:
            nodes = self.k8s_client.list_node()
            
            for node in nodes.items:
                if self._is_node_failing(node):
                    self._handle_node_failure(node)

        except Exception as e:
            logger.error(f"Error checking nodes: {e}")

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

        # Check if we've already handled this node recently
        current_time = time.time()
        if node_key in self.last_check:
            if current_time - self.last_check[node_key] < 300:  # Wait 5 minutes between checks
                return

        self.last_check[node_key] = current_time

        logger.warning(f"Node failure detected: {node_name}")

        # Send notification
        self._send_slack_notification(
            f"🚨 Node Failure: {node_name}", f"Node {node_name} has failed. Triggering reboot..."
        )

        # Trigger node reboot via Kured
        if self.config["kured_integration_enabled"]:
            self._trigger_node_reboot(node)

    def _trigger_node_reboot(self, node):
        """Trigger node reboot using Kured"""
        try:
            # Annotate node to trigger Kured reboot
            self.k8s_client.patch_node(
                name=node.metadata.name, 
                body={"metadata": {"annotations": {"weave.works/kured-node-lock": ""}}}
            )
            logger.info(f"Triggered reboot for node: {node.metadata.name}")
        except ApiException as e:
            logger.error(f"Failed to trigger reboot for node {node.metadata.name}: {e}")

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
            "pod_failures": len(self.pod_failures),
            "node_failures": len(self.node_failures),
            "helm_rollbacks": len(self.helm_releases),
            "running": self.running,
            "last_checks": len(self.last_check),
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
        
        # Keep the main thread alive
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
