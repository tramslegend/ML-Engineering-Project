resource "aws_secretsmanager_secret" "app_secrets" {
  name = "${var.name_prefix}/app/secrets"
  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "app_secrets" {
  secret_id = aws_secretsmanager_secret.app_secrets.id
  secret_string = jsonencode({
    jwt_secret       = var.jwt_secret
    deepseek_api_key = var.deepseek_api_key
  })
}

# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------

variable "name_prefix" {
  type = string
}

variable "jwt_secret" {
  type      = string
  sensitive = true
}

variable "deepseek_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "secret_arn" {
  value = aws_secretsmanager_secret.app_secrets.arn
}
