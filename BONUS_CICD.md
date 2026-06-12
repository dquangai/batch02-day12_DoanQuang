# Bonus CI/CD Evidence

## Requirement

Bonus asks for a GitHub Actions CI/CD pipeline that deploys the agent to Railway or Render, with:

- CI stage: code lint.
- CI stage: unit tests with coverage.
- CD stage: deploy.
- Demo evidence.

## Implemented Files

- `.github/workflows/ci-cd.yml`
- `tests/test_app.py`
- `requirements-dev.txt`
- `pyproject.toml`

## CI Stages

The `ci` job runs on pull requests and pushes:

1. Starts Redis service for production-like tests.
2. Installs `requirements.txt` and `requirements-dev.txt`.
3. Runs `ruff check app tests`.
4. Runs `pytest` with coverage threshold from `pyproject.toml`.
5. Runs `python 06-lab-complete/check_production_ready.py`.
6. Runs `docker compose config`.

The `docker-build` job builds the final Docker image after CI passes.

## CD Stages

Deployment is controlled by repository variable `DEPLOY_TARGET`:

- `DEPLOY_TARGET=railway`: runs `railway up --service "$RAILWAY_SERVICE" --detach`.
- `DEPLOY_TARGET=render`: calls Render deploy hook.

Required GitHub secrets:

- Railway: `RAILWAY_TOKEN`, `RAILWAY_SERVICE`.
- Render: `RENDER_DEPLOY_HOOK_URL`.

## Demo Commands

Local demo equivalent:

```bash
ruff check app tests
pytest
python 06-lab-complete/check_production_ready.py
docker compose config
docker build -t day12-agent:bonus .
```

Expected results:

- Lint passes.
- Unit tests pass with coverage at or above 75%.
- Production readiness checker reports 100%.
- Docker config is valid.
- Docker image builds under 500 MB.

## Local Verification Result

Verified on 2026-06-12:

- `ruff check app tests --no-cache`: all checks passed.
- `pytest`: 5 passed.
- Coverage: 75.49%, threshold 75%.
- `06-lab-complete/check_production_ready.py`: 20/20 checks, 100%.
