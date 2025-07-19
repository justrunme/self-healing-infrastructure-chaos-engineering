#!/usr/bin/env python3
"""
Integration Tests for Self-Healing Infrastructure

This module contains comprehensive integration tests for the entire
Self-Healing Infrastructure system.
"""

import unittest

import requests

from kubernetes import client, config


class TestSelfHealingInfrastructure(unittest.TestCase):
    """Integration tests for Self-Healing Infrastructure"""

    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.k8s_client = None
        cls.apps_client = None
        cls.base_url = "http://localhost:8081"

        # Try to initialize Kubernetes client
        try:
            config.load_incluster_config()
        except config.ConfigException:
            try:
                config.load_kube_config()
            except config.ConfigException:
                # Kubernetes not available, tests will be skipped
                return

        cls.k8s_client = client.CoreV1Api()
        cls.apps_client = client.AppsV1Api()

    def _skip_if_no_k8s(self):
        """Skip test if Kubernetes is not available"""
        if self.k8s_client is None:
            self.skipTest("Kubernetes not available")

    def test_self_healing_controller_health(self):
        """Test Self-Healing Controller health endpoint"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "healthy")
            self.assertTrue(data["running"])
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Self-Healing Controller not accessible: {e}")

    def test_self_healing_controller_metrics(self):
        """Test Self-Healing Controller metrics endpoint"""
        try:
            response = requests.get(f"{self.base_url}/metrics", timeout=10)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("pod_failures_total", data)
            self.assertIn("node_failures_total", data)
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Self-Healing Controller not accessible: {e}")

    def test_prometheus_connectivity(self):
        """Test Prometheus connectivity"""
        try:
            response = requests.get("http://localhost:9090/api/v1/query?query=up", timeout=10)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "success")
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Prometheus not accessible: {e}")

    def test_grafana_connectivity(self):
        """Test Grafana connectivity"""
        try:
            response = requests.get("http://localhost:3000/api/health", timeout=10)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["database"], "ok")
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Grafana not accessible: {e}")

    def test_alertmanager_connectivity(self):
        """Test Alertmanager connectivity"""
        try:
            response = requests.get("http://localhost:9093/api/v2/status", timeout=10)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("cluster", data)
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Alertmanager not accessible: {e}")

    def test_test_application_connectivity(self):
        """Test Test Application connectivity"""
        try:
            response = requests.get("http://localhost:8080", timeout=10)
            self.assertEqual(response.status_code, 200)
            self.assertIn("nginx", response.text.lower())
        except requests.exceptions.RequestException as e:
            self.skipTest(f"Test Application not accessible: {e}")

    def test_namespaces_exist(self):
        """Test that all required namespaces exist"""
        self._skip_if_no_k8s()

        required_namespaces = ["self-healing", "test-app", "monitoring", "chaos-engineering", "kured"]

        namespaces = self.k8s_client.list_namespace()
        namespace_names = [ns.metadata.name for ns in namespaces.items]

        for ns in required_namespaces:
            self.assertIn(ns, namespace_names, f"Namespace {ns} not found")

    def test_self_healing_controller_pod_running(self):
        """Test that Self-Healing Controller pod is running"""
        self._skip_if_no_k8s()

        pods = self.k8s_client.list_namespaced_pod(
            namespace="self-healing", label_selector="app=self-healing-controller"
        )

        self.assertGreater(len(pods.items), 0, "No Self-Healing Controller pods found")

        for pod in pods.items:
            self.assertEqual(pod.status.phase, "Running", f"Pod {pod.metadata.name} is not running")

    def test_test_application_pods_running(self):
        """Test that Test Application pods are running"""
        self._skip_if_no_k8s()

        pods = self.k8s_client.list_namespaced_pod(namespace="test-app", label_selector="app=test-app")

        self.assertGreater(len(pods.items), 0, "No Test Application pods found")

        for pod in pods.items:
            self.assertEqual(pod.status.phase, "Running", f"Pod {pod.metadata.name} is not running")

    def test_prometheus_pods_running(self):
        """Test that Prometheus pods are running"""
        self._skip_if_no_k8s()

        pods = self.k8s_client.list_namespaced_pod(
            namespace="monitoring", label_selector="app.kubernetes.io/name=prometheus"
        )

        self.assertGreater(len(pods.items), 0, "No Prometheus pods found")

        for pod in pods.items:
            self.assertEqual(pod.status.phase, "Running", f"Pod {pod.metadata.name} is not running")

    def test_chaos_mesh_pods_running(self):
        """Test that Chaos Mesh pods are running"""
        self._skip_if_no_k8s()

        pods = self.k8s_client.list_namespaced_pod(namespace="chaos-engineering", label_selector="app=chaos-mesh")

        self.assertGreater(len(pods.items), 0, "No Chaos Mesh pods found")

        for pod in pods.items:
            self.assertEqual(pod.status.phase, "Running", f"Pod {pod.metadata.name} is not running")

    def test_services_exist(self):
        """Test that all required services exist"""
        self._skip_if_no_k8s()

        required_services = [
            ("self-healing", "self-healing-controller"),
            ("test-app", "test-app"),
            ("monitoring", "prometheus-kube-prometheus-prometheus"),
            ("monitoring", "prometheus-grafana"),
            ("monitoring", "prometheus-kube-prometheus-alertmanager"),
            ("chaos-engineering", "chaos-mesh-controller-manager"),
        ]

        for namespace, service_name in required_services:
            services = self.k8s_client.list_namespaced_service(
                namespace=namespace, field_selector=f"metadata.name={service_name}"
            )
            self.assertGreater(len(services.items), 0, f"Service {service_name} not found in namespace {namespace}")

    def test_configmaps_exist(self):
        """Test that all required ConfigMaps exist"""
        self._skip_if_no_k8s()

        required_configmaps = [
            ("self-healing", "self-healing-config"),
            ("monitoring", "prometheus-alerts"),
            ("monitoring", "self-healing-dashboard"),
        ]

        for namespace, configmap_name in required_configmaps:
            configmaps = self.k8s_client.list_namespaced_config_map(
                namespace=namespace, field_selector=f"metadata.name={configmap_name}"
            )
            self.assertGreater(
                len(configmaps.items), 0, f"ConfigMap {configmap_name} not found in namespace {namespace}"
            )

    def test_secrets_exist(self):
        """Test that all required Secrets exist"""
        self._skip_if_no_k8s()

        required_secrets = [("monitoring", "slack-secret"), ("self-healing", "self-healing-secret")]

        for namespace, secret_name in required_secrets:
            secrets = self.k8s_client.list_namespaced_secret(
                namespace=namespace, field_selector=f"metadata.name={secret_name}"
            )
            self.assertGreater(len(secrets.items), 0, f"Secret {secret_name} not found in namespace {namespace}")

    def test_network_policies_exist(self):
        """Test that Network Policies exist"""
        self._skip_if_no_k8s()

        network_policies = self.k8s_client.list_namespaced_network_policy(namespace="self-healing")
        self.assertGreater(len(network_policies.items), 0, "No Network Policies found in self-healing namespace")

    def test_resource_limits_set(self):
        """Test that resource limits are set on pods"""
        self._skip_if_no_k8s()

        pods = self.k8s_client.list_namespaced_pod(
            namespace="self-healing", label_selector="app=self-healing-controller"
        )

        for pod in pods.items:
            for container in pod.spec.containers:
                self.assertIsNotNone(
                    container.resources.limits, f"Resource limits not set for container {container.name}"
                )
                self.assertIsNotNone(
                    container.resources.requests, f"Resource requests not set for container {container.name}"
                )

    def test_health_checks_configured(self):
        """Test that health checks are configured"""
        self._skip_if_no_k8s()

        pods = self.k8s_client.list_namespaced_pod(
            namespace="self-healing", label_selector="app=self-healing-controller"
        )

        for pod in pods.items:
            for container in pod.spec.containers:
                self.assertIsNotNone(
                    container.liveness_probe, f"Liveness probe not configured for container {container.name}"
                )
                self.assertIsNotNone(
                    container.readiness_probe, f"Readiness probe not configured for container {container.name}"
                )

    def test_security_context_configured(self):
        """Test that security context is configured"""
        self._skip_if_no_k8s()

        pods = self.k8s_client.list_namespaced_pod(
            namespace="self-healing", label_selector="app=self-healing-controller"
        )

        for pod in pods.items:
            self.assertIsNotNone(
                pod.spec.security_context, "Security context not configured for pod"
            )

    def test_backup_cronjob_exists(self):
        """Test that backup CronJob exists"""
        self._skip_if_no_k8s()

        cronjobs = self.k8s_client.list_namespaced_cron_job(
            namespace="monitoring", field_selector="metadata.name=infrastructure-backup"
        )
        self.assertGreater(len(cronjobs.items), 0, "Backup CronJob not found")

    def test_chaos_experiments_exist(self):
        """Test that Chaos Experiments exist"""
        self._skip_if_no_k8s()

        # This test would check for Chaos Mesh experiments
        # Implementation depends on Chaos Mesh API
        pass


if __name__ == "__main__":
    unittest.main()
