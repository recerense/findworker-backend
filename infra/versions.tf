terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # NOTE: To use remote S3 backend for GitHub Actions or team collaboration,
  # create an S3 bucket and DynamoDB table (see backend.tf.example), then uncomment below:
  #
  # backend "s3" {
  #   bucket         = "findworker-terraform-state"
  #   key            = "findworker/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "findworker-terraform-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

