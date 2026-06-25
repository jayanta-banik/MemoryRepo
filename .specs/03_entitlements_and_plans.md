# Entitlements and Plans

## 1. Purpose

This document defines how MemoryRepo determines what each authenticated user is allowed to do.

Plan behavior must be data-driven. A plan name such as `Free`, `Go`, `Plus`, or `Premium` is only a label. The actual limits and feature availability must come from database records so administrators can change product policy without redeploying application code.

---

## 2. Core entitlement model

Each user has one effective plan.

Each plan defines limits and features that control:

- Maximum concurrent active sessions.
- Per-session context token budget.
- Maximum context-item size.
- API request limits.
- Retrieval limits.
- Access to reranking.
- Access to PageIndex-backed structured retrieval.
- Access to manual compaction.
- Access to higher-cost model capabilities.
- Retention and observability features, if later added.

The API must resolve entitlements before creating a session or performing any plan-gated operation.

---

## 3. Initial plan labels

MemoryRepo must support these initial plan labels:

| Plan key | Display name | Intended role |
|---|---|---|
| `free` | Free | Default entry tier. |
| `go` | Go | Lightweight paid tier. |
| `plus` | Plus | Higher-capacity individual tier. |
| `premium` | Premium | Highest initial individual tier. |

These labels are configurable product data. The backend should not assume that `premium` always has the highest numerical limit, although that is the expected initial policy.

---

## 4. Initial entitlement policy

The values below are initial defaults only. Administrators must be able to change them in the database.

| Entitlement | Free | Go | Plus | Premium |
|---|---:|---:|---:|---:|
| Maximum active sessions | 1 | 1 | 2 | 3 |
| Session token budget | 10,000 | 15,000 | 25,000 | 40,000 |
| Maximum context items per session | 250 | 500 | 1,000 | 2,000 |
| Maximum input tokens per add request | 2,000 | 4,000 | 8,000 | 12,000 |
| Default retrieval top-k cap | 3 | 3 | 5 | 8 |
| Reranking enabled | No | Optional | Yes | Yes |
| PageIndex retrieval enabled | No | Optional | Yes | Yes |
| Manual compaction allowed | Yes | Yes | Yes | Yes |
| Automatic compaction | Yes | Yes | Yes | Yes |
| Maximum API requests per minute | 60 | 120 | 300 | 600 |
| Maximum MCP tool calls per minute | 60 | 120 | 300 | 600 |

The first MVP may initially enforce only:

1. Maximum active sessions.
2. Session token budget.
3. Maximum retrieval count.
4. API request rate.
5. Feature flags for reranking and PageIndex.

Other limits should still exist in the schema so they can be enabled later without redesigning the entitlement model.

---

## 5. Required plan configuration fields

Each plan record must include at least the following fields.

| Field | Type | Purpose |
|---|---|---|
| `plan_id` | String / UUID | Stable internal identifier. |
| `plan_key` | String | Unique machine-readable name, such as `free`. |
| `display_name` | String | User-facing label. |
| `is_active` | Boolean | Determines whether new assignments are allowed. |
| `max_active_sessions` | Integer | Maximum concurrent active sessions per user. |
| `session_token_budget` | Integer | Maximum total token count allowed in a single session. |
| `max_context_items_per_session` | Integer | Maximum context records allowed in one session. |
| `max_add_request_tokens` | Integer | Maximum token count accepted by one add request. |
| `max_retrieval_top_k` | Integer | Maximum retrieval count allowed for the plan. |
| `api_requests_per_minute` | Integer | API rate-limit policy. |
| `mcp_requests_per_minute` | Integer | MCP rate-limit policy. |
| `enable_reranking` | Boolean | Allows cross-encoder reranking. |
| `enable_pageindex_retrieval` | Boolean | Allows structured retrieval path. |
| `enable_manual_compaction` | Boolean | Allows client-requested compaction. |
| `enable_debug_retrieval_metadata` | Boolean | Allows detailed retrieval diagnostics. |
| `effective_from` | Timestamp | Start of policy validity. |
| `effective_to` | Timestamp / null | Optional end of policy validity. |
| `version` | Integer | Incremented for material plan changes. |
| `updated_at` | Timestamp | Last update time. |
| `updated_by` | String | Administrator or service identity that changed it. |

---

## 6. User entitlement assignment

A user entitlement record must map one user to one effective plan.

### Required user entitlement fields

| Field | Type | Purpose |
|---|---|---|
| `user_id` | String | Authenticated user identity. |
| `plan_id` | String / UUID | Current plan assignment. |
| `status` | Enum | `active`, `suspended`, `expired`, or `grace_period`. |
| `effective_from` | Timestamp | Time plan becomes active. |
| `effective_to` | Timestamp / null | Optional expiration time. |
| `override_max_active_sessions` | Integer / null | Optional user-specific override. |
| `override_session_token_budget` | Integer / null | Optional user-specific override. |
| `feature_overrides` | Map / JSON | Explicit feature-level overrides. |
| `updated_at` | Timestamp | Last change time. |
| `updated_by` | String | Administrator or system actor. |

### Effective entitlement resolution

The system must resolve policy in this order:

```text
1. Verify user identity.
2. Load user entitlement assignment.
3. Validate entitlement status and effective dates.
4. Load referenced plan configuration.
5. Apply user-specific overrides where present.
6. Return the effective entitlement snapshot.
```

A missing user entitlement assignment must resolve to the active default Free plan.

---

## 7. Session creation rules

### 7.1 Create-or-get behavior

When a client calls `create_or_get_session`, MemoryRepo must:

1. Resolve the effective entitlement for the authenticated user.
2. Find active sessions owned by that user.
3. Return an existing eligible active session when reuse mode is requested.
4. Create a new session only when:
   - The caller requests creation or no reusable session exists.
   - The user has not reached `max_active_sessions`.
   - The user entitlement is active.
5. Persist the session’s entitlement snapshot at creation time.
6. Return the session ID, remaining capacity, plan key, and token budget.

### 7.2 Default behavior

The initial default behavior must be:

```text
When no active session exists:
    create one session automatically.

When one or more active sessions exist:
    return the most recently active session unless the client explicitly
    selects another session or explicitly requests a new session.
```

This avoids accidental creation of multiple sessions by tools that call the connector repeatedly.

### 7.3 Parallel active sessions

A user may have multiple active sessions only if their effective entitlement permits it.

Example:

| User plan | Active sessions allowed |
|---|---:|
| Free | 1 |
| Go | 1 |
| Plus | 2 |
| Premium | 3 |

The exact values are configuration data, not application constants.

### 7.4 Session creation rejection

When the active session limit is reached, the API must return a machine-readable error.

Example:

```json
{
  "error": {
    "code": "ACTIVE_SESSION_LIMIT_REACHED",
    "message": "The user has reached the maximum number of active sessions for the current plan.",
    "details": {
      "plan_key": "free",
      "max_active_sessions": 1,
      "active_session_count": 1
    }
  }
}
```

The API must not silently disable an existing active session to create a new one.

---

## 8. Active session definition

A session counts toward `max_active_sessions` only when all conditions are true:

1. Its state is `active`.
2. Its inactivity TTL has not expired.
3. It has not been explicitly disabled.
4. It has not been explicitly terminated.
5. It has not been deactivated by entitlement enforcement.

A session does not count toward the limit when it is:

- `expired`
- `disabled`
- `terminated`
- `deleted`
- `entitlement_deactivated`

---

## 9. Entitlement snapshot at session creation

A session must store the effective policy snapshot used when it was created.

This protects the system from ambiguity when a plan changes later.

### Required session entitlement snapshot

```json
{
  "plan_id": "plan_premium_v3",
  "plan_key": "premium",
  "plan_version": 3,
  "max_active_sessions": 3,
  "session_token_budget": 40000,
  "max_retrieval_top_k": 8,
  "enable_reranking": true,
  "enable_pageindex_retrieval": true,
  "resolved_at": "2026-06-23T00:00:00Z"
}
```

The system may refresh policy for an existing session on each operation, but it must define this behavior consistently.

For the initial design:

```text
Session-count limits are enforced using the user’s current effective entitlement.
Per-session token budget and enabled retrieval features use the session’s
entitlement snapshot unless an administrator explicitly forces re-evaluation.
```

This prevents an unexpected reduction in a running session’s token budget after a plan change.

---

## 10. Upgrade behavior

When a user upgrades:

1. The user entitlement record is updated.
2. New session creation immediately uses the new limit.
3. Existing sessions remain valid.
4. New sessions can be created up to the updated maximum.
5. New calls may access newly enabled features.
6. Existing sessions may retain their original token-budget snapshot unless a policy explicitly refreshes it.

Example:

```text
Free user has one active session.
User upgrades to Plus, where max_active_sessions = 2.
The user may immediately create one additional active session.
```

---

## 11. Downgrade behavior

Downgrades require careful handling because the user may already have more active sessions than the new plan permits.

### 11.1 Default downgrade rule

The default policy must be non-destructive.

When a user downgrades:

1. Do not delete active sessions automatically.
2. Mark excess sessions as `entitlement_over_limit`.
3. Prevent creation of any new session.
4. Allow existing sessions to remain accessible until they expire naturally.
5. After enough sessions expire or are terminated, enforce the new limit normally.

Example:

```text
Premium user has 3 active sessions.
User downgrades to Free, where max_active_sessions = 1.

Result:
- Existing 3 sessions remain active until expiry.
- No new session can be created.
- The account is marked as over the active-session limit.
- Once 2 sessions expire or terminate, normal Free-tier behavior resumes.
```

### 11.2 Optional strict downgrade mode

An administrator may force immediate enforcement.

In strict mode:

1. Preserve the most recently active sessions up to the new limit.
2. Disable excess sessions.
3. Record an audit event for each disabled session.
4. Return a clear state reason such as `entitlement_deactivated`.

Strict enforcement must never silently delete session data.

---

## 12. Feature gating rules

Feature access must be checked at request time.

### 12.1 Reranking

If `enable_reranking = false`:

- The client may request reranking.
- The API must either reject the request with a feature-not-enabled error, or safely fall back to non-reranked retrieval if the API contract explicitly permits fallback.
- The response must indicate whether reranking was applied.

### 12.2 PageIndex retrieval

If `enable_pageindex_retrieval = false`:

- The API must not invoke PageIndex retrieval.
- The response should indicate that vector-only retrieval was used when retrieval diagnostics are authorized.

### 12.3 Manual compaction

If `enable_manual_compaction = false`:

- Client-triggered `compact` requests must be rejected.
- Automatic compaction may remain enabled for token-budget safety.

---

## 13. Rate-limit policy

Rate limits must be plan-aware.

Initial rate limits should be enforced separately for:

- REST API requests.
- MCP tool calls.
- Expensive inference-backed operations.
- Manual compaction requests.

### Required rate-limit dimensions

| Dimension | Example |
|---|---|
| User | Requests per authenticated user. |
| Session | Retrieval calls per session. |
| API operation | Add, get, compact, session create. |
| Client type | REST or MCP. |
| Plan | Free, Go, Plus, Premium. |

The first MVP may implement only per-user request limits, but the policy schema must support the other dimensions.

---

## 14. Caching of entitlement data

The entitlement lookup path must balance correctness and low latency.

### Requirements

1. The authoritative plan and user-entitlement records must be durable.
2. The API may cache resolved entitlement records in Valkey.
3. Cached entitlement entries must have a short TTL.
4. Administrative plan updates must invalidate or version-bust relevant cached entries.
5. A cache failure must fall back to the durable source when possible.
6. A stale cache must not grant more permissive access after an entitlement is suspended or revoked.

### Initial cache direction

```text
Authoritative store: DynamoDB
Hot entitlement cache: Valkey
Suggested cache TTL: 60 seconds
Immediate invalidation: required for suspension, revocation, or strict limit reduction
```

---

## 15. Administrative requirements

The system must support administrative actions for:

- Create plan.
- Update plan.
- Activate or deactivate plan.
- Assign user plan.
- Suspend user entitlement.
- Add user-specific override.
- Remove user-specific override.
- Force session entitlement re-evaluation.
- Force disablement of excess sessions.
- View entitlement audit history.

The first MVP may expose these actions through internal scripts or protected administration APIs rather than a web UI.

---

## 16. Audit requirements

The system must record an audit event for:

- Plan creation or update.
- User plan assignment.
- User entitlement suspension or reactivation.
- User override creation or removal.
- Session creation rejection caused by entitlement limits.
- Session deactivation caused by a downgrade or strict enforcement.
- Explicit administrator session disablement.

Each event must include:

- Event ID.
- Event type.
- Timestamp.
- Actor identity.
- Affected user ID.
- Previous value where applicable.
- New value where applicable.
- Correlation ID.

---

## 17. Acceptance criteria

This document is satisfied when the following can be demonstrated:

1. A user with no explicit entitlement receives the Free plan.
2. Plan limits are read from persistent configuration.
3. Changing a plan limit does not require application redeployment.
4. A Free user with one active session cannot create another active session.
5. A Premium user can create up to the configured maximum active sessions.
6. The API returns a clear error when the session limit is reached.
7. Session creation remains correct during concurrent requests.
8. A plan upgrade increases eligibility for new sessions immediately.
9. A downgrade does not silently destroy active sessions.
10. A strict administrative downgrade can disable excess sessions with audit records.
11. Feature-gated retrieval behavior follows the user’s effective entitlement.
12. Entitlement caching does not continue granting access after a suspension or revocation.
