# 🌪️ Chaos Engineering

> **How failure testing and resilience validation works in the infrastructure**

---

## 🧪 Chaos Engineering Overview

### **What is Chaos Engineering?**
Chaos Engineering is the discipline of experimenting on a system in order to build confidence in the system's capability to withstand turbulent conditions in production.

### **Why Chaos Engineering?**
- **Proactive Failure Detection**: Find weaknesses before they cause outages
- **Resilience Validation**: Ensure recovery mechanisms actually work
- **Confidence Building**: Build trust in system reliability
- **Performance Testing**: Validate system behavior under stress

---

## 🔬 Chaos Mesh Integration

### **Chaos Mesh Architecture**
```
┌─────────────────────────────────────────────────────────────┐
│                  Chaos Mesh Platform                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Controller  │  │ Dashboard   │  │ Experiments │         │
│  │ Manager     │  │             │  │             │         │
│  │             │  │ • Web UI    │  │ • Pod Chaos │         │
│  │ • Pod Chaos │  │ • Metrics   │  │ • Network   │         │
│  │ • Network   │  │ • Status    │  │ • CPU/Mem   │         │
│  │ • CPU/Mem   │  │ • History   │  │ • Container │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### **Chaos Mesh Installation**
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: chaos-engineering

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: chaos-mesh-controller-manager
  namespace: chaos-engineering
spec:
  replicas: 1
  selector:
    matchLabels:
      app: chaos-mesh-controller-manager
  template:
    metadata:
      labels:
        app: chaos-mesh-controller-manager
    spec:
      containers:
        - name: chaos-mesh-controller-manager
          image: chaos-mesh/chaos-mesh:latest
          ports:
            - containerPort: 10080
              name: http
          env:
            - name: NAMESPACE
              value: "chaos-engineering"
            - name: TZ
              value: "UTC"
```

---

## 🧪 Experiment Types

### **1. Pod Chaos Experiments**

#### **Pod Failure**
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: test-pod-failure
  namespace: chaos-engineering
spec:
  action: pod-failure
  mode: one
  selector:
    namespaces:
      - test-app
    labelSelectors:
      app: test-app
  duration: "30s"
  scheduler:
    cron: "@every 5m"
```

#### **Pod Kill**
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: test-pod-kill
  namespace: chaos-engineering
spec:
  action: pod-kill
  mode: random
  value: "1"
  selector:
    namespaces:
      - test-app
  scheduler:
    cron: "@every 10m"
```

#### **Container Kill**
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: test-container-kill
  namespace: chaos-engineering
spec:
  action: container-kill
  mode: one
  selector:
    namespaces:
      - test-app
  duration: "15s"
  scheduler:
    cron: "@every 15m"
```

### **2. Network Chaos Experiments**

#### **Network Delay**
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: test-network-delay
  namespace: chaos-engineering
spec:
  action: delay
  mode: one
  selector:
    namespaces:
      - test-app
  delay:
    latency: "100ms"
    correlation: "100"
    jitter: "0ms"
  duration: "30s"
  scheduler:
    cron: "@every 20m"
```

#### **Network Loss**
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: test-network-loss
  namespace: chaos-engineering
spec:
  action: loss
  mode: one
  selector:
    namespaces:
      - test-app
  loss:
    loss: "25"
    correlation: "100"
  duration: "20s"
  scheduler:
    cron: "@every 25m"
```

#### **Network Partition**
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: test-network-partition
  namespace: chaos-engineering
spec:
  action: partition
  mode: one
  selector:
    namespaces:
      - test-app
  duration: "45s"
  scheduler:
    cron: "@every 30m"
```

### **3. Resource Chaos Experiments**

#### **CPU Stress**
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: test-cpu-stress
  namespace: chaos-engineering
spec:
  mode: one
  selector:
    namespaces:
      - test-app
  stressors:
    cpu:
      workers: 2
      load: 80
  duration: "60s"
  scheduler:
    cron: "@every 35m"
```

#### **Memory Stress**
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: test-memory-stress
  namespace: chaos-engineering
spec:
  mode: one
  selector:
    namespaces:
      - test-app
  stressors:
    memory:
      workers: 1
      size: "256MB"
  duration: "45s"
  scheduler:
    cron: "@every 40m"
```

---

## 🔄 Experiment Workflow

### **1. Experiment Lifecycle**
```
Planning → Execution → Monitoring → Analysis → Cleanup
    ↓         ↓          ↓          ↓         ↓
  Define    Deploy    Watch      Validate   Remove
  Scope     Chaos    Metrics    Recovery   Chaos
```

### **2. Automated Experiment Pipeline**
```python
class ChaosExperimentPipeline:
    def __init__(self):
        self.chaos_client = self.get_chaos_mesh_client()
        self.monitoring_client = self.get_prometheus_client()
    
    def run_experiment(self, experiment_config):
        """Run a complete chaos experiment"""
        # 1. Pre-experiment baseline
        baseline_metrics = self.collect_baseline_metrics()
        
        # 2. Deploy chaos experiment
        experiment = self.deploy_experiment(experiment_config)
        
        # 3. Monitor during experiment
        experiment_metrics = self.monitor_experiment(experiment)
        
        # 4. Validate recovery
        recovery_metrics = self.validate_recovery(experiment)
        
        # 5. Generate report
        report = self.generate_experiment_report(
            baseline_metrics, 
            experiment_metrics, 
            recovery_metrics
        )
        
        return report
    
    def collect_baseline_metrics(self):
        """Collect baseline metrics before experiment"""
        return {
            'pod_count': self.get_pod_count(),
            'cpu_usage': self.get_cpu_usage(),
            'memory_usage': self.get_memory_usage(),
            'response_time': self.get_response_time(),
            'error_rate': self.get_error_rate()
        }
    
    def monitor_experiment(self, experiment):
        """Monitor system during chaos experiment"""
        metrics = []
        start_time = time.time()
        
        while time.time() - start_time < experiment.spec.duration:
            current_metrics = {
                'timestamp': time.time(),
                'pod_count': self.get_pod_count(),
                'cpu_usage': self.get_cpu_usage(),
                'memory_usage': self.get_memory_usage(),
                'response_time': self.get_response_time(),
                'error_rate': self.get_error_rate()
            }
            metrics.append(current_metrics)
            time.sleep(5)  # Collect every 5 seconds
        
        return metrics
    
    def validate_recovery(self, experiment):
        """Validate system recovery after experiment"""
        # Wait for recovery period
        time.sleep(60)  # 1 minute recovery window
        
        recovery_metrics = {
            'pod_count': self.get_pod_count(),
            'cpu_usage': self.get_cpu_usage(),
            'memory_usage': self.get_memory_usage(),
            'response_time': self.get_response_time(),
            'error_rate': self.get_error_rate(),
            'recovery_time': self.calculate_recovery_time()
        }
        
        return recovery_metrics
```

---

## 📊 Experiment Monitoring

### **Chaos Mesh Dashboard**

#### **Dashboard Access**
```bash
# Access Chaos Mesh Dashboard
kubectl port-forward -n chaos-engineering svc/chaos-mesh-dashboard 2333:2333
# Open: http://localhost:2333
```

#### **Dashboard Features**
- **Experiment Overview**: Current and historical experiments
- **Real-time Metrics**: System metrics during experiments
- **Experiment Status**: Success/failure rates
- **Recovery Validation**: Automatic recovery verification

### **Prometheus Integration**

#### **Chaos Experiment Metrics**
```promql
# Chaos experiment success rate
rate(chaos_experiment_status{phase="Succeeded"}[5m]) / 
rate(chaos_experiment_status[5m])

# Average experiment duration
histogram_quantile(0.95, rate(chaos_experiment_duration_seconds_bucket[5m]))

# Recovery time after chaos
histogram_quantile(0.95, rate(recovery_time_seconds_bucket[5m]))
```

#### **System Health During Chaos**
```promql
# Pod availability during chaos
kube_pod_status_phase{phase="Running"} / 
kube_pod_status_phase

# Response time during chaos
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate during chaos
rate(http_requests_total{status=~"5.."}[5m]) / 
rate(http_requests_total[5m])
```

---

## 🎯 Experiment Scenarios

### **1. Pod Failure Scenarios**

#### **Single Pod Failure**
```yaml
# Scenario: Kill one pod and verify recovery
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: single-pod-failure
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces: ["test-app"]
  scheduler:
    cron: "@every 10m"
```

**Expected Behavior:**
- Pod is killed
- Self-healing controller detects failure
- New pod is created automatically
- Service remains available

#### **Multiple Pod Failures**
```yaml
# Scenario: Kill multiple pods simultaneously
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: multiple-pod-failure
spec:
  action: pod-kill
  mode: random
  value: "2"
  selector:
    namespaces: ["test-app"]
  scheduler:
    cron: "@every 15m"
```

**Expected Behavior:**
- Multiple pods are killed
- HPA scales up to maintain availability
- Self-healing controller recovers pods
- Service remains available

### **2. Network Failure Scenarios**

#### **Network Delay**
```yaml
# Scenario: Introduce network delay
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: network-delay
spec:
  action: delay
  mode: one
  selector:
    namespaces: ["test-app"]
  delay:
    latency: "200ms"
    correlation: "100"
  duration: "30s"
  scheduler:
    cron: "@every 20m"
```

**Expected Behavior:**
- Network latency increases
- Response times increase
- Service remains functional
- Recovery after chaos ends

#### **Network Partition**
```yaml
# Scenario: Partition network between services
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: network-partition
spec:
  action: partition
  mode: one
  selector:
    namespaces: ["test-app"]
  duration: "45s"
  scheduler:
    cron: "@every 30m"
```

**Expected Behavior:**
- Network communication fails
- Circuit breakers activate
- Fallback mechanisms engage
- Recovery after partition ends

### **3. Resource Exhaustion Scenarios**

#### **CPU Exhaustion**
```yaml
# Scenario: Exhaust CPU resources
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: cpu-exhaustion
spec:
  mode: one
  selector:
    namespaces: ["test-app"]
  stressors:
    cpu:
      workers: 4
      load: 90
  duration: "60s"
  scheduler:
    cron: "@every 35m"
```

**Expected Behavior:**
- CPU usage spikes
- Response times increase
- HPA may scale up
- Recovery after stress ends

#### **Memory Exhaustion**
```yaml
# Scenario: Exhaust memory resources
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: memory-exhaustion
spec:
  mode: one
  selector:
    namespaces: ["test-app"]
  stressors:
    memory:
      workers: 2
      size: "512MB"
  duration: "45s"
  scheduler:
    cron: "@every 40m"
```

**Expected Behavior:**
- Memory usage increases
- Pods may be evicted
- Self-healing restarts pods
- Recovery after stress ends

---

## 📈 Experiment Results

### **Success Metrics**

#### **Recovery Success Rate**
```promql
# Percentage of successful recoveries
rate(chaos_recovery_success_total[24h]) / 
rate(chaos_experiments_total[24h]) * 100
```

#### **Mean Time to Recovery (MTTR)**
```promql
# Average recovery time
histogram_quantile(0.5, rate(recovery_time_seconds_bucket[24h]))
```

#### **Service Availability**
```promql
# Service uptime during chaos
(1 - rate(http_requests_total{status=~"5.."}[5m]) / 
rate(http_requests_total[5m])) * 100
```

### **Experiment Reports**

#### **Daily Chaos Report**
```
=== Chaos Engineering Daily Report ===
Date: 2024-01-15

Experiments Run: 24
Successful Recoveries: 23 (95.8%)
Failed Recoveries: 1 (4.2%)

Average Recovery Time: 25.3 seconds
Fastest Recovery: 12.1 seconds
Slowest Recovery: 89.7 seconds

Service Availability: 99.7%
Peak Response Time: 2.3 seconds
Average Error Rate: 0.3%

Top Failure Scenarios:
1. Pod Kill (8 experiments) - 100% recovery
2. Network Delay (6 experiments) - 100% recovery
3. CPU Stress (5 experiments) - 100% recovery
4. Memory Stress (3 experiments) - 66.7% recovery
5. Network Partition (2 experiments) - 100% recovery

Recommendations:
- Investigate memory stress recovery failures
- Optimize memory allocation for test-app
- Consider increasing memory limits
```

---

## 🔧 Configuration

### **Chaos Mesh Configuration**

#### **Controller Configuration**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: chaos-mesh-config
  namespace: chaos-engineering
data:
  controller-manager.conf: |
    [chaos]
    # Maximum concurrent experiments
    max-concurrent-experiments = 5
    
    # Default experiment timeout
    default-experiment-timeout = 300s
    
    # Metrics collection interval
    metrics-collection-interval = 5s
    
    # Recovery validation timeout
    recovery-validation-timeout = 60s
```

#### **Experiment Scheduling**
```yaml
# Cron schedule for experiments
schedules:
  - name: "pod-failure-every-10m"
    cron: "@every 10m"
    experiment: "pod-kill"
    
  - name: "network-delay-every-20m"
    cron: "@every 20m"
    experiment: "network-delay"
    
  - name: "cpu-stress-every-35m"
    cron: "@every 35m"
    experiment: "cpu-stress"
```

---

<div align="center">

**[← Self-Healing](./self-healing.md)** | **[CI/CD Pipeline →](./ci-cd.md)**

</div> 