# 🏗️ Infrastructure Components

## Terraform Infrastructure

The infrastructure is managed using Terraform, providing a declarative approach to infrastructure provisioning and management.

### Main Infrastructure Configuration

```hcl
# main.tf
terraform {
  required_version = ">= 1.0"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.0"
    }
  }
}

# Kubernetes provider configuration
provider "kubernetes" {
  config_path = "~/.kube/config"
}

# Helm provider for installing charts
provider "helm" {
  kubernetes {
    config_path = "~/.kube/config"
  }
}
```

### Resource Definitions

#### 1. Namespace Management
```hcl
# Create namespaces for different components
resource "kubernetes_namespace" "monitoring" {
  metadata {
    name = "monitoring"
    labels = {
      name = "monitoring"
    }
  }
}

resource "kubernetes_namespace" "chaos_engineering" {
  metadata {
    name = "chaos-engineering"
    labels = {
      name = "chaos-engineering"
    }
  }
}

resource "kubernetes_namespace" "self_healing" {
  metadata {
    name = "self-healing"
    labels = {
      name = "self-healing"
    }
  }
}
```

#### 2. Storage Configuration
```hcl
# Storage class for fast SSD storage
resource "kubernetes_storage_class" "fast_ssd" {
  metadata {
    name = "fast-ssd"
  }
  storage_provisioner = "kubernetes.io/aws-ebs"
  parameters = {
    type = "gp3"
    iops = "3000"
    throughput = "125"
  }
  allow_volume_expansion = true
}

# Persistent volume claims
resource "kubernetes_persistent_volume_claim" "prometheus_data" {
  metadata {
    name      = "prometheus-data"
    namespace = kubernetes_namespace.monitoring.metadata[0].name
  }
  spec {
    access_modes = ["ReadWriteOnce"]
    resources {
      requests = {
        storage = "50Gi"
      }
    }
    storage_class_name = kubernetes_storage_class.fast_ssd.metadata[0].name
  }
}
```

#### 3. Network Policies
```hcl
# Network policy for monitoring namespace
resource "kubernetes_network_policy" "monitoring_policy" {
  metadata {
    name      = "monitoring-network-policy"
    namespace = kubernetes_namespace.monitoring.metadata[0].name
  }
  spec {
    pod_selector {
      match_labels = {
        app = "monitoring"
      }
    }
    policy_types = ["Ingress", "Egress"]
    
    ingress {
      from {
        namespace_selector {
          match_labels = {
            name = "default"
          }
        }
      }
      ports {
        protocol = "TCP"
        port     = 9090
      }
    }
    
    egress {
      to {
        namespace_selector {
          match_labels = {
            name = "kube-system"
          }
        }
      }
    }
  }
}
```

## Kubernetes Resources

### 1. Self-Healing Controller Deployment

```yaml
# kubernetes/self-healing/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: self-healing-controller
  namespace: self-healing
  labels:
    app: self-healing-controller
spec:
  replicas: 1
  selector:
    match_labels:
      app: self-healing-controller
  template:
    metadata:
      labels:
        app: self-healing-controller
    spec:
      serviceAccountName: self-healing-sa
      containers:
      - name: controller
        image: self-healing-controller:latest
        imagePullPolicy: Always
        env:
        - name: HEALTH_CHECK_INTERVAL
          value: "30"
        - name: NODE_FAILURE_THRESHOLD
          value: "3"
        - name: POD_RESTART_THRESHOLD
          value: "5"
        - name: SLACK_WEBHOOK_URL
          valueFrom:
            secretKeyRef:
              name: slack-secret
              key: webhook-url
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "200m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
```

### 2. Service Account and RBAC

```yaml
# kubernetes/self-healing/rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: self-healing-sa
  namespace: self-healing
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: self-healing-role
rules:
- apiGroups: [""]
  resources: ["pods", "nodes", "services", "events"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets", "statefulsets"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: ["batch"]
  resources: ["jobs", "cronjobs"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: self-healing-binding
subjects:
- kind: ServiceAccount
  name: self-healing-sa
  namespace: self-healing
roleRef:
  kind: ClusterRole
  name: self-healing-role
  apiGroup: rbac.authorization.k8s.io
```

### 3. Monitoring Stack

#### Prometheus Configuration
```yaml
# kubernetes/monitoring/prometheus-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: monitoring
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s
    
    rule_files:
      - "alert_rules.yml"
    
    alerting:
      alertmanagers:
        - static_configs:
            - targets:
              - alertmanager:9093
    
    scrape_configs:
      - job_name: 'kubernetes-pods'
        kubernetes_sd_configs:
          - role: pod
        relabel_configs:
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
            action: keep
            regex: true
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
            action: replace
            target_label: __metrics_path__
            regex: (.+)
          - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
            action: replace
            regex: ([^:]+)(?::\d+)?;(\d+)
            replacement: $1:$2
            target_label: __address__
          - action: labelmap
            regex: __meta_kubernetes_pod_label_(.+)
          - source_labels: [__meta_kubernetes_namespace]
            action: replace
            target_label: kubernetes_namespace
          - source_labels: [__meta_kubernetes_pod_name]
            action: replace
            target_label: kubernetes_pod_name
```

#### Grafana Dashboard
```yaml
# kubernetes/monitoring/grafana-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-dashboards
  namespace: monitoring
data:
  kubernetes-cluster.json: |
    {
      "dashboard": {
        "title": "Kubernetes Cluster Overview",
        "panels": [
          {
            "title": "Node CPU Usage",
            "type": "graph",
            "targets": [
              {
                "expr": "100 - (avg by (instance) (irate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)"
              }
            ]
          },
          {
            "title": "Node Memory Usage",
            "type": "graph",
            "targets": [
              {
                "expr": "(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100"
              }
            ]
          }
        ]
      }
    }
```

## Chaos Engineering Infrastructure

### Chaos Mesh Installation
```yaml
# kubernetes/chaos-engineering/chaos-mesh.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: chaos-testing
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: chaos-controller
  namespace: chaos-testing
spec:
  replicas: 1
  selector:
    match_labels:
      app: chaos-controller
  template:
    metadata:
      labels:
        app: chaos-controller
    spec:
      containers:
      - name: controller
        image: pingcap/chaos-controller-manager:latest
        ports:
        - containerPort: 443
        env:
        - name: METRICS_PORT
          value: "8080"
        - name: WEBHOOK_PORT
          value: "9443"
```

### Chaos Experiments
```yaml
# kubernetes/chaos-engineering/chaos-experiments.yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: pod-failure
  namespace: chaos-testing
spec:
  action: pod-failure
  mode: one
  selector:
    namespaces: [default]
    labelSelectors:
      app: test-app
  duration: 30s
  scheduler:
    cron: "@every 10m"
---
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: network-delay
  namespace: chaos-testing
spec:
  action: delay
  mode: one
  selector:
    namespaces: [default]
  delay:
    latency: 100ms
    correlation: 100
    jitter: 0ms
  duration: 60s
  scheduler:
    cron: "@every 15m"
```

## Infrastructure Monitoring

### Resource Monitoring
- **CPU Usage**: Monitor cluster CPU utilization
- **Memory Usage**: Track memory consumption
- **Storage Usage**: Monitor persistent volume usage
- **Network Traffic**: Track network bandwidth

### Performance Metrics
- **Response Time**: API response times
- **Throughput**: Requests per second
- **Error Rate**: Error percentage
- **Availability**: Uptime percentage

### Cost Monitoring
- **Resource Costs**: Track infrastructure costs
- **Optimization**: Identify cost-saving opportunities
- **Budget Alerts**: Set budget limits and alerts
