# N7/N11: customer-managed KMS keys, rotation enabled. Separate keys for the
# vault (F3.4) and general data (raw docs, tokenized docs, audit log) so a
# vault key compromise/rotation event has a blast radius limited to the
# thing that actually reverses pseudonymization.

resource "aws_kms_key" "vault" {
  description             = "Sentinel token vault CMK (F3.4)"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}

resource "aws_kms_alias" "vault" {
  name          = "alias/${var.project}-vault"
  target_key_id = aws_kms_key.vault.key_id
}

resource "aws_kms_key" "data" {
  description             = "Sentinel general data CMK (raw docs, tokenized docs, audit log)"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}

resource "aws_kms_alias" "data" {
  name          = "alias/${var.project}-data"
  target_key_id = aws_kms_key.data.key_id
}
