# MemoryRepo

MemoryRepo is a low-latency, session-scoped context-memory provider for LLM applications, coding agents, and agent frameworks.

It exposes memory operations through an API and an MCP connector so tools such as VS Code agents, Cursor-style coding assistants, LangChain applications, and custom LLM workflows can store, compact, retrieve, and remove relevant context without repeatedly sending an entire conversation or workspace history to a model.

## Core problem

Agentic applications often resend large context windows on every model call. That increases token cost, latency, and prompt noise.

MemoryRepo manages a bounded working-memory layer per user session. It keeps recent and relevant context available for retrieval, returns only the highest-value items for a query, and expires inactive sessions automatically.

## Product goals

- Provide a low-latency context-memory service suitable for MCP clients and agent frameworks.
- Enforce plan-based limits for active sessions and context capacity.
- Maintain session memory for up to three hours after the most recent activity.
- Support semantic retrieval, duplication control, compaction, and explicit deletion.
- Use AWS-native infrastructure provisioned through Terraform.
- Separate latency-critical operations from asynchronous compaction and indexing workflows.
- Support hybrid retrieval using vector search, PageIndex-based structured retrieval, and optional reranking.
- Provide production-oriented CI/CD, observability, security, and MLOps design.

## Initial scope

### Included

- User entitlements driven by database-configured plans.
- One or more concurrent active memory sessions per user, based on plan limits.
- Session creation, status, expiry, disablement, and cleanup.
- Context operations:
  - `add()`
  - `get()`
  - `remove()`
  - `compact()`
- Maximum context token budget per session.
- Semantic and hybrid retrieval.
- MCP connector integration.
- AWS deployment using Terraform.
- SageMaker endpoints for embeddings, reranking, and compaction workloads.
- PageIndex for long-form or structured context retrieval.
- TurboQuant as an optional GPU inference experiment for long-context compaction workloads.

### Excluded from the first MVP

- Billing and payment processing.
- A consumer-facing web dashboard.
- Cross-user shared memory.
- Long-term personal profile memory.
- Multi-region active-active deployment.
- Fine-tuning custom foundation models.
- Automated execution of code retrieved from memory.

## Key terminology

| Term | Meaning |
|---|---|
| User | An authenticated tenant of the MemoryRepo service. |
| Plan | A database-configured entitlement tier such as Free, Go, Plus, or Premium. |
| Session | A user-scoped active working-memory container with a sliding inactivity timeout. |
| Active session | A session that has not expired, has not been disabled, and remains within entitlement limits. |
| Context item | A stored unit of text or structured metadata that can be retrieved later. |
| Context budget | The maximum token capacity permitted within a session. |
| Compaction | Reducing redundant or related context items into concise, provenance-preserving summaries. |
| Hybrid retrieval | Combining dense semantic retrieval with structured or vectorless retrieval signals. |
| PageIndex | A hierarchical, structure-aware retrieval approach used for long-form documents and larger compacted context trees. |
| MCP | Model Context Protocol, used to expose MemoryRepo as a tool provider for LLM clients and agent frameworks. |
| Hot path | Latency-sensitive request handling, such as session lookup, context addition, and retrieval. |
| Async path | Background work such as compaction, indexing, tree rebuilding, and audit persistence. |

## High-level architecture snapshot

```text
MCP Client / LangChain / Application
            |
            v
API Gateway + Cognito
            |
            v
MemoryRepo API on ECS Fargate
     |                    |
     v                    v
ElastiCache Valkey    SageMaker inference
     |                    |
     v                    v
DynamoDB / S3       Embeddings, reranking,
                    compaction, PageIndex reasoning

Background workers process compaction, document indexing,
and PageIndex tree updates through SQS FIFO queues.
```

## Architectural direction

- **Amazon ElastiCache for Valkey** is the active session-memory store because it supports low-latency reads, TTL-based expiry, atomic updates, and vector or hybrid search capabilities.
- **DynamoDB** stores durable entitlement, audit, and session metadata that does not require strict real-time expiry behavior.
- **Amazon S3** stores PageIndex artifacts, long-form context sources, evaluation data, and model artifacts.
- **Amazon SageMaker AI** hosts embedding, reranking, and optional compaction inference endpoints.
- **Amazon ECS Fargate** hosts the API, MCP service, and asynchronous workers.
- **Terraform** provisions all AWS infrastructure and environment configuration.

## Documentation map

| Document | Purpose |
|---|---|
| `docs/01_project_overview.md` | Product context, actors, scope, and success criteria. |
| `docs/02_requirements.md` | Master functional and non-functional requirements. |
| `docs/03_entitlements_and_plans.md` | Configurable plan tiers and session limits. |
| `docs/04_session_lifecycle.md` | Session state machine and expiry behavior. |
| `docs/05_memory_service.md` | `add`, `get`, `remove`, and `compact` behavior. |
| `docs/06_mcp_connector_spec.md` | MCP tools and integration contract. |
| `docs/07_data_model.md` | DynamoDB, Valkey, and S3 data design. |
| `docs/08_hld_architecture.md` | High-level AWS system design. |
| `docs/09_mermaid_architecture.md` | Architecture and workflow diagrams. |
| `docs/10_low_latency_design.md` | Latency budgets and hot-path optimization. |
| `docs/11_rag_and_retrieval.md` | Hybrid retrieval and evaluation design. |
| `docs/12_sagemaker_inference.md` | SageMaker endpoints and model-serving strategy. |
| `docs/13_background_jobs.md` | Compaction, retries, queues, and indexing. |
| `docs/14_security_and_privacy.md` | Authentication, tenant isolation, and data security. |
| `docs/15_observability.md` | Metrics, logs, tracing, alarms, and SLOs. |
| `docs/16_cicd.md` | CI/CD pipelines and deployment safety. |
| `docs/17_terraform_plan.md` | Terraform modules and infrastructure rollout. |
| `docs/18_api_contract.md` | REST API schemas and error contracts. |
| `docs/19_task_breakdown.md` | Ordered implementation tasks and acceptance criteria. |
| `docs/20_delivery_plan.md` | Milestones, MVP sequence, and release plan. |
| `docs/21_test_strategy.md` | Unit, integration, load, security, and retrieval testing. |
| `docs/22_decisions_log.md` | Architecture decision records. |

## Implementation rule

Each document should define requirements before implementation. Code, Terraform modules, deployment manifests, and tests will be added only after the relevant requirement documents are approved.

