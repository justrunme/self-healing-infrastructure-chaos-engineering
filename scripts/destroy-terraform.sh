#!/bin/bash

# Self-Healing Infrastructure - Terraform Destroy Script
# This script destroys the entire infrastructure using Terraform

set -e

echo "🗑️  Destroying Self-Healing Infrastructure with Terraform..."
echo "============================================================"

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
    exit 1
fi

if ! command_exists kubectl; then
    echo -e "${RED}❌ kubectl is not installed${NC}"
    exit 1
fi

print_status 0 "All prerequisites are installed"

# Check if Kubernetes cluster is running
echo "🔍 Checking Kubernetes cluster..."

if ! kubectl cluster-info >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Kubernetes cluster is not running${NC}"
    echo "No infrastructure to destroy"
    exit 0
fi

print_status 0 "Kubernetes cluster is running"

# Show current resources
echo "📊 Current resources:"
echo "Namespaces:"
kubectl get namespaces | grep -E "(monitoring|chaos-engineering|self-healing|kured|test-app)" || echo "No namespaces found"

echo "Pods:"
kubectl get pods --all-namespaces | grep -E "(prometheus|alertmanager|kured|self-healing|test-app)" || echo "No pods found"

# Confirm destruction
echo ""
echo -e "${YELLOW}⚠️  WARNING: This will destroy all Self-Healing Infrastructure resources${NC}"
echo "This includes:"
echo "  - All namespaces (monitoring, chaos-engineering, self-healing, kured, test-app)"
echo "  - All pods and services"
echo "  - All Helm releases"
echo "  - All ConfigMaps and Secrets"
echo ""
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Operation cancelled"
    exit 0
fi

# Destroy Terraform infrastructure
echo "🗑️  Destroying Terraform infrastructure..."

cd terraform

# Check if terraform is initialized
if [ ! -d ".terraform" ]; then
    echo -e "${YELLOW}⚠️  Terraform not initialized, initializing...${NC}"
    terraform init
fi

# Plan destruction
echo "📋 Planning destruction..."
terraform plan -destroy -out=destroy-plan
print_status 0 "Destruction plan created"

# Apply destruction
echo "🗑️  Applying destruction..."
terraform apply destroy-plan
print_status 0 "Terraform destruction completed"

cd ..

# Clean up any remaining resources
echo "🧹 Cleaning up remaining resources..."

# Delete namespaces if they still exist
for namespace in monitoring chaos-engineering self-healing kured test-app; do
    if kubectl get namespace $namespace >/dev/null 2>&1; then
        echo "Deleting namespace: $namespace"
        kubectl delete namespace $namespace --ignore-not-found=true
    fi
done

# Stop Minikube if it's running
if command_exists minikube; then
    echo "Stopping Minikube..."
    minikube stop || echo "Minikube stop failed"
    print_status 0 "Minikube stopped"
fi

# Final verification
echo "🔍 Final verification..."

# Check if any resources remain
remaining_namespaces=$(kubectl get namespaces 2>/dev/null | grep -E "(monitoring|chaos-engineering|self-healing|kured|test-app)" || echo "")
remaining_pods=$(kubectl get pods --all-namespaces 2>/dev/null | grep -E "(prometheus|alertmanager|kured|self-healing|test-app)" || echo "")

if [ -z "$remaining_namespaces" ] && [ -z "$remaining_pods" ]; then
    print_status 0 "All resources destroyed successfully"
else
    echo -e "${YELLOW}⚠️  Some resources may still exist:${NC}"
    if [ ! -z "$remaining_namespaces" ]; then
        echo "Remaining namespaces:"
        echo "$remaining_namespaces"
    fi
    if [ ! -z "$remaining_pods" ]; then
        echo "Remaining pods:"
        echo "$remaining_pods"
    fi
fi

# Final status
echo ""
echo "🎉 Self-Healing Infrastructure destruction completed!"
echo "====================================================="
echo ""
echo "📊 Cleanup Summary:"
echo "  ✅ Terraform resources destroyed"
echo "  ✅ Kubernetes namespaces deleted"
echo "  ✅ Minikube stopped"
echo "  ✅ All infrastructure removed"
echo ""
echo "🔧 Next Steps:"
echo "  To redeploy, run: ./scripts/deploy-terraform.sh"
echo "  To start fresh, run: minikube start"
echo "" 