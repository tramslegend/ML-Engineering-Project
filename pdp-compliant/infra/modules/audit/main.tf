# F8.1: append-only audit log in S3 with Object Lock in compliance mode.
# F8.2: CloudTrail data events on the vault table, plus trail-wide
# management events (which is where KMS key usage actually shows up —
# see the aws_cloudtrail resource below for why it's not a data_resource).

locals {
  retention_days = var.retention_years * 365
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "audit_log" {
  bucket              = "${var.project}-audit-log-${data.aws_caller_identity.current.account_id}"
  object_lock_enabled = true
  # force_destroy only helps for ordinary objects — it does NOT override
  # Object Lock COMPLIANCE-mode retention on anything actually written here.
  # Safe for now because nothing in this scaffold writes to S3 yet (the app
  # audit log is a local JSONL file, not wired to this bucket) — the bucket
  # stays empty, so destroy succeeds regardless. That stops being true the
  # moment something starts uploading real audit events here.
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "audit_log" {
  # Object Lock requires versioning; also gives us the "append-only, can't
  # silently overwrite" property even before the lock's retention kicks in.
  bucket = aws_s3_bucket.audit_log.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_object_lock_configuration" "audit_log" {
  bucket = aws_s3_bucket.audit_log.id
  rule {
    default_retention {
      mode = "COMPLIANCE" # N18: not even the account root can delete before retention expires
      days = local.retention_days
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit_log" {
  bucket = aws_s3_bucket.audit_log.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
  }
}

resource "aws_s3_bucket_public_access_block" "audit_log" {
  bucket                  = aws_s3_bucket.audit_log.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- CloudTrail: a separate, un-locked delivery bucket for the trail
# itself. Object Lock and CloudTrail's own object-naming/ACL requirements
# don't mix well, so the trail writes here and the *application* audit log
# (JSONL events from core/audit/log.py) is what lands in the locked bucket
# above via the app's own write path, not via CloudTrail.

resource "aws_s3_bucket" "cloudtrail_logs" {
  bucket = "${var.project}-cloudtrail-logs-${data.aws_caller_identity.current.account_id}"
  # Unlike audit_log, this one WILL be non-empty within minutes of the trail
  # going live (CloudTrail delivers log files on its own schedule) —
  # force_destroy is load-bearing here, not just defensive.
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "cloudtrail_logs" {
  bucket                  = aws_s3_bucket.cloudtrail_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_iam_policy_document" "cloudtrail_bucket" {
  statement {
    sid       = "AWSCloudTrailAclCheck"
    effect    = "Allow"
    actions   = ["s3:GetBucketAcl"]
    resources = [aws_s3_bucket.cloudtrail_logs.arn]
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
  }
  statement {
    sid       = "AWSCloudTrailWrite"
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.cloudtrail_logs.arn}/AWSLogs/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["bucket-owner-full-control"]
    }
  }
}

resource "aws_s3_bucket_policy" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id
  policy = data.aws_iam_policy_document.cloudtrail_bucket.json
}

resource "aws_cloudtrail" "this" {
  name                          = "${var.project}-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail_logs.id
  include_global_service_events = false
  is_multi_region_trail         = false # N17: single-region by design
  enable_log_file_validation    = true

  # F8.2 correction: "CloudTrail data events on the vault table and KMS
  # key" originally tried to register the KMS key as a `data_resource` —
  # that's invalid. AWS::KMS::Key is not a data-event resource type at all
  # (this basic event-selector API only accepts DynamoDB::Table,
  # Lambda::Function, S3::Object; confirmed by the provider rejecting it
  # outright on apply). KMS key usage (Encrypt/Decrypt/GenerateDataKey) is
  # a *management* event in CloudTrail's model, not a data event — so it's
  # captured via `include_management_events = true` below instead, applied
  # trail-wide rather than scoped to this one key (basic event selectors
  # can't scope management events to a single resource ARN).
  event_selector {
    read_write_type           = "All"
    include_management_events = true

    data_resource {
      type   = "AWS::DynamoDB::Table"
      values = [var.vault_table_arn]
    }
  }

  depends_on = [aws_s3_bucket_policy.cloudtrail_logs]
}

output "audit_log_bucket" {
  value = aws_s3_bucket.audit_log.id
}
