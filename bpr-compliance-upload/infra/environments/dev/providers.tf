terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  backend "s3" {
    bucket         = "bpr-compliance-tfstate-dev"
    key            = "dev/terraform.tfstate"
    region         = "ap-southeast-3"
    dynamodb_table = "bpr-compliance-tflock-dev"
    encrypt        = true
    profile        = "bpr-compliance-dev"
  }
}

provider "aws" {
  region  = var.aws_region
  profile = "bpr-compliance-dev"
  default_tags {
    tags = local.common_tags
  }
}
