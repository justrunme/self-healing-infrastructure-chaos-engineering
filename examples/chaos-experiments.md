# Chaos Engineering Experiments Examples

This document provides various chaos experiment examples to test the self-healing capabilities of your Kubernetes infrastructure.

## 1. Pod Failure Experiments

### Basic Pod Failure
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: basic-pod-failure
  namespace: test-app
spec:
  action: pod-failure
  mode: one
  selector:
    namespaces:
      - test-app
    labelSelectors:
      app: test-app
  duration: "30s"
```

### Pod Failure with Multiple Targets
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: multiple-pod-failure
  namespace: test-app
spec:
  action: pod-failure
  mode: fixed-percent
  value: "50"
  selector:
    namespaces:
      - test-app
    labelSelectors:
      app: test-app
  duration: "1m"
```

### Scheduled Pod Failure
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: scheduled-pod-failure
  namespace: test-app
spec:
  action: pod-failure
  mode: one
  selector:
    namespaces:
      - test-app
    labelSelectors:
      app: test-app
  duration: "30s"
  scheduler:
    cron: "@every 5m"
```

## 2. Network Chaos Experiments

### Network Delay
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: network-delay
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
    latency: "100ms"
    correlation: "100"
    jitter: "0ms"
  duration: "2m"
```

### Network Loss
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: network-loss
  namespace: test-app
spec:
  action: loss
  mode: one
  selector:
    namespaces:
      - test-app
    labelSelectors:
      app: test-app
  loss:
    loss: "25"
    correlation: "100"
  duration: "1m"
```

### Network Corruption
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: network-corruption
  namespace: test-app
spec:
  action: corrupt
  mode: one
  selector:
    namespaces:
      - test-app
    labelSelectors:
      app: test-app
  corrupt:
    corrupt: "1"
    correlation: "100"
  duration: "30s"
```

### Network Bandwidth Limit
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: network-bandwidth
  namespace: test-app
spec:
  action: bandwidth
  mode: one
  selector:
    namespaces:
      - test-app
    labelSelectors:
      app: test-app
  bandwidth:
    rate: "1mbps"
    limit: 2097152
    buffer: 10000
  duration: "2m"
```

## 3. Resource Stress Experiments

### CPU Stress
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: cpu-stress
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
      load: 50
      options: ["cpu-cores"]
  duration: "2m"
```

### Memory Stress
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: memory-stress
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
      size: "256MB"
  duration: "1m"
```

### Mixed CPU and Memory Stress
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: mixed-stress
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
      load: 30
    memory:
      workers: 1
      size: "128MB"
  duration: "3m"
```

## 4. Container Kill Experiments

### Basic Container Kill
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: container-kill
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
```

### Scheduled Container Kill
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: scheduled-container-kill
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
  scheduler:
    cron: "@every 3m"
```

## 5. Advanced Experiments

### Multi-Component Chaos
```yaml
# This experiment combines multiple chaos types
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: multi-chaos-pod
  namespace: test-app
spec:
  action: pod-failure
  mode: one
  selector:
    namespaces:
      - test-app
    labelSelectors:
      app: test-app
  duration: "30s"
---
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: multi-chaos-network
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
  duration: "1m"
```

### Chaos with Specific Pod Selection
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: specific-pod-chaos
  namespace: test-app
spec:
  action: pod-failure
  mode: one
  selector:
    namespaces:
      - test-app
    labelSelectors:
      app: test-app
      version: "v1"
    annotationSelectors:
      chaos-testing: "enabled"
  duration: "30s"
```

## 6. Production-Safe Experiments

### Gradual Pod Failure
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: gradual-pod-failure
  namespace: test-app
spec:
  action: pod-failure
  mode: fixed-percent
  value: "10"
  selector:
    namespaces:
      - test-app
    labelSelectors:
      app: test-app
  duration: "30s"
  scheduler:
    cron: "@every 10m"
```

### Safe Network Chaos
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: safe-network-chaos
  namespace: test-app
spec:
  action: delay
  mode: fixed-percent
  value: "20"
  selector:
    namespaces:
      - test-app
    labelSelectors:
      app: test-app
  delay:
    latency: "50ms"
    correlation: "100"
    jitter: "10ms"
  duration: "1m"
  scheduler:
    cron: "@every 15m"
```

## 7. Testing Scripts

### Automated Chaos Testing
```bash
#!/bin/bash

# Run a series of chaos experiments
echo "Starting chaos experiments..."

# Pod failure test
kubectl apply -f - <<EOF
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: test-pod-failure
  namespace: test-app
spec:
  action: pod-failure
  mode: one
  selector:
    namespaces:
      - test-app
    labelSelectors:
      app: test-app
  duration: "30s"
EOF

echo "Pod failure experiment created"
sleep 35

# Network delay test
kubectl apply -f - <<EOF
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: test-network-delay
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
    latency: "100ms"
    correlation: "100"
    jitter: "0ms"
  duration: "1m"
EOF

echo "Network delay experiment created"
sleep 65

# Clean up
kubectl delete podchaos test-pod-failure -n test-app
kubectl delete networkchaos test-network-delay -n test-app

echo "Chaos experiments completed"
```

## 8. Monitoring Chaos Experiments

### Check Experiment Status
```bash
# List all chaos experiments
kubectl get chaos -n test-app

# Get detailed information about an experiment
kubectl describe podchaos <experiment-name> -n test-app

# Check experiment logs
kubectl logs -n chaos-engineering -l app=chaos-mesh
```

### Monitor Recovery
```bash
# Watch pod status during chaos
kubectl get pods -n test-app -w

# Check self-healing controller logs
kubectl logs -n self-healing -l app=self-healing-controller -f

# Monitor metrics
kubectl port-forward -n self-healing svc/self-healing-controller 8080:8080
curl http://localhost:8080/metrics
```

## 9. Best Practices

### 1. Start Small
- Begin with single pod failures
- Gradually increase complexity
- Monitor system behavior closely

### 2. Use Scheduling
- Schedule experiments during low-traffic periods
- Use cron expressions for regular testing
- Avoid critical business hours

### 3. Monitor and Document
- Track experiment results
- Document lessons learned
- Update recovery procedures

### 4. Gradual Scaling
- Start with 1% of pods
- Increase to 5%, 10%, 25%
- Monitor system resilience

### 5. Clean Up
- Always clean up experiments
- Monitor for lingering effects
- Verify system health after experiments 