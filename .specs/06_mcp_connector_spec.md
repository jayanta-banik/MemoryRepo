   +# MCP Connector Specification

## 1. Purpose

This document defines the Model Context Protocol connector for MemoryRepo.

The connector exposes session-scoped context memory as MCP tools so an LLM host, coding agent, IDE extension, LangChain application, LangGraph workflow, or other MCP client can store and retrieve relevant context without repeatedly injecting a full history into every model prompt.

MemoryRepo uses MCP for tool invocation. The MemoryRepo session is application state and is not the same thing as an MCP transport or protocol session.

---

## 2. Design goals

The MCP connector must:

- Expose a small tool surface that models can use reliably.
- Support low-latency repeated retrieval for coding and agent workflows.
- Use explicit MemoryRepo session IDs as tool arguments.
- Enforce the same authentication, ownership, entitlement, and rate-limit rules as the REST API.
- Return stable structured content suitable for model consumption.
- Avoid leaking AWS, database, embedding-model, or internal topology details.
- Keep expensive work, including compaction and PageIndex rebuilding, off the normal tool-response path.
- Make destructive actions clearly distinguishable from read-only actions.

---

## 3. Protocol boundary

MCP defines the protocol between a host, its MCP client, and the MemoryRepo MCP server. MemoryRepo defines its own user working-memory sessions.

```text
LLM Host / IDE / Agent
        |
        | MCP
        v
MemoryRepo MCP Server
        |
        | internal service calls
        v
MemoryRepo Session and Memory Service
```

The MCP server must not use an MCP connection identifier as a MemoryRepo session identifier.

A MemoryRepo session identifier must always be explicit:

```text
sess_<ULID>
```

This supports stateless horizontal scaling of the MCP service and allows a client to reconnect without losing its application-level memory reference.

---

## 4. Initial transport strategy

### 4.1 Primary transport

The first remote deployment must use:

```text
Streamable HTTP over HTTPS
```

The MCP server must be deployable behind API Gateway and an internal load-balanced ECS service.

### 4.2 Local development transport

The project may provide a local `stdio` MCP server for development and IDE testing.

The local server must use environment-provided credentials or a local development identity strategy. It must not expose production credentials in configuration files.

### 4.3 Transport independence

All MemoryRepo tool contracts must be transport-independent.

A client invoking `memory_get` through local `stdio` must receive the same logical schema and business behavior as a client invoking it through remote Streamable HTTP.

---

## 5. Authentication and authorization

## 5.1 Remote MCP authentication

Remote MCP requests must use an authenticated identity.

Initial production direction:

```text
OAuth 2.1 / OpenID Connect compatible access token
validated against Amazon Cognito configuration
```

The MemoryRepo MCP server must:

1. Validate the access token.
2. Derive `user_id` from trusted token claims.
3. Use that derived identity for all ownership checks.
4. Reject malformed, expired, revoked, or unauthorized tokens.
5. Never authorize based only on a user ID supplied in tool arguments.

### 5.2 Local stdio authentication

For local development only, the server may obtain a short-lived token or developer identity from environment variables, AWS profile credentials, or a secure local credential helper.

Local development must not bypass authorization logic. It may use a different credential source, but it must still produce a valid effective user identity before invoking the memory service.

### 5.3 Tool authorization rules

Every tool call must validate:

```text
1. Authenticated identity.
2. Effective entitlement.
3. Session ownership where session_id is supplied.
4. Rate limits.
5. Tool-specific feature flags.
```

---

## 6. Tool catalog

The initial MCP server must expose these tools in deterministic order:

1. `memory_create_or_get_session`
2. `memory_get_session_status`
3. `memory_add`
4. `memory_get`
5. `memory_remove`
6. `memory_compact`
7. `memory_terminate_session`

The server may later expose administrative tools through a separate admin-only MCP server. Administrative capabilities must not be exposed by the user-facing connector.

---

## 7. Tool design rules

### 7.1 Naming

Tool names must:

- Use lowercase snake_case.
- Start with the `memory_` prefix.
- Be stable once published.
- Describe an action precisely.

### 7.2 Input schemas

Each tool must define JSON Schema input validation.

The server must reject unknown or malformed required fields unless the schema intentionally allows extension fields.

### 7.3 Output schemas

Each tool must return:

- Human-readable text content for basic agent compatibility.
- Structured JSON content for programmatic clients.
- A stable operation result or error code.

### 7.4 Idempotency

The tools `memory_create_or_get_session` and `memory_add` must accept an optional or required `idempotency_key` appropriate to their operation.

### 7.5 Tool annotations

The MCP implementation should annotate tools by behavior:

| Tool | Read-only | Destructive |
|---|---:|---:|
| `memory_create_or_get_session` | No | No |
| `memory_get_session_status` | Yes | No |
| `memory_add` | No | No |
| `memory_get` | Yes | No |
| `memory_remove` | No | Yes |
| `memory_compact` | No | Potentially destructive |
| `memory_terminate_session` | No | Yes |

Clients should show user confirmation for destructive operations where their interaction model supports it.

---

## 8. Tool specifications

# 8.1 memory_create_or_get_session

### Purpose

Returns the most recently active eligible MemoryRepo session for the authenticated user or creates one when no eligible session exists.

The default behavior prevents editor agents from creating unnecessary sessions on every connection or tool call.

### Input schema

```json
{
  "type": "object",
  "properties": {
    "mode": {
      "type": "string",
      "enum": ["reuse_existing", "create_new"],
      "default": "reuse_existing"
    },
    "session_label": {
      "type": "string",
      "maxLength": 128
    },
    "idempotency_key": {
      "type": "string",
      "maxLength": 256
    }
  },
  "additionalProperties": false
}
```

### Functional behavior

```text
1. Resolve authenticated user.
2. Resolve effective entitlement.
3. If mode = reuse_existing:
      return most recently active session, if present.
      otherwise create one.
4. If mode = create_new:
      create a session only if the active session limit permits it.
5. Return the session entitlement snapshot and current state.
```

### Structured result

```json
{
  "operation": "memory_create_or_get_session",
  "action": "created",
  "session": {
    "session_id": "sess_...",
    "state": "active",
    "plan_key": "free",
    "token_budget": 10000,
    "token_usage": 0,
    "ttl_remaining_seconds": 10800,
    "expires_at": "2026-06-23T18:30:00Z"
  }
}
```

### Error codes

- `ACTIVE_SESSION_LIMIT_REACHED`
- `ENTITLEMENT_SUSPENDED`
- `INVALID_IDEMPOTENCY_KEY`
- `RATE_LIMIT_EXCEEDED`

---

# 8.2 memory_get_session_status

### Purpose

Returns lifecycle and usage information for an active user-owned session.

### Input schema

```json
{
  "type": "object",
  "properties": {
    "session_id": {
      "type": "string",
      "pattern": "^sess_[A-Za-z0-9_-]+$"
    }
  },
  "required": ["session_id"],
  "additionalProperties": false
}
```

### Structured result

```json
{
  "operation": "memory_get_session_status",
  "session": {
    "session_id": "sess_...",
    "state": "active",
    "plan_key": "plus",
    "created_at": "2026-06-23T15:30:00Z",
    "last_activity_at": "2026-06-23T16:11:00Z",
    "ttl_remaining_seconds": 10800,
    "token_usage": 6350,
    "token_budget": 25000,
    "memory_item_count": 24,
    "memory_version": 17
  }
}
```

A successful status request refreshes the MemoryRepo session inactivity TTL.

---

# 8.3 memory_add

### Purpose

Adds one bounded context item to an active user-owned MemoryRepo session.

### Input schema

```json
{
  "type": "object",
  "properties": {
    "session_id": {
      "type": "string",
      "pattern": "^sess_[A-Za-z0-9_-]+$"
    },
    "content": {
      "type": "string",
      "minLength": 1
    },
    "content_type": {
      "type": "string",
      "enum": [
        "preference",
        "instruction",
        "task_state",
        "agent_plan",
        "tool_output",
        "code_context",
        "document_excerpt",
        "conversation_summary",
        "compacted_summary",
        "system_note"
      ]
    },
    "importance": {
      "type": "number",
      "minimum": 0,
      "maximum": 1
    },
    "metadata": {
      "type": "object"
    },
    "idempotency_key": {
      "type": "string",
      "minLength": 1,
      "maxLength": 256
    }
  },
  "required": [
    "session_id",
    "content",
    "content_type",
    "idempotency_key"
  ],
  "additionalProperties": false
}
```

### Functional behavior

```text
1. Confirm session state and ownership.
2. Validate plan-level add size and rate limits.
3. Count tokens.
4. Detect exact duplicates.
5. Attempt near-duplicate detection when enabled.
6. Add or deduplicate memory.
7. Enforce session token budget atomically.
8. Queue asynchronous compaction when applicable.
9. Refresh MemoryRepo session TTL.
```

### Structured result

```json
{
  "operation": "memory_add",
  "action": "created",
  "memory": {
    "memory_id": "mem_...",
    "content_type": "instruction",
    "token_count": 24
  },
  "session": {
    "session_id": "sess_...",
    "token_usage": 674,
    "token_budget": 10000,
    "ttl_remaining_seconds": 10800
  },
  "async": {
    "compaction_queued": false
  }
}
```

---

# 8.4 memory_get

### Purpose

Retrieves the most relevant context items from a specific active session.

This tool is expected to be called frequently by coding agents and should be optimized for low latency.

### Input schema

```json
{
  "type": "object",
  "properties": {
    "session_id": {
      "type": "string",
      "pattern": "^sess_[A-Za-z0-9_-]+$"
    },
    "query": {
      "type": "string",
      "minLength": 1
    },
    "top_k": {
      "type": "integer",
      "minimum": 1,
      "maximum": 20,
      "default": 3
    },
    "min_similarity": {
      "type": "number",
      "minimum": 0,
      "maximum": 1
    },
    "content_types": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "uniqueItems": true
    },
    "max_return_tokens": {
      "type": "integer",
      "minimum": 1
    },
    "retrieval_mode": {
      "type": "string",
      "enum": ["auto", "vector_only", "hybrid"],
      "default": "auto"
    }
  },
  "required": ["session_id", "query"],
  "additionalProperties": false
}
```

### Functional behavior

```text
1. Confirm session state and ownership.
2. Enforce plan-specific top-k and feature limits.
3. Generate query embedding.
4. Retrieve session-local semantic candidates.
5. Optionally use PageIndex structured retrieval when:
      - feature is entitled,
      - the client permits hybrid mode,
      - indexed structured content exists.
6. Filter ineligible or superseded items.
7. Apply optional reranking when enabled.
8. Return only the requested and allowed number of results.
9. Refresh MemoryRepo session TTL.
```

### Structured result

```json
{
  "operation": "memory_get",
  "session_id": "sess_...",
  "results": [
    {
      "memory_id": "mem_...",
      "content": "Use PostgreSQL for durable transactional data.",
      "content_type": "preference",
      "score": 0.91,
      "token_count": 8,
      "source": "dense_vector"
    }
  ],
  "result_count": 1,
  "retrieval_mode_used": "vector_only",
  "session_ttl_remaining_seconds": 10800
}
```

The default client-visible result must contain only useful context and minimal ranking data. Detailed diagnostics require entitlement and explicit opt-in.

---

# 8.5 memory_remove

### Purpose

Removes a memory item from future normal retrieval.

### Input schema

```json
{
  "type": "object",
  "properties": {
    "session_id": {
      "type": "string",
      "pattern": "^sess_[A-Za-z0-9_-]+$"
    },
    "memory_id": {
      "type": "string",
      "pattern": "^mem_[A-Za-z0-9_-]+$"
    }
  },
  "required": ["session_id", "memory_id"],
  "additionalProperties": false
}
```

### Functional behavior

```text
1. Confirm session ownership and state.
2. Verify memory belongs to session.
3. Remove from the active retrieval index.
4. Update token usage and memory count atomically.
5. Retain a logical deletion or audit trace as configured.
6. Queue dependent summary or PageIndex rebuild work when needed.
7. Refresh session TTL.
```

### Structured result

```json
{
  "operation": "memory_remove",
  "action": "removed",
  "memory_id": "mem_...",
  "session": {
    "session_id": "sess_...",
    "token_usage": 542,
    "ttl_remaining_seconds": 10800
  },
  "async": {
    "rebuild_queued": false
  }
}
```

---

# 8.6 memory_compact

### Purpose

Requests asynchronous compaction of related or redundant memory within an active session.

### Input schema

```json
{
  "type": "object",
  "properties": {
    "session_id": {
      "type": "string",
      "pattern": "^sess_[A-Za-z0-9_-]+$"
    },
    "strategy": {
      "type": "string",
      "enum": ["auto", "deduplicate", "summarize", "budget_relief"],
      "default": "auto"
    }
  },
  "required": ["session_id"],
  "additionalProperties": false
}
```

### Functional behavior

```text
1. Confirm entitlement allows manual compaction.
2. Confirm session ownership and state.
3. Check whether a compaction lock or equivalent job already exists.
4. Queue ordered asynchronous compaction work.
5. Return acceptance immediately.
6. Refresh session TTL because the request represents user activity.
```

### Structured result

```json
{
  "operation": "memory_compact",
  "action": "queued",
  "session_id": "sess_...",
  "job": {
    "job_id": "cmp_...",
    "state": "queued",
    "strategy": "budget_relief"
  }
}
```

---

# 8.7 memory_terminate_session

### Purpose

Explicitly ends an active MemoryRepo session.

This action is destructive because the session cannot be resumed after termination.

### Input schema

```json
{
  "type": "object",
  "properties": {
    "session_id": {
      "type": "string",
      "pattern": "^sess_[A-Za-z0-9_-]+$"
    },
    "reason": {
      "type": "string",
      "maxLength": 256
    }
  },
  "required": ["session_id"],
  "additionalProperties": false
}
```

### Functional behavior

```text
1. Confirm session ownership.
2. Change lifecycle state to terminated.
3. Remove or invalidate hot session keys.
4. Update active session count.
5. Preserve durable lifecycle metadata.
6. Return termination confirmation.
```

---

## 9. Tool response conventions

Every successful result must include:

```text
operation
```

Every error result must use this structure:

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

### Required error codes

- `AUTHENTICATION_REQUIRED`
- `AUTHORIZATION_DENIED`
- `ENTITLEMENT_SUSPENDED`
- `ACTIVE_SESSION_LIMIT_REACHED`
- `SESSION_NOT_FOUND`
- `SESSION_EXPIRED`
- `SESSION_DISABLED`
- `SESSION_TERMINATED`
- `MEMORY_NOT_FOUND`
- `MEMORY_TOKEN_BUDGET_EXCEEDED`
- `ADD_REQUEST_TOO_LARGE`
- `FEATURE_NOT_ENABLED`
- `RETRIEVAL_LIMIT_EXCEEDED`
- `COMPACTION_ALREADY_RUNNING`
- `RATE_LIMIT_EXCEEDED`
- `INTERNAL_ERROR`

The server must not expose stack traces, AWS resource identifiers, database keys, internal hostnames, or secret-related data in tool results.

---

## 10. Latency requirements for MCP tools

| Tool | Target behavior |
|---|---|
| `memory_create_or_get_session` | Return quickly using cached entitlement and hot session state. |
| `memory_get_session_status` | Hot-store read only under normal conditions. |
| `memory_add` | Synchronous validation and storage. Heavy compaction remains async. |
| `memory_get` | Vector-first retrieval. Hybrid features are optional and bounded. |
| `memory_remove` | Atomic hot-store removal. Rebuild tasks remain async. |
| `memory_compact` | Queue only, never wait for model execution. |
| `memory_terminate_session` | Immediate state invalidation and durable audit update. |

The MCP server should use connection pooling to Valkey and inference endpoints. It should avoid per-call cold starts and avoid synchronous durable analytics writes in normal paths.

---

## 11. Session discovery guidance for agents

A client should follow this pattern:

```text
At agent startup or task start:
    call memory_create_or_get_session(mode="reuse_existing")

Before expensive LLM generation:
    call memory_get(session_id, query, top_k=3)

After resolving a meaningful task state, preference, decision, or tool outcome:
    call memory_add(...)

When memory grows or task context becomes repetitive:
    call memory_compact(session_id)

At explicit end of task:
    optionally call memory_terminate_session(session_id)
```

The connector must not automatically add all conversations or raw tool outputs to memory. The integrating client or agent should choose context worth persisting.

---

## 12. Resource and prompt policy

### 12.1 Resources

The first MCP release should not expose raw session memory as broadly browseable MCP resources.

Reason:

- Session IDs are sensitive capability-like references.
- Tool calls provide clearer authorization boundaries.
- Retrieval should remain query-driven to minimize context flooding.

A later release may add read-only resources for explicitly selected, user-owned session summaries.

### 12.2 Prompts

The first MCP release should not expose prompt templates as core functionality.

MemoryRepo provides memory tools. Prompt assembly remains the responsibility of the host application or agent.

---

## 13. Observability and trace propagation

The MCP server must:

- Generate or accept a correlation ID.
- Pass the correlation ID to the internal API service.
- Log the tool name, latency, response status, session ID hash, and user ID hash.
- Avoid logging raw memory content by default.
- Emit separate metrics for each tool.
- Support OpenTelemetry trace-context propagation where the client provides standard trace metadata.

---

## 14. Security requirements

The MCP server must:

- Require HTTPS for remote traffic.
- Validate input against declared schemas.
- Enforce tenant isolation on every tool.
- Apply plan-aware rate limits.
- Rate-limit expensive operations separately.
- Require user confirmation where host interaction patterns support confirmation for removal and session termination.
- Restrict diagnostic metadata to authorized users and plans.
- Avoid returning unbounded raw context.
- Avoid treating LLM-generated tool arguments as trusted authorization data.

---

## 15. Compatibility and versioning

The server must:

- Advertise the supported MCP protocol version through the SDK or protocol handshake.
- Maintain deterministic tool order for predictable client behavior and client-side caching.
- Version MemoryRepo tool schemas carefully.
- Avoid breaking renamed tools when a backwards-compatible alias is possible.
- Include a server implementation version in diagnostics only, not in normal user-facing results.
- Keep the MemoryRepo API version independent from MCP protocol version.

---

## 16. Acceptance criteria

This document is satisfied when:

1. A remote MCP client can authenticate and call MemoryRepo tools over HTTPS.
2. A local stdio development server can use the same tool behavior with safe local credentials.
3. `memory_create_or_get_session` returns or creates a user-owned session without accidental duplication.
4. `memory_add` stores valid context and enforces session ownership, idempotency, and budget rules.
5. `memory_get` returns bounded relevant context from only the requested user-owned session.
6. `memory_remove` prevents removed context from appearing in ordinary retrieval.
7. `memory_compact` queues asynchronous work and returns without waiting for compaction completion.
8. `memory_terminate_session` invalidates active use of the session.
9. Tool errors are machine-readable and do not expose infrastructure internals.
10. The connector remains horizontally scalable because MemoryRepo session state is explicit and external to MCP transport state.

---

## 17. References

The connector should track the current stable MCP specification and implementation guidance before production release. MCP uses JSON-RPC messages between hosts, clients, and servers, and official guidance defines tool schemas, HTTP authorization, and transport behavior. citeturn780751search1turn780751search2turn780751search13
