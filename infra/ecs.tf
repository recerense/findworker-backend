# =============================================================================
# Amazon ECS (Elastic Container Service) with AWS Fargate
# 3 Microservices:
#   1. auth     - Authentication, tokens, and authorization
#   2. customer - Customer profiles, service booking, requests
#   3. worker   - Worker directory, skills, availability, job acceptance
# =============================================================================

resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-cluster"
  })
}

# Use FARGATE and cost-effective FARGATE_SPOT capacity providers
resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name

  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
    base              = 1
  }

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 2
  }
}

# -----------------------------------------------------------------------------
# CloudWatch Log Groups for each microservice
# -----------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "services" {
  for_each = var.services

  name              = "/ecs/${local.name_prefix}-${each.key}"
  retention_in_days = var.log_retention_days

  tags = merge(local.common_tags, {
    Name    = "${local.name_prefix}-${each.key}-logs"
    Service = each.key
  })
}

# -----------------------------------------------------------------------------
# ECS Task Definitions
# -----------------------------------------------------------------------------
resource "aws_ecs_task_definition" "services" {
  for_each = var.services

  family                   = "${local.name_prefix}-${each.key}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = tostring(each.value.cpu)
  memory                   = tostring(each.value.memory)
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "${local.name_prefix}-${each.key}"
      essential = true

      # If use_placeholder_image is true, runs a lightweight Alpine python web server
      # responding with 200 OK on /health to allow the stack to provision cleanly before real code deployment.
      image = var.use_placeholder_image ? "public.ecr.aws/docker/library/python:3.11-alpine" : (
        lookup(var.container_images, each.key, "") != "" ? var.container_images[each.key] : "${aws_ecr_repository.services[each.key].repository_url}:latest"
      )

      command = var.use_placeholder_image ? [
        "python3",
        "-c",
        "from http.server import HTTPServer, BaseHTTPRequestHandler; import json; class H(BaseHTTPRequestHandler): do_GET = lambda s: (s.send_response(200), s.send_header('Content-Type', 'application/json'), s.end_headers(), s.wfile.write(json.dumps({'status': 'healthy', 'service': '${each.key}'}).encode())); HTTPServer(('0.0.0.0', ${each.value.container_port}), H).serve_forever()"
      ] : null

      portMappings = [
        {
          containerPort = each.value.container_port
          hostPort      = each.value.container_port
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "APP_NAME"
          value = "FindWorker ${title(each.key)} Service"
        },
        {
          name  = "APP_VERSION"
          value = "1.0.0"
        },
        {
          name  = "ENVIRONMENT"
          value = var.environment
        },
        {
          name  = "DEBUG"
          value = "false"
        },
        {
          name  = "DB_HOST"
          value = aws_rds_cluster.aurora.endpoint
        },
        {
          name  = "DB_PORT"
          value = "5432"
        },
        {
          name  = "DB_NAME"
          value = var.db_name
        },
        {
          name  = "DB_USER"
          value = var.db_username
        },
        {
          name  = "REDIS_URL"
          value = "redis://${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379/0"
        }
      ]

      secrets = [
        {
          name      = "DB_PASSWORD"
          valueFrom = "${aws_secretsmanager_secret.db_credentials.arn}:password::"
        },
        {
          name      = "SECRET_KEY"
          valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:SECRET_KEY::"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.services[each.key].name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = merge(local.common_tags, {
    Name    = "${local.name_prefix}-${each.key}-task"
    Service = each.key
  })
}

# -----------------------------------------------------------------------------
# ECS Services
# -----------------------------------------------------------------------------
resource "aws_ecs_service" "services" {
  for_each = var.services

  name            = "${local.name_prefix}-${each.key}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.services[each.key].arn
  desired_count   = each.value.desired_count
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.services[each.key].arn
    container_name   = "${local.name_prefix}-${each.key}"
    container_port   = each.value.container_port
  }

  depends_on = [
    aws_lb_listener.http,
    aws_iam_role_policy_attachment.ecs_execution_secrets,
    aws_iam_role_policy_attachment.ecs_execution_standard
  ]

  tags = merge(local.common_tags, {
    Name    = "${local.name_prefix}-${each.key}-service"
    Service = each.key
  })
}

