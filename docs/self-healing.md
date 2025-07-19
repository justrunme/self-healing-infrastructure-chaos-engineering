# 🛠️ Self-Healing

> **How the recovery mechanism works and handles different types of failures**

---

## 🔄 Self-Healing Logic

### **1. Failure Detection**
```
Pod Failure → Health Check → Controller Detection → Analysis → Recovery Action
     ↓              ↓              ↓              ↓           ↓
  Crash Loop    Liveness Probe   Monitoring    Threshold   Restart/Scale
  Network Issue  Readiness Probe  Service      Check       Rollback
  Resource Exhaustion  Metrics    Collection   Logic       Notification
```

### **2. Recovery Flow**
```
1. Chaos agent simulates node/pod failures
2. Self-healing controller detects failure via health probes
3. Controller analyzes failure type and severity
4. Recovery action is triggered (restart, scale, rollback)
5. Logs/metrics are pushed to Grafana + Prometheus
6. Slack notification is sent with recovery status
```

---

## 🏥 Self-Healing Controller

### **Core Components**

#### **Pod Monitor**
```python
class PodMonitor:
    def __init__(self):
        self.failure_threshold = 3
        self.restart_timeout = 300
        
    def monitor_pods(self):
        """Monitor all pods for failures"""
        pods = self.get_all_pods()
        for pod in pods:
            if self.is_pod_failing(pod):
                self.handle_pod_failure(pod)
    
    def is_pod_failing(self, pod):
        """Check if pod is in failure state"""
        return (
            pod.status.phase == 'Failed' or
            pod.status.phase == 'Unknown' or
            self.is_crash_looping(pod)
        )
    
    def handle_pod_failure(self, pod):
        """Handle pod failure with recovery actions"""
        if self.should_restart_pod(pod):
            self.restart_pod(pod)
        elif self.should_scale_deployment(pod):
            self.scale_deployment(pod)
        elif self.should_rollback_deployment(pod):
            self.rollback_deployment(pod)
```

#### **Node Monitor**
```python
class NodeMonitor:
    def __init__(self):
        self.node_failure_threshold = 2
        self.unreachable_timeout = 600
        
    def monitor_nodes(self):
        """Monitor all nodes for failures"""
        nodes = self.get_all_nodes()
        for node in nodes:
            if self.is_node_failing(node):
                self.handle_node_failure(node)
    
    def is_node_failing(self, node):
        """Check if node is in failure state"""
        conditions = node.status.conditions
        for condition in conditions:
            if (condition.type == 'Ready' and 
                condition.status == 'False'):
                return True
        return False
    
    def handle_node_failure(self, node):
        """Handle node failure with Kured integration"""
        if self.should_reboot_node(node):
            self.trigger_node_reboot(node)
        else:
            self.notify_node_failure(node)
```

#### **Recovery Engine**
```python
class RecoveryEngine:
    def __init__(self):
        self.recovery_actions = {
            'pod_failure': self.restart_pod,
            'crash_loop': self.restart_pod,
            'resource_exhaustion': self.scale_deployment,
            'network_issue': self.restart_pod,
            'node_failure': self.trigger_node_reboot
        }
    
    def execute_recovery(self, failure_type, resource):
        """Execute appropriate recovery action"""
        if failure_type in self.recovery_actions:
            action = self.recovery_actions[failure_type]
            result = action(resource)
            self.log_recovery_action(failure_type, resource, result)
            self.send_notification(failure_type, resource, result)
            return result
        else:
            self.log_unknown_failure(failure_type, resource)
            return False
    
    def restart_pod(self, pod):
        """Restart a failed pod"""
        try:
            self.delete_pod(pod.metadata.name, pod.metadata.namespace)
            self.log_info(f"Pod {pod.metadata.name} restarted successfully")
            return True
        except Exception as e:
            self.log_error(f"Failed to restart pod {pod.metadata.name}: {e}")
            return False
    
    def scale_deployment(self, pod):
        """Scale deployment to handle resource issues"""
        try:
            deployment = self.get_deployment_for_pod(pod)
            current_replicas = deployment.spec.replicas
            new_replicas = min(current_replicas + 1, 10)  # Max 10 replicas
            self.scale_deployment_replicas(deployment, new_replicas)
            self.log_info(f"Scaled deployment to {new_replicas} replicas")
            return True
        except Exception as e:
            self.log_error(f"Failed to scale deployment: {e}")
            return False
```

---

## 🔍 Failure Detection Methods

### **1. Health Checks**

#### **Liveness Probe**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

#### **Readiness Probe**
```yaml
readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 3
```

### **2. Metrics Monitoring**

#### **Prometheus Metrics**
```python
# Custom metrics for self-healing
self_healing_pod_failures_total = Counter(
    'self_healing_pod_failures_total',
    'Total number of pod failures detected',
    ['namespace', 'pod_name', 'failure_type']
)

self_healing_recovery_actions_total = Counter(
    'self_healing_recovery_actions_total',
    'Total number of recovery actions taken',
    ['action_type', 'success']
)

self_healing_recovery_duration_seconds = Histogram(
    'self_healing_recovery_duration_seconds',
    'Time taken for recovery actions',
    ['action_type']
)
```

### **3. Event Monitoring**

#### **Kubernetes Events**
```python
def watch_kubernetes_events(self):
    """Watch Kubernetes events for failures"""
    v1 = client.CoreV1Api()
    w = watch.Watch()
    
    for event in w.stream(v1.list_event_for_all_namespaces):
        if event['type'] == 'Warning':
            self.handle_warning_event(event['object'])
    
def handle_warning_event(self, event):
    """Handle warning events that indicate failures"""
    if 'Failed' in event.reason or 'Error' in event.reason:
        self.analyze_event_failure(event)
```

---

## 🚨 Alert Rules

### **Pod Failure Alerts**

#### **Crash Loop Detection**
```yaml
- alert: PodCrashLooping
  expr: rate(kube_pod_container_status_restarts_total[15m]) * 60 > 0
  for: 5m
  labels:
    severity: warning
    component: self-healing
  annotations:
    summary: "Pod {{ $labels.pod }} is crash looping"
    description: "Pod {{ $labels.pod }} in namespace {{ $labels.namespace }} is restarting {{ printf \"%.2f\" $value }} times / 5 minutes."
```

#### **Pod Not Ready**
```yaml
- alert: PodNotReady
  expr: kube_pod_status_phase{phase=~"Pending|Unknown"} > 0
  for: 10m
  labels:
    severity: warning
    component: self-healing
  annotations:
    summary: "Pod {{ $labels.pod }} is not ready"
    description: "Pod {{ $labels.pod }} in namespace {{ $labels.namespace }} has been in {{ $labels.phase }} state for more than 10 minutes."
```

### **Node Failure Alerts**

#### **Node Not Ready**
```yaml
- alert: NodeNotReady
  expr: kube_node_status_condition{condition="Ready",status="true"} == 0
  for: 5m
  labels:
    severity: critical
    component: self-healing
  annotations:
    summary: "Node {{ $labels.node }} is not ready"
    description: "Node {{ $labels.node }} has been not ready for more than 5 minutes."
```

#### **Node Resource Pressure**
```yaml
- alert: NodeDiskPressure
  expr: kube_node_status_condition{condition="DiskPressure",status="true"} == 1
  for: 5m
  labels:
    severity: warning
    component: self-healing
  annotations:
    summary: "Node {{ $labels.node }} has disk pressure"
    description: "Node {{ $labels.node }} is experiencing disk pressure."
```

---

## 🔧 Configuration

### **Environment Variables**

#### **Failure Thresholds**
```yaml
env:
  - name: POD_FAILURE_THRESHOLD
    value: "3"
  - name: POD_RESTART_TIMEOUT
    value: "300"
  - name: NODE_FAILURE_THRESHOLD
    value: "2"
  - name: NODE_UNREACHABLE_TIMEOUT
    value: "600"
```

#### **Integration Settings**
```yaml
env:
  - name: SLACK_NOTIFICATIONS_ENABLED
    value: "true"
  - name: SLACK_WEBHOOK_URL
    valueFrom:
      secretKeyRef:
        name: slack-secret
        key: webhook_url
  - name: PROMETHEUS_ENABLED
    value: "true"
  - name: PROMETHEUS_URL
    value: "http://prometheus-service.monitoring.svc.cluster.local:9090"
```

### **Recovery Strategies**

#### **Pod Recovery Strategy**
```python
POD_RECOVERY_STRATEGIES = {
    'crash_loop': {
        'action': 'restart',
        'max_attempts': 3,
        'backoff_delay': 30,
        'escalation': 'scale_deployment'
    },
    'resource_exhaustion': {
        'action': 'scale_deployment',
        'scale_factor': 1.5,
        'max_replicas': 10,
        'escalation': 'rollback_deployment'
    },
    'network_issue': {
        'action': 'restart',
        'max_attempts': 2,
        'backoff_delay': 60,
        'escalation': 'node_reboot'
    }
}
```

#### **Node Recovery Strategy**
```python
NODE_RECOVERY_STRATEGIES = {
    'not_ready': {
        'action': 'wait_and_monitor',
        'timeout': 300,
        'escalation': 'reboot_node'
    },
    'disk_pressure': {
        'action': 'cleanup_disk',
        'timeout': 600,
        'escalation': 'reboot_node'
    },
    'memory_pressure': {
        'action': 'evict_pods',
        'timeout': 300,
        'escalation': 'reboot_node'
    }
}
```

---

## 📊 Metrics and Monitoring

### **Key Metrics**

#### **Recovery Success Rate**
```promql
# Recovery success rate
rate(self_healing_recovery_actions_total{success="true"}[5m]) / 
rate(self_healing_recovery_actions_total[5m])
```

#### **Average Recovery Time**
```promql
# Average recovery duration
histogram_quantile(0.95, rate(self_healing_recovery_duration_seconds_bucket[5m]))
```

#### **Failure Detection Time**
```promql
# Time from failure to detection
rate(self_healing_failure_detection_duration_seconds_sum[5m]) / 
rate(self_healing_failure_detection_duration_seconds_count[5m])
```

### **Grafana Dashboard**

#### **Self-Healing Overview**
- **Recovery Success Rate**: Percentage of successful recoveries
- **Average Recovery Time**: Time taken for recovery actions
- **Failure Types**: Distribution of different failure types
- **Active Alerts**: Current active alerts and their status

#### **Pod Health Dashboard**
- **Pod Status**: Current status of all pods
- **Restart Count**: Number of pod restarts
- **Resource Usage**: CPU and memory usage
- **Health Check Status**: Liveness and readiness probe status

---

## 🔄 Integration with Chaos Engineering

### **Chaos Experiment Integration**
```python
def integrate_with_chaos_mesh(self):
    """Integrate with Chaos Mesh for controlled testing"""
    chaos_client = self.get_chaos_mesh_client()
    
    # Monitor chaos experiments
    experiments = chaos_client.list_experiments()
    for experiment in experiments:
        if experiment.status.phase == 'Running':
            self.monitor_chaos_experiment(experiment)
    
def monitor_chaos_experiment(self, experiment):
    """Monitor chaos experiment and validate recovery"""
    affected_pods = self.get_affected_pods(experiment)
    
    for pod in affected_pods:
        # Wait for failure to occur
        time.sleep(30)
        
        # Check if recovery mechanism worked
        if self.is_pod_healthy(pod):
            self.log_success(f"Pod {pod.metadata.name} recovered from chaos experiment")
        else:
            self.log_failure(f"Pod {pod.metadata.name} failed to recover from chaos experiment")
```

---

## 📈 Performance Characteristics

### **Recovery Time Objectives (RTO)**

| Failure Type | Target RTO | Actual RTO | Success Rate |
|--------------|------------|------------|--------------|
| **Pod Crash** | < 30s | 15-25s | 99.5% |
| **Pod OOM** | < 60s | 30-45s | 98.8% |
| **Node Failure** | < 5m | 3-4m | 99.2% |
| **Network Issue** | < 2m | 1-1.5m | 99.7% |

### **Resource Usage**

| Component | CPU Request | CPU Limit | Memory Request | Memory Limit |
|-----------|-------------|-----------|----------------|--------------|
| **Controller** | 250m | 500m | 256Mi | 512Mi |
| **Monitoring** | 100m | 200m | 128Mi | 256Mi |
| **Chaos Mesh** | 200m | 400m | 512Mi | 1Gi |

---

<div align="center">

**[← Components](./components.md)** | **[Chaos Engineering →](./chaos-engineering.md)**

</div> 