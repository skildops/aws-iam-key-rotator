data "aws_caller_identity" "current" {}

locals {
  account_id           = data.aws_caller_identity.current.account_id
  lambda_assume_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow"
    }
  ]
}
EOF
}

# DyanmoDb table for storing old keys
resource "aws_dynamodb_table" "iam_key_rotator" {
  # checkov:skip=CKV_AWS_119: SSE is enabled by default using AWS owned SSE. If required customer owned key can be used
  # checkov:skip=CKV_AWS_28: Enabling PITR depends on user
  name         = var.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user"
  range_key    = "ak"

  attribute {
    name = "user"
    type = "S"
  }

  attribute {
    name = "ak"
    type = "S"
  }

  ttl {
    attribute_name = "delete_on"
    enabled        = true
  }

  server_side_encryption {
    enabled     = var.enable_sse
    kms_key_arn = var.kms_key_arn
  }

  point_in_time_recovery {
    enabled = var.enable_pitr
  }

  stream_enabled   = true
  stream_view_type = "OLD_IMAGE"

  tags = var.tags
}

# ====== Lambda Layers =====
resource "aws_lambda_layer_version" "pytz" {
  filename            = "pytz.zip"
  source_code_hash    = filebase64sha256("pytz.zip")
  description         = "https://pypi.org/project/pytz/"
  layer_name          = "pytz"
  compatible_runtimes = ["python3.6", "python3.7", "python3.8", "python3.9"]

}

resource "aws_lambda_layer_version" "requests" {
  filename            = "requests.zip"
  source_code_hash    = filebase64sha256("requests.zip")
  description         = "https://pypi.org/project/requests/"
  layer_name          = "requests"
  compatible_runtimes = ["python3.6", "python3.7", "python3.8", "python3.9"]
}

resource "aws_lambda_layer_version" "cryptography" {
  filename            = "cryptography.zip"
  source_code_hash    = filebase64sha256("cryptography.zip")
  description         = "https://cryptography.io/en/latest/"
  layer_name          = "cryptography"
  compatible_runtimes = ["python3.6", "python3.7", "python3.8", "python3.9"]
}

# ====== iam-key-creator ======
resource "aws_iam_role" "iam_key_creator" {
  name                  = var.key_creator_role_name
  assume_role_policy    = local.lambda_assume_policy
  force_detach_policies = true
  tags                  = var.tags
}

resource "aws_iam_role_policy" "iam_key_creator_policy" {
  name = "${var.key_creator_role_name}-policy"
  role = aws_iam_role.iam_key_creator.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = flatten([
      [{
        Effect = "Allow"
        Action = [
          "iam:ListUserTags",
          "iam:ListAccessKeys",
          "iam:ListUsers",
          "iam:CreateAccessKey",
          "iam:ListAccountAliases"
        ]
        Resource = ["*"]
        },
        {
          Effect = "Allow"
          Action = [
            "dynamodb:PutItem"
          ]
          Resource = [aws_dynamodb_table.iam_key_rotator.arn]
        },
        {
          Effect = "Allow"
          Action = [
            "ssm:GetParameter"
          ]
          Resource = ["arn:aws:ssm:${var.region}:${local.account_id}:parameter/ikr/*"]
      }],
      var.encrypt_key_pair ? [{
        Effect   = "Allow"
        Action   = ["ssm:PutParameter"]
        Resource = ["arn:aws:ssm:${var.region}:${local.account_id}:parameter/ikr/*"]
      }] : [],
      var.mail_client == "ses" ? [{
        Effect   = "Allow"
        Action   = ["ses:SendEmail"]
        Resource = ["*"]
      }] : []
    ])
  })
}

resource "aws_iam_role_policy_attachment" "iam_key_creator_logs" {
  role       = aws_iam_role.iam_key_creator.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_ssm_parameter" "mailgun" {
  count = var.mail_client == "mailgun" ? 1 : 0
  name  = "/ikr/secret/mailgun"
  value = var.mailgun_api_key
  type  = "SecureString"
  tags  = var.tags
}

resource "aws_ssm_parameter" "smtp_password" {
  count = var.mail_client == "smtp" ? 1 : 0
  name  = "/ikr/secret/smtp"
  value = var.smtp_password
  type  = "SecureString"
  tags  = var.tags
}

resource "aws_cloudwatch_log_group" "iam_key_creator" {
  # checkov:skip=CKV_AWS_338: Retention period is user dependant
  name              = "/aws/lambda/${var.key_creator_function_name}"
  retention_in_days = var.cw_log_group_retention
  kms_key_id        = var.cw_logs_kms_key_arn
  tags              = var.tags
}

resource "aws_lambda_function" "iam_key_creator" {
  # checkov:skip=CKV_AWS_50: Enabling X-Ray tracing depends on user
  # checkov:skip=CKV_AWS_115: Setting reserved concurrent execution depends on user
  # checkov:skip=CKV_AWS_116: DLQ not required
  # checkov:skip=CKV_AWS_117: VPC deployment not required
  # checkov:skip=CKV_AWS_173: By default environment variables are encrypted at rest
  # checkov:skip=CKV_AWS_272: Code-signing not required
  function_name    = var.key_creator_function_name
  description      = "Create new access key pair for IAM user"
  role             = aws_iam_role.iam_key_creator.arn
  filename         = data.archive_file.creator.output_path
  source_code_hash = data.archive_file.creator.output_base64sha256
  handler          = "creator.handler"
  runtime          = var.lambda_runtime

  memory_size                    = var.function_memory_size
  timeout                        = var.function_timeout
  reserved_concurrent_executions = var.reserved_concurrent_executions

  layers = [aws_lambda_layer_version.pytz.arn, aws_lambda_layer_version.requests.arn, aws_lambda_layer_version.cryptography.arn]

  tracing_config {
    mode = var.xray_tracing_mode
  }

  environment {
    variables = {
      IAM_KEY_ROTATOR_TABLE   = aws_dynamodb_table.iam_key_rotator.name
      ROTATE_AFTER_DAYS       = var.rotate_after_days
      DELETE_AFTER_DAYS       = var.delete_after_days
      ENCRYPT_KEY_PAIR        = var.encrypt_key_pair
      MAIL_CLIENT             = var.mail_client
      MAIL_FROM               = var.mail_from
      SMTP_PROTOCOL           = var.smtp_protocol
      SMTP_PORT               = var.smtp_port
      SMTP_SERVER             = var.smtp_server
      SMTP_PASSWORD_PARAMETER = var.mail_client == "smtp" ? join(",", aws_ssm_parameter.smtp_password.*.name) : null
      MAILGUN_API_URL         = var.mailgun_api_url
      MAILGUN_API_KEY_NAME    = var.mail_client == "mailgun" ? join(",", aws_ssm_parameter.mailgun.*.name) : null
      ACCOUNT_ID              = local.account_id
    }
  }

  tags = var.tags
}

resource "aws_cloudwatch_event_rule" "iam_key_creator" {
  name                = "IAMAccessKeyCreator"
  description         = "Triggers a lambda function periodically which creates a set of new access key pair for a user if the existing key pair is X days old"
  state               = "ENABLED"
  schedule_expression = "cron(${var.cron_expression})"
  tags                = var.tags
}

resource "aws_cloudwatch_event_target" "iam_key_creator" {
  rule      = aws_cloudwatch_event_rule.iam_key_creator.name
  target_id = "TriggerIAMKeyCreatorLambda"
  arn       = aws_lambda_function.iam_key_creator.arn
}

resource "aws_lambda_permission" "iam_key_creator" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.iam_key_creator.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.iam_key_creator.arn
}

# ====== iam-key-destructor ======
resource "aws_iam_role" "iam_key_destructor" {
  name                  = var.key_destructor_role_name
  assume_role_policy    = local.lambda_assume_policy
  force_detach_policies = true
  tags                  = var.tags
}

resource "aws_iam_role_policy" "iam_key_destructor_policy" {
  name = "${var.key_destructor_role_name}-policy"
  role = aws_iam_role.iam_key_destructor.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = flatten([
      [{
        Effect = "Allow"
        Action = [
          "iam:DeleteAccessKey",
          "iam:ListAccountAliases"
        ]
        Resource = ["*"]
        },
        {
          Effect = "Allow"
          Action = [
            "dynamodb:PutItem"
          ]
          Resource = [aws_dynamodb_table.iam_key_rotator.arn]
        },
        {
          Effect = "Allow"
          Action = [
            "dynamodb:DescribeStream",
            "dynamodb:GetRecords",
            "dynamodb:GetShardIterator",
            "dynamodb:ListShards",
            "dynamodb:ListStreams"
          ]
          Resource = [aws_dynamodb_table.iam_key_rotator.stream_arn]
      }],
      var.encrypt_key_pair ? [{
        Effect   = "Allow"
        Action   = ["ssm:DeleteParameter"]
        Resource = ["arn:aws:ssm:${var.region}:${local.account_id}:parameter/ikr/secret/iam/*"]
      }] : [],
      var.mail_client == "ses" ? [{
        Effect   = "Allow"
        Action   = ["ses:SendEmail"]
        Resource = ["*"]
      }] : []
    ])
  })
}

resource "aws_iam_role_policy_attachment" "iam_key_destructor_logs" {
  role       = aws_iam_role.iam_key_destructor.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_cloudwatch_log_group" "iam_key_destructor" {
  # checkov:skip=CKV_AWS_338: Retention period is user dependant
  name              = "/aws/lambda/${var.key_destructor_function_name}"
  retention_in_days = var.cw_log_group_retention
  kms_key_id        = var.cw_logs_kms_key_arn
  tags              = var.tags
}

resource "aws_lambda_function" "iam_key_destructor" {
  # checkov:skip=CKV_AWS_50: Enabling X-Ray tracing depends on user
  # checkov:skip=CKV_AWS_115: Setting reserved concurrent execution depends on user
  # checkov:skip=CKV_AWS_116: DLQ not required
  # checkov:skip=CKV_AWS_117: VPC deployment not required
  # checkov:skip=CKV_AWS_173: By default environment variables are encrypted at rest
  # checkov:skip=CKV_AWS_272: Code-signing not required
  function_name    = var.key_destructor_function_name
  description      = "Delete existing access key pair for IAM user"
  role             = aws_iam_role.iam_key_destructor.arn
  filename         = data.archive_file.destructor.output_path
  source_code_hash = data.archive_file.destructor.output_base64sha256
  handler          = "destructor.handler"
  runtime          = var.lambda_runtime

  memory_size                    = var.function_memory_size
  timeout                        = var.function_timeout
  reserved_concurrent_executions = var.reserved_concurrent_executions

  layers = [aws_lambda_layer_version.requests.arn]

  tracing_config {
    mode = var.xray_tracing_mode
  }

  environment {
    variables = {
      IAM_KEY_ROTATOR_TABLE   = aws_dynamodb_table.iam_key_rotator.name
      RETRY_AFTER_MINS        = var.retry_after_mins
      MAIL_CLIENT             = var.mail_client
      MAIL_FROM               = var.mail_from
      SMTP_PROTOCOL           = var.smtp_protocol
      SMTP_PORT               = var.smtp_port
      SMTP_SERVER             = var.smtp_server
      SMTP_PASSWORD_PARAMETER = var.mail_client == "smtp" ? join(",", aws_ssm_parameter.smtp_password.*.name) : null
      MAILGUN_API_URL         = var.mailgun_api_url
      MAILGUN_API_KEY_NAME    = var.mail_client == "mailgun" ? join(",", aws_ssm_parameter.mailgun.*.name) : null
      ACCOUNT_ID              = local.account_id
    }
  }

  tags = var.tags
}

resource "aws_lambda_event_source_mapping" "iam_key_destructor" {
  event_source_arn       = aws_dynamodb_table.iam_key_rotator.stream_arn
  function_name          = aws_lambda_function.iam_key_destructor.arn
  starting_position      = "LATEST"
  maximum_retry_attempts = 0

  depends_on = [aws_iam_role_policy.iam_key_destructor_policy]
}
