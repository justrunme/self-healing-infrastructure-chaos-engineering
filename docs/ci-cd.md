# 🚀 CI/CD Pipeline

> **GitHub Actions workflow and automation for the self-healing infrastructure**

---

## 🔄 CI/CD Flow Overview

### **Pipeline Stages**
```
Code Push → Lint & Test → Build & Push → Deploy → Integration Test → Performance Test → Cleanup
    ↓           ↓            ↓           ↓           ↓               ↓              ↓
  Trigger    Quality     Docker      Terraform    Validation     Load Test     Reporting
  Workflow   Checks      Images      Deploy       Tests          Chaos Eng     Artifacts
```

### **Workflow Triggers**
```yaml
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment'
        required: true
        default: 'dev'
        type: choice
        options: [dev, staging, prod]
```

---

## 🧪 Test Stages

### **1. Code Quality & Linting**

#### **Python Code Quality**
```yaml
- name: Setup Python
  uses: actions/setup-python@v4
  with: 
    python-version: '3.9'

- name: Install dependencies
  run: |
    pip install --upgrade pip
    pip install -r kubernetes/self-healing/requirements.txt
    pip install -r kubernetes/self-healing/requirements-dev.txt

- name: Lint with Black & isort & Flake8
  run: |
    black --check kubernetes/self-healing/
    isort --check-only kubernetes/self-healing/
    flake8 kubernetes/self-healing/ --max-line-length=120

- name: Run unit tests with coverage
  working-directory: kubernetes/self-healing
  run: |
    pytest \
      --maxfail=1 \
      --disable-warnings \
      -v \
      --cov=. \
      --cov-report=xml \
      --cov-report=html
```

#### **Terraform Validation**
```yaml
- name: Setup Terraform
  uses: hashicorp/setup-terraform@v2
  with: 
    terraform_version: '1.0.11'

- name: Configure Terraform plugin cache
  run: |
    mkdir -p ~/.terraform.d/plugin-cache
    echo "TF_PLUGIN_CACHE_DIR=$HOME/.terraform.d/plugin-cache" >> $GITHUB_ENV

- name: Terraform Validate
  run: |
    cd terraform
    terraform init
    terraform validate
```

### **2. Infrastructure Deployment**

#### **Minikube Setup**
```yaml
- name: Setup Minikube
  uses: ./.github/actions/setup-minikube

- name: Ensure we talk to Minikube
  run: |
    echo "Current context: $(kubectl config current-context)"
    kubectl cluster-info

- name: Debug list namespaces
  run: |
    kubectl get namespaces
```

#### **Terraform Deployment**
```yaml
- name: Terraform Init & Apply
  working-directory: terraform
  run: |
    terraform init
    terraform plan -var="ci_cd_mode=false" -out=tfplan
    terraform apply -auto-approve tfplan
```

### **3. Self-Healing Controller Tests**

#### **Health Endpoint Validation**
```yaml
- name: Test Self-Healing Controller Health
  run: |
    # Wait for controller to be ready
    kubectl wait --for=condition=available --timeout=300s deployment/self-healing-controller -n self-healing
    
    # Test health endpoint
    kubectl port-forward -n self-healing svc/self-healing-controller 8080:8080 &
    sleep 10
    
    # Test health endpoint
    curl -f http://localhost:8080/health || exit 1
    curl -f http://localhost:8080/ready || exit 1
    curl -f http://localhost:8080/metrics || exit 1
    
    # Stop port-forward
    pkill -f "kubectl port-forward"
```

#### **Pod Failure Recovery Test**
```yaml
- name: Test Pod Failure Recovery
  run: |
    # Create a test pod that will fail
    kubectl run test-fail-pod --image=busybox --command -- /bin/sh -c "sleep 5 && exit 1" -n test-app
    
    # Wait for pod to fail
    sleep 10
    
    # Check if self-healing controller detected the failure
    kubectl logs -n self-healing deployment/self-healing-controller --tail=50 | grep -i "failure\|recovery" || echo "No recovery logs found"
    
    # Clean up
    kubectl delete pod test-fail-pod -n test-app --force --grace-period=0
```

### **4. Monitoring Stack Tests**

#### **Prometheus Connectivity**
```yaml
- name: Test Prometheus Connectivity
  run: |
    # Wait for Prometheus to be ready
    kubectl wait --for=condition=available --timeout=300s deployment/prometheus-kube-prometheus-prometheus -n monitoring
    
    # Test Prometheus endpoint
    kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090 &
    sleep 10
    
    # Test Prometheus API
    curl -f http://localhost:9090/api/v1/query?query=up || exit 1
    
    # Stop port-forward
    pkill -f "kubectl port-forward"
```

#### **Grafana Dashboard Test**
```yaml
- name: Test Grafana Dashboard
  run: |
    # Wait for Grafana to be ready
    kubectl wait --for=condition=available --timeout=300s deployment/prometheus-grafana -n monitoring
    
    # Test Grafana endpoint
    kubectl port-forward -n monitoring svc/prometheus-grafana 3000:3000 &
    sleep 10
    
    # Test Grafana API
    curl -f http://localhost:3000/api/health || exit 1
    
    # Stop port-forward
    pkill -f "kubectl port-forward"
```

### **5. Integration Tests**

#### **Kured Daemon Test**
```yaml
- name: Test Kured Daemon
  run: |
    # Check if Kured is running
    kubectl get daemonset kured -n kube-system
    
    # Check Kured logs
    kubectl logs -n kube-system -l name=kured --tail=20
```

#### **HPA (Horizontal Pod Autoscaler) Test**
```yaml
- name: Test HPA Functionality
  run: |
    # Check HPA status
    kubectl get hpa -n test-app
    
    # Verify HPA is working
    kubectl describe hpa test-app-hpa -n test-app
```

### **6. Performance Tests**

#### **Resource Limits Validation**
```yaml
- name: Test Resource Limits
  run: |
    # Check resource usage
    kubectl top pods --all-namespaces
    
    # Check resource limits
    kubectl get pods --all-namespaces -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].resources.limits.cpu}{"\t"}{.spec.containers[*].resources.limits.memory}{"\n"}{end}'
```

#### **Scalability Test**
```yaml
- name: Test Scalability
  run: |
    # Scale test app to 5 replicas
    kubectl scale deployment test-app --replicas=5 -n test-app
    
    # Wait for scaling
    kubectl rollout status deployment/test-app -n test-app
    
    # Verify all pods are running
    kubectl get pods -n test-app
    
    # Scale back down
    kubectl scale deployment test-app --replicas=2 -n test-app
```

### **7. Cleanup & Reporting**

#### **System State Collection**
```yaml
- name: Collect System State
  run: |
    # Collect pod status
    kubectl get pods --all-namespaces > system-report.txt
    
    # Collect service status
    kubectl get svc --all-namespaces >> system-report.txt
    
    # Collect events
    kubectl get events --all-namespaces --sort-by='.lastTimestamp' >> system-report.txt
    
    # Collect logs
    kubectl logs -n self-healing deployment/self-healing-controller --tail=100 >> system-report.txt
```

#### **Artifact Upload**
```yaml
- name: Upload System Report
  uses: actions/upload-artifact@v4
  with:
    name: system-report
    path: system-report.txt
    retention-days: 30

- name: Upload Coverage Report
  uses: actions/upload-artifact@v4
  with:
    name: coverage-report
    path: kubernetes/self-healing/htmlcov/
    retention-days: 30
```

---

## 🐳 Docker Build & Push

### **Docker Build Configuration**
```yaml
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v3

- name: Log in to Container Registry
  uses: docker/login-action@v3
  with:
    registry: ${{ env.REGISTRY }}
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}

- name: Extract metadata
  id: meta
  uses: docker/metadata-action@v5
  with:
    images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
    tags: |
      type=semver,pattern={{version}}
      type=semver,pattern={{major}}.{{minor}}
      type=semver,pattern={{major}}
      type=raw,value=latest,enable={{is_default_branch}}

- name: Build and push Docker image
  uses: docker/build-push-action@v5
  with:
    context: ./kubernetes/self-healing
    file: ./kubernetes/self-healing/Dockerfile
    push: true
    tags: ${{ steps.meta.outputs.tags }}
    labels: ${{ steps.meta.outputs.labels }}
    cache-from: type=gha
    cache-to: type=gha,mode=max
    platforms: linux/amd64,linux/arm64
```

---

## 🔄 Release Workflow

### **Release Trigger**
```yaml
on:
  workflow_dispatch:
  push:
    tags:
      - 'v*'
```

### **Release Process**
```yaml
- name: Create GitHub Release
  uses: actions/create-release@v1
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  with:
    tag_name: ${{ github.ref_name }}
    release_name: Release ${{ github.ref_name }}
    draft: false
    prerelease: false
    body: |
      ## Release ${{ github.ref_name }}
      
      ### 🐳 Images
      - **latest**: `${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:latest`
      - **version**: `${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.ref_name }}`
      
      ### 📦 What's New
      - Self-Healing improvements
      - Enhanced monitoring
      - Chaos-engineering integration
      - Security fixes
      - Performance optimizations
      
      ### 🚀 Quick Start
      ```bash
      docker pull ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:latest
      ./scripts/deploy-terraform.sh
      ```
      
      ### 📋 Changelog
      [Compare changes](https://github.com/${{ github.repository }}/compare/v${{ github.ref_name }}...main)
```

---

## 📊 CI/CD Metrics

### **Pipeline Performance**

#### **Build Time Metrics**
```promql
# Average build time
histogram_quantile(0.95, rate(ci_build_duration_seconds_bucket[24h]))

# Build success rate
rate(ci_builds_total{status="success"}[24h]) / 
rate(ci_builds_total[24h]) * 100
```

#### **Test Coverage Metrics**
```promql
# Test coverage percentage
test_coverage_percentage

# Test execution time
histogram_quantile(0.95, rate(test_execution_duration_seconds_bucket[24h]))
```

### **Deployment Metrics**

#### **Deployment Success Rate**
```promql
# Deployment success rate
rate(deployments_total{status="success"}[24h]) / 
rate(deployments_total[24h]) * 100

# Average deployment time
histogram_quantile(0.95, rate(deployment_duration_seconds_bucket[24h]))
```

#### **Rollback Rate**
```promql
# Rollback rate
rate(deployments_total{status="rollback"}[24h]) / 
rate(deployments_total[24h]) * 100
```

---

## 🔧 Configuration

### **Environment Variables**
```yaml
env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}/self-healing-controller
  IMAGE_TAG: ${{ github.sha }}
```

### **Secrets**
```yaml
secrets:
  GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
  DOCKER_REGISTRY_TOKEN: ${{ secrets.DOCKER_REGISTRY_TOKEN }}
```

### **Caching Strategy**
```yaml
# Terraform plugin cache
- uses: actions/cache@v3
  with:
    path: ~/.terraform.d/plugin-cache
    key: ${{ runner.os }}-tf-plugins-${{ hashFiles('terraform/**/*.tf') }}

# Python dependencies cache
- uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('kubernetes/self-healing/requirements*.txt') }}

# Docker layer cache
- uses: docker/build-push-action@v5
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

---

## 🚨 Error Handling

### **Failure Recovery**
```yaml
- name: Handle Pipeline Failure
  if: failure()
  run: |
    # Send failure notification
    curl -X POST -H 'Content-type: application/json' \
      --data '{"text":"CI/CD Pipeline failed for ${{ github.repository }}#${{ github.run_number }}"}' \
      ${{ secrets.SLACK_WEBHOOK_URL }}
    
    # Collect failure logs
    kubectl logs --all-namespaces --tail=100 > failure-logs.txt
    
    # Upload failure artifacts
    actions/upload-artifact@v4
      with:
        name: failure-logs
        path: failure-logs.txt
```

### **Rollback Strategy**
```yaml
- name: Rollback on Failure
  if: failure()
  run: |
    # Rollback to previous deployment
    kubectl rollout undo deployment/self-healing-controller -n self-healing
    
    # Verify rollback
    kubectl rollout status deployment/self-healing-controller -n self-healing
    
    # Send rollback notification
    curl -X POST -H 'Content-type: application/json' \
      --data '{"text":"Rolled back deployment due to CI/CD failure"}' \
      ${{ secrets.SLACK_WEBHOOK_URL }}
```

---

## 📈 Performance Optimization

### **Parallel Execution**
```yaml
strategy:
  matrix:
    tool: [python, terraform]
  fail-fast: false
```

### **Resource Optimization**
```yaml
# Use larger runners for heavy workloads
runs-on: ubuntu-latest

# Optimize Docker builds
- uses: docker/build-push-action@v5
  with:
    platforms: linux/amd64,linux/arm64
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

### **Timeouts and Limits**
```yaml
# Set appropriate timeouts
timeout-minutes: 30

# Resource limits for jobs
resource_class: large
```

---

<div align="center">

**[← Chaos Engineering](./chaos-engineering.md)** | **[Screenshots →](./screenshots.md)**

</div> 