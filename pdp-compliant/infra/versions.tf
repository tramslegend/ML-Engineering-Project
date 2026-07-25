terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  # §11 specifies "Remote state in S3 with DynamoDB locking" for a real
  # deployment — that requires the bucket/table to exist before `init`
  # (chicken-and-egg with a Terraform-managed backend), so it's bootstrapped
  # out-of-band. Defaulted to local state here instead so this scaffold is
  # runnable without that bootstrap step first. Switch back to the S3 block
  # (see git history / README) once this is more than a solo test run —
  # local state has no locking, so concurrent `apply`s can corrupt it, and
  # it only exists on this machine (nothing to recover from if this disk is
  # lost).
  backend "local" {
    path = "terraform.tfstate"
  }
}
