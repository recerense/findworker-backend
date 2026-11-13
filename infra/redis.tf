# =============================================================================
# Amazon ElastiCache for Redis (Minimum Specification)
# Instance Type: cache.t4g.micro (AWS Graviton2 lowest-cost tier)
# Isolated in private database subnets with encryption at rest
# =============================================================================

resource "aws_elasticache_subnet_group" "redis" {
  name        = "${local.name_prefix}-redis-subnet-group"
  description = "Isolated database subnet group for Redis cluster"
  subnet_ids  = aws_subnet.database[*].id

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-redis-subnet-group"
  })
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "${local.name_prefix}-redis"
  description                = "Redis cache and session store for ${local.name_prefix}"
  node_type                  = var.redis_node_type
  port                       = 6379
  parameter_group_name       = "default.redis7"
  subnet_group_name          = aws_elasticache_subnet_group.redis.name
  security_group_ids         = [aws_security_group.redis.id]
  automatic_failover_enabled = var.redis_multi_az
  num_cache_clusters         = var.redis_num_nodes
  at_rest_encryption_enabled = true
  transit_encryption_enabled = false
  apply_immediately          = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-redis"
  })
}

