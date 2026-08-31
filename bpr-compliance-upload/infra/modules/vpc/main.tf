resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(var.tags, { Name = "${var.name_prefix}-vpc" })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name_prefix}-igw" })
}

resource "aws_subnet" "public" {
  count                   = length(var.public_subnet_cidrs)
  vpc_id                  = aws_vpc.this.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = var.azs[count.index]
  map_public_ip_on_launch = true
  tags                    = merge(var.tags, { Name = "${var.name_prefix}-public-${count.index}" })
}

resource "aws_subnet" "private_app" {
  count             = length(var.private_app_subnet_cidrs)
  vpc_id            = aws_vpc.this.id
  cidr_block        = var.private_app_subnet_cidrs[count.index]
  availability_zone = var.azs[count.index]
  tags              = merge(var.tags, { Name = "${var.name_prefix}-private-app-${count.index}" })
}

# No internet route is attached to this subnet group at all (see route table
# below) -- this is the air-gap boundary the PRD's LLM inference node must
# run inside.
resource "aws_subnet" "private_inference" {
  count             = length(var.private_inference_subnet_cidrs)
  vpc_id            = aws_vpc.this.id
  cidr_block        = var.private_inference_subnet_cidrs[count.index]
  availability_zone = var.azs[count.index]
  tags              = merge(var.tags, { Name = "${var.name_prefix}-private-inference-${count.index}" })
}

resource "aws_subnet" "private_db" {
  count             = length(var.private_db_subnet_cidrs)
  vpc_id            = aws_vpc.this.id
  cidr_block        = var.private_db_subnet_cidrs[count.index]
  availability_zone = var.azs[count.index]
  tags              = merge(var.tags, { Name = "${var.name_prefix}-private-db-${count.index}" })
}

resource "aws_eip" "nat" {
  count  = length(var.azs)
  domain = "vpc"
  tags   = merge(var.tags, { Name = "${var.name_prefix}-nat-eip-${count.index}" })
}

resource "aws_nat_gateway" "this" {
  count         = length(var.azs)
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags          = merge(var.tags, { Name = "${var.name_prefix}-nat-${count.index}" })
  depends_on    = [aws_internet_gateway.this]
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }
  tags = merge(var.tags, { Name = "${var.name_prefix}-public-rt" })
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# App tier: outbound via NAT (needs ECR pulls, Secrets Manager, CloudWatch).
resource "aws_route_table" "private_app" {
  count  = length(var.azs)
  vpc_id = aws_vpc.this.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this[count.index].id
  }
  tags = merge(var.tags, { Name = "${var.name_prefix}-private-app-rt-${count.index}" })
}

resource "aws_route_table_association" "private_app" {
  count          = length(aws_subnet.private_app)
  subnet_id      = aws_subnet.private_app[count.index].id
  route_table_id = aws_route_table.private_app[count.index].id
}

# Inference tier: deliberately NO route to the NAT gateway or IGW. Only a
# local VPC route (implicit, added by AWS automatically) exists, so traffic
# can reach the DB/app tiers inside the VPC but nothing external.
resource "aws_route_table" "private_inference" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name_prefix}-private-inference-rt-noegress" })
}

resource "aws_route_table_association" "private_inference" {
  count          = length(aws_subnet.private_inference)
  subnet_id      = aws_subnet.private_inference[count.index].id
  route_table_id = aws_route_table.private_inference.id
}

resource "aws_route_table" "private_db" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name_prefix}-private-db-rt-noegress" })
}

resource "aws_route_table_association" "private_db" {
  count          = length(aws_subnet.private_db)
  subnet_id      = aws_subnet.private_db[count.index].id
  route_table_id = aws_route_table.private_db.id
}

# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------

variable "name_prefix" {
  type = string
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "azs" {
  type        = list(string)
  description = "At least 2 AZs for the ALB/ECS multi-AZ requirement"
}

variable "public_subnet_cidrs" {
  type = list(string)
}

variable "private_app_subnet_cidrs" {
  type        = list(string)
  description = "Subnets for the FastAPI backend / ECS tasks (has NAT egress for ECR pulls, etc.)"
}

variable "private_inference_subnet_cidrs" {
  type        = list(string)
  description = "Isolated subnet for the self-hosted LLM inference node: no NAT, no internet route at all (PRD Security requirement)"
}

variable "private_db_subnet_cidrs" {
  type = list(string)
}

variable "tags" {
  type    = map(string)
  default = {}
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "vpc_id" {
  value = aws_vpc.this.id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "private_app_subnet_ids" {
  value = aws_subnet.private_app[*].id
}

output "private_inference_subnet_ids" {
  value = aws_subnet.private_inference[*].id
}

output "private_db_subnet_ids" {
  value = aws_subnet.private_db[*].id
}
