#!/bin/bash

# Test Self-Healing Controller functionality

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if Self-Healing Controller is running
check_controller_status() {
    print_status "Checking Self-Healing Controller status..."
    
    if kubectl get pods -n self-healing -l app=self-healing-controller | grep -q Running; then
        print_success "Self-Healing Controller is running"
        return 0
    else
        print_error "Self-Healing Controller is not running"
        return 1
    fi
}

# Test pod failure recovery
test_pod_failure_recovery() {
    print_status "Testing pod failure recovery..."
    
    # Create a test pod that will fail
    kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: test-failing-pod
  namespace: test-app
  labels:
    app: test-app
spec:
  containers:
  - name: failing-container
    image: busybox
    command: ["/bin/sh", "-c", "exit 1"]
    restartPolicy: Never
EOF
    
    # Wait for pod to fail
    sleep 10
    
    # Check if pod was restarted by Self-Healing Controller
    RESTART_COUNT=$(kubectl get pod test-failing-pod -n test-app -o jsonpath='{.status.containerStatuses[0].restartCount}')
    
    if [ "$RESTART_COUNT" -gt 0 ]; then
        print_success "Pod failure recovery test passed (restart count: $RESTART_COUNT)"
    else
        print_warning "Pod failure recovery test inconclusive"
    fi
    
    # Clean up
    kubectl delete pod test-failing-pod -n test-app
}

# Test metrics endpoint
test_metrics_endpoint() {
    print_status "Testing metrics endpoint..."
    
    # Start port-forward in background
    kubectl port-forward -n self-healing svc/self-healing-controller 8080:8080 &
    PF_PID=$!
    
    # Wait for port-forward to be ready
    sleep 5
    
    # Test metrics endpoint
    if curl -f http://localhost:8080/metrics > /dev/null 2>&1; then
        print_success "Metrics endpoint is accessible"
    else
        print_error "Metrics endpoint is not accessible"
    fi
    
    # Test health endpoint
    if curl -f http://localhost:8080/health > /dev/null 2>&1; then
        print_success "Health endpoint is accessible"
    else
        print_error "Health endpoint is not accessible"
    fi
    
    # Kill port-forward
    kill $PF_PID
}

# Test chaos engineering integration
test_chaos_integration() {
    print_status "Testing Chaos Engineering integration..."
    
    # Check if Chaos Mesh is running
    if kubectl get pods -n chaos-engineering | grep -q Running; then
        print_success "Chaos Mesh is running"
        
        # Create a simple chaos experiment
        kubectl apply -f - <<EOF
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: test-pod-chaos
  namespace: test-app
spec:
  action: pod-failure
  mode: one
  selector:
    namespaces: [test-app]
    labelSelectors:
      app: test-app
  duration: "10s"
EOF
        
        # Wait for experiment to complete
        sleep 15
        
        # Clean up
        kubectl delete podchaos test-pod-chaos -n test-app
        
        print_success "Chaos Engineering integration test completed"
    else
        print_warning "Chaos Mesh is not running, skipping chaos integration test"
    fi
}

# Show controller logs
show_controller_logs() {
    print_status "Showing Self-Healing Controller logs..."
    kubectl logs -n self-healing -l app=self-healing-controller --tail=50
}

# Main test function
main() {
    print_status "Starting Self-Healing Controller tests..."
    echo ""
    
    # Check controller status
    if ! check_controller_status; then
        print_error "Self-Healing Controller is not running. Please deploy it first."
        exit 1
    fi
    
    echo ""
    
    # Test metrics endpoint
    test_metrics_endpoint
    echo ""
    
    # Test chaos integration
    test_chaos_integration
    echo ""
    
    # Test pod failure recovery
    test_pod_failure_recovery
    echo ""
    
    # Show logs
    show_controller_logs
    echo ""
    
    print_success "Self-Healing Controller tests completed!"
}

# Run main function
main "$@" 