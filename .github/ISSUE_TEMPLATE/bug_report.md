---
name: Bug report
about: Create a report to help us improve
title: '[BUG] '
labels: ['bug', 'needs-triage']
assignees: ''
---

**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Deploy the system using '...'
2. Run chaos experiment '....'
3. See error

**Expected behavior**
A clear and concise description of what you expected to happen.

**Actual behavior**
A clear and concise description of what actually happened.

**Environment:**
 - OS: [e.g. macOS, Ubuntu]
 - Kubernetes Version: [e.g. 1.25.0]
 - Minikube Version: [e.g. 1.28.0]
 - Self-Healing Controller Version: [e.g. 1.0.0]

**Logs**
Please include relevant logs from:
- Self-Healing Controller: `kubectl logs -n self-healing -l app=self-healing-controller`
- Chaos Mesh: `kubectl logs -n chaos-engineering -l app=chaos-mesh`
- Test Application: `kubectl logs -n test-app -l app=test-app`

**Screenshots**
If applicable, add screenshots to help explain your problem.

**Additional context**
Add any other context about the problem here. 