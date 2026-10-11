# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.0] - 2026-10-11

Version numbering continues the v2.x line after legacy `v2.1.1` (Jul 2025).
`v1.1.0` (Oct 2026) remains a valid prior release on the interim 1.x track;
this release re-aligns the newest tag with the historical 2.x series.

### Added
- OpenSSF Scorecard workflow and release supply-chain controls: keyless Cosign signing, SPDX SBOM, and build provenance attestations
- Remediation demo recording and measured time-to-remediation (20.1s) with weekly/manual `demo-results` workflow
- `docs/EVIDENCE.md` claim/status standard with README link
- Contributing guide and GitHub issue/PR templates
- Security policy, LICENSE, and Dependabot configuration

### Fixed
- Remediation safety: brake and skip paths no longer consume namespace/workload budget or reset cooldowns
- Owner-aware deletes: only controller-owned pods are deleted gracefully; bare pods are skipped with an Event and metric
- Helm rollback only when a real Helm release (secret + annotation) exists
- Replace ineffective kured Node annotation with an approved cordon
- Lease leader election with 2 replicas and least-privilege RBAC (no cluster-wide secrets or apps write)

### Changed
- README header refreshed for consistent pinned layout
- `DRY_RUN` now defaults to `true`; live remediation requires `DRY_RUN=false` and a non-empty `REMEDIATION_NAMESPACES` allowlist

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
