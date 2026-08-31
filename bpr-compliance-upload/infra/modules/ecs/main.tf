resource "aws_ecs_cluster" "this" {
  name = "${var.name_prefix}-cluster"
  tags = var.tags
}

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${var.name_prefix}-backend"
  retention_in_days = 30
  tags              = var.tags
}

resource "aws_security_group" "backend" {
  name_prefix = "${var.name_prefix}-backend-"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${var.name_prefix}-backend-sg" })
}

resource "aws_vpc_security_group_ingress_rule" "backend_from_alb" {
  security_group_id            = aws_security_group.backend.id
  referenced_security_group_id = var.alb_security_group_id
  from_port                    = 8000
  to_port                      = 8000
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "backend_all_out" {
  security_group_id = aws_security_group.backend.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.name_prefix}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([
    {
      name         = "backend-api"
      image        = var.backend_image
      portMappings = [{ containerPort = 8000, protocol = "tcp" }]
      # Real BPR_* names app/config.py's pydantic Settings actually reads --
      # the previous BPR_DATABASE_URL_BASE/BPR_DB_CREDENTIALS/BPR_APP_SECRETS
      # names matched nothing in the app, so the container would have started
      # but immediately failed to reach RDS and fallen back to every default
      # (including localhost CORS). use_mock_llm=true here is deliberate for
      # this demo deployment -- it keeps the deployed app fully self-contained
      # and not dependent on any external LLM provider's uptime/quota.
      environment = [
        { name = "BPR_CORS_ORIGINS", value = var.cors_origins_json },
        { name = "BPR_USE_MOCK_LLM", value = "true" },
        { name = "BPR_QUARANTINE_DIR", value = "/tmp/quarantine" },
      ]
      secrets = [
        { name = "BPR_DATABASE_URL", valueFrom = "${var.db_secret_arn}:database_url::" },
        { name = "BPR_JWT_SECRET", valueFrom = "${var.app_secret_arn}:jwt_secret::" },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.backend.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "backend"
        }
      }
    }
  ])

  tags = var.tags
}

data "aws_region" "current" {}

resource "aws_lb_listener_rule" "backend" {
  listener_arn = var.alb_listener_arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = var.alb_target_group_arn
  }

  condition {
    path_pattern {
      values = ["/*"]
    }
  }
}

resource "aws_ecs_service" "backend" {
  name            = "${var.name_prefix}-backend"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_app_subnet_ids
    security_groups = [aws_security_group.backend.id]
  }

  load_balancer {
    target_group_arn = var.alb_target_group_arn
    container_name   = "backend-api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener_rule.backend]
  tags       = var.tags
}

resource "aws_appautoscaling_target" "backend" {
  max_capacity       = var.max_capacity
  min_capacity       = var.min_capacity
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.backend.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# Scale out on CPU >70% (PRD §12) so the screening queue and report drafting
# stay responsive under a spike in concurrent officers/auditors.
resource "aws_appautoscaling_policy" "cpu" {
  name               = "${var.name_prefix}-backend-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.backend.resource_id
  scalable_dimension = aws_appautoscaling_target.backend.scalable_dimension
  service_namespace  = aws_appautoscaling_target.backend.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70
    scale_in_cooldown  = 120
    scale_out_cooldown = 60
  }
}

resource "aws_appautoscaling_policy" "request_count" {
  name               = "${var.name_prefix}-backend-request-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.backend.resource_id
  scalable_dimension = aws_appautoscaling_target.backend.scalable_dimension
  service_namespace  = aws_appautoscaling_target.backend.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ALBRequestCountPerTarget"
      resource_label         = "${var.alb_arn_suffix}/${var.alb_target_group_arn_suffix}"
    }
    target_value       = 1000
    scale_in_cooldown  = 120
    scale_out_cooldown = 60
  }
}

# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------

variable "name_prefix" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_app_subnet_ids" {
  type = list(string)
}

variable "alb_security_group_id" {
  type = string
}

variable "alb_target_group_arn" {
  type = string
}

variable "alb_arn_suffix" {
  type        = string
  description = "aws_lb.arn_suffix, used to build the ALBRequestCountPerTarget resource_label for autoscaling"
}

variable "alb_target_group_arn_suffix" {
  type = string
}

variable "alb_listener_arn" {
  type        = string
  description = "Listener this service's routing rule attaches to (environments/{dev,prod} wire the real HTTPS listener here)"
}

variable "execution_role_arn" {
  type = string
}

variable "task_role_arn" {
  type = string
}

variable "backend_image" {
  type        = string
  description = "Full ECR image URI:tag for the FastAPI backend"
}

variable "db_secret_arn" {
  type = string
}

variable "app_secret_arn" {
  type = string
}

variable "cors_origins_json" {
  type        = string
  description = "BPR_CORS_ORIGINS value -- a JSON array string, e.g. [\"https://xxx.cloudfront.net\"]"
}

variable "desired_count" {
  type    = number
  default = 2
}

variable "min_capacity" {
  type    = number
  default = 2
}

variable "max_capacity" {
  type    = number
  default = 6
}

variable "cpu" {
  type    = number
  default = 512
}

variable "memory" {
  type    = number
  default = 1024
}

variable "tags" {
  type    = map(string)
  default = {}
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "cluster_id" {
  value = aws_ecs_cluster.this.id
}

output "service_name" {
  value = aws_ecs_service.backend.name
}

output "backend_security_group_id" {
  value = aws_security_group.backend.id
}
