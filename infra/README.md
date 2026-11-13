# FindWorker Infrastructure as Code (Terraform)

This directory contains the complete AWS infrastructure for **FindWorker**, an on-demand service marketplace connecting users with skilled workers (e.g., plumbers, electricians, carpenters, etc.).

---

## 🏗️ Architecture Overview

The infrastructure provisions a production-ready, highly secure, and cost-optimized AWS architecture using **AWS Free-Tier & Minimum Specification** configurations:

```
                                  INTERNET
                                     │
                                     ▼
                    ┌─────────────────────────────────┐
                    │  Application Load Balancer      │
                    │  (Port 80 HTTP / 443 HTTPS)     │
                    └────────────────┬────────────────┘
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           │ Path: /api/auth*        │ Path: /api/customer*    │ Path: /api/worker*
           ▼                         ▼                         ▼
   ┌───────────────┐         ┌───────────────┐         ┌───────────────┐
   │  ECS Fargate  │         │  ECS Fargate  │         │  ECS Fargate  │
   │  Auth Service │         │ Customer Svc  │         │  Worker Svc   │
   │ (256 CPU/512M)│         │ (256 CPU/512M)│         │ (256 CPU/512M)│
   └───────┬───────┘         └───────┬───────┘         └───────┬───────┘
           │                         │                         │
           └─────────────────────────┼─────────────────────────┘
                                     │
                   ┌─────────────────┴─────────────────┐
                   ▼                                   ▼
        ┌─────────────────────┐             ┌─────────────────────┐
        │ RDS Aurora Postgres │             │  ElastiCache Redis  │
        │ Serverless v2       │             │  cache.t4g.micro    │
        │ (0.5 ACU Min Spec)  │             │  (Port 6379)        │
        └─────────────────────┘             └─────────────────────┘
```

### Components Provisioned:

1. **VPC & Networking (`vpc.tf`)**:
   - Dedicated VPC (`10.0.0.0/16`) spanning 2 Availability Zones.
   - **Public Subnets**: ALB and single NAT Gateway (cost-saving for dev/staging).
   - **Private App Subnets**: ECS Fargate tasks with outbound NAT internet access.
   - **Database Subnets**: Completely isolated subnets for Aurora and Redis with no internet or NAT routes.
   - **S3 VPC Gateway Endpoint**: Free internal AWS endpoint to pull ECR layers without NAT data transfer charges.

2. **Application Load Balancer (`alb.tf`)**:
   - Single entry point with path-based routing:
     - `/api/auth*` & `/api/v1/auth*` ➔ `findworker-auth` Target Group
     - `/api/customer*` & `/api/v1/customer*` ➔ `findworker-customer` Target Group
     - `/api/worker*` & `/api/v1/worker*` ➔ `findworker-worker` Target Group
   - Root `/` and unmatched requests return a JSON discovery message.

3. **ECS with Fargate (`ecs.tf`, `iam.tf`)**:
   - Serverless container orchestration for 3 microservices (`auth`, `customer`, `worker`).
   - Default min spec: 256 CPU (0.25 vCPU) and 512 MB memory per task.
   - FARGATE and FARGATE_SPOT capacity providers for maximum cost efficiency.
   - Integrated with CloudWatch Log Groups (7-day retention).
   - **Placeholder Web Server**: Provisions with an instant HTTP health check server so Terraform applies successfully before real Docker images are built.

4. **RDS Aurora PostgreSQL Serverless v2 (`rds_aurora.tf`)**:
   - **Minimum Spec**: `min_capacity = 0.5 ACU` (~1GB RAM, lowest possible spec on AWS).
   - Scales automatically to `max_capacity = 2.0 ACU` when traffic spikes.
   - Encrypted at rest (AWS KMS).
   - 7-day automated backups.
   - PostGIS / GeoAlchemy ready for location-based worker searches.

5. **ElastiCache Redis (`redis.tf`)**:
   - **Minimum Spec**: `cache.t4g.micro` (AWS Graviton2 lowest-cost instance).
   - Standalone replication group for caching, session management, and rate limiting.

6. **ECR Repositories (`ecr.tf`)**:
   - 3 repositories: `findworker/auth`, `findworker/customer`, `findworker/worker`.
   - Vulnerability scanning enabled on push (`scan_on_push = true`).
   - Lifecycle policy: Automatically prunes untagged images older than 7 days and keeps the 15 most recent images.

7. **Secrets Management (`secrets.tf`)**:
   - Master DB password generated cryptographically via `random_password`.
   - Application `SECRET_KEY` (JWT) generated cryptographically.
   - Stored in AWS Secrets Manager and securely injected into ECS containers as environment variables at runtime.

---

## 🔐 GitHub Actions Pipeline Setup

The automated provisioning pipeline is located at `.github/workflows/terraform.yml`.

### Step 1: Add AWS Credentials to GitHub Secrets

In your GitHub repository, navigate to **Settings > Secrets and variables > Actions** and add the following repository secrets:

| Secret Name | Required | Description |
| :--- | :--- | :--- |
| `AWS_ACCESS_KEY_ID` | **Yes** | AWS IAM Access Key ID |
| `AWS_SECRET_ACCESS_KEY` | **Yes** | AWS IAM Secret Access Key |
| `AWS_REGION` | No | Target region (defaults to `us-east-1` if not set) |

> **IAM Permissions Required**: Ensure the IAM user has permissions for VPC, EC2, ECS, ECR, RDS, ElastiCache, IAM, Secrets Manager, and CloudWatch.

### Step 2: Triggering the Pipeline (100% Manual Execution)

All pipeline stages are configured for **manual triggers only** (zero automatic runs on code pushes or pull requests):

1. Navigate to the **Actions** tab in your GitHub repository.
2. Select **Terraform Infrastructure Pipeline (Manual)** from the left sidebar.
3. Click the **Run workflow** button on the right.
4. Choose the stage to run:
   - **`plan`** (Default): Validates syntax and generates an execution plan showing exactly what AWS resources will be created/modified.
   - **`apply`**: Plans and provisions the infrastructure in AWS. *(Requires checking the `confirm_dangerous_action` box)*.
   - **`validate_only`**: Fast syntax and formatting validation.
   - **`destroy`**: Tears down Terraform-managed resources in AWS. *(Requires checking the `confirm_dangerous_action` box)*.

---

## 💻 Running Terraform Locally

### Prerequisites
- [Terraform >= 1.5.0](https://developer.hashicorp.com/terraform/install)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) configured (`aws configure`)

### Quickstart Commands

```bash
cd findworker-backend/infra

# 1. Initialize providers
terraform init

# 2. Review execution plan
terraform plan

# 3. Apply infrastructure
terraform apply
```

To customize variables (e.g., change region or DB settings):
```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars
```

---

## 🚀 Next Steps: Deploying Your Application Code

Once you build your service code:

1. **Authenticate Docker with ECR**:
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
   ```

2. **Build and Push Service Images**:
   ```bash
   # Auth Service
   docker build -t findworker/auth:latest -f Dockerfile.auth .
   docker tag findworker/auth:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/findworker/auth:latest
   docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/findworker/auth:latest

   # Customer Service
   docker build -t findworker/customer:latest -f Dockerfile.customer .
   docker tag findworker/customer:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/findworker/customer:latest
   docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/findworker/customer:latest

   # Worker Service
   docker build -t findworker/worker:latest -f Dockerfile.worker .
   docker tag findworker/worker:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/findworker/worker:latest
   docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/findworker/worker:latest
   ```

3. **Switch to Production Images**:
   Update `use_placeholder_image = false` in `terraform.tfvars` or pass `-var="use_placeholder_image=false"` during `terraform apply`. ECS will automatically roll out the real containers without downtime.

---

## 💰 Cost Optimization Summary

- **Aurora Serverless v2**: Starts at **0.5 ACU** (scales down to near-zero load when idle).
- **ElastiCache Redis**: **`cache.t4g.micro`** Graviton2 (~$0.016/hr, ~$11/month).
- **Single NAT Gateway**: Configured with `single_nat_gateway = true` (saves ~$35/month compared to dual-NAT).
- **ECS Fargate Spot**: Leverages AWS excess capacity for up to **70% discount** on container compute.
- **S3 Gateway Endpoint**: 100% free; routes ECR container image pulls internally without NAT data charges.

