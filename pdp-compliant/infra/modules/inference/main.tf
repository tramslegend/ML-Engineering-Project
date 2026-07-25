# §11: "Local inference | ECS Fargate or EC2 ASG, CPU | 4B at Q4_K_M needs
# no GPU." Both paths are defined; var.deployment_mode selects which set of
# resources is actually created (`count` gates below).
#
# F4.6 (hot-swap without redeploy): the model name is an SSM Parameter, read
# by the serving process at request time or on a short poll — NOT baked into
# the task definition's environment block or into EC2 user_data, because
# either of those would force a redeploy/replacement to change.

resource "aws_ssm_parameter" "local_inference_model" {
  name  = "/${var.project}/inference/model"
  type  = "String"
  value = var.local_inference_model
}

resource "aws_security_group" "inference" {
  name_prefix = "${var.project}-inference-"
  vpc_id      = var.vpc_id
  ingress {
    from_port   = 11434
    to_port     = 11434
    protocol    = "tcp"
    cidr_blocks = ["10.42.0.0/16"] # in-VPC only; not internet-facing
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# --- Fargate path ---

resource "aws_ecs_cluster" "this" {
  count = var.deployment_mode == "fargate" ? 1 : 0
  name  = "${var.project}-inference"
}

data "aws_iam_policy_document" "ecs_task_assume" {
  count = var.deployment_mode == "fargate" ? 1 : 0
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_task_execution" {
  count              = var.deployment_mode == "fargate" ? 1 : 0
  name               = "${var.project}-ecs-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume[0].json
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  count      = var.deployment_mode == "fargate" ? 1 : 0
  role       = aws_iam_role.ecs_task_execution[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_ecs_task_definition" "inference" {
  count                    = var.deployment_mode == "fargate" ? 1 : 0
  family                   = "${var.project}-inference"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "4096" # 4 vCPU, CPU-only per §11's cost rationale
  memory                   = "8192" # headroom above the ~2.5GB Q4_K_M footprint for KV cache
  execution_role_arn       = aws_iam_role.ecs_task_execution[0].arn

  # Model weights: "baked into a Packer AMI or synced from S3 with checksum
  # verification, never pulled from the internet on boot" (§11). For the
  # container path that means baking weights into the image at build time
  # (CI, not here) — this container_definitions block references an image
  # tag CI is responsible for producing, not a runtime download step.
  container_definitions = jsonencode([{
    name         = "inference"
    image        = "REPLACE_ME.dkr.ecr.${data.aws_region.current.name}.amazonaws.com/${var.project}-inference:latest"
    portMappings = [{ containerPort = 11434, protocol = "tcp" }]
    environment = [
      { name = "SENTINEL_LOCAL_INFERENCE_MODEL_SSM_PATH", value = aws_ssm_parameter.local_inference_model.name }
    ]
  }])
}

data "aws_region" "current" {}

resource "aws_ecs_service" "inference" {
  count           = var.deployment_mode == "fargate" ? 1 : 0
  name            = "${var.project}-inference"
  cluster         = aws_ecs_cluster.this[0].id
  task_definition = aws_ecs_task_definition.inference[0].arn
  desired_count   = 0 # N16: scales to zero when queue is empty; see aws_appautoscaling_* below
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [aws_security_group.inference.id]
  }
}

resource "aws_appautoscaling_target" "inference" {
  count              = var.deployment_mode == "fargate" ? 1 : 0
  max_capacity       = 3
  min_capacity       = 0
  resource_id        = "service/${aws_ecs_cluster.this[0].name}/${aws_ecs_service.inference[0].name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "scale_on_queue_depth" {
  count              = var.deployment_mode == "fargate" ? 1 : 0
  name               = "${var.project}-scale-on-queue-depth"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.inference[0].resource_id
  scalable_dimension = aws_appautoscaling_target.inference[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.inference[0].service_namespace

  target_tracking_scaling_policy_configuration {
    target_value = 5 # aim for <=5 in-flight messages per task
    customized_metric_specification {
      metric_name = "ApproximateNumberOfMessagesVisible"
      namespace   = "AWS/SQS"
      statistic   = "Average"
      dimensions {
        name  = "QueueName"
        value = split(":", var.ingest_queue_arn)[5]
      }
    }
    scale_in_cooldown  = 120
    scale_out_cooldown = 30
  }
}

# --- EC2 ASG path ---
# Included specifically to demonstrate the §11 Terraform practice: "AMI
# selected via data aws_ami with a name filter, never a hardcoded ID."

data "aws_ami" "al2023" {
  count       = var.deployment_mode == "ec2_asg" ? 1 : 0
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_iam_policy_document" "ec2_assume" {
  count = var.deployment_mode == "ec2_asg" ? 1 : 0
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2_inference" {
  count              = var.deployment_mode == "ec2_asg" ? 1 : 0
  name               = "${var.project}-ec2-inference"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume[0].json
}

resource "aws_iam_role_policy_attachment" "ec2_ssm" {
  count      = var.deployment_mode == "ec2_asg" ? 1 : 0
  role       = aws_iam_role.ec2_inference[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ec2_inference" {
  count = var.deployment_mode == "ec2_asg" ? 1 : 0
  name  = "${var.project}-ec2-inference"
  role  = aws_iam_role.ec2_inference[0].name
}

resource "aws_launch_template" "inference" {
  count         = var.deployment_mode == "ec2_asg" ? 1 : 0
  name_prefix   = "${var.project}-inference-"
  image_id      = data.aws_ami.al2023[0].id
  instance_type = "c7i.xlarge" # CPU-optimized, 4 vCPU class matching the Fargate sizing above

  iam_instance_profile {
    arn = aws_iam_instance_profile.ec2_inference[0].arn
  }

  vpc_security_group_ids = [aws_security_group.inference.id]

  # Static bootstrap only: installs the SSM agent poller that reads model
  # name / thresholds from Parameter Store on an interval. Volatile config
  # changes (model swap, thresholds) go through aws_ssm_parameter, NOT
  # through editing this user_data — editing user_data forces instance
  # replacement, which is exactly what §11 says to avoid.
  user_data = base64encode(<<-EOF
    #!/bin/bash
    # Placeholder bootstrap: pulls the CI-built inference server artifact
    # (with model weights already baked in per §11 — never downloaded here)
    # and starts a systemd timer that re-reads ${aws_ssm_parameter.local_inference_model.name}
    # on a short interval, so a parameter update takes effect without a
    # replacement/redeploy.
    echo "TODO: fetch inference server artifact, install systemd unit + SSM poll timer"
  EOF
  )

  tag_specifications {
    resource_type = "instance"
    tags          = { Name = "${var.project}-inference" }
  }
}

resource "aws_autoscaling_group" "inference" {
  count               = var.deployment_mode == "ec2_asg" ? 1 : 0
  name                = "${var.project}-inference"
  vpc_zone_identifier = var.private_subnet_ids
  min_size            = 0
  max_size            = 3
  desired_capacity    = 0 # N16: scales to zero; scaling policy analogous to the Fargate target-tracking above, omitted for brevity

  launch_template {
    id      = aws_launch_template.inference[0].id
    version = "$Latest"
  }
}

output "ssm_model_parameter_name" {
  value = aws_ssm_parameter.local_inference_model.name
}
