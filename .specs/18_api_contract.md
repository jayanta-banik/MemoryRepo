# API Contract

## 1. Purpose

This document defines the REST API contract for MemoryRepo.

The REST API is the primary internal and remote service interface. The MCP connector maps its tools to these same business operations but does not replace this contract.

All endpoints are versioned under:

```text
/v1
```

The API uses JSON request and response bodies.

---

## 2. Common conventions

## 2.1 Authentication

All protected endpoints require:

```http
Authorization: Bearer <access_token>
```

The API derives the authenticated user from verified identity claims.

Client-provided user IDs are ignored for authorization.

## 2.2 Correlation ID

Clients may send:

```http
X-Correlation-ID: <client-generated-id>
```

If omitted, MemoryRepo generates one.

Every response must include:

```http
X-Correlation-ID: <id>
```

## 2.3 Idempotency

Endpoints that create state must support:

```http
Idempotency-Key: <client-generated-key>
```

Required for:

- Session creation.
- Context add.

Recommended for:

- Explicit session termination.
- Administrative mutations.

## 2.4 Content type

```http
Content-Type: application/json
Accept: application/json
```

## 2.5 Response envelope

Successful API responses use endpoint-specific JSON structures.

Errors use a common envelope:

```json
{
  "error": {
    "code": "SESSION_EXPIRED",
    "message": "The session expired after inactivity.",
    "retryable": false,
    "details": {
      "session_id": "sess_..."
    }
  }
}
```

---

## 3. Resource model

| Resource | Identifier format | Ownership |
|---|---|---|
| Session | `sess_<ULID>` | Authenticated user. |
| Memory item | `mem_<ULID>` | User-owned session. |
| Job | `job_<ULID>` | User-owned session or administrative process. |
| Plan | Internal UUID or stable plan ID | Administrative data. |

---

## 4. Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/sessions:resolve` | Create or return an active session. |
| `GET` | `/v1/sessions/{session_id}` | Get session status. |
| `POST` | `/v1/sessions/{session_id}:terminate` | Explicitly terminate a session. |
| `POST` | `/v1/sessions/{session_id}/memories` | Add memory context. |
| `POST` | `/v1/sessions/{session_id}/memories:retrieve` | Retrieve relevant memory. |
| `DELETE` | `/v1/sessions/{session_id}/memories/{memory_id}` | Remove a memory item. |
| `POST` | `/v1/sessions/{session_id}/memories:compact` | Queue asynchronous compaction. |
| `GET` | `/v1/jobs/{job_id}` | Get visible job status. |
| `GET` | `/v1/health` | Liveness health endpoint. |
| `GET` | `/v1/ready` | Readiness health endpoint. |

---

# 5. Resolve session

## 5.1 Endpoint

```http
POST /v1/sessions:resolve
```

## 5.2 Purpose

Returns the most recently active eligible session for the authenticated user or creates a new session when no eligible session exists.

## 5.3 Headers

```http
Authorization: Bearer <token>
Idempotency-Key: <key>
Content-Type: application/json
```

## 5.4 Request body

```json
{
  "mode": "reuse_existing",
  "session_label": "cursor-project-memory"
}
```

### Fields

| Field | Required | Description |
|---|---:|---|
| `mode` | No | `reuse_existing` or `create_new`. Defaults to `reuse_existing`. |
| `session_label` | No | Optional human-readable label, max 128 chars. |

## 5.5 Success response

```http
200 OK
```

```json
{
  "action": "reused",
  "session": {
    "session_id": "sess_01J...",
    "state": "active",
    "plan_key": "plus",
    "token_usage": 2300,
    "token_budget": 25000,
    "memory_item_count": 18,
    "ttl_remaining_seconds": 10800,
    "expires_at": "2026-06-25T21:00:00Z",
    "created_at": "2026-06-25T18:00:00Z"
  }
}
```

Possible action values:

```text
created
reused
```

## 5.6 Errors

| Status | Error code | Meaning |
|---|---|---|
| 401 | `AUTHENTICATION_REQUIRED` | Missing or invalid token. |
| 403 | `ENTITLEMENT_SUSPENDED` | User plan is suspended. |
| 409 | `ACTIVE_SESSION_LIMIT_REACHED` | Requested new session exceeds plan limit. |
| 422 | `INVALID_REQUEST` | Invalid body or idempotency key. |
| 429 | `RATE_LIMIT_EXCEEDED` | Request limit exceeded. |
| 503 | `DEPENDENCY_UNAVAILABLE` | Required entitlement or session dependency unavailable. |

---

# 6. Get session status

## 6.1 Endpoint

```http
GET /v1/sessions/{session_id}
```

## 6.2 Purpose

Returns lifecycle, entitlement snapshot, usage, and expiry information for a user-owned active session.

A successful status request refreshes session TTL.

## 6.3 Success response

```http
200 OK
```

```json
{
  "session": {
    "session_id": "sess_01J...",
    "state": "active",
    "plan_key": "premium",
    "plan_version": 3,
    "created_at": "2026-06-25T18:00:00Z",
    "last_activity_at": "2026-06-25T18:30:00Z",
    "ttl_remaining_seconds": 10800,
    "expires_at": "2026-06-25T21:30:00Z",
    "token_usage": 6480,
    "token_budget": 40000,
    "memory_item_count": 44,
    "memory_version": 17,
    "tree_version": 5
  }
}
```

## 6.4 Errors

| Status | Error code |
|---|---|
| 401 | `AUTHENTICATION_REQUIRED` |
| 403 | `AUTHORIZATION_DENIED` |
| 404 | `SESSION_NOT_FOUND` |
| 410 | `SESSION_EXPIRED` |
| 423 | `SESSION_DISABLED` |
| 429 | `RATE_LIMIT_EXCEEDED` |

---

# 7. Terminate session

## 7.1 Endpoint

```http
POST /v1/sessions/{session_id}:terminate
```

## 7.2 Purpose

Explicitly ends an active session.

Termination invalidates further memory operations. The session cannot be resumed.

## 7.3 Request body

```json
{
  "reason": "task_complete"
}
```

## 7.4 Success response

```http
200 OK
```

```json
{
  "action": "terminated",
  "session": {
    "session_id": "sess_01J...",
    "state": "terminated",
    "terminated_at": "2026-06-25T18:45:00Z"
  }
}
```

## 7.5 Errors

| Status | Error code |
|---|---|
| 403 | `AUTHORIZATION_DENIED` |
| 404 | `SESSION_NOT_FOUND` |
| 410 | `SESSION_EXPIRED` |
| 409 | `SESSION_ALREADY_TERMINATED` |

---

# 8. Add memory

## 8.1 Endpoint

```http
POST /v1/sessions/{session_id}/memories
```

## 8.2 Purpose

Adds one context item to an active user-owned session.

## 8.3 Headers

```http
Authorization: Bearer <token>
Idempotency-Key: <key>
Content-Type: application/json
```

## 8.4 Request body

```json
{
  "content": "Use DynamoDB for plan and entitlement metadata.",
  "content_type": "instruction",
  "importance": 0.8,
  "metadata": {
    "source": "coding-agent",
    "workspace_id": "workspace_123"
  }
}
```

## 8.5 Field validation

| Field | Required | Constraints |
|---|---:|---|
| `content` | Yes | Non-empty text, constrained by plan input-token limit. |
| `content_type` | Yes | Controlled enum. |
| `importance` | No | Number from 0.0 to 1.0. |
| `metadata` | No | Bounded JSON object. |

Allowed `content_type` values:

```text
preference
instruction
task_state
agent_plan
tool_output
code_context
document_excerpt
conversation_summary
compacted_summary
system_note
```

## 8.6 Success response

```http
201 Created
```

```json
{
  "action": "created",
  "memory": {
    "memory_id": "mem_01J...",
    "content_type": "instruction",
    "token_count": 10,
    "state": "active",
    "created_at": "2026-06-25T18:50:00Z"
  },
  "session": {
    "session_id": "sess_01J...",
    "token_usage": 6490,
    "token_budget": 10000,
    "memory_item_count": 45,
    "ttl_remaining_seconds": 10800
  },
  "async": {
    "compaction_queued": false
  }
}
```

## 8.7 Duplicate response

```http
200 OK
```

```json
{
  "action": "duplicate_detected",
  "memory": {
    "memory_id": "mem_existing",
    "canonical_memory_id": "mem_existing"
  },
  "session": {
    "session_id": "sess_01J...",
    "ttl_remaining_seconds": 10800
  },
  "async": {
    "compaction_queued": false
  }
}
```

## 8.8 Errors

| Status | Error code | Meaning |
|---|---|---|
| 400 | `INVALID_CONTENT_TYPE` | Unsupported content type. |
| 403 | `AUTHORIZATION_DENIED` | Session does not belong to user. |
| 404 | `SESSION_NOT_FOUND` | Session unavailable. |
| 410 | `SESSION_EXPIRED` | Session expired. |
| 413 | `ADD_REQUEST_TOO_LARGE` | Input exceeds plan or API size limit. |
| 409 | `IDEMPOTENCY_KEY_REUSED` | Same key with different payload. |
| 422 | `MEMORY_TOKEN_BUDGET_EXCEEDED` | Add would exceed session budget. |
| 429 | `RATE_LIMIT_EXCEEDED` | Rate limit exceeded. |
| 503 | `EMBEDDING_UNAVAILABLE` | Required embedding service unavailable. |

---

# 9. Retrieve memory

## 9.1 Endpoint

```http
POST /v1/sessions/{session_id}/memories:retrieve
```

## 9.2 Purpose

Retrieves relevant context from one active user-owned session.

## 9.3 Request body

```json
{
  "query": "Where are plan limits stored?",
  "top_k": 3,
  "min_similarity": 0.78,
  "content_types": [
    "instruction",
    "task_state"
  ],
  "max_return_tokens": 800,
  "retrieval_mode": "auto",
  "use_reranker": true
}
```

## 9.4 Field validation

| Field | Required | Constraints |
|---|---:|---|
| `query` | Yes | Non-empty string. |
| `top_k` | No | Minimum 1, capped by plan and service limit. |
| `min_similarity` | No | Number from 0 to 1. |
| `content_types` | No | Array of allowed content types. |
| `max_return_tokens` | No | Positive integer. |
| `retrieval_mode` | No | `auto`, `vector_only`, or `hybrid`. |
| `use_reranker` | No | Feature-gated boolean. |

## 9.5 Success response

```http
200 OK
```

```json
{
  "session_id": "sess_01J...",
  "query": "Where are plan limits stored?",
  "results": [
    {
      "memory_id": "mem_01J...",
      "content": "Plan definitions and user entitlement assignments are stored durably in DynamoDB.",
      "content_type": "instruction",
      "score": 0.91,
      "token_count": 13,
      "source": "dense_vector",
      "created_at": "2026-06-25T18:50:00Z"
    }
  ],
  "result_count": 1,
  "retrieval_mode_used": "vector_only",
  "reranking_applied": false,
  "session_ttl_remaining_seconds": 10800
}
```

## 9.6 Authorized debug response extension

When authorized and explicitly requested, the API may include:

```json
{
  "diagnostics": {
    "embedding_model_version": "embedding-v1",
    "reranker_model_version": null,
    "tree_version": 5,
    "candidate_count": 12,
    "dense_score": 0.88,
    "structured_score": null,
    "reranker_score": null,
    "final_score": 0.91
  }
}
```

Diagnostics must not reveal internal hostnames, raw logs, secrets, or unrelated tenant information.

## 9.7 Errors

| Status | Error code |
|---|---|
| 403 | `AUTHORIZATION_DENIED` |
| 404 | `SESSION_NOT_FOUND` |
| 410 | `SESSION_EXPIRED` |
| 422 | `RETRIEVAL_LIMIT_EXCEEDED` |
| 403 | `FEATURE_NOT_ENABLED` |
| 429 | `RATE_LIMIT_EXCEEDED` |
| 503 | `EMBEDDING_UNAVAILABLE` |

---

# 10. Remove memory

## 10.1 Endpoint

```http
DELETE /v1/sessions/{session_id}/memories/{memory_id}
```

## 10.2 Purpose

Removes a memory item from normal retrieval.

## 10.3 Success response

```http
200 OK
```

```json
{
  "action": "removed",
  "memory_id": "mem_01J...",
  "session": {
    "session_id": "sess_01J...",
    "token_usage": 6400,
    "token_budget": 10000,
    "memory_item_count": 44,
    "ttl_remaining_seconds": 10800
  },
  "async": {
    "pageindex_rebuild_queued": false
  }
}
```

## 10.4 Errors

| Status | Error code |
|---|---|
| 403 | `AUTHORIZATION_DENIED` |
| 404 | `SESSION_NOT_FOUND` |
| 404 | `MEMORY_NOT_FOUND` |
| 410 | `SESSION_EXPIRED` |
| 423 | `SESSION_DISABLED` |

---

# 11. Queue compaction

## 11.1 Endpoint

```http
POST /v1/sessions/{session_id}/memories:compact
```

## 11.2 Purpose

Queues asynchronous compaction for an active session.

## 11.3 Request body

```json
{
  "strategy": "budget_relief"
}
```

Allowed strategies:

```text
auto
deduplicate
summarize
budget_relief
```

## 11.4 Success response

```http
202 Accepted
```

```json
{
  "action": "queued",
  "job": {
    "job_id": "job_01J...",
    "job_type": "compaction",
    "state": "queued",
    "strategy": "budget_relief"
  },
  "session": {
    "session_id": "sess_01J...",
    "ttl_remaining_seconds": 10800
  }
}
```

## 11.5 Errors

| Status | Error code |
|---|---|
| 403 | `FEATURE_NOT_ENABLED` |
| 403 | `AUTHORIZATION_DENIED` |
| 404 | `SESSION_NOT_FOUND` |
| 409 | `COMPACTION_ALREADY_RUNNING` |
| 410 | `SESSION_EXPIRED` |
| 429 | `RATE_LIMIT_EXCEEDED` |

---

# 12. Get job status

## 12.1 Endpoint

```http
GET /v1/jobs/{job_id}
```

## 12.2 Purpose

Returns job status when the job belongs to the authenticated user.

## 12.3 Success response

```http
200 OK
```

```json
{
  "job": {
    "job_id": "job_01J...",
    "job_type": "compaction",
    "state": "succeeded",
    "session_id": "sess_01J...",
    "created_at": "2026-06-25T18:55:00Z",
    "started_at": "2026-06-25T18:55:02Z",
    "completed_at": "2026-06-25T18:55:07Z",
    "result_summary": {
      "source_memory_count": 8,
      "summary_memory_id": "mem_01J...",
      "tokens_before": 1800,
      "tokens_after": 420
    }
  }
}
```

## 12.4 Errors

| Status | Error code |
|---|---|
| 403 | `AUTHORIZATION_DENIED` |
| 404 | `JOB_NOT_FOUND` |

---

# 13. Health endpoints

## 13.1 Liveness

```http
GET /v1/health
```

Response:

```json
{
  "status": "ok"
}
```

This endpoint confirms the process is running.

## 13.2 Readiness

```http
GET /v1/ready
```

Response:

```json
{
  "status": "ready",
  "dependencies": {
    "valkey": "ok",
    "dynamodb": "ok",
    "embedding_service": "ok"
  }
}
```

Readiness must avoid expensive full retrieval or compaction probes.

---

## 14. Common error codes

| Error code | HTTP status | Retryable |
|---|---:|---:|
| `AUTHENTICATION_REQUIRED` | 401 | No |
| `AUTHORIZATION_DENIED` | 403 | No |
| `ENTITLEMENT_SUSPENDED` | 403 | No |
| `FEATURE_NOT_ENABLED` | 403 | No |
| `SESSION_NOT_FOUND` | 404 | No |
| `MEMORY_NOT_FOUND` | 404 | No |
| `JOB_NOT_FOUND` | 404 | No |
| `ACTIVE_SESSION_LIMIT_REACHED` | 409 | No |
| `COMPACTION_ALREADY_RUNNING` | 409 | Yes |
| `IDEMPOTENCY_KEY_REUSED` | 409 | No |
| `SESSION_EXPIRED` | 410 | No |
| `SESSION_ALREADY_TERMINATED` | 409 | No |
| `SESSION_DISABLED` | 423 | No |
| `INVALID_REQUEST` | 422 | No |
| `INVALID_CONTENT_TYPE` | 400 | No |
| `ADD_REQUEST_TOO_LARGE` | 413 | No |
| `MEMORY_TOKEN_BUDGET_EXCEEDED` | 422 | No |
| `RETRIEVAL_LIMIT_EXCEEDED` | 422 | No |
| `RATE_LIMIT_EXCEEDED` | 429 | Yes |
| `EMBEDDING_UNAVAILABLE` | 503 | Yes |
| `DEPENDENCY_UNAVAILABLE` | 503 | Yes |
| `INTERNAL_ERROR` | 500 | Maybe |

---

## 15. Pagination

The initial API does not require broad memory-list endpoints because retrieval is query-driven.

If future list endpoints are added, use opaque cursor pagination:

```text
cursor
limit
next_cursor
```

Do not expose raw Valkey keys or DynamoDB partition keys as cursors.

---

## 16. Versioning and compatibility

- API paths must remain versioned under `/v1`.
- Additive response fields are allowed.
- Required fields must not be removed without version change or deprecation period.
- New enum values must be introduced carefully because clients may use strict validation.
- MCP tool schemas must be kept compatible with this REST contract.
- All API contracts should be represented in OpenAPI before implementation.

---

## 17. Acceptance criteria

This document is satisfied when:

1. Core session and memory operations have stable REST endpoints.
2. All protected endpoints derive user identity from verified tokens.
3. Session creation and add-memory operations support idempotency.
4. Responses include correlation IDs.
5. Error responses use one consistent machine-readable format.
6. Retrieval respects plan limits, feature gates, and session ownership.
7. Compaction returns `202 Accepted` and does not block on job completion.
8. Health and readiness endpoints support ECS and deployment checks.
9. API schemas can be mapped directly into OpenAPI and MCP tool contracts.
