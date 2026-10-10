#!/usr/bin/env python3
"""
Unit tests for Self-Healing Controller with Bounded Remediation
"""

import os
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from self_healing_controller import (
    ObjectCooldown,
    RemediationBudget,
    SelfHealingController,
)


class TestRemediationBudget:
    """Test cases for RemediationBudget"""

    def test_budget_initialization(self):
        """Test budget initialization"""
        budget = RemediationBudget(max_count=10, window_seconds=300)
        assert budget.max_count == 10
        assert budget.window_seconds == 300
        assert budget.can_remediate() is True
        assert budget.remaining() == 10

    def test_budget_tracking(self):
        """Test budget tracking and enforcement"""
        budget = RemediationBudget(max_count=3, window_seconds=300)

        for i in range(3):
            assert budget.can_remediate() is True
            budget.record_remediation()
            assert budget.remaining() == 2 - i

        assert budget.can_remediate() is False
        assert budget.remaining() == 0

    def test_budget_sliding_window(self):
        """Test budget resets after window expires"""
        budget = RemediationBudget(max_count=2, window_seconds=1)

        budget.record_remediation()
        budget.record_remediation()
        assert budget.can_remediate() is False

        time.sleep(1.1)

        assert budget.can_remediate() is True
        assert budget.remaining() == 2


class TestObjectCooldown:
    """Test cases for ObjectCooldown"""

    def test_cooldown_initialization(self):
        """Test cooldown initialization"""
        cooldown = ObjectCooldown(cooldown_seconds=60)
        assert cooldown.cooldown_seconds == 60
        assert cooldown.can_remediate("test-obj") is True

    def test_cooldown_enforcement(self):
        """Test cooldown enforcement"""
        cooldown = ObjectCooldown(cooldown_seconds=2)

        obj_key = "namespace/pod-name"
        assert cooldown.can_remediate(obj_key) is True

        cooldown.record_remediation(obj_key)
        assert cooldown.can_remediate(obj_key) is False

        time.sleep(2.1)
        assert cooldown.can_remediate(obj_key) is True

    def test_cooldown_per_object(self):
        """Test cooldown is per-object"""
        cooldown = ObjectCooldown(cooldown_seconds=60)

        cooldown.record_remediation("obj1")
        assert cooldown.can_remediate("obj1") is False
        assert cooldown.can_remediate("obj2") is True


class TestSelfHealingController:
    """Test cases for Self-Healing Controller"""

    @pytest.fixture
    def controller(self):
        """Create a test controller instance"""
        with patch("self_healing_controller.config.load_incluster_config"):
            with patch("self_healing_controller.client.CoreV1Api"):
                with patch("self_healing_controller.client.AppsV1Api"):
                    controller = SelfHealingController()
                    return controller

    def test_load_config(self, controller):
        """Test configuration loading"""
        config = controller._load_config()

        assert "pod_failure_threshold" in config
        assert "slack_notifications_enabled" in config
        assert "helm_rollback_enabled" in config
        assert config["pod_failure_threshold"] == 3

    def test_load_remediation_config(self, controller):
        """Test remediation configuration loading"""
        config = controller.remediation_config

        assert config.budget_per_namespace == 10
        assert config.budget_window_seconds == 300
        assert config.cooldown_seconds == 60
        assert config.dry_run is False
        assert config.require_approval_for_dangerous is True

    def test_load_remediation_config_from_env(self):
        """Test remediation config from environment variables"""
        with patch.dict(
            os.environ,
            {
                "REMEDIATION_BUDGET_PER_NAMESPACE": "5",
                "REMEDIATION_BUDGET_WINDOW_SECONDS": "600",
                "REMEDIATION_COOLDOWN_SECONDS": "120",
                "DRY_RUN": "true",
                "REQUIRE_APPROVAL_FOR_DANGEROUS": "false",
            },
        ):
            with patch("self_healing_controller.config.load_incluster_config"):
                with patch("self_healing_controller.client.CoreV1Api"):
                    with patch("self_healing_controller.client.AppsV1Api"):
                        controller = SelfHealingController()
                        config = controller.remediation_config

                        assert config.budget_per_namespace == 5
                        assert config.budget_window_seconds == 600
                        assert config.cooldown_seconds == 120
                        assert config.dry_run is True
                        assert config.require_approval_for_dangerous is False

    def test_is_pod_failing_failed_state(self, controller):
        """Test pod failure detection for failed state"""
        pod = MagicMock()
        pod.status.phase = "Failed"

        result = controller._is_pod_failing(pod)
        assert result is True

    def test_is_pod_failing_unknown_state(self, controller):
        """Test pod failure detection for unknown state"""
        pod = MagicMock()
        pod.status.phase = "Unknown"

        result = controller._is_pod_failing(pod)
        assert result is True

    def test_is_pod_failing_not_ready(self, controller):
        """Test pod failure detection for not ready condition"""
        pod = MagicMock()
        pod.status.phase = "Running"

        condition = MagicMock()
        condition.type = "Ready"
        condition.status = "False"
        pod.status.conditions = [condition]

        result = controller._is_pod_failing(pod)
        assert result is True

    def test_is_pod_failing_healthy(self, controller):
        """Test pod failure detection for healthy pod"""
        pod = MagicMock()
        pod.status.phase = "Running"
        pod.status.conditions = []

        result = controller._is_pod_failing(pod)
        assert result is False

    def test_is_pod_crash_looping_true(self, controller):
        """Test crash looping detection when true"""
        pod = MagicMock()
        container = MagicMock()
        container.restart_count = 5
        pod.status.container_statuses = [container]

        result = controller._is_pod_crash_looping(pod)
        assert result is True

    def test_is_pod_crash_looping_false(self, controller):
        """Test crash looping detection when false"""
        pod = MagicMock()
        container = MagicMock()
        container.restart_count = 1
        pod.status.container_statuses = [container]

        result = controller._is_pod_crash_looping(pod)
        assert result is False

    def test_is_helm_managed_pod_true(self, controller):
        """Test Helm managed pod detection when true"""
        pod = MagicMock()
        pod.metadata.labels = {"app.kubernetes.io/managed-by": "Helm"}

        result = controller._is_helm_managed_pod(pod)
        assert result is True

    def test_is_helm_managed_pod_false(self, controller):
        """Test Helm managed pod detection when false"""
        pod = MagicMock()
        pod.metadata.labels = {"app": "test"}

        result = controller._is_helm_managed_pod(pod)
        assert result is False

    def test_is_node_failing_ready_false(self, controller):
        """Test node failure detection for not ready"""
        node = MagicMock()
        condition = MagicMock()
        condition.type = "Ready"
        condition.status = "False"
        node.status.conditions = [condition]

        result = controller._is_node_failing(node)
        assert result is True

    def test_is_node_failing_healthy(self, controller):
        """Test node failure detection for healthy node"""
        node = MagicMock()
        condition = MagicMock()
        condition.type = "Ready"
        condition.status = "True"
        node.status.conditions = [condition]

        result = controller._is_node_failing(node)
        assert result is False

    def test_can_remediate_within_budget(self, controller):
        """Test remediation allowed within budget"""
        can_remediate, reason = controller._can_remediate("test-ns", "test-ns/pod1", "restart_pod")
        assert can_remediate is True
        assert reason is None

    def test_can_remediate_budget_exhausted(self, controller):
        """Test remediation blocked when budget exhausted"""
        namespace = "test-ns"
        controller.remediation_config.budget_per_namespace = 2

        controller._can_remediate(namespace, f"{namespace}/pod1", "restart_pod")
        controller._record_remediation(namespace, f"{namespace}/pod1", "restart_pod", "success")

        controller._can_remediate(namespace, f"{namespace}/pod2", "restart_pod")
        controller._record_remediation(namespace, f"{namespace}/pod2", "restart_pod", "success")

        can_remediate, reason = controller._can_remediate(namespace, f"{namespace}/pod3", "restart_pod")
        assert can_remediate is False
        assert "budget_exhausted" in reason

    def test_can_remediate_cooldown_active(self, controller):
        """Test remediation blocked during cooldown"""
        namespace = "test-ns"
        obj_key = f"{namespace}/pod1"

        controller._can_remediate(namespace, obj_key, "restart_pod")
        controller._record_remediation(namespace, obj_key, "restart_pod", "success")

        can_remediate, reason = controller._can_remediate(namespace, obj_key, "restart_pod")
        assert can_remediate is False
        assert "cooldown_active" in reason

    def test_is_dangerous_action(self, controller):
        """Test dangerous action detection"""
        assert controller._is_dangerous_action("node_reboot") is True
        assert controller._is_dangerous_action("node_drain") is True
        assert controller._is_dangerous_action("restart_pod") is False

    def test_check_approval_with_annotation(self, controller):
        """Test approval check with annotation"""
        node = MagicMock()
        node.metadata.annotations = {"self-healing.justrunme.com/approve-reboot": "true"}

        controller.k8s_client.read_node = MagicMock(return_value=node)

        result = controller._check_approval("node/test-node", "node_reboot")
        assert result is True

    def test_check_approval_without_annotation(self, controller):
        """Test approval check without annotation"""
        node = MagicMock()
        node.metadata.annotations = {}

        controller.k8s_client.read_node = MagicMock(return_value=node)

        result = controller._check_approval("node/test-node", "node_reboot")
        assert result is False

    def test_check_approval_disabled(self, controller):
        """Test approval check when disabled"""
        controller.remediation_config.require_approval_for_dangerous = False

        result = controller._check_approval("node/test-node", "node_reboot")
        assert result is True

    def test_handle_pod_failure_dry_run(self, controller):
        """Test pod failure handling in dry run mode"""
        controller.remediation_config.dry_run = True

        pod = MagicMock()
        pod.metadata.name = "test-pod"
        pod.metadata.namespace = "test-ns"
        pod.status.phase = "Failed"

        controller._handle_pod_failure(pod)

        controller.k8s_client.delete_namespaced_pod.assert_not_called()

    def test_handle_pod_failure_budget_exhausted(self, controller):
        """Test pod failure handling when budget exhausted"""
        namespace = "test-ns"
        controller.remediation_config.budget_per_namespace = 1

        pod1 = MagicMock()
        pod1.metadata.name = "pod1"
        pod1.metadata.namespace = namespace

        pod2 = MagicMock()
        pod2.metadata.name = "pod2"
        pod2.metadata.namespace = namespace

        controller._handle_pod_failure(pod1)

        controller.k8s_client.delete_namespaced_pod.reset_mock()
        controller._handle_pod_failure(pod2)

        controller.k8s_client.delete_namespaced_pod.assert_not_called()

    def test_handle_node_failure_requires_approval(self, controller):
        """Test node failure handling requires approval"""
        node = MagicMock()
        node.metadata.name = "test-node"
        node.metadata.annotations = {}

        controller.k8s_client.read_node = MagicMock(return_value=node)

        controller._handle_node_failure(node)

        controller.k8s_client.patch_node.assert_not_called()

    def test_handle_node_failure_with_approval(self, controller):
        """Test node failure handling with approval"""
        node = MagicMock()
        node.metadata.name = "test-node"
        node.metadata.annotations = {"self-healing.justrunme.com/approve-reboot": "true"}

        controller.k8s_client.read_node = MagicMock(return_value=node)

        controller._handle_node_failure(node)

        controller.k8s_client.patch_node.assert_called_once()

    @patch("self_healing_controller.requests.post")
    def test_send_slack_notification_success(self, mock_post, controller):
        """Test successful Slack notification"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        controller.config["slack_notifications_enabled"] = True
        controller.config["slack_webhook_url"] = "https://hooks.slack.com/test"

        controller._send_slack_notification("Test Title", "Test Message")

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["text"] == "*Test Title*\nTest Message"

    @patch("self_healing_controller.requests.post")
    def test_send_slack_notification_disabled(self, mock_post, controller):
        """Test Slack notification when disabled"""
        controller.config["slack_notifications_enabled"] = False

        controller._send_slack_notification("Test Title", "Test Message")

        mock_post.assert_not_called()

    def test_get_metrics(self, controller):
        """Test metrics collection"""
        metrics = controller.get_metrics()

        assert "running" in metrics
        assert "dry_run" in metrics
        assert "budget_per_namespace" in metrics
        assert "cooldown_seconds" in metrics

    @patch("self_healing_controller.subprocess.run")
    def test_helm_rollback_success(self, mock_run, controller):
        """Test successful Helm rollback"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        pod = MagicMock()
        pod.metadata.labels = {"app.kubernetes.io/instance": "test-release"}
        pod.metadata.namespace = "test-namespace"

        controller.config["helm_rollback_enabled"] = True

        controller._handle_helm_pod_failure(pod)

        mock_run.assert_called_once_with(
            ["helm", "rollback", "test-release", "--namespace", "test-namespace"],
            capture_output=True,
            text=True,
            timeout=300,
        )

    @patch("self_healing_controller.subprocess.run")
    def test_helm_rollback_budget_exhausted(self, mock_run, controller):
        """Test Helm rollback blocked by budget"""
        namespace = "test-namespace"
        controller.remediation_config.budget_per_namespace = 1

        pod = MagicMock()
        pod.metadata.labels = {"app.kubernetes.io/instance": "test-release"}
        pod.metadata.namespace = namespace

        controller.config["helm_rollback_enabled"] = True

        controller._record_remediation(namespace, f"{namespace}/other", "restart_pod", "success")

        controller._handle_helm_pod_failure(pod)

        mock_run.assert_not_called()


class TestControllerIntegration:
    """Integration tests for Self-Healing Controller"""

    @pytest.fixture
    def mock_k8s_client(self):
        """Create a mock Kubernetes client"""
        with patch("self_healing_controller.client.CoreV1Api") as mock_client:
            yield mock_client

    def test_controller_initialization(self, mock_k8s_client):
        """Test controller initialization"""
        with patch("self_healing_controller.config.load_incluster_config"):
            with patch("self_healing_controller.client.AppsV1Api"):
                controller = SelfHealingController()
                assert controller is not None
                assert hasattr(controller, "config")
                assert hasattr(controller, "remediation_config")
                assert hasattr(controller, "k8s_client")
                assert hasattr(controller, "namespace_budgets")
                assert hasattr(controller, "object_cooldown")

    def test_config_environment_variables(self):
        """Test configuration from environment variables"""
        with patch.dict(
            os.environ,
            {
                "POD_FAILURE_THRESHOLD": "5",
                "SLACK_NOTIFICATIONS_ENABLED": "false",
                "REMEDIATION_BUDGET_PER_NAMESPACE": "20",
                "DRY_RUN": "true",
            },
        ):
            with patch("self_healing_controller.config.load_incluster_config"):
                with patch("self_healing_controller.client.CoreV1Api"):
                    with patch("self_healing_controller.client.AppsV1Api"):
                        controller = SelfHealingController()
                        config = controller._load_config()
                        assert config["pod_failure_threshold"] == 5
                        assert config["slack_notifications_enabled"] is False

                        remediation_config = controller.remediation_config
                        assert remediation_config.budget_per_namespace == 20
                        assert remediation_config.dry_run is True


class TestWatchPattern:
    """Test watch pattern and resource version handling"""

    @pytest.fixture
    def controller(self):
        """Create a test controller instance"""
        with patch("self_healing_controller.config.load_incluster_config"):
            with patch("self_healing_controller.client.CoreV1Api"):
                with patch("self_healing_controller.client.AppsV1Api"):
                    controller = SelfHealingController()
                    return controller

    def test_should_skip_pod_system_namespace(self, controller):
        """Test skipping system namespace pods"""
        pod = MagicMock()
        pod.metadata.namespace = "kube-system"
        pod.metadata.name = "test-pod"
        pod.metadata.deletion_timestamp = None

        assert controller._should_skip_pod(pod) is True

    def test_should_skip_pod_self_healing(self, controller):
        """Test skipping self-healing controller pods"""
        pod = MagicMock()
        pod.metadata.namespace = "default"
        pod.metadata.name = "self-healing-controller-12345"
        pod.metadata.deletion_timestamp = None

        assert controller._should_skip_pod(pod) is True

    def test_should_not_skip_regular_pod(self, controller):
        """Test not skipping regular pods"""
        pod = MagicMock()
        pod.metadata.namespace = "default"
        pod.metadata.name = "my-app-12345"
        pod.metadata.deletion_timestamp = None

        assert controller._should_skip_pod(pod) is False
