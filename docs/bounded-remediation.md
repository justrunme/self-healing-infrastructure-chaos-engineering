# Bounded Remediation (Human Brake)

The self-healing controller implements a sophisticated "human brake" system to prevent runaway remediation and cascading failures. This ensures that automated healing actions remain safe and predictable.

## Overview

Traditional self-healing systems can cause cascading failures when they remediate issues too aggressively. The bounded remediation system adds multiple safety mechanisms:

- **Budget Limits**: Maximum remediations per namespace within a sliding window
- **Cooldown Periods**: Minimum time between remediations of the same object
- **Dry-Run Mode**: Test remediation logic without making changes
- **Approval Gates**: Require explicit approval for dangerous actions
- **Observability**: Comprehensive Prometheus metrics for monitoring

## Key Concepts

### 1. Remediation Budget

Each namespace has a budget for remediation actions within a configurable time window.

```
Budget = 10 remediations per 5 minutes (default)
```

Once the budget is exhausted, the brake engages and no further remediations occur until actions age out of the sliding window.

**Benefits:**
- Prevents remediation storms during widespread failures
- Limits blast radius of automated actions
- Provides time for human intervention when needed

### 2. Per-Object Cooldown

Each Kubernetes object (pod, node, etc.) has a cooldown period after remediation.

```
Cooldown = 60 seconds (default)
```

The controller will not remediate the same object again until the cooldown expires.

**Benefits:**
- Prevents rapid-fire restarts of the same pod
- Allows time for natural recovery
- Reduces unnecessary churn

### 3. Dry-Run Mode

In dry-run mode, the controller detects issues and logs what it would do, but makes no actual changes.

**Use cases:**
- Testing new remediation policies
- Validating configuration changes
- Auditing remediation decisions
- Training and demonstration

### 4. Approval Gates

Dangerous actions (node reboot, node drain) require explicit approval via Kubernetes annotations.

**Actions requiring approval:**
- `node_reboot` - Triggering a node reboot
- `node_drain` - Draining a node for maintenance

**How it works:**
1. Controller detects a node failure
2. Checks for approval annotation
3. If approved, performs action
4. If not approved, logs the need for approval and sends notification

## Configuration

### Environment Variables

Configure the brake system via environment variables in the controller deployment:

| Variable | Default | Description |
|----------|---------|-------------|
| `REMEDIATION_BUDGET_PER_NAMESPACE` | `10` | Maximum remediations per namespace in the time window |
| `REMEDIATION_BUDGET_WINDOW_SECONDS` | `300` | Sliding time window in seconds (5 minutes) |
| `REMEDIATION_COOLDOWN_SECONDS` | `60` | Cooldown period per object in seconds |
| `DRY_RUN` | `false` | Enable dry-run mode (true/false) |
| `REQUIRE_APPROVAL_FOR_DANGEROUS` | `true` | Require approval for dangerous actions (true/false) |

### Example Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: self-healing-controller
  namespace: self-healing
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: controller
        image: self-healing-controller:latest
        env:
        - name: REMEDIATION_BUDGET_PER_NAMESPACE
          value: "15"
        - name: REMEDIATION_BUDGET_WINDOW_SECONDS
          value: "600"
        - name: REMEDIATION_COOLDOWN_SECONDS
          value: "120"
        - name: DRY_RUN
          value: "false"
        - name: REQUIRE_APPROVAL_FOR_DANGEROUS
          value: "true"
```

## Approval Annotations

### Approving Node Reboot

```bash
kubectl annotate node <node-name> \
  self-healing.justrunme.com/approve-reboot=true
```

### Approving Node Drain

```bash
kubectl annotate node <node-name> \
  self-healing.justrunme.com/approve-drain=true
```

### Removing Approval

```bash
# Remove reboot approval
kubectl annotate node <node-name> \
  self-healing.justrunme.com/approve-reboot-

# Remove drain approval
kubectl annotate node <node-name> \
  self-healing.justrunme.com/approve-drain-
```

## Prometheus Metrics

The controller exposes three key metrics at `/metrics`:

### 1. remediations_total

Counter tracking all remediation actions.

**Labels:**
- `namespace` - Namespace where remediation occurred
- `action` - Type of action (restart_pod, helm_rollback, node_reboot, etc.)
- `result` - Outcome (success, failure, brake_engaged, dry_run, approval_required)

**Example queries:**

```promql
# Total remediations by namespace
sum(remediations_total) by (namespace)

# Failed remediations
sum(remediations_total{result="failure"}) by (action)

# Actions blocked by brake
sum(remediations_total{result="brake_engaged"}) by (namespace)
```

### 2. brake_engaged

Gauge indicating whether the brake is currently engaged.

**Labels:**
- `namespace` - Namespace being monitored
- `reason` - Reason for brake engagement (budget_exhausted, cooldown_active, none)

**Values:**
- `1` - Brake is engaged
- `0` - Brake is not engaged

**Example queries:**

```promql
# Namespaces with brake engaged
brake_engaged == 1

# Budget exhaustion events
brake_engaged{reason="budget_exhausted"} == 1

# Active cooldowns
brake_engaged{reason="cooldown_active"} == 1
```

### 3. remediation_budget_remaining

Gauge showing remaining remediation budget per namespace.

**Labels:**
- `namespace` - Namespace being tracked

**Example queries:**

```promql
# Remaining budget across all namespaces
remediation_budget_remaining

# Namespaces with low budget
remediation_budget_remaining < 3

# Budget utilization percentage
(10 - remediation_budget_remaining) / 10 * 100
```

## Monitoring and Alerting

### Recommended Alerts

```yaml
groups:
  - name: self-healing-brake
    interval: 30s
    rules:
      - alert: RemediationBudgetExhausted
        expr: brake_engaged{reason="budget_exhausted"} == 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Remediation budget exhausted in namespace {{ $labels.namespace }}"
          description: "The self-healing controller has exhausted its remediation budget."

      - alert: HighRemediationRate
        expr: rate(remediations_total[5m]) > 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High remediation rate in namespace {{ $labels.namespace }}"
          description: "Remediation rate is {{ $value }} actions/sec."

      - alert: FrequentRemediationFailures
        expr: |
          sum(rate(remediations_total{result="failure"}[5m])) by (namespace, action) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Frequent remediation failures for {{ $labels.action }}"
          description: "Failure rate is {{ $value }} failures/sec."

      - alert: ApprovalRequired
        expr: |
          sum(increase(remediations_total{result="approval_required"}[10m])) by (action) > 0
        labels:
          severity: info
        annotations:
          summary: "{{ $labels.action }} requires approval"
          description: "Dangerous action is waiting for approval annotation."
```

## Testing in Dry-Run Mode

### Enable Dry-Run Mode

```bash
kubectl set env deployment/self-healing-controller \
  -n self-healing \
  DRY_RUN=true
```

### Monitor Dry-Run Logs

```bash
kubectl logs -n self-healing -f deployment/self-healing-controller \
  | grep "DRY RUN"
```

**Example output:**

```
2026-10-10 11:45:23 - __main__ - INFO - 🔍 DRY RUN: Would restart pod test-ns/failing-pod
2026-10-10 11:45:45 - __main__ - INFO - 🔍 DRY RUN: Would rollback Helm release my-app
2026-10-10 11:46:12 - __main__ - INFO - 🔍 DRY RUN: Would trigger reboot for node worker-1
```

### Verify Metrics in Dry-Run

```bash
kubectl port-forward -n self-healing svc/self-healing-controller 8080:8080 &
curl -s http://localhost:8080/metrics | grep 'dry_run'
```

### Disable Dry-Run Mode

```bash
kubectl set env deployment/self-healing-controller \
  -n self-healing \
  DRY_RUN=false
```

## Best Practices

### 1. Start Conservative

Begin with strict limits and relax them based on observed behavior:

```yaml
REMEDIATION_BUDGET_PER_NAMESPACE: "5"
REMEDIATION_BUDGET_WINDOW_SECONDS: "600"
REMEDIATION_COOLDOWN_SECONDS: "120"
```

### 2. Test with Dry-Run

Always test new configurations in dry-run mode first:

1. Enable `DRY_RUN=true`
2. Deploy configuration
3. Monitor logs and metrics
4. Verify expected behavior
5. Disable dry-run mode

### 3. Monitor Brake Engagement

Set up alerts for brake engagement to understand your remediation patterns:

- Frequent budget exhaustion → Increase budget or investigate root cause
- Many cooldown activations → Pods may need longer to stabilize
- Approval requests → Review node health checks

### 4. Adjust per Environment

Use different configurations for different environments:

**Development:**
```yaml
REMEDIATION_BUDGET_PER_NAMESPACE: "20"
REMEDIATION_COOLDOWN_SECONDS: "30"
REQUIRE_APPROVAL_FOR_DANGEROUS: "false"
```

**Production:**
```yaml
REMEDIATION_BUDGET_PER_NAMESPACE: "10"
REMEDIATION_COOLDOWN_SECONDS: "120"
REQUIRE_APPROVAL_FOR_DANGEROUS: "true"
```

### 5. Regular Review

Periodically review remediation metrics:

```bash
# Weekly remediation summary
kubectl port-forward -n self-healing svc/self-healing-controller 8080:8080 &

# Total remediations by result
curl -s http://localhost:8080/metrics | grep remediations_total

# Brake engagement frequency
curl -s http://localhost:8080/metrics | grep brake_engaged
```

## Troubleshooting

### Problem: Brake Engages Too Frequently

**Symptoms:**
- `brake_engaged{reason="budget_exhausted"}` is often `1`
- Legitimate failures are not being remediated

**Solutions:**
1. Increase budget: `REMEDIATION_BUDGET_PER_NAMESPACE=15`
2. Increase window: `REMEDIATION_BUDGET_WINDOW_SECONDS=600`
3. Investigate root cause of high failure rate

### Problem: Same Pod Restarts Repeatedly

**Symptoms:**
- High restart count on specific pods
- Cooldown frequently engaged for same objects

**Solutions:**
1. Increase cooldown: `REMEDIATION_COOLDOWN_SECONDS=180`
2. Investigate application issues causing crashes
3. Consider implementing backoff in application

### Problem: Dangerous Actions Not Executing

**Symptoms:**
- `remediations_total{result="approval_required"}` increasing
- Nodes not rebooting despite failures

**Solutions:**
1. Add approval annotation to nodes
2. Disable approval requirement (if appropriate): `REQUIRE_APPROVAL_FOR_DANGEROUS=false`
3. Review node failure detection thresholds

### Problem: Too Many Dry-Run Logs

**Symptoms:**
- Controller logs show many "DRY RUN" messages
- No actual remediation happening

**Solutions:**
1. Verify dry-run mode is disabled: `DRY_RUN=false`
2. Check deployment configuration
3. Restart controller after configuration change

## Architecture

### Watch/Informer Pattern

The controller uses Kubernetes watch API instead of polling:

```python
# Efficient: Watch for changes
w = watch.Watch()
for event in w.stream(self.k8s_client.list_pod_for_all_namespaces):
    handle_event(event)

# Handles resource version expiration
# Automatic reconnection
# Lower API server load
```

### Budget Tracking

Budget uses a sliding window with deque for efficient cleanup:

```python
class RemediationBudget:
    def __init__(self, max_count, window_seconds):
        self.remediations = deque()  # Ordered timestamps
    
    def can_remediate(self):
        self._cleanup_old_entries()  # Remove expired
        return len(self.remediations) < self.max_count
```

### Cooldown Tracking

Per-object cooldown uses dictionary with timestamps:

```python
class ObjectCooldown:
    def __init__(self, cooldown_seconds):
        self.last_remediation = {}  # object_key -> timestamp
    
    def can_remediate(self, obj_key):
        elapsed = now - self.last_remediation.get(obj_key, 0)
        return elapsed >= self.cooldown_seconds
```

## Related Documentation

- [Self-Healing Controller](self-healing.md)
- [Monitoring Setup](monitoring.md)
- [Chaos Engineering](chaos-engineering.md)
- [CI/CD Pipeline](ci-cd.md)
