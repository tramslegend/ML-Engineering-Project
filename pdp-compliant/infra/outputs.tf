output "api_invoke_url" {
  value = module.api.invoke_url
}

output "frontend_cloudfront_domain" {
  value = module.frontend.cloudfront_domain
}

output "vault_table_name" {
  value = module.vault.table_name
}

output "audit_log_bucket" {
  value = module.audit.audit_log_bucket
}

output "github_actions_deploy_role_arn" {
  value = aws_iam_role.github_actions_deploy.arn
}
