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
  }
}

# Создание namespace для chaos engineering
resource "kubernetes_namespace" "chaos_engineering" {
  metadata {
    name = "chaos-engineering"
  }
}

# Создание namespace для self-healing
resource "kubernetes_namespace" "self_healing" {
  metadata {
    name = "self-healing"
  }
}

# Создание namespace для kured
resource "kubernetes_namespace" "kured" {
  metadata {
    name = "kured"
  }
}

# Создание namespace для тестового приложения
resource "kubernetes_namespace" "test_app" {
  metadata {
    name = "test-app"
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