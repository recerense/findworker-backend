# =============================================================================
# Application Load Balancer (ALB) & Path-based Routing
# Routes requests to the 3 microservices:
#   - /api/auth*     -> auth service
#   - /api/customer* -> customer service
#   - /api/worker*   -> worker service
# =============================================================================

resource "aws_lb" "main" {
  name               = "${local.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = false

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-alb"
  })
}

# -----------------------------------------------------------------------------
# Target Groups for each microservice
# -----------------------------------------------------------------------------
resource "aws_lb_target_group" "services" {
  for_each = var.services

  name        = "${local.name_prefix}-${each.key}-tg"
  port        = each.value.container_port
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  deregistration_delay = 30

  tags = merge(local.common_tags, {
    Name    = "${local.name_prefix}-${each.key}-tg"
    Service = each.key
  })
}

# -----------------------------------------------------------------------------
# HTTP Listener (Port 80)
# -----------------------------------------------------------------------------
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  # If HTTPS certificate is configured, redirect HTTP traffic to HTTPS (port 443).
  # Otherwise, serve standard API gateway root response.
  dynamic "default_action" {
    for_each = var.certificate_arn != "" ? [1] : []
    content {
      type = "redirect"
      redirect {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }
  }

  dynamic "default_action" {
    for_each = var.certificate_arn == "" ? [1] : []
    content {
      type = "fixed-response"
      fixed_response {
        content_type = "application/json"
        message_body = jsonencode({
          name        = "FindWorker API Gateway"
          status      = "running"
          environment = var.environment
          services = {
            auth     = "/api/auth/*"
            customer = "/api/customer/*"
            worker   = "/api/worker/*"
          }
        })
        status_code = "200"
      }
    }
  }
}

# -----------------------------------------------------------------------------
# Optional HTTPS Listener (Port 443)
# -----------------------------------------------------------------------------
resource "aws_lb_listener" "https" {
  count             = var.certificate_arn != "" ? 1 : 0
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "application/json"
      message_body = jsonencode({
        name        = "FindWorker API Gateway (HTTPS)"
        status      = "running"
        environment = var.environment
        services = {
          auth     = "/api/auth/*"
          customer = "/api/customer/*"
          worker   = "/api/worker/*"
        }
      })
      status_code = "200"
    }
  }
}

# -----------------------------------------------------------------------------
# Path-based Listener Rules
# -----------------------------------------------------------------------------
resource "aws_lb_listener_rule" "http_services" {
  for_each = var.certificate_arn == "" ? var.services : {}

  listener_arn = aws_lb_listener.http.arn
  priority     = each.value.priority

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.services[each.key].arn
  }

  condition {
    path_pattern {
      values = each.value.path_patterns
    }
  }
}

resource "aws_lb_listener_rule" "https_services" {
  for_each = var.certificate_arn != "" ? var.services : {}

  listener_arn = aws_lb_listener.https[0].arn
  priority     = each.value.priority

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.services[each.key].arn
  }

  condition {
    path_pattern {
      values = each.value.path_patterns
    }
  }
}

