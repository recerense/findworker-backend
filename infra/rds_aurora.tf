# =============================================================================
# Amazon Aurora PostgreSQL (Serverless v2 - Minimum Specification)
# Min Capacity: 0.5 ACU (~1GB RAM, lowest cost footprint)
# Isolated in private database subnets with encryption at rest
# =============================================================================

# Cryptographically strong master password for Aurora PostgreSQL
resource "random_password" "aurora_master_password" {
  length           = 24
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# Subnet Group for RDS Aurora (placed exclusively in private database subnets)
resource "aws_db_subnet_group" "aurora" {
  name        = "${local.name_prefix}-aurora-subnet-group"
  description = "Isolated database subnet group for Aurora PostgreSQL"
  subnet_ids  = aws_subnet.database[*].id

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-aurora-subnet-group"
  })
}

# Aurora PostgreSQL DB Cluster
resource "aws_rds_cluster" "aurora" {
  cluster_identifier      = "${local.name_prefix}-aurora-cluster"
  engine                  = "aurora-postgresql"
  engine_mode             = "provisioned" # Required by AWS for Aurora Serverless v2
  engine_version          = var.aurora_engine_version
  database_name           = var.db_name
  master_username         = var.db_username
  master_password         = random_password.aurora_master_password.result
  db_subnet_group_name    = aws_db_subnet_group.aurora.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  # Min spec: 0.5 ACU (~1GB RAM) scaling up to max_capacity dynamically
  serverlessv2_scaling_configuration {
    min_capacity = var.aurora_min_capacity
    max_capacity = var.aurora_max_capacity
  }

  storage_encrypted       = true
  backup_retention_period = 7
  preferred_backup_window = "02:00-03:00"
  skip_final_snapshot     = var.skip_final_snapshot
  deletion_protection     = var.deletion_protection
  apply_immediately       = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-aurora-cluster"
  })
}

# Aurora Serverless v2 DB Instance (1 instance for min spec)
resource "aws_rds_cluster_instance" "aurora" {
  count              = var.aurora_instance_count
  identifier         = "${local.name_prefix}-aurora-instance-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.aurora.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.aurora.engine
  engine_version     = aws_rds_cluster.aurora.engine_version
  db_subnet_group_name = aws_db_subnet_group.aurora.name
  publicly_accessible = false
  apply_immediately   = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-aurora-instance-${count.index + 1}"
  })
}

