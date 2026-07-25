variable "project" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "vault_rw_policy_arn" {
  type = string
}

variable "data_kms_key_arn" {
  type = string
}
