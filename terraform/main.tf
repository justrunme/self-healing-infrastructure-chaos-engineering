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
    time = {
      source  = "hashicorp/time"
      version = "~> 0.9"
    }
  }
}

provider "kubernetes" {
  # In CI/CD, Terraform will automatically use kubectl context
  # No explicit configuration needed - it will use KUBECONFIG env var
}

provider "helm" {
  kubernetes {
    # In CI/CD, Terraform will automatically use kubectl context
    # No explicit configuration needed - it will use KUBECONFIG env var
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
    labels = {
      app = "slack-notifications"
    }
  }

  data = {
    "webhook_url" = base64encode(var.slack_webhook_url)
    "channel"     = base64encode(var.slack_channel)
  }

  type = "Opaque"
}

# Создание Secret для Self-Healing Controller
resource "kubernetes_secret" "self_healing_secret" {
  metadata {
    name      = "self-healing-secret"
    namespace = kubernetes_namespace.self_healing.metadata[0].name
    labels = {
      app = "self-healing-controller"
    }
  }

  data = {
    "slack_webhook_url" = base64encode(var.slack_webhook_url)
    "slack_channel"     = base64encode(var.slack_channel)
    "grafana_admin_password" = base64encode(var.grafana_admin_password)
  }

  type = "Opaque"
}

# Создание Secret для Prometheus
resource "kubernetes_secret" "prometheus_secret" {
  metadata {
    name      = "prometheus-secret"
    namespace = kubernetes_namespace.monitoring.metadata[0].name
    labels = {
      app = "prometheus"
    }
  }

  data = {
    "admin_password" = base64encode(var.grafana_admin_password)
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

# Kured will be deployed via GitHub Actions workflow
# This ensures proper deployment in CI/CD environment

# Развертывание Chaos Mesh
resource "kubernetes_manifest" "chaos_mesh_deployment" {
  provider = kubernetes
  manifest = yamldecode(file("${path.module}/../kubernetes/chaos-engineering/chaos-mesh-deployment.yaml"))
  
  # Игнорируем изменения в env переменных, которые могут быть конвертированы Kubernetes API
  lifecycle {
    ignore_changes = [
      manifest["spec"]["template"]["spec"]["containers"][0]["env"]
    ]
  }
  
  depends_on = [
    kubernetes_namespace.chaos_engineering
  ]
}

# Установка Chaos Mesh CRD
resource "kubernetes_manifest" "chaos_mesh_crd" {
  provider = kubernetes
  for_each = toset([
    for doc in split("---", file("${path.module}/../kubernetes/chaos-engineering/chaos-mesh-crd.yaml")) : 
    trimspace(doc) if length(trimspace(doc)) > 0
  ])
  
  manifest = yamldecode(each.value)
  
  depends_on = [
    kubernetes_manifest.chaos_mesh_deployment
  ]
}

# Ждем готовности CRD
resource "time_sleep" "wait_for_crd" {
  depends_on = [kubernetes_manifest.chaos_mesh_crd]
  create_duration = "30s"
  count = var.enable_chaos_experiments ? 1 : 0
}

# Развертывание Chaos экспериментов
resource "kubernetes_manifest" "chaos_experiments" {
  provider = kubernetes
  for_each = var.enable_chaos_experiments ? toset([
    for doc in split("---", file("${path.module}/../kubernetes/chaos-engineering/chaos-experiments.yaml")) : 
    trimspace(doc) if length(trimspace(doc)) > 0
  ]) : []
  
  manifest = yamldecode(each.value)
  
  depends_on = [
    time_sleep.wait_for_crd[0]
  ]
}

# Развертывание Backup системы - разделяем на отдельные ресурсы
resource "kubernetes_manifest" "backup_cronjob" {
  provider = kubernetes
  manifest = yamldecode(split("---", file("${path.module}/../kubernetes/backup/backup-cronjob.yaml"))[0])
  
  depends_on = [
    kubernetes_namespace.monitoring
  ]
}

resource "kubernetes_manifest" "backup_service_account" {
  provider = kubernetes
  manifest = yamldecode(split("---", file("${path.module}/../kubernetes/backup/backup-cronjob.yaml"))[1])
  
  depends_on = [
    kubernetes_namespace.monitoring
  ]
}

resource "kubernetes_manifest" "backup_cluster_role" {
  provider = kubernetes
  manifest = yamldecode(split("---", file("${path.module}/../kubernetes/backup/backup-cronjob.yaml"))[2])
  
  depends_on = [
    kubernetes_namespace.monitoring
  ]
}

resource "kubernetes_manifest" "backup_cluster_role_binding" {
  provider = kubernetes
  manifest = yamldecode(split("---", file("${path.module}/../kubernetes/backup/backup-cronjob.yaml"))[3])
  
  depends_on = [
    kubernetes_namespace.monitoring
  ]
}

resource "kubernetes_manifest" "backup_pvc" {
  provider = kubernetes
  manifest = yamldecode(split("---", file("${path.module}/../kubernetes/backup/backup-cronjob.yaml"))[4])
  
  depends_on = [
    kubernetes_namespace.monitoring
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
          image_pull_policy = "IfNotPresent"

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
            timeout_seconds       = 5
            failure_threshold     = 3
            success_threshold     = 1
          }

          readiness_probe {
            http_get {
              path = "/ready"
              port = 8080
            }
            initial_delay_seconds = 5
            period_seconds        = 5
            timeout_seconds       = 3
            failure_threshold     = 3
            success_threshold     = 1
          }

          startup_probe {
            http_get {
              path = "/health"
              port = 8080
            }
            initial_delay_seconds = 10
            period_seconds        = 5
            timeout_seconds       = 3
            failure_threshold     = 30
            success_threshold     = 1
          }

          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = true
            run_as_non_root            = true
            run_as_user                = 1000
            capabilities {
              drop = ["ALL"]
            }
          }
        }

        security_context {
          fs_group        = 1000
          run_as_group    = 1000
          run_as_non_root = true
          run_as_user     = 1000
        }
      }
    }
  }

  # Не ждём завершения rollout-а, чтобы Terraform не застревал
  wait_for_rollout = false

  # Завершаем create после 2 минут, если будет висеть
  timeouts {
    create = "2m"
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
    replicas = 2  # Уменьшаем до min_replicas HPA

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
        # Создаём пустой каталог, в который nginx сможет писать
        volume {
          name = "nginx-cache"
          empty_dir {}
        }

        container {
          image = "nginx:1.21-alpine"
          name  = "test-app"

          port {
            container_port = 80
            name          = "http"
          }

          # Монтируем volume внутрь контейнера для nginx кеша
          volume_mount {
            name       = "nginx-cache"
            mount_path = "/var/cache/nginx"
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
            initial_delay_seconds = 15  # Уменьшаем задержку
            period_seconds        = 10
            timeout_seconds       = 3   # Уменьшаем таймаут
            failure_threshold     = 3
            success_threshold     = 1
          }

          readiness_probe {
            http_get {
              path = "/"
              port = 80
            }
            initial_delay_seconds = 2  # Уменьшаем задержку
            period_seconds        = 3  # Уменьшаем период
            timeout_seconds       = 2  # Уменьшаем таймаут
            failure_threshold     = 2  # Уменьшаем порог ошибок
            success_threshold     = 1
          }

          security_context {
            allow_privilege_escalation = false
            read_only_root_filesystem  = false
            run_as_non_root            = false  # Разрешаем запуск от root для nginx
            run_as_user                = 0      # Запускаем от root
            capabilities {
              drop = ["ALL"]
            }
          }
        }

        security_context {
          fs_group        = 0
          run_as_group    = 0
          run_as_non_root = false  # Разрешаем запуск от root для nginx
          run_as_user     = 0
        }
      }
    }
  }

  # Не ждём завершения rollout-а, чтобы Terraform не застревал
  wait_for_rollout = false

  # Завершаем create после 2 минут, если будет висеть
  timeouts {
    create = "2m"
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

# Network Policy для Self-Healing Controller
resource "kubernetes_network_policy" "self_healing_controller" {
  metadata {
    name      = "self-healing-controller-network-policy"
    namespace = kubernetes_namespace.self_healing.metadata[0].name
  }

  spec {
    pod_selector {
      match_labels = {
        app = "self-healing-controller"
      }
    }

    policy_types = ["Ingress", "Egress"]

    ingress {
      from {
        namespace_selector {
          match_labels = {
            name = "monitoring"
          }
        }
      }
      ports {
        port     = 8080
        protocol = "TCP"
      }
    }

    ingress {
      from {
        namespace_selector {
          match_labels = {
            name = "kube-system"
          }
        }
      }
      ports {
        port     = 8080
        protocol = "TCP"
      }
    }

    egress {
      to {
        namespace_selector {
          match_labels = {
            name = "monitoring"
          }
        }
      }
      ports {
        port     = 9090
        protocol = "TCP"
      }
    }

    egress {
      to {
        namespace_selector {
          match_labels = {
            name = "chaos-engineering"
          }
        }
      }
      ports {
        port     = 10080
        protocol = "TCP"
      }
    }

    egress {
      to {
        namespace_selector {
          match_labels = {
            name = "test-app"
          }
        }
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

  depends_on = [
    kubernetes_namespace.self_healing
  ]
}

# Network Policy для Test Application
resource "kubernetes_network_policy" "test_app" {
  metadata {
    name      = "test-app-network-policy"
    namespace = kubernetes_namespace.test_app.metadata[0].name
  }

  spec {
    pod_selector {
      match_labels = {
        app = "test-app"
      }
    }

    policy_types = ["Ingress", "Egress"]

    ingress {
      from {
        namespace_selector {
          match_labels = {
            name = "self-healing"
          }
        }
      }
      ports {
        port     = 80
        protocol = "TCP"
      }
    }

    ingress {
      from {
        namespace_selector {
          match_labels = {
            name = "monitoring"
          }
        }
      }
      ports {
        port     = 80
        protocol = "TCP"
      }
    }

    egress {
      to {
        namespace_selector {
          match_labels = {
            name = "monitoring"
          }
        }
      }
      ports {
        port     = 9090
        protocol = "TCP"
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

  depends_on = [
    kubernetes_namespace.test_app
  ]
}

# Network Policy для Monitoring
resource "kubernetes_network_policy" "monitoring" {
  metadata {
    name      = "monitoring-network-policy"
    namespace = kubernetes_namespace.monitoring.metadata[0].name
  }

  spec {
    pod_selector {
      match_labels = {
        app = "prometheus"
      }
    }

    policy_types = ["Ingress", "Egress"]

    ingress {
      from {
        namespace_selector {
          match_labels = {
            name = "self-healing"
          }
        }
      }
      ports {
        port     = 9090
        protocol = "TCP"
      }
    }

    ingress {
      from {
        namespace_selector {
          match_labels = {
            name = "test-app"
          }
        }
      }
      ports {
        port     = 9090
        protocol = "TCP"
      }
    }

    egress {
      to {
        namespace_selector {
          match_labels = {
            name = "self-healing"
          }
        }
      }
      ports {
        port     = 8080
        protocol = "TCP"
      }
    }

    egress {
      to {
        namespace_selector {
          match_labels = {
            name = "test-app"
          }
        }
      }
      ports {
        port     = 80
        protocol = "TCP"
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

  depends_on = [
    kubernetes_namespace.monitoring
  ]
} 