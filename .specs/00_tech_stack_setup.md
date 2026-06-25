# Technology Stack Setup

## 1. Purpose

This document defines the implementation technology stack for MemoryRepo.

MemoryRepo will use a **Node.js-first service layer** for API, MCP, and product-facing workflows, with **Python services and workers** for machine-learning, retrieval evaluation, data validation, and model operations.

The architecture is intentionally hybrid:

```text
Node.js / Express / ESM
    -> API gateway, MCP server, session and entitlement orchestration

Python
    -> ML inference adapters, retrieval evaluation, compaction workers,
       PageIndex processing, data-quality checks, model monitoring
```

This keeps the real-time API ergonomic for JavaScript and MCP ecosystems while preserving Python for the ML-heavy path.

---

## 2. Final recommended stack

| Layer | Primary tool | Role |
|---|---|---|
| Infrastructure as code | Terraform | Provision AWS resources reproducibly. |
| CI/CD | GitHub Actions | Build, test, scan, deploy from `dev` and `main`. |
| Runtime | Node.js LTS with ESM | API and MCP service runtime. |
| API framework | Express | REST API, middleware, health checks, routing. |
| MCP | TypeScript MCP SDK | Local stdio and remote Streamable HTTP tools. |
| ORM | Prisma | Durable relational application data where relational modeling is useful. |
| Ephemeral state and vector search | Valkey | Session TTL, locks, counters, entitlement cache, vector retrieval. |
| Durable operational state | DynamoDB | Entitlements, sessions, jobs, idempotency, audit events. |
| Structured retrieval | PageIndex | Long-form, hierarchical context artifacts. |
| Object storage | Amazon S3 | PageIndex artifacts, datasets, model artifacts, evaluations. |
| Queue | Amazon SQS FIFO | Ordered session-level background jobs. |
| ML serving | Amazon SageMaker AI | Embeddings, reranking, compaction, optional long-context models. |
| ML lifecycle | MLflow | Experiment tracking, model registry, model and prompt versioning. |
| Product analytics | PostHog | User events, funnels, feature flags, experiments. |
| API/infrastructure observability | OpenTelemetry + CloudWatch initially | Traces, logs, metrics, AWS-native alarms. |
| Optional unified observability | Datadog | APM, infrastructure, LLM-agent observability, dashboards. |
| Data quality | Great Expectations | Data schema, freshness, integrity, distribution checks. |
| Data/model drift | Evidently | Drift, data statistics, model performance reports. |
| Error tracking | Sentry | Application exceptions, stack traces, release health. |
| Load testing | k6 | API and MCP performance validation. |
| Containerization | Docker | Local development, ECS, and SageMaker custom images. |
| Package managers | Yarn for Node, uv for Python | Reproducible dependency management. |

---

## 3. Core architecture decision

## 3.1 Node.js owns the synchronous product path

Node.js services should own:

- Express REST API.
- Remote MCP server.
- Authentication middleware.
- Entitlement lookup orchestration.
- Session create-or-get.
- Valkey Lua-script invocation.
- Memory add/get/remove orchestration.
- API request validation.
- API response shaping.
- PostHog event capture.
- OpenTelemetry request tracing.
- SQS enqueue for background work.

This is the path that needs quick response times for IDE, MCP, and agent clients.

## 3.2 Python owns ML and data-heavy workflows

Python services should own:

- Embedding and reranker evaluation.
- Model-training or benchmark jobs.
- Compaction worker logic.
- PageIndex build and retrieval adapters.
- Great Expectations data checks.
- Evidently drift reports.
- Offline retrieval evaluation.
- MLflow tracking and model registration.
- SageMaker model packaging and inference adapters.
- Statistical monitoring and feature-distribution analysis.

Python should not be required for every normal API request unless the Node service calls a SageMaker endpoint or a small internal Python service through a controlled interface.

---

## 4. Node.js and Express setup

## 4.1 Runtime

Use:

```text
Node.js LTS
TypeScript
ES Modules only
Yarn
```

Do not use CommonJS for new code.

Required root configuration:

```json
{
  "type": "module",
  "packageManager": "yarn@<pinned-version>"
}
```

## 4.2 Express role

Express should provide:

- `/v1` REST routes.
- Authentication middleware.
- Correlation-ID middleware.
- Request body size limits.
- Rate-limit middleware.
- Zod schema validation.
- Health and readiness routes.
- Error middleware.
- OpenTelemetry instrumentation.
- PostHog event forwarding.
- Internal service adapters.

Recommended Node packages:

```text
express
typescript
tsx
zod
pino
pino-http
ioredis
@aws-sdk/client-dynamodb
@aws-sdk/lib-dynamodb
@aws-sdk/client-sqs
@aws-sdk/client-s3
@aws-sdk/client-sagemaker-runtime
@aws-sdk/client-cognito-identity-provider
@opentelemetry/api
@opentelemetry/sdk-node
@opentelemetry/auto-instrumentations-node
posthog-node
@prisma/client
```

Recommended supporting packages:

```text
helmet
cors
express-rate-limit
jose
ulid
prom-client
```

## 4.3 Validation

Use Zod for all external input:

- REST request bodies.
- Query parameters.
- MCP tool input.
- Environment configuration.
- SQS messages.
- Internal job payloads.

Never trust client-provided:

```text
user_id
owner_user_id
token_count
plan_limit
session_state
memory_state
```

---

## 5. ESM Node.js folder structure

```text
memoryrepo/
  apps/
    api/
      src/
        server.ts
        app.ts
        routes/
        middleware/
        controllers/
        services/
        repositories/
        clients/
        schemas/
        telemetry/
      package.json

    mcp/
      src/
        server.ts
        tools/
        transport/
        clients/
        schemas/
      package.json

  packages/
    shared-ts/
      src/
        errors/
        ids/
        types/
        config/
        logging/
        contracts/
      package.json

    db/
      prisma/
        schema.prisma
        migrations/
      src/
      package.json

  python/
    memoryrepo_ml/
      src/
        memoryrepo_ml/
          embeddings/
          compaction/
          pageindex/
          evaluation/
          monitoring/
          data_quality/
          jobs/
      pyproject.toml

    services/
      worker/
      evaluation/
      inference_adapter/

  infra/
    modules/
    environments/

  tests/
    node/
    python/
    contract/
    integration/
    load/
```

---

## 6. Python and Node.js hybrid boundaries

## 6.1 Communication rules

Use the following communication patterns:

| Need | Preferred approach |
|---|---|
| Fast online embedding | Node service invokes SageMaker Runtime directly. |
| Compaction job | Node or worker enqueues SQS job, Python worker processes it. |
| PageIndex build | Python worker consumes session-scoped SQS job. |
| Retrieval evaluation | Python CLI or GitHub Actions job. |
| Data quality checks | Python batch job with Great Expectations. |
| Drift report | Python scheduled job with Evidently. |
| Model registry | Python MLflow client. |
| API contract ownership | Node/OpenAPI source of truth. |
| Shared event schemas | JSON Schema or TypeScript/Pydantic-generated contract artifacts. |

## 6.2 Avoid direct database coupling

Node and Python must not independently invent different storage schemas.

Use:

- Shared JSON schemas for messages.
- Explicit SQS message versions.
- OpenAPI for REST interfaces.
- Prisma schema for relational data.
- DynamoDB entity definitions documented in code and architecture docs.
- Contract tests across Node and Python boundaries.

---

## 7. Terraform setup

Terraform owns AWS infrastructure.

## 7.1 Required modules

```text
vpc
security_groups
ecr
ecs_cluster
ecs_service
elasticache_valkey
dynamodb
s3
sqs
cognito
api_gateway
waf
sagemaker
cloudwatch
iam
github_oidc
kms
```

## 7.2 State

Use separate encrypted remote state for:

```text
dev
stage
prod
```

Recommended state backend:

```text
Amazon S3 with versioning and encryption
Terraform S3 lockfile
```

## 7.3 Environment promotion

```text
feature branch -> PR checks only
dev            -> automatic Terraform apply to development
main           -> production plan + protected approval + apply
```

---

## 8. GitHub Actions setup

## 8.1 Required workflows

```text
pr-checks.yml
dev-deploy.yml
prod-deploy.yml
terraform-plan.yml
security-scan.yml
model-evaluation.yml
nightly-validation.yml
manual-rollback.yml
```

## 8.2 Branch policy

```text
feature/* -> squash merge -> dev
dev       -> normal merge commit -> main
```

## 8.3 AWS authentication

Use GitHub Actions OIDC to assume AWS IAM roles.

Do not store long-lived AWS access keys in GitHub Secrets.

Use separate roles for:

```text
plan-only
dev deployment
production deployment
model evaluation
rollback
```

---

## 9. Valkey setup

Valkey is the low-latency active-session and vector-retrieval layer.

## 9.1 Use Valkey for

- Session metadata.
- Three-hour sliding TTL.
- Active-session index.
- Session counters.
- Token budget counters.
- Idempotency cache.
- Entitlement cache.
- Distributed worker locks.
- Session-local vector search.
- Query embedding cache.
- PageIndex artifact pointers.

## 9.2 Do not use Valkey for

- Permanent billing records.
- Durable audit history.
- Permanent user profiles.
- Long-term source-of-truth plan data.
- Large document blobs.
- Model artifacts.

## 9.3 Node client

Use:

```text
ioredis
```

Requirements:

- Persistent connection pool.
- TLS in production.
- Lua scripts for atomic session and token operations.
- No `KEYS` command in production.
- Use namespaced keys.
- Monitor memory, evictions, command latency, and connected clients.

---

## 10. DynamoDB setup

DynamoDB is the durable operational datastore.

## 10.1 Tables

```text
memoryrepo-users
memoryrepo-plans
memoryrepo-entitlements
memoryrepo-sessions
memoryrepo-idempotency
memoryrepo-audit-events
memoryrepo-jobs
```

## 10.2 Use DynamoDB for

- Plan definitions.
- User entitlements.
- Durable session lifecycle record.
- Job lifecycle.
- Audit history.
- Idempotency records beyond short Valkey TTL.
- Administrative configuration.

## 10.3 ORM note

Prisma does **not** support DynamoDB as its database connector.

Therefore:

```text
Prisma is for relational data only.
DynamoDB uses AWS SDK repositories.
```

This is intentional.

---

## 11. Prisma setup

## 11.1 Why Prisma is included

Use Prisma only if MemoryRepo needs relational application data such as:

- Organization and team tenancy.
- Billing-account records.
- Subscription integration metadata.
- Admin users and roles.
- Project/workspace catalog.
- User settings.
- Usage aggregation for invoicing.
- Support-ticket or internal workflow data.

For the session-memory MVP, Prisma can remain present but unused until relational requirements exist.

## 11.2 Recommended relational database

When Prisma becomes active, use:

```text
PostgreSQL on Amazon RDS or Aurora PostgreSQL
```

## 11.3 Prisma role

```text
Prisma
    -> PostgreSQL
    -> relational account and commercial data

AWS SDK
    -> DynamoDB
    -> entitlement/session/job/audit operational data

ioredis
    -> Valkey
    -> hot active-session data
```

Do not try to force all data through Prisma.

---

## 12. VectorDB and PageIndex setup

## 12.1 Vector database choice

Use Valkey vector search first.

Reason:

- Session-local data is already in Valkey.
- TTL and vector retrieval share the same lifecycle.
- User/session filters stay close to authorization boundary.
- No extra vector database is needed for MVP.

## 12.2 Future dedicated VectorDB decision

Evaluate a separate vector database only when one or more conditions occur:

- Persistent long-term memory is introduced.
- Index size exceeds Valkey cost or performance envelope.
- Cross-session retrieval becomes a core requirement.
- Advanced hybrid search requires a specialized engine.
- Multi-region retrieval becomes necessary.

Potential future choices:

```text
OpenSearch Serverless
pgvector on Aurora PostgreSQL
Pinecone
Weaviate
Qdrant
```

Do not add a second vector database before an explicit benchmark and architecture decision record.

## 12.3 PageIndex role

PageIndex is not the vector database.

Use PageIndex for:

- Long-form structured documents.
- Compacted session history.
- Codebase-level trees.
- Large tool-output collections.
- Hierarchical retrieval artifacts.

Store PageIndex artifacts in:

```text
S3
```

Store current artifact metadata and pointer in:

```text
Valkey
```

Build artifacts through:

```text
Python worker + SQS FIFO
```

---

## 13. Product analytics and feature flags

## 13.1 PostHog

Use PostHog for:

- Product analytics.
- User activation funnels.
- Feature flags.
- Controlled experiments.
- Usage analytics by plan.
- Client and server event capture.

Recommended MemoryRepo events:

```text
session_resolved
session_created
session_expired
memory_added
memory_duplicate_detected
memory_removed
memory_retrieved
memory_compaction_requested
memory_compaction_completed
mcp_tool_called
mcp_tool_failed
plan_limit_reached
feature_flag_evaluated
```

Feature flags are appropriate for staged rollout of:

```text
reranker
pageindex
automatic_compaction
TurboQuant experiment
new embedding model
new retrieval weights
```

PostHog feature flags support targeted toggles without redeploying, making them appropriate for safe incremental rollout. citeturn107067search0

## 13.2 Product analytics privacy rules

Do not send:

- Raw memory content.
- Raw prompt text.
- Full tool output.
- Access tokens.
- Embeddings.
- Sensitive document excerpts.

Send only:

- Event names.
- Plan tier.
- Feature-flag value.
- Success/failure.
- Latency bucket.
- Token-count bucket.
- Retrieval mode.
- Pseudonymous user/session identifiers.

---

## 14. API, infrastructure, and performance monitoring

## 14.1 Recommended baseline: OpenTelemetry + CloudWatch

Use this from day one.

| Capability | Tool |
|---|---|
| Distributed traces | OpenTelemetry SDK |
| AWS logs | CloudWatch Logs |
| AWS metrics | CloudWatch Metrics |
| Dashboards | CloudWatch Dashboards |
| AWS alarms | CloudWatch Alarms |
| ECS, SQS, DynamoDB, SageMaker metrics | AWS-native CloudWatch metrics |
| Application metrics | OpenTelemetry metrics or Prometheus-compatible metrics |

This is the lowest-cost AWS-native baseline.

## 14.2 Error monitoring: Sentry

Use Sentry for:

- Node API exceptions.
- Python worker exceptions.
- Release tracking.
- Stack traces.
- Error grouping.
- Regression visibility.

Sentry complements CloudWatch. It should not replace CloudWatch alarms for infrastructure events.

## 14.3 Optional unified observability: Datadog

You likely meant **Datadog**, not “Datahog.”

Use Datadog if you want one commercial platform for:

- API performance monitoring.
- Distributed tracing.
- Logs.
- Infrastructure monitoring.
- ECS and AWS dashboards.
- Alerting.
- LLM and agent observability.

Datadog’s Agent Observability supports tracing and monitoring LLM applications and agent workflows, including token usage, latency, errors, evaluations, and production troubleshooting. citeturn107067search1turn107067search19turn107067search25

### Recommendation

For a portfolio or early project:

```text
OpenTelemetry + CloudWatch + Sentry
```

For a production-style unified platform:

```text
Datadog + OpenTelemetry
```

Do not run Datadog, Grafana, Sentry, PostHog, and multiple LLM observability products at full depth on day one. That creates noisy instrumentation and duplicated cost.

---

## 15. LLM and ML model monitoring

## 15.1 MLflow

Use MLflow for:

- Experiment tracking.
- Parameter tracking.
- Metric tracking.
- Artifact tracking.
- Model registry.
- Model aliases.
- Model versioning.
- Prompt and LLM application versioning.
- Evaluation records.

MLflow Model Registry supports centralized lifecycle management, including model versions, aliases, lineage, and metadata. citeturn107067search2turn107067search10

Recommended tracked fields:

```text
embedding_model_version
reranker_model_version
compactor_model_version
tokenizer_version
dataset_version
retrieval_eval_version
prompt_template_version
container_image_digest
git_commit
latency_metrics
quality_metrics
cost_metrics
```

## 15.2 LLM observability

Choose one primary implementation:

### Option A: Datadog LLM Observability

Best when Datadog is already selected for infrastructure/APM.

Track:

- LLM traces.
- Model calls.
- Prompt and response metadata under redaction policy.
- Token usage.
- Cost.
- Latency.
- Tool calls.
- Agent failures.
- Evaluation outcomes.

### Option B: Langfuse

Best when you want an LLM-native, open-source-friendly observability platform.

Use it for:

- Prompt versions.
- Traces.
- Datasets.
- Evaluations.
- Cost and token visibility.
- Agent workflow inspection.

### Recommendation

```text
Early project:
    MLflow + OpenTelemetry + CloudWatch

Production-like AI observability:
    MLflow + Datadog LLM Observability
or
    MLflow + Langfuse
```

Use one LLM tracing platform, not both Datadog LLM Observability and Langfuse, unless you have a deliberate integration requirement.

---

## 16. Data quality and data statistics monitoring

## 16.1 Great Expectations

Use Great Expectations for deterministic data-quality validation.

Examples:

- Required columns exist.
- `user_id` is not null.
- Session state values are valid.
- Token counts are non-negative.
- Plan limits are within allowed range.
- Job IDs are unique.
- S3 artifact metadata conforms to schema.
- Evaluation datasets meet expected shape.
- Feature distributions contain no impossible values.
- Data freshness meets expectation.

Great Expectations supports data-integrity and schema validation, and its core framework is available as open source. citeturn107067search3turn107067search4turn107067search11

## 16.2 Evidently

Use Evidently for statistical monitoring and model/data drift.

Monitor:

- Query length distributions.
- Token usage distribution.
- Embedding norm and dimension checks.
- Retrieval similarity-score distribution.
- Empty retrieval rate.
- Retrieval result-count distribution.
- Feature drift.
- Label drift when feedback labels exist.
- Model output performance.
- Data-quality report summaries.

Recommended use:

```text
Scheduled Python job
    -> load anonymized aggregate metrics
    -> compute Evidently report
    -> write report to S3
    -> emit summary metrics to CloudWatch
    -> alert on thresholds
```

## 16.3 Why both tools

```text
Great Expectations
    -> deterministic expectation checks

Evidently
    -> statistical drift and distribution monitoring
```

They solve different problems and work well together.

---

## 17. Recommended observability map

| Area | Primary tool | Secondary tool |
|---|---|---|
| Product usage | PostHog | CloudWatch custom metrics |
| Feature rollout | PostHog feature flags | Config/entitlement flags |
| API latency and availability | OpenTelemetry + CloudWatch | Datadog if adopted |
| Exceptions | Sentry | CloudWatch Logs |
| AWS infrastructure | CloudWatch | Datadog if adopted |
| ECS / API / worker performance | CloudWatch Container Insights | Datadog APM |
| Valkey health | CloudWatch + custom Redis metrics | Datadog Redis integration |
| DynamoDB and SQS health | CloudWatch | Datadog AWS integration |
| LLM traces and token cost | Datadog LLM Observability or Langfuse | OpenTelemetry |
| ML experiments and registry | MLflow | SageMaker Model Registry if later needed |
| Data quality | Great Expectations | CloudWatch alarms |
| Data and model drift | Evidently | MLflow evaluation artifacts |
| Load testing | k6 | CloudWatch dashboards |
| Security events | CloudTrail, WAF logs, CloudWatch | Datadog Security if adopted |

---

## 18. Monitoring metrics to implement

## 18.1 API metrics

```text
http_request_count
http_request_latency_ms
http_request_error_count
http_request_size_bytes
http_response_size_bytes
rate_limit_denied_count
authentication_failure_count
authorization_denied_count
```

## 18.2 Session metrics

```text
active_session_count
session_created_count
session_expired_count
session_terminated_count
session_limit_rejection_count
session_ttl_refresh_count
```

## 18.3 Retrieval metrics

```text
retrieval_latency_ms
retrieval_result_count
retrieval_empty_result_count
retrieval_return_tokens
retrieval_mode_count
retrieval_similarity_distribution
reranker_applied_count
reranker_fallback_count
pageindex_used_count
pageindex_fallback_count
```

## 18.4 ML and LLM metrics

```text
embedding_latency_ms
embedding_error_count
embedding_model_version_count
reranker_latency_ms
compactor_latency_ms
llm_input_tokens
llm_output_tokens
llm_cost_estimate
model_quality_score
retrieval_recall_at_k
retrieval_mrr
retrieval_ndcg
```

## 18.5 Data-quality and drift metrics

```text
data_validation_pass_rate
data_validation_failure_count
dataset_freshness_seconds
schema_change_detected_count
feature_drift_score
prediction_drift_score
embedding_norm_distribution
similarity_score_drift
empty_retrieval_rate_drift
```

## 18.6 Infrastructure metrics

```text
valkey_memory_usage
valkey_eviction_count
valkey_command_latency_ms
valkey_connected_clients
sqs_queue_depth
sqs_oldest_message_age
worker_job_duration_ms
worker_retry_count
dlq_message_count
dynamodb_throttle_count
ecs_cpu_utilization
ecs_memory_utilization
sagemaker_model_latency_ms
sagemaker_invocation_error_count
```

---

## 19. Local development setup

## 19.1 Local services

Use Docker Compose for:

```text
Valkey
PostgreSQL for Prisma development
MLflow tracking server
MinIO optional S3-compatible artifact storage
PostHog optional local deployment only if needed
```

Use mocks for:

```text
Cognito
SageMaker
SQS
DynamoDB
```

or use local AWS-compatible services only when integration fidelity is required.

## 19.2 Local commands

Recommended root scripts:

```text
yarn dev:api
yarn dev:mcp
yarn test:node
yarn lint
yarn typecheck
yarn prisma:generate
yarn prisma:migrate

uv run pytest
uv run python -m memoryrepo_ml.evaluation
uv run python -m memoryrepo_ml.data_quality
uv run mlflow ui
```

---

## 20. Minimal first setup

Start with this exact subset:

```text
Terraform
GitHub Actions
Node.js + TypeScript + ESM + Express
Valkey
DynamoDB
SQS FIFO
S3
AWS Cognito
OpenTelemetry + CloudWatch
PostHog
Sentry
Python + uv
MLflow
Great Expectations
k6
```

Add later:

```text
Prisma + PostgreSQL
SageMaker endpoint deployment
PageIndex
Reranker
Evidently
Datadog or Langfuse
TurboQuant
```

This avoids building an expensive observability and ML platform before the session-memory MVP exists.

---

## 21. Acceptance criteria

This stack setup is complete when:

1. Node.js with ESM and Express owns REST and MCP request handling.
2. Python owns ML, data quality, and worker-heavy responsibilities.
3. Valkey is the hot session and vector layer.
4. DynamoDB is the durable operational data store.
5. Prisma is restricted to future relational PostgreSQL use cases.
6. PageIndex is implemented as an asynchronous structured-retrieval layer.
7. Terraform provisions AWS resources.
8. GitHub Actions deploys `dev` and protects `main`.
9. PostHog is used for product analytics and feature rollout.
10. OpenTelemetry and CloudWatch provide baseline observability.
11. Sentry captures application errors.
12. MLflow tracks models and experiments.
13. Great Expectations validates deterministic data quality.
14. Evidently is reserved for drift and statistical monitoring.
15. Datadog or Langfuse is selected only when deeper production LLM observability is needed.
