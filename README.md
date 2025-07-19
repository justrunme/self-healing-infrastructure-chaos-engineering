# 🚀 Self-Healing Infrastructure with Chaos Engineering

[![CI/CD Pipeline](https://github.com/justrunme/self-healing-infrastructure-chaos-engineering/workflows/CI%2FCD%20Pipeline/badge.svg)](https://github.com/justrunme/self-healing-infrastructure-chaos-engineering/actions/workflows/ci-cd.yml)
[![Release](https://github.com/justrunme/self-healing-infrastructure-chaos-engineering/workflows/Release/badge.svg)](https://github.com/justrunme/self-healing-infrastructure-chaos-engineering/actions/workflows/release.yml)
[![Docker Image](https://img.shields.io/badge/docker-latest-blue.svg)](https://github.com/justrunme/self-healing-infrastructure-chaos-engineering/packages)
[![Terraform](https://img.shields.io/badge/terraform-1.0+-blue.svg)](https://www.terraform.io/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-1.24+-blue.svg)](https://kubernetes.io/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A comprehensive **Kubernetes-based self-healing infrastructure** that automatically detects and recovers from failures, with integrated monitoring, chaos engineering, and automated node management. Built with modern DevOps practices and robust testing.

## 🎯 What This Infrastructure Guarantees

### ✅ **Infrastructure Reliability**
- **Automatic Pod Recovery**: Failed pods are automatically detected and restarted
- **Crash Loop Prevention**: Intelligent handling of crash looping applications
- **Node Health Management**: Automatic node reboots for security updates via Kured
- **Resource Optimization**: Horizontal Pod Autoscaler (HPA) for dynamic scaling
- **High Availability**: Multi-replica deployments with health checks

### ✅ **Monitoring & Observability**
- **Real-time Metrics**: Prometheus-based monitoring with custom dashboards
- **Alert Management**: Intelligent alerting with Slack integration
- **Performance Tracking**: Resource usage monitoring and optimization
- **Health Dashboards**: Grafana dashboards for infrastructure overview

### ✅ **Chaos Engineering & Testing**
- **Automated Chaos Experiments**: Chaos Mesh integration for resilience testing
- **Failure Simulation**: Controlled pod failures and network chaos
- **Recovery Validation**: Automated testing of self-healing mechanisms
- **Performance Stress Testing**: Load testing and scalability validation

### ✅ **Security & Compliance**
- **Network Policies**: Isolated namespace communication
- **RBAC Implementation**: Role-based access control for all components
- **Security Contexts**: Non-root execution and minimal privileges
- **Secret Management**: Secure handling of sensitive configuration

## 🧪 Comprehensive Test Suite

Our CI/CD pipeline includes **8 comprehensive test stages** that validate every aspect of the infrastructure:

### 1. **Code Quality & Linting** ✅
- YAML validation and linting
- Python code quality checks
- Docker image validation
- Terraform configuration validation

### 2. **Infrastructure Deployment** ✅
- Terraform plan and apply
- Namespace creation and management
- Resource deployment validation
- Minikube cluster setup

### 3. **Self-Healing Controller Tests** ✅
- Health endpoint validation (`/health`, `/metrics`)
- Pod failure recovery testing
- Controller functionality verification
- Service connectivity tests

### 4. **Monitoring Stack Tests** ✅
- Prometheus deployment and connectivity
- Grafana dashboard accessibility
- Alertmanager configuration
- Metrics collection validation

### 5. **Integration Tests** ✅
- Kured daemon functionality
- PrometheusRules CRD validation
- Test application accessibility
- HPA (Horizontal Pod Autoscaler) testing

### 6. **Performance Tests** ✅
- Resource limits validation
- Scalability testing (scale to 5 replicas)
- Multiple pod failure recovery
- Node metrics and resource monitoring

### 7. **Cleanup & Reporting** ✅
- System state collection
- Log aggregation
- Test resource cleanup
- Comprehensive reporting

## 📊 Test Results & System Report

After each successful CI/CD run, we generate a comprehensive system report that includes:

```bash
# System Status Report
=== Pod Status Across All Namespaces ===
NAMESPACE         NAME                                    READY   STATUS    RESTARTS   AGE
kube-system       coredns-787d4945fb-abc12              1/1     Running   0          5m
kube-system       etcd-minikube                         1/1     Running   0          5m
kube-system       kube-apiserver-minikube               1/1     Running   0          5m
kube-system       kube-controller-manager-minikube      1/1     Running   0          5m
kube-system       kube-proxy-xyz789                     1/1     Running   0          5m
kube-system       kube-scheduler-minikube               1/1     Running   0          5m
kube-system       metrics-server-5c6d7f8g9h             1/1     Running   0          4m
kube-system       storage-provisioner                   1/1     Running   0          5m
monitoring        prometheus-kube-prometheus-prometheus-0 2/2   Running   0          3m
monitoring        prometheus-grafana-abc123-def456      2/2     Running   0          3m
self-healing      self-healing-controller-xyz789-abc12  1/1     Running   0          2m
test-app          test-app-abc123-def456                1/1     Running   0          2m
test-app          test-app-abc123-ghi789                1/1     Running   0          2m

=== Self-Healing Controller Logs ===
2024-01-15 10:30:15 INFO Starting Self-Healing Controller v1.0.0
2024-01-15 10:30:15 INFO Monitoring namespace: test-app
2024-01-15 10:30:15 INFO Health check endpoint: /health
2024-01-15 10:30:15 INFO Metrics endpoint: /metrics
2024-01-15 10:30:16 INFO Controller ready to monitor pods

=== Recent Cluster Events ===
LAST SEEN   TYPE      REASON              OBJECT                    MESSAGE
2m          Normal    Scheduled           pod/test-app-abc123-def456 Successfully assigned test-app/test-app-abc123-def456 to minikube
2m          Normal    Pulled              pod/test-app-abc123-def456 Container image "nginx:1.21-alpine" already present on machine
2m          Normal    Created             pod/test-app-abc123-def456 Created container test-app
2m          Normal    Started             pod/test-app-abc123-def456 Started container test-app
2m          Normal    Scheduled           pod/test-app-abc123-ghi789 Successfully assigned test-app/test-app-abc123-ghi789 to minikube
2m          Normal    Pulled              pod/test-app-abc123-ghi789 Container image "nginx:1.21-alpine" already present on machine
2m          Normal    Created             pod/test-app-abc123-ghi789 Created container test-app
2m          Normal    Started             pod/test-app-abc123-ghi789 Started container test-app
```

## 🚀 Quick Start

### Prerequisites
- **Docker** (for local development)
- **kubectl** (Kubernetes CLI)
- **Terraform** >= 1.0
- **Minikube** (for local testing)

### Option 1: Terraform Deployment (Recommended)

```bash
# Clone the repository
git clone https://github.com/justrunme/self-healing-infrastructure-chaos-engineering.git
cd self-healing-infrastructure-chaos-engineering

# Deploy with Terraform
./scripts/deploy-terraform.sh
```

### Option 2: Manual Deployment

```bash
# Start Minikube
minikube start --driver=docker --cpus=2 --memory=4096

# Build and load Self-Healing Controller
cd kubernetes/self-healing
docker build -t self-healing-controller:latest .
minikube image load self-healing-controller:latest
cd ../..

# Deploy components
kubectl apply -f kubernetes/monitoring/
kubectl apply -f kubernetes/self-healing/deployment.yaml
kubectl apply -f kubernetes/test-app/test-app.yaml
kubectl apply -f kubernetes/kured/kured.yaml
kubectl apply -f kubernetes/chaos-engineering/
```

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Self-Healing Infrastructure                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Test App  │  │ Self-Healing│  │  Monitoring │            │
│  │   (Nginx)   │  │ Controller  │  │   Stack     │            │
│  │             │  │             │  │             │            │
│  │ • HPA       │  │ • Pod Watch │  │ • Prometheus│            │
│  │ • Health    │  │ • Recovery  │  │ • Grafana   │            │
│  │ • Scaling   │  │ • Metrics   │  │ • Alerts    │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │    Kured    │  │    Chaos    │  │   Backup    │            │
│  │             │  │  Engineering │  │   System    │            │
│  │ • Node      │  │             │  │             │            │
│  │   Reboots   │  │ • Chaos Mesh│  │ • Automated │            │
│  │ • Security  │  │ • Pod Chaos │  │ • Retention │            │
│  │   Updates   │  │ • Network   │  │ • Recovery  │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
self-healing-infrastructure-chaos-engineering/
├── terraform/                    # Infrastructure as Code
│   ├── main.tf                  # Main Terraform configuration
│   ├── variables.tf             # Variable definitions
│   ├── outputs.tf               # Output values
│   └── terraform.tfvars.example # Example variables file
├── kubernetes/                  # Kubernetes manifests
│   ├── self-healing/           # Self-Healing Controller
│   │   ├── tests/              # Unit and integration tests
│   │   ├── self_healing_controller.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── monitoring/             # Monitoring stack
│   │   ├── grafana-dashboard.yaml
│   │   └── prometheus-alerts.yaml
│   ├── test-app/               # Test application (Nginx)
│   ├── kured/                  # Node reboot daemon
│   ├── chaos-engineering/      # Chaos Mesh and experiments
│   └── backup/                 # Backup system
├── scripts/                    # Deployment scripts
│   ├── deploy-terraform.sh     # Terraform deployment
│   ├── destroy-terraform.sh    # Terraform cleanup
│   └── test-infrastructure.sh  # Infrastructure testing
├── docs/                       # Documentation
│   ├── architecture.md         # System architecture
│   ├── user-guide.md           # User guide
│   └── troubleshooting.md      # Troubleshooting guide
└── .github/workflows/          # CI/CD pipelines
    ├── ci-cd.yml              # Main CI/CD pipeline
    ├── release.yml            # Release automation
    └── README.md              # Workflow documentation
```

## 🔧 Configuration

### Terraform Variables

Copy `terraform/terraform.tfvars.example` to `terraform/terraform.tfvars` and customize:

```hcl
# Slack Configuration
slack_webhook_url = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
slack_channel = "#alerts"
slack_notifications_enabled = true

# Cluster Configuration
cluster_name = "self-healing-cluster"
environment = "dev"

# Monitoring Configuration
prometheus_retention_days = 15
grafana_admin_password = "your-secure-password"

# Self-Healing Controller
self_healing_controller_image = "self-healing-controller:latest"
```

### Self-Healing Controller Configuration

The controller can be configured via environment variables:

```yaml
POD_FAILURE_THRESHOLD: "3"
POD_RESTART_TIMEOUT: "300"
NODE_FAILURE_THRESHOLD: "2"
NODE_UNREACHABLE_TIMEOUT: "600"
CHECK_INTERVAL: "30"
SLACK_NOTIFICATIONS_ENABLED: "true"
```

## 🐳 Docker Images

### Available Images

The Self-Healing Controller is automatically built and published to GitHub Container Registry:

```bash
# Pull the latest image
docker pull ghcr.io/justrunme/self-healing-infrastructure-chaos-engineering/self-healing-controller:latest

# Pull a specific version
docker pull ghcr.io/justrunme/self-healing-infrastructure-chaos-engineering/self-healing-controller:v1.0.0
```

### Image Management

```bash
# Build a new image
./scripts/manage-images.sh build v1.0.0

# Create a release
./scripts/manage-images.sh release v1.0.0

# Update Terraform with new version
./scripts/manage-images.sh update-terraform v1.0.0
```

## 📈 Performance & Reliability Features

- **Health Checks**: Liveness, readiness, and startup probes
- **Resource Management**: Optimized resource allocation with limits and requests
- **Backup & Recovery**: Automated backup system with configurable retention
- **Integration Tests**: Comprehensive test coverage across all components
- **Performance Tests**: Load testing and performance validation
- **Chaos Engineering**: Automated resilience testing with Chaos Mesh

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: Check the [docs/](docs/) directory
- **Issues**: Report bugs and feature requests via [GitHub Issues](https://github.com/justrunme/self-healing-infrastructure-chaos-engineering/issues)
- **Discussions**: Join the conversation in [GitHub Discussions](https://github.com/justrunme/self-healing-infrastructure-chaos-engineering/discussions)

---

<div align="center">

**Built with ❤️ for reliable, self-healing infrastructure**

[![GitHub stars](https://img.shields.io/github/stars/justrunme/self-healing-infrastructure-chaos-engineering?style=social)](https://github.com/justrunme/self-healing-infrastructure-chaos-engineering/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/justrunme/self-healing-infrastructure-chaos-engineering?style=social)](https://github.com/justrunme/self-healing-infrastructure-chaos-engineering/network)
[![GitHub issues](https://img.shields.io/github/issues/justrunme/self-healing-infrastructure-chaos-engineering)](https://github.com/justrunme/self-healing-infrastructure-chaos-engineering/issues)

</div>