#!/bin/bash

# Self-Healing Infrastructure Deployment Script
# This script deploys the complete self-healing infrastructure

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if kubectl is installed
check_kubectl() {
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed. Please install kubectl first."
        exit 1
    fi
    print_success "kubectl found"
}

# Check if helm is installed
check_helm() {
    if ! command -v helm &> /dev/null; then
        print_error "helm is not installed. Please install helm first."
        exit 1
    fi
    print_success "helm found"
}

# Check if minikube is running
check_minikube() {
    if ! minikube status | grep -q "Running"; then
        print_warning "Minikube is not running. Starting minikube..."
        minikube start --driver=docker --cpus=4 --memory=8192
    fi
    print_success "Minikube is running"
}

# Deploy Terraform infrastructure
deploy_terraform() {
    print_status "Deploying Terraform infrastructure..."
    cd terraform
    
    # Initialize Terraform
    terraform init
    
    # Apply Terraform configuration
    terraform apply -auto-approve
    
    cd ..
    print_success "Terraform infrastructure deployed"
}

# Deploy monitoring stack
deploy_monitoring() {
    print_status "Deploying monitoring stack..."
    
    # Create monitoring namespace
    kubectl apply -f kubernetes/monitoring/prometheus-config.yaml
    kubectl apply -f kubernetes/monitoring/alertmanager-config.yaml
    
    # Deploy Prometheus using Helm
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo update
    
    helm install prometheus prometheus-community/kube-prometheus-stack \
        --namespace monitoring \
        --create-namespace \
        --set prometheus.prometheusSpec.retention=7d \
        --set grafana.enabled=true \
        --set grafana.adminPassword=admin123
    
    print_success "Monitoring stack deployed"
}

# Deploy Chaos Mesh
deploy_chaos_mesh() {
    print_status "Deploying Chaos Mesh..."
    
    kubectl apply -f kubernetes/chaos-engineering/chaos-mesh.yaml
    
    # Wait for Chaos Mesh to be ready
    kubectl wait --for=condition=ready pod -l app=chaos-mesh -n chaos-engineering --timeout=300s
    
    print_success "Chaos Mesh deployed"
}

# Deploy Kured
deploy_kured() {
    print_status "Deploying Kured..."
    
    kubectl apply -f kubernetes/kured/kured.yaml
    
    # Wait for Kured to be ready
    kubectl wait --for=condition=ready pod -l app=kured -n kured --timeout=300s
    
    print_success "Kured deployed"
}

# Build and deploy Self-Healing Controller
deploy_self_healing_controller() {
    print_status "Building Self-Healing Controller..."
    
    # Build Docker image
    cd kubernetes/self-healing
    docker build -t self-healing-controller:latest .
    
    # Load image into minikube
    minikube image load self-healing-controller:latest
    
    cd ../..
    
    print_status "Deploying Self-Healing Controller..."
    kubectl apply -f kubernetes/self-healing/deployment.yaml
    
    # Wait for Self-Healing Controller to be ready
    kubectl wait --for=condition=ready pod -l app=self-healing-controller -n self-healing --timeout=300s
    
    print_success "Self-Healing Controller deployed"
}

# Deploy test application
deploy_test_app() {
    print_status "Deploying test application..."
    
    kubectl apply -f kubernetes/test-app/test-app.yaml
    
    # Wait for test app to be ready
    kubectl wait --for=condition=ready pod -l app=test-app -n test-app --timeout=300s
    
    print_success "Test application deployed"
}

# Deploy Chaos experiments
deploy_chaos_experiments() {
    print_status "Deploying Chaos experiments..."
    
    kubectl apply -f kubernetes/chaos-engineering/chaos-experiments.yaml
    
    print_success "Chaos experiments deployed"
}

# Show deployment status
show_status() {
    print_status "Deployment Status:"
    echo ""
    
    print_status "Namespaces:"
    kubectl get namespaces | grep -E "(monitoring|chaos-engineering|self-healing|kured|test-app)"
    echo ""
    
    print_status "Pods:"
    kubectl get pods --all-namespaces | grep -E "(prometheus|alertmanager|chaos-mesh|kured|self-healing|test-app)"
    echo ""
    
    print_status "Services:"
    kubectl get services --all-namespaces | grep -E "(prometheus|alertmanager|chaos-mesh|kured|self-healing|test-app)"
    echo ""
}

# Show access information
show_access_info() {
    print_status "Access Information:"
    echo ""
    
    print_status "Prometheus UI:"
    echo "  kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090"
    echo "  http://localhost:9090"
    echo ""
    
    print_status "Grafana UI:"
    echo "  kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80"
    echo "  http://localhost:3000 (admin/admin123)"
    echo ""
    
    print_status "Alertmanager UI:"
    echo "  kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-alertmanager 9093:9093"
    echo "  http://localhost:9093"
    echo ""
    
    print_status "Chaos Mesh UI:"
    echo "  kubectl port-forward -n chaos-engineering svc/chaos-mesh-controller-manager 2333:10080"
    echo "  http://localhost:2333"
    echo ""
    
    print_status "Test Application:"
    echo "  kubectl port-forward -n test-app svc/test-app 8080:80"
    echo "  http://localhost:8080"
    echo ""
}

# Main deployment function
main() {
    print_status "Starting Self-Healing Infrastructure deployment..."
    echo ""
    
    # Check prerequisites
    check_kubectl
    check_helm
    check_minikube
    echo ""
    
    # Deploy components
    deploy_terraform
    echo ""
    
    deploy_monitoring
    echo ""
    
    deploy_chaos_mesh
    echo ""
    
    deploy_kured
    echo ""
    
    deploy_self_healing_controller
    echo ""
    
    deploy_test_app
    echo ""
    
    deploy_chaos_experiments
    echo ""
    
    # Show status and access info
    show_status
    echo ""
    show_access_info
    echo ""
    
    print_success "Self-Healing Infrastructure deployment completed successfully!"
    print_status "You can now start testing the system with Chaos experiments."
}

# Run main function
main "$@" 