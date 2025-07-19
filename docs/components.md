# 🔧 Components

> **Detailed descriptions of Terraform, Kubernetes, and tools used in the infrastructure**

---

## 🏗️ Infrastructure as Code

### **Terraform Configuration**

#### **Main Configuration (`main.tf`)**
```hcl
# Kubernetes Provider
provider "kubernetes" {
  config_path = "~/.kube/config"
}

# Helm Provider
provider "helm" {
  kubernetes {
    config_path = "~/.kube/config"
  }
}

# Namespace Resources
resource "kubernetes_namespace" "monitoring" {
  metadata {
    name = "monitoring"
  }
}

resource "kubernetes_namespace" "self_healing" {
  metadata {
    name = "self-healing"
  }
}

resource "kubernetes_namespace" "test_app" {
  metadata {
    name = "test-app"
  }
}

resource "kubernetes_namespace" "chaos_engineering" {
  metadata {
    name = "chaos-engineering"
  }
}
```

#### **Variables (`variables.tf`)**
```hcl
variable "slack_webhook_url" {
  description = "Slack webhook URL for notifications"
  type        = string
  sensitive   = true
}

variable "cluster_name" {
  description = "Kubernetes cluster name"
  type        = string
  default     = "self-healing-cluster"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}
```

#### **Outputs (`outputs.tf`)**
```hcl
output "grafana_url" {
  description = "Grafana dashboard URL"
  value       = "http://localhost:3000"
}

output "prometheus_url" {
  description = "Prometheus metrics URL"
  value       = "http://localhost:9090"
}

output "self_healing_controller_url" {
  description = "Self-healing controller health URL"
  value       = "http://localhost:8080/health"
}
```

---

## 🐳 Kubernetes Components

### **Self-Healing Controller**

#### **Deployment Configuration**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: self-healing-controller
  namespace: self-healing
spec:
  replicas: 1
  selector:
    matchLabels:
      app: self-healing-controller
  template:
    metadata:
      labels:
        app: self-healing-controller
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
    spec:
      serviceAccountName: self-healing-controller
      containers:
        - name: self-healing-controller
          image: self-healing-controller:latest
          ports:
            - containerPort: 8080
              name: metrics
          env:
            - name: POD_FAILURE_THRESHOLD
              value: "3"
            - name: POD_RESTART_TIMEOUT
              value: "300"
            - name: SLACK_NOTIFICATIONS_ENABLED
              value: "true"
          resources:
            limits:
              cpu: 500m
              memory: 512Mi
            requests:
              cpu: 250m
              memory: 256Mi
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
```

#### **Service Configuration**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: self-healing-controller
  namespace: self-healing
spec:
  ports:
    - port: 8080
      targetPort: 8080
      protocol: TCP
      name: metrics
  selector:
    app: self-healing-controller
```

#### **RBAC Configuration**
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: self-healing-controller
rules:
  - apiGroups: [""]
    resources: ["pods", "nodes", "services", "events"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
  - apiGroups: ["apps"]
    resources: ["deployments", "daemonsets", "replicasets"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
```

---

## 📊 Monitoring Stack

### **Prometheus Configuration**

#### **ConfigMap**
```yaml
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
    
    scrape_configs:
      - job_name: 'kubernetes-pods'
        kubernetes_sd_configs:
          - role: pod
        relabel_configs:
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
            action: keep
            regex: true
      
      - job_name: 'self-healing-controller'
        static_configs:
          - targets: ['self-healing-controller.self-healing.svc.cluster.local:8080']
```

#### **Alert Rules**
```yaml
groups:
  - name: self-healing.rules
    rules:
      - alert: PodCrashLooping
        expr: rate(kube_pod_container_status_restarts_total[15m]) * 60 > 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Pod {{ $labels.pod }} is crash looping"
      
      - alert: PodNotReady
        expr: kube_pod_status_phase{phase=~"Pending|Unknown"} > 0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Pod {{ $labels.pod }} is not ready"
```

### **Grafana Configuration**

#### **Dashboard Configuration**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: grafana-dashboards
  namespace: monitoring
data:
  self-healing-dashboard.json: |
    {
      "dashboard": {
        "title": "Self-Healing Infrastructure",
        "panels": [
          {
            "title": "Pod Health Status",
            "type": "stat",
            "targets": [
              {
                "expr": "kube_pod_status_phase",
                "legendFormat": "{{pod}}"
              }
            ]
          },
          {
            "title": "Node Health Status",
            "type": "stat",
            "targets": [
              {
                "expr": "kube_node_status_condition",
                "legendFormat": "{{node}}"
              }
            ]
          }
        ]
      }
    }
```

---

## 🧪 Test Application

### **Nginx Test App**

#### **Deployment**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-app
  namespace: test-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: test-app
  template:
    metadata:
      labels:
        app: test-app
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "80"
    spec:
      containers:
        - name: test-app
          image: nginx:1.21-alpine
          ports:
            - containerPort: 80
          resources:
            limits:
              cpu: 200m
              memory: 256Mi
            requests:
              cpu: 100m
              memory: 128Mi
          livenessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 10
            periodSeconds: 5
          readinessProbe:
            httpGet:
              path: /
              port: 80
            initialDelaySeconds: 5
            periodSeconds: 5
```

#### **Service**
```yaml
apiVersion: v1
kind: Service
metadata:
  name: test-app
  namespace: test-app
spec:
  ports:
    - port: 80
      targetPort: 80
      protocol: TCP
  selector:
    app: test-app
```

#### **Horizontal Pod Autoscaler**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: test-app-hpa
  namespace: test-app
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: test-app
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

---

## 🌪️ Chaos Engineering

### **Chaos Mesh Configuration**

#### **Chaos Mesh Installation**
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: chaos-engineering

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: chaos-mesh-controller-manager
  namespace: chaos-engineering
spec:
  replicas: 1
  selector:
    matchLabels:
      app: chaos-mesh-controller-manager
  template:
    metadata:
      labels:
        app: chaos-mesh-controller-manager
    spec:
      containers:
        - name: chaos-mesh-controller-manager
          image: chaos-mesh/chaos-mesh:latest
          ports:
            - containerPort: 10080
              name: http
          env:
            - name: NAMESPACE
              value: "chaos-engineering"
```

#### **Chaos Experiments**
```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: test-pod-failure
  namespace: chaos-engineering
spec:
  action: pod-failure
  mode: one
  selector:
    namespaces:
      - test-app
  duration: "30s"
  scheduler:
    cron: "@every 5m"

---
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: test-network-delay
  namespace: chaos-engineering
spec:
  action: delay
  mode: one
  selector:
    namespaces:
      - test-app
  delay:
    latency: "100ms"
    correlation: "100"
    jitter: "0ms"
  duration: "30s"
```

---

## 🔄 Node Management

### **Kured (Kubernetes Reboot Daemon)**

#### **DaemonSet Configuration**
```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: kured
  namespace: kube-system
spec:
  selector:
    matchLabels:
      name: kured
  template:
    metadata:
      labels:
        name: kured
    spec:
      serviceAccountName: kured
      containers:
        - name: kured
          image: docker.io/weaveworks/kured:latest
          args:
            - --reboot-days=sun,mon,tue,wed,thu,fri,sat
            - --start-time=3am
            - --end-time=4am
            - --time-zone=UTC
            - --slack-hook-url=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
            - --slack-username=kured
            - --notify-url=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
          env:
            - name: KURED_NODE_ID
              valueFrom:
                fieldRef:
                  fieldPath: spec.nodeName
          securityContext:
            privileged: true
          volumeMounts:
            - name: var-lib-docker
              mountPath: /var/lib/docker
            - name: etc-machines-id
              mountPath: /etc/machine-id
              readOnly: true
      volumes:
        - name: var-lib-docker
          hostPath:
            path: /var/lib/docker
        - name: etc-machines-id
          hostPath:
            path: /etc/machine-id
            type: File
```

---

## 🔐 Security Components

### **Network Policies**

#### **Self-Healing Network Policy**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: self-healing-network-policy
  namespace: self-healing
spec:
  podSelector:
    matchLabels:
      app: self-healing-controller
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: monitoring
      ports:
        - protocol: TCP
          port: 8080
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: monitoring
      ports:
        - protocol: TCP
          port: 9090
```

#### **Test App Network Policy**
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: test-app-network-policy
  namespace: test-app
spec:
  podSelector:
    matchLabels:
      app: test-app
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector: {}
      ports:
        - protocol: TCP
          port: 80
```

---

## 📦 Backup System

### **Backup CronJob**
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: infrastructure-backup
  namespace: backup
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: backup-service-account
          containers:
            - name: backup
              image: bitnami/kubectl:latest
              command:
                - /bin/bash
                - -c
                - |
                  # Backup Kubernetes resources
                  kubectl get all --all-namespaces -o yaml > /backup/k8s-resources.yaml
                  
                  # Backup Prometheus data
                  kubectl exec -n monitoring prometheus-0 -- tar czf /tmp/prometheus-data.tar.gz /prometheus
                  kubectl cp monitoring/prometheus-0:/tmp/prometheus-data.tar.gz /backup/
                  
                  # Backup Grafana dashboards
                  kubectl get configmap -n monitoring grafana-dashboards -o yaml > /backup/grafana-dashboards.yaml
                  
                  echo "Backup completed at $(date)"
          volumes:
            - name: backup-storage
              persistentVolumeClaim:
                claimName: backup-pvc
          restartPolicy: OnFailure
```

---

<div align="center">

**[← Architecture](./architecture.md)** | **[Self-Healing →](./self-healing.md)**

</div> 