# Terraform Infrastructure Plan

## 1. Purpose

This document defines the Terraform strategy for provisioning MemoryRepo infrastructure on AWS.

Terraform is the source of truth for AWS resource configuration. Application code, model code, and workflow definitions remain in their own repositories or directories, but AWS infrastructure must be reproducible from reviewed Terraform changes.

The plan supports isolated environments:

```text
dev
stage
prod
```

The first implementation may begin with `dev` and add `stage` and `prod` after the core service works.

---

## 2. Terraform goals

Terraform must:

- Provision all required AWS infrastructure.
- Keep environments isolated.
- Use reusable modules.
- Avoid copy-paste infrastructure definitions.
- Support plan on pull request and apply through GitHub Actions.
- Use remote encrypted state.
- Support safe incremental rollout.
- Keep secrets out of Terraform state where possible.
- Make AWS dependencies explicit.
- Support teardown for development environments without risking production resources.

---

## 3. Infrastructure scope

Terraform must eventually provision:

| Domain | AWS resources |
|---|---|
| Networking | VPC, subnets, route tables, NAT, security groups, VPC endpoints. |
| Edge | API Gateway, WAF, domain configuration if needed. |
| Identity | Cognito user pool, app clients, resource servers, authorizers. |
| Compute | ECS cluster, ECS services, task definitions, ALB, autoscaling. |
| Data | ElastiCache for Valkey, DynamoDB tables, S3 buckets. |
| Async | SQS FIFO queues and DLQs. |
| ML | SageMaker execution roles, endpoint configuration, model artifacts references. |
| Security | IAM roles, policies, KMS keys, Secrets Manager entries. |
| Observability | CloudWatch log groups, alarms, dashboards, X-Ray configuration. |
| CI/CD support | ECR repositories, OIDC roles for GitHub Actions. |

---

## 4. Recommended repository layout

```text
infra/
  bootstrap/
    state_backend/
    github_oidc/

  environments/
    dev/
      main.tf
      variables.tf
      outputs.tf
      terraform.tfvars.example
    stage/
      main.tf
      variables.tf
      outputs.tf
      terraform.tfvars.example
    prod/
      main.tf
      variables.tf
      outputs.tf
      terraform.tfvars.example

  modules/
    naming/
    kms/
    vpc/
    vpc_endpoints/
    security_groups/
    ecr/
    cognito/
    api_gateway/
    alb/
    ecs_cluster/
    ecs_service/
    elasticache_valkey/
    dynamodb/
    s3/
    sqs/
    iam/
    secrets/
    sagemaker/
    cloudwatch/
    waf/
    github_oidc/

  shared/
    versions.tf
    provider.tf
    tags.tf
```

---

## 5. Bootstrap layer

The bootstrap layer creates resources needed before normal Terraform environments can run.

Bootstrap resources:

- Terraform state S3 bucket.
- Terraform state lock configuration.
- KMS key for Terraform state if required.
- GitHub Actions OIDC provider.
- GitHub Actions IAM roles.
- Optional central ECR repositories.
- Optional organization-wide CloudTrail or logging integration.

Bootstrap should be applied manually once per AWS account or through a carefully protected bootstrap workflow.

---

## 6. Terraform state design

## 6.1 Remote state backend

Use an encrypted S3 backend.

Suggested state paths:

```text
memoryrepo-tfstate/dev/terraform.tfstate
memoryrepo-tfstate/stage/terraform.tfstate
memoryrepo-tfstate/prod/terraform.tfstate
```

## 6.2 Locking

Use Terraform-supported S3 lockfile behavior.

Example direction:

```hcl
terraform {
  backend "s3" {
    bucket       = "memoryrepo-tfstate"
    key          = "dev/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
```

## 6.3 State rules

- Never share one state file between environments.
- Do not store raw secrets in Terraform variables if avoidable.
- Restrict state bucket access to Terraform deployment roles.
- Enable bucket versioning.
- Enable encryption.
- Enable lifecycle policy for stale state versions according to policy.
- Enable audit logging if organization policy requires it.
- Never run `terraform apply` from a local laptop against production unless emergency policy explicitly allows it.

---

## 7. Environment composition

Each environment should call the same modules with different variables.

Example high-level composition:

```hcl
module "naming" {
  source      = "../../modules/naming"
  environment = var.environment
  project     = "memoryrepo"
}

module "vpc" {
  source = "../../modules/vpc"

  name_prefix = module.naming.name_prefix
  cidr_block  = var.vpc_cidr
}

module "data" {
  source = "../../modules/dynamodb"

  name_prefix = module.naming.name_prefix
}

module "valkey" {
  source = "../../modules/elasticache_valkey"

  name_prefix        = module.naming.name_prefix
  private_subnet_ids = module.vpc.data_subnet_ids
  security_group_ids = [module.security_groups.valkey_sg_id]
}
```

Environment-specific variables should control:

- Region.
- VPC CIDR.
- Availability zones.
- NAT configuration.
- ECS desired count.
- Valkey node size.
- DynamoDB capacity mode.
- SageMaker endpoint instance type.
- Log retention.
- Alarm thresholds.
- Domain names.
- Feature flags.
- Cost controls.

---

## 8. Core Terraform modules

# 8.1 `naming`

Purpose:

- Standardize resource names.
- Apply environment prefixes.
- Apply common tags.
- Avoid collisions.

Inputs:

```text
project
environment
region
component
```

Outputs:

```text
name_prefix
common_tags
resource_name helpers
```

Example name:

```text
memoryrepo-dev-api
memoryrepo-prod-valkey
memoryrepo-stage-jobs.fifo
```

---

# 8.2 `kms`

Purpose:

- Create KMS keys for data, logs, queues, and secrets where separate keys are required.
- Define key policies.
- Create aliases.

Initial keys may include:

```text
memoryrepo-{env}-data
memoryrepo-{env}-logs
memoryrepo-{env}-secrets
memoryrepo-{env}-terraform-state
```

Requirements:

- Environment isolation.
- Least-privilege key policies.
- Terraform role access.
- Application role access only where needed.

---

# 8.3 `vpc`

Purpose:

- Create VPC.
- Create public, private application, and private data subnets.
- Create route tables.
- Create NAT gateways where required.
- Configure DNS support and hostnames.

Inputs:

```text
vpc_cidr
availability_zones
public_subnet_cidrs
app_subnet_cidrs
data_subnet_cidrs
nat_gateway_mode
```

Outputs:

```text
vpc_id
public_subnet_ids
app_subnet_ids
data_subnet_ids
private_route_table_ids
```

Initial cost-conscious development configuration may use a single NAT gateway. Production should evaluate multi-AZ NAT design.

---

# 8.4 `vpc_endpoints`

Purpose:

Reduce public egress and improve private service access.

Initial endpoint candidates:

- S3 gateway endpoint.
- DynamoDB gateway endpoint.
- ECR API interface endpoint.
- ECR DKR interface endpoint.
- CloudWatch Logs endpoint.
- Secrets Manager endpoint.
- SQS endpoint.
- STS endpoint.
- SageMaker runtime endpoint if supported by selected architecture.

---

# 8.5 `security_groups`

Purpose:

Create least-privilege network rules.

Required groups:

| Security group | Used by |
|---|---|
| `alb_sg` | Internal ALB. |
| `api_sg` | ECS API and MCP tasks. |
| `worker_sg` | ECS worker tasks. |
| `valkey_sg` | ElastiCache for Valkey. |
| `vpclink_sg` | API Gateway VPC Link if required. |
| `sagemaker_sg` | SageMaker VPC-attached endpoints if configured. |

Rules must be explicit.

Example:

```text
ALB -> API/MCP on application port
API/Worker -> Valkey on Valkey port
API/Worker -> required VPC endpoints
No public ingress to Valkey
```

---

# 8.6 `ecr`

Purpose:

Create image repositories.

Initial repositories:

```text
memoryrepo-api
memoryrepo-mcp
memoryrepo-worker
memoryrepo-embedding
memoryrepo-reranker
memoryrepo-compactor
```

Requirements:

- Immutable image tags where possible.
- Enhanced scanning.
- Lifecycle policies.
- Encryption.
- Repository policies allowing only approved CI roles to push.

---

# 8.7 `cognito`

Purpose:

Provision identity configuration.

Resources may include:

- Cognito user pool.
- User pool clients.
- Hosted UI only if required.
- Resource server and scopes.
- Domain configuration.
- Token validity policy.
- Callback URLs for approved clients.

The module must expose:

```text
user_pool_id
user_pool_client_id
issuer_url
jwks_uri
```

---

# 8.8 `dynamodb`

Purpose:

Create durable operational tables.

Tables:

```text
memoryrepo-users
memoryrepo-plans
memoryrepo-entitlements
memoryrepo-sessions
memoryrepo-idempotency
memoryrepo-audit-events
memoryrepo-jobs
```

Requirements:

- Point-in-time recovery in stage and prod.
- KMS encryption.
- Tags.
- TTL configuration where relevant.
- GSI definitions from the data-model document.
- Deletion protection in production where supported by service policy.
- Autoscaling or on-demand mode based on environment.

---

# 8.9 `elasticache_valkey`

Purpose:

Provision the active session and memory store.

Requirements:

- Private subnet group.
- Encryption in transit where available.
- Encryption at rest where available.
- Security group restricted to API and worker services.
- Parameter group configured for required search or vector capability.
- CloudWatch monitoring.
- Backup policy aligned with temporary-session privacy rules.
- Environment-specific node type.
- Production replication and failover strategy.

Important:

```text
Valkey is an ephemeral active-session dependency.
It must not be treated as permanent user memory storage.
```

---

# 8.10 `s3`

Purpose:

Create private artifact buckets.

Buckets may include:

```text
memoryrepo-{env}-artifacts
memoryrepo-{env}-model-artifacts
memoryrepo-{env}-evaluation-data
```

Requirements:

- Block all public access.
- SSE-KMS encryption.
- Bucket versioning where required.
- Lifecycle policies.
- Access logging if required.
- Restricted bucket policies.
- Prefix-level access for worker and model roles.

---

# 8.11 `sqs`

Purpose:

Create background job queues.

Required queues:

```text
memoryrepo-{env}-jobs.fifo
memoryrepo-{env}-jobs-dlq.fifo
```

Requirements:

- FIFO mode.
- Content-based deduplication only if payload design supports it.
- Explicit dead-letter configuration.
- KMS encryption.
- Visibility timeout greater than expected worker processing time.
- Redrive policy.
- Alarms for queue depth, oldest message age, and DLQ messages.

---

# 8.12 `iam`

Purpose:

Create service roles and scoped policies.

Required roles:

| Role | Used by |
|---|---|
| `memoryrepo-api-task-role` | API service. |
| `memoryrepo-mcp-task-role` | MCP service. |
| `memoryrepo-worker-task-role` | Background workers. |
| `memoryrepo-sagemaker-execution-role` | SageMaker models and endpoints. |
| `memoryrepo-github-dev-deploy-role` | GitHub Actions dev workflow. |
| `memoryrepo-github-prod-deploy-role` | GitHub Actions prod workflow. |
| `memoryrepo-github-plan-role` | Plan-only workflow. |
| `memoryrepo-admin-role` | Protected administrative operations. |

Policies must reference specific resources and prefixes.

---

# 8.13 `secrets`

Purpose:

Create and manage secret placeholders, resource policies, and rotation hooks.

Examples:

- Internal service signing keys if needed.
- External model repository tokens if required.
- Development-only integration credentials.
- Admin bootstrap credentials if approved.

Terraform should create secret containers but should avoid embedding secret values directly in `.tf` or `.tfvars` files.

---

# 8.14 `ecs_cluster`

Purpose:

Create ECS cluster and shared runtime configuration.

Resources:

- ECS cluster.
- Capacity provider configuration if required.
- CloudWatch log group.
- Container Insights.
- Service discovery namespace if later needed.

---

# 8.15 `ecs_service`

Purpose:

Deploy API, MCP, and worker services.

Inputs:

```text
service_name
container_image
task_cpu
task_memory
desired_count
environment_variables
secret_references
security_group_ids
subnet_ids
load_balancer_target_group
autoscaling_configuration
task_role_arn
execution_role_arn
```

Service variants:

```text
memoryrepo-api
memoryrepo-mcp
memoryrepo-worker
```

API and MCP services need ALB target groups. Worker service does not.

---

# 8.16 `alb`

Purpose:

Create internal application load balancer and target groups.

Initial route patterns:

```text
/v1/*          -> API service
/mcp/*         -> MCP service
/health/*      -> health endpoints
```

The final route pattern depends on selected MCP transport design.

---

# 8.17 `api_gateway`

Purpose:

Create public HTTPS API entry point.

Resources may include:

- HTTP API.
- JWT authorizer.
- VPC Link.
- Private ALB integration.
- Access logs.
- Throttling.
- Route definitions.
- Custom domain mapping if needed.

Initial routes:

```text
/v1/{proxy+}
/mcp/{proxy+}
```

WAF should protect the API Gateway endpoint.

---

# 8.18 `waf`

Purpose:

Protect public API entry.

Initial controls:

- AWS managed common rule set.
- Known bad input rules.
- Rate-based rules.
- IP allow-list support for administration if needed.
- Logging destination.

WAF rules must not block valid MCP long-lived or streaming requests without testing.

---

# 8.19 `sagemaker`

Purpose:

Provision ML endpoint support.

Resources may include:

- SageMaker execution role.
- Model definitions.
- Endpoint configurations.
- Endpoints.
- VPC configuration.
- Auto-scaling policies.
- CloudWatch alarms.
- Model artifact S3 access policies.

Initial endpoint logical names:

```text
memoryrepo-{env}-embedding
memoryrepo-{env}-reranker
memoryrepo-{env}-compactor
```

The first MVP may provision only the embedding endpoint.

---

# 8.20 `cloudwatch`

Purpose:

Create logs, alarms, dashboards, and metric filters.

Must include:

- API and MCP error alarms.
- Valkey eviction alarms.
- SQS DLQ alarms.
- SageMaker endpoint error alarms.
- ECS task health alarms.
- DynamoDB throttle alarms.
- Dashboards from observability requirements.
- Log retention policies by environment.

---

# 8.21 `github_oidc`

Purpose:

Allow GitHub Actions to assume AWS roles without long-lived access keys.

Requirements:

- OIDC provider.
- Role trust conditions restricted by repository.
- Separate roles by environment.
- Branch and environment conditions.
- Least-privilege deployment policies.

Example conceptual trust boundaries:

```text
dev deployment role:
  repository = approved repo
  ref = refs/heads/dev

prod deployment role:
  repository = approved repo
  ref = refs/heads/main
  environment = production
```

---

## 9. Dependency order

Terraform rollout should follow this sequence.

### Phase 0: Bootstrap

1. State bucket.
2. State locking.
3. GitHub OIDC provider.
4. GitHub plan and deploy roles.

### Phase 1: Shared foundation

1. Naming.
2. KMS.
3. VPC.
4. Subnets and routing.
5. VPC endpoints.
6. Security groups.
7. CloudWatch base log groups.

### Phase 2: Data and artifacts

1. DynamoDB tables.
2. S3 buckets.
3. SQS queues and DLQ.
4. ECR repositories.
5. Secrets containers.
6. Valkey subnet group and replication group.

### Phase 3: Identity and edge

1. Cognito.
2. Internal ALB.
3. API Gateway.
4. WAF.
5. Route integrations.

### Phase 4: Compute

1. ECS cluster.
2. Task execution roles.
3. API task definition.
4. MCP task definition.
5. Worker task definition.
6. ECS services.
7. Autoscaling.
8. Health checks.

### Phase 5: ML

1. SageMaker execution role.
2. Model artifact bucket policy.
3. Embedding model.
4. Endpoint configuration.
5. Embedding endpoint.
6. Optional reranker and compactor endpoints.

### Phase 6: Observability

1. Dashboards.
2. Alarms.
3. Log metric filters.
4. Cost alerts.
5. Synthetics or smoke-check resources if adopted.

---

## 10. Terraform variables

Each environment must define at least:

| Variable | Purpose |
|---|---|
| `aws_region` | Deployment region. |
| `environment` | `dev`, `stage`, or `prod`. |
| `project_name` | `memoryrepo`. |
| `vpc_cidr` | Network range. |
| `availability_zones` | Selected AZs. |
| `api_desired_count` | API task count. |
| `mcp_desired_count` | MCP task count. |
| `worker_desired_count` | Worker task count. |
| `valkey_node_type` | Valkey capacity. |
| `dynamodb_billing_mode` | On-demand or provisioned. |
| `embedding_instance_type` | SageMaker endpoint instance type. |
| `log_retention_days` | Log lifecycle. |
| `domain_name` | Optional custom domain. |
| `enable_reranker` | Environment capability. |
| `enable_compactor` | Environment capability. |
| `enable_pageindex` | Environment capability. |
| `deletion_protection` | Production safeguard. |
| `cost_guardrail_mode` | Development cost control. |

---

## 11. Environment sizing guidance

### Development

Use minimal-cost configuration where possible:

- Small ECS desired counts.
- Small Valkey node.
- On-demand DynamoDB.
- Embedding endpoint only when testing requires it.
- Optional local model stub for unit tests.
- Short log retention.
- Single NAT gateway or controlled egress strategy.

### Stage

Use production-like topology where practical:

- Multiple ECS tasks.
- Real integration with Valkey and SageMaker.
- Load testing enabled.
- Production-like alarms.
- Smaller but representative data size.

### Production

Use resilience and scale controls:

- Multi-AZ design where justified.
- Multiple API and MCP tasks.
- Valkey replication and failover strategy.
- Production alarms.
- Longer retention for operational metadata.
- Protected state and deletion safeguards.
- Approved deployment roles only.

---

## 12. Terraform quality controls

All infrastructure changes must pass:

```text
terraform fmt -check
terraform init
terraform validate
terraform plan
static IaC security scan
policy checks
module tests where available
```

Additional recommended controls:

- `tflint`
- Checkov or equivalent IaC scan
- Infracost estimate for cost-impact visibility
- Terraform provider version pinning
- Module version pinning
- Required tags policy

---

## 13. Tagging strategy

All supported resources must carry tags:

```text
Project = MemoryRepo
Environment = dev | stage | prod
ManagedBy = Terraform
Service = api | mcp | worker | data | ml | edge
Owner = platform-team
CostCenter = configurable
DataClassification = internal | sensitive
```

Tags support:

- Cost allocation.
- Environment isolation.
- Incident response.
- Inventory.
- Lifecycle automation.
- Access-control conditions where applicable.

---

## 14. Secrets and Terraform state precautions

Terraform state can contain sensitive metadata.

Rules:

- Do not pass raw secret values through Terraform variables.
- Create Secrets Manager objects without embedding the final secret in state where possible.
- Use references, ARNs, and generated placeholders.
- Restrict state bucket access.
- Enable encryption and versioning.
- Review plan output for accidental secret exposure.
- Redact CI logs when tools may print sensitive values.

---

## 15. Destruction and lifecycle protection

### Development

Terraform destroy may be allowed with explicit safeguards.

### Stage

Terraform destroy should require manual approval.

### Production

Production destruction must be blocked by default.

Use:

- Terraform resource lifecycle protection.
- AWS deletion protection where supported.
- Separate destroy workflow.
- Protected GitHub Environment.
- Explicit confirmation variable.
- Audit record.

Never include destructive production actions in ordinary deployment workflows.

---

## 16. Acceptance criteria

This document is satisfied when:

1. Terraform state is remote, encrypted, versioned, and isolated by environment.
2. Terraform infrastructure is organized into reusable modules.
3. Dev, stage, and prod can use the same module set with different variables.
4. GitHub Actions can plan and apply infrastructure through OIDC roles.
5. Infrastructure rollout order is explicit.
6. Valkey, DynamoDB, S3, SQS, ECS, API Gateway, Cognito, SageMaker, and observability resources have defined Terraform modules.
7. Production infrastructure has deletion and approval safeguards.
8. Secrets are not embedded in Terraform source or state unnecessarily.
9. Tags support cost, ownership, and environment visibility.
10. Terraform validation and security checks run before apply.
