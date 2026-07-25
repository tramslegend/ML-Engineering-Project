provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "sentinel"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }

  # N17: all processing in ap-southeast-3, enforced by SCP/IAM condition,
  # not convention. `allowed_account_ids` plus the org-level SCP (deployed
  # separately, outside this stack's blast radius) are the two enforcement
  # points; this provider block pins the *default* region, it is not itself
  # the enforcement mechanism.
}
