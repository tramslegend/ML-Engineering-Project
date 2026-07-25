variable "project" {
  type = string
}

variable "api_domain" {
  description = "Domain the frontend's api.js should call in production; wired via a build-time config substitution, not baked into this module."
  type        = string
  default     = ""
}
