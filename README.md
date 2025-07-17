# Self-Healing Infrastructure with Chaos Engineering

A comprehensive system for automatic recovery of Kubernetes infrastructure with integrated Chaos Engineering for resilience testing.

## 🎯 Project Goals

- Automatic detection and recovery of failures in Kubernetes cluster
- Integration with Kured for automatic node reboots
- Chaos Engineering for resilience testing
- Automatic Helm release rollbacks on failures
- Slack notifications for incidents

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Prometheus    │    │   Alertmanager  │    │   Chaos Mesh    │
│   (monitoring)  │    │  (notifications)│    │   (testing)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │  Self-Healing   │
                    │   Controller    │
                    └─────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Kubernetes    │
                    │    Cluster      │
                    └─────────────────┘
```

## 🚀 Core Components

### 1. Self-Healing Controller
- Automatic detection of pod and node failures
- Automatic Helm release rollbacks
- Integration with Kured for node reboots
- Application scaling when needed

### 2. Chaos Engineering
- Chaos Mesh for conducting chaos tests
- Automatic resilience testing
- Simulation of various failure scenarios

### 3. Monitoring and Alerting
- Prometheus for metrics collection
- Alertmanager for notification management
- Slack integration for notifications

### 4. Kured Integration
- Automatic node reboots
- Integration with Self-Healing Controller

## 📁 Project Structure

```
.
├── README.md
├── terraform/                 # Terraform configurations
├── kubernetes/               # Kubernetes manifests
│   ├── monitoring/          # Prometheus, Alertmanager
│   ├── chaos-engineering/   # Chaos Mesh, Litmus
│   ├── self-healing/        # Self-Healing Controller
│   └── kured/              # Kured DaemonSet
├── helm-charts/             # Helm charts
├── scripts/                 # Deployment scripts
└── docs/                   # Documentation
```

## 🛠️ Technologies

- **Kubernetes** - container orchestration
- **Helm** - package management
- **ArgoCD** - GitOps deployment
- **Prometheus** - monitoring
- **Chaos Mesh** - Chaos Engineering
- **Alertmanager** - notification management
- **Kured** - automatic node reboots
- **Terraform** - infrastructure as code

## 🚀 Quick Start

### Option 1: Full Deployment with Slack Notifications

1. **Prepare cluster:**
   ```bash
   cd terraform
   terraform init
   terraform apply
   ```

2. **Create Slack secret (optional):**
   ```bash
   kubectl apply -f kubernetes/self-healing/slack-secret.yaml
   ```

3. **Deploy all components:**
   ```bash
   ./scripts/deploy.sh
   ```

### Option 2: Deployment without Slack Notifications (CI/CD)

1. **Deploy with optional Slack notifications:**
   ```bash
   kubectl apply -f kubernetes/self-healing/deployment-optional-slack.yaml
   ```

2. **Or use the deployment script:**
   ```bash
   ./scripts/deploy.sh
   ```

### Manual Deployment Steps

1. **Deploy monitoring:**
   ```bash
   kubectl apply -f kubernetes/monitoring/
   ```

2. **Deploy Chaos Engineering:**
   ```bash
   kubectl apply -f kubernetes/chaos-engineering/
   ```

3. **Deploy Self-Healing Controller:**
   ```bash
   kubectl apply -f kubernetes/self-healing/deployment-optional-slack.yaml
   ```

4. **Deploy Kured:**
   ```bash
   kubectl apply -f kubernetes/kured/
   ```

## 📊 Monitoring

- Prometheus UI: `http://localhost:9090`
- Alertmanager UI: `http://localhost:9093`
- Chaos Mesh UI: `http://localhost:2333`

## 🧪 Testing

### Test Self-Healing Controller
```bash
./scripts/test-self-healing.sh
```

This script will:
- Check if the controller is running
- Test metrics and health endpoints
- Test Chaos Engineering integration
- Test pod failure recovery
- Show controller logs

### Run Chaos Experiments
```bash
./scripts/test-chaos.sh
```

This script will run various chaos experiments to test the resilience of your infrastructure.

## 🔧 Configuration

### Slack Notifications

The Self-Healing Controller supports Slack notifications for incidents. You can configure it in two ways:

#### Option 1: With Slack Notifications
1. Create a Slack webhook URL in your Slack workspace
2. Create the secret:
   ```bash
   kubectl create secret generic slack-secret \
     --from-literal=webhook_url=https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
     -n self-healing
   ```
3. Deploy with Slack notifications enabled:
   ```bash
   kubectl apply -f kubernetes/self-healing/deployment.yaml
   ```

#### Option 2: Without Slack Notifications (Default for CI/CD)
Deploy with Slack notifications disabled:
```bash
kubectl apply -f kubernetes/self-healing/deployment-optional-slack.yaml
```

### Environment Variables

The Self-Healing Controller can be configured using environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SLACK_NOTIFICATIONS_ENABLED` | `true` | Enable/disable Slack notifications |
| `SLACK_WEBHOOK_URL` | `""` | Slack webhook URL |
| `SLACK_CHANNEL` | `#alerts` | Slack channel for notifications |
| `POD_FAILURE_THRESHOLD` | `3` | Number of pod failures before action |
| `NODE_FAILURE_THRESHOLD` | `2` | Number of node failures before action |
| `HELM_ROLLBACK_ENABLED` | `true` | Enable Helm rollback on failures |
| `CHAOS_ENGINEERING_ENABLED` | `true` | Enable Chaos Engineering integration |

### All configurations are located in their respective folders:
- `kubernetes/` - Kubernetes manifests
- `terraform/` - Terraform configurations
- `helm-charts/` - Helm charts

## 📝 License

MIT License 