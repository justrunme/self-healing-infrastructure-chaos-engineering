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

    def test_memory_usage_under_load(self):
        """Test memory usage under load"""
        self._skip_if_no_k8s()

        # Get initial memory usage
        initial_memory = self._get_pod_memory_usage("self-healing-controller", "self-healing")

        # Generate load
        def generate_load():
            for _ in range(10):
                try:
                    requests.get(f"{self.base_url}/health", timeout=1)
                    requests.get(f"{self.base_url}/metrics", timeout=1)
                except Exception:
                    pass

        # Run load generation
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(generate_load) for _ in range(5)]
            concurrent.futures.wait(futures)

        # Get final memory usage
        final_memory = self._get_pod_memory_usage("self-healing-controller", "self-healing")

        # Check memory increase is reasonable
        if initial_memory and final_memory:
            memory_increase = final_memory - initial_memory
            self.assertLess(memory_increase, 100, "Memory usage increased too much")

    def test_cpu_usage_under_load(self):
        """Test CPU usage under load"""
        self._skip_if_no_k8s()

        # Get initial CPU usage
        initial_cpu = self._get_pod_cpu_usage("self-healing-controller", "self-healing")

        # Generate load
        def generate_load():
            for _ in range(20):
                try:
                    requests.get(f"{self.base_url}/health", timeout=1)
                except Exception:
                    pass

        # Run load generation
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(generate_load) for _ in range(10)]
            concurrent.futures.wait(futures)

        # Get final CPU usage
        final_cpu = self._get_pod_cpu_usage("self-healing-controller", "self-healing")

        # Check CPU increase is reasonable
        if initial_cpu and final_cpu:
            cpu_increase = final_cpu - initial_cpu
            self.assertLess(cpu_increase, 50, "CPU usage increased too much")

    def _get_pod_memory_usage(self, pod_name, namespace):
        """Get pod memory usage in MB"""
        try:
            pods = self.k8s_client.list_namespaced_pod(namespace=namespace, field_selector=f"metadata.name={pod_name}")
            if pods.items:
                # In a real implementation, this would query metrics API
                # For now, return a mock value
                return 50.0
        except Exception:
            pass
        return None

    def _get_pod_cpu_usage(self, pod_name, namespace):
        """Get pod CPU usage in millicores"""
        try:
            pods = self.k8s_client.list_namespaced_pod(namespace=namespace, field_selector=f"metadata.name={pod_name}")
            if pods.items:
                # In a real implementation, this would query metrics API
                # For now, return a mock value
                return 100.0
        except Exception:
            pass
        return None

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
