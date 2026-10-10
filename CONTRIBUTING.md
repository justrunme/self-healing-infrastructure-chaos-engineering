# Contributing

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
# controller deps used by CI:
pip install -r kubernetes/self-healing/requirements.txt
pip install -r kubernetes/self-healing/requirements-dev.txt
pre-commit install   # optional
```

## Branch naming

- `feat/<short-name>`
- `fix/<short-name>`
- `chore/<short-name>`
- `docs/<short-name>`
- `ci/<short-name>`

## Commits

Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, `test:`, `ci:`.

## Tests

```bash
pytest kubernetes/self-healing/tests -m "not slow"
# chaos / infra scripts (cluster required):
bash scripts/test-self-healing.sh
bash scripts/test-chaos.sh
```

## Pull requests

Open against `main`. CI must be green. Squash merge preferred.

Checklist:

- [ ] Unit tests pass (`pytest`)
- [ ] Branch naming follows convention
- [ ] Conventional commits
- [ ] Helm / Kubernetes manifests stay valid
- [ ] Docs updated when recovery loops change
