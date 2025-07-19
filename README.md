# Self-Healing Infrastructure with Chaos Engineering

A comprehensive Kubernetes-based self-healing infrastructure that automatically detects and recovers from failures, with integrated monitoring, chaos engineering, and automated node reboots.

## 🎯 Features

### ✅ **Self-Healing Controller**
- **Automatic Pod Recovery**: Detects and restarts failed pods
- **Crash Loop Detection**: Identifies and handles crash looping pods
- **Health Monitoring**: Real-time health checks and metrics
- **Rate Limiting**: Prevents excessive pod checks
- **Error Handling**: Robust error handling and logging
- **Security**: Non-root execution, read-only filesystems, dropped capabilities
- **Resource Management**: CPU and memory limits with requests

### 📊 **Monitoring Stack**
- **Prometheus**: Metrics collection and alerting
- **Grafana**: Custom dashboards for infrastructure monitoring
- **Alertmanager**: Alert routing and notification management
- **Custom Alerts**: Pod failures, resource usage, controller status
- **Comprehensive Dashboards**: Self-healing overview, chaos engineering, cluster health

### 🔧 **Infrastructure Components**
- **Kured**: Automatic node reboots for security updates
- **Test Application**: Nginx with Horizontal Pod Autoscaler (HPA)
- **Terraform**: Infrastructure as Code for complete deployment
- **Helm Charts**: Prometheus Stack deployment
- **Network Policies**: Security isolation between namespaces
- **Backup System**: Automated daily backups with retention

### 🧪 **Chaos Engineering**
- **Chaos Mesh**: Comprehensive chaos engineering platform
- **Automated Experiments**: Pod failures, network chaos, resource stress
- **Integration**: Seamless integration with self-healing mechanisms
- **Monitoring**: Real-time experiment status and results

### 🔒 **Security Features**
- **Network Policies**: Isolated namespace communication
- **Service Mesh**: Controlled inter-service communication
- **Port Restrictions**: Only necessary ports are exposed
- **Non-root Execution**: All containers run as non-root users
- **Read-only Filesystems**: Where possible
- **Dropped Capabilities**: Minimal required privileges
- **Security Contexts**: Enforced at pod and container level
- **RBAC**: Role-based access control for all components
- **Service Accounts**: Dedicated accounts for each component
- **Namespace Isolation**: Resource isolation by namespace
- **Secret Management**: Secure handling of sensitive data
- **Resource Limits**: CPU and memory constraints

### 🐳 Docker Registry Integration

### Available Images

The Self-Healing Controller is automatically built and published to GitHub Container Registry:

```bash
# Pull the latest image
docker pull ghcr.io/justrunme/self-healing-infrastructure-chaos-engineering/self-healing-controller:latest

# Pull a specific version
docker pull ghcr.io/justrunme/self-healing-infrastructure-chaos-engineering/self-healing-controller:v1.0.0
```

### Image Management

Use the provided script to manage Docker images:

```bash
# Make script executable
chmod +x scripts/manage-images.sh

# Build a new image
./scripts/manage-images.sh build v1.0.0

# Create a release
./scripts/manage-images.sh release v1.0.0

# Update Terraform with new version
./scripts/manage-images.sh update-terraform v1.0.0

# List available tags
./scripts/manage-images.sh list

# Clean up old images
./scripts/manage-images.sh cleanup 3
```

### Multi-stage Build Benefits

- **Smaller Runtime Images**: Only runtime dependencies included
- **Better Security**: Reduced attack surface
- **Faster Builds**: Layer caching optimization
- **Multi-platform Support**: AMD64 and ARM64 architectures

## 📈 **Performance & Reliability**
- **Health Checks**: Liveness, readiness, and startup probes
- **Resource Management**: Optimized resource allocation
- **Backup & Recovery**: Automated backup system with 7-day retention
- **Integration Tests**: Comprehensive test coverage
- **Performance Tests**: Load testing and performance validation

## 🚀 Quick Start

### Prerequisites
- Docker
- kubectl
- Terraform >= 1.0
- Minikube (for local development)

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
kubectl apply -f kubernetes/self-healing/deployment-optional-slack.yaml
kubectl apply -f kubernetes/test-app/test-app.yaml
kubectl apply -f kubernetes/kured/kured.yaml
kubectl apply -f kubernetes/chaos-engineering/
kubectl apply -f kubernetes/backup/
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
│   │   ├── tests/              # Unit, integration, and performance tests
│   │   └── self_healing_controller.py
│   ├── monitoring/             # Monitoring stack
│   │   ├── grafana-dashboard.yaml
│   │   └── prometheus-alerts.yaml
│   ├── test-app/               # Test application
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