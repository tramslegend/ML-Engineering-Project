variable "project" {
  type = string
}

variable "deployment_mode" {
  type = string # "fargate" | "ec2_asg"
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "ingest_queue_arn" {
  type = string
}

variable "local_inference_model" {
  description = "F4.6: hot-swappable without redeploy — lives in SSM Parameter Store, not user_data/task-def env."
  type        = string
  default     = "sea-lion-v4-4b"
}
