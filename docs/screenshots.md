# 📊 Screenshots

> **Visual demonstrations and dashboards of the self-healing infrastructure**

---

## 🖥️ Grafana Dashboards

### **Self-Healing Infrastructure Overview**

![Grafana Overview Dashboard](./images/grafana-overview.png)

**Dashboard Features:**
- **Pod Health Status**: Real-time pod status across all namespaces
- **Node Health**: Node availability and resource usage
- **Recovery Metrics**: Self-healing success rate and recovery times
- **Chaos Engineering**: Active chaos experiments and their impact
- **Resource Utilization**: CPU, memory, and network usage

### **Self-Healing Controller Metrics**

![Self-Healing Metrics](./images/self-healing-metrics.png)

**Key Metrics:**
- **Recovery Success Rate**: Percentage of successful recoveries
- **Average Recovery Time**: Time taken for recovery actions
- **Failure Detection Time**: Time from failure to detection
- **Active Alerts**: Current active alerts and their status
- **Recovery Actions**: Breakdown of recovery action types

### **Pod Health Dashboard**

![Pod Health Dashboard](./images/pod-health.png)

**Pod Monitoring:**
- **Pod Status**: Current status of all pods (Running, Pending, Failed)
- **Restart Count**: Number of pod restarts over time
- **Resource Usage**: CPU and memory usage per pod
- **Health Check Status**: Liveness and readiness probe status
- **Pod Events**: Recent events affecting pods

---

## 🔍 Prometheus Metrics

### **Prometheus Query Interface**

![Prometheus Interface](./images/prometheus-interface.png)

**Key Queries:**
```promql
# Pod availability
kube_pod_status_phase{phase="Running"} / kube_pod_status_phase

# Recovery success rate
rate(self_healing_recovery_actions_total{success="true"}[5m]) / 
rate(self_healing_recovery_actions_total[5m])

# Average recovery time
histogram_quantile(0.95, rate(self_healing_recovery_duration_seconds_bucket[5m]))
```

### **Alertmanager Interface**

![Alertmanager Dashboard](./images/alertmanager.png)

**Alert Management:**
- **Active Alerts**: Currently firing alerts
- **Alert History**: Historical alert data
- **Silence Management**: Alert silencing configuration
- **Notification Status**: Alert delivery status

---

## 🌪️ Chaos Mesh Dashboard

### **Chaos Experiments Overview**

![Chaos Mesh Dashboard](./images/chaos-mesh-dashboard.png)

**Experiment Management:**
- **Active Experiments**: Currently running chaos experiments
- **Experiment History**: Past experiment results
- **Success Rate**: Experiment success and failure rates
- **Recovery Validation**: Automatic recovery verification

### **Experiment Details**

![Chaos Experiment Details](./images/chaos-experiment-details.png)

**Experiment Information:**
- **Experiment Type**: Pod chaos, network chaos, stress chaos
- **Target Selection**: Affected pods and namespaces
- **Duration**: Experiment duration and scheduling
- **Status**: Current experiment status and progress

---

## 🚀 GitHub Actions

### **CI/CD Pipeline Status**

![GitHub Actions Pipeline](./images/github-actions-pipeline.png)

**Pipeline Stages:**
- **Code Quality**: Linting and unit tests
- **Infrastructure Deployment**: Terraform deployment
- **Self-Healing Tests**: Controller functionality tests
- **Integration Tests**: End-to-end validation
- **Performance Tests**: Load testing and chaos engineering

### **Release Workflow**

![Release Workflow](./images/release-workflow.png)

**Release Process:**
- **Docker Build**: Multi-platform image building
- **Image Push**: Container registry upload
- **GitHub Release**: Release creation and tagging
- **Terraform Update**: Infrastructure version update

---

## 🐳 Kubernetes Dashboard

### **Cluster Overview**

![Kubernetes Dashboard](./images/k8s-dashboard-overview.png)

**Cluster Information:**
- **Node Status**: All nodes and their health
- **Namespace Overview**: All namespaces and their resources
- **Resource Usage**: Cluster-wide resource utilization
- **Events**: Recent cluster events

### **Pod Management**

![Pod Management](./images/k8s-pod-management.png)

**Pod Operations:**
- **Pod List**: All pods across namespaces
- **Pod Details**: Individual pod information
- **Pod Logs**: Real-time log viewing
- **Pod Metrics**: Resource usage per pod

---

## 📱 Slack Notifications

### **Alert Notifications**

![Slack Alerts](./images/slack-alerts.png)

**Notification Types:**
- **Pod Failure Alerts**: Pod crash and recovery notifications
- **Node Failure Alerts**: Node health notifications
- **Chaos Experiment Alerts**: Chaos engineering status updates
- **Recovery Success**: Successful recovery confirmations

### **Recovery Notifications**

![Recovery Notifications](./images/slack-recovery.png)

**Recovery Information:**
- **Failure Type**: Type of failure detected
- **Recovery Action**: Action taken to recover
- **Recovery Time**: Time taken for recovery
- **Status**: Success or failure of recovery

---

## 🔧 K9s Terminal Interface

### **K9s Pod View**

![K9s Pod View](./images/k9s-pod-view.png)

**K9s Features:**
- **Real-time Updates**: Live pod status updates
- **Quick Actions**: Pod restart, logs, describe
- **Filtering**: Filter pods by namespace, status, labels
- **Resource Monitoring**: CPU, memory usage per pod

### **K9s Service View**

![K9s Service View](./images/k9s-service-view.png)

**Service Management:**
- **Service List**: All services across namespaces
- **Endpoint Status**: Service endpoint health
- **Port Forwarding**: Quick port-forward setup
- **Service Details**: Service configuration and selectors

---

## 📊 System Reports

### **CI/CD System Report**

![System Report](./images/system-report.png)

**Report Contents:**
```
=== Pod Status Across All Namespaces ===
NAMESPACE         NAME                                    READY   STATUS    RESTARTS   AGE
kube-system       coredns-787d4945fb-abc12              1/1     Running   0          5m
kube-system       etcd-minikube                         1/1     Running   0          5m
kube-system       kube-apiserver-minikube               1/1     Running   0          5m
kube-system       kube-controller-manager-minikube      1/1     Running   0          5m
kube-system       kube-proxy-xyz789                     1/1     Running   0          5m
kube-system       kube-scheduler-minikube               1/1     Running   0          5m
kube-system       metrics-server-5c6d7f8g9h             1/1     Running   0          4m
kube-system       storage-provisioner                   1/1     Running   0          5m
monitoring        prometheus-kube-prometheus-prometheus-0 2/2   Running   0          3m
monitoring        prometheus-grafana-abc123-def456      2/2     Running   0          3m
self-healing      self-healing-controller-xyz789-abc12  1/1     Running   0          2m
test-app          test-app-abc123-def456                1/1     Running   0          2m
test-app          test-app-abc123-ghi789                1/1     Running   0          2m

=== Self-Healing Controller Logs ===
2024-01-15 10:30:15 INFO Starting Self-Healing Controller v1.0.0
2024-01-15 10:30:15 INFO Monitoring namespace: test-app
2024-01-15 10:30:15 INFO Health check endpoint: /health
2024-01-15 10:30:15 INFO Metrics endpoint: /metrics
2024-01-15 10:30:16 INFO Controller ready to monitor pods

=== Recent Cluster Events ===
LAST SEEN   TYPE      REASON              OBJECT                    MESSAGE
2m          Normal    Scheduled           pod/test-app-abc123-def456 Successfully assigned test-app/test-app-abc123-def456 to minikube
2m          Normal    Pulled              pod/test-app-abc123-def456 Container image "nginx:1.21-alpine" already present on machine
2m          Normal    Created             pod/test-app-abc123-def456 Created container test-app
2m          Normal    Started             pod/test-app-abc123-def456 Started container test-app
2m          Normal    Scheduled           pod/test-app-abc123-ghi789 Successfully assigned test-app/test-app-abc123-ghi789 to minikube
2m          Normal    Pulled              pod/test-app-abc123-ghi789 Container image "nginx:1.21-alpine" already present on machine
2m          Normal    Created             pod/test-app-abc123-ghi789 Created container test-app
2m          Normal    Started             pod/test-app-abc123-ghi789 Started container test-app
```

### **Performance Test Results**

![Performance Results](./images/performance-results.png)

**Performance Metrics:**
- **Response Time**: Average and 95th percentile response times
- **Throughput**: Requests per second
- **Error Rate**: Percentage of failed requests
- **Resource Usage**: CPU and memory utilization during tests

---

## 🎯 Test Application

### **Nginx Test App**

![Test Application](./images/test-app.png)

**Application Features:**
- **Health Check**: `/health` endpoint for liveness probe
- **Metrics**: `/metrics` endpoint for Prometheus scraping
- **Load Testing**: `/load` endpoint for performance testing
- **Status Page**: `/status` endpoint for application status

### **Load Testing Interface**

![Load Testing](./images/load-testing.png)

**Load Test Features:**
- **Concurrent Users**: Configurable number of concurrent users
- **Test Duration**: Adjustable test duration
- **Request Types**: Different types of requests to test
- **Real-time Metrics**: Live performance metrics during tests

---

## 📈 Monitoring Alerts

### **Alert Rules Configuration**

![Alert Rules](./images/alert-rules.png)

**Alert Configuration:**
- **Pod Failure Alerts**: Crash loop and pod not ready alerts
- **Node Failure Alerts**: Node not ready and resource pressure alerts
- **Service Alerts**: Service unavailability alerts
- **Custom Alerts**: Application-specific alert rules

### **Alert History**

![Alert History](./images/alert-history.png)

**Alert Tracking:**
- **Alert Timeline**: Historical alert occurrences
- **Resolution Time**: Time to resolve alerts
- **Alert Patterns**: Recurring alert patterns
- **Escalation History**: Alert escalation tracking

---

## 🔄 Recovery Demonstrations

### **Pod Failure Recovery**

![Pod Recovery](./images/pod-recovery.png)

**Recovery Process:**
1. **Pod Failure**: Pod crashes or becomes unresponsive
2. **Detection**: Self-healing controller detects failure
3. **Analysis**: Controller analyzes failure type
4. **Recovery**: Controller executes recovery action
5. **Validation**: System validates successful recovery

### **Node Failure Recovery**

![Node Recovery](./images/node-recovery.png)

**Node Recovery:**
1. **Node Failure**: Node becomes unavailable
2. **Pod Eviction**: Pods are evicted from failed node
3. **Rescheduling**: Pods are rescheduled to healthy nodes
4. **Node Reboot**: Kured triggers node reboot if needed
5. **Recovery**: Node returns to healthy state

---

## 📱 Mobile Dashboard

### **Mobile Grafana View**

![Mobile Dashboard](./images/mobile-dashboard.png)

**Mobile Features:**
- **Responsive Design**: Optimized for mobile devices
- **Touch Interface**: Touch-friendly controls
- **Quick Actions**: Swipe gestures for common actions
- **Offline Support**: Cached data for offline viewing

---

<div align="center">

**[← CI/CD Pipeline](./ci-cd.md)** | **[Links →](./links.md)**

</div> 