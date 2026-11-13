# =============================================================================
# Security Groups: Strictly following Principle of Least Privilege
# =============================================================================

# -----------------------------------------------------------------------------
# 1. Application Load Balancer Security Group
# -----------------------------------------------------------------------------
resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb-sg"
  description = "Controls HTTP/HTTPS inbound traffic to the FindWorker ALB"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "Allow inbound HTTP from internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Allow inbound HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound traffic from ALB to ECS tasks"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-alb-sg"
  })
}

# -----------------------------------------------------------------------------
# 2. ECS Fargate Tasks Security Group
# -----------------------------------------------------------------------------
resource "aws_security_group" "ecs_tasks" {
  name        = "${local.name_prefix}-ecs-tasks-sg"
  description = "Controls traffic to and from ECS Fargate microservices"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Allow traffic from ALB only on service container ports"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "Allow outbound traffic for pulling images, logging, secrets, DB and Redis"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-ecs-tasks-sg"
  })
}

# -----------------------------------------------------------------------------
# 3. RDS Aurora PostgreSQL Security Group
# -----------------------------------------------------------------------------
resource "aws_security_group" "rds" {
  name        = "${local.name_prefix}-rds-sg"
  description = "Controls access to Aurora PostgreSQL cluster"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Allow PostgreSQL access strictly from ECS Fargate tasks"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  egress {
    description = "Outbound traffic rule"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-rds-sg"
  })
}

# -----------------------------------------------------------------------------
# 4. ElastiCache Redis Security Group
# -----------------------------------------------------------------------------
resource "aws_security_group" "redis" {
  name        = "${local.name_prefix}-redis-sg"
  description = "Controls access to ElastiCache Redis cluster"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Allow Redis access strictly from ECS Fargate tasks"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-redis-sg"
  })
}

