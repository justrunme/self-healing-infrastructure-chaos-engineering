#!/bin/bash

# Chaos Engineering Test Script
# This script runs various chaos experiments to test the self-healing capabilities

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

# Check if test app is running
check_test_app() {
    print_status "Checking test application status..."
    
    if kubectl get pods -n test-app | grep -q "Running"; then
        print_success "Test application is running"
        return 0
    else
        print_error "Test application is not running"
        return 1
    fi
}

# Test 1: Pod Failure
test_pod_failure() {
    print_status "Running Pod Failure Test..."
    
    # Get a random pod from test-app
    POD_NAME=$(kubectl get pods -n test-app -o jsonpath='{.items[0].metadata.name}')
    
    print_status "Deleting pod: $POD_NAME"
    kubectl delete pod $POD_NAME -n test-app
    
    # Wait for pod to be recreated
    print_status "Waiting for pod to be recreated..."
    sleep 30
    
    # Check if pod is running again
    if kubectl get pods -n test-app | grep -q "Running"; then
        print_success "Pod failure test passed - pod was recreated"
    else
        print_error "Pod failure test failed - pod was not recreated"
    fi
}

# Test 2: Node Pressure Simulation
test_node_pressure() {
    print_status "Running Node Pressure Test..."
    
    # Create a stress test pod
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: stress-test
  namespace: test-app
spec:
  containers:
  - name: stress
    image: busybox
    command: ["sh", "-c"]
    args:
    - |
      while true; do
        dd if=/dev/zero of=/tmp/stress bs=1M count=100
        sleep 10
      done
    resources:
      requests:
        memory: "100Mi"
        cpu: "100m"
      limits:
        memory: "200Mi"
        cpu: "200m"
EOF
    
    print_status "Stress test pod created. Running for 60 seconds..."
    sleep 60
    
    # Clean up stress test
    kubectl delete pod stress-test -n test-app
    
    print_success "Node pressure test completed"
}

# Test 3: Network Chaos
test_network_chaos() {
    print_status "Running Network Chaos Test..."
    
    # Create network chaos experiment
    cat <<EOF | kubectl apply -f -
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: network-delay-test
  namespace: test-app
spec:
  action: delay
  mode: one
  selector:
    namespaces:
      - test-app
    labelSelectors:
      app: test-app
  delay:
    latency: "200ms"
    correlation: "100"
    jitter: "0ms"
  duration: "30s"
EOF
    
    print_status "Network chaos experiment created. Running for 30 seconds..."
    sleep 30
    
    # Clean up
    kubectl delete networkchaos network-delay-test -n test-app
    
    print_success "Network chaos test completed"
}

# Test 4: CPU Stress
test_cpu_stress() {
    print_status "Running CPU Stress Test..."
    
    # Create CPU stress experiment
    cat <<EOF | kubectl apply -f -
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: cpu-stress-test
  namespace: test-app
spec:
  mode: one
  selector:
    namespaces:
      - test-app
    labelSelectors:
      app: test-app
  stressors:
    cpu:
      workers: 1
      load: 80
      options: ["cpu-cores"]
  duration: "30s"
EOF
    
    print_status "CPU stress experiment created. Running for 30 seconds..."
    sleep 30
    
    # Clean up
    kubectl delete stresschaos cpu-stress-test -n test-app
    
    print_success "CPU stress test completed"
}

# Test 5: Memory Stress
test_memory_stress() {
    print_status "Running Memory Stress Test..."
    
    # Create memory stress experiment
    cat <<EOF | kubectl apply -f -
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: memory-stress-test
  namespace: test-app
spec:
  mode: one
  selector:
    namespaces:
      - test-app
    labelSelectors:
      app: test-app
  stressors:
    memory:
      workers: 1
      size: "100MB"
  duration: "30s"
EOF
    
    print_status "Memory stress experiment created. Running for 30 seconds..."
    sleep 30
    
    # Clean up
    kubectl delete stresschaos memory-stress-test -n test-app
    
    print_success "Memory stress test completed"
}

# Test 6: Container Kill
test_container_kill() {
    print_status "Running Container Kill Test..."
    
    # Create container kill experiment
    cat <<EOF | kubectl apply -f -
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: container-kill-test
  namespace: test-app
spec:
  action: container-kill
  mode: one
  selector:
    namespaces:
      - test-app
    labelSelectors:
      app: test-app
  containerNames:
    - test-app
  duration: "10s"
EOF
    
    print_status "Container kill experiment created. Running for 10 seconds..."
    sleep 10
    
    # Clean up
    kubectl delete podchaos container-kill-test -n test-app
    
    print_success "Container kill test completed"
}

# Check system health after tests
check_system_health() {
    print_status "Checking system health after chaos tests..."
    
    # Check if all pods are running
    if kubectl get pods -n test-app | grep -v "Running" | grep -v "NAME"; then
        print_warning "Some pods are not in Running state"
    else
        print_success "All test app pods are running"
    fi
    
    # Check if self-healing controller is running
    if kubectl get pods -n self-healing | grep -q "Running"; then
        print_success "Self-healing controller is running"
    else
        print_error "Self-healing controller is not running"
    fi
    
    # Check if monitoring is working
    if kubectl get pods -n monitoring | grep -q "Running"; then
        print_success "Monitoring stack is running"
    else
        print_error "Monitoring stack is not running"
    fi
}

# Show test results
show_test_results() {
    print_status "Chaos Test Results:"
    echo ""
    
    print_status "Test Application Status:"
    kubectl get pods -n test-app
    echo ""
    
    print_status "Self-Healing Controller Logs:"
    kubectl logs -n self-healing -l app=self-healing-controller --tail=20
    echo ""
    
    print_status "Chaos Mesh Status:"
    kubectl get chaos -n test-app
    echo ""
}

# Main test function
main() {
    print_status "Starting Chaos Engineering Tests..."
    echo ""
    
    # Check prerequisites
    if ! check_test_app; then
        print_error "Test application is not ready. Please deploy it first."
        exit 1
    fi
    
    # Run chaos tests
    test_pod_failure
    echo ""
    
    test_node_pressure
    echo ""
    
    test_network_chaos
    echo ""
    
    test_cpu_stress
    echo ""
    
    test_memory_stress
    echo ""
    
    test_container_kill
    echo ""
    
    # Check system health
    check_system_health
    echo ""
    
    # Show results
    show_test_results
    echo ""
    
    print_success "Chaos Engineering tests completed!"
    print_status "Check the logs and monitoring dashboards for detailed results."
}

# Run main function
main "$@" 