# Mermaid Architecture Diagrams

## 1. Purpose

This document contains the primary Mermaid diagrams for MemoryRepo.

These diagrams are intended to be reused in the README, architecture reviews, implementation planning, and future deployment documentation.

---

## 2. System context

```mermaid
flowchart LR
    User[Authenticated User]
    IDE[VS Code / Cursor-style IDE]
    Agent[LangChain / LangGraph / Custom Agent]
    Host[MCP Host]

    User --> IDE
    User --> Agent
    IDE --> Host
    Agent --> Host
    Host --> MemoryRepo[MemoryRepo MCP Connector]
    IDE --> MemoryRepo
    Agent --> MemoryRepo
```

---

## 3. Core AWS architecture

```mermaid
flowchart TB
    Client[MCP Client / IDE / Agent / REST Client]
    WAF[AWS WAF]
    Cognito[Amazon Cognito]
    APIGW[API Gateway HTTP API]
    VPCL[VPC Link]
    ALB[Internal Application Load Balancer]

    subgraph VPC[AWS VPC]
        subgraph ECS[ECS Fargate]
            API[MemoryRepo API Service]
            MCP[MemoryRepo MCP Service]
            Worker[Async Worker Service]
        end

        Valkey[ElastiCache for Valkey]
        SQS[SQS FIFO Queue]
        DDB[DynamoDB]
        SageMaker[SageMaker AI Endpoints]
        S3[S3 Artifact Buckets]
        Secrets[Secrets Manager]
    end

    Client --> WAF
    WAF --> APIGW
    Client --> Cognito
    Cognito --> APIGW

    APIGW --> VPCL
    VPCL --> ALB
    ALB --> API
    ALB --> MCP

    MCP --> API
    API --> Valkey
    API --> DDB
    API --> SageMaker
    API --> SQS
    API --> S3
    API --> Secrets

    SQS --> Worker
    Worker --> Valkey
    Worker --> DDB
    Worker --> SageMaker
    Worker --> S3
    Worker --> Secrets
```

---

## 4. Service responsibility boundaries

```mermaid
flowchart LR
    MCP[MCP Service]
    API[API Service]
    Worker[Worker Service]
    Embeddings[Embedding Endpoint]
    Reranker[Reranker Endpoint]
    Compactor[Compactor Endpoint]
    Valkey[Valkey]
    DDB[DynamoDB]
    S3[S3]

    MCP -->|MCP tool mapping| API

    API -->|hot session state| Valkey
    API -->|plans, entitlements, audit| DDB
    API -->|query and content embeddings| Embeddings
    API -->|bounded candidates| Reranker
    API -->|enqueue| Worker

    Worker -->|compaction requests| Compactor
    Worker -->|PageIndex artifacts| S3
    Worker -->|memory mutations| Valkey
    Worker -->|jobs and audit| DDB
```

---

## 5. Session lifecycle

```mermaid
stateDiagram-v2
    [*] --> creating

    creating --> active: entitlement and persistence succeed
    creating --> creation_failed: validation or persistence fails

    active --> active: valid operation refreshes TTL
    active --> entitlement_over_limit: plan downgrade
    entitlement_over_limit --> active: active count returns within limit

    active --> expired: inactivity TTL reaches zero
    entitlement_over_limit --> expired: inactivity TTL reaches zero

    active --> disabled: explicit disable
    entitlement_over_limit --> disabled: explicit disable

    active --> terminated: explicit termination
    entitlement_over_limit --> terminated: explicit termination

    active --> entitlement_deactivated: strict downgrade
    entitlement_over_limit --> entitlement_deactivated: strict downgrade

    expired --> deleted: retention cleanup
    disabled --> deleted: retention cleanup
    terminated --> deleted: retention cleanup
    entitlement_deactivated --> deleted: retention cleanup

    deleted --> [*]
    creation_failed --> [*]
```

---

## 6. Entitlement resolution and session creation

```mermaid
sequenceDiagram
    participant C as Client / MCP Host
    participant A as MemoryRepo API
    participant V as Valkey
    participant D as DynamoDB

    C->>A: create_or_get_session(mode)
    A->>V: resolve cached entitlement

    alt cache miss
        A->>D: load user entitlement
        D-->>A: plan + overrides
        A->>V: cache effective entitlement
    end

    A->>V: atomically inspect active session count

    alt reuse_existing and active session exists
        A->>V: return most recently active session
        A-->>C: existing session
    else creation allowed
        A->>V: reserve active-session slot
        A->>V: create session metadata and TTL
        A->>D: persist durable session record
        A-->>C: new session
    else plan limit reached
        A-->>C: ACTIVE_SESSION_LIMIT_REACHED
    end
```

---

## 7. Add-context sequence

```mermaid
sequenceDiagram
    participant C as Client / MCP Host
    participant A as API Service
    participant V as Valkey
    participant E as SageMaker Embeddings
    participant Q as SQS FIFO
    participant D as DynamoDB

    C->>A: memory_add(session_id, content)
    A->>V: validate session ownership and state
    A->>V: check idempotency key
    A->>E: generate embedding
    E-->>A: embedding vector
    A->>V: exact and near-duplicate checks
    A->>V: atomically enforce budget and write memory
    A->>V: refresh TTL

    opt soft token threshold crossed
        A->>Q: enqueue compaction
    end

    A->>D: record durable audit summary
    A-->>C: created or duplicate result
```

---

## 8. Retrieve-context sequence

```mermaid
sequenceDiagram
    participant C as Client / MCP Host
    participant A as API Service
    participant V as Valkey
    participant E as SageMaker Embeddings
    participant R as SageMaker Reranker
    participant S3 as S3 / PageIndex Artifacts

    C->>A: memory_get(session_id, query)
    A->>V: validate active session and plan
    A->>E: embed query
    E-->>A: query vector
    A->>V: vector search within user and session boundary

    opt hybrid enabled and PageIndex exists
        A->>S3: load bounded structured candidates
        S3-->>A: PageIndex candidate references
    end

    opt reranking enabled
        A->>R: rerank bounded candidates
        R-->>A: relevance scores
    end

    A->>V: refresh TTL and retrieval metadata
    A-->>C: top-k relevant context
```

---

## 9. Compaction workflow

```mermaid
sequenceDiagram
    participant C as Client / MCP Host
    participant A as API Service
    participant V as Valkey
    participant Q as SQS FIFO
    participant W as Worker
    participant M as SageMaker Compactor
    participant S3 as S3
    participant D as DynamoDB

    C->>A: memory_compact(session_id)
    A->>V: validate ownership and session state
    A->>Q: enqueue session-ordered job
    A->>V: refresh TTL
    A-->>C: queued job response

    Q->>W: compaction job
    W->>V: acquire session lock
    W->>V: read active candidate memories
    W->>M: generate compacted summary
    M-->>W: summary + source references
    W->>V: atomically write summary and supersede sources
    W->>S3: write or update PageIndex artifact
    W->>D: update job and audit state
    W->>V: release lock
```

---

## 10. Hybrid retrieval decision flow

```mermaid
flowchart TD
    Start[Receive memory_get request]
    Validate[Validate user, session, plan]
    Embed[Generate query embedding]
    Dense[Valkey vector retrieval]
    HasPageIndex{PageIndex enabled<br/>and artifact available?}
    Structured[Retrieve structured candidates]
    HasReranker{Reranking enabled?}
    Rerank[Bounded reranking]
    Fuse[Score fusion and duplicate removal]
    Filter[Apply threshold, top-k, and token cap]
    Return[Return context results]

    Start --> Validate
    Validate --> Embed
    Embed --> Dense
    Dense --> HasPageIndex
    HasPageIndex -- Yes --> Structured
    HasPageIndex -- No --> HasReranker
    Structured --> HasReranker
    HasReranker -- Yes --> Rerank
    HasReranker -- No --> Fuse
    Rerank --> Fuse
    Fuse --> Filter
    Filter --> Return
```

---

## 11. Data ownership boundaries

```mermaid
flowchart TB
    Auth[Verified Cognito identity]
    User[User ID]
    Session[Session ID]
    Memory[Memory ID]

    Auth --> User
    User --> Session
    Session --> Memory

    User --> UserRecord[DynamoDB user and entitlement data]
    User --> SessionIndex[Valkey active session index]
    Session --> SessionMeta[Valkey session metadata]
    Session --> DurableSession[DynamoDB durable session metadata]
    Session --> MemoryItems[Valkey session memory items]
    Session --> PageIndex[S3 PageIndex artifacts]
```

---

## 12. CI/CD delivery flow

```mermaid
flowchart LR
    Git[GitHub Repository]
    Conn[AWS CodeConnections]
    Pipe[CodePipeline]
    Build[CodeBuild]
    Tests[Unit / Integration / Security Tests]
    Plan[Terraform Plan]
    Approval[Manual Production Approval]
    Apply[Terraform Apply]
    ECR[Amazon ECR]
    Deploy[CodeDeploy / ECS Deployment]
    Smoke[Smoke and Contract Tests]
    Monitor[CloudWatch Monitoring]

    Git --> Conn
    Conn --> Pipe
    Pipe --> Build
    Build --> Tests
    Tests --> Plan
    Plan --> Approval
    Approval --> Apply
    Build --> ECR
    ECR --> Deploy
    Apply --> Deploy
    Deploy --> Smoke
    Smoke --> Monitor
```

---

## 13. Failure-degradation flow

```mermaid
flowchart TD
    Request[Incoming request]
    Valkey{Valkey available?}
    DDB{DynamoDB available?}
    Embed{Embedding endpoint available?}
    Rerank{Reranker available?}
    PageIndex{PageIndex / S3 available?}
    Success[Serve response]

    Request --> Valkey
    Valkey -- No --> FailClosed[Return retryable service unavailable]
    Valkey -- Yes --> DDB

    DDB -- No --> CachedEntitlement{Valid cached entitlement exists?}
    CachedEntitlement -- No --> Retry[Return retryable dependency error]
    CachedEntitlement -- Yes --> Embed

    DDB -- Yes --> Embed
    Embed -- No --> EmbedFail[Return inference unavailable or pending policy]
    Embed -- Yes --> Rerank

    Rerank -- No --> VectorFallback[Use vector-only ranking]
    Rerank -- Yes --> PageIndex

    VectorFallback --> PageIndex
    PageIndex -- No --> Success
    PageIndex -- Yes --> Success
```

---

## 14. Scaling domains

```mermaid
flowchart TB
    Traffic[Request Traffic]
    Queue[Background Queue Depth]
    Inference[Model Inference Load]

    Traffic --> APIScale[ECS API and MCP Autoscaling]
    Queue --> WorkerScale[ECS Worker Autoscaling]
    Inference --> EmbedScale[SageMaker Embedding Autoscaling]
    Inference --> RankScale[SageMaker Reranker Autoscaling]
    Inference --> CompactScale[SageMaker Compactor Capacity]

    APIScale --> ValkeyCapacity[Valkey Capacity Monitoring]
    WorkerScale --> QueueHealth[SQS Age and Retry Monitoring]
    EmbedScale --> ModelHealth[Endpoint Latency and Error Monitoring]
```

---

## 15. Diagram usage guidance

| Diagram | Primary use |
|---|---|
| System context | Product and integration discussion. |
| Core AWS architecture | Infrastructure design and Terraform planning. |
| Service boundaries | Codebase module ownership. |
| Session lifecycle | Lifecycle implementation and test cases. |
| Entitlement sequence | Atomic session creation and plan enforcement. |
| Add and retrieve sequences | API implementation and latency design. |
| Compaction workflow | Worker, SQS, and model integration. |
| Hybrid retrieval flow | Retrieval evaluation and feature-gate behavior. |
| Ownership boundaries | Security and data-model review. |
| CI/CD flow | Deployment pipeline implementation. |
| Failure flow | Resiliency and incident-response planning. |
| Scaling domains | Autoscaling and capacity planning. |
