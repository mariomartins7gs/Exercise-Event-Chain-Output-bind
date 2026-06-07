# 05 — CI/CD Pipeline (GitHub Actions)

## Workflow: `deploy.yml`

**Triggers**: `push` to `main`, `pull_request` to `main`, `workflow_dispatch`

**6 sequential jobs**:

```yaml
name: Deploy Order Processing Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

env:
  AZURE_FUNCTIONAPP_NAME: func-order-processing-${{ vars.SUFFIX }}
  AZURE_RESOURCE_GROUP: rg-order-processing-${{ vars.SUFFIX }}
  PYTHON_VERSION: '3.11'
  INFRA_DIR: 'infra'
```

## Job 1: Lint (fastest — ~1min)

| Step | Action | Tool |
|---|---|---|
| Checkout | `actions/checkout@v4` | Git |
| Setup Python | `actions/setup-python@v5` | Python 3.11 |
| Install deps | `pip install flake8 black` | flake8 + black |
| Lint | `flake8 src/ --max-complexity=10` | flake8 |
| Format check | `black --check src/` | black |

## Job 2: Test (~2min)

| Step | Action |
|---|---|
| Checkout | `actions/checkout@v4` |
| Setup Python | Python 3.11 |
| Install | `pip install pytest pytest-asyncio pytest-cov pytest-mock httpx` |
| Install project deps | `pip install -r requirements.txt` |
| Run tests | `pytest test/ -v --cov=src --cov-report=xml --cov-report=term-missing` |
| Upload coverage | `codecov/codecov-action@v4` |

## Job 3: Build (~1min)

| Step | Action |
|---|---|
| Checkout | `actions/checkout@v4` |
| Build package | Copy `src/`, `host.json`, `requirements.txt` → `deployment/` → `zip -r function-app.zip .` |
| Upload | `actions/upload-artifact@v4` |

## Job 4: Deploy Infrastructure (Bicep) — ~5min

*Only runs on `main` branch.*

| Step | Action |
|---|---|
| Checkout | `actions/checkout@v4` |
| Azure Login | `azure/login@v2` (OIDC or SP) |
| Deploy Bicep | `azure/arm-deploy@v2` with `template: ./infra/main.bicep` |

**Parameters**: `suffix=${{ vars.SUFFIX }}`, `location=${{ vars.LOCATION }}`

## Job 5: Deploy Functions (~2min)

| Step | Action |
|---|---|
| Download artifact | `actions/download-artifact@v4` |
| Azure Login | `azure/login@v2` |
| Deploy | `Azure/functions-action@v1` with zip deploy, SCM build |

## Job 6: Deploy Webapp (~1min)

| Step | Action |
|---|---|
| Checkout | `actions/checkout@v4` |
| Azure Login | `azure/login@v2` |
| Upload to `$web` | `az storage blob upload-batch --destination '$web' --source webapp/ --auth-mode login` |

## Required GitHub Secrets

| Secret | Purpose |
|---|---|
| `AZURE_CLIENT_ID` | Service principal app ID (for `azure/login@v2`) |
| `AZURE_TENANT_ID` | Azure AD tenant |
| `AZURE_SUBSCRIPTION_ID` | Subscription |

## Required GitHub Variables

| Variable | Example | Purpose |
|---|---|---|
| `SUFFIX` | `a1b2c3` | Unique suffix for resource naming |
| `LOCATION` | `westeurope` | Azure region |
