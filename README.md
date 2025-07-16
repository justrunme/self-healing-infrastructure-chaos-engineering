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

1. **Prepare cluster:**
   ```bash
   cd terraform
   terraform init
   terraform apply
   ```

2. **Deploy monitoring:**
   ```bash
   kubectl apply -f kubernetes/monitoring/
   ```

3. **Deploy Chaos Engineering:**
   ```bash
   kubectl apply -f kubernetes/chaos-engineering/
   ```

4. **Deploy Self-Healing Controller:**
   ```bash
   kubectl apply -f kubernetes/self-healing/
   ```

5. **Deploy Kured:**
   ```bash
   kubectl apply -f kubernetes/kured/
   ```

## 📊 Monitoring

- Prometheus UI: `http://localhost:9090`
- Alertmanager UI: `http://localhost:9093`
- Chaos Mesh UI: `http://localhost:2333`

## 🔧 Configuration

All configurations are located in their respective folders:
- `kubernetes/` - Kubernetes manifests
- `terraform/` - Terraform configurations
- `helm-charts/` - Helm charts

## 📝 License

MIT License 