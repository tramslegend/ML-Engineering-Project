locals {
  azs = ["${var.aws_region}a", "${var.aws_region}b"]

  common_tags = {
    Project     = "bpr-compliance-copilot"
    Environment = "dev"
    ManagedBy   = "terraform"
  }
}

module "vpc" {
  source = "../../modules/vpc"

  name_prefix                    = var.name_prefix
  azs                            = local.azs
  public_subnet_cidrs            = ["10.20.0.0/24", "10.20.1.0/24"]
  private_app_subnet_cidrs       = ["10.20.10.0/24", "10.20.11.0/24"]
  private_inference_subnet_cidrs = ["10.20.20.0/24", "10.20.21.0/24"]
  private_db_subnet_cidrs        = ["10.20.30.0/24", "10.20.31.0/24"]
  tags                           = local.common_tags
}

module "ecr" {
  source      = "../../modules/ecr"
  name_prefix = var.name_prefix
  tags        = local.common_tags
}

module "secrets" {
  source           = "../../modules/secrets"
  name_prefix      = var.name_prefix
  jwt_secret       = var.jwt_secret
  deepseek_api_key = var.deepseek_api_key
  tags             = local.common_tags
}

module "alb" {
  source            = "../../modules/alb"
  name_prefix       = var.name_prefix
  vpc_id            = module.vpc.vpc_id
  public_subnet_ids = module.vpc.public_subnet_ids
  tags              = local.common_tags
}

module "iam" {
  source              = "../../modules/iam"
  name_prefix         = var.name_prefix
  db_secret_arn       = module.rds.credentials_secret_arn
  app_secret_arn      = module.secrets.secret_arn
  ecr_repository_arns = values(module.ecr.repository_urls)
  tags                = local.common_tags
}

module "rds" {
  source                     = "../../modules/rds"
  name_prefix                = var.name_prefix
  vpc_id                     = module.vpc.vpc_id
  subnet_ids                 = module.vpc.private_db_subnet_ids
  allowed_security_group_ids = [module.ecs.backend_security_group_id]
  multi_az                   = false # single-AZ acceptable for this phase per PRD NFR
  tags                       = local.common_tags
}

module "ecs" {
  source = "../../modules/ecs"

  name_prefix                 = var.name_prefix
  vpc_id                      = module.vpc.vpc_id
  private_app_subnet_ids      = module.vpc.private_app_subnet_ids
  alb_security_group_id       = module.alb.security_group_id
  alb_target_group_arn        = module.alb.backend_target_group_arn
  alb_listener_arn            = module.alb.http_listener_arn # swap for the HTTPS listener once a cert/domain exists
  alb_arn_suffix              = module.alb.alb_arn_suffix
  alb_target_group_arn_suffix = module.alb.backend_target_group_arn_suffix
  execution_role_arn          = module.iam.execution_role_arn
  task_role_arn               = module.iam.task_role_arn
  backend_image               = "${module.ecr.repository_urls["backend-api"]}:${var.backend_image_tag}"
  db_secret_arn               = module.rds.credentials_secret_arn
  app_secret_arn              = module.secrets.secret_arn
  cors_origins_json           = jsonencode(["https://${module.cloudfront.distribution_domain_name}"])
  desired_count               = 2
  min_capacity                = 2
  max_capacity                = 4
  tags                        = local.common_tags
}

resource "aws_s3_bucket" "frontend" {
  bucket = "${var.name_prefix}-frontend"
  tags   = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = false # CloudFront OAC bucket policy needs this open; ACLs stay blocked
  ignore_public_acls      = true
  restrict_public_buckets = false
}

module "cloudfront" {
  source = "../../modules/cloudfront"

  name_prefix                          = var.name_prefix
  frontend_bucket_regional_domain_name = aws_s3_bucket.frontend.bucket_regional_domain_name
  frontend_bucket_id                   = aws_s3_bucket.frontend.id
  tags                                 = local.common_tags

  depends_on = [aws_s3_bucket_public_access_block.frontend]
}

# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------

variable "aws_region" {
  type    = string
  default = "ap-southeast-3"
}

variable "name_prefix" {
  type    = string
  default = "bpr-compliance-dev"
}

variable "jwt_secret" {
  type      = string
  sensitive = true
}

variable "deepseek_api_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "backend_image_tag" {
  type    = string
  default = "latest"
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "alb_dns_name" {
  value = module.alb.alb_dns_name
}

output "cloudfront_domain_name" {
  value = module.cloudfront.distribution_domain_name
}

output "rds_endpoint" {
  value     = module.rds.endpoint
  sensitive = true
}

output "ecr_repository_urls" {
  value = module.ecr.repository_urls
}
