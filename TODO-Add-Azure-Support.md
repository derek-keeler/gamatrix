# Azure hosting implementation plan

## Problem

Add a first-class Azure deployment path without destabilizing or materially changing the existing AWS production path. AWS remains the champion production environment; Azure must be additive, isolated, and configuration-driven. The Azure solution must use `azd` as the primary deployment entrypoint, `az` for lower-level operations where needed, Python for cross-platform operational scripting, GitHub Actions for deployment automation, Azure Key Vault for secrets, and config-as-code for all non-secret deployment settings.

## Current state

- The repository is AWS-first today.
  - `infrastructure/cdk/` defines the production stack with CDK.
  - The stack provisions DynamoDB, S3, SQS, three Lambdas (web, parser, enricher), API Gateway, Secrets Manager, SSM parameters, and custom-domain wiring.
- The application code is portable at the web framework layer but not at the cloud integration layer.
  - `src/gamatrix/app.py` is plain FastAPI and can run under Uvicorn.
  - `Dockerfile` already builds runnable Python images, but its production targets are Lambda-oriented.
  - `src/gamatrix/storage/*.py`, `src/gamatrix/config.py`, and `src/gamatrix/auth/service.py` are tightly coupled to AWS services via `boto3`.
- GitHub Actions currently provides CI and release tagging only. There is no Azure deployment workflow.
- There is no Azure infrastructure, Azure environment config, or Azure operational tooling in the repo today.

## Proposed approach

### 1. Preserve AWS as-is and add a parallel Azure deployment lane

- Keep `infrastructure/cdk/`, `just deploy`, and the AWS runtime path intact.
- Add a separate Azure infrastructure tree, likely `infrastructure/azure/`, owned by `azd` and Bicep.
- Avoid reusing AWS deployment config files for Azure; instead add Azure-specific config-as-code inputs so each cloud can evolve independently.

### 2. Target an Azure-native architecture that mirrors the existing responsibilities

Recommended design:

- **Web runtime:** Azure Container Apps running the FastAPI app under Uvicorn from a new container target optimized for non-Lambda hosting.
- **Image registry:** Azure Container Registry.
- **Uploads:** Azure Blob Storage with private containers and SAS/presigned-upload-style flow adapted from the current S3 pattern.
- **Background parser trigger:** Azure Function on Blob-created events or Event Grid + Function.
- **Background enrichment trigger:** Azure Function on Azure Queue Storage messages.
- **Primary data store:** Azure Cosmos DB (NoSQL) with a repository adapter that preserves current app-level semantics.
- **Secrets:** Azure Key Vault with managed identity access for runtime components.
- **Email:** Azure Communication Services Email if full parity is required, or SMTP if an approved external mail service is preferred for Azure.
- **Canonical domain / passkeys:** Azure-managed custom domain and TLS, with app settings continuing to enforce a single canonical HTTPS origin.

This keeps the same high-level flow as AWS:

1. Browser uploads DB directly to object storage.
2. Upload event triggers parsing.
3. Parsed ownership data is persisted.
4. Enrichment work is queued asynchronously.
5. The web app serves the same FastAPI UI/API and polls job status.

### 3. Introduce provider-aware seams instead of rewriting business logic

The safest implementation path is to isolate cloud-specific concerns behind small adapters while leaving routes, business logic, templates, and tests as unchanged as possible.

Planned code seams:

- **Settings/provider selection**
  - Add an explicit cloud/runtime provider setting.
  - Keep existing AWS env names working.
  - Add Azure-specific settings alongside them, not instead of them.
- **Repository abstraction**
  - Extract an interface/protocol for the persistence operations already centralized in `Repository`.
  - Keep the current DynamoDB implementation for AWS/local.
  - Add a Cosmos-backed implementation for Azure.
- **Object storage abstraction**
  - Keep the S3 implementation.
  - Add an Azure Blob implementation for direct browser uploads and downloads.
- **Queue abstraction**
  - Keep the SQS implementation.
  - Add an Azure Queue implementation.
- **Secret resolution**
  - Generalize secret lookup so JWT/IGDB credentials can come from Secrets Manager in AWS and Key Vault in Azure.
- **Email delivery**
  - Generalize the non-local email sender so AWS SES remains untouched and Azure gets its own sender implementation.

### 4. Make Azure deployment fully config-as-code

Planned Azure assets:

- `azure.yaml` for `azd`
- Bicep templates and modules for all Azure resources
- Environment variable and secret-name mapping files checked in as code
- Non-secret per-environment values in `azd` environment config
- Secret values stored only in Key Vault
- Role assignments and managed identity wiring declared in IaC

### 5. Add cross-platform Python operational tooling under `devops/`

Planned scripts:

- `devops/azure_setup.py`
  - bootstrap/validate local prerequisites
  - validate selected `azd` environment
  - create or verify required Key Vault secrets by name only where safe
  - wrap approved `azd` / `az` commands
- `devops/azure_teardown.py`
  - controlled removal flow for Azure resources/environment
  - explicit safety rails and environment targeting
- `devops/azure_status.py`
  - read-only status checks for resource health, deployed revisions, endpoint URLs, and identity/secret wiring state

All scripts should shell out to `azd` / `az`, remain host-portable across Windows/macOS/Linux, and follow the user's Python docstring expectations.

### 6. Add GitHub deployment automation without checked-in secrets

Recommended workflow design:

- Use GitHub Actions OIDC federation to Azure; do not store Azure client secrets in GitHub.
- Use environment-scoped GitHub variables for non-secret identifiers such as subscription ID, tenant ID, location, resource group, environment name, and Key Vault name.
- Run `azd auth login` / `az login` through the federated identity path inside the workflow.
- Run checked-in Python validation/setup helpers as needed.
- Run `azd provision` and `azd deploy` (or the equivalent split approved during implementation).
- Keep secret material in Azure Key Vault; the workflow should reference secret names and verify presence, not emit secret values.

## Implementation todos

1. Analyze the AWS-only deployment surface and define the adapter seams that let Azure be added without changing the working AWS deployment path.
2. Finalize the Azure architecture and service mappings for web, storage, queueing, data, secrets, email, and domain/TLS handling.
3. Introduce provider-aware configuration and service abstractions so Azure support can coexist with the current AWS code path.
4. Author `azd` + Bicep infrastructure and environment config for Azure resources and managed identities.
5. Add Python setup, teardown, and status scripts under `devops/`.
6. Add a GitHub Actions workflow for Azure deployment using OIDC and Key Vault.
7. Update documentation for Azure prerequisites, configuration, deployment, status checks, and teardown.

## Notes and constraints

- No Azure write/delete operations are permitted during planning or implementation validation in this session unless explicitly approved later.
- Read-only discovery against Azure is acceptable if needed during implementation.
- AWS deployment behavior should remain the default documented production path unless/until Azure is explicitly selected.
- The Docker build currently favors Lambda entrypoints; the Azure plan should add new targets rather than distort the existing Lambda targets.
- The Azure work will likely require new tests around provider selection, secret resolution, and Azure infrastructure rendering.
- Confirmed scope: Azure should target full production parity from the start, including uploads, async background processing, password-reset email, and passkey/custom-domain behavior.

## Resolved decision

Azure will target **full production parity** from the start rather than a reduced first cut.
