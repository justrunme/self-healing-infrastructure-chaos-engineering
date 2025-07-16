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