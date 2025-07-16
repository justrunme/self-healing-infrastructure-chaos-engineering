# Quick Start Guide

## 🚀 Deploy Self-Healing Infrastructure in 5 Minutes

This guide will help you quickly deploy and test the Self-Healing Infrastructure with Chaos Engineering.

### Prerequisites

Ensure you have the following installed:
- [Docker](https://docs.docker.com/get-docker/)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Helm](https://helm.sh/docs/intro/install/)
- [Minikube](https://minikube.sigs.k8s.io/docs/start/)

### Step 1: Start Minikube

```bash
# Start Minikube with sufficient resources
minikube start --driver=docker --cpus=4 --memory=8192

# Verify cluster is running
kubectl cluster-info
```

### Step 2: Deploy the System

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Run the deployment script
./scripts/deploy.sh
```

The script will:
- ✅ Deploy Terraform infrastructure
- ✅ Install monitoring stack (Prometheus, Grafana, Alertmanager)
- ✅ Deploy Chaos Mesh for chaos engineering
- ✅ Install Kured for automatic node reboots
- ✅ Build and deploy Self-Healing Controller
- ✅ Deploy test application
- ✅ Configure chaos experiments

### Step 3: Access the Dashboards

```bash
# Prometheus UI
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
# Open: http://localhost:9090

# Grafana UI (admin/admin123)
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
# Open: http://localhost:3000

# Alertmanager UI
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-alertmanager 9093:9093
# Open: http://localhost:9093

# Chaos Mesh UI
kubectl port-forward -n chaos-engineering svc/chaos-mesh-controller-manager 2333:10080
# Open: http://localhost:2333

# Test Application
kubectl port-forward -n test-app svc/test-app 8080:80
# Open: http://localhost:8080
```

### Step 4: Test Chaos Engineering

```bash
# Run automated chaos tests
./scripts/test-chaos.sh
```

This will test:
- 🧪 Pod failures and recovery
- 🌐 Network chaos (delays, losses)
- 💻 CPU and memory stress
- 🔄 Container kills
- 📊 System health monitoring

### Step 5: Monitor Self-Healing

```bash
# Watch Self-Healing Controller logs
kubectl logs -n self-healing -l app=self-healing-controller -f

# Check test application status
kubectl get pods -n test-app -w

# View chaos experiments
kubectl get chaos -n test-app
```

## 🎯 What You'll See

### Self-Healing in Action

1. **Pod Failures**: When pods crash, they're automatically restarted
2. **Helm Rollbacks**: Failed Helm releases are automatically rolled back
3. **Node Recovery**: Unhealthy nodes trigger automatic reboots via Kured
4. **Slack Notifications**: Real-time alerts for all incidents

### Chaos Engineering Results

- **Resilience Testing**: System behavior under stress
- **Recovery Validation**: Automatic recovery verification
- **Performance Impact**: Monitoring during chaos experiments
- **Alert Verification**: Notification system testing

## 🔧 Configuration

### Slack Notifications

```bash
# Set your Slack webhook URL
kubectl create secret generic slack-secret \
  --from-literal=webhook_url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL" \
  -n monitoring
```

### Custom Chaos Experiments

```bash
# Apply custom chaos experiments
kubectl apply -f examples/chaos-experiments.md

# Or create your own
kubectl apply -f - <<EOF
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: my-chaos-test
  namespace: test-app
spec:
  action: pod-failure
  mode: one
  selector:
    namespaces: [test-app]
    labelSelectors:
      app: test-app
  duration: "30s"
EOF
```

## 📊 Monitoring Dashboards

### Grafana Dashboards

1. **Self-Healing Overview**: System health and recovery metrics
2. **Chaos Engineering**: Experiment status and results
3. **Cluster Health**: Overall cluster status
4. **Alert History**: Past incidents and resolutions

### Key Metrics

- `pod_failures_total`: Total pod failures detected
- `node_failures_total`: Total node failures detected
- `helm_rollbacks_total`: Total Helm rollbacks performed
- `chaos_experiments_running`: Active chaos experiments

## 🧹 Cleanup

```bash
# Stop port forwarding (Ctrl+C)

# Delete the entire system
kubectl delete namespace monitoring chaos-engineering self-healing kured test-app

# Stop Minikube
minikube stop
```

## 🆘 Troubleshooting

### Common Issues

**Self-Healing Controller not starting:**
```bash
kubectl logs -n self-healing -l app=self-healing-controller
kubectl describe pod -n self-healing -l app=self-healing-controller
```

**Chaos experiments not working:**
```bash
kubectl get pods -n chaos-engineering
kubectl get chaos -n test-app
```

**Monitoring not accessible:**
```bash
kubectl get pods -n monitoring
kubectl get svc -n monitoring
```

### Get Help

- 📖 Read the full [User Guide](docs/user-guide.md)
- 🏗️ Check the [Architecture](docs/architecture.md)
- 🧪 Explore [Chaos Experiments](examples/chaos-experiments.md)
- 📝 Review the [README](README.md)

## 🎉 Congratulations!

You've successfully deployed a Self-Healing Infrastructure with Chaos Engineering! 

The system is now:
- ✅ Automatically detecting and recovering from failures
- ✅ Running chaos experiments to test resilience
- ✅ Sending notifications for incidents
- ✅ Monitoring system health in real-time

Start experimenting with different chaos scenarios and watch your system heal itself! 🚀 