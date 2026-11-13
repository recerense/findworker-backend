variable "aws_region" {
  description = "AWS region to deploy resources into"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name identifier used for prefixing resource names"
  type        = string
  default     = "findworker"
}

variable "environment" {
  description = "Deployment environment (e.g. dev, staging, prod)"
  type        = string
  default     = "dev"
}

# -----------------------------------------------------------------------------
# Networking / VPC
# -----------------------------------------------------------------------------

variable "vpc_cidr" {
  description = "CIDR block for the dedicated VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets (ALB & NAT Gateways)"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_app_subnet_cidrs" {
  description = "CIDR blocks for private application subnets (ECS Fargate tasks)"
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24"]
}

variable "database_subnet_cidrs" {
  description = "CIDR blocks for isolated database and cache subnets (Aurora & Redis)"
  type        = list(string)
  default     = ["10.0.21.0/24", "10.0.22.0/24"]
}

variable "single_nat_gateway" {
  description = "Set to true to use a single NAT Gateway across AZs to minimize AWS costs for dev/staging. Set to false in prod for multi-AZ NAT HA."
  type        = bool
  default     = true
}

# -----------------------------------------------------------------------------
# RDS Aurora PostgreSQL
# -----------------------------------------------------------------------------

variable "db_name" {
  description = "Initial PostgreSQL database name"
  type        = string
  default     = "findworker"
}

variable "db_username" {
  description = "Master username for Aurora PostgreSQL"
  type        = string
  default     = "postgres"
}

variable "aurora_engine_version" {
  description = "Aurora PostgreSQL engine version"
  type        = string
  default     = "15.4"
}

variable "aurora_min_capacity" {
  description = "Minimum ACU (Aurora Capacity Unit) for Aurora Serverless v2. Min supported is 0.5 (~1GB RAM)."
  type        = number
  default     = 0.5
}

variable "aurora_max_capacity" {
  description = "Maximum ACU for Aurora Serverless v2. 1.0 or 2.0 provides good headroom for burst traffic at low cost."
  type        = number
  default     = 2.0
}

variable "aurora_instance_count" {
  description = "Number of Aurora DB instances in the cluster. Minimum is 1 (writer)."
  type        = number
  default     = 1
}

variable "deletion_protection" {
  description = "Enable deletion protection on RDS cluster. Recommended true in production."
  type        = bool
  default     = false
}

variable "skip_final_snapshot" {
  description = "Skip final snapshot before cluster deletion. Set to false in production to prevent data loss."
  type        = bool
  default     = true
}

# -----------------------------------------------------------------------------
# Redis (ElastiCache)
# -----------------------------------------------------------------------------

variable "redis_node_type" {
  description = "ElastiCache Redis node instance type. cache.t4g.micro is the lowest-cost Graviton2 min spec."
  type        = string
  default     = "cache.t4g.micro"
}

variable "redis_num_nodes" {
  description = "Number of cache nodes in the Redis cluster. 1 for min-spec dev."
  type        = number
  default     = 1
}

variable "redis_multi_az" {
  description = "Enable Multi-AZ automatic failover for Redis. Set to false for single-node min spec."
  type        = bool
  default     = false
}

# -----------------------------------------------------------------------------
# Microservices & ECS Fargate
# -----------------------------------------------------------------------------

variable "services" {
  description = "Configuration map for the 3 backend microservices: auth, customer, worker"
  type = map(object({
    cpu            = number
    memory         = number
    container_port = number
    desired_count  = number
    path_patterns  = list(string)
    priority       = number
  }))
  default = {
    auth = {
      cpu            = 256
      memory         = 512
      container_port = 8000
      desired_count  = 1
      path_patterns  = ["/api/auth*", "/api/v1/auth*"]
      priority       = 10
    }
    customer = {
      cpu            = 256
      memory         = 512
      container_port = 8000
      desired_count  = 1
      path_patterns  = ["/api/customer*", "/api/customers*", "/api/v1/customer*"]
      priority       = 20
    }
    worker = {
      cpu            = 256
      memory         = 512
      container_port = 8000
      desired_count  = 1
      path_patterns  = ["/api/worker*", "/api/workers*", "/api/v1/worker*"]
      priority       = 30
    }
  }
}

variable "use_placeholder_image" {
  description = "Whether to use a lightweight HTTP placeholder container for initial infrastructure provisioning so ECS tasks start and pass health checks before real app code is built and pushed to ECR."
  type        = bool
  default     = true
}

variable "container_images" {
  description = "Custom container image URIs for each service. If use_placeholder_image is false and a value is empty, defaults to the service's ECR repository URL with :latest tag."
  type        = map(string)
  default = {
    auth     = ""
    customer = ""
    worker   = ""
  }
}

variable "log_retention_days" {
  description = "Retention period in days for CloudWatch log groups"
  type        = number
  default     = 7
}

# -----------------------------------------------------------------------------
# Load Balancer & Domain (Optional)
# -----------------------------------------------------------------------------

variable "certificate_arn" {
  description = "Optional ACM SSL/TLS certificate ARN for HTTPS listener on port 443. Leave empty for HTTP only."
  type        = string
  default     = ""
}

