# =============================================================================
# IAM Roles & Policies for ECS Fargate Tasks
# Follows Principle of Least Privilege
# =============================================================================

# Trust policy document for ECS Tasks
data "aws_iam_policy_document" "ecs_tasks_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# -----------------------------------------------------------------------------
# 1. ECS Task Execution Role (used by ECS agent to pull images & fetch secrets)
# -----------------------------------------------------------------------------
resource "aws_iam_role" "ecs_execution_role" {
  name               = "${local.name_prefix}-ecs-execution-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-ecs-execution-role"
  })
}

# Attach AWS managed execution policy (ECR pull, CloudWatch logs)
resource "aws_iam_role_policy_attachment" "ecs_execution_standard" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Policy allowing ECS agent to read Secrets Manager secrets for environment variables
resource "aws_iam_policy" "ecs_secrets_access" {
  name        = "${local.name_prefix}-ecs-secrets-policy"
  description = "Allows ECS agent to retrieve database credentials and app secrets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.db_credentials.arn,
          aws_secretsmanager_secret.app_secrets.arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_secrets" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = aws_iam_policy.ecs_secrets_access.arn
}

# -----------------------------------------------------------------------------
# 2. ECS Task Role (used by the running application container code)
# -----------------------------------------------------------------------------
resource "aws_iam_role" "ecs_task_role" {
  name               = "${local.name_prefix}-ecs-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-ecs-task-role"
  })
}

# Base application runtime policy (CloudWatch metrics, X-Ray)
resource "aws_iam_policy" "ecs_task_policy" {
  name        = "${local.name_prefix}-ecs-task-app-policy"
  description = "Application permissions for FindWorker services"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_app" {
  role       = aws_iam_role.ecs_task_role.name
  policy_arn = aws_iam_policy.ecs_task_policy.arn
}

