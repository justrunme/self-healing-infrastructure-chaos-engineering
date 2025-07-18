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

provider "kubernetes" {
  config_path = "~/.kube/config"
}

provider "helm" {
  kubernetes {
    config_path = "~/.kube/config"
  }
}

# Создание namespace для мониторинга
resource "kubernetes_namespace" "monitoring" {
  metadata {
    name = "monitoring"
    labels = {
      name = "monitoring"
    }
  }
}

# Создание namespace для chaos engineering
resource "kubernetes_namespace" "chaos_engineering" {
  metadata {
    name = "chaos-engineering"
    labels = {
      name = "chaos-engineering"
    }
  }
}

# Создание namespace для self-healing
resource "kubernetes_namespace" "self_healing" {
  metadata {
    name = "self-healing"
    labels = {
      name = "self-healing"
    }
  }
}

# Создание namespace для kured
resource "kubernetes_namespace" "kured" {
  metadata {
    name = "kured"
    labels = {
      name = "kured"
    }
  }
}

# Создание namespace для тестового приложения
resource "kubernetes_namespace" "test_app" {
  metadata {
    name = "test-app"
    labels = {
      name = "test-app"
    }
  }
}

# Создание ConfigMap для конфигурации Slack webhook
resource "kubernetes_config_map" "slack_config" {
  metadata {
    name      = "slack-config"
    namespace = kubernetes_namespace.monitoring.metadata[0].name
  }

  data = {
    "slack_webhook_url" = var.slack_webhook_url
    "slack_channel"     = var.slack_channel
  }
}

# Создание Secret для Slack webhook (если URL содержит токен)
resource "kubernetes_secret" "slack_secret" {
  metadata {
    name      = "slack-secret"
    namespace = kubernetes_namespace.monitoring.metadata[0].name
  }

  data = {
    "webhook_url" = base64encode(var.slack_webhook_url)
  }

  type = "Opaque"
}

# Создание ConfigMap для Prometheus алертов
resource "kubernetes_config_map" "prometheus_alerts" {
  metadata {
    name      = "prometheus-alerts"
    namespace = kubernetes_namespace.monitoring.metadata[0].name
  }

  data = {
    "alerts.yaml" = file("${path.module}/../kubernetes/monitoring/prometheus-alerts.yaml")
  }
}

# Создание ConfigMap для Grafana дашборда
resource "kubernetes_config_map" "grafana_dashboard" {
  metadata {
    name      = "self-healing-dashboard"
    namespace = kubernetes_namespace.monitoring.metadata[0].name
    labels = {
      grafana_dashboard = "1"
    }
  }

  data = {
    "self-healing-dashboard.json" = file("${path.module}/../kubernetes/monitoring/grafana-dashboard.yaml")
  }
}

# Развертывание Prometheus Stack через Helm
resource "helm_release" "prometheus_stack" {
  name       = "prometheus"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name
  create_namespace = false

  set {
    name  = "prometheus.prometheusSpec.retention"
    value = "${var.prometheus_retention_days}d"
  }

  set {
    name  = "grafana.enabled"
    value = "true"
  }

  set {
    name  = "grafana.adminPassword"
    value = var.grafana_admin_password
  }

  set {
    name  = "grafana.dashboardProviders.dashboardproviders.yaml.apiVersion"
    value = "1"
  }

  set {
    name  = "grafana.dashboardProviders.dashboardproviders.yaml.providers[0].name"
    value = "default"
  }

  set {
    name  = "grafana.dashboardProviders.dashboardproviders.yaml.providers[0].orgId"
    value = "1"
  }

  set {
    name  = "grafana.dashboardProviders.dashboardproviders.yaml.providers[0].folder"
    value = ""
  }

  set {
    name  = "grafana.dashboardProviders.dashboardproviders.yaml.providers[0].type"
    value = "file"
  }

  set {
    name  = "grafana.dashboardProviders.dashboardproviders.yaml.providers[0].disableDeletion"
    value = "false"
  }

  set {
    name  = "grafana.dashboardProviders.dashboardproviders.yaml.providers[0].editable"
    value = "true"
  }

  set {
    name  = "grafana.dashboardProviders.dashboardproviders.yaml.providers[0].options.path"
    value = "/var/lib/grafana/dashboards/default"
  }

  depends_on = [
    kubernetes_namespace.monitoring
  ]
}

# Развертывание Kured через Helm
resource "helm_release" "kured" {
  name       = "kured"
  repository = "https://weaveworks.github.io/kured"
  chart      = "kured"
  namespace  = kubernetes_namespace.kured.metadata[0].name
  create_namespace = false

  set {
    name  = "configuration.rebootDays"
    value = "mon,tue,wed,thu,fri"
  }

  set {
    name  = "configuration.startTime"
    value = "3am"
  }

  set {
    name  = "configuration.endTime"
    value = "5am"
  }

  set {
    name  = "configuration.timeZone"
    value = "UTC"
  }

  depends_on = [
    kubernetes_namespace.kured
  ]
}

# Создание ServiceAccount для Self-Healing Controller
resource "kubernetes_service_account" "self_healing_controller" {
  metadata {
    name      = "self-healing-controller"
    namespace = kubernetes_namespace.self_healing.metadata[0].name
  }
}

# Создание ClusterRole для Self-Healing Controller
resource "kubernetes_cluster_role" "self_healing_controller" {
  metadata {
    name = "self-healing-controller"
  }

  rule {
    api_groups = [""]
    resources  = ["pods", "nodes", "services", "endpoints", "events", "configmaps", "secrets"]
    verbs      = ["get", "list", "watch", "create", "update", "patch", "delete"]
  }

  rule {
    api_groups = ["apps"]
    resources  = ["deployments", "daemonsets", "replicasets", "statefulsets"]
    verbs      = ["get", "list", "watch", "create", "update", "patch", "delete"]
  }

  rule {
    api_groups = ["chaos-mesh.org"]
    resources  = ["*"]
    verbs      = ["get", "list", "watch", "create", "update", "patch", "delete"]
  }
}

# Создание ClusterRoleBinding для Self-Healing Controller
resource "kubernetes_cluster_role_binding" "self_healing_controller" {
  metadata {
    name = "self-healing-controller"
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = kubernetes_cluster_role.self_healing_controller.metadata[0].name
  }

  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account.self_healing_controller.metadata[0].name
    namespace = kubernetes_namespace.self_healing.metadata[0].name
  }
}

# Создание ConfigMap для Self-Healing Controller конфигурации
resource "kubernetes_config_map" "self_healing_config" {
  metadata {
    name      = "self-healing-config"
    namespace = kubernetes_namespace.self_healing.metadata[0].name
  }

  data = {
    "POD_FAILURE_THRESHOLD"        = "3"
    "POD_RESTART_TIMEOUT"          = "300"
    "NODE_FAILURE_THRESHOLD"       = "2"
    "NODE_UNREACHABLE_TIMEOUT"     = "600"
    "HELM_ROLLBACK_ENABLED"        = "true"
    "HELM_ROLLBACK_TIMEOUT"        = "300"
    "KURED_INTEGRATION_ENABLED"    = "true"
    "SLACK_NOTIFICATIONS_ENABLED"  = var.slack_notifications_enabled ? "true" : "false"
    "SLACK_WEBHOOK_URL"            = var.slack_webhook_url
    "SLACK_CHANNEL"                = var.slack_channel
    "PROMETHEUS_ENABLED"           = "true"
    "PROMETHEUS_URL"               = "http://prometheus-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090"
    "CHAOS_ENGINEERING_ENABLED"    = "true"
    "CHAOS_MESH_URL"               = "http://chaos-mesh-controller-manager.chaos-engineering.svc.cluster.local:10080"
    "CHECK_INTERVAL"               = "30"
  }
}

# Создание Deployment для Self-Healing Controller
resource "kubernetes_deployment" "self_healing_controller" {
  metadata {
    name      = "self-healing-controller"
    namespace = kubernetes_namespace.self_healing.metadata[0].name
    labels = {
      app = "self-healing-controller"
    }
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "self-healing-controller"
      }
    }

    template {
      metadata {
        labels = {
          app = "self-healing-controller"
        }
      }

      spec {
        service_account_name = kubernetes_service_account.self_healing_controller.metadata[0].name

        container {
          image = var.self_healing_controller_image
          name  = "self-healing-controller"

          port {
            container_port = 8080
            name          = "http"
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map.self_healing_config.metadata[0].name
            }
          }

          resources {
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
            requests = {
              cpu    = "250m"
              memory = "256Mi"
            }
          }

          liveness_probe {
            http_get {
              path = "/health"
              port = 8080
            }
            initial_delay_seconds = 30
            period_seconds        = 10
          }

          readiness_probe {
            http_get {
              path = "/ready"
              port = 8080
            }
            initial_delay_seconds = 5
            period_seconds        = 5
          }
        }
      }
    }
  }

  depends_on = [
    kubernetes_namespace.self_healing,
    kubernetes_service_account.self_healing_controller,
    kubernetes_cluster_role_binding.self_healing_controller
  ]
}

# Создание Service для Self-Healing Controller
resource "kubernetes_service" "self_healing_controller" {
  metadata {
    name      = "self-healing-controller"
    namespace = kubernetes_namespace.self_healing.metadata[0].name
    labels = {
      app = "self-healing-controller"
    }
  }

  spec {
    selector = {
      app = "self-healing-controller"
    }

    port {
      port        = 8080
      target_port = 8080
      protocol    = "TCP"
      name        = "http"
    }

    type = "ClusterIP"
  }

  depends_on = [
    kubernetes_deployment.self_healing_controller
  ]
}

# Создание Deployment для тестового приложения
resource "kubernetes_deployment" "test_app" {
  metadata {
    name      = "test-app"
    namespace = kubernetes_namespace.test_app.metadata[0].name
    labels = {
      app = "test-app"
    }
  }

  spec {
    replicas = 3

    selector {
      match_labels = {
        app = "test-app"
      }
    }

    template {
      metadata {
        labels = {
          app = "test-app"
        }
      }

      spec {
        container {
          image = "nginx:latest"
          name  = "test-app"

          port {
            container_port = 80
          }

          resources {
            limits = {
              cpu    = "200m"
              memory = "256Mi"
            }
            requests = {
              cpu    = "100m"
              memory = "128Mi"
            }
          }

          liveness_probe {
            http_get {
              path = "/"
              port = 80
            }
            initial_delay_seconds = 30
            period_seconds        = 10
          }

          readiness_probe {
            http_get {
              path = "/"
              port = 80
            }
            initial_delay_seconds = 5
            period_seconds        = 5
          }
        }
      }
    }
  }

  depends_on = [
    kubernetes_namespace.test_app
  ]
}

# Создание Service для тестового приложения
resource "kubernetes_service" "test_app" {
  metadata {
    name      = "test-app"
    namespace = kubernetes_namespace.test_app.metadata[0].name
    labels = {
      app = "test-app"
    }
  }

  spec {
    selector = {
      app = "test-app"
    }

    port {
      port        = 80
      target_port = 80
      protocol    = "TCP"
      name        = "http"
    }

    port {
      port        = 8080
      target_port = 80
      protocol    = "TCP"
      name        = "http-alt"
    }

    type = "ClusterIP"
  }

  depends_on = [
    kubernetes_deployment.test_app
  ]
}

# Создание HorizontalPodAutoscaler для тестового приложения
resource "kubernetes_horizontal_pod_autoscaler" "test_app" {
  metadata {
    name      = "test-app-hpa"
    namespace = kubernetes_namespace.test_app.metadata[0].name
  }

  spec {
    max_replicas                      = 10
    min_replicas                      = 2
    target_cpu_utilization_percentage = 70

    scale_target_ref {
      api_version = "apps/v1"
      kind        = "Deployment"
      name        = kubernetes_deployment.test_app.metadata[0].name
    }
  }

  depends_on = [
    kubernetes_deployment.test_app
  ]
} 