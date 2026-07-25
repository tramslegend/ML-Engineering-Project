variable "aws_region" {
  description = "All resources must live here per §2/§6.1 — jurisdiction is controlled by region selection, not model ownership."
  type        = string
  default     = "ap-southeast-3"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "project" {
  type    = string
  default = "sentinel"
}

variable "escalation_kill_switch_default" {
  description = "F5.6. Open question 6 in the PRD: should escalation be opt-in per deployment? Defaulting to true (egress OFF) here — flip explicitly per environment."
  type        = bool
  default     = true
}

variable "inference_deployment_mode" {
  description = "§11: 'ECS Fargate or EC2 ASG, CPU'. Fargate avoids AMI/instance lifecycle management; the EC2 path exists for cases where sustained CPU cost favors reserved/spot instances."
  type        = string
  default     = "fargate"
  validation {
    condition     = contains(["fargate", "ec2_asg"], var.inference_deployment_mode)
    error_message = "inference_deployment_mode must be 'fargate' or 'ec2_asg'."
  }
}

variable "budget_alarm_usd" {
  description = "N14: AWS Budgets alarm at USD 50 with notification."
  type        = number
  default     = 50
}

variable "idle_cost_target_usd" {
  description = "N13/M8: idle infra cost target, informational only — not enforced by Terraform, tracked via Cost Explorer / the budget alarm above."
  type        = number
  default     = 30
}

variable "budget_notification_email" {
  description = "Where the AWS Budgets alarm (N14) sends notifications."
  type        = string
  default     = "REPLACE_ME@example.com"
}

variable "escalation_provider_allowed_hosts" {
  description = "N12: egress restricted to declared provider endpoints. Domains the VPC egress policy allows for the escalation tier (Zone C)."
  type        = list(string)
  default     = ["api.deepseek.com", "generativelanguage.googleapis.com"]
}

variable "github_repo" {
  description = "N9: GitHub OIDC trust is scoped to this repo (org/name), never long-lived AWS credentials."
  type        = string
  default     = "REPLACE_ME/sentinel"
}
