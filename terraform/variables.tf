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

variable "alertmanager_config" {
  description = "Alertmanager configuration"
  type        = map(any)
  default = {
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