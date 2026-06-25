# Architecture Decisions Log

## 1. Purpose

This document records the major technical and product decisions for MemoryRepo.

The goal is to preserve the reasoning behind important choices so future implementation work does not accidentally reverse a deliberate decision or introduce incompatible architecture.

Each decision includes:

- Context.
- Decision.
- Rationale.
- Consequences.
- Revisit trigger.

Status values:

```text
accepted
provisional
deferred
superseded
```

---

## 2. Decision summary

| ID | Decision | Status |
|---|---|---|
| ADR-001 | Use Valkey for active session memory. | accepted |
| ADR-002 | Use DynamoDB for durable operational metadata. | accepted |
| ADR-003 | Use three-hour sliding session TTL. | accepted |
| ADR-004 | Make plans and entitlements database-driven. | accepted |
| ADR-005 | Enforce active-session limits atomically in Valkey. | accepted |
| ADR-006 | Use vector-only retrieval as initial MVP baseline. | accepted |
| ADR-007 | Use PageIndex only for structured long-form context. | accepted |
| ADR-008 | Keep compaction asynchronous. | accepted |
| ADR-009 | Use SageMaker for inference workloads only. | accepted |
| ADR-010 | Treat TurboQuant as experimental long-context optimization. | accepted |
| ADR-011 | Use REST as core service contract and MCP as connector layer. | accepted |
| ADR-012 | Use GitHub Actions with `dev` and `main` branch flow. | accepted |
| ADR-013 | Use Terraform as AWS infrastructure source of truth. | accepted |
| ADR-014 | Use GitHub OIDC for AWS deployment credentials. | accepted |
| ADR-015 | Use strict ownership filtering on every retrieval operation. | accepted |
| ADR-016 | Keep raw user context out of normal logs. | accepted |
| ADR-017 | Use SQS FIFO for session-sensitive background jobs. | accepted |
| ADR-018 | Use session-bound embedding model versions. | provisional |
| ADR-019 | Use normal merge commits from `dev` into `main`. | accepted |
| ADR-020 | Defer billing, long-term memory, and admin UI from MVP. | accepted |

---

# ADR-001: Use Valkey for active session memory

## Status

```text
accepted
```

## Context

MemoryRepo requires low-latency session-scoped context storage with:

- Sliding TTL.
- Fast reads and writes.
- Session-local vector search.
- Atomic counter updates.
- Active-session tracking.
- Locking for background jobs.

## Decision

Use Amazon ElastiCache for Valkey as the primary active-session memory store.

## Rationale

Valkey supports the operations needed for the hot path:

- Low-latency key-value access.
- TTL expiration.
- Hashes, sorted sets, and indexes.
- Atomic Lua scripts.
- Session-local metadata.
- Cache-friendly entitlement lookups.
- Vector-search capabilities where configured.

## Consequences

Positive:

- Low latency for session and memory operations.
- Natural three-hour inactivity expiration.
- Efficient atomic session-limit and token-budget enforcement.
- Suitable location for active vector index.

Tradeoffs:

- Valkey data is ephemeral.
- Capacity must be monitored carefully.
- Eviction is dangerous for active session correctness.
- Durable audit and lifecycle information must live elsewhere.

## Revisit trigger

Revisit only if:

- Session state requires strong durable transactional semantics beyond current design.
- Vector-search support becomes insufficient.
- Active context size exceeds feasible Valkey cost or memory model.
- A different managed low-latency store materially improves requirements.

---

# ADR-002: Use DynamoDB for durable operational metadata

## Status

```text
accepted
```

## Context

MemoryRepo needs durable records for plans, entitlements, sessions, jobs, idempotency, audit events, and lifecycle evidence.

## Decision

Use DynamoDB for durable operational metadata.

## Rationale

DynamoDB fits the current access patterns:

- User entitlement lookup.
- Session lookup by user and state.
- Job lifecycle tracking.
- Audit-event writes.
- Idempotency record storage.
- Serverless operational scaling.

It also avoids introducing a relational database before the product requires relational transactions or advanced reporting.

## Consequences

Positive:

- Managed durability and scale.
- Clear separation from ephemeral session data.
- Simple Terraform provisioning.
- Flexible schema evolution.

Tradeoffs:

- Complex joins are unavailable.
- Access patterns must be designed explicitly.
- Reporting may later require export or analytics pipeline.

## Revisit trigger

Revisit if:

- Billing, invoicing, or relational account management becomes a core feature.
- Admin workflows require complex relational querying.
- Reporting needs cannot be handled by exports, streams, or analytics storage.

---

# ADR-003: Use three-hour sliding session TTL

## Status

```text
accepted
```

## Context

MemoryRepo is designed for active coding-agent or task-agent sessions, not permanent personal memory.

## Decision

Active sessions expire after three hours of inactivity.

Successful session status, add, get, remove, and compact-queue operations refresh the inactivity timer.

## Rationale

Three hours is long enough for an active engineering or research workflow while preventing temporary context from becoming indefinite storage.

## Consequences

Positive:

- Clear session boundary.
- Reduced storage growth.
- Reduced privacy retention risk.
- Natural cleanup behavior.

Tradeoffs:

- Users may lose active memory after long inactivity.
- Clients should resolve or create sessions explicitly.
- Long-running workflows may require periodic valid activity.

## Revisit trigger

Revisit after usage telemetry shows:

- Frequent unwanted expiration during normal workflows.
- Sessions are routinely much shorter.
- Enterprise plans require configurable inactivity policies.

---

# ADR-004: Make plans and entitlements database-driven

## Status

```text
accepted
```

## Context

MemoryRepo needs Free, Go, Plus, and Premium plans with different session, token, retrieval, and feature limits.

Hardcoded plan values would require code deployment for normal business changes.

## Decision

Store plan definitions, feature flags, overrides, and entitlement assignments in durable data tables.

## Rationale

This supports:

- Controlled plan changes.
- User-specific overrides.
- Suspension.
- Feature gating.
- Versioning.
- Future billing integration.

## Consequences

Positive:

- Limits are configurable.
- Free and premium behavior can evolve without code rewrite.
- Product policy is separated from service logic.

Tradeoffs:

- Entitlement resolution adds a hot-path dependency.
- Cache invalidation becomes important.
- Plan changes need auditability.

## Revisit trigger

Revisit if a dedicated entitlement platform is adopted later.

---

# ADR-005: Enforce active-session limits atomically in Valkey

## Status

```text
accepted
```

## Context

Concurrent requests can create multiple sessions for a user at the same time.

A simple read-count-then-create sequence can violate Free or Premium session limits.

## Decision

Use Valkey Lua scripts or equivalent atomic operations to:

1. Check entitlement limit.
2. Reuse active session when appropriate.
3. Reserve active-session count.
4. Create session metadata.
5. Update active-session index.
6. Apply TTL.

## Rationale

This keeps the critical concurrency boundary close to the active state source.

## Consequences

Positive:

- Prevents session-limit races.
- Avoids distributed lock complexity for normal session creation.
- Supports predictable behavior under concurrent clients.

Tradeoffs:

- Lua script logic must be carefully tested.
- Script versioning is required.
- Script errors can affect critical paths.

## Revisit trigger

Revisit only if session lifecycle is moved away from Valkey.

---

# ADR-006: Use vector-only retrieval as initial MVP baseline

## Status

```text
accepted
```

## Context

MemoryRepo aims to provide semantic retrieval, but hybrid retrieval adds complexity through lexical search, PageIndex, reranking, score fusion, and artifact management.

## Decision

Deliver vector-only retrieval first.

## Rationale

Vector-only retrieval is sufficient to validate core value:

- Session context can be added.
- Relevant context can be retrieved.
- Top-k and token caps can be enforced.
- Latency and quality baselines can be measured.

## Consequences

Positive:

- Faster MVP.
- Smaller operational surface.
- Clear baseline for quality evaluation.
- Easier debugging.

Tradeoffs:

- Exact code identifiers may initially retrieve less reliably.
- Long-form structured documents may not perform optimally.
- Some ambiguous queries may benefit from later reranking.

## Revisit trigger

Advance to hybrid retrieval when:

- Vector-only quality metrics identify systematic failures.
- Coding-agent identifier queries need lexical support.
- Long-form context becomes a major product workload.

---

# ADR-007: Use PageIndex only for structured long-form context

## Status

```text
accepted
```

## Context

PageIndex can add hierarchical or structured retrieval over large content collections.

Using it for every short memory item would add latency and build cost without clear value.

## Decision

Use PageIndex only for long-form or aggregated context artifacts.

Examples:

- Long transcripts.
- Document bundles.
- Codebase summaries.
- Large task histories.
- Compacted memory trees.

## Rationale

Short context notes are adequately handled by vector search. Structured indexing should be reserved for content where hierarchy materially improves retrieval.

## Consequences

Positive:

- Avoids unnecessary hot-path complexity.
- Keeps normal retrieval fast.
- Makes PageIndex build an asynchronous artifact workflow.

Tradeoffs:

- Some sessions will have vector-only behavior even after PageIndex exists.
- Artifact freshness and lifecycle must be managed.
- Hybrid ranking requires more evaluation.

## Revisit trigger

Revisit if product usage shows short-item hierarchy provides measurable value.

---

# ADR-008: Keep compaction asynchronous

## Status

```text
accepted
```

## Context

Compaction can involve clustering, long-context summarization, model calls, source validation, and index updates.

## Decision

Queue compaction through SQS and process it in ECS workers.

The API returns `202 Accepted` for compaction requests.

## Rationale

Compaction is expensive and not required to complete before ordinary memory retrieval can continue.

## Consequences

Positive:

- API and MCP latency remain predictable.
- Retry and DLQ policies can be applied.
- Worker capacity scales independently.
- Compaction can use slower or GPU-backed models.

Tradeoffs:

- Compaction is eventually consistent.
- Users may temporarily see pre-compaction memory.
- Job status tracking is required.

## Revisit trigger

Do not move compaction to the hot path unless a narrowly scoped lightweight deterministic compaction operation proves necessary.

---

# ADR-009: Use SageMaker for inference workloads only

## Status

```text
accepted
```

## Context

MemoryRepo uses models for embeddings, reranking, compaction, and optional structured reasoning.

## Decision

Use SageMaker AI for model-serving workloads only.

Do not use SageMaker as session storage, vector index, entitlement store, or job coordinator.

## Rationale

SageMaker is appropriate for managed inference endpoints and model lifecycle, while Valkey, DynamoDB, SQS, and S3 are better fits for service state and artifacts.

## Consequences

Positive:

- Clear architectural boundaries.
- Independent scaling of model workloads.
- Model versioning and rollout can be separated from API deployment.

Tradeoffs:

- More infrastructure components.
- Endpoint latency must be monitored.
- Cost controls are necessary.

## Revisit trigger

Revisit endpoint hosting only if another AWS-native runtime materially improves latency, cost, or operational simplicity.

---

# ADR-010: Treat TurboQuant as experimental long-context optimization

## Status

```text
accepted
```

## Context

TurboQuant may reduce GPU KV-cache memory use or improve long-context inference efficiency.

## Decision

TurboQuant is an optional experiment inside a custom GPU inference container for compaction or PageIndex-associated long-context reasoning.

It is not part of core session storage or retrieval correctness.

## Rationale

The product can deliver core value without TurboQuant. Introducing it early would create unnecessary model-runtime risk.

## Consequences

Positive:

- Core architecture remains simple.
- Experiment can be benchmarked independently.
- No user-facing correctness dependency.

Tradeoffs:

- Long-context model cost may remain higher before optimization.
- Experimental evaluation work is deferred.

## Revisit trigger

Revisit when:

- Long-context compaction workload is real.
- GPU memory or throughput becomes material cost driver.
- Benchmark shows quality-preserving benefit.

---

# ADR-011: Use REST as core service contract and MCP as connector layer

## Status

```text
accepted
```

## Context

MemoryRepo must support MCP clients, IDE clients, agents, and direct application integration.

## Decision

Implement business operations behind a versioned REST API. MCP tools map to those operations.

## Rationale

REST provides:

- Stable service contract.
- Easier direct integration.
- Clear authentication and observability boundary.
- Testable OpenAPI contract.

MCP provides:

- Agent-native tool access.
- IDE and coding-assistant interoperability.
- Structured tool schemas.

## Consequences

Positive:

- One shared business layer.
- MCP transport remains replaceable.
- REST contract can support future clients.

Tradeoffs:

- Two interface layers must be tested.
- Error mapping must remain consistent.

## Revisit trigger

Revisit only if product becomes MCP-only and direct API support is intentionally removed.

---

# ADR-012: Use GitHub Actions with `dev` and `main` branch flow

## Status

```text
accepted
```

## Context

The project needs simple continuous integration and controlled deployments.

## Decision

Use GitHub Actions.

Branch flow:

```text
feature branch
    -> squash merge into dev
    -> dev auto-builds and deploys development
    -> release PR merges dev into main
    -> main starts production release workflow
```

## Rationale

This matches the desired shared-history model while keeping feature work clean.

## Consequences

Positive:

- Predictable developer workflow.
- Continuous development deployment.
- Clear production release boundary.
- Easier rollback and audit.

Tradeoffs:

- Requires protected branches.
- Requires discipline around release PRs.
- Dev may temporarily contain incomplete but merged features unless feature flags are used.

## Revisit trigger

Revisit only if team size or release cadence requires release branches or trunk-based development.

---

# ADR-013: Use Terraform as AWS infrastructure source of truth

## Status

```text
accepted
```

## Context

MemoryRepo uses multiple AWS services that must remain reproducible across environments.

## Decision

Use Terraform for AWS infrastructure provisioning and configuration.

## Rationale

Terraform supports:

- Reusable modules.
- Environment separation.
- Reviewable plans.
- GitHub Actions integration.
- Controlled infrastructure changes.

## Consequences

Positive:

- Infrastructure is versioned.
- Dev, stage, and prod can share modules.
- Drift can be detected.

Tradeoffs:

- Terraform state must be protected.
- Module design requires upfront discipline.
- Some AWS service features may need careful provider compatibility testing.

## Revisit trigger

Revisit only if organization mandates another infrastructure-as-code system.

---

# ADR-014: Use GitHub OIDC for AWS deployment credentials

## Status

```text
accepted
```

## Context

CI/CD requires AWS credentials.

Long-lived access keys in GitHub Secrets increase security risk.

## Decision

Use GitHub Actions OpenID Connect federation to assume short-lived AWS IAM roles.

## Rationale

OIDC reduces long-lived credential exposure and enables branch- and environment-bound trust policies.

## Consequences

Positive:

- No long-lived AWS access keys in GitHub.
- Better auditability.
- Separate dev and production deployment roles.

Tradeoffs:

- IAM trust configuration is more complex.
- Workflow identity conditions must be carefully tested.

## Revisit trigger

Revisit only if GitHub Actions is replaced.

---

# ADR-015: Enforce strict ownership filtering on every retrieval operation

## Status

```text
accepted
```

## Context

Vector similarity search can accidentally surface unrelated records if metadata filtering is weak.

## Decision

Every retrieval operation must require:

```text
owner_user_id = authenticated user
session_id = requested session
state = active
```

before score ranking.

## Rationale

Tenant isolation is more important than retrieval recall.

## Consequences

Positive:

- Strong protection against cross-user leakage.
- Security rules are explicit.
- Retrieval tests have clear required behavior.

Tradeoffs:

- Index schema must support filters efficiently.
- Incorrect filter implementation is a critical defect.

## Revisit trigger

Never relax this rule without replacing it with equally strong authorization boundaries.

---

# ADR-016: Keep raw user context out of normal logs

## Status

```text
accepted
```

## Context

MemoryRepo context may contain sensitive prompts, code, tool output, or document excerpts.

## Decision

Default logs include metadata, hashes, timings, status, model versions, and correlation IDs, but not raw memory content, embeddings, tokens, or secrets.

## Rationale

This minimizes privacy risk and reduces sensitive operational-data exposure.

## Consequences

Positive:

- Lower logging privacy risk.
- Safer incident-response workflows.
- Reduced accidental data leakage.

Tradeoffs:

- Debugging content-specific issues may require controlled diagnostic flows.
- Retrieval evaluation must use safe fixtures.

## Revisit trigger

Revisit only to define tightly controlled forensic logging procedures, not to enable broad raw-content logging.

---

# ADR-017: Use SQS FIFO for session-sensitive background jobs

## Status

```text
accepted
```

## Context

Compaction and PageIndex rebuilds can conflict if multiple jobs modify the same session out of order.

## Decision

Use SQS FIFO queues with session ID as `MessageGroupId` for session-scoped jobs.

## Rationale

FIFO ordering reduces out-of-order mutation risk while still allowing parallel work across sessions.

## Consequences

Positive:

- Session job ordering.
- Simpler worker coordination.
- Better duplicate suppression with deterministic deduplication IDs.

Tradeoffs:

- Throughput is constrained per message group.
- Worker code still requires idempotency and locks.
- Queue configuration is more specific than standard SQS.

## Revisit trigger

Revisit if workload throughput requirements exceed FIFO constraints and a stronger versioned concurrency model is implemented.

---

# ADR-018: Use session-bound embedding model versions

## Status

```text
provisional
```

## Context

Changing embedding models can create incompatible vector spaces inside active sessions.

## Decision

Assign an embedding model version when a session is created. New sessions use the latest approved model. Existing active sessions retain their assigned model until expiry.

## Rationale

This prevents mixed embedding spaces inside one session without requiring immediate reindexing.

## Consequences

Positive:

- Consistent similarity behavior per active session.
- Simpler model rollout.
- No forced live-session re-embedding.

Tradeoffs:

- Multiple embedding endpoints or versions may coexist temporarily.
- Migration complexity rises if sessions become long-lived.
- Cross-session comparisons are not directly comparable.

## Revisit trigger

Revisit after model rollout experience or when long-lived persistent memory is introduced.

---

# ADR-019: Use normal merge commits from `dev` into `main`

## Status

```text
accepted
```

## Context

Feature branches should be cleanly consolidated, but production releases should preserve visibility of the shared `dev` history.

## Decision

Use:

```text
squash merge: feature branch -> dev
normal merge commit: dev -> main
```

## Rationale

Squash merge keeps feature changes concise. A normal merge commit preserves release boundaries and branch relationship between `dev` and `main`.

## Consequences

Positive:

- Clear history.
- Easier release rollback.
- Explicit production promotion point.

Tradeoffs:

- Main history includes merge commits.
- Release PR discipline is required.

## Revisit trigger

Revisit only if team workflow moves to release branches or trunk-based deployment.

---

# ADR-020: Defer billing, long-term memory, and admin UI from MVP

## Status

```text
accepted
```

## Context

MemoryRepo has a wide potential scope. Attempting to build billing, subscription checkout, persistent user memory, and full admin dashboards before core retrieval works would delay validation.

## Decision

Defer the following from MVP:

- Payment collection.
- Billing provider integration.
- Long-term permanent memory.
- Full administrative UI.
- Multi-region deployment.
- Consumer workspace management.
- Full analytics warehouse.

## Rationale

The highest-value initial proof is low-latency session memory with plan enforcement and MCP integration.

## Consequences

Positive:

- Faster MVP.
- Lower operational complexity.
- Clear product validation path.

Tradeoffs:

- Plans are initially seeded or administratively managed.
- Some commercial workflows remain manual.
- Long-term memory requires future architecture decisions.

## Revisit trigger

Revisit after MVP usage validates demand and operational baseline.

---

## 3. Deferred decisions

The following areas require future explicit decisions.

| Topic | Why deferred |
|---|---|
| Billing provider | No payment workflow required for MVP. |
| Long-term memory product | Current design is intentionally session-scoped. |
| Region strategy | MVP can operate in one region. |
| Multi-account AWS organization layout | Depends on deployment maturity. |
| Exact embedding model | Requires benchmark evidence. |
| Exact reranker model | Requires retrieval evaluation. |
| Exact compaction model | Requires factual-retention evaluation. |
| Valkey cluster sizing | Requires load profile. |
| API custom domain | Depends on final product branding and auth flow. |
| Admin portal | Not required to prove core service. |
| Organization or team tenancy | Current design is single-user scoped. |
| Usage-based billing metric | Depends on commercial model. |
| Customer-managed encryption keys | Enterprise requirement, not MVP. |
| Data residency controls | Depends on target market. |
| Persistent document ingestion | Separate product expansion. |

---

## 4. Decision process

A new architecture decision should be created when a change:

- Alters a core storage boundary.
- Changes tenant isolation model.
- Changes session lifetime semantics.
- Adds a new external system.
- Changes deployment or branch strategy.
- Introduces a model-runtime dependency.
- Changes privacy or retention behavior.
- Affects cost materially.
- Requires irreversible data migration.
- Alters API or MCP compatibility.

Each new ADR should include:

```text
ID
Title
Status
Context
Decision
Rationale
Consequences
Alternatives considered
Revisit trigger
Owner
Date
```

---

## 5. Acceptance criteria

This log is complete when:

1. Core architecture choices are documented.
2. Each decision includes rationale and consequences.
3. Deferred product and technical choices are visible.
4. Future contributors can identify which decisions are fixed, provisional, or intentionally deferred.
5. New major changes use the same ADR format.
