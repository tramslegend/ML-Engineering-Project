# Root wiring. See §9 for the data model this maps to, §11 for the
# component table, and each module's own file for what's implemented vs
# flagged as a gap.

# S3 bucket names are globally unique across ALL AWS accounts, not just this
# one — a plain "${var.project}-frontend" collides the moment anyone else in
# the world has already claimed that string. Every bucket in this stack is
# suffixed with the account ID (data source, not a resource — free, no
# extra API calls of consequence) to make collisions structurally
# impossible rather than hoping a short generic name happens to be free.
data "aws_caller_identity" "current" {}

module "vault" {
  source      = "./modules/vault"
  project     = var.project
  kms_key_arn = aws_kms_key.vault.arn
}

module "audit" {
  source          = "./modules/audit"
  project         = var.project
  kms_key_arn     = aws_kms_key.data.arn
  vault_table_arn = module.vault.table_arn
  retention_years = 7 # N18
}

module "api" {
  source              = "./modules/api"
  project             = var.project
  vpc_id              = aws_vpc.this.id
  private_subnet_ids  = aws_subnet.private[*].id
  vault_rw_policy_arn = module.vault.rw_policy_arn
  data_kms_key_arn    = aws_kms_key.data.arn
}

module "inference" {
  source             = "./modules/inference"
  project            = var.project
  deployment_mode    = var.inference_deployment_mode
  vpc_id             = aws_vpc.this.id
  private_subnet_ids = aws_subnet.private[*].id
  ingest_queue_arn   = module.api.ingest_queue_arn
}

module "frontend" {
  source  = "./modules/frontend"
  project = var.project
}

# --- §9 data stores not owned by a module above ---

resource "aws_s3_bucket" "raw_docs" {
  # Zone A (§6.1): original complaint text/files. F1.3 encrypted at rest,
  # F1.4 default 90-day TTL below.
  bucket = "${var.project}-raw-docs-${data.aws_caller_identity.current.account_id}"
  # force_destroy: this scaffold has never carried real customer data, and
  # is applied/destroyed as an ephemeral demo run (see README) — without
  # this, `terraform destroy` fails on any bucket that isn't empty. Remove
  # once this holds real data with a real retention requirement.
  force_destroy = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw_docs" {
  bucket = aws_s3_bucket.raw_docs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.data.arn
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "raw_docs" {
  bucket = aws_s3_bucket.raw_docs.id
  rule {
    id     = "default-ttl"
    status = "Enabled"
    filter {} # applies to the whole bucket; required explicitly as of provider v5
    expiration {
      days = 90 # F1.4 default; configurable per the PRD, override via a separate rule if a deployment needs otherwise
    }
  }
}

resource "aws_s3_bucket_public_access_block" "raw_docs" {
  bucket                  = aws_s3_bucket.raw_docs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket" "tokenized_docs" {
  # Zone B: de-identified text only.
  bucket        = "${var.project}-tokenized-docs-${data.aws_caller_identity.current.account_id}"
  force_destroy = true # see raw_docs above
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tokenized_docs" {
  bucket = aws_s3_bucket.tokenized_docs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.data.arn
    }
  }
}

# Policy corpus: §9 specifies "S3 Vectors" (AWS's vector-search-on-S3
# offering) for the grounding-check retrieval store (F6.5). Provider support
# for that resource type is new/limited as of this writing; modeled here as
# a plain S3 bucket placeholder until the aws provider exposes a dedicated
# resource, or until a decision is made to use OpenSearch Serverless instead.
resource "aws_s3_bucket" "policy_corpus" {
  bucket        = "${var.project}-policy-corpus-${data.aws_caller_identity.current.account_id}"
  force_destroy = true # see raw_docs above
}

resource "aws_dynamodb_table" "triage_results" {
  name         = "${var.project}-triage-results"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "job_id"
  attribute {
    name = "job_id"
    type = "S"
  }
  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.data.arn
  }
}

resource "aws_dynamodb_table" "cost_ledger" {
  name         = "${var.project}-cost-ledger"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"
  attribute {
    name = "id"
    type = "S"
  }
  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.data.arn
  }
}

# N10: provider API keys in Secrets Manager, never environment variables.
# Values are set out-of-band (console/CLI, or a separate sealed-secrets
# process) — Terraform manages the secret's existence/policy, not its value.
resource "aws_secretsmanager_secret" "escalation_provider_keys" {
  name = "${var.project}/escalation-provider-keys"
  # Default recovery window is 30 days (secret stays around, undeletable-by-
  # name, after `destroy`). Zeroed out for this ephemeral demo run so a
  # second apply under the same name doesn't collide with a lingering
  # scheduled-for-deletion secret. Don't do this for anything holding a real
  # key you'd want to recover from an accidental delete.
  recovery_window_in_days = 0
}
