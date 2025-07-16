# Self-Healing Infrastructure User Guide

## Quick Start

### Prerequisites

Before deploying the Self-Healing Infrastructure, ensure you have the following installed:

- **Kubernetes Cluster** (Minikube, Kind, or production cluster)
- **kubectl** - Kubernetes command-line tool
- **Helm** - Kubernetes package manager
- **Docker** - Container runtime
- **Terraform** - Infrastructure as Code tool

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd self-healing-infrastructure-chaos-engineering
   ```

2. **Run the deployment script:**
   ```bash
   ./scripts/deploy.sh
   ```

3. **Verify the installation:**
   ```bash
   kubectl get pods --all-namespaces
   ```

## Component Overview

### 1. Self-Healing Controller

The Self-Healing Controller automatically monitors and recovers from failures.

**Configuration:**
```yaml
# Environment variables for the controller
POD_FAILURE_THRESHOLD: 3          # Number of restarts before action
POD_RESTART_TIMEOUT: 300          # Timeout for pod restart (seconds)
NODE_FAILURE_THRESHOLD: 2         # Node failure threshold
HELM_ROLLBACK_ENABLED: true       # Enable Helm rollback
SLACK_NOTIFICATIONS_ENABLED: true # Enable Slack notifications
```

**Monitoring:**
```bash
# Check controller status
kubectl get pods -n self-healing

# View controller logs
kubectl logs -n self-healing -l app=self-healing-controller

# Check controller metrics
kubectl port-forward -n self-healing svc/self-healing-controller 8080:8080
curl http://localhost:8080/metrics
```

### 2. Monitoring Stack

**Prometheus:**
```bash
# Access Prometheus UI
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
# Open http://localhost:9090
```

**Grafana:**
```bash
# Access Grafana UI
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
# Open http://localhost:3000 (admin/admin123)
```

**Alertmanager:**
```bash
# Access Alertmanager UI
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-alertmanager 9093:9093
# Open http://localhost:9093
```

### 3. Chaos Engineering

**Chaos Mesh:**
```bash
# Access Chaos Mesh UI
kubectl port-forward -n chaos-engineering svc/chaos-mesh-controller-manager 2333:10080
# Open http://localhost:2333
```

**Running Chaos Experiments:**
```bash
# Run the chaos test script
./scripts/test-chaos.sh

# Or manually create experiments
kubectl apply -f kubernetes/chaos-engineering/chaos-experiments.yaml
```

### 4. Kured (Node Reboots)

**Configuration:**
```yaml
# Kured configuration in kubernetes/kured/kured.yaml
reboot-days: sun,mon,tue,wed,thu,fri,sat
reboot-sentinel-file: /var/run/reboot-required
blocking-pods: kube-system/calico-node,kube-system/kube-proxy
```

**Manual Node Reboot:**
```bash
# Trigger reboot on a specific node
kubectl annotate node <node-name> weave.works/kured-node-lock=""
```

## Usage Examples

### 1. Testing Pod Failures

**Manual Pod Failure:**
```bash
# Delete a pod to test recovery
kubectl delete pod <pod-name> -n test-app

# Monitor recovery
kubectl get pods -n test-app -w
```

**Automated Chaos Test:**
```bash
# Create a pod failure experiment
cat <<EOF | kubectl apply -f -
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: test-pod-failure
  namespace: test-app
spec:
  action: pod-failure
  mode: one
  selector:
    namespaces:
      - test-app
    labelSelectors:
      app: test-app
  duration: "30s"
EOF
```

### 2. Testing Network Chaos

**Network Delay:**
```bash
cat <<EOF | kubectl apply -f -
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: network-delay
  namespace: test-app
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
  duration: "1m"
EOF
```

### 3. Testing Resource Stress

**CPU Stress:**
```bash
cat <<EOF | kubectl apply -f -
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: cpu-stress
  namespace: test-app
spec:
  mode: one
  selector:
    namespaces:
      - test-app
  stressors:
    cpu:
      workers: 1
      load: 50
  duration: "2m"
EOF
```

### 4. Helm Rollback Testing

**Deploy with Helm:**
```bash
# Install a test application with Helm
helm install test-app ./helm-charts/test-app --namespace test-app

# Simulate failure and trigger rollback
kubectl delete pod -l app=test-app -n test-app
```

## Monitoring and Alerts

### 1. Custom Alerts

**Pod Failure Alert:**
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

### 2. Slack Notifications

**Configuration:**
```yaml
# Set Slack webhook URL
kubectl create secret generic slack-secret \
  --from-literal=webhook_url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL" \
  -n monitoring
```

**Notification Types:**
- 🚨 Critical alerts (node failures)
- 🔧 Self-healing actions (pod restarts, rollbacks)
- 🧪 Chaos experiments (running, completed, failed)

### 3. Metrics and Dashboards

**Key Metrics:**
- `pod_failures_total` - Total number of pod failures detected
- `node_failures_total` - Total number of node failures detected
- `helm_rollbacks_total` - Total number of Helm rollbacks performed
- `slack_notifications_sent` - Total number of Slack notifications sent

**Grafana Dashboards:**
- Self-Healing Overview
- Chaos Engineering Experiments
- Cluster Health Status
- Alert History

## Troubleshooting

### 1. Common Issues

**Self-Healing Controller Not Starting:**
```bash
# Check logs
kubectl logs -n self-healing -l app=self-healing-controller

# Check RBAC permissions
kubectl auth can-i delete pods --as=system:serviceaccount:self-healing:self-healing-controller
```

**Prometheus Not Scraping:**
```bash
# Check Prometheus targets
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
# Open http://localhost:9090/targets
```

**Chaos Experiments Not Working:**
```bash
# Check Chaos Mesh status
kubectl get pods -n chaos-engineering

# Check experiment status
kubectl get chaos -n test-app
```

### 2. Debugging Commands

**Check Component Status:**
```bash
# All components
kubectl get pods --all-namespaces | grep -E "(prometheus|alertmanager|chaos-mesh|kured|self-healing)"

# Specific component
kubectl get pods -n <namespace> -l app=<app-name>
```

**View Logs:**
```bash
# Component logs
kubectl logs -n <namespace> -l app=<app-name>

# Follow logs
kubectl logs -n <namespace> -l app=<app-name> -f
```

**Check Events:**
```bash
# Namespace events
kubectl get events -n <namespace>

# All events
kubectl get events --all-namespaces
```

### 3. Performance Tuning

**Resource Limits:**
```yaml
# Adjust resource limits in deployment.yaml
resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 250m
    memory: 256Mi
```

**Monitoring Intervals:**
```yaml
# Adjust Prometheus scrape intervals
scrape_interval: 15s
evaluation_interval: 15s
```

## Best Practices

### 1. Production Deployment

- Use production-grade Kubernetes cluster
- Configure proper resource limits
- Set up monitoring and alerting
- Regular backup and disaster recovery testing
- Security hardening (RBAC, network policies)

### 2. Chaos Engineering

- Start with small, controlled experiments
- Gradually increase chaos intensity
- Monitor system behavior during experiments
- Document lessons learned
- Regular chaos testing schedules

### 3. Monitoring

- Set up comprehensive alerting
- Regular dashboard reviews
- Performance monitoring
- Capacity planning
- Incident response procedures

### 4. Security

- Regular security updates
- Access control reviews
- Secret rotation
- Network security policies
- Compliance monitoring 