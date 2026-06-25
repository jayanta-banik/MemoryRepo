# Low-Latency Design

## 1. Purpose

This document defines the low-latency design for MemoryRepo.

MemoryRepo is intended to serve repeated context operations from MCP clients, coding agents, IDE extensions, LangChain applications, and other agentic systems. The service must keep normal session, add, and retrieval operations fast enough that it reduces prompt cost and context handling overhead rather than becoming a new bottleneck.

The design distinguishes between:

- **Hot-path operations** that are synchronous and latency-sensitive.
- **Async operations** that must not delay normal client responses.

---

## 2. Performance objectives

The initial targets are directional engineering goals. They should be validated with load tests before production release.

| Operation | Target p50 | Target p95 | Notes |
|---|---:|---:|---|
| `create_or_get_session` | < 25 ms | < 75 ms | Excluding client internet transit. |
| `get_session_status` | < 15 ms | < 50 ms | Hot-store read only under normal conditions. |
| `memory_add` without cold inference | < 100 ms | < 250 ms | Includes validation, dedupe, write, TTL refresh. |
| `memory_get` vector-only | < 100 ms | < 300 ms | Includes query embedding and bounded vector search. |
| `memory_get` hybrid retrieval | < 200 ms | < 600 ms | Only when PageIndex candidate metadata is already available. |
| `memory_get` with reranking | < 250 ms | < 800 ms | Candidate set must remain bounded. |
| `memory_remove` | < 50 ms | < 150 ms | Atomic update and index removal. |
| `memory_compact` request | < 25 ms | < 100 ms | Queue acceptance only. |
| Background compaction | Not user-facing | Not user-facing | Must not block normal requests. |

These targets apply inside AWS service boundaries. Browser, IDE, local host, VPN, and public internet latency are outside direct API-service control.

---

## 3. Hot-path operations

The following operations are part of the hot path:

- JWT verification or trusted identity validation.
- Entitlement cache lookup.
- Session lookup in Valkey.
- User ownership validation.
- Active-state and TTL validation.
- Rate-limit check.
- Idempotency lookup.
- Token counting.
- Exact duplicate detection.
- Bounded semantic embedding request.
- Session-local vector search.
- Atomic memory write or removal.
- Session TTL refresh.
- Small response assembly.

The hot path must avoid unbounded work.

---

## 4. Async operations

The following operations must remain asynchronous:

- Large-scale compaction.
- LLM-generated summarization.
- PageIndex hierarchy generation.
- PageIndex tree rebuild.
- Long-document parsing.
- Batch embedding repair.
- Reindexing large memory sets.
- Audit aggregation.
- Cost reporting.
- Offline retrieval evaluation.
- Model benchmarking.
- Retention cleanup.
- Historical analytics export.

The API may enqueue these tasks, but it must not wait for their completion unless an explicitly separate long-running workflow is introduced.

---

## 5. Latency budget by request type

# 5.1 create_or_get_session

| Step | Budget |
|---|---:|
| Token verification | 5 to 15 ms |
| Entitlement cache lookup | 1 to 5 ms |
| Valkey active-session lookup | 1 to 5 ms |
| Atomic session create or reuse operation | 2 to 10 ms |
| Durable session metadata write | 5 to 25 ms |
| Response assembly | 1 to 5 ms |
| Total p95 target | Under 75 ms |

The durable write may be made asynchronous only if the system retains enough reliable state to prevent lost session records. The default first implementation should write durable session metadata synchronously because session creation is relatively infrequent.

# 5.2 memory_add

| Step | Budget |
|---|---:|
| Authentication and authorization | 5 to 15 ms |
| Session lookup and state validation | 1 to 5 ms |
| Idempotency lookup | 1 to 5 ms |
| Token counting | 1 to 10 ms |
| Embedding generation | 20 to 120 ms |
| Duplicate candidate query | 2 to 20 ms |
| Atomic write and TTL refresh | 2 to 15 ms |
| Queue compaction if needed | 2 to 10 ms |
| Audit event enqueue or write | 1 to 20 ms |
| Total p95 target | Under 250 ms |

# 5.3 memory_get

| Step | Budget |
|---|---:|
| Authentication and authorization | 5 to 15 ms |
| Session validation | 1 to 5 ms |
| Query tokenization | 1 to 10 ms |
| Query embedding | 20 to 120 ms |
| Valkey vector search | 3 to 30 ms |
| Optional structured candidate lookup | 5 to 50 ms |
| Optional reranking | 20 to 250 ms |
| Ranking and response trimming | 1 to 20 ms |
| TTL refresh | 1 to 5 ms |
| Total vector-only p95 target | Under 300 ms |
| Total hybrid p95 target | Under 600 ms |
| Total reranked p95 target | Under 800 ms |

---

## 6. Deployment locality

Latency is heavily affected by network distance.

MemoryRepo should place the following components in the same AWS region:

- API Gateway private integration target.
- ECS API service.
- ECS MCP service.
- ElastiCache for Valkey.
- DynamoDB tables.
- SageMaker embedding and reranking endpoints.
- SQS queues.
- S3 artifacts.

The API service and Valkey cluster should be in the same VPC and availability-zone topology that minimizes cross-AZ calls where resilience requirements allow.

Do not place embedding inference in a different region from the API path for the initial deployment.

---

## 7. Connection management

## 7.1 Valkey connection pooling

The API and worker services must use persistent pooled Valkey connections.

Requirements:

- Create connections at process startup.
- Reuse connections across requests.
- Limit maximum connections per task.
- Set reasonable connection and command timeouts.
- Use health checks and reconnect logic.
- Avoid opening one connection per request.
- Monitor pool exhaustion and command latency.

Suggested initial controls:

| Setting | Initial direction |
|---|---|
| Connect timeout | 100 to 250 ms |
| Command timeout | 250 to 500 ms for hot-path commands |
| Connection pool size | Derived from ECS task concurrency |
| Retry behavior | Small bounded retry only for safe idempotent reads |
| Pipeline usage | Use for independent short commands where atomicity is not required |

## 7.2 HTTP client pooling

The API service must use persistent HTTP connection pools for:

- SageMaker inference calls.
- Internal service calls.
- API Gateway or service integrations where applicable.

Requirements:

- Enable keep-alive.
- Bound client connection pool size.
- Use request timeouts per dependency.
- Propagate correlation IDs.
- Avoid unbounded retries.

## 7.3 DNS and TLS reuse

Container runtime configuration should avoid repeated DNS resolution and repeated TLS setup where client libraries support pooling and keep-alive.

---

## 8. Entitlement caching

Entitlement resolution must be fast because it is used on most requests.

### 8.1 Cache layout

Suggested key:

```text
memoryrepo:{env}:entitlement:{user_id}
```

Suggested TTL:

```text
60 seconds
```

### 8.2 Cache contents

The cache should contain only the effective entitlement needed for fast authorization:

```json
{
  "plan_key": "plus",
  "plan_version": 3,
  "status": "active",
  "max_active_sessions": 2,
  "session_token_budget": 25000,
  "max_retrieval_top_k": 5,
  "enable_reranking": true,
  "enable_pageindex_retrieval": true,
  "enable_manual_compaction": true,
  "expires_at": "..."
}
```

### 8.3 Invalidation rules

Immediate invalidation is required for:

- User suspension.
- Entitlement revocation.
- Strict downgrade enforcement.
- Administrative feature disablement with security or cost implications.
- Account deletion.

Normal plan changes may use versioned cache invalidation or short TTL expiry.

---

## 9. Embedding latency strategy

Embedding generation is often the largest part of the normal add and get paths.

## 9.1 Model selection rule

Use a compact embedding model for the online path.

The online embedding model should prioritize:

- Low inference latency.
- Stable output dimensions.
- Good retrieval quality for short instructions, code context, task state, and tool outputs.
- Batch support.
- Version stability.

A larger model may be evaluated offline, but should not be deployed to the hot path without latency evidence.

## 9.2 Query embedding caching

A short-lived query embedding cache may be used for repeated queries.

Suggested cache key:

```text
memoryrepo:{env}:query_embedding:{model_version}:{normalized_query_hash}
```

Suggested TTL:

```text
5 to 15 minutes
```

Do not cache raw query text as the key. Use a normalized cryptographic hash.

## 9.3 Add-content embedding caching

Content embeddings may be reused when:

- Content hash matches exactly.
- Embedding model version matches.
- Embedding policy allows reuse.

This can reduce duplicate add latency.

## 9.4 Batch inference

Use batch inference only for async jobs or multiple independent operations.

Do not wait to batch unrelated live user requests if batching increases p95 latency.

---

## 10. Vector retrieval design

## 10.1 Session-local search

All vector retrieval must filter by:

```text
owner_user_id
session_id
state = active
```

This filter is mandatory before ranking results.

## 10.2 Candidate limits

Retrieval must use bounded candidate counts.

Suggested defaults:

| Stage | Candidate count |
|---|---:|
| Initial dense vector candidates | 10 to 30 |
| Structured candidates | 5 to 15 |
| Reranker candidates | 5 to 15 |
| Final returned results | 1 to plan-allowed top-k |

Do not retrieve hundreds or thousands of candidate memories for a normal MCP call.

## 10.3 Approximate nearest-neighbor behavior

Use approximate vector search settings that balance latency and recall.

The implementation must expose tuning parameters through environment or deployment configuration, such as:

- Vector index type.
- Candidate count.
- Search effort.
- Similarity metric.
- Minimum score.
- Metadata filters.

The first release should prioritize predictable p95 latency and validate recall through an evaluation dataset.

---

## 11. Reranking policy

Reranking must be optional and bounded.

### 11.1 When to use reranking

Use reranking when:

- The user plan enables it.
- The request has enough ambiguity to justify it.
- Candidate count is small.
- The API is still within latency budget.

### 11.2 When to skip reranking

Skip reranking when:

- The plan does not permit it.
- Candidate count is one.
- Embedding confidence is high.
- The reranker endpoint is degraded.
- The caller explicitly requests low-latency mode.
- The operation is part of a high-frequency tool loop.

### 11.3 Fallback

If reranking fails or times out:

- Return vector-only or hybrid non-reranked results.
- Do not retry repeatedly in the same request.
- Record an observability signal.
- Do not fail retrieval solely due to reranker unavailability.

---

## 12. PageIndex latency policy

PageIndex is useful for long-form or structured context. It is not appropriate for every short memory item.

### 12.1 When PageIndex may run in retrieval

Use PageIndex candidate retrieval only when:

- The plan feature flag permits it.
- The session has a valid PageIndex artifact.
- The requested context is likely to benefit from structured retrieval.
- Artifact metadata is already known or quickly accessible.
- The query is not a high-frequency low-latency call requiring vector-only mode.

### 12.2 What PageIndex must not do on hot path

The hot path must not:

- Build a PageIndex tree.
- Parse a long document from scratch.
- Read a large number of S3 objects.
- Invoke long-context LLM reasoning without explicit latency allowance.
- Recompute a full hierarchy after every memory addition.

### 12.3 Artifact metadata cache

Store small PageIndex metadata or pointers in Valkey:

```text
memoryrepo:{env}:session:{user_id}:{session_id}:pageindex_meta
```

This allows the API to decide quickly whether structured retrieval is available.

---

## 13. Token counting strategy

Token counting must be consistent and fast.

### 13.1 Online counting

For normal request sizes, token counting should occur in the API process using a compatible tokenizer library.

### 13.2 Large content

If content is too large for fast synchronous tokenization:

- Reject it according to plan limits.
- Require client-side chunking.
- Or route it to an explicit asynchronous document ingestion flow.

Do not allow arbitrarily large add requests into the normal MCP memory tool.

### 13.3 Token budget cache

The session metadata hash in Valkey must contain current:

```text
token_usage
token_budget
```

The API must not scan all memory items to calculate remaining capacity during normal add operations.

---

## 14. Atomic operations and Lua scripts

Use Valkey Lua scripts or equivalent atomic transactions for multi-key state changes.

Required atomic flows:

| Flow | Atomic requirements |
|---|---|
| Create session | Check plan limit, reserve count, add active index, create metadata, apply TTL. |
| Add memory | Validate active session, enforce budget, update counters, write memory, update memory index, refresh TTL. |
| Remove memory | Confirm membership, decrement counters, remove index entry, change state, refresh TTL. |
| Refresh session | Update activity timestamp, update active-session score, refresh all session-local TTLs. |
| Compact commit | Verify memory version, write summary, supersede sources, update counters, increment version. |

Lua script failures must be instrumented. The API must not attempt non-atomic fallback logic that can violate session limits or token budgets.

---

## 15. Request shaping

The API must protect the hot path from oversized requests.

### 15.1 Limits

Initial configurable limits should include:

| Limit | Purpose |
|---|---|
| Maximum request body size | Prevent oversized payloads. |
| Maximum content tokens per add | Keep add latency bounded. |
| Maximum metadata size | Avoid large JSON blobs. |
| Maximum retrieval top-k | Keep ranking and response bounded. |
| Maximum return tokens | Prevent context flooding. |
| Maximum concurrent requests per user | Prevent abuse. |
| Maximum compaction requests per session | Prevent queue flooding. |

### 15.2 Response shaping

Retrieval responses should:

- Return only top-k permitted items.
- Apply a total return-token cap.
- Exclude unnecessary debug data by default.
- Avoid repeated raw content.
- Include compact metadata only.

---

## 16. Rate limiting and backpressure

## 16.1 Rate-limit layers

Rate limits should apply at:

- API Gateway or WAF edge layer.
- Application user-level layer.
- Operation-level layer.
- Expensive inference-operation layer.
- Session-level compaction queue layer.

## 16.2 Backpressure behavior

When load rises:

- Reject excess requests early with `RATE_LIMIT_EXCEEDED`.
- Return retry guidance only when safe.
- Do not queue unlimited synchronous operations.
- Apply queue depth alarms.
- Reduce optional reranking before rejecting core retrieval.
- Prefer vector-only retrieval over total service failure when optional features degrade.

## 16.3 Circuit breakers

The API should use circuit-breaker behavior for SageMaker dependencies.

Example:

```text
If embedding endpoint failures exceed threshold:
    open circuit briefly
    fail fast with retryable inference error
    avoid overwhelming the already failing endpoint
```

---

## 17. ECS runtime tuning

The API and MCP services should:

- Use async-capable application servers.
- Set worker count based on CPU and expected I/O concurrency.
- Avoid blocking CPU-heavy tokenization on the event loop.
- Use bounded task concurrency.
- Use graceful shutdown so in-flight requests can complete.
- Set health checks that verify application readiness without calling expensive dependencies.
- Emit startup logs showing configured model version and environment.

The worker service should be tuned separately because its workload is CPU, memory, and GPU-dependency heavy rather than request-latency sensitive.

---

## 18. Observability for latency

The service must emit latency metrics for:

- Authentication.
- Entitlement lookup.
- Valkey read and write.
- Lua script execution.
- Token counting.
- Embedding request.
- Vector search.
- Structured candidate lookup.
- Reranking.
- TTL refresh.
- DynamoDB writes.
- SQS enqueue.
- End-to-end API response.
- End-to-end MCP tool response.

Each request must carry a correlation ID so p95 outliers can be traced across components.

Suggested metric names:

```text
memoryrepo.api.latency_ms
memoryrepo.mcp.latency_ms
memoryrepo.valkey.command_latency_ms
memoryrepo.embedding.latency_ms
memoryrepo.vector_search.latency_ms
memoryrepo.reranker.latency_ms
memoryrepo.pageindex.lookup_latency_ms
memoryrepo.compaction.enqueue_latency_ms
```

---

## 19. Load-test scenarios

The load-test suite must include:

1. Repeated `memory_get` calls from one active coding-agent session.
2. Many users with one active Free session each.
3. Premium users with multiple active sessions.
4. Concurrent `create_new` calls against a one-session limit.
5. Add operations near token-budget soft threshold.
6. Add operations at hard token limit.
7. Retrieval with vector-only mode.
8. Retrieval with hybrid mode.
9. Retrieval during reranker outage.
10. Retrieval during PageIndex artifact outage.
11. Compaction queue backlog.
12. Valkey connection pool saturation.
13. SageMaker embedding endpoint latency spike.
14. Session expiration during a client retry.
15. Rate-limit burst from an MCP client.

---

## 20. Acceptance criteria

This document is satisfied when:

1. Hot-path and async-path operations are clearly separated.
2. Each core API operation has a measurable p95 latency target.
3. Valkey and SageMaker clients use pooled persistent connections.
4. Entitlement data is cached safely with clear invalidation rules.
5. Retrieval uses bounded candidate counts.
6. Reranking can be skipped or degraded without failing ordinary retrieval.
7. PageIndex is never rebuilt in a normal request path.
8. Token accounting does not require scanning all session memory.
9. Atomic Valkey operations enforce session and token constraints.
10. Rate limits and circuit breakers prevent dependency overload.
11. Metrics can identify which dependency contributes to latency.
12. Load tests cover realistic MCP and coding-agent patterns.
