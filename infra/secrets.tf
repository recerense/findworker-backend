# =============================================================================
# AWS Secrets Manager
# Secure storage for database credentials, cache endpoints, and application secrets
# (Zero plaintext secrets in source code or task definitions)
# =============================================================================

# Random cryptographically strong JWT / Application secret key
resource "random_password" "jwt_secret" {
  length  = 48
  special = false
}

# -----------------------------------------------------------------------------
# 1. Database Credentials Secret (`findworker-dev/aurora-credentials`)
# -----------------------------------------------------------------------------
resource "aws_secretsmanager_secret" "db_credentials" {
  name                    = "${local.name_prefix}/aurora-credentials"
  description             = "Master credentials and connection parameters for Aurora PostgreSQL"
  recovery_window_in_days = 0

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-db-secret"
  })
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    engine       = "postgres"
    host         = aws_rds_cluster.aurora.endpoint
    port         = 5432
    username     = var.db_username
    password     = random_password.aurora_master_password.result
    dbname       = var.db_name
    database_url = "postgresql+psycopg://${var.db_username}:${random_password.aurora_master_password.result}@${aws_rds_cluster.aurora.endpoint}:5432/${var.db_name}"
  })
}

# -----------------------------------------------------------------------------
# 2. Application & Cache Secrets (`findworker-dev/app-secrets`)
# -----------------------------------------------------------------------------
resource "aws_secretsmanager_secret" "app_secrets" {
  name                    = "${local.name_prefix}/app-secrets"
  description             = "Runtime application secrets, JWT key, and Redis configuration for FindWorker services"
  recovery_window_in_days = 0

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-app-secret"
  })
}

resource "aws_secretsmanager_secret_version" "app_secrets" {
  secret_id = aws_secretsmanager_secret.app_secrets.id
  secret_string = jsonencode({
    SECRET_KEY = random_password.jwt_secret.result
    REDIS_HOST = aws_elasticache_replication_group.redis.primary_endpoint_address
    REDIS_PORT = 6379
    REDIS_URL  = "redis://${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379/0"
  })
}
