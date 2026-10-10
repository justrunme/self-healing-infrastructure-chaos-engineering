# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-10-10

### Added
- Bounded remediation with per-namespace budget, per-object cooldown, and dry-run mode
- Approval gates (annotations) required before node reboot or drain
- Prometheus metrics: `remediations_total`, `brake_engaged`, `remediation_budget_remaining`
- Watch-based controller with resync instead of polling
- Honest CI with failure injection: crashloop remediation and brake exhaustion tests
- MkDocs documentation site and bounded remediation docs

### Changed
- Python runtime and base image updated to 3.12
- GitHub Actions, Docker, and Python dependency updates
- Docs site deploys only from `main`

### Fixed
- CI no longer masks self-healing failures; remediation and brake paths are asserted
- GitHub Pages / MkDocs build and workflow reliability issues

## [1.0.2] - 2025-07-19

### Changed
- Release workflow improvements: `workflow_dispatch`, full history checkout, clearer permissions
- Conditional Terraform image variable update on release

## [1.0.1] - 2025-07-19

### Changed
- README cleanup and structure improvements
- Release notes and container image tagging for GHCR

### Fixed
- Release workflow Terraform update made conditional when `terraform.tfvars` is absent

## [1.0.0] - 2025-07-16

### Added
- Initial self-healing controller, chaos-engineering integration, and monitoring stack
- Terraform and Helm packaging for deployment
- CI/CD pipeline for lint, tests, and image builds
