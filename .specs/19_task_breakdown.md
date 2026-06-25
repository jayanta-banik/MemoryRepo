# Implementation Task Breakdown

## 1. Purpose

This document turns MemoryRepo requirements into small implementation tasks.

Each task is intentionally scoped so it can be implemented, tested, reviewed, and merged independently.

Recommended workflow:

```text
Create feature branch
    -> implement one task or a tightly related task group
    -> open PR to dev
    -> pass checks
    -> squash merge into dev
    -> dev auto-deploys
    -> release dev to main through release PR
```

---

## 2. Task status conventions

| Status | Meaning |
|---|---|
| `not_started` | Work has not begun. |
| `in_progress` | Active implementation. |
| `blocked` | Waiting on dependency or decision. |
| `review` | Implementation complete, awaiting PR review. |
| `done` | Merged and validated. |
| `deferred` | Intentionally postponed. |

---

## 3. Milestone 0: Repository foundation

### Task M0.1: Create repository structure

**Goal**

Create the base repository layout for services, infrastructure, models, tests, and documentation.

**Functional requirements**

- Create `services/api`.
- Create `services/mcp`.
- Create `services/worker`.
- Create `infra`.
- Create `models`.
- Create `tests`.
- Create `.github/workflows`.
- Add root-level README and contribution guidance.

**Dependencies**

- None.

**Acceptance criteria**

- Repository structure matches CI/CD requirements.
- Each service directory contains a minimal README.
- Python project configuration is present.
- Local test command can run successfully.

---

### Task M0.2: Configure branch protections

**Goal**

Enforce the Git workflow.

**Functional requirements**

- Protect `dev`.
- Protect `main`.
- Require PRs for both branches.
- Require squash merge into `dev`.
- Require normal merge commit from `dev` into `main`.
- Require status checks.
- Disable direct pushes except emergency policy.

**Dependencies**

- M0.1.

**Acceptance criteria**

- Feature branch cannot merge into `dev` without required checks.
- `main` cannot receive a direct push.
- Release PR from `dev` to `main` is possible.
- Merge strategy settings match CI/CD design.

---

### Task M0.3: Create base GitHub Actions checks

**Goal**

Run basic validation on every pull request.

**Functional requirements**

- Add lint workflow.
- Add unit-test workflow.
- Add type-check workflow.
- Add secret scan.
- Add Terraform format and validation checks.
- Add container build smoke check.

**Dependencies**

- M0.1.

**Acceptance criteria**

- Opening a PR to `dev` triggers checks.
- Failing lint or tests blocks merge.
- Workflow output is visible in GitHub PR checks.

---

### Task M0.4: Create Python shared package

**Goal**

Create common types and utilities shared across API, MCP, and worker services.

**Functional requirements**

- Define shared configuration loader.
- Define shared error classes.
- Define common IDs and timestamp utilities.
- Define correlation ID helper.
- Define common Pydantic models.
- Define structured logging helper.

**Dependencies**

- M0.1.

**Acceptance criteria**

- API, MCP, and worker can import shared package.
- Unit tests validate ID and error behavior.
- No service-specific business logic is placed in shared utilities.

---

## 4. Milestone 1: Local development baseline

### Task M1.1: Create local configuration model

**Goal**

Define environment-driven application configuration.

**Functional requirements**

- Support `dev`, `stage`, and `prod`.
- Validate required environment variables.
- Separate public config from secrets.
- Include placeholders for Valkey, DynamoDB, SQS, Cognito, and SageMaker settings.
- Fail fast for invalid environment configuration.

**Dependencies**

- M0.4.

**Acceptance criteria**

- Service startup fails with clear message when required settings are absent.
- Local `.env.example` contains no secrets.
- Configuration supports test overrides.

---

### Task M1.2: Create local Valkey development service

**Goal**

Allow local development against a Valkey-compatible store.

**Functional requirements**

- Add Docker Compose or equivalent local runtime.
- Expose Valkey locally for development only.
- Include health check.
- Document startup and cleanup commands.

**Dependencies**

- M1.1.

**Acceptance criteria**

- Developer can start Valkey locally.
- API test can connect to local Valkey.
- No production infrastructure assumptions are embedded in local compose setup.

---

### Task M1.3: Add local DynamoDB strategy

**Goal**

Support local and testable durable metadata behavior.

**Functional requirements**

- Choose DynamoDB Local, mocked repository interfaces, or both.
- Create repository abstraction.
- Support test fixtures for plans, entitlements, sessions, and jobs.

**Dependencies**

- M1.1.

**Acceptance criteria**

- Unit tests run without production AWS access.
- Integration tests can use local or isolated test DynamoDB.
- Repository interfaces are independent from API handlers.

---

### Task M1.4: Create local mock embedding provider

**Goal**

Enable memory and retrieval development before SageMaker is deployed.

**Functional requirements**

- Define embedding provider interface.
- Add deterministic mock embedding provider.
- Add test fixture vectors.
- Add provider selection through configuration.

**Dependencies**

- M0.4, M1.1.

**Acceptance criteria**

- Retrieval tests run deterministically without AWS.
- API can switch between mock and real embedding providers.
- Mock provider does not become production default.

---

## 5. Milestone 2: Identity and entitlement foundation

### Task M2.1: Implement authenticated-user context

**Goal**

Establish one trusted identity source for every request.

**Functional requirements**

- Define authenticated user model.
- Add JWT validation adapter interface.
- Implement local development identity adapter.
- Reject missing identity on protected routes.
- Store user ID in request context.

**Dependencies**

- M1.1.

**Acceptance criteria**

- Protected endpoint rejects request without identity.
- User ID comes from trusted adapter.
- Client body user ID cannot override authenticated identity.

---

### Task M2.2: Create user repository

**Goal**

Persist durable user records.

**Functional requirements**

- Create user entity.
- Create get-or-create user operation.
- Support active, suspended, deleted state.
- Add optimistic version field.

**Dependencies**

- M1.3, M2.1.

**Acceptance criteria**

- User record is created on first valid authenticated request.
- Suspended user state can be read.
- Unit tests cover state transitions.

---

### Task M2.3: Create plans repository

**Goal**

Support database-driven plan definitions.

**Functional requirements**

- Create plan entity.
- Support plan versioning.
- Support lookup by plan key.
- Support active and inactive plan states.
- Seed Free, Go, Plus, and Premium plans for development.

**Dependencies**

- M1.3.

**Acceptance criteria**

- Plan limits are loaded from persistent data.
- Updating a plan version does not require API code change.
- Development seed data includes all initial plan keys.

---

### Task M2.4: Create entitlement repository

**Goal**

Map users to plans and overrides.

**Functional requirements**

- Create entitlement entity.
- Resolve default Free plan when no entitlement record exists.
- Support active, suspended, expired, and grace-period states.
- Support session-limit override.
- Support token-budget override.
- Support feature override map.

**Dependencies**

- M2.2, M2.3.

**Acceptance criteria**

- User without assignment resolves to Free.
- User-specific override changes effective entitlement.
- Suspended entitlement prevents protected operations.

---

### Task M2.5: Implement entitlement resolution service

**Goal**

Return one effective entitlement object for each user.

**Functional requirements**

- Load entitlement assignment.
- Load plan version.
- Apply user overrides.
- Validate effective dates.
- Return effective limits and feature flags.
- Include plan version and resolution timestamp.

**Dependencies**

- M2.4.

**Acceptance criteria**

- Effective entitlement matches plan plus overrides.
- Missing assignment returns Free plan.
- Expired assignment fails correctly.
- Unit tests cover upgrade, downgrade, suspension, and override cases.

---

### Task M2.6: Add Valkey entitlement cache

**Goal**

Reduce durable entitlement reads on hot paths.

**Functional requirements**

- Cache effective entitlement by user.
- Use short TTL.
- Add cache invalidation method.
- Invalidate on suspension and strict downgrade.
- Fall back to durable source on cache miss.

**Dependencies**

- M1.2, M2.5.

**Acceptance criteria**

- Repeated requests hit cache.
- Suspension invalidates cache.
- Cache miss resolves from repository.
- Tests cover stale-cache protection behavior.

---

## 6. Milestone 3: Session lifecycle

### Task M3.1: Define session entities and state machine

**Goal**

Create session domain models.

**Functional requirements**

- Define session ID generation.
- Define valid session states.
- Define transition validation.
- Define session entitlement snapshot.
- Define session status response model.

**Dependencies**

- M0.4, M2.5.

**Acceptance criteria**

- Invalid state transitions are rejected.
- Session IDs use required prefix.
- Tests cover active, expired, disabled, terminated, and entitlement-deactivated states.

---

### Task M3.2: Implement hot session metadata store

**Goal**

Store active session state in Valkey.

**Functional requirements**

- Create session metadata hash.
- Apply three-hour TTL.
- Store token usage and budget.
- Store memory count.
- Store session state.
- Store plan snapshot.
- Implement session lookup by user and session.

**Dependencies**

- M1.2, M3.1.

**Acceptance criteria**

- Session metadata expires after configured TTL.
- Session lookup returns correct owner and state.
- Metadata has all required fields.
- Test verifies TTL exists.

---

### Task M3.3: Implement active-session index

**Goal**

Track active sessions per user.

**Functional requirements**

- Create sorted set for active sessions.
- Track last activity score.
- Create active-session count.
- Add cleanup behavior for terminated or disabled sessions.
- Support most recently active session lookup.

**Dependencies**

- M3.2.

**Acceptance criteria**

- Latest active session can be resolved.
- Count matches active index.
- Disabled session no longer counts.
- Tests cover multiple active sessions.

---

### Task M3.4: Implement atomic create-or-get session script

**Goal**

Prevent race conditions during session creation.

**Functional requirements**

- Create Valkey Lua script or equivalent atomic operation.
- Support `reuse_existing`.
- Support `create_new`.
- Check entitlement max active sessions.
- Reserve session slot atomically.
- Create session metadata.
- Set TTL.
- Add active-session index entry.

**Dependencies**

- M3.3, M2.6.

**Acceptance criteria**

- Two concurrent Free-user create requests produce one active session.
- `reuse_existing` returns same session.
- `create_new` returns limit error when full.
- Script failure does not leave incorrect active count.

---

### Task M3.5: Persist durable session metadata

**Goal**

Store session lifecycle evidence in DynamoDB.

**Functional requirements**

- Create durable session record on creation.
- Store entitlement snapshot.
- Store lifecycle timestamps.
- Support state updates.
- Support lookup by user and session.
- Support list sessions by user and state.

**Dependencies**

- M1.3, M3.4.

**Acceptance criteria**

- Created hot session has durable metadata record.
- State updates persist.
- Durable record does not override missing hot session as active.
- Tests cover durable lifecycle fields.

---

### Task M3.6: Implement session TTL refresh

**Goal**

Refresh session inactivity timer only after successful valid operations.

**Functional requirements**

- Update last activity timestamp.
- Update expiration timestamp.
- Refresh metadata TTL.
- Refresh session-local indexes and memory TTLs.
- Update active-session sorted-set score.
- Do not refresh on unauthorized or invalid requests.

**Dependencies**

- M3.2, M3.3.

**Acceptance criteria**

- Valid operation resets TTL to 10,800 seconds.
- Invalid request does not change TTL.
- Unauthorized request does not change TTL.
- Tests verify active-session ordering changes after refresh.

---

### Task M3.7: Implement session status API

**Goal**

Expose current session lifecycle state.

**Functional requirements**

- Add session status service.
- Return session state, limits, usage, TTL, and versions.
- Enforce ownership.
- Refresh TTL on valid status request.

**Dependencies**

- M3.5, M3.6.

**Acceptance criteria**

- Owner receives status.
- Non-owner receives authorization denial.
- Expired session returns expiry error.
- Valid status refreshes TTL.

---

### Task M3.8: Implement session termination

**Goal**

Allow explicit end of session.

**Functional requirements**

- Validate owner.
- Mark durable session terminated.
- Remove active-session index entry.
- Remove or invalidate hot session state.
- Update active count.
- Write audit event.

**Dependencies**

- M3.5, M3.6.

**Acceptance criteria**

- Terminated session cannot be used.
- Active session count decreases.
- Durable state is terminated.
- Audit event exists.

---

## 7. Milestone 4: Memory add and remove

### Task M4.1: Define memory entities

**Goal**

Create memory domain models.

**Functional requirements**

- Define memory ID generation.
- Define content type enum.
- Define memory states.
- Define metadata validation.
- Define provenance fields.
- Define duplicate fields.

**Dependencies**

- M0.4.

**Acceptance criteria**

- Invalid content type fails validation.
- Memory IDs use required prefix.
- State transitions are defined.
- Unit tests cover schema validation.

---

### Task M4.2: Implement token counting interface

**Goal**

Measure memory capacity consistently.

**Functional requirements**

- Define tokenizer provider interface.
- Implement local deterministic tokenizer for tests.
- Support configured production tokenizer.
- Return token count for content.
- Reject oversized input before expensive inference.

**Dependencies**

- M1.1.

**Acceptance criteria**

- Same input gives stable count.
- Oversized add request is rejected.
- Token count can be mocked in tests.
- API does not use whitespace count in production configuration.

---

### Task M4.3: Implement exact duplicate detection

**Goal**

Avoid storing repeated identical context.

**Functional requirements**

- Normalize content safely.
- Hash normalized content.
- Store content hash.
- Search same-session active content hash.
- Return canonical memory on duplicate.
- Refresh TTL for successful duplicate response.

**Dependencies**

- M3.6, M4.1.

**Acceptance criteria**

- Identical add request returns existing memory.
- Different whitespace behavior follows normalization policy.
- Code-content normalization does not destroy meaningful formatting.
- Duplicate does not increase token usage.

---

### Task M4.4: Implement embedding provider interface

**Goal**

Prepare online semantic retrieval.

**Functional requirements**

- Define `embed_text`.
- Define `embed_batch`.
- Return model version and vector dimension.
- Support mock provider.
- Support future SageMaker provider.
- Validate input and output dimensions.

**Dependencies**

- M1.4.

**Acceptance criteria**

- Mock provider works in tests.
- Provider errors map to controlled application errors.
- Model version is returned with vector.

---

### Task M4.5: Implement memory persistence in Valkey

**Goal**

Store active memory records.

**Functional requirements**

- Store memory document or hash.
- Apply same TTL as owning session.
- Add memory ID to session memory index.
- Store content hash, token count, state, metadata, source IDs.
- Store embedding metadata.

**Dependencies**

- M3.2, M4.1.

**Acceptance criteria**

- Memory expires with session.
- Memory belongs to correct user and session.
- Session index contains memory ID.
- Stored record includes required fields.

---

### Task M4.6: Implement atomic add-memory script

**Goal**

Enforce token budget and counters safely.

**Functional requirements**

- Validate session state.
- Verify token budget.
- Increment token usage.
- Increment memory count.
- Write memory.
- Update memory index.
- Refresh TTL.
- Return budget and usage details.

**Dependencies**

- M3.6, M4.5, M4.2.

**Acceptance criteria**

- Concurrent adds cannot exceed budget.
- Failed add leaves counters unchanged.
- Successful add updates counters and TTL.
- Test simulates concurrent near-limit adds.

---

### Task M4.7: Implement add-memory service

**Goal**

Combine validation, dedupe, embedding, persistence, and async trigger.

**Functional requirements**

- Validate ownership.
- Validate idempotency.
- Count tokens.
- Check exact duplicate.
- Generate embedding.
- Perform near-duplicate candidate lookup when available.
- Call atomic add script.
- Queue compaction at soft threshold.
- Write audit event.

**Dependencies**

- M4.3, M4.4, M4.6.

**Acceptance criteria**

- Valid add creates memory.
- Duplicate add returns canonical memory.
- Add over budget fails correctly.
- Soft threshold queues compaction.
- Session TTL refreshes.

---

### Task M4.8: Implement remove-memory service

**Goal**

Remove memory safely.

**Functional requirements**

- Validate ownership and session.
- Validate memory membership.
- Remove from retrieval index.
- Decrement token usage.
- Decrement memory count.
- Mark logical deletion where required.
- Queue rebuild if PageIndex depends on source.
- Refresh TTL.
- Audit action.

**Dependencies**

- M4.5, M4.6.

**Acceptance criteria**

- Removed memory is not retrievable.
- Counters decrease.
- Non-owner cannot remove.
- Source-dependent artifact rebuild can be queued.
- TTL refreshes.

---

## 8. Milestone 5: Retrieval MVP

### Task M5.1: Configure Valkey vector index

**Goal**

Enable session-local semantic retrieval.

**Functional requirements**

- Define vector index schema.
- Index user, session, state, content type, recency, importance, embedding.
- Confirm required filters.
- Create development index setup script.
- Version index definition.

**Dependencies**

- M4.5.

**Acceptance criteria**

- Vector query can filter by user and session.
- Deleted or superseded state can be excluded.
- Index setup is repeatable.
- Tests validate filter construction.

---

### Task M5.2: Implement near-duplicate candidate query

**Goal**

Identify semantically similar memory during add.

**Functional requirements**

- Query vector index within same session.
- Return bounded candidate count.
- Apply duplicate threshold.
- Apply merge-candidate threshold.
- Avoid cross-session candidates.

**Dependencies**

- M5.1, M4.4.

**Acceptance criteria**

- Similar memory returns as candidate.
- Different user memory never returns.
- Candidate count is bounded.
- Threshold behavior is configurable.

---

### Task M5.3: Implement vector-only retrieval service

**Goal**

Return top relevant context from one session.

**Functional requirements**

- Validate owner and active session.
- Embed query.
- Search bounded candidates.
- Apply content-type filters.
- Filter active state.
- Apply similarity threshold.
- Apply top-k entitlement limit.
- Apply response token cap.
- Refresh TTL.
- Return retrieval metadata.

**Dependencies**

- M5.1, M4.4, M3.6.

**Acceptance criteria**

- Query returns relevant session memory.
- Top-k cannot exceed plan limit.
- Empty result is valid.
- Cross-session retrieval is impossible.
- TTL refreshes after successful retrieval.

---

### Task M5.4: Implement retrieval response shaping

**Goal**

Keep returned context concise and useful.

**Functional requirements**

- Enforce max return tokens.
- Deduplicate same memory ID.
- Prefer active compacted summary over superseded sources.
- Preserve contradictory items where both are relevant.
- Return source type.

**Dependencies**

- M5.3.

**Acceptance criteria**

- Response token cap is respected.
- Duplicate candidates are collapsed.
- Contradictions are not silently removed.
- Returned results include required metadata.

---

### Task M5.5: Build retrieval fixture dataset

**Goal**

Create a quality baseline.

**Functional requirements**

- Add fixtures for preferences.
- Add task-state fixtures.
- Add code identifier fixtures.
- Add duplicates.
- Add contradictory records.
- Add expired and superseded items.
- Add expected relevant memory IDs.

**Dependencies**

- M5.3.

**Acceptance criteria**

- Dataset supports Recall@k, MRR, and nDCG tests.
- Fixtures run locally.
- Test scenarios include session isolation.

---

### Task M5.6: Add retrieval evaluation command

**Goal**

Measure retrieval changes before merge.

**Functional requirements**

- Load fixture dataset.
- Run vector-only retrieval.
- Calculate Recall@k.
- Calculate MRR.
- Calculate nDCG.
- Emit JSON report.
- Fail CI on configured regression.

**Dependencies**

- M5.5.

**Acceptance criteria**

- Command produces repeatable metrics.
- CI can run evaluation.
- Baseline thresholds are configurable.

---

## 9. Milestone 6: REST API

### Task M6.1: Create FastAPI application shell

**Goal**

Create API runtime.

**Functional requirements**

- Add versioned `/v1` router.
- Add health endpoint.
- Add readiness endpoint.
- Add correlation middleware.
- Add structured error middleware.
- Add authentication dependency.

**Dependencies**

- M2.1, M0.4.

**Acceptance criteria**

- `/v1/health` returns success.
- Invalid request returns standard error envelope.
- Correlation ID appears in response.

---

### Task M6.2: Implement resolve-session endpoint

**Goal**

Expose session create-or-get API.

**Functional requirements**

- Map request to M3.4.
- Support idempotency header.
- Return session response contract.
- Map entitlement errors correctly.

**Dependencies**

- M3.4, M3.5.

**Acceptance criteria**

- Endpoint passes API contract tests.
- Repeated key returns same response.
- Limit error maps to correct status.

---

### Task M6.3: Implement session-status endpoint

**Goal**

Expose status API.

**Functional requirements**

- Map to M3.7.
- Enforce owner.
- Refresh TTL.
- Return required lifecycle fields.

**Dependencies**

- M3.7.

**Acceptance criteria**

- Contract test passes.
- Non-owner denied.
- Expired session returns correct status.

---

### Task M6.4: Implement add-memory endpoint

**Goal**

Expose context ingestion API.

**Functional requirements**

- Map to M4.7.
- Require idempotency header.
- Validate request schema.
- Return created or duplicate response.

**Dependencies**

- M4.7.

**Acceptance criteria**

- Contract test passes.
- Duplicate response returns 200.
- New memory returns 201.
- Budget error maps correctly.

---

### Task M6.5: Implement retrieve endpoint

**Goal**

Expose low-latency retrieval API.

**Functional requirements**

- Map to M5.3 and M5.4.
- Validate retrieval parameters.
- Enforce plan feature gates.
- Return bounded results.

**Dependencies**

- M5.4.

**Acceptance criteria**

- Contract test passes.
- Top-k respects plan.
- Empty result returns 200.
- Unauthorized request denied.

---

### Task M6.6: Implement remove endpoint

**Goal**

Expose memory deletion API.

**Functional requirements**

- Map to M4.8.
- Return removal result.
- Map missing memory and ownership errors.

**Dependencies**

- M4.8.

**Acceptance criteria**

- Contract test passes.
- Removed item disappears from retrieval.
- Counters update correctly.

---

### Task M6.7: Implement compact endpoint and job-status endpoint

**Goal**

Expose async compaction control.

**Functional requirements**

- Queue compaction.
- Return 202.
- Add visible job-status endpoint.
- Enforce feature gate.
- Return job ownership-safe status.

**Dependencies**

- M8.1, M8.2.

**Acceptance criteria**

- Compaction request returns quickly.
- Job record is available.
- Unauthorized job lookup fails.
- Duplicate compaction is handled.

---

## 10. Milestone 7: MCP connector

### Task M7.1: Create MCP server shell

**Goal**

Create MCP service with local stdio transport.

**Functional requirements**

- Register MCP server.
- Register tool catalog.
- Add local configuration.
- Add shared authentication adapter.
- Map errors to MCP result format.

**Dependencies**

- M6.1.

**Acceptance criteria**

- Local MCP inspector can list tools.
- Tools expose schemas.
- Invalid input returns structured error.

---

### Task M7.2: Implement memory session tools

**Goal**

Expose session operations through MCP.

**Functional requirements**

- Implement `memory_create_or_get_session`.
- Implement `memory_get_session_status`.
- Implement `memory_terminate_session`.
- Map to API service or shared domain layer.

**Dependencies**

- M6.2, M6.3.

**Acceptance criteria**

- Tools match MCP spec.
- Tool behavior matches REST contract.
- Local integration test succeeds.

---

### Task M7.3: Implement memory context tools

**Goal**

Expose add, get, remove, and compact through MCP.

**Functional requirements**

- Implement `memory_add`.
- Implement `memory_get`.
- Implement `memory_remove`.
- Implement `memory_compact`.
- Return structured content.
- Preserve tool annotations.

**Dependencies**

- M6.4, M6.5, M6.6, M6.7.

**Acceptance criteria**

- Tools are callable from MCP client.
- Results are machine-readable.
- Destructive tools are correctly annotated.
- Error codes are stable.

---

### Task M7.4: Add remote Streamable HTTP MCP transport

**Goal**

Deploy remote MCP service through AWS.

**Functional requirements**

- Add HTTP transport.
- Validate remote bearer tokens.
- Support API Gateway routing.
- Add health checks.
- Add transport integration tests.

**Dependencies**

- M7.3, M6.1.

**Acceptance criteria**

- Remote MCP client can connect over HTTPS.
- Authentication works.
- Tool calls complete through deployed service.
- No session state depends on transport connection ID.

---

## 11. Milestone 8: Background compaction

### Task M8.1: Create SQS FIFO queue and job repository

**Goal**

Support durable asynchronous work.

**Functional requirements**

- Create job entity.
- Create enqueue service.
- Write job record before enqueue.
- Include session ID message group.
- Include deduplication ID.
- Create DLQ configuration.

**Dependencies**

- M1.3, M3.5.

**Acceptance criteria**

- Job can be enqueued.
- Job appears in DynamoDB.
- Duplicate enqueue is suppressed.
- Queue message includes correct group ID.

---

### Task M8.2: Create worker service shell

**Goal**

Consume jobs safely.

**Functional requirements**

- Poll SQS.
- Validate message schema.
- Load job record.
- Mark running.
- Emit logs and metrics.
- Support graceful shutdown.
- Support retryable and permanent failures.

**Dependencies**

- M8.1.

**Acceptance criteria**

- Worker processes test job.
- Invalid job is marked failed.
- Retryable error leaves message for retry.
- Logs contain job and correlation IDs.

---

### Task M8.3: Implement compaction lock

**Goal**

Prevent concurrent compaction for one session.

**Functional requirements**

- Acquire Valkey lock by user and session.
- Use job ID ownership.
- Use bounded lease.
- Release only by owner.
- Handle lock contention.

**Dependencies**

- M1.2, M8.2.

**Acceptance criteria**

- Second concurrent compaction does not run.
- Expired lock can be recovered.
- Lock release does not remove another job’s lock.

---

### Task M8.4: Implement compaction candidate selection

**Goal**

Choose memory sets worth compacting.

**Functional requirements**

- Select near duplicates.
- Select old repetitive task states.
- Respect active state.
- Respect token budget pressure.
- Bound input token count.
- Preserve candidate source IDs.

**Dependencies**

- M5.2, M8.3.

**Acceptance criteria**

- Candidate set is bounded.
- Superseded and deleted memory excluded.
- Candidate set includes source IDs.
- Tests cover conflicting content.

---

### Task M8.5: Implement compaction model adapter

**Goal**

Abstract compaction inference.

**Functional requirements**

- Define compactor interface.
- Implement deterministic local test compactor.
- Add future SageMaker adapter.
- Validate source IDs and output shape.
- Return contradiction flags.

**Dependencies**

- M8.4.

**Acceptance criteria**

- Local compaction test creates valid summary.
- Invalid output rejected.
- Model errors map to retryable or permanent job error.

---

### Task M8.6: Implement atomic compaction commit

**Goal**

Safely write summary and supersede sources.

**Functional requirements**

- Compare memory version.
- Create compacted summary.
- Mark sources superseded.
- Update token usage.
- Update memory count according to policy.
- Update vector index.
- Increment memory version.
- Queue PageIndex rebuild if needed.

**Dependencies**

- M8.5, M4.6.

**Acceptance criteria**

- Summary has provenance.
- Source memory no longer returns normally.
- Token usage reflects summary replacement.
- Stale worker cannot overwrite newer memory changes.

---

## 12. Milestone 9: SageMaker embedding endpoint

### Task M9.1: Create embedding container

**Goal**

Package online embedding model.

**Functional requirements**

- Create container Dockerfile.
- Define inference handler.
- Define health behavior.
- Define input and output schema.
- Pin model and tokenizer version.
- Emit safe structured logs.

**Dependencies**

- M4.4.

**Acceptance criteria**

- Container runs locally.
- Test request returns expected vector shape.
- Invalid payload returns controlled error.

---

### Task M9.2: Provision ECR and SageMaker embedding resources

**Goal**

Deploy embedding inference infrastructure.

**Functional requirements**

- Create ECR repository.
- Create SageMaker model.
- Create endpoint configuration.
- Create endpoint.
- Create IAM role.
- Add CloudWatch alarms.

**Dependencies**

- Terraform foundation tasks.

**Acceptance criteria**

- Endpoint is reachable from API service.
- Endpoint invocation succeeds.
- IAM prevents unauthorized invocation.

---

### Task M9.3: Implement SageMaker embedding provider

**Goal**

Use deployed embedding endpoint in API.

**Functional requirements**

- Implement request client with pooling.
- Add timeout and circuit breaker.
- Map endpoint errors.
- Include model version.
- Support config switch from mock provider.

**Dependencies**

- M9.2, M4.4.

**Acceptance criteria**

- API can add and retrieve using SageMaker embeddings.
- Timeout returns controlled retryable error.
- Metrics capture endpoint latency.

---

## 13. Milestone 10: Hybrid retrieval and reranking

### Task M10.1: Add lexical retrieval signal

**Goal**

Improve exact technical identifier retrieval.

**Functional requirements**

- Add filtered lexical query.
- Support code identifiers and file paths.
- Merge with dense candidates.
- Keep candidate count bounded.

**Dependencies**

- M5.3.

**Acceptance criteria**

- Exact identifier query retrieves expected memory.
- Session filters remain mandatory.
- Latency remains within target.

---

### Task M10.2: Create reranker adapter

**Goal**

Add optional relevance refinement.

**Functional requirements**

- Define reranker interface.
- Add local mock reranker.
- Support feature gate.
- Bound candidates.
- Add fallback behavior.

**Dependencies**

- M5.3, M2.5.

**Acceptance criteria**

- Disabled plan never calls reranker.
- Reranker failure falls back.
- Output affects final ordering in tests.

---

### Task M10.3: Deploy SageMaker reranker

**Goal**

Host reranker model.

**Functional requirements**

- Build container or package model.
- Add model registry entry.
- Provision endpoint.
- Add health and performance metrics.
- Add rollout gate.

**Dependencies**

- M9.2, M10.2.

**Acceptance criteria**

- Endpoint can score bounded candidates.
- API uses endpoint when enabled.
- Latency and fallback metrics exist.

---

### Task M10.4: Implement score fusion

**Goal**

Combine dense, lexical, PageIndex, reranker, recency, and importance scores.

**Functional requirements**

- Normalize scores.
- Configure weights.
- Produce final score.
- Preserve source origin.
- Add test fixtures.

**Dependencies**

- M10.1, M10.2.

**Acceptance criteria**

- Fusion is deterministic.
- Weight configuration changes ranking predictably.
- Raw incompatible scores are not combined directly.

---

## 14. Milestone 11: PageIndex

### Task M11.1: Define PageIndex artifact schema

**Goal**

Create versioned structured retrieval artifacts.

**Functional requirements**

- Define artifact metadata.
- Define S3 path layout.
- Include session ID, memory version, tree version.
- Include source memory IDs.
- Include builder and model version.
- Define stale state.

**Dependencies**

- M8.6.

**Acceptance criteria**

- Artifact schema validates.
- S3 path includes pseudonymous user partition.
- Staleness can be detected.

---

### Task M11.2: Implement PageIndex worker adapter

**Goal**

Build structured context trees asynchronously.

**Functional requirements**

- Load source memory bundle.
- Build hierarchy.
- Write artifact to S3.
- Update Valkey metadata pointer.
- Update durable tree version.
- Handle stale-memory cancellation.

**Dependencies**

- M11.1, M8.2.

**Acceptance criteria**

- Worker writes artifact.
- API can detect available artifact.
- Rebuild does not block vector retrieval.
- Stale job cancels safely.

---

### Task M11.3: Add hybrid retrieval candidate source

**Goal**

Use PageIndex artifacts in eligible retrieval.

**Functional requirements**

- Check entitlement flag.
- Check artifact freshness.
- Load bounded structured candidates.
- Merge candidates with dense pool.
- Fall back to vector-only when unavailable.

**Dependencies**

- M11.2, M10.4.

**Acceptance criteria**

- Hybrid mode uses PageIndex only when enabled.
- S3 or artifact failure falls back.
- Stale artifacts follow policy.
- Retrieval diagnostics report source.

---

## 15. Milestone 12: SageMaker compaction and TurboQuant experiment

### Task M12.1: Deploy compactor endpoint

**Goal**

Move compaction inference from local adapter to SageMaker.

**Functional requirements**

- Build compactor container.
- Define input/output contract.
- Register model version.
- Provision endpoint.
- Configure worker permissions.
- Add metrics.

**Dependencies**

- M8.5, M9.2.

**Acceptance criteria**

- Worker can call compactor endpoint.
- Output validation works.
- Failures retry through job queue.

---

### Task M12.2: Benchmark long-context compaction

**Goal**

Establish baseline quality and cost.

**Functional requirements**

- Create compaction benchmark set.
- Measure input tokens.
- Measure output tokens.
- Measure factual retention.
- Measure contradiction preservation.
- Measure latency and cost.

**Dependencies**

- M12.1.

**Acceptance criteria**

- Benchmark report exists.
- Baseline model behavior is documented.
- CI or scheduled evaluation can run.

---

### Task M12.3: TurboQuant experiment

**Goal**

Evaluate KV-cache optimization for long-context compaction.

**Functional requirements**

- Build experimental GPU container.
- Keep experiment feature-flagged.
- Compare baseline and TurboQuant.
- Measure GPU memory.
- Measure throughput.
- Measure quality regression.
- Keep disabled by default.

**Dependencies**

- M12.2.

**Acceptance criteria**

- Benchmark compares baseline and experimental mode.
- Results include factual retention and contradiction behavior.
- No core session or retrieval logic depends on TurboQuant.
- Production enablement requires explicit decision record.

---

## 16. Milestone 13: Security and operations

### Task M13.1: Implement structured logging and correlation IDs

**Goal**

Make requests traceable.

**Functional requirements**

- Add correlation middleware.
- Add JSON logs.
- Hash user and session IDs.
- Exclude raw context.
- Propagate correlation ID to jobs and inference.

**Dependencies**

- M6.1, M8.2.

**Acceptance criteria**

- API and worker logs include correlation ID.
- Raw context is absent from default logs.
- Trace can connect API request to job.

---

### Task M13.2: Add metrics and dashboards

**Goal**

Monitor service health.

**Functional requirements**

- Emit API latency metrics.
- Emit retrieval metrics.
- Emit queue metrics.
- Emit Valkey metrics.
- Emit SageMaker metrics.
- Create initial CloudWatch dashboard.

**Dependencies**

- M13.1.

**Acceptance criteria**

- Dashboard displays API, retrieval, queue, and dependency health.
- Metrics can be filtered by operation.
- p95 latency is visible.

---

### Task M13.3: Add alarms and runbooks

**Goal**

Detect critical failures early.

**Functional requirements**

- Add API error alarm.
- Add Valkey eviction alarm.
- Add DLQ alarm.
- Add embedding endpoint alarm.
- Add latency breach alarm.
- Document operator runbooks.

**Dependencies**

- M13.2.

**Acceptance criteria**

- Test alarm paths exist.
- Runbook exists for each critical alarm.
- Operators can identify responsible component.

---

### Task M13.4: Implement security hardening

**Goal**

Apply production security baseline.

**Functional requirements**

- Add Cognito JWT validation.
- Add WAF rules.
- Add IAM least privilege.
- Add Secrets Manager references.
- Add encryption configuration.
- Add request-size limits.
- Add rate limiting.
- Add audit events.

**Dependencies**

- Core API and Terraform modules.

**Acceptance criteria**

- Unauthorized access tests pass.
- Secrets are not in source code.
- Data stores are private.
- Security scans run in CI.

---

## 17. Milestone 14: Release readiness

### Task M14.1: Add end-to-end environment test

**Goal**

Validate deployed system behavior.

**Functional requirements**

- Create test user and entitlement fixture.
- Resolve session.
- Add memory.
- Retrieve memory.
- Remove memory.
- Queue compaction.
- Verify job state.
- Terminate session.
- Verify expiration behavior.

**Dependencies**

- All core milestones.

**Acceptance criteria**

- End-to-end test runs in dev.
- Test validates user isolation.
- Test output is readable in CI.

---

### Task M14.2: Add load test suite

**Goal**

Validate performance targets.

**Functional requirements**

- Repeated MCP retrieval load.
- Concurrent session creation.
- Add near token limit.
- Vector-only retrieval.
- Hybrid retrieval.
- Reranker outage.
- Queue backlog.
- Rate-limit burst.

**Dependencies**

- M13.2.

**Acceptance criteria**

- p95 reports generated.
- Bottlenecks are documented.
- Load tests can run against stage.

---

### Task M14.3: Production readiness review

**Goal**

Verify requirements before production deployment.

**Functional requirements**

- Review security controls.
- Review backups and retention.
- Review alarms.
- Review rollback.
- Review Terraform state access.
- Review branch protection.
- Review model quality metrics.
- Review cost guardrails.

**Dependencies**

- M14.1, M14.2.

**Acceptance criteria**

- Release checklist is completed.
- Open risks are recorded.
- Production approval is documented.

---

## 18. Suggested first implementation sequence

Implement in this exact practical order:

```text
1. M0.1 through M0.4
2. M1.1 through M1.4
3. M2.1 through M2.6
4. M3.1 through M3.8
5. M4.1 through M4.8
6. M5.1 through M5.6
7. M6.1 through M6.7
8. M7.1 through M7.4
9. M8.1 through M8.6
10. M9.1 through M9.3
11. M10.1 through M10.4
12. M11.1 through M11.3
13. M12.1 through M12.3
14. M13.1 through M13.4
15. M14.1 through M14.3
```

---

## 19. MVP cut line

A usable MVP includes:

- M0 through M7.
- M8.1 and M8.2 only for job infrastructure.
- M9 embedding endpoint or mock embedding provider.
- M13.1 basic logs.

The MVP does not require:

- PageIndex.
- Reranking.
- SageMaker compactor.
- TurboQuant.
- Production multi-AZ high availability.
- Full production cost optimization.

The first high-value demo should show:

```text
MCP client
    -> create or reuse session
    -> add context
    -> retrieve relevant top-3 context
    -> enforce plan session limit
    -> expire after inactivity
```

---

## 20. Acceptance criteria for task execution

The implementation backlog is complete when:

1. Every task has a clear goal.
2. Every task lists dependencies.
3. Every task has testable acceptance criteria.
4. The first MVP cut line is clear.
5. Feature branches can be mapped to task IDs.
6. Work can progress sequentially without requiring the entire platform to be built first.
