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


def _owner_ref(kind, name, controller=True):
    ref = MagicMock()
    ref.kind = kind
    ref.name = name
    ref.controller = controller
    return ref


def _owned_pod(name="test-pod", namespace="test-ns", kind="ReplicaSet", owner="test-rs"):
    pod = MagicMock()
    pod.metadata.name = name
    pod.metadata.namespace = namespace
    pod.metadata.owner_references = [_owner_ref(kind, owner)]
    pod.metadata.labels = {}
    pod.metadata.annotations = {}
    pod.status.phase = "Failed"
    return pod


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
                    with patch("self_healing_controller.client.CoordinationV1Api"):
                        controller = SelfHealingController()
                        controller.config["leader_election_enabled"] = False
                        controller.is_leader = True
                        return controller

    def test_load_config(self, controller):
        """Test configuration loading"""
        config = controller._load_config()

        assert "pod_failure_threshold" in config
        assert "slack_notifications_enabled" in config
        assert "helm_rollback_enabled" in config
        assert config["pod_failure_threshold"] == 3

    def test_load_remediation_config(self, controller):
        """Test remediation configuration loading — safe defaults"""
        config = controller.remediation_config

        assert config.budget_per_namespace == 10
        assert config.budget_per_workload == 3
        assert config.budget_window_seconds == 300
        assert config.cooldown_seconds == 60
        assert config.dry_run is True
        assert config.allowed_namespaces == frozenset()
        assert config.require_approval_for_dangerous is True
        assert config.pod_delete_grace_period_seconds == 30

    def test_load_remediation_config_from_env(self):
        """Test remediation config from environment variables"""
        with patch.dict(
            os.environ,
            {
                "REMEDIATION_BUDGET_PER_NAMESPACE": "5",
                "REMEDIATION_BUDGET_PER_WORKLOAD": "2",
                "REMEDIATION_BUDGET_WINDOW_SECONDS": "600",
                "REMEDIATION_COOLDOWN_SECONDS": "120",
                "DRY_RUN": "false",
                "REMEDIATION_NAMESPACES": "test-app, other-ns",
                "REQUIRE_APPROVAL_FOR_DANGEROUS": "false",
            },
        ):
            with patch("self_healing_controller.config.load_incluster_config"):
                with patch("self_healing_controller.client.CoreV1Api"):
                    with patch("self_healing_controller.client.AppsV1Api"):
                        with patch("self_healing_controller.client.CoordinationV1Api"):
                            controller = SelfHealingController()
                            config = controller.remediation_config

                            assert config.budget_per_namespace == 5
                            assert config.budget_per_workload == 2
                            assert config.budget_window_seconds == 600
                            assert config.cooldown_seconds == 120
                            assert config.dry_run is False
                            assert config.allowed_namespaces == frozenset({"test-app", "other-ns"})
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

    def test_is_pod_failing_not_ready_is_not_terminal(self, controller):
        """Starting pods are Ready=False and must not be treated as failed."""
        pod = MagicMock()
        pod.status.phase = "Running"

        condition = MagicMock()
        condition.type = "Ready"
        condition.status = "False"
        pod.status.conditions = [condition]

        result = controller._is_pod_failing(pod)
        assert result is False

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
        container.state.waiting = None
        pod.status.container_statuses = [container]

        result = controller._is_pod_crash_looping(pod)
        assert result is True

    def test_is_pod_crash_looping_waiting_reason(self, controller):
        """CrashLoopBackOff is a crash loop even before the restart threshold."""
        pod = MagicMock()
        container = MagicMock()
        container.restart_count = 1
        container.state.waiting.reason = "CrashLoopBackOff"
        pod.status.container_statuses = [container]

        result = controller._is_pod_crash_looping(pod)
        assert result is True

    def test_is_pod_crash_looping_false(self, controller):
        """Test crash looping detection when false"""
        pod = MagicMock()
        container = MagicMock()
        container.restart_count = 1
        container.state.waiting = None
        pod.status.container_statuses = [container]

        result = controller._is_pod_crash_looping(pod)
        assert result is False

    def test_is_helm_managed_pod_true(self, controller):
        """Test Helm managed pod detection when true"""
        pod = MagicMock()
        pod.metadata.namespace = "test-ns"
        pod.metadata.labels = {
            "app.kubernetes.io/managed-by": "Helm",
            "app.kubernetes.io/instance": "my-release",
        }
        pod.metadata.annotations = {"meta.helm.sh/release-name": "my-release"}
        controller._helm_release_exists = MagicMock(return_value=True)

        result = controller._is_helm_managed_pod(pod)
        assert result is True
        controller._helm_release_exists.assert_called_once_with("test-ns", "my-release")

    def test_is_helm_managed_pod_rejects_non_helm_managed_by(self, controller):
        """Any managed-by value other than Helm must not trigger rollback."""
        pod = MagicMock()
        pod.metadata.labels = {"app.kubernetes.io/managed-by": "kubectl"}
        pod.metadata.annotations = {"meta.helm.sh/release-name": "my-release"}

        assert controller._is_helm_managed_pod(pod) is False

    def test_is_helm_managed_pod_requires_release_secret(self, controller):
        """Helm label alone is insufficient without a release secret."""
        pod = MagicMock()
        pod.metadata.namespace = "test-ns"
        pod.metadata.labels = {
            "app.kubernetes.io/managed-by": "Helm",
            "app.kubernetes.io/instance": "my-release",
        }
        pod.metadata.annotations = {"meta.helm.sh/release-name": "my-release"}
        controller._helm_release_exists = MagicMock(return_value=False)

        assert controller._is_helm_managed_pod(pod) is False

    def test_is_helm_managed_pod_false(self, controller):
        """Test Helm managed pod detection when false"""
        pod = MagicMock()
        pod.metadata.labels = {"app": "test"}
        pod.metadata.annotations = {}

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
        can_remediate, reason = controller._can_remediate("test-ns", "test-ns/Deployment/app", "restart_pod")
        assert can_remediate is True
        assert reason is None

    def test_can_remediate_budget_exhausted(self, controller):
        """Test remediation blocked when namespace budget exhausted"""
        namespace = "test-ns"
        controller.remediation_config.budget_per_namespace = 2
        controller.namespace_budgets[namespace] = RemediationBudget(2, 300)

        controller._record_remediation(namespace, f"{namespace}/Deployment/a", "restart_pod", "success")
        controller._record_remediation(namespace, f"{namespace}/Deployment/b", "restart_pod", "success")

        can_remediate, reason = controller._can_remediate(namespace, f"{namespace}/Deployment/c", "restart_pod")
        assert can_remediate is False
        assert "budget_exhausted" in reason

    def test_can_remediate_workload_budget_exhausted(self, controller):
        """Test remediation blocked when per-workload budget exhausted"""
        namespace = "test-ns"
        workload = f"{namespace}/Deployment/app"
        controller.remediation_config.budget_per_workload = 1
        controller.workload_budgets[workload] = RemediationBudget(1, 300)

        controller._record_remediation(namespace, workload, "restart_pod", "success")

        can_remediate, reason = controller._can_remediate(namespace, workload, "restart_pod")
        assert can_remediate is False
        assert "workload" in reason

    def test_can_remediate_cooldown_active(self, controller):
        """Test remediation blocked during cooldown"""
        namespace = "test-ns"
        workload = f"{namespace}/Deployment/app"

        controller._record_remediation(namespace, workload, "restart_pod", "success")

        can_remediate, reason = controller._can_remediate(namespace, workload, "restart_pod")
        assert can_remediate is False
        assert "cooldown_active" in reason

    def test_brake_does_not_consume_budget_or_cooldown(self, controller):
        """Reproduce starvation bug: brake events must not burn budget/cooldown.

        Old bug: crash-loop MODIFIED events recorded brake_engaged via
        _record_remediation, permanently resetting cooldown and exhausting the
        namespace budget so other workloads starved.
        """
        namespace = "test-ns"
        crashing = f"{namespace}/Deployment/crash"
        healthy = f"{namespace}/Deployment/healthy"
        controller.remediation_config.budget_per_namespace = 3
        controller.namespace_budgets[namespace] = RemediationBudget(3, 300)
        controller.remediation_config.budget_per_workload = 5
        controller.workload_budgets[crashing] = RemediationBudget(5, 300)
        controller.workload_budgets[healthy] = RemediationBudget(5, 300)

        # One real remediation on the crashing workload starts cooldown
        controller._record_remediation(namespace, crashing, "restart_crash_loop", "success")
        remaining_before = controller.namespace_budgets[namespace].remaining()
        cooldown_before = controller.object_cooldown.last_timestamp(crashing)

        # Simulate 50 brake engagements (old code would burn budget + reset cooldown)
        for _ in range(50):
            controller._record_brake(namespace, crashing, "restart_crash_loop", "cooldown_active")

        assert controller.namespace_budgets[namespace].remaining() == remaining_before
        assert controller.object_cooldown.last_timestamp(crashing) == cooldown_before

        # Another workload in the same namespace must still be remediable
        can_remediate, reason = controller._can_remediate(namespace, healthy, "restart_pod")
        assert can_remediate is True
        assert reason is None

    @patch("self_healing_controller.requests.post")
    def test_brake_rate_limits_slack(self, mock_post, controller):
        """Brake Slack alerts are rate-limited per workload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        controller.config["slack_notifications_enabled"] = True
        controller.config["slack_webhook_url"] = "https://hooks.slack.com/test"
        controller.remediation_config.slack_brake_rate_limit_seconds = 60

        for _ in range(50):
            controller._send_slack_notification("Brake", "msg", rate_key="brake:ns/Deployment/x")

        assert mock_post.call_count == 1

    def test_is_dangerous_action(self, controller):
        """Test dangerous action detection"""
        assert controller._is_dangerous_action("node_cordon") is True
        assert controller._is_dangerous_action("node_drain") is True
        assert controller._is_dangerous_action("restart_pod") is False

    def test_check_approval_with_annotation(self, controller):
        """Test approval check with annotation"""
        node = MagicMock()
        node.metadata.annotations = {"self-healing.justrunme.com/approve-cordon": "true"}

        controller.k8s_client.read_node = MagicMock(return_value=node)

        result = controller._check_approval("node/test-node", "node_cordon")
        assert result is True

    def test_check_approval_without_annotation(self, controller):
        """Test approval check without annotation"""
        node = MagicMock()
        node.metadata.annotations = {}

        controller.k8s_client.read_node = MagicMock(return_value=node)

        result = controller._check_approval("node/test-node", "node_cordon")
        assert result is False

    def test_check_approval_disabled(self, controller):
        """Test approval check when disabled"""
        controller.remediation_config.require_approval_for_dangerous = False

        result = controller._check_approval("node/test-node", "node_cordon")
        assert result is True

    def test_resolve_owner_bare_pod(self, controller):
        """Bare pods have no owner chain."""
        pod = MagicMock()
        pod.metadata.owner_references = []
        assert controller._resolve_owner(pod) is None

    def test_resolve_owner_replicaset_to_deployment(self, controller):
        """ReplicaSet owner is walked up to Deployment."""
        pod = _owned_pod(kind="ReplicaSet", owner="app-rs")
        rs = MagicMock()
        rs.metadata.owner_references = [_owner_ref("Deployment", "app")]
        controller.apps_v1.read_namespaced_replica_set = MagicMock(return_value=rs)

        assert controller._resolve_owner(pod) == ("test-ns", "Deployment", "app")

    def test_handle_pod_failure_skips_bare_pod(self, controller):
        """Bare pods are skipped with event + metric, never deleted."""
        pod = MagicMock()
        pod.metadata.name = "bare-pod"
        pod.metadata.namespace = "test-ns"
        pod.metadata.owner_references = []
        pod.status.phase = "Failed"

        controller._handle_pod_failure(pod)

        controller.k8s_client.delete_namespaced_pod.assert_not_called()
        controller.k8s_client.create_namespaced_event.assert_called()

    def test_restart_pod_uses_grace_period(self, controller):
        """Deletion must use configured grace period (no force-delete)."""
        pod = _owned_pod()
        controller.remediation_config.pod_delete_grace_period_seconds = 30

        assert controller._restart_pod(pod) is True
        controller.k8s_client.delete_namespaced_pod.assert_called_once()
        kwargs = controller.k8s_client.delete_namespaced_pod.call_args.kwargs
        assert kwargs["grace_period_seconds"] == 30
        assert kwargs["grace_period_seconds"] != 0

    def test_handle_pod_failure_dry_run(self, controller):
        """Test pod failure handling in dry run mode"""
        controller.remediation_config.dry_run = True
        pod = _owned_pod()
        rs = MagicMock()
        rs.metadata.owner_references = [_owner_ref("Deployment", "test")]
        controller.apps_v1.read_namespaced_replica_set = MagicMock(return_value=rs)

        controller._handle_pod_failure(pod)

        controller.k8s_client.delete_namespaced_pod.assert_not_called()

    def test_default_dry_run_does_not_delete_unhealthy_pod(self, controller):
        """NEGATIVE: defaults keep dry-run on — unhealthy owned pod is not deleted."""
        assert controller.remediation_config.dry_run is True
        assert controller.remediation_config.allowed_namespaces == frozenset()

        pod = _owned_pod(name="unhealthy-pod", namespace="test-ns")
        rs = MagicMock()
        rs.metadata.owner_references = [_owner_ref("Deployment", "app")]
        controller.apps_v1.read_namespaced_replica_set = MagicMock(return_value=rs)

        with patch("self_healing_controller.remediations_total") as mock_counter:
            controller._handle_pod_failure(pod)

        controller.k8s_client.delete_namespaced_pod.assert_not_called()
        mock_counter.labels.assert_called_with(namespace="test-ns", action="restart_pod", result="dry_run")
        mock_counter.labels.return_value.inc.assert_called()

    def test_live_mode_without_allowlist_refuses_delete(self, controller):
        """NEGATIVE: DRY_RUN=false with empty allowlist must not delete."""
        controller.remediation_config.dry_run = False
        controller.remediation_config.allowed_namespaces = frozenset()

        pod = _owned_pod(name="unhealthy-pod", namespace="test-ns")
        rs = MagicMock()
        rs.metadata.owner_references = [_owner_ref("Deployment", "app")]
        controller.apps_v1.read_namespaced_replica_set = MagicMock(return_value=rs)

        controller._handle_pod_failure(pod)

        controller.k8s_client.delete_namespaced_pod.assert_not_called()

    def test_live_mode_outside_allowlist_does_not_delete(self, controller):
        """NEGATIVE: DRY_RUN=false but pod namespace outside allowlist — not deleted."""
        controller.remediation_config.dry_run = False
        controller.remediation_config.allowed_namespaces = frozenset({"allowed-ns"})

        pod = _owned_pod(name="unhealthy-pod", namespace="other-ns")
        rs = MagicMock()
        rs.metadata.owner_references = [_owner_ref("Deployment", "app")]
        controller.apps_v1.read_namespaced_replica_set = MagicMock(return_value=rs)

        controller._handle_pod_failure(pod)

        controller.k8s_client.delete_namespaced_pod.assert_not_called()

    def test_live_mode_with_allowlist_deletes_owned_pod(self, controller):
        """Live remediation deletes when DRY_RUN=false and namespace is allowlisted."""
        controller.remediation_config.dry_run = False
        controller.remediation_config.allowed_namespaces = frozenset({"test-ns"})

        pod = _owned_pod(name="unhealthy-pod", namespace="test-ns")
        rs = MagicMock()
        rs.metadata.owner_references = [_owner_ref("Deployment", "app")]
        controller.apps_v1.read_namespaced_replica_set = MagicMock(return_value=rs)

        controller._handle_pod_failure(pod)

        controller.k8s_client.delete_namespaced_pod.assert_called_once()

    def test_handle_pod_failure_budget_exhausted(self, controller):
        """Test pod failure handling when budget exhausted"""
        namespace = "test-ns"
        controller.remediation_config.dry_run = False
        controller.remediation_config.allowed_namespaces = frozenset({namespace})
        controller.remediation_config.budget_per_namespace = 1
        controller.namespace_budgets[namespace] = RemediationBudget(1, 300)

        rs = MagicMock()
        rs.metadata.owner_references = [_owner_ref("Deployment", "app1")]
        controller.apps_v1.read_namespaced_replica_set = MagicMock(return_value=rs)

        pod1 = _owned_pod(name="pod1", namespace=namespace, owner="rs1")
        controller._handle_pod_failure(pod1)

        rs.metadata.owner_references = [_owner_ref("Deployment", "app2")]
        pod2 = _owned_pod(name="pod2", namespace=namespace, owner="rs2")
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

        # Must not cordon without approval
        patch_calls = controller.k8s_client.patch_node.call_args_list
        for call in patch_calls:
            body = call.kwargs.get("body") or (call.args[1] if len(call.args) > 1 else None)
            if isinstance(body, dict) and body.get("spec", {}).get("unschedulable") is True:
                pytest.fail("Node was cordoned without approval")

    def test_handle_node_failure_with_approval_cordons(self, controller):
        """Approved NotReady handling cordons the node (no fake kured annotation)."""
        controller.remediation_config.dry_run = False
        controller.remediation_config.allowed_namespaces = frozenset({"kube-system"})
        node = MagicMock()
        node.metadata.name = "test-node"
        node.metadata.annotations = {"self-healing.justrunme.com/approve-cordon": "true"}

        controller.k8s_client.read_node = MagicMock(return_value=node)
        controller._consume_approval = MagicMock(return_value=True)

        controller._handle_node_failure(node)

        controller.k8s_client.patch_node.assert_called()
        body = controller.k8s_client.patch_node.call_args.kwargs.get("body")
        if body is None:
            body = controller.k8s_client.patch_node.call_args[1].get("body")
        assert body == {"spec": {"unschedulable": True}}
        # Must not set the obsolete kured node-lock annotation on the Node
        assert "weave.works/kured-node-lock" not in str(body)

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
        assert metrics["dry_run"] is True
        assert "allowed_namespaces" in metrics
        assert metrics["allowed_namespaces"] == []
        assert "budget_per_namespace" in metrics
        assert "budget_per_workload" in metrics
        assert "cooldown_seconds" in metrics

    @patch("self_healing_controller.subprocess.run")
    def test_helm_rollback_success(self, mock_run, controller):
        """Test successful Helm rollback"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        controller.remediation_config.dry_run = False
        controller.remediation_config.allowed_namespaces = frozenset({"test-namespace"})
        pod = MagicMock()
        pod.metadata.labels = {
            "app.kubernetes.io/managed-by": "Helm",
            "app.kubernetes.io/instance": "test-release",
        }
        pod.metadata.annotations = {"meta.helm.sh/release-name": "test-release"}
        pod.metadata.namespace = "test-namespace"
        controller._helm_release_exists = MagicMock(return_value=True)
        controller.config["helm_rollback_enabled"] = True

        controller._handle_helm_pod_failure(pod)

        mock_run.assert_called_once_with(
            ["helm", "rollback", "test-release", "--namespace", "test-namespace"],
            capture_output=True,
            text=True,
            timeout=300,
        )

    @patch("self_healing_controller.subprocess.run")
    def test_helm_rollback_skipped_without_release(self, mock_run, controller):
        """Helm rollback must not run when release secret is missing."""
        pod = MagicMock()
        pod.metadata.labels = {
            "app.kubernetes.io/managed-by": "Helm",
            "app.kubernetes.io/instance": "test-release",
        }
        pod.metadata.annotations = {"meta.helm.sh/release-name": "test-release"}
        pod.metadata.namespace = "test-namespace"
        controller._helm_release_exists = MagicMock(return_value=False)
        controller.config["helm_rollback_enabled"] = True

        controller._handle_helm_pod_failure(pod)

        mock_run.assert_not_called()

    @patch("self_healing_controller.subprocess.run")
    def test_helm_rollback_budget_exhausted(self, mock_run, controller):
        """Test Helm rollback blocked by budget"""
        namespace = "test-namespace"
        controller.remediation_config.budget_per_namespace = 1
        controller.namespace_budgets[namespace] = RemediationBudget(1, 300)

        pod = MagicMock()
        pod.metadata.labels = {
            "app.kubernetes.io/managed-by": "Helm",
            "app.kubernetes.io/instance": "test-release",
        }
        pod.metadata.annotations = {"meta.helm.sh/release-name": "test-release"}
        pod.metadata.namespace = namespace
        controller._helm_release_exists = MagicMock(return_value=True)
        controller.config["helm_rollback_enabled"] = True

        controller._record_remediation(namespace, f"{namespace}/Deployment/other", "restart_pod", "success")

        controller._handle_helm_pod_failure(pod)

        mock_run.assert_not_called()

    def test_helm_release_exists_via_secret(self, controller):
        """Helm release detection looks for helm.sh/release.v1 secrets."""
        secret = MagicMock()
        secret.type = "helm.sh/release.v1"
        secret.metadata.name = "sh.helm.release.v1.demo.v1"
        result = MagicMock()
        result.items = [secret]
        controller.k8s_client.list_namespaced_secret = MagicMock(return_value=result)

        assert controller._helm_release_exists("demo-ns", "demo") is True


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
                with patch("self_healing_controller.client.CoordinationV1Api"):
                    controller = SelfHealingController()
                    assert controller is not None
                    assert hasattr(controller, "config")
                    assert hasattr(controller, "remediation_config")
                    assert hasattr(controller, "k8s_client")
                    assert hasattr(controller, "namespace_budgets")
                    assert hasattr(controller, "workload_budgets")
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
                        with patch("self_healing_controller.client.CoordinationV1Api"):
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
                    with patch("self_healing_controller.client.CoordinationV1Api"):
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
