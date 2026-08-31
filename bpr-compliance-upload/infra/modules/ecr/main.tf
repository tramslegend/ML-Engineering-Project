resource "aws_ecr_repository" "this" {
  for_each             = toset(var.repository_names)
  name                 = "${var.name_prefix}-${each.value}"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = var.tags
}

resource "aws_ecr_lifecycle_policy" "expire_untagged" {
  for_each   = aws_ecr_repository.this
  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Expire untagged images after 14 days"
      selection = {
        tagStatus   = "untagged"
        countType   = "sinceImagePushed"
        countUnit   = "days"
        countNumber = 14
      }
      action = { type = "expire" }
    }]
  })
}

# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------

variable "name_prefix" {
  type = string
}

variable "repository_names" {
  type    = list(string)
  default = ["backend-api", "agent-worker"]
}

variable "tags" {
  type    = map(string)
  default = {}
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "repository_urls" {
  value = { for k, v in aws_ecr_repository.this : k => v.repository_url }
}
