# §11 API row: "API Gateway HTTP API + Lambda | Presigned S3 upload".
#
# NOT fully realized here: the backend (backend/app/) currently runs as one
# FastAPI process with an in-process background task for the pipeline
# (app/pipeline.py) — see that file's docstring for how its function
# boundaries map onto Step Functions states. Lifting it into this
# Lambda+SQS+Step-Functions shape is Phase 3 work; what's below is the
# resource skeleton that work targets, wired for least-privilege and no
# hardcoded secrets, not a working deployment (there is no Lambda deployment
# package build step here — see the archive_file placeholder).

resource "aws_sqs_queue" "dlq" {
  name                      = "${var.project}-ingest-dlq"
  message_retention_seconds = 1209600 # 14 days
}

resource "aws_sqs_queue" "ingest" {
  name                       = "${var.project}-ingest"
  visibility_timeout_seconds = 120 # > N2's 30s local-inference p95, with headroom for escalation
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3
  })
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "api_lambda" {
  name               = "${var.project}-api-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "api_lambda_vault" {
  role       = aws_iam_role.api_lambda.name
  policy_arn = var.vault_rw_policy_arn
}

resource "aws_iam_role_policy_attachment" "api_lambda_basic" {
  role       = aws_iam_role.api_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

data "aws_iam_policy_document" "api_lambda_extra" {
  statement {
    sid       = "SqsSend"
    effect    = "Allow"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.ingest.arn]
  }
  statement {
    sid       = "DataKeyUse"
    effect    = "Allow"
    actions   = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"]
    resources = [var.data_kms_key_arn]
  }
  statement {
    sid     = "SecretsRead"
    effect  = "Allow"
    actions = ["secretsmanager:GetSecretValue"]
    # N8: scoped to this project's secret path, not "*".
    resources = ["arn:aws:secretsmanager:*:*:secret:${var.project}/*"]
  }
}

resource "aws_iam_policy" "api_lambda_extra" {
  name   = "${var.project}-api-lambda-extra"
  policy = data.aws_iam_policy_document.api_lambda_extra.json
}

resource "aws_iam_role_policy_attachment" "api_lambda_extra" {
  role       = aws_iam_role.api_lambda.name
  policy_arn = aws_iam_policy.api_lambda_extra.arn
}

# Placeholder deployment package. Real build: package backend/app plus a
# Mangum ASGI adapter and dependencies (or a container image Lambda, given
# the dependency list in backend/requirements.txt) via CI, not `terraform
# apply` — this data source exists so the resource graph is valid, not as
# the intended packaging mechanism.
data "archive_file" "api_lambda_placeholder" {
  type        = "zip"
  output_path = "${path.module}/.build/placeholder.zip"
  source {
    content  = "# placeholder — replace with CI-built Lambda package"
    filename = "placeholder.txt"
  }
}

resource "aws_lambda_function" "api" {
  function_name = "${var.project}-api"
  role          = aws_iam_role.api_lambda.arn
  handler       = "app.lambda_handler.handler" # TODO: Mangum-wrapped FastAPI entrypoint, not yet written
  runtime       = "python3.12"
  timeout       = 30
  filename      = data.archive_file.api_lambda_placeholder.output_path

  environment {
    variables = {
      SENTINEL_AWS_REGION                     = "ap-southeast-3"
      SENTINEL_INGEST_QUEUE_URL               = aws_sqs_queue.ingest.url
      SENTINEL_ESCALATION_KILL_SWITCH_DEFAULT = "true"
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }
}

resource "aws_security_group" "lambda" {
  name_prefix = "${var.project}-api-lambda-"
  vpc_id      = var.vpc_id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"] # scoped down by the VPC's own routing (private subnet, no direct IGW)
  }
}

resource "aws_apigatewayv2_api" "this" {
  name          = "${var.project}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "proxy" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "ANY /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/*"
}

output "invoke_url" {
  value = aws_apigatewayv2_stage.default.invoke_url
}

output "ingest_queue_url" {
  value = aws_sqs_queue.ingest.url
}

output "ingest_queue_arn" {
  value = aws_sqs_queue.ingest.arn
}
