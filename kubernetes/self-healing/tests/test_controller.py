#!/usr/bin/env python3
"""
Unit tests for Self-Healing Controller
"""

import pytest
import unittest.mock as mock
from unittest.mock import MagicMock, patch
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from self_healing_controller import SelfHealingController


class TestSelfHealingController:
    """Test cases for Self-Healing Controller"""

    @pytest.fixture
    def controller(self):
        """Create a test controller instance"""
        with patch('self_healing_controller.config.load_incluster_config'):
            with patch('self_healing_controller.client.CoreV1Api'):
                controller = SelfHealingController()
                return controller

    def test_load_config(self, controller):
        """Test configuration loading"""
        config = controller._load_config()
        
        assert 'pod_failure_threshold' in config
        assert 'slack_notifications_enabled' in config
        assert 'helm_rollback_enabled' in config
        assert config['pod_failure_threshold'] == 3
        assert config['slack_notifications_enabled'] is True

    def test_is_pod_failing_failed_state(self, controller):
        """Test pod failure detection for failed state"""
        pod = MagicMock()
        pod.status.phase = 'Failed'
        
        result = controller._is_pod_failing(pod)
        assert result is True

    def test_is_pod_failing_unknown_state(self, controller):
        """Test pod failure detection for unknown state"""
        pod = MagicMock()
        pod.status.phase = 'Unknown'
        
        result = controller._is_pod_failing(pod)
        assert result is True

    def test_is_pod_failing_not_ready(self, controller):
        """Test pod failure detection for not ready condition"""
        pod = MagicMock()
        pod.status.phase = 'Running'
        
        condition = MagicMock()
        condition.type = 'Ready'
        condition.status = 'False'
        pod.status.conditions = [condition]
        
        result = controller._is_pod_failing(pod)
        assert result is True

    def test_is_pod_failing_healthy(self, controller):
        """Test pod failure detection for healthy pod"""
        pod = MagicMock()
        pod.status.phase = 'Running'
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
        pod.metadata.labels = {'app.kubernetes.io/managed-by': 'Helm'}
        
        result = controller._is_helm_managed_pod(pod)
        assert result is True

    def test_is_helm_managed_pod_false(self, controller):
        """Test Helm managed pod detection when false"""
        pod = MagicMock()
        pod.metadata.labels = {'app': 'test'}
        
        result = controller._is_helm_managed_pod(pod)
        assert result is False

    def test_is_node_failing_ready_false(self, controller):
        """Test node failure detection for not ready"""
        node = MagicMock()
        condition = MagicMock()
        condition.type = 'Ready'
        condition.status = 'False'
        node.status.conditions = [condition]
        
        result = controller._is_node_failing(node)
        assert result is True

    def test_is_node_failing_disk_pressure(self, controller):
        """Test node failure detection for disk pressure"""
        node = MagicMock()
        condition = MagicMock()
        condition.type = 'DiskPressure'
        condition.status = 'True'
        node.status.conditions = [condition]
        
        result = controller._is_node_failing(node)
        assert result is True

    def test_is_node_failing_memory_pressure(self, controller):
        """Test node failure detection for memory pressure"""
        node = MagicMock()
        condition = MagicMock()
        condition.type = 'MemoryPressure'
        condition.status = 'True'
        node.status.conditions = [condition]
        
        result = controller._is_node_failing(node)
        assert result is True

    def test_is_node_failing_healthy(self, controller):
        """Test node failure detection for healthy node"""
        node = MagicMock()
        condition = MagicMock()
        condition.type = 'Ready'
        condition.status = 'True'
        node.status.conditions = [condition]
        
        result = controller._is_node_failing(node)
        assert result is False

    @patch('self_healing_controller.requests.post')
    def test_send_slack_notification_success(self, mock_post, controller):
        """Test successful Slack notification"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        controller.config['slack_notifications_enabled'] = True
        controller.config['slack_webhook_url'] = 'https://hooks.slack.com/test'
        
        controller._send_slack_notification('Test Title', 'Test Message')
        
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]['json']['text'] == 'Test Title\nTest Message'

    @patch('self_healing_controller.requests.post')
    def test_send_slack_notification_disabled(self, mock_post, controller):
        """Test Slack notification when disabled"""
        controller.config['slack_notifications_enabled'] = False
        
        controller._send_slack_notification('Test Title', 'Test Message')
        
        mock_post.assert_not_called()

    @patch('self_healing_controller.requests.post')
    def test_send_slack_notification_no_webhook(self, mock_post, controller):
        """Test Slack notification when no webhook URL"""
        controller.config['slack_notifications_enabled'] = True
        controller.config['slack_webhook_url'] = ''
        
        controller._send_slack_notification('Test Title', 'Test Message')
        
        mock_post.assert_not_called()

    def test_get_metrics(self, controller):
        """Test metrics collection"""
        controller.pod_failures = {'pod1': {}, 'pod2': {}}
        controller.node_failures = {'node1': {}}
        
        metrics = controller.get_metrics()
        
        assert metrics['pod_failures_total'] == 2
        assert metrics['node_failures_total'] == 1
        assert 'helm_rollbacks_total' in metrics
        assert 'slack_notifications_sent' in metrics

    @patch('self_healing_controller.subprocess.run')
    def test_helm_rollback_success(self, mock_run, controller):
        """Test successful Helm rollback"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        controller.config['helm_rollback_enabled'] = True
        
        pod = MagicMock()
        pod.metadata.labels = {'app.kubernetes.io/instance': 'test-release'}
        pod.metadata.namespace = 'test-namespace'
        
        with patch.object(controller, '_send_slack_notification') as mock_notify:
            controller._handle_helm_pod_failure(pod)
            
            mock_run.assert_called_once()
            mock_notify.assert_called()

    @patch('self_healing_controller.subprocess.run')
    def test_helm_rollback_failure(self, mock_run, controller):
        """Test failed Helm rollback"""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = 'Rollback failed'
        mock_run.return_value = mock_result
        
        controller.config['helm_rollback_enabled'] = True
        
        pod = MagicMock()
        pod.metadata.labels = {'app.kubernetes.io/instance': 'test-release'}
        pod.metadata.namespace = 'test-namespace'
        
        with patch.object(controller, '_send_slack_notification') as mock_notify:
            controller._handle_helm_pod_failure(pod)
            
            mock_run.assert_called_once()
            mock_notify.assert_called()

    def test_helm_rollback_disabled(self, controller):
        """Test Helm rollback when disabled"""
        controller.config['helm_rollback_enabled'] = False
        
        pod = MagicMock()
        
        with patch.object(controller, '_send_slack_notification') as mock_notify:
            controller._handle_helm_pod_failure(pod)
            
            mock_notify.assert_not_called()

    def test_helm_rollback_no_release_name(self, controller):
        """Test Helm rollback when no release name"""
        controller.config['helm_rollback_enabled'] = True
        
        pod = MagicMock()
        pod.metadata.labels = {}
        
        with patch.object(controller, '_send_slack_notification') as mock_notify:
            controller._handle_helm_pod_failure(pod)
            
            mock_notify.assert_not_called()


class TestControllerIntegration:
    """Integration tests for Self-Healing Controller"""

    @pytest.fixture
    def mock_k8s_client(self):
        """Mock Kubernetes client"""
        with patch('self_healing_controller.client.CoreV1Api') as mock_client:
            yield mock_client

    def test_controller_initialization(self, mock_k8s_client):
        """Test controller initialization"""
        with patch('self_healing_controller.config.load_incluster_config'):
            controller = SelfHealingController()
            
            assert controller.k8s_client is not None
            assert hasattr(controller, 'pod_failures')
            assert hasattr(controller, 'node_failures')
            assert hasattr(controller, 'helm_releases')

    def test_config_environment_variables(self):
        """Test configuration with environment variables"""
        with patch.dict(os.environ, {
            'POD_FAILURE_THRESHOLD': '5',
            'SLACK_NOTIFICATIONS_ENABLED': 'false',
            'HELM_ROLLBACK_ENABLED': 'false'
        }):
            with patch('self_healing_controller.config.load_incluster_config'):
                with patch('self_healing_controller.client.CoreV1Api'):
                    controller = SelfHealingController()
                    config = controller._load_config()
                    
                    assert config['pod_failure_threshold'] == 5
                    assert config['slack_notifications_enabled'] is False
                    assert config['helm_rollback_enabled'] is False


if __name__ == '__main__':
    pytest.main([__file__]) 