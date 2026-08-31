resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-db-subnets"
  subnet_ids = var.subnet_ids
  tags       = var.tags
}

resource "aws_security_group" "db" {
  name_prefix = "${var.name_prefix}-db-"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${var.name_prefix}-db-sg" })
}

resource "aws_vpc_security_group_ingress_rule" "db_from_app" {
  for_each                     = { for idx, sg_id in var.allowed_security_group_ids : idx => sg_id }
  security_group_id            = aws_security_group.db.id
  referenced_security_group_id = each.value
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "db_all_out" {
  security_group_id = aws_security_group.db.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "random_password" "master" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "db_credentials" {
  name = "${var.name_prefix}/rds/master-credentials"
  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = var.master_username
    password = random_password.master.result
    # Composed here (not in the ECS task def) because this is the only place
    # username + password + the RDS-assigned endpoint are all known at once --
    # ECS's `secrets` block can only pull one JSON key per env var verbatim,
    # it can't concatenate fields into a connection string itself.
    database_url = "postgresql+psycopg2://${var.master_username}:${random_password.master.result}@${aws_db_instance.this.endpoint}/${var.db_name}"
  })
}

resource "aws_db_instance" "this" {
  identifier                = "${var.name_prefix}-postgres"
  engine                    = "postgres"
  engine_version            = "16.15"
  instance_class            = var.instance_class
  allocated_storage         = var.allocated_storage
  storage_encrypted         = true
  db_name                   = var.db_name
  username                  = var.master_username
  password                  = random_password.master.result
  db_subnet_group_name      = aws_db_subnet_group.this.name
  vpc_security_group_ids    = [aws_security_group.db.id]
  publicly_accessible       = false
  multi_az                  = var.multi_az
  backup_retention_period   = 7
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.name_prefix}-postgres-final"
  deletion_protection       = true
  tags                      = var.tags
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

variable "subnet_ids" {
  type = list(string)
}

variable "allowed_security_group_ids" {
  type        = list(string)
  description = "Security groups (e.g. the backend ECS service SG) permitted to reach Postgres on 5432"
}

variable "instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "allocated_storage" {
  type    = number
  default = 20
}

variable "db_name" {
  type    = string
  default = "bpr_compliance"
}

variable "master_username" {
  type    = string
  default = "bpr_admin"
}

variable "multi_az" {
  type        = bool
  default     = false
  description = "Single-AZ is acceptable for this phase per PRD NFRs; flip to true for prod if the budget allows"
}

variable "tags" {
  type    = map(string)
  default = {}
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "endpoint" {
  value = aws_db_instance.this.endpoint
}

output "security_group_id" {
  value = aws_security_group.db.id
}

output "credentials_secret_arn" {
  value = aws_secretsmanager_secret.db_credentials.arn
}
