# Delivery Plan

## 1. Purpose

This document defines the delivery plan for MemoryRepo.

The plan moves from a local implementation baseline to a deployable AWS service in controlled phases. Each phase has a defined objective, deliverables, validation criteria, and release decision.

The plan intentionally prioritizes:

1. Session correctness.
2. User isolation.
3. Low-latency vector retrieval.
4. MCP usability.
5. Operational safety.
6. Advanced retrieval and model optimization only after the baseline works.

---

## 2. Delivery principles

MemoryRepo delivery must follow these principles:

- Build the smallest working vertical slice first.
- Keep active session state simple and correct before adding advanced retrieval.
- Do not introduce PageIndex, reranking, or TurboQuant before vector-only retrieval is measurable.
- Keep all expensive work asynchronous.
- Use feature flags for optional capabilities.
- Deploy to `dev` continuously.
- Promote from `dev` to `main` only through reviewed release PRs.
- Treat model changes as separate production risks from API changes.
- Prefer a working observable baseline over a broad but untestable architecture.

---

## 3. Release phases

| Phase | Name | Main outcome |
|---|---|---|
| 0 | Foundation | Repository, branching, CI checks, local runtime. |
| 1 | Session Core | Entitlements, active sessions, TTL lifecycle. |
| 2 | Memory Core | Add, remove, token budgets, duplicate control. |
| 3 | Retrieval MVP | Vector-only retrieval and evaluation fixtures. |
| 4 | API and MCP MVP | REST API and MCP connector. |
| 5 | AWS Development Deployment | Terraform-managed dev environment. |
| 6 | Async Compaction | SQS, worker, compaction workflow. |
| 7 | SageMaker Inference | Real embedding endpoint and optional reranker. |
| 8 | Hybrid Retrieval | PageIndex and score fusion. |
| 9 | Production Readiness | Security, observability, load testing, rollback. |
| 10 | Advanced Optimization | TurboQuant experiment and cost tuning. |

---

## 4. Phase 0: Foundation

## Objective

Create a stable repository and local development workflow.

## Deliverables

- Repository structure.
- `dev` and `main` branch protection.
- Feature branch naming and squash-merge workflow.
- GitHub Actions pull-request checks.
- Shared Python package.
- Local Valkey runtime.
- Local test configuration.
- Mock embedding provider.
- Documentation skeleton.

## Required proof

```text
A developer can clone the repository,
start local dependencies,
run tests,
and open a feature PR that triggers required checks.
```

## Exit criteria

- CI runs on pull requests.
- Local Valkey starts successfully.
- Unit tests execute without production AWS access.
- Feature branch can squash-merge into `dev`.
- Push to `dev` triggers development workflow.

---

## 5. Phase 1: Session Core

## Objective

Implement user entitlement resolution and active session lifecycle.

## Deliverables

- User repository.
- Plan repository.
- Entitlement repository.
- Effective entitlement resolution.
- Free-plan default behavior.
- Session state machine.
- Valkey session metadata.
- Active-session index.
- Atomic create-or-get session flow.
- Three-hour sliding TTL.
- Durable session metadata.
- Session termination.

## Required proof

```text
Free user:
    can create one active session
    cannot create a second active session

Premium user:
    can create up to configured limit

Any active session:
    expires after inactivity timeout
    refreshes TTL after valid session activity
```

## Exit criteria

- Concurrent create requests cannot exceed limits.
- Ownership checks work.
- Expired sessions cannot be reused.
- Durable session records exist.
- Session lifecycle tests pass.

---

## 6. Phase 2: Memory Core

## Objective

Add bounded session memory operations.

## Deliverables

- Memory entity and schema.
- Content-type validation.
- Token counting interface.
- Exact duplicate detection.
- Memory persistence in Valkey.
- Atomic add-memory operation.
- Token-budget enforcement.
- Remove-memory operation.
- Session counter updates.
- Add and remove audit events.

## Required proof

```text
User can add memory to active session.
Duplicate memory does not increase token usage.
Memory over budget is rejected.
Removed memory no longer appears in active store.
```

## Exit criteria

- Token accounting remains correct under concurrent add requests.
- Add and remove refresh session TTL.
- Removed memory reduces token count.
- Cross-session memory access is denied.
- Memory unit tests pass.

---

## 7. Phase 3: Retrieval MVP

## Objective

Provide low-latency vector-only retrieval.

## Deliverables

- Valkey vector-index configuration.
- Query embedding interface.
- Session-filtered vector search.
- Metadata and content-type filters.
- Similarity threshold.
- Entitlement-limited top-k.
- Response token cap.
- Retrieval response shaping.
- Evaluation fixtures.
- Recall@k, MRR, and nDCG command.

## Required proof

```text
Given a session with context:
    query returns relevant top-k context
    unrelated context is filtered
    results never cross user or session boundaries
```

## Exit criteria

- Vector-only retrieval p95 meets initial target in local or dev test.
- Empty retrieval returns valid response.
- Retrieval fixtures establish quality baseline.
- Candidate count is bounded.
- Retrieval evaluation runs in CI.

---

## 8. Phase 4: API and MCP MVP

## Objective

Expose the memory service through REST and MCP.

## Deliverables

- FastAPI service.
- Versioned `/v1` routes.
- Error envelope.
- Correlation ID middleware.
- Session endpoints.
- Add, retrieve, remove, compact queue endpoints.
- MCP stdio server.
- MCP memory tools.
- MCP contract tests.
- Local MCP client or inspector validation.

## Required proof

```text
An MCP client can:
    resolve a session
    add context
    retrieve top-3 context
    remove context
    request compaction
```

## Exit criteria

- REST API contract tests pass.
- MCP tools match declared schemas.
- Authentication adapter is applied consistently.
- MCP transport does not own session state.
- Basic demo works locally.

---

## 9. Phase 5: AWS Development Deployment

## Objective

Deploy the vector-only MVP to AWS development environment using Terraform.

## Deliverables

- Terraform state backend.
- GitHub OIDC roles.
- VPC and security groups.
- ECR repositories.
- ECS cluster.
- API service.
- MCP service.
- Valkey.
- DynamoDB tables.
- S3 artifact bucket.
- API Gateway.
- Cognito.
- Basic CloudWatch logs and alarms.
- GitHub Actions auto-deploy from `dev`.

## Required proof

```text
Push to dev:
    runs CI
    builds immutable images
    pushes to ECR
    applies approved dev Terraform changes
    deploys API and MCP services
    runs smoke tests
```

## Exit criteria

- Dev environment is Terraform-created.
- API and MCP reachability tests pass.
- Valkey is private.
- Authenticated dev user can complete memory lifecycle.
- Deployment has rollback target.

---

## 10. Phase 6: Async Compaction

## Objective

Add safe background compaction and job lifecycle.

## Deliverables

- SQS FIFO queue and DLQ.
- Job records in DynamoDB.
- Worker ECS service.
- Compaction lock.
- Candidate selection.
- Local compactor adapter.
- Atomic compaction commit.
- PageIndex rebuild job skeleton.
- Job status endpoint.
- Queue and worker metrics.

## Required proof

```text
Memory nearing budget:
    queues compaction
    API returns immediately
    worker compacts eligible memory
    source provenance is preserved
```

## Exit criteria

- Compaction does not block add or retrieve.
- Duplicate SQS delivery is safe.
- Stale job cannot overwrite newer user memory.
- DLQ alarm exists.
- Job status is visible to owner.

---

## 11. Phase 7: SageMaker Inference

## Objective

Replace local embedding and compaction adapters with deployable SageMaker endpoints.

## Deliverables

- Embedding container.
- ECR model image.
- SageMaker embedding endpoint.
- API embedding provider.
- Model version metadata.
- Endpoint metrics and alarms.
- Optional reranker container and endpoint.
- Optional SageMaker compactor endpoint.
- Model registry process.

## Required proof

```text
API add and get use SageMaker embedding endpoint.
Embedding failures return controlled retryable errors.
Model version is recorded with memory vectors.
```

## Exit criteria

- Embedding endpoint latency is measured.
- Vector retrieval quality is compared to local baseline.
- Endpoint fallback behavior works.
- Model deployment has approval and rollback process.

---

## 12. Phase 8: Hybrid Retrieval

## Objective

Add PageIndex and hybrid ranking for long-form context.

## Deliverables

- PageIndex artifact schema.
- S3 artifact lifecycle.
- Worker-based PageIndex build.
- Artifact metadata pointer in Valkey.
- Structured candidate retrieval.
- Lexical retrieval signal.
- Score fusion.
- Optional reranker integration.
- Hybrid evaluation suite.

## Required proof

```text
Long-form session:
    vector-only provides baseline results
    hybrid retrieval adds relevant structured context
    failure of structured retrieval falls back to vector-only
```

## Exit criteria

- PageIndex build is asynchronous.
- Hybrid mode is feature-gated.
- Artifact freshness is checked.
- Quality lift is measured.
- Latency remains within configured hybrid budget.

---

## 13. Phase 9: Production Readiness

## Objective

Make the system safe and operable for production.

## Deliverables

- Production Terraform environment.
- Protected GitHub production environment.
- WAF rules.
- Final Cognito configuration.
- Least-privilege IAM review.
- Encryption verification.
- Rate limits.
- CloudWatch dashboards.
- Critical alarms.
- Runbooks.
- Load tests.
- Security tests.
- Rollback workflow.
- Retention policy implementation.
- Production release checklist.

## Required proof

```text
A production release:
    is reviewed
    has approved Terraform plan
    uses immutable image digests
    passes smoke tests
    can be rolled back
    is monitored after deployment
```

## Exit criteria

- Security test suite passes.
- Load tests meet baseline SLOs.
- Alarms and runbooks are tested.
- Production deployment approval process is active.
- Data retention behavior is documented and verified.

---

## 14. Phase 10: Advanced Optimization

## Objective

Optimize expensive long-context workloads only after baseline quality and reliability are proven.

## Deliverables

- Long-context compaction benchmark.
- Cost benchmark.
- TurboQuant experiment container.
- GPU memory analysis.
- Quality regression analysis.
- Feature flag.
- Architecture decision record.

## Required proof

```text
TurboQuant experiment:
    reduces GPU memory or improves throughput
    without unacceptable compaction quality loss
    and does not affect core session correctness
```

## Exit criteria

- Baseline and experiment comparison exists.
- Factual retention is measured.
- Contradiction handling is measured.
- Experiment remains disabled unless approved.
- Production activation has explicit decision record.

---

## 15. MVP definition

The MVP is complete when MemoryRepo can demonstrate:

```text
Authenticated user
    -> resolves one active session
    -> plan limit is enforced
    -> adds context
    -> retrieves relevant top-3 context
    -> removes context
    -> session expires after three hours of inactivity
    -> accesses tools through MCP
```

MVP infrastructure may use:

- Development AWS environment.
- Vector-only retrieval.
- Mock or small embedding provider before full SageMaker optimization.
- Basic observability.
- Manual plan seed data.

MVP does not require:

- PageIndex.
- Reranking.
- SageMaker compactor.
- TurboQuant.
- Multi-region deployment.
- Consumer billing integration.
- Full administrative UI.

---

## 16. Milestone release gates

| Gate | Required before next phase |
|---|---|
| Foundation gate | CI, branch protection, local runtime work. |
| Session gate | Limits, TTL, ownership, concurrency tests pass. |
| Memory gate | Token accounting and add/remove tests pass. |
| Retrieval gate | Vector evaluation baseline and isolation tests pass. |
| MCP gate | Local tool workflow passes. |
| Dev deployment gate | Terraform deployment and smoke tests pass. |
| Async gate | Job idempotency, DLQ, and stale-work tests pass. |
| Model gate | Endpoint latency and quality benchmark pass. |
| Hybrid gate | Measured retrieval lift and safe fallback pass. |
| Production gate | Security, load, rollback, alarms, and approval complete. |

---

## 17. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Vector search latency too high | MCP experience degrades. | Keep candidate sets bounded, optimize embeddings, use vector-only fallback. |
| Session creation race condition | Plan limits violated. | Atomic Valkey scripts and concurrency tests. |
| Valkey eviction | Active sessions disappear early. | Capacity alarms, TTL policy, no-eviction sizing. |
| Embedding endpoint outage | Add and get requests fail. | Circuit breakers, controlled errors, repair jobs. |
| Compaction loses facts | Retrieval quality degrades. | Provenance, evaluation fixtures, model validation. |
| PageIndex adds too much latency | Hybrid mode unusable. | Asynchronous build, bounded candidate lookup, feature gating. |
| Branch workflow bypass | Unreviewed production changes. | Branch protection and GitHub environment approval. |
| Terraform state exposure | Infrastructure/security risk. | Encrypted state, least-privilege roles, OIDC. |
| Cost growth | Project becomes expensive. | Dev sizing, endpoint autoscaling, feature gates, cost dashboard. |
| Cross-tenant retrieval | Critical security incident. | Mandatory filters, authorization tests, audit alarms. |

---

## 18. Recommended demo sequence

A strong portfolio demo should show:

1. User authenticates.
2. API resolves a session based on Free or Premium entitlement.
3. Free plan is blocked from a second active session.
4. User adds coding-task context.
5. User retrieves top relevant context through MCP.
6. User removes a memory item.
7. API shows updated token usage.
8. Compaction request queues asynchronously.
9. Worker completes compaction.
10. Session expires after configured inactivity in a shortened dev test.
11. GitHub Actions deploys the change from `dev`.

---

## 19. Release checklist

Before promoting `dev` to `main`, verify:

- [ ] All required CI checks passed.
- [ ] API and MCP smoke tests passed in dev.
- [ ] Terraform plan reviewed.
- [ ] No critical security scan findings.
- [ ] No unapproved retrieval-quality regression.
- [ ] No unapproved latency regression.
- [ ] Rollback target identified.
- [ ] Model changes reviewed separately.
- [ ] Changelog or release summary prepared.
- [ ] Production environment approval obtained.

---

## 20. Acceptance criteria

This delivery plan is complete when:

1. Releases are organized into progressive phases.
2. MVP scope is explicit.
3. Advanced capabilities are deferred until baseline functionality works.
4. Each phase has measurable exit criteria.
5. Release gates prevent unsafe promotion.
6. Risks have named mitigations.
7. The project can be demoed meaningfully before PageIndex, reranking, or TurboQuant are complete.
