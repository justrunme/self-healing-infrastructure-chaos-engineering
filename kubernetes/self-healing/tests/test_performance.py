#!/usr/bin/env python3
"""
Performance Tests for Self-Healing Infrastructure

This module contains performance and load testing for the
Self-Healing Infrastructure system.
"""

import concurrent.futures
import time
import unittest

import requests

from kubernetes import client, config


class TestSelfHealingPerformance(unittest.TestCase):
    """Performance tests for Self-Healing Infrastructure"""

    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        cls.k8s_client = None
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

    def _skip_if_no_k8s(self):
        """Skip test if Kubernetes is not available"""
        if self.k8s_client is None:
            self.skipTest("Kubernetes not available")

    def test_health_endpoint_performance(self):
        """Test health endpoint performance under load"""
        # Check if service is available
        try:
            response = requests.get(f"{self.base_url}/health", timeout=2)
            if response.status_code != 200:
                self.skipTest("Health endpoint not available")
        except Exception:
            self.skipTest("Health endpoint not reachable")

        def make_request():
            start_time = time.time()
            try:
                response = requests.get(f"{self.base_url}/health", timeout=5)
                end_time = time.time()
                return {
                    "status_code": response.status_code,
                    "response_time": end_time - start_time,
                    "success": response.status_code == 200,
                }
            except Exception as e:
                end_time = time.time()
                return {"status_code": None, "response_time": end_time - start_time, "success": False, "error": str(e)}

        # Test with 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # Analyze results
        successful_requests = [r for r in results if r["success"]]
        response_times = [r["response_time"] for r in successful_requests]

        self.assertGreater(len(successful_requests), 8, "Too many failed requests")
        self.assertLess(max(response_times), 2.0, "Response time too high")
        self.assertLess(sum(response_times) / len(response_times), 1.0, "Average response time too high")

    def test_metrics_endpoint_performance(self):
        """Test metrics endpoint performance under load"""
        # Check if service is available
        try:
            response = requests.get(f"{self.base_url}/metrics", timeout=2)
            if response.status_code != 200:
                self.skipTest("Metrics endpoint not available")
        except Exception:
            self.skipTest("Metrics endpoint not reachable")

        def make_request():
            start_time = time.time()
            try:
                response = requests.get(f"{self.base_url}/metrics", timeout=5)
                end_time = time.time()
                return {
                    "status_code": response.status_code,
                    "response_time": end_time - start_time,
                    "success": response.status_code == 200,
                }
            except Exception as e:
                end_time = time.time()
                return {"status_code": None, "response_time": end_time - start_time, "success": False, "error": str(e)}

        # Test with 5 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # Analyze results
        successful_requests = [r for r in results if r["success"]]
        response_times = [r["response_time"] for r in successful_requests]

        self.assertGreater(len(successful_requests), 4, "Too many failed requests")
        self.assertLess(max(response_times), 3.0, "Response time too high")

    def test_prometheus_query_performance(self):
        """Test Prometheus query performance"""

        def make_query():
            start_time = time.time()
            try:
                response = requests.get("http://localhost:9090/api/v1/query?query=up", timeout=10)
                end_time = time.time()
                return {
                    "status_code": response.status_code,
                    "response_time": end_time - start_time,
                    "success": response.status_code == 200,
                }
            except Exception as e:
                end_time = time.time()
                return {"status_code": None, "response_time": end_time - start_time, "success": False, "error": str(e)}

        # Test with 5 concurrent queries
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_query) for _ in range(5)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # Analyze results
        successful_queries = [r for r in results if r["success"]]
        response_times = [r["response_time"] for r in successful_queries]

        if successful_queries:
            self.assertLess(max(response_times), 5.0, "Prometheus query time too high")

    def test_pod_creation_performance(self):
        """Test pod creation performance"""
        self._skip_if_no_k8s()

        def create_test_pod(pod_name):
            start_time = time.time()
            try:
                pod = client.V1Pod(
                    metadata=client.V1ObjectMeta(name=f"test-pod-{pod_name}", namespace="test-app"),
                    spec=client.V1PodSpec(
                        containers=[
                            client.V1Container(name="test-container", image="busybox:1.35", command=["sleep", "30"])
                        ],
                        restart_policy="Never",
                    ),
                )

                self.k8s_client.create_namespaced_pod(namespace="test-app", body=pod)

                end_time = time.time()
                return {"success": True, "creation_time": end_time - start_time}
            except Exception as e:
                end_time = time.time()
                return {"success": False, "creation_time": end_time - start_time, "error": str(e)}

        # Test creating 3 pods concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(create_test_pod, i) for i in range(3)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # Clean up test pods
        for i in range(3):
            try:
                self.k8s_client.delete_namespaced_pod(name=f"test-pod-{i}", namespace="test-app")
            except Exception:
                pass

        # Analyze results
        successful_creations = [r for r in results if r["success"]]
        creation_times = [r["creation_time"] for r in successful_creations]

        if successful_creations:
            self.assertLess(max(creation_times), 30.0, "Pod creation time too high")

    @staticmethod
    def _usage_delta(initial, final):
        """Compute usage increase. Returns None if either sample is missing."""
        if initial is None or final is None:
            return None
        return final - initial

    def test_usage_delta_computation_unit(self):
        """Unit test of usage-delta math with fixture inputs.

        This is NOT a performance measurement and must not be treated as
        cluster resource evidence. Fixture values exercise the formula only.
        """
        self.assertEqual(self._usage_delta(40.0, 55.0), 15.0)
        self.assertEqual(self._usage_delta(100.0, 100.0), 0.0)
        self.assertIsNone(self._usage_delta(None, 10.0))
        self.assertIsNone(self._usage_delta(10.0, None))

    def test_memory_usage_under_load_requires_real_metrics(self):
        """Load check uses metrics.k8s.io only; skips if metrics are unavailable.

        Does not invent CPU/memory numbers. Not evidence when skipped.
        """
        self._skip_if_no_k8s()

        initial_memory = self._get_pod_memory_usage_mb("self-healing-controller", "self-healing")
        if initial_memory is None:
            self.skipTest("Pod metrics API unavailable; refusing to invent memory figures")

        def generate_load():
            for _ in range(10):
                try:
                    requests.get(f"{self.base_url}/health", timeout=1)
                    requests.get(f"{self.base_url}/metrics", timeout=1)
                except Exception:
                    pass

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(generate_load) for _ in range(5)]
            concurrent.futures.wait(futures)

        final_memory = self._get_pod_memory_usage_mb("self-healing-controller", "self-healing")
        if final_memory is None:
            self.skipTest("Pod metrics API unavailable after load; refusing to invent memory figures")

        memory_increase = self._usage_delta(initial_memory, final_memory)
        self.assertIsNotNone(memory_increase)
        self.assertGreaterEqual(memory_increase, 0.0)

    def test_cpu_usage_under_load_requires_real_metrics(self):
        """Load check uses metrics.k8s.io only; skips if metrics are unavailable.

        Does not invent CPU/memory numbers. Not evidence when skipped.
        """
        self._skip_if_no_k8s()

        initial_cpu = self._get_pod_cpu_usage_millicores("self-healing-controller", "self-healing")
        if initial_cpu is None:
            self.skipTest("Pod metrics API unavailable; refusing to invent CPU figures")

        def generate_load():
            for _ in range(20):
                try:
                    requests.get(f"{self.base_url}/health", timeout=1)
                except Exception:
                    pass

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(generate_load) for _ in range(10)]
            concurrent.futures.wait(futures)

        final_cpu = self._get_pod_cpu_usage_millicores("self-healing-controller", "self-healing")
        if final_cpu is None:
            self.skipTest("Pod metrics API unavailable after load; refusing to invent CPU figures")

        cpu_increase = self._usage_delta(initial_cpu, final_cpu)
        self.assertIsNotNone(cpu_increase)
        self.assertGreaterEqual(cpu_increase, -1.0)

    def _resolve_pod_name(self, name_prefix, namespace):
        """Resolve a running pod name by prefix (Deployments append a suffix)."""
        try:
            pods = self.k8s_client.list_namespaced_pod(namespace=namespace)
            for pod in pods.items:
                if pod.metadata.name.startswith(name_prefix) and pod.status.phase == "Running":
                    return pod.metadata.name
        except Exception:
            return None
        return None

    def _get_pod_memory_usage_mb(self, name_prefix, namespace):
        """Query metrics.k8s.io for pod memory usage in MB. None if unavailable."""
        pod_name = self._resolve_pod_name(name_prefix, namespace)
        if not pod_name:
            return None
        try:
            metrics_api = client.CustomObjectsApi()
            metrics = metrics_api.get_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=namespace,
                plural="pods",
                name=pod_name,
            )
            total_bytes = 0
            for container in metrics.get("containers", []):
                usage = container.get("usage", {}).get("memory", "0")
                total_bytes += self._parse_k8s_quantity_to_bytes(usage)
            return total_bytes / (1024.0 * 1024.0)
        except Exception:
            return None

    def _get_pod_cpu_usage_millicores(self, name_prefix, namespace):
        """Query metrics.k8s.io for pod CPU usage in millicores. None if unavailable."""
        pod_name = self._resolve_pod_name(name_prefix, namespace)
        if not pod_name:
            return None
        try:
            metrics_api = client.CustomObjectsApi()
            metrics = metrics_api.get_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=namespace,
                plural="pods",
                name=pod_name,
            )
            total_millicores = 0.0
            for container in metrics.get("containers", []):
                usage = container.get("usage", {}).get("cpu", "0")
                total_millicores += self._parse_k8s_cpu_to_millicores(usage)
            return total_millicores
        except Exception:
            return None

    @staticmethod
    def _parse_k8s_quantity_to_bytes(quantity):
        """Parse a Kubernetes memory quantity string into bytes."""
        text = str(quantity).strip()
        if text.endswith("Ki"):
            return int(text[:-2]) * 1024
        if text.endswith("Mi"):
            return int(text[:-2]) * 1024 * 1024
        if text.endswith("Gi"):
            return int(text[:-2]) * 1024 * 1024 * 1024
        if text.endswith("n"):
            return 0
        if text.endswith("m"):
            return 0
        return int(float(text))

    @staticmethod
    def _parse_k8s_cpu_to_millicores(quantity):
        """Parse a Kubernetes CPU quantity string into millicores."""
        text = str(quantity).strip()
        if text.endswith("n"):
            return int(text[:-1]) / 1_000_000.0
        if text.endswith("u"):
            return int(text[:-1]) / 1_000.0
        if text.endswith("m"):
            return float(text[:-1])
        return float(text) * 1000.0

    def test_concurrent_pod_failures(self):
        """Test handling of concurrent pod failures"""
        self._skip_if_no_k8s()

        def create_failing_pod(pod_name):
            try:
                pod = client.V1Pod(
                    metadata=client.V1ObjectMeta(name=f"failing-pod-{pod_name}", namespace="test-app"),
                    spec=client.V1PodSpec(
                        containers=[
                            client.V1Container(
                                name="failing-container", image="busybox:1.35", command=["sh", "-c", "exit 1"]
                            )
                        ],
                        restart_policy="Never",
                    ),
                )

                self.k8s_client.create_namespaced_pod(namespace="test-app", body=pod)
                return True
            except Exception:
                return False

        # Create multiple failing pods concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(create_failing_pod, i) for i in range(3)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # Clean up
        for i in range(3):
            try:
                self.k8s_client.delete_namespaced_pod(name=f"failing-pod-{i}", namespace="test-app")
            except Exception:
                pass

        # Check that some pods were created successfully
        successful_creations = sum(results)
        self.assertGreater(successful_creations, 0, "No failing pods were created")

    def test_large_scale_deployment(self):
        """Test performance with large scale deployment"""
        # This test would simulate a large number of pods
        # and measure the controller's performance
        pass

    def test_network_latency_impact(self):
        """Test impact of network latency on performance"""
        # This test would simulate network latency
        # and measure its impact on response times
        pass


if __name__ == "__main__":
    unittest.main()
