variable "slack_webhook_url" {
  description = "Slack webhook URL for notifications"
  type        = string
  default     = ""
}

variable "slack_channel" {
  description = "Slack channel for notifications"
  type        = string
  default     = "#alerts"
}

variable "slack_notifications_enabled" {
  description = "Enable Slack notifications"
  type        = bool
  default     = false
}

variable "cluster_name" {
  description = "Name of the Kubernetes cluster"
  type        = string
  default     = "self-healing-cluster"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "prometheus_retention_days" {
  description = "Prometheus data retention in days"
  type        = number
  default     = 15
}

variable "grafana_admin_password" {
  description = "Grafana admin password"
  type        = string
  default     = "admin123"
  sensitive   = true
}

# Docker Registry Configuration
variable "docker_registry" {
  description = "Docker registry URL"
  type        = string
  default     = "ghcr.io"
}

variable "docker_image_name" {
  description = "Docker image name"
  type        = string
  default     = "justrunme/self-healing-infrastructure-chaos-engineering/self-healing-controller"
}

variable "docker_image_tag" {
  description = "Docker image tag"
  type        = string
  default     = "latest"
}

variable "self_healing_controller_image" {
  description = "Self-Healing Controller Docker image"
  type        = string
  default     = "ghcr.io/justrunme/self-healing-infrastructure-chaos-engineering/self-healing-controller:latest"
}

variable "alertmanager_config" {
  description = "Alertmanager configuration"
  type        = any
  default     = {
    global = {
      slack_api_url = ""
    }
    route = {
      group_by        = ["alertname"]
      group_wait      = "10s"
      group_interval  = "10s"
      repeat_interval = "1h"
      receiver        = "slack-notifications"
    }
    receivers = [
      {
        name = "slack-notifications"
        slack_configs = [
          {
            channel = "#alerts"
          }
        ]
      }
    ]
  }
} 