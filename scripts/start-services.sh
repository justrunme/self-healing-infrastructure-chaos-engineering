#!/bin/bash

# Self-Healing Infrastructure - Service Starter
# This script starts port forwarding for all services

echo "🚀 Starting Self-Healing Infrastructure Services..."
echo "=================================================="

# Kill any existing port-forward processes
echo "Cleaning up existing port-forward processes..."
pkill -f "kubectl port-forward" 2>/dev/null || true
sleep 2

# Start port forwarding for all services
echo "Starting port forwarding..."

# Grafana
echo "📊 Starting Grafana (http://localhost:3000)..."
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80 >/dev/null 2>&1 &
GRAFANA_PID=$!

# Prometheus
echo "📈 Starting Prometheus (http://localhost:9090)..."
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090 >/dev/null 2>&1 &
PROMETHEUS_PID=$!

# Alertmanager
echo "🚨 Starting Alertmanager (http://localhost:9093)..."
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-alertmanager 9093:9093 >/dev/null 2>&1 &
ALERTMANAGER_PID=$!

# Test Application
echo "🧪 Starting Test Application (http://localhost:8080)..."
kubectl port-forward -n test-app svc/test-app 8080:80 >/dev/null 2>&1 &
TESTAPP_PID=$!

# Self-Healing Controller
echo "🔧 Starting Self-Healing Controller (http://localhost:8081)..."
kubectl port-forward -n self-healing svc/self-healing-controller 8081:8080 >/dev/null 2>&1 &
CONTROLLER_PID=$!

# Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 5

# Test services
echo "🧪 Testing services..."
echo ""

# Test Grafana
if curl -s http://localhost:3000 >/dev/null 2>&1; then
    echo "✅ Grafana: http://localhost:3000 (admin/admin)"
else
    echo "❌ Grafana: Not accessible"
fi

# Test Prometheus
if curl -s http://localhost:9090/api/v1/query?query=up >/dev/null 2>&1; then
    echo "✅ Prometheus: http://localhost:9090"
else
    echo "❌ Prometheus: Not accessible"
fi

# Test Alertmanager
if curl -s http://localhost:9093 >/dev/null 2>&1; then
    echo "✅ Alertmanager: http://localhost:9093"
else
    echo "❌ Alertmanager: Not accessible"
fi

# Test Test Application
if curl -s http://localhost:8080 >/dev/null 2>&1; then
    echo "✅ Test Application: http://localhost:8080"
else
    echo "❌ Test Application: Not accessible"
fi

# Test Self-Healing Controller
if curl -s http://localhost:8081/health >/dev/null 2>&1; then
    echo "✅ Self-Healing Controller: http://localhost:8081/health"
else
    echo "❌ Self-Healing Controller: Not accessible"
fi

echo ""
echo "🎯 Quick Access:"
echo "================"
echo "📊 Grafana Dashboard: http://localhost:3000"
echo "📈 Prometheus Metrics: http://localhost:9090"
echo "🚨 Alertmanager: http://localhost:9093"
echo "🧪 Test Application: http://localhost:8080"
echo "🔧 Self-Healing Controller: http://localhost:8081/health"
echo "📊 Self-Healing Metrics: http://localhost:8081/metrics"

echo ""
echo "🔍 Useful Commands:"
echo "==================="
echo "kubectl get pods --all-namespaces | grep -E '(monitoring|self-healing|test-app)'"
echo "kubectl logs -n self-healing deployment/self-healing-controller"
echo "kubectl get events --all-namespaces --sort-by='.lastTimestamp'"

echo ""
echo "🛑 To stop all services, run:"
echo "pkill -f 'kubectl port-forward'"

echo ""
echo "🎉 All services are running!"
echo "Press Ctrl+C to stop this script (services will continue running in background)"

# Store PIDs for cleanup
echo $GRAFANA_PID > /tmp/grafana.pid
echo $PROMETHEUS_PID > /tmp/prometheus.pid
echo $ALERTMANAGER_PID > /tmp/alertmanager.pid
echo $TESTAPP_PID > /tmp/testapp.pid
echo $CONTROLLER_PID > /tmp/controller.pid

# Keep script running
trap 'echo "Stopping services..."; pkill -f "kubectl port-forward"; exit' INT
while true; do
    sleep 10
done 