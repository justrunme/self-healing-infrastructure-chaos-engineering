# Troubleshooting Guide

This guide provides solutions for common issues encountered with the Self-Healing Infrastructure.

## Table of Contents

1. [Self-Healing Controller Issues](#self-healing-controller-issues)
2. [Monitoring Stack Issues](#monitoring-stack-issues)
3. [Chaos Engineering Issues](#chaos-engineering-issues)
4. [Network Policy Issues](#network-policy-issues)
5. [Backup System Issues](#backup-system-issues)
6. [Terraform Deployment Issues](#terraform-deployment-issues)
7. [Performance Issues](#performance-issues)
8. [Security Issues](#security-issues)

## Self-Healing Controller Issues

### Controller Not Starting

**Symptoms**: Self-Healing Controller pod is in `CrashLoopBackOff` or `Pending` state.

**Diagnosis**:
```bash
# Check pod status
kubectl get pods -n self-healing

# Check pod logs
kubectl logs -n self-healing -l app=self-healing-controller

# Check pod events
kubectl describe pod -n self-healing -l app=self-healing-controller
```

**Common Causes and Solutions**:

1. **Missing Service Account**:
   ```bash
   # Check if service account exists
   kubectl get serviceaccount -n self-healing
   
   # Create if missing
   kubectl apply -f kubernetes/self-healing/service-account.yaml
   ```

2. **Insufficient Resources**:
   ```bash
   # Check node resources
   kubectl top nodes
   
   # Check pod resource requests
   kubectl describe pod -n self-healing -l app=self-healing-controller
   ```

3. **Configuration Issues**:
   ```bash
   # Check ConfigMap
   kubectl get configmap -n self-healing self-healing-config -o yaml
   
   # Check environment variables
   kubectl exec -n self-healing -l app=self-healing-controller -- env
   ```

### Controller Not Detecting Failures

**Symptoms**: Pod failures are not being detected or recovered.

**Diagnosis**:
```bash
# Check controller logs
kubectl logs -n self-healing -l app=self-healing-controller -f

# Check controller metrics
curl http://localhost:8081/metrics

# Check pod status
kubectl get pods --all-namespaces
```

**Solutions**:

1. **Check RBAC Permissions**:
   ```bash
   # Verify cluster role binding
   kubectl get clusterrolebinding self-healing-controller
   
   # Check permissions
   kubectl auth can-i get pods --as=system:serviceaccount:self-healing:self-healing-controller
   ```

2. **Verify Configuration**:
   ```bash
   # Check failure thresholds
   kubectl get configmap -n self-healing self-healing-config -o yaml
   ```

### Health Endpoint Not Responding

**Symptoms**: `/health` endpoint returns errors or timeouts.

**Diagnosis**:
```bash
# Test health endpoint
curl -v http://localhost:8081/health

# Check if port forwarding is active
kubectl port-forward -n self-healing svc/self-healing-controller 8081:8080
```

**Solutions**:

1. **Restart Controller**:
   ```bash
   kubectl rollout restart deployment/self-healing-controller -n self-healing
   ```

2. **Check Resource Limits**:
   ```bash
   kubectl describe pod -n self-healing -l app=self-healing-controller
   ```

## Monitoring Stack Issues

### Prometheus Not Scraping Metrics

**Symptoms**: No metrics visible in Prometheus or Grafana.

**Diagnosis**:
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Check Prometheus logs
kubectl logs -n monitoring -l app.kubernetes.io/name=prometheus

# Check service discovery
kubectl get endpoints -n monitoring
```

**Solutions**:

1. **Check Service Monitors**:
   ```bash
   kubectl get servicemonitor -n monitoring
   ```

2. **Verify Service Labels**:
   ```bash
   kubectl get svc --show-labels -n self-healing
   ```

### Grafana Not Accessible

**Symptoms**: Cannot access Grafana dashboard.

**Diagnosis**:
```bash
# Check Grafana pod status
kubectl get pods -n monitoring -l app.kubernetes.io/name=grafana

# Check Grafana logs
kubectl logs -n monitoring -l app.kubernetes.io/name=grafana

# Check service
kubectl get svc -n monitoring prometheus-grafana
```

**Solutions**:

1. **Reset Grafana Password**:
   ```bash
   kubectl get secret -n monitoring prometheus-grafana -o jsonpath="{.data.admin-password}" | base64 -d
   ```

2. **Check Persistent Volume**:
   ```bash
   kubectl get pvc -n monitoring
   ```

### Alertmanager Not Sending Notifications

**Symptoms**: Alerts are not being sent to Slack.

**Diagnosis**:
```bash
# Check Alertmanager status
curl http://localhost:9093/api/v2/status

# Check Alertmanager logs
kubectl logs -n monitoring -l app.kubernetes.io/name=alertmanager

# Check Slack webhook
kubectl get secret -n monitoring slack-secret -o yaml
```

**Solutions**:

1. **Verify Slack Webhook**:
   ```bash
   # Test webhook manually
   curl -X POST -H 'Content-type: application/json' \
     --data '{"text":"Test message"}' \
     YOUR_SLACK_WEBHOOK_URL
   ```

2. **Check Alertmanager Configuration**:
   ```bash
   kubectl get configmap -n monitoring prometheus-kube-prometheus-alertmanager -o yaml
   ```

## Chaos Engineering Issues

### Chaos Mesh Not Working

**Symptoms**: Chaos experiments are not being applied or executed.

**Diagnosis**:
```bash
# Check Chaos Mesh pods
kubectl get pods -n chaos-engineering

# Check Chaos Mesh logs
kubectl logs -n chaos-engineering -l app=chaos-mesh

# Check chaos experiments
kubectl get chaos -n test-app
```

**Solutions**:

1. **Reinstall Chaos Mesh**:
   ```bash
   kubectl delete -f kubernetes/chaos-engineering/chaos-mesh.yaml
   kubectl apply -f kubernetes/chaos-engineering/chaos-mesh.yaml
   ```

2. **Check CRDs**:
   ```bash
   kubectl get crd | grep chaos
   ```

### Chaos Experiments Not Affecting Pods

**Symptoms**: Chaos experiments are created but pods are not affected.

**Diagnosis**:
```bash
# Check experiment status
kubectl describe chaos -n test-app

# Check pod labels
kubectl get pods -n test-app --show-labels
```

**Solutions**:

1. **Verify Selectors**:
   ```bash
   # Check if pod labels match experiment selectors
   kubectl get chaos -n test-app -o yaml
   ```

2. **Check Namespace**:
   ```bash
   # Ensure experiments target correct namespace
   kubectl get chaos --all-namespaces
   ```

## Network Policy Issues

### Pods Cannot Communicate

**Symptoms**: Pods cannot reach each other or external services.

**Diagnosis**:
```bash
# Check network policies
kubectl get networkpolicy --all-namespaces

# Test connectivity
kubectl exec -n test-app -it <pod-name> -- ping <target-pod>
```

**Solutions**:

1. **Temporarily Disable Network Policies**:
   ```bash
   kubectl delete networkpolicy --all-namespaces
   ```

2. **Check Policy Rules**:
   ```bash
   kubectl get networkpolicy -n self-healing -o yaml
   ```

### Service Discovery Issues

**Symptoms**: Services cannot be resolved within the cluster.

**Diagnosis**:
```bash
# Check DNS resolution
kubectl exec -n test-app -it <pod-name> -- nslookup <service-name>

# Check CoreDNS
kubectl get pods -n kube-system -l k8s-app=kube-dns
```

**Solutions**:

1. **Restart CoreDNS**:
   ```bash
   kubectl rollout restart deployment/coredns -n kube-system
   ```

2. **Check Service Endpoints**:
   ```bash
   kubectl get endpoints -n <namespace>
   ```

## Backup System Issues

### Backup CronJob Not Running

**Symptoms**: Backup jobs are not being created or are failing.

**Diagnosis**:
```bash
# Check CronJob status
kubectl get cronjob -n monitoring infrastructure-backup

# Check job history
kubectl get jobs -n monitoring

# Check job logs
kubectl logs -n monitoring job/infrastructure-backup-<timestamp>
```

**Solutions**:

1. **Check RBAC**:
   ```bash
   kubectl get clusterrole backup-role
   kubectl get clusterrolebinding backup-role-binding
   ```

2. **Verify PVC**:
   ```bash
   kubectl get pvc -n monitoring backup-pvc
   ```

### Backup Storage Issues

**Symptoms**: Backups are not being saved or are corrupted.

**Diagnosis**:
```bash
# Check PVC status
kubectl describe pvc -n monitoring backup-pvc

# Check storage class
kubectl get storageclass
```

**Solutions**:

1. **Check Storage Class**:
   ```bash
   # Verify storage class exists
   kubectl get storageclass standard
   ```

2. **Increase Storage**:
   ```bash
   # Edit PVC to increase size
   kubectl patch pvc backup-pvc -n monitoring -p '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'
   ```

## Terraform Deployment Issues

### Terraform Plan Fails

**Symptoms**: `terraform plan` returns errors.

**Diagnosis**:
```bash
# Check Terraform version
terraform version

# Check provider versions
terraform providers
```

**Solutions**:

1. **Update Terraform**:
   ```bash
   # Update to latest version
   brew upgrade terraform  # macOS
   ```

2. **Reinitialize**:
   ```bash
   terraform init -upgrade
   ```

### Terraform Apply Fails

**Symptoms**: `terraform apply` fails with resource creation errors.

**Diagnosis**:
```bash
# Check Terraform state
terraform show

# Check resource status
kubectl get all --all-namespaces
```

**Solutions**:

1. **Clean State**:
   ```bash
   terraform destroy
   terraform apply
   ```

2. **Check Dependencies**:
   ```bash
   # Ensure all dependencies are met
   kubectl get nodes
   kubectl get namespaces
   ```

## Performance Issues

### High Resource Usage

**Symptoms**: Pods are consuming excessive CPU or memory.

**Diagnosis**:
```bash
# Check resource usage
kubectl top pods --all-namespaces

# Check node resources
kubectl top nodes

# Check pod metrics
kubectl describe pod -n self-healing -l app=self-healing-controller
```

**Solutions**:

1. **Adjust Resource Limits**:
   ```bash
   # Edit deployment to increase limits
   kubectl edit deployment self-healing-controller -n self-healing
   ```

2. **Scale Components**:
   ```bash
   # Scale down if needed
   kubectl scale deployment self-healing-controller -n self-healing --replicas=0
   ```

### Slow Response Times

**Symptoms**: Health checks or API calls are slow.

**Diagnosis**:
```bash
# Test response times
time curl http://localhost:8081/health

# Check pod logs for errors
kubectl logs -n self-healing -l app=self-healing-controller --tail=100
```

**Solutions**:

1. **Optimize Queries**:
   ```bash
   # Check for slow queries in logs
   kubectl logs -n self-healing -l app=self-healing-controller | grep -i slow
   ```

2. **Increase Resources**:
   ```bash
   # Add more CPU/memory
   kubectl patch deployment self-healing-controller -n self-healing -p '{"spec":{"template":{"spec":{"containers":[{"name":"self-healing-controller","resources":{"requests":{"cpu":"500m","memory":"512Mi"},"limits":{"cpu":"1000m","memory":"1Gi"}}}]}}}}'
   ```

## Security Issues

### Pod Security Violations

**Symptoms**: Pods are being blocked by security policies.

**Diagnosis**:
```bash
# Check pod security policies
kubectl get psp

# Check pod security context
kubectl get pod -n self-healing -o yaml | grep -A 10 securityContext
```

**Solutions**:

1. **Update Security Context**:
   ```bash
   # Ensure pods run as non-root
   kubectl patch deployment self-healing-controller -n self-healing -p '{"spec":{"template":{"spec":{"securityContext":{"runAsNonRoot":true,"runAsUser":1000}}}}}'
   ```

2. **Check RBAC**:
   ```bash
   # Verify service account permissions
   kubectl auth can-i get pods --as=system:serviceaccount:self-healing:self-healing-controller
   ```

### Network Policy Violations

**Symptoms**: Network traffic is being blocked unexpectedly.

**Diagnosis**:
```bash
# Check network policies
kubectl get networkpolicy --all-namespaces

# Test connectivity
kubectl exec -n test-app -it <pod-name> -- curl <service-url>
```

**Solutions**:

1. **Update Network Policies**:
   ```bash
   # Add missing ingress/egress rules
   kubectl patch networkpolicy self-healing-controller-network-policy -n self-healing -p '{"spec":{"ingress":[{"from":[{"namespaceSelector":{"matchLabels":{"name":"monitoring"}}}],"ports":[{"port":8080,"protocol":"TCP"}]}]}}'
   ```

2. **Temporarily Disable**:
   ```bash
   # For debugging, temporarily remove policies
   kubectl delete networkpolicy --all-namespaces
   ```

## General Debugging Commands

### Cluster Health Check
```bash
# Overall cluster status
kubectl get componentstatuses

# Node status
kubectl get nodes

# All resources
kubectl get all --all-namespaces

# Events
kubectl get events --all-namespaces --sort-by='.lastTimestamp'
```

### Log Analysis
```bash
# Follow logs from all pods
kubectl logs -f --all-namespaces --tail=100

# Search for errors
kubectl logs --all-namespaces | grep -i error

# Check specific pod logs
kubectl logs -n self-healing -l app=self-healing-controller --tail=100 -f
```

### Resource Monitoring
```bash
# Resource usage
kubectl top pods --all-namespaces
kubectl top nodes

# Storage usage
kubectl get pvc --all-namespaces

# Network policies
kubectl get networkpolicy --all-namespaces
```

### Configuration Verification
```bash
# Check all ConfigMaps
kubectl get configmap --all-namespaces

# Check all Secrets
kubectl get secret --all-namespaces

# Check RBAC
kubectl get clusterrole,clusterrolebinding --all-namespaces
```

## Getting Help

If you cannot resolve an issue using this guide:

1. **Check the logs**: Use the diagnostic commands above
2. **Review recent changes**: Check git history for recent modifications
3. **Test in isolation**: Try reproducing the issue in a clean environment
4. **Check documentation**: Review the architecture and user guides
5. **Open an issue**: Create a detailed issue report with logs and steps to reproduce

### Issue Report Template

When reporting issues, include:

- **Environment**: Kubernetes version, OS, Terraform version
- **Steps to reproduce**: Detailed steps to reproduce the issue
- **Expected behavior**: What should happen
- **Actual behavior**: What actually happens
- **Logs**: Relevant logs from all components
- **Configuration**: Relevant configuration files
- **Screenshots**: If applicable 