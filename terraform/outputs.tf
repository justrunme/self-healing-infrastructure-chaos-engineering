output "cluster_name" {
  description = "Name of the Kubernetes cluster"
  value       = var.cluster_name
}

output "monitoring_namespace" {
  description = "Namespace for monitoring components"
  value       = kubernetes_namespace.monitoring.metadata[0].name
}

output "chaos_engineering_namespace" {
  description = "Namespace for chaos engineering components"
  value       = kubernetes_namespace.chaos_engineering.metadata[0].name
}

output "self_healing_namespace" {
  description = "Namespace for self-healing components"
  value       = kubernetes_namespace.self_healing.metadata[0].name
}

output "kured_namespace" {
  description = "Namespace for Kured components"
  value       = kubernetes_namespace.kured.metadata[0].name
}

output "test_app_namespace" {
  description = "Namespace for test application"
  value       = kubernetes_namespace.test_app.metadata[0].name
}

output "prometheus_stack_name" {
  description = "Name of the Prometheus stack release"
  value       = helm_release.prometheus_stack.name
}

output "kured_release_name" {
  description = "Name of the Kured release"
  value       = "kured"
}

output "kured_version" {
  description = "Kured version deployed"
  value       = "deployed-via-github-actions"
}

output "self_healing_controller_service" {
  description = "Self-Healing Controller service details"
  value = {
    name      = kubernetes_service.self_healing_controller.metadata[0].name
    namespace = kubernetes_service.self_healing_controller.metadata[0].namespace
    port      = kubernetes_service.self_healing_controller.spec[0].port[0].port
  }
}

output "test_app_service" {
  description = "Test application service details"
  value = {
    name      = kubernetes_service.test_app.metadata[0].name
    namespace = kubernetes_service.test_app.metadata[0].namespace
    port      = kubernetes_service.test_app.spec[0].port[0].port
  }
}

output "grafana_url" {
  description = "Grafana access URL"
  value       = "http://localhost:3000"
}

output "prometheus_url" {
  description = "Prometheus access URL"
  value       = "http://localhost:9090"
}

output "alertmanager_url" {
  description = "Alertmanager access URL"
  value       = "http://localhost:9093"
}

output "self_healing_controller_url" {
  description = "Self-Healing Controller health check URL"
  value       = "http://localhost:8081/health"
}

output "test_app_url" {
  description = "Test application access URL"
  value       = "http://localhost:8080"
} 