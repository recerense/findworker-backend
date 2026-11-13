data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  # Pick first 2 availability zones in the configured region
  azs = slice(data.aws_availability_zones.available.names, 0, 2)

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
    Application = "FindWorker"
  }
}

