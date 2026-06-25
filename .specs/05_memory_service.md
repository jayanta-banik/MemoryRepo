# Memory Service

## 1. Purpose

This document defines the session-scoped memory service for MemoryRepo.

The memory service stores temporary context for LLM applications, MCP clients, coding agents, LangChain workflows, and related systems. It is designed to reduce repeated prompt transmission by selectively storing, compacting, and retrieving useful context from an active user session.

Core operations:

```text
create()
add()
get()
remove()
compact()
```

All memory operations are scoped to one active session owned by one authenticated user.

---

## 2. Memory model

A memory item is a bounded unit of context stored inside an active session.

A memory item may represent:

- User preference.
- System instruction.
- Task state.
- Agent plan.
- Tool output.
- Code snippet or repository summary.
- Document excerpt.
- Error diagnosis.
- Conversation summary.
- Compacted summary generated from other memory items.

Each memory item must have a unique identifier.

Recommended format:

```text
mem_<ULID>
```

---

## 3. Core principles

### 3.1 Session-scoped

Memory is temporary and belongs to exactly one session.

### 3.2 User-isolated

A user may access only memory from sessions they own.

### 3.3 Token-budgeted

Each session has a maximum token budget determined by its entitlement snapshot.

### 3.4 Retrieval-oriented

Memory should be stored in a form that supports fast relevance retrieval.

### 3.5 Provenance-preserving

Compacted memory must reference the memory items it was derived from.

### 3.6 Hot-path discipline

Add and get operations must avoid waiting on expensive work whenever possible.

Compaction, large document indexing, and PageIndex tree rebuilds must run asynchronously.

---

## 4. Memory item schema

Each memory item must support the following fields.

| Field | Required | Purpose |
|---|---:|---|
| `memory_id` | Yes | Unique memory item identifier. |
| `session_id` | Yes | Owning session. |
| `owner_user_id` | Yes | Owning authenticated user. |
| `content` | Yes | Main text content. |
| `content_type` | Yes | Classification of memory. |
| `token_count` | Yes | Token count using configured tokenizer. |
| `created_at` | Yes | Creation timestamp. |
| `updated_at` | No | Last update timestamp. |
| `importance` | No | Optional priority score. |
| `metadata` | No | Structured metadata. |
| `embedding` | Conditional | Dense semantic vector. |
| `embedding_model_version` | Conditional | Embedding model identifier. |
| `state` | Yes | Active, superseded, deleted, or archived. |
| `source_memory_ids` | No | Original memories used to create a compacted result. |
| `superseded_by` | No | Replacement summary or memory item. |
| `duplicate_of` | No | Canonical memory identifier when duplicate detected. |
| `last_retrieved_at` | No | Most recent retrieval timestamp. |
| `retrieval_count` | No | Number of times retrieved. |
| `expires_with_session` | Yes | Indicates session lifecycle dependency. |

---

## 5. Memory states

| State | Meaning | Eligible for normal retrieval? |
|---|---|---:|
| `active` | Current usable memory item. | Yes |
| `superseded` | Replaced by a compacted or updated memory item. | No |
| `duplicate` | Equivalent to another canonical item. | No |
| `deleted` | Explicitly removed. | No |
| `archived` | Retained for audit or provenance only. | No |
| `pending_embedding` | Stored but semantic vector not yet available. | No by default |
| `compaction_pending` | Candidate waiting for compaction. | Yes unless excluded by policy |
| `compaction_failed` | Compaction failed. Original item remains usable. | Yes |

---

## 6. Content types

The API must support at least these values:

| Content type | Example |
|---|---|
| `preference` | “Use PostgreSQL for transactional data.” |
| `instruction` | “Always use ES modules in this repository.” |
| `task_state` | “Authentication refactor is blocked on Cognito callback setup.” |
| `agent_plan` | “First add Terraform modules, then deploy API.” |
| `tool_output` | Test result, command output, compiler output. |
| `code_context` | Summary of a module or code segment. |
| `document_excerpt` | Relevant passage from a long document. |
| `conversation_summary` | Summary of a discussion. |
| `compacted_summary` | Summary generated from multiple prior memories. |
| `system_note` | Internal service-generated metadata note. |

The API may allow custom content types later, but the first implementation should validate against a controlled list.

---

## 7.0 create()

creates a new session for the user

## 7. add()

## 7.1 Purpose

`add()` stores one new context item in an active session.

It must:

1. Validate user ownership.
2. Validate session state and expiry.
3. Validate request payload.
4. Enforce per-request size limits.
5. Enforce session token budget.
6. Detect duplicates where possible.
7. Generate or attach an embedding.
8. Persist the memory item.
9. Refresh the session inactivity TTL.
10. Queue asynchronous compaction if needed.

---

## 7.2 Input contract

Suggested logical request:

```json
{
  "session_id": "sess_...",
  "content": "The codebase uses Terraform modules by service boundary.",
  "content_type": "instruction",
  "importance": 0.8,
  "metadata": {
    "source": "agent",
    "workspace_id": "repo_123",
    "language": "python"
  },
  "idempotency_key": "client-generated-key"
}
```

### Required input fields

| Field | Requirement |
|---|---|
| `session_id` | Required. Must identify an active user-owned session. |
| `content` | Required. Non-empty text. |
| `content_type` | Required. Controlled enum. |
| `idempotency_key` | Required for production-safe add behavior. |

### Optional input fields

| Field | Requirement |
|---|---|
| `importance` | Numeric value within configured range. |
| `metadata` | Validated JSON map. |
| `source_reference` | Optional source locator or tool reference. |
| `client_timestamp` | Optional, must not replace server timestamp. |

---

## 7.3 add() algorithm

```text
1. Authenticate caller.
2. Resolve user identity from verified credentials.
3. Load and validate session from hot store.
4. Verify session ownership.
5. Validate content, content type, metadata, and request size.
6. Check idempotency key.
7. Count tokens using configured tokenizer.
8. Reject if request token count exceeds plan-level request limit.
9. Perform exact duplicate check.
10. Generate embedding or use supported cached embedding path.
11. Perform near-duplicate candidate search.
12. Decide whether to:
      a. create new memory,
      b. return canonical duplicate,
      c. merge or update an existing memory,
      d. queue compaction.
13. Atomically enforce token budget and write memory.
14. Refresh session TTL.
15. Update session memory count and token usage.
16. Emit audit and operational events.
17. Queue asynchronous work if required.
18. Return result.
```

---

## 7.4 Token accounting

Token accounting must use the tokenizer associated with the primary generation or compaction model policy.

The implementation must not use simple whitespace counts as production token accounting.

Each session maintains:

```text
token_usage
token_budget
remaining_tokens = token_budget - token_usage
```

The token budget must be enforced atomically with memory creation.

### Budget policy options

The service must support one configured behavior when a new item would exceed the budget:

| Policy | Behavior |
|---|---|
| `reject` | Reject the add request without storing new content. |
| `compact_then_retry` | Queue compaction and return a retryable response. |
| `truncate_input` | Store only a configured prefix or summarized form. |
| `evict_low_value` | Remove low-value eligible memory items before adding. |
| `store_pending` | Store outside retrieval path until compaction succeeds. |

Initial recommended policy:

```text
If usage is below a soft threshold:
    add normally.

If usage crosses soft threshold:
    add normally and queue compaction.

If usage would exceed hard budget:
    reject with MEMORY_TOKEN_BUDGET_EXCEEDED
    or compact_then_retry if client explicitly supports asynchronous retry.
```

Initial soft threshold:

```text
85% of session token budget
```

---

## 7.5 Duplicate detection

### Exact duplicate detection

The service must detect exact duplicates using normalized content hashing.

Normalization should include:

- Trim surrounding whitespace.
- Normalize line endings.
- Collapse repeated internal whitespace where appropriate.
- Preserve semantic punctuation where important.
- Avoid destructive normalization of code content.

Suggested record:

```text
normalized_content_hash
```

If an exact duplicate is found in the same active session:

- Do not create a second memory item.
- Return the canonical memory identifier.
- Refresh session TTL.
- Optionally update retrieval or access metadata.

### Near-duplicate detection

The service should perform a semantic similarity search against recent active memory items.

Initial conceptual thresholds:

| Similarity range | Suggested action |
|---|---|
| `>= 0.92` | Treat as likely duplicate and return canonical item. |
| `0.82 to < 0.92` | Store item but mark as compaction candidate or merge candidate. |
| `< 0.82` | Store as new active memory. |

Thresholds must be configurable and evaluated empirically.

Code, logs, and structured tool output may need separate duplicate policies because small textual differences can be meaningful.

---

## 7.6 add() responses

### Created memory

```json
{
  "memory_id": "mem_...",
  "action": "created",
  "session_id": "sess_...",
  "token_count": 14,
  "session_token_usage": 640,
  "session_token_budget": 10000,
  "compaction_queued": false
}
```

### Duplicate response

```json
{
  "memory_id": "mem_existing",
  "action": "duplicate_detected",
  "canonical_memory_id": "mem_existing",
  "session_id": "sess_...",
  "compaction_queued": false
}
```

### Budget error

```json
{
  "error": {
    "code": "MEMORY_TOKEN_BUDGET_EXCEEDED",
    "message": "Adding this context would exceed the session token budget.",
    "details": {
      "token_usage": 9800,
      "token_budget": 10000,
      "incoming_token_count": 500
    }
  }
}
```

---

## 8. get()

## 8.1 Purpose

`get()` retrieves the most relevant memory items from an active session for a supplied query.

The initial default maximum result count is:

```text
top_k = 3
```

The effective maximum depends on the user’s entitlement.

---

## 8.2 Input contract

```json
{
  "session_id": "sess_...",
  "query": "What database choice did we make for transactional data?",
  "top_k": 3,
  "min_similarity": 0.78,
  "filters": {
    "content_types": ["preference", "instruction"]
  },
  "include_debug_metadata": false
}
```

### Required input fields

| Field | Requirement |
|---|---|
| `session_id` | Required. Active user-owned session. |
| `query` | Required. Non-empty text. |

### Optional input fields

| Field | Requirement |
|---|---|
| `top_k` | Defaults to 3 and cannot exceed plan limit. |
| `min_similarity` | Optional threshold within configured bounds. |
| `filters` | Optional metadata and content-type filters. |
| `include_debug_metadata` | Requires entitlement or administrative authorization. |
| `max_return_tokens` | Optional response-budget constraint. |
| `use_reranker` | Optional and feature-gated. |
| `use_pageindex` | Optional and feature-gated. |

---

## 8.3 get() algorithm

```text
1. Authenticate caller.
2. Load active session from hot store.
3. Verify user ownership.
4. Validate query and options.
5. Resolve entitlement feature flags and limits.
6. Generate query embedding.
7. Retrieve dense semantic candidates from session-local index.
8. Optionally retrieve PageIndex or structured candidates.
9. Remove ineligible items:
      - expired,
      - deleted,
      - superseded,
      - duplicate,
      - wrong session,
      - filtered-out metadata.
10. Optionally rerank candidates.
11. Apply score fusion.
12. Apply minimum similarity threshold.
13. Deduplicate semantically overlapping candidates.
14. Apply top-k limit.
15. Apply response token budget.
16. Refresh session TTL.
17. Update retrieval metadata.
18. Return items and optional diagnostics.
```

---

## 8.4 Ranking model

The initial retrieval score may combine:

```text
final_score =
    semantic_similarity_weight * semantic_similarity
  + recency_weight * recency_score
  + importance_weight * importance_score
  + structured_weight * structured_retrieval_score
  + reranker_weight * reranker_score
```

The actual weights must be configurable.

Initial conceptual weights for hybrid-enabled plans:

```text
semantic_similarity: 0.55
structured_retrieval: 0.20
reranker_score: 0.15
recency_score: 0.05
importance_score: 0.05
```

For vector-only retrieval:

```text
semantic_similarity: 0.80
recency_score: 0.10
importance_score: 0.10
```

These are starting points, not fixed production constants.

---

## 8.5 Retrieval result schema

```json
{
  "session_id": "sess_...",
  "query": "What database choice did we make?",
  "results": [
    {
      "memory_id": "mem_...",
      "content": "Use PostgreSQL for durable transactional data.",
      "content_type": "preference",
      "score": 0.91,
      "token_count": 8,
      "created_at": "2026-06-23T00:00:00Z",
      "source": "dense_vector"
    }
  ],
  "result_count": 1,
  "retrieval_mode": "vector_only",
  "session_ttl_remaining_seconds": 10800
}
```

Debug metadata must not be returned unless authorized.

Potential debug fields:

- Dense similarity.
- Reranker score.
- Structured retrieval score.
- Recency score.
- Importance score.
- Ranking explanation.
- Model version.
- Index version.

---

## 8.6 Empty retrieval

When no result satisfies threshold or filters:

```json
{
  "session_id": "sess_...",
  "query": "...",
  "results": [],
  "result_count": 0,
  "retrieval_mode": "vector_only"
}
```

An empty retrieval is not an error.

---

## 9. remove()

## 9.1 Purpose

`remove()` removes or logically deletes a specific memory item from an active session.

The user may remove memory that is obsolete, incorrect, sensitive, or no longer useful.

---

## 9.2 remove() algorithm

```text
1. Authenticate caller.
2. Load session from hot store.
3. Verify session ownership.
4. Locate requested memory item.
5. Confirm memory belongs to session.
6. Mark item deleted or remove it from hot store.
7. Remove vector index entry.
8. Decrement session token usage and memory count atomically.
9. Mark dependent compacted summaries for review if necessary.
10. Queue PageIndex rebuild if applicable.
11. Refresh session TTL.
12. Record audit event.
13. Return deletion result.
```

---

## 9.3 Removal policy

The initial service should use logical deletion for auditability, with hot-path removal from retrieval indexes.

Deletion must ensure the item is not returned by future retrieval.

When a removed memory was used in a compacted summary:

- Do not silently rewrite the summary in the hot path.
- Mark the summary as `provenance_changed` or `rebuild_required`.
- Queue asynchronous review or summary rebuild.
- Preserve removal audit history.

---

## 9.4 remove() response

```json
{
  "memory_id": "mem_...",
  "action": "removed",
  "session_id": "sess_...",
  "session_token_usage": 610,
  "rebuild_queued": false
}
```

---

## 10. compact()

## 10.1 Purpose

`compact()` reduces memory footprint by combining related, redundant, or low-value context into smaller high-value summaries.

Compaction is not simple deletion. It must preserve useful facts, source provenance, and contradictions.

---

## 10.2 Compaction triggers

Compaction may be initiated by:

- Client request.
- Token-budget soft threshold.
- High duplicate density.
- High memory-item count.
- Long inactive interval before session expiration.
- Background optimization policy.
- Large document ingestion completion.

Initial trigger policy:

```text
Queue compaction when session token usage reaches 85% of token budget.
```

Manual compaction must be feature-gated by entitlement.

---

## 10.3 Compaction execution model

Compaction must be asynchronous.

```text
Client/API request
    |
    v
Validate and enqueue job
    |
    v
SQS FIFO queue
    |
    v
Compaction worker
    |
    v
Embedding / clustering / LLM summary generation
    |
    v
Atomic memory replacement and index update
```

The client must receive a job or acceptance response without waiting for full LLM compaction.

---

## 10.4 Compaction algorithm

```text
1. Acquire session-level compaction lock.
2. Read current active memories and session memory version.
3. Select candidate groups:
      - near duplicates,
      - repeated task updates,
      - related tool outputs,
      - stale detailed context with a newer summary.
4. Cluster candidate memories.
5. Preserve contradictions as separate facts.
6. Generate compacted summary.
7. Validate summary length and source references.
8. Re-check session memory version before commit.
9. Create compacted summary memory item.
10. Mark source items as superseded or archived.
11. Update vector index.
12. Update token accounting.
13. Increment memory version.
14. Queue PageIndex tree rebuild if needed.
15. Release lock.
16. Emit job result and metrics.
```

---

## 10.5 Compaction output schema

```json
{
  "memory_id": "mem_compacted_...",
  "content_type": "compacted_summary",
  "content": "The project uses Valkey for active session memory and DynamoDB for durable entitlement metadata.",
  "source_memory_ids": [
    "mem_001",
    "mem_002",
    "mem_003"
  ],
  "token_count": 19,
  "state": "active"
}
```

---

## 10.6 Contradiction handling

The compactor must not convert contradictory memories into one misleading statement.

Example source memories:

```text
A: The user prefers PostgreSQL for transactional data.
B: The user currently uses DynamoDB for plan configuration.
```

Valid compacted result:

```text
The system uses PostgreSQL for transactional workloads and DynamoDB for plan configuration.
```

Example contradiction:

```text
A: Use Redis for permanent user profile data.
B: Do not use Redis for permanent user profile data.
```

The compactor should preserve the conflict:

```text
There are conflicting historical instructions about Redis for permanent profile data. Treat DynamoDB as the current durable-profile direction until resolved.
```

---

## 10.7 Compaction failure behavior

If compaction fails:

- Source memories must remain retrievable.
- Token accounting must remain correct.
- Job status must become failed or retryable.
- The API must not claim compaction succeeded.
- The system may retry according to policy.
- A failed compaction must not block ordinary retrieval.

---

## 11. Low-latency boundaries

The following should remain on the synchronous request path:

| Operation | Hot path? |
|---|---:|
| Authentication and ownership validation | Yes |
| Session state validation | Yes |
| Token-budget check | Yes |
| Exact duplicate check | Yes |
| Valkey write or read | Yes |
| Dense vector candidate retrieval | Yes |
| Lightweight embedding generation | Yes, where latency permits |
| TTL refresh | Yes |

The following must be asynchronous or optional:

| Operation | Hot path? |
|---|---:|
| Large-scale compaction | No |
| PageIndex tree rebuilding | No |
| Long document processing | No |
| Batch embedding repair | No |
| Durable analytics export | No |
| Large audit aggregation | No |
| Heavy reranking | Optional |
| GPU long-context compaction | No |

---

## 12. Error conditions

| Error code | Meaning |
|---|---|
| `SESSION_NOT_FOUND` | Session does not exist in active store. |
| `SESSION_EXPIRED` | Session expired due to inactivity. |
| `SESSION_DISABLED` | Session is disabled. |
| `SESSION_TERMINATED` | Session was explicitly ended. |
| `MEMORY_NOT_FOUND` | Requested memory does not exist in session. |
| `MEMORY_TOKEN_BUDGET_EXCEEDED` | Add would exceed session budget. |
| `ADD_REQUEST_TOO_LARGE` | Add request exceeds plan or API limit. |
| `FEATURE_NOT_ENABLED` | Requested capability not available for plan. |
| `INVALID_CONTENT_TYPE` | Unsupported memory classification. |
| `DUPLICATE_REQUEST` | Idempotency key maps to previous request. |
| `COMPACTION_ALREADY_RUNNING` | Existing session compaction lock is active. |
| `RETRIEVAL_LIMIT_EXCEEDED` | Requested top-k exceeds entitlement. |

---

## 13. Metrics

The memory service must emit at least:

- Add request count.
- Get request count.
- Remove request count.
- Compact request count.
- Add latency.
- Get latency.
- Duplicate detection rate.
- Near-duplicate candidate rate.
- Token-budget rejection count.
- Mean session token usage.
- Memory items per session.
- Retrieval result count.
- Empty retrieval rate.
- Retrieval similarity distribution.
- Compaction queue depth.
- Compaction success and failure rate.
- Token compression ratio.
- PageIndex rebuild count.
- Embedding inference latency.
- Reranker latency when enabled.

---

## 14. Acceptance criteria

This document is satisfied when all of the following can be demonstrated:

1. A user can add context to an owned active session.
2. The same idempotency key does not create duplicate memory records.
3. Exact duplicates do not create additional active memory items.
4. Session token usage updates correctly after add and remove.
5. The system rejects add requests that exceed configured request or session limits.
6. Retrieval returns only active, eligible context from the requested session.
7. Retrieval returns no more than the plan-allowed top-k.
8. Retrieval can return an empty result without error.
9. Removed memory no longer appears in normal retrieval.
10. Compaction runs asynchronously.
11. Compaction preserves source-memory references.
12. Compaction failure does not corrupt source memory.
13. Session TTL refreshes after successful memory operations.
14. Expired, disabled, or unauthorized sessions cannot access memory.
