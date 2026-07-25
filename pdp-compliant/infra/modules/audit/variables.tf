variable "project" {
  type = string
}

variable "kms_key_arn" {
  type = string
}

variable "vault_table_arn" {
  type = string
}

variable "retention_years" {
  description = "F8.1/N18: audit log immutable, retained 7 years by default."
  type        = number
  default     = 7
}
