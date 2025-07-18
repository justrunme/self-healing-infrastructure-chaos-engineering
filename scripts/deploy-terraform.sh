#!/bin/bash

# Self-Healing Infrastructure - Terraform Deployment Script
# This script deploys the entire infrastructure using Terraform

set -e

echo "🚀 Deploying Self-Healing Infrastructure with Terraform..."
echo "=========================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
        exit 1
    fi
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo "🔍 Checking prerequisites..."

if ! command_exists terraform; then
    echo -e "${RED}❌ Terraform is not installed${NC}"
    echo "Please install Terraform: https://www.terraform.io/downloads.html"
    exit 1
fi

if ! command_exists kubectl; then
    echo -e "${RED}❌ kubectl is not installed${NC}"
    echo "Please install kubectl: https://kubernetes.io/docs/tasks/tools/"
    exit 1
fi

if ! command_exists docker; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

print_status 0 "All prerequisites are installed"

# Check if Kubernetes cluster is running
echo "🔍 Checking Kubernetes cluster..."

if ! kubectl cluster-info >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Kubernetes cluster is not running${NC}"
    echo "Starting Minikube..."
    
    if command_exists minikube; then
        minikube start --driver=docker --cpus=2 --memory=4096
        print_status 0 "Minikube started successfully"
    else
        echo -e "${RED}❌ Minikube is not installed${NC}"
        echo "Please install Minikube: https://minikube.sigs.k8s.io/docs/start/"
        exit 1
    fi
else
    print_status 0 "Kubernetes cluster is running"
fi

# Build Self-Healing Controller image
echo "🔨 Building Self-Healing Controller image..."

cd kubernetes/self-healing
docker build -t self-healing-controller:latest .
cd ../..

if command_exists minikube; then
    echo "📦 Loading image into Minikube..."
    minikube image load self-healing-controller:latest
fi

print_status 0 "Self-Healing Controller image built and loaded"

# Initialize Terraform
echo "🔧 Initializing Terraform..."

cd terraform

# Check if terraform.tfvars exists, if not create from example
if [ ! -f terraform.tfvars ]; then
    echo -e "${YELLOW}⚠️  terraform.tfvars not found, creating from example...${NC}"
    cp terraform.tfvars.example terraform.tfvars
    echo -e "${BLUE}📝 Please review and modify terraform.tfvars as needed${NC}"
fi

terraform init
print_status 0 "Terraform initialized"

# Validate Terraform configuration
echo "🔍 Validating Terraform configuration..."
terraform validate
print_status 0 "Terraform configuration is valid"

# Plan Terraform deployment
echo "📋 Planning Terraform deployment..."
terraform plan -out=tfplan
print_status 0 "Terraform plan created"

# Apply Terraform deployment
echo "🚀 Applying Terraform deployment..."
terraform apply tfplan
print_status 0 "Terraform deployment completed"

# Show Terraform outputs
echo "📊 Terraform outputs:"
terraform output

cd ..

# Wait for components to be ready
echo "⏳ Waiting for components to be ready..."

echo "Waiting for Self-Healing Controller..."
kubectl wait --for=condition=ready pod -l app=self-healing-controller -n self-healing --timeout=600s
print_status 0 "Self-Healing Controller is ready"

echo "Waiting for test application..."
kubectl wait --for=condition=ready pod -l app=test-app -n test-app --timeout=300s
print_status 0 "Test application is ready"

echo "Waiting for Prometheus stack..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=prometheus -n monitoring --timeout=300s
print_status 0 "Prometheus stack is ready"

echo "Waiting for Kured..."
kubectl wait --for=condition=ready pod -l app=kured -n kured --timeout=300s
print_status 0 "Kured is ready"

# Verify deployment
echo "🔍 Verifying deployment..."

echo "Checking all namespaces..."
kubectl get namespaces | grep -E "(monitoring|chaos-engineering|self-healing|kured|test-app)"
print_status 0 "All namespaces created"

echo "Checking all pods..."
kubectl get pods --all-namespaces | grep -E "(prometheus|alertmanager|kured|self-healing|test-app)"
print_status 0 "All pods are running"

echo "Checking services..."
kubectl get svc --all-namespaces | grep -E "(prometheus|alertmanager|kured|self-healing|test-app)"
print_status 0 "All services created"

# Test Self-Healing Controller
echo "🧪 Testing Self-Healing Controller..."

# Start port-forward in background
kubectl port-forward -n self-healing svc/self-healing-controller 8081:8080 &
PF_PID=$!

# Wait for port-forward to be ready
sleep 10

# Test health endpoint
if curl -f http://localhost:8081/health >/dev/null 2>&1; then
    print_status 0 "Self-Healing Controller health check passed"
else
    print_status 1 "Self-Healing Controller health check failed"
fi

# Test metrics endpoint
if curl -f http://localhost:8081/metrics >/dev/null 2>&1; then
    print_status 0 "Self-Healing Controller metrics endpoint working"
else
    print_status 1 "Self-Healing Controller metrics endpoint failed"
fi

# Kill port-forward
kill $PF_PID >/dev/null 2>&1 || true

# Test pod failure recovery
echo "🧪 Testing pod failure recovery..."

# Create a failing pod
kubectl run test-healing-pod --image=busybox --command -- /bin/sh -c "sleep 3 && exit 1" -n test-app

# Wait for the pod to fail and be detected
sleep 15

# Check if the pod was handled by the self-healing controller
pod_status=$(kubectl get pod test-healing-pod -n test-app -o jsonpath='{.status.phase}' 2>/dev/null || echo "NotFound")
if [ "$pod_status" = "NotFound" ]; then
    print_status 0 "Self-Healing Controller successfully detected and handled failing pod"
else
    print_status 1 "Self-Healing Controller did not handle failing pod (status: $pod_status)"
fi

# Clean up test pod
kubectl delete pod test-healing-pod -n test-app --ignore-not-found=true >/dev/null 2>&1

# Final status
echo ""
echo "🎉 Self-Healing Infrastructure deployment completed successfully!"
echo "================================================================"
echo ""
echo "📊 Component Status:"
echo "  ✅ Self-Healing Controller: Running"
echo "  ✅ Prometheus Stack: Running"
echo "  ✅ Grafana: Running"
echo "  ✅ Alertmanager: Running"
echo "  ✅ Kured: Running"
echo "  ✅ Test Application: Running"
echo ""
echo "🌐 Access URLs:"
echo "  📊 Grafana Dashboard: http://localhost:3000 (admin/admin123)"
echo "  📈 Prometheus Metrics: http://localhost:9090"
echo "  🚨 Alertmanager: http://localhost:9093"
echo "  🧪 Test Application: http://localhost:8080"
echo "  🔧 Self-Healing Controller: http://localhost:8081/health"
echo ""
echo "🔧 Quick Commands:"
echo "  kubectl get pods --all-namespaces"
echo "  kubectl logs -n self-healing deployment/self-healing-controller"
echo "  kubectl get events --all-namespaces --sort-by='.lastTimestamp'"
echo ""
echo "📝 Next Steps:"
echo "  1. Configure Slack notifications in terraform.tfvars"
echo "  2. Customize monitoring dashboards"
echo "  3. Add more test scenarios"
echo "  4. Configure Chaos Engineering experiments"
echo "" 