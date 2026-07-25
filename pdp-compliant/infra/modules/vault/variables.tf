variable "project" {
  type = string
}

variable "kms_key_arn" {
  type = string
}

variable "point_in_time_recovery" {
  type    = bool
  default = true
}
