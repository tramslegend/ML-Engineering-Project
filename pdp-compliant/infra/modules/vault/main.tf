# F3.4-F3.6: token vault as DynamoDB, SSE-KMS with a customer-managed key.
# §9 schema: subject_id, token, entity_type, real_value, created_at.

resource "aws_dynamodb_table" "vault" {
  name         = "${var.project}-vault"
  billing_mode = "PAY_PER_REQUEST" # N16: scales to zero-ish; no provisioned capacity to idle-pay for
  hash_key     = "token"

  attribute {
    name = "token"
    type = "S"
  }
  attribute {
    name = "subject_id"
    type = "S"
  }

  global_secondary_index {
    name            = "by_subject"
    hash_key        = "subject_id"
    projection_type = "ALL"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  point_in_time_recovery {
    enabled = var.point_in_time_recovery
  }
}

# F3.5: "No human IAM principal has read access in normal operation." This
# policy is written to be attached ONLY to the de-identification and
# re-identification service roles (see ../inference and root IAM wiring) —
# it is deliberately not a role definition itself, so it can't accidentally
# be attached to a broader principal by a future edit.
data "aws_iam_policy_document" "vault_rw" {
  statement {
    sid    = "VaultReadWrite"
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:Query",
      "dynamodb:DeleteItem", # required for F3.6 single-call erasure
    ]
    resources = [
      aws_dynamodb_table.vault.arn,
      "${aws_dynamodb_table.vault.arn}/index/*",
    ]
  }
  statement {
    sid       = "VaultKeyUse"
    effect    = "Allow"
    actions   = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"]
    resources = [var.kms_key_arn]
  }
}

resource "aws_iam_policy" "vault_rw" {
  name   = "${var.project}-vault-rw"
  policy = data.aws_iam_policy_document.vault_rw.json
}

output "table_name" {
  value = aws_dynamodb_table.vault.name
}

output "table_arn" {
  value = aws_dynamodb_table.vault.arn
}

output "rw_policy_arn" {
  value = aws_iam_policy.vault_rw.arn
}
