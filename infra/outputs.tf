# =============================================================================
# Outputs for FindWorker Infrastructure
# =============================================================================

# -----------------------------------------------------------------------------
# Networking Outputs
# -----------------------------------------------------------------------------
output "vpc_id" {
  description = "The ID of the dedicated FindWorker VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "List of public subnet IDs (ALB & NAT)"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "List of private subnet IDs (ECS Fargate Tasks)"
  value       = aws_subnet.private[*].id
}

output "database_subnet_ids" {
  description = "List of isolated database subnet IDs (Aurora & Redis)"
  value       = aws_subnet.database[*].id
}

# -----------------------------------------------------------------------------
# ALB & Service URL Outputs
# -----------------------------------------------------------------------------
output "alb_dns_name" {
  description = "Public DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "alb_http_url" {
  description = "Public HTTP endpoint URL for the FindWorker API Gateway"
  value       = "http://${aws_lb.main.dns_name}"
}

output "service_endpoints" {
  description = "Direct HTTP route endpoints for each microservice"
  value = {
    for k, v in var.services : k => "http://${aws_lb.main.dns_name}/api/${k}"
  }
}

# -----------------------------------------------------------------------------
# ECR Repository URLs
# -----------------------------------------------------------------------------
output "ecr_repository_urls" {
  description = "ECR repository URLs for Docker image build and push"
  value = {
    for k, v in aws_ecr_repository.services : k => v.repository_url
  }
}

# -----------------------------------------------------------------------------
# Database (Aurora PostgreSQL) Outputs
# -----------------------------------------------------------------------------
output "aurora_cluster_endpoint" {
  description = "Aurora PostgreSQL cluster writer endpoint"
  value       = aws_rds_cluster.aurora.endpoint
}

output "aurora_cluster_reader_endpoint" {
  description = "Aurora PostgreSQL cluster reader endpoint (read-only replicas)"
  value       = aws_rds_cluster.aurora.reader_endpoint
}

output "aurora_database_name" {
  description = "Default database name"
  value       = var.db_name
}

output "aurora_master_username" {
  description = "Master username for Aurora PostgreSQL"
  value       = var.db_username
}

# -----------------------------------------------------------------------------
# Redis Outputs
# -----------------------------------------------------------------------------
output "redis_endpoint" {
  description = "Primary endpoint address for ElastiCache Redis"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "redis_port" {
  description = "Redis port"
  value       = aws_elasticache_replication_group.redis.port
}

# -----------------------------------------------------------------------------
# ECS & CloudWatch Outputs
# -----------------------------------------------------------------------------
output "ecs_cluster_name" {
  description = "Name of the ECS Fargate cluster"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_names" {
  description = "Map of ECS service names"
  value = {
    for k, v in aws_ecs_service.services : k => v.name
  }
}

output "secrets_manager_db_secret_name" {
  description = "AWS Secrets Manager secret name holding database credentials"
  value       = aws_secretsmanager_secret.db_credentials.name
}

output "secrets_manager_app_secret_name" {
  description = "AWS Secrets Manager secret name holding application secrets"
  value       = aws_secretsmanager_secret.app_secrets.name
}


output "secrets_manager_db_secret_arn" {
  description = "AWS Secrets Manager secret ARN holding database credentials"
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "secrets_manager_app_secret_arn" {
  description = "AWS Secrets Manager secret ARN holding application secrets"
  value       = aws_secretsmanager_secret.app_secrets.arn
}
