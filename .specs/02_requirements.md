# Master Requirements

## 1. Purpose

This document defines the master functional and non-functional requirements for MemoryRepo.

It is the baseline requirement document. Later documents may add implementation detail, schemas, flows, thresholds, and acceptance criteria, but they must not contradict this document without a recorded architecture decision.

---

## 2. Requirement terminology

| Term | Meaning |
|---|---|
| Must | Mandatory for the target release or MVP unless explicitly marked as deferred. |
| Should | Strongly recommended. A deviation requires a documented rationale. |
| May | Optional enhancement. |
| Active session | A session that is valid, enabled, not expired, and within user entitlement limits. |
| Hot path | A synchronous request path that directly affects client latency. |
| Async path | Background processing that must not block a successful client request. |
| Tenant | An authenticated user or organization boundary that owns data. |

---

## 3. Functional requirements

# 3.1 Identity and authentication

### FR-AUTH-001
The system must authenticate API and MCP requests before allowing session or memory operations.

### FR-AUTH-002
The system must derive the authenticated user identity from the verified authentication token or trusted identity context.

### FR-AUTH-003
The system must not trust a user identifier supplied only in a request body, query parameter, or path parameter for authorization purposes.

### FR-AUTH-004
The system must reject requests with invalid, expired, malformed, or unauthorized credentials.

### FR-AUTH-005
The system must support machine-to-machine or MCP-compatible authentication in addition to human interactive authentication.

### FR-AUTH-006
The system must attach the authenticated user identity to every request context, audit event, and session access decision.

---

# 3.2 User profile and entitlement requirements

### FR-ENT-001
The system must maintain a durable user profile record.

### FR-ENT-002
The system must associate each user with a plan or entitlement tier.

### FR-ENT-003
The system must retrieve plan limits from a database or durable configuration source.

### FR-ENT-004
The system must not hardcode plan-specific values such as maximum active sessions, token budgets, rate limits, or feature access into business logic.

### FR-ENT-005
The system must support at least the following initial plan labels:

- Free
- Go
- Plus
- Premium

### FR-ENT-006
The system must allow plan definitions to be changed without redeploying the API service.

### FR-ENT-007
The system must support different maximum active-session limits by plan.

### FR-ENT-008
The system must support different per-session context token budgets by plan.

### FR-ENT-009
The system must support plan-specific feature flags.

### FR-ENT-010
The system must support a default Free plan for users without an explicit paid-tier assignment.

### FR-ENT-011
The system must enforce entitlement limits before creating a new active session.

### FR-ENT-012
The system must return a clear entitlement error when a request exceeds a plan limit.

### FR-ENT-013
The system must record the plan configuration version or effective entitlement snapshot used when a session is created.

---

# 3.3 Session management requirements

### FR-SES-001
The system must create a session for an authenticated user when the user has no active session and is within entitlement limits.

### FR-SES-002
The system must support a `create_or_get_session` operation.

### FR-SES-003
The system must return an existing eligible active session when the caller requests reuse behavior.

### FR-SES-004
The system must support explicit creation of an additional session when the user’s plan permits more than one concurrent active session.

### FR-SES-005
The system must enforce a configurable inactivity timeout for each active session.

### FR-SES-006
The initial default inactivity timeout must be three hours.

### FR-SES-007
The system must implement a sliding inactivity timeout.

### FR-SES-008
The system must refresh session activity after successful authorized session operations.

### FR-SES-009
The operations that refresh session activity must include:

- Session status lookup
- Add context
- Get context
- Remove context
- Compact context

### FR-SES-010
The system must reject context operations on expired sessions.

### FR-SES-011
The system must reject context operations on disabled sessions.

### FR-SES-012
The system must support explicit session disablement.

### FR-SES-013
The system must support explicit session deletion or termination.

### FR-SES-014
The system must expose session status including at least:

- Session ID
- Session state
- Created time
- Last activity time
- Expiration time or remaining TTL
- Context token usage
- Context token budget
- Memory item count
- Effective plan identifier

### FR-SES-015
The system must enforce user ownership for every session operation.

### FR-SES-016
The system must prevent accidental duplicate session creation from retried client requests.

### FR-SES-017
The system must support idempotency for session creation requests.

### FR-SES-018
The system must keep active-session enforcement consistent under concurrent create-session requests.

### FR-SES-019
The system must record a durable session metadata record for audit and operational purposes.

### FR-SES-020
The system must distinguish between session expiration, explicit disablement, explicit deletion, and entitlement-based deactivation.

---

# 3.4 Context memory requirements

### FR-MEM-001
The system must support adding a context item to an active session.

### FR-MEM-002
The system must require a valid session identifier for session-scoped context operations.

### FR-MEM-003
The system must verify session ownership before adding context.

### FR-MEM-004
The system must accept text content as the primary context payload.

### FR-MEM-005
The system must allow optional context metadata.

### FR-MEM-006
The system must support optional context classifications such as:

- Preference
- Instruction
- Task state
- Tool output
- Code context
- Document excerpt
- Conversation summary
- System-generated compaction

### FR-MEM-007
The system must calculate or receive a token count for each stored context item.

### FR-MEM-008
The system must enforce a maximum token budget per session.

### FR-MEM-009
The system must reject, compact, truncate, or otherwise handle an add request that would exceed the session token budget according to configured policy.

### FR-MEM-010
The system must return the action taken when an add request exceeds the budget.

### FR-MEM-011
The system must support context removal by memory item identifier.

### FR-MEM-012
The system must support removal of context only by the owning user or an authorized service identity.

### FR-MEM-013
The system must mark or remove superseded memory so it is not returned by normal retrieval.

### FR-MEM-014
The system must support context compaction.

### FR-MEM-015
The system must preserve source-memory references when compacting multiple memory items into a summary item.

### FR-MEM-016
The system must support idempotency for context-add requests.

### FR-MEM-017
The system must maintain memory-item creation timestamps.

### FR-MEM-018
The system must maintain memory-item update or supersession timestamps when applicable.

### FR-MEM-019
The system must support optional importance or priority metadata.

### FR-MEM-020
The system must support optional recency-aware retrieval behavior.

---

# 3.5 Duplicate detection and compaction requirements

### FR-CMP-001
The system must detect exact duplicate context items where practical.

### FR-CMP-002
The system should detect near-duplicate or semantically overlapping context items.

### FR-CMP-003
The system must avoid storing repeated identical content when idempotency or duplicate detection identifies an equivalent item.

### FR-CMP-004
The system must support asynchronous compaction.

### FR-CMP-005
The system must not require a client request to wait for long-running compaction to complete.

### FR-CMP-006
The system must preserve provenance from compacted summaries to original memory items.

### FR-CMP-007
The system must not silently delete source information without preserving a deletion or supersession trace.

### FR-CMP-008
The system must support compaction triggers based on configurable conditions.

### FR-CMP-009
The initial compaction trigger should include token-budget pressure.

### FR-CMP-010
The system must avoid compacting contradictory memories into a misleading single statement.

### FR-CMP-011
The system should preserve conflicting context as distinct facts, with timestamps or source references where possible.

### FR-CMP-012
The system must record compaction job status and failures.

### FR-CMP-013
The system must support retryable compaction jobs.

### FR-CMP-014
The system must prevent duplicate concurrent compaction jobs for the same session where possible.

---

# 3.6 Retrieval requirements

### FR-RET-001
The system must retrieve context items from a specific active session.

### FR-RET-002
The system must verify session ownership before retrieval.

### FR-RET-003
The system must support semantic similarity retrieval.

### FR-RET-004
The system must support configurable top-k retrieval.

### FR-RET-005
The initial default retrieval maximum must be three returned context items.

### FR-RET-006
The system must support a minimum similarity threshold.

### FR-RET-007
The system must exclude expired, disabled, deleted, and superseded context items from normal retrieval.

### FR-RET-008
The system must support metadata filters when configured.

### FR-RET-009
The system should support recency and importance signals during ranking.

### FR-RET-010
The system should support optional reranking after initial candidate retrieval.

### FR-RET-011
The system should support hybrid retrieval using dense vector retrieval and structured or vectorless retrieval signals.

### FR-RET-012
The system should support PageIndex-based retrieval for long-form source content, compacted context trees, or session documents.

### FR-RET-013
The system must identify whether each retrieval result originated from dense, structured, hybrid, or reranked retrieval.

### FR-RET-014
The system must return retrieval metadata sufficient for client debugging when debug mode is authorized.

### FR-RET-015
The system must refresh session activity after successful retrieval.

---

# 3.7 MCP connector requirements

### FR-MCP-001
The system must expose a Model Context Protocol compatible interface.

### FR-MCP-002
The MCP interface must support session discovery or session creation.

### FR-MCP-003
The MCP interface must support adding context.

### FR-MCP-004
The MCP interface must support retrieving context.

### FR-MCP-005
The MCP interface must support removing context.

### FR-MCP-006
The MCP interface must support requesting compaction.

### FR-MCP-007
The MCP interface must enforce the same user ownership and entitlement checks as the REST API.

### FR-MCP-008
The MCP interface must return stable machine-readable result schemas.

### FR-MCP-009
The MCP interface must return actionable machine-readable errors.

### FR-MCP-010
The MCP interface must avoid returning unnecessary internal infrastructure details.

### FR-MCP-011
The MCP interface should support agent clients that need lightweight, repeated retrieval calls.

---

# 3.8 API requirements

### FR-API-001
The system must expose REST endpoints for core session and context operations.

### FR-API-002
The system must use versioned API paths.

### FR-API-003
The system must use JSON request and response bodies for standard operations.

### FR-API-004
The system must provide a consistent error response schema.

### FR-API-005
The system must return a correlation or request identifier with API responses.

### FR-API-006
The system must support idempotency keys for create-session and add-context operations.

### FR-API-007
The system must reject malformed payloads with clear validation errors.

### FR-API-008
The system must document request limits and payload size limits.

### FR-API-009
The system must return session expiration or state errors distinctly from authorization errors.

---

# 3.9 Data storage requirements

### FR-DATA-001
The system must use a low-latency hot store for active session context.

### FR-DATA-002
The hot store must support TTL-based session expiry.

### FR-DATA-003
The hot store must support atomic operations needed for token-budget enforcement and session activity refresh.

### FR-DATA-004
The system must use durable storage for user profiles, plans, entitlement configuration, and session audit metadata.

### FR-DATA-005
The system must use durable object storage for long-form source artifacts, PageIndex artifacts, or model-related artifacts when needed.

### FR-DATA-006
The system must maintain a clear data ownership boundary by user and session.

### FR-DATA-007
The system must support cleanup or retention policies for expired session artifacts.

### FR-DATA-008
The system must not treat asynchronous durable-record cleanup as the mechanism for strict session expiry enforcement.

### FR-DATA-009
The system must record sufficient metadata to reconstruct why a session was created, disabled, expired, or rejected.

---

# 3.10 ML inference requirements

### FR-ML-001
The system must support embedding generation for semantic retrieval.

### FR-ML-002
The system must support a pluggable embedding model implementation.

### FR-ML-003
The system must support a configurable reranker implementation.

### FR-ML-004
The system must support an optional compaction model.

### FR-ML-005
The system must support custom inference containers when required by model dependencies.

### FR-ML-006
The system must support model version tracking.

### FR-ML-007
The system must support model evaluation before production promotion.

### FR-ML-008
The system must record model version metadata for embedding, reranking, and compaction outputs where practical.

### FR-ML-009
The system may use TurboQuant only as an experimental optimization within GPU inference workloads.

### FR-ML-010
The system must not depend on TurboQuant for core session correctness, memory storage, or retrieval availability.

---

# 3.11 Background-processing requirements

### FR-BG-001
The system must support asynchronous job execution.

### FR-BG-002
The system must support ordered processing for tasks that require session-level ordering.

### FR-BG-003
The system must support idempotent background jobs.

### FR-BG-004
The system must support retry policies.

### FR-BG-005
The system must support dead-letter handling for permanently failing jobs.

### FR-BG-006
The system must record job status and error details.

### FR-BG-007
The system must avoid blocking hot-path API calls on compaction, PageIndex rebuilding, or long-running document processing.

---

## 4. Non-functional requirements

# 4.1 Performance and latency

### NFR-PERF-001
The system must be designed for low-latency, repeated use by MCP clients and agent workflows.

### NFR-PERF-002
The session lookup path should target p95 latency below 50 milliseconds excluding client-side and internet transit latency.

### NFR-PERF-003
The vector-only retrieval path should target p95 latency below 300 milliseconds under normal load.

### NFR-PERF-004
The add-context path should target p95 latency below 250 milliseconds when embedding inference is lightweight, cached, or colocated.

### NFR-PERF-005
The system must keep nonessential work off the hot path.

### NFR-PERF-006
The system must use connection pooling or persistent connections for hot-store and inference dependencies.

### NFR-PERF-007
The system must support load testing for API, retrieval, and MCP usage patterns.

---

# 4.2 Availability and resiliency

### NFR-REL-001
The production target architecture should support a 99.9% API availability objective.

### NFR-REL-002
The system must degrade gracefully when optional retrieval enhancements are unavailable.

### NFR-REL-003
The system must allow vector-only retrieval when structured retrieval or reranking is unavailable.

### NFR-REL-004
The system must avoid returning unauthorized or cross-tenant context during any partial failure mode.

### NFR-REL-005
The system must use retry behavior carefully to avoid duplicate session or context creation.

### NFR-REL-006
The system must emit alarms for dependency failures, elevated latency, and error-rate spikes.

---

# 4.3 Security

### NFR-SEC-001
The system must encrypt data in transit.

### NFR-SEC-002
The system must encrypt durable data at rest.

### NFR-SEC-003
The system must use least-privilege service permissions.

### NFR-SEC-004
The system must isolate user data by authenticated identity and session ownership.

### NFR-SEC-005
The system must not log raw sensitive context by default.

### NFR-SEC-006
The system must support secrets management outside application source code.

### NFR-SEC-007
The system must support audit logging for administrative or security-sensitive events.

### NFR-SEC-008
The system must validate all inbound request content and metadata.

---

# 4.4 Privacy and data retention

### NFR-PRIV-001
The system must treat session context as user-scoped data.

### NFR-PRIV-002
The system must define retention behavior for hot-store data, durable metadata, object artifacts, and logs.

### NFR-PRIV-003
The system must support explicit deletion or disablement workflows.

### NFR-PRIV-004
The system must preserve only the minimum data necessary for operational auditing.

### NFR-PRIV-005
The system must document whether expired context is recoverable or permanently removed.

---

# 4.5 Observability

### NFR-OBS-001
The system must emit structured logs.

### NFR-OBS-002
The system must attach a request or correlation identifier to logs and responses.

### NFR-OBS-003
The system must emit metrics for request rate, error rate, latency, active sessions, token usage, retrieval outcomes, and compaction jobs.

### NFR-OBS-004
The system must support distributed tracing across the API, workers, hot store, and inference dependencies where available.

### NFR-OBS-005
The system must expose dashboards for operational health.

### NFR-OBS-006
The system must define alarms for latency, availability, job backlog, model failures, and hot-store saturation.

---

# 4.6 Maintainability

### NFR-MAIN-001
The system must define clear module boundaries.

### NFR-MAIN-002
The system must use infrastructure as code.

### NFR-MAIN-003
The system must support separate development, staging, and production environments.

### NFR-MAIN-004
The system must version API contracts and infrastructure modules.

### NFR-MAIN-005
The system must document architectural decisions that affect core behavior.

### NFR-MAIN-006
The system must include automated tests for core business rules.

---

# 4.7 Scalability

### NFR-SCALE-001
The API service must be horizontally scalable.

### NFR-SCALE-002
The background worker service must be independently scalable from the API service.

### NFR-SCALE-003
The inference layer must support independent scaling from the API layer.

### NFR-SCALE-004
The system must support plan-based limits that protect shared infrastructure from excessive usage.

### NFR-SCALE-005
The system must support capacity monitoring for Valkey memory, request throughput, inference capacity, and queue depth.

---

## 5. Constraints

### CON-001
The initial infrastructure design must use AWS services only.

### CON-002
Infrastructure provisioning must use Terraform.

### CON-003
The active session-memory design must use a low-latency TTL-capable store.

### CON-004
The first implementation must support a three-hour inactivity timeout.

### CON-005
The system must be suitable for use as an MCP connector.

### CON-006
The system must support deployment through an automated CI/CD pipeline.

### CON-007
The system must keep expensive compaction and indexing operations asynchronous.

### CON-008
The system must allow plan limits to be configured through data rather than code.

---

## 6. Acceptance baseline

The following conditions must be true before the MVP can be considered functionally complete:

1. An authenticated Free user can create one active session.
2. The Free user cannot create a second active session when the plan limit is one.
3. A higher-tier user can create multiple active sessions according to database-configured policy.
4. An active session expires after three hours without valid activity.
5. Session activity refreshes after valid memory operations.
6. A user cannot access another user’s session or memory.
7. Context can be added, retrieved, removed, and compacted.
8. The context token budget is enforced.
9. Retrieval returns only eligible context items from the requested session.
10. Compaction is asynchronous and preserves source references.
11. An MCP client can execute the core memory operations.
12. The service exposes operational metrics and structured logs.
13. AWS infrastructure can be deployed with Terraform.
14. CI/CD runs tests before deployment.
