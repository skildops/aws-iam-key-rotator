output "table_name" {
  value       = aws_dynamodb_table.iam_key_rotator.name
  description = "Name of dynamodb table created for storing access keys to be deleted"
}

output "key_creator_function_name" {
  value       = aws_lambda_function.iam_key_creator.function_name
  description = "Name of lambda function created to create a set of new key pair for IAM user"
}

output "key_destructor_function_name" {
  value       = aws_lambda_function.iam_key_destructor.function_name
  description = "Name of lambda function created to delete existing key pair which has reached its expiry"
}

output "cron_expression" {
  value       = aws_cloudwatch_event_rule.iam_key_creator.schedule_expression
  description = "Interval at which `key creator` function will be invoked"
}

output "mailgun_ssm_parameter_arn" {
  value       = var.mail_client == "mailgun" ? join(",", aws_ssm_parameter.mailgun.arn) : null
  description = "ARN of SSM parameter that stores mailgun API key. Available only if mail client is set to Mailgun"
}

output "smtp_ssm_parameter_arn" {
  value       = var.mail_client == "smtp" ? join(",", aws_ssm_parameter.smtp_password.arn) : null
  description = "ARN of SSM parameter that stores SMTP password. Available only if mail client is set to SMTP"
}
