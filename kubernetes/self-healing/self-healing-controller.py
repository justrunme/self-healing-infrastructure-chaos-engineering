#!/usr/bin/env python3
"""
Self-Healing Infrastructure Controller

This controller monitors Kubernetes cluster for failures and automatically
responds by restarting pods, scaling applications, and performing rollbacks.
"""

import os
import time
import logging
import json
import requests
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
import yaml
import subprocess
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SelfHealingController:
    def __init__(self):
        """Initialize the Self-Healing Controller"""
        self.config = self._load_config()
        self.k8s_client = self._init_kubernetes_client()
        self.pod_failures = {}
        self.node_failures = {}
        self.helm_releases = {}
        
    def _load_config(self):
        """Load configuration from environment variables"""
        return {
            'pod_failure_threshold': int(os.getenv('POD_FAILURE_THRESHOLD', 3)),
            'pod_restart_timeout': int(os.getenv('POD_RESTART_TIMEOUT', 300)),
            'node_failure_threshold': int(os.getenv('NODE_FAILURE_THRESHOLD', 2)),
            'node_unreachable_timeout': int(os.getenv('NODE_UNREACHABLE_TIMEOUT', 600)),
            'helm_rollback_enabled': os.getenv('HELM_ROLLBACK_ENABLED', 'true').lower() == 'true',
            'helm_rollback_timeout': int(os.getenv('HELM_ROLLBACK_TIMEOUT', 300)),
            'kured_integration_enabled': os.getenv('KURED_INTEGRATION_ENABLED', 'true').lower() == 'true',
            'slack_notifications_enabled': os.getenv('SLACK_NOTIFICATIONS_ENABLED', 'true').lower() == 'true',
            'slack_webhook_url': os.getenv('SLACK_WEBHOOK_URL', ''),
            'slack_channel': os.getenv('SLACK_CHANNEL', '#alerts'),
            'prometheus_enabled': os.getenv('PROMETHEUS_ENABLED', 'true').lower() == 'true',
            'prometheus_url': os.getenv('PROMETHEUS_URL', 'http://prometheus-service.monitoring.svc.cluster.local:9090'),
            'chaos_engineering_enabled': os.getenv('CHAOS_ENGINEERING_ENABLED', 'true').lower() == 'true',
            'chaos_mesh_url': os.getenv('CHAOS_MESH_URL', 'http://chaos-mesh-controller-manager.chaos-engineering.svc.cluster.local:10080')
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
        
        # Start monitoring threads
        self._monitor_pods()
        self._monitor_nodes()
        self._monitor_helm_releases()
    
    def _monitor_pods(self):
        """Monitor pods for failures"""
        logger.info("Starting pod monitoring...")
        
        w = watch.Watch()
        for event in w.stream(self.k8s_client.list_pod_for_all_namespaces):
            pod = event['object']
            event_type = event['type']
            
            if event_type in ['MODIFIED', 'DELETED']:
                self._handle_pod_event(pod, event_type)
    
    def _handle_pod_event(self, pod, event_type):
        """Handle pod events and detect failures"""
        pod_name = pod.metadata.name
        namespace = pod.metadata.namespace
        
        # Skip system pods
        if namespace in ['kube-system', 'monitoring', 'chaos-engineering']:
            return
        
        # Check for pod failures
        if self._is_pod_failing(pod):
            self._handle_pod_failure(pod)
        elif self._is_pod_crash_looping(pod):
            self._handle_crash_looping_pod(pod)
    
    def _is_pod_failing(self, pod):
        """Check if pod is in a failed state"""
        if pod.status.phase in ['Failed', 'Unknown']:
            return True
        
        if pod.status.conditions:
            for condition in pod.status.conditions:
                if condition.type == 'Ready' and condition.status == 'False':
                    return True
        
        return False
    
    def _is_pod_crash_looping(self, pod):
        """Check if pod is crash looping"""
        if pod.status.container_statuses:
            for container in pod.status.container_statuses:
                if container.restart_count > self.config['pod_failure_threshold']:
                    return True
        return False
    
    def _handle_pod_failure(self, pod):
        """Handle pod failure by attempting recovery"""
        pod_name = pod.metadata.name
        namespace = pod.metadata.namespace
        
        logger.warning(f"Pod failure detected: {namespace}/{pod_name}")
        
        # Send notification
        self._send_slack_notification(
            f"🚨 Pod Failure: {pod_name}",
            f"Pod {pod_name} in namespace {namespace} has failed. Attempting recovery..."
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
        
        logger.warning(f"Crash looping pod detected: {namespace}/{pod_name}")
        
        # Send notification
        self._send_slack_notification(
            f"🔄 Crash Looping Pod: {pod_name}",
            f"Pod {pod_name} in namespace {namespace} is crash looping. Attempting recovery..."
        )
        
        # Attempt pod restart
        self._restart_pod(pod)
    
    def _restart_pod(self, pod):
        """Restart a pod by deleting it"""
        try:
            self.k8s_client.delete_namespaced_pod(
                name=pod.metadata.name,
                namespace=pod.metadata.namespace
            )
            logger.info(f"Restarted pod: {pod.metadata.namespace}/{pod.metadata.name}")
        except ApiException as e:
            logger.error(f"Failed to restart pod {pod.metadata.name}: {e}")
    
    def _is_helm_managed_pod(self, pod):
        """Check if pod is managed by Helm"""
        if pod.metadata.labels:
            return 'app.kubernetes.io/managed-by' in pod.metadata.labels
        return False
    
    def _handle_helm_pod_failure(self, pod):
        """Handle failure of Helm-managed pod"""
        if not self.config['helm_rollback_enabled']:
            return
        
        # Extract Helm release name from pod labels
        release_name = pod.metadata.labels.get('app.kubernetes.io/instance')
        if not release_name:
            return
        
        logger.info(f"Attempting Helm rollback for release: {release_name}")
        
        # Perform Helm rollback
        try:
            result = subprocess.run([
                'helm', 'rollback', release_name, '--namespace', pod.metadata.namespace
            ], capture_output=True, text=True, timeout=self.config['helm_rollback_timeout'])
            
            if result.returncode == 0:
                logger.info(f"Successfully rolled back Helm release: {release_name}")
                self._send_slack_notification(
                    f"✅ Helm Rollback: {release_name}",
                    f"Successfully rolled back Helm release {release_name} in namespace {pod.metadata.namespace}"
                )
            else:
                logger.error(f"Failed to rollback Helm release {release_name}: {result.stderr}")
                self._send_slack_notification(
                    f"❌ Helm Rollback Failed: {release_name}",
                    f"Failed to rollback Helm release {release_name}: {result.stderr}"
                )
        except subprocess.TimeoutExpired:
            logger.error(f"Helm rollback timeout for release: {release_name}")
        except Exception as e:
            logger.error(f"Error during Helm rollback: {e}")
    
    def _monitor_nodes(self):
        """Monitor nodes for failures"""
        logger.info("Starting node monitoring...")
        
        w = watch.Watch()
        for event in w.stream(self.k8s_client.list_node):
            node = event['object']
            event_type = event['type']
            
            if event_type in ['MODIFIED', 'DELETED']:
                self._handle_node_event(node, event_type)
    
    def _handle_node_event(self, node, event_type):
        """Handle node events and detect failures"""
        node_name = node.metadata.name
        
        # Check for node failures
        if self._is_node_failing(node):
            self._handle_node_failure(node)
    
    def _is_node_failing(self, node):
        """Check if node is in a failed state"""
        if node.status.conditions:
            for condition in node.status.conditions:
                if condition.type == 'Ready' and condition.status == 'False':
                    return True
                if condition.type in ['DiskPressure', 'MemoryPressure'] and condition.status == 'True':
                    return True
        return False
    
    def _handle_node_failure(self, node):
        """Handle node failure"""
        node_name = node.metadata.name
        
        logger.warning(f"Node failure detected: {node_name}")
        
        # Send notification
        self._send_slack_notification(
            f"🚨 Node Failure: {node_name}",
            f"Node {node_name} has failed. Initiating recovery procedures..."
        )
        
        # If Kured integration is enabled, trigger node reboot
        if self.config['kured_integration_enabled']:
            self._trigger_node_reboot(node)
    
    def _trigger_node_reboot(self, node):
        """Trigger node reboot using Kured"""
        node_name = node.metadata.name
        
        try:
            # Create a file on the node to trigger reboot
            # This is a simplified approach - in production you'd use Kured's API
            logger.info(f"Triggering reboot for node: {node_name}")
            
            # Send notification
            self._send_slack_notification(
                f"🔄 Node Reboot: {node_name}",
                f"Triggering reboot for node {node_name} via Kured integration"
            )
            
        except Exception as e:
            logger.error(f"Failed to trigger node reboot: {e}")
    
    def _monitor_helm_releases(self):
        """Monitor Helm releases for failures"""
        logger.info("Starting Helm release monitoring...")
        
        # This would typically involve monitoring Helm release status
        # For now, we'll implement a basic check
        pass
    
    def _send_slack_notification(self, title, message):
        """Send notification to Slack"""
        if not self.config['slack_notifications_enabled'] or not self.config['slack_webhook_url']:
            return
        
        try:
            payload = {
                "channel": self.config['slack_channel'],
                "text": f"{title}\n{message}",
                "username": "Self-Healing Controller",
                "icon_emoji": ":robot_face:"
            }
            
            response = requests.post(
                self.config['slack_webhook_url'],
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("Slack notification sent successfully")
            else:
                logger.error(f"Failed to send Slack notification: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
    
    def get_metrics(self):
        """Get metrics for Prometheus"""
        return {
            'pod_failures_total': len(self.pod_failures),
            'node_failures_total': len(self.node_failures),
            'helm_rollbacks_total': len([f for f in self.pod_failures.values() if f.get('helm_rollback')]),
            'slack_notifications_sent': 0  # This would be tracked in production
        }

def main():
    """Main function"""
    controller = SelfHealingController()
    
    try:
        controller.start_monitoring()
    except KeyboardInterrupt:
        logger.info("Self-Healing Controller stopped by user")
    except Exception as e:
        logger.error(f"Self-Healing Controller error: {e}")
        raise

if __name__ == "__main__":
    main() 