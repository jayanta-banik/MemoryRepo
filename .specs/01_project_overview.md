# Project Overview

## 1. Project name

**MemoryRepo**

MemoryRepo is a low-latency context-memory provider for LLM applications, coding agents, MCP clients, LangChain workflows, and custom agentic systems.

The service gives each authenticated user one or more temporary memory sessions, based on their entitlement plan. Each session stores bounded context, supports semantic retrieval, and expires automatically after a configurable inactivity window.

The initial inactivity timeout is:

```text
3 hours = 10,800 seconds
```

---

## 2. Problem statement

LLM agents frequently resend large amounts of conversation history, tool output, code context, repository information, and user instructions to a model.

This creates several practical problems:

- Higher token cost.
- Longer prompt construction time.
- More model latency.
- More irrelevant context entering the prompt.
- Reduced model quality when relevant information is buried under noise.
- Repeated context transmission across agent steps.

MemoryRepo reduces this burden by storing temporary, session-scoped context outside the model prompt and returning only the most relevant context for a given query.

---

## 3. Product objective

Provide an API and MCP-compatible memory service that enables agentic applications to:

1. Create or reuse a user-scoped active memory session.
2. Add context items into that session.
3. Retrieve a small number of relevant context items for a query.
4. Compact redundant or related context.
5. Remove obsolete or user-requested context.
6. Automatically expire inactive sessions.
7. Enforce plan-specific limits for simultaneous active sessions and context capacity.

The project should be deployable on AWS, provisioned through Terraform, observable, secure, and structured for iterative implementation.

---

## 4. Primary users

### 4.1 End user

A person using an LLM-powered coding tool, assistant, IDE extension, workflow automation, or custom application.

Examples:

- A developer using a VS Code agent.
- A developer using a Cursor-style coding assistant.
- A user interacting with a LangChain application.
- A user working with an internal enterprise assistant.
- A researcher using an agent to navigate long documents or notebooks.

### 4.2 Integrating application

A client application that calls MemoryRepo through REST APIs or MCP tools.

Examples:

- VS Code extension.
- Cursor-like desktop client.
- LangChain agent.
- LangGraph workflow.
- Internal web application.
- CLI coding agent.
- Custom MCP client.

### 4.3 Platform administrator

An operator who manages plans, entitlement limits, environment configuration, monitoring, deployment, and incident response.

---

## 5. Core user experience

### 5.1 First use

When an authenticated user has no active session:

1. The client calls `create_or_get_session`.
2. MemoryRepo reads the user’s plan and entitlement configuration.
3. MemoryRepo checks the number of active sessions.
4. MemoryRepo creates a new session if the user is within plan limits.
5. The session is stored in Valkey with a sliding TTL of three hours.
6. The API returns the session identifier, token budget, and expiration metadata.

### 5.2 Existing active session

When the user already has an active session:

1. The client calls `create_or_get_session`.
2. MemoryRepo finds the existing active session.
3. MemoryRepo returns that session unless the client explicitly requests another session and the user’s plan permits it.
4. The system does not create duplicate sessions unintentionally.

### 5.3 Add context

When an agent learns something worth retaining:

1. The client submits text and optional metadata.
2. MemoryRepo validates ownership, session state, and expiration.
3. MemoryRepo checks the session token budget.
4. MemoryRepo detects near duplicates where possible.
5. MemoryRepo stores the new memory item.
6. MemoryRepo refreshes the session inactivity TTL.
7. MemoryRepo may queue compaction if the session is approaching its token budget.

### 5.4 Retrieve context

When an agent needs context for a task:

1. The client submits a query.
2. MemoryRepo performs semantic retrieval from the active session.
3. MemoryRepo optionally performs structured retrieval for long-form context.
4. MemoryRepo filters weak, superseded, expired, or duplicated results.
5. MemoryRepo returns up to the requested number of items, initially capped at three.
6. MemoryRepo refreshes session activity time.

### 5.5 Session expiry

When no valid activity occurs for three hours:

1. The Valkey TTL reaches zero.
2. The active session data expires from the hot store.
3. The session is no longer retrievable.
4. A later request creates a new session if entitlement limits permit.
5. Durable audit metadata may remain in DynamoDB according to retention policy.

---

## 6. Core value proposition

MemoryRepo should help agent clients reduce unnecessary prompt repetition while keeping useful context available at low latency.

The intended benefits are:

- Lower token usage.
- Faster prompt assembly.
- More focused context windows.
- Lower cost for long-running agent workflows.
- Better separation between ephemeral working memory and durable user data.
- Reusable memory tools across multiple LLM clients.

---

## 7. Product scope

## 7.1 In scope

### Session management

- Create or retrieve a session.
- Enforce maximum active sessions per user.
- Support configurable inactivity TTL.
- Support explicit session disablement.
- Support session status lookup.
- Support plan-based session capacity.

### Context memory

- Add context items.
- Retrieve relevant context.
- Remove context items.
- Compact related context.
- Track token usage.
- Enforce context token budget.
- Preserve source provenance for compacted memories.
- Perform duplicate or near-duplicate detection.

### Entitlements

- Read plan definitions from a database.
- Assign users to plans.
- Support configurable limits without redeploying application code.
- Support tier changes.
- Support feature flags by plan.

### Retrieval

- Dense semantic retrieval.
- Metadata filtering.
- Threshold-based filtering.
- Top-k retrieval.
- Optional reranking.
- Optional PageIndex-based structured retrieval for large or long-form context.

### Infrastructure

- AWS-only deployment architecture.
- Terraform-managed infrastructure.
- ECS-hosted API and worker services.
- ElastiCache for Valkey for active memory.
- DynamoDB for durable metadata.
- S3 for document and index artifacts.
- SageMaker endpoints for ML inference.
- CI/CD using AWS CodePipeline and CodeBuild.

### MCP integration

- MCP tool definitions.
- Session discovery.
- Context add and retrieval tools.
- Authentication and tenant isolation.
- Low-latency design suitable for agent workflows.

---

## 7.2 Out of scope for MVP

- Billing provider integration.
- Credit card processing.
- Customer support portal.
- User-facing dashboard.
- Cross-user shared sessions.
- Permanent personal memory across all sessions.
- Fine-tuning foundation models.
- Multi-region failover.
- Offline analytics warehouse.
- Full document collaboration features.
- Running arbitrary customer code.
- Automatic execution of retrieved instructions.

---

## 8. Product principles

### 8.1 Session memory is temporary

MemoryRepo is initially a working-memory service, not a permanent personal knowledge store.

### 8.2 The hot path must remain small

Session lookup, add, and retrieve operations should avoid unnecessary synchronous dependencies.

The hot path should not synchronously wait for:

- Compaction.
- PageIndex tree rebuilding.
- Long document indexing.
- Model retraining.
- Audit aggregation.
- Analytics exports.

### 8.3 Entitlements are data-driven

Plan limits must come from persistent configuration, not hardcoded application constants.

### 8.4 Tenant isolation is mandatory

A user must only access sessions and context that belong to that user.

### 8.5 Compaction must preserve provenance

Summarized memory should retain references to the original memory identifiers used to produce it.

### 8.6 Retrieval must be explainable enough to debug

The service should store or emit retrieval signals such as similarity score, recency signal, source type, and whether a result came from vector or structured retrieval.

---

## 9. Initial business rules

| Rule | Initial value |
|---|---:|
| Default inactivity timeout | 3 hours |
| Default free-tier active sessions | 1 |
| Premium-tier active sessions | 3 |
| Default session context budget | 10,000 tokens |
| Initial maximum retrieval count | 3 context items |
| Session activity refresh | On successful add, get, remove, compact, or status access |
| Session expiry behavior | Expire from hot store after inactivity TTL |
| Plan configuration source | Database |
| Active-session enforcement source of truth | Durable metadata plus atomic hot-store check |

The exact tier names, limits, rates, and features will be defined in `docs/03_entitlements_and_plans.md`.

---

## 10. Initial quality targets

These are directional targets for the first production-oriented design. They will be refined in the low-latency requirements document.

| Operation | Target |
|---|---:|
| Session lookup, p95 | Under 50 ms excluding network edge latency |
| Add context, p95 | Under 250 ms when embedding is cached or lightweight |
| Retrieve context, p95 | Under 300 ms for vector-only retrieval |
| Retrieve context, p95 | Under 800 ms when reranking is enabled |
| Compaction | Asynchronous, not on user request path |
| Session-expiry correctness | No active hot-store access after TTL expiration |
| Availability objective | 99.9% for API service in production target design |

---

## 11. Success criteria

The MVP is successful when all of the following are demonstrated:

1. A user on the Free plan can create one active session.
2. A user on a higher plan can create multiple concurrent sessions based on configured limits.
3. An inactive session expires after the configured TTL.
4. `add`, `get`, `remove`, and `compact` operate on user-owned active sessions only.
5. The API can retrieve relevant context from a session using semantic similarity.
6. The API returns no more than the configured top-k results.
7. Session token budgets are enforced.
8. Compaction runs asynchronously and preserves original-memory references.
9. An MCP client can use the service through documented tools.
10. Infrastructure can be created from Terraform.
11. CI/CD can deploy a tested API revision.
12. Monitoring can show latency, error rate, session counts, retrieval quality signals, and compaction behavior.

---

## 12. Dependencies

The project will depend on the following logical components:

- Authentication and identity provider.
- User and plan database.
- Session-state store.
- Semantic embedding service.
- Vector retrieval capability.
- Structured retrieval capability for longer context.
- Background task queue.
- API service.
- MCP adapter.
- Infrastructure-as-code.
- CI/CD pipeline.
- Monitoring and alerting.

Detailed service ownership and AWS mapping will be defined in the architecture documents.

---

## 13. Open design questions

These questions will be resolved in later documents:

1. Should a user be allowed to explicitly choose a session, or should the client default to one current session?
2. What should happen when a user downgrades to a plan with fewer allowed active sessions?
3. Should token budgets vary by tier?
4. Should embeddings be generated synchronously for every context item?
5. Which metadata fields should be filterable during retrieval?
6. When should compaction trigger?
7. Should retrieval use a reranker for every request or only for high-value plans?
8. Which MCP transport mode should be prioritized first?
9. How much long-form source content should be retained in S3 after session expiry?
10. Should session-level audit records be retained for operational analysis?

These will be converted into explicit requirements or documented decisions before implementation begins.
