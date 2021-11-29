variable "region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region in which you want to create resources"
}

variable "profile" {
  type        = string
  default     = null
  description = "AWS CLI profile to use as authentication method"
}

variable "access_key" {
  type        = string
  default     = null
  description = "AWS access key to use as authentication method"
}

variable "secret_key" {
  type        = string
  default     = null
  description = "AWS secret key to use as authentication method"
}

variable "session_token" {
  type        = string
  default     = null
  description = "AWS session token to use as authentication method"
}

variable "table_name" {
  type        = string
  default     = "iam-key-rotator"
  description = "Name of dynamodb table to store access keys to be deleted"
}

variable "enable_sse" {
  type        = bool
  default     = true
  description = "Whether to enable server-side encryption"
}

variable "kms_key_arn" {
  type        = string
  default     = null
  description = "ARN of customer owned CMK to use instead of AWS owned key"
}

variable "enable_pitr" {
  type        = bool
  default     = false
  description = "Enable point-in time recovery for dynamodb table"
}

variable "key_creator_role_name" {
  type        = string
  default     = "iam-key-creator"
  description = "Name for IAM role to assocaite with key creator lambda function"
}

variable "key_creator_function_name" {
  type        = string
  default     = "iam-key-creator"
  description = "Name for lambda function responsible for creating new access key pair"
}

variable "key_destructor_role_name" {
  type        = string
  default     = "iam-key-destructor"
  description = "Name for IAM role to assocaite with key destructor lambda function"
}

variable "key_destructor_function_name" {
  type        = string
  default     = "iam-key-destructor"
  description = "Name for lambda function responsible for deleting existing access key pair"
}

variable "cron_expression" {
  type        = string
  default     = "0 12 * * ? *"
  description = "[CRON expression](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-schedule-expressions.html) to determine how frequently `key creator` function will be invoked to check if new key pair needs to be generated for an IAM user"
}

variable "lambda_runtime" {
  type        = string
  default     = "python3.8"
  description = "Lambda runtime to use for code execution for both creator and destructor function"
}

variable "function_memory_size" {
  type        = number
  default     = 128
  description = "Amount of memory to allocate to both creator and destructor function"
}

variable "function_timeout" {
  type        = number
  default     = 10
  description = "Timeout to set for both creator and destructor function"
}

variable "reserved_concurrent_executions" {
  type        = number
  default     = -1
  description = "Amount of reserved concurrent executions for this lambda function. A value of `0` disables lambda from being triggered and `-1` removes any concurrency limitations"
}

variable "xray_tracing_mode" {
  type        = string
  default     = "PassThrough"
  description = "Whether to sample and trace a subset of incoming requests with AWS X-Ray. **Possible values:** `PassThrough` and `Active`"
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Key value pair to assign to resources"
}

variable "rotate_after_days" {
  type        = number
  default     = 85
  description = "Days after which a new access key pair should be generated. **Note:** If `IKR:ROTATE_AFTER_DAYS` tag is set for the IAM user, this is ignored"
}

variable "delete_after_days" {
  type        = number
  default     = 5
  description = "No. of days to wait for deleting existing key pair after a new key pair is generated. **Note:** If `IKR:DELETE_AFTER_DAYS` tag is set for the IAM user, this is ignored"
}

variable "retry_after_mins" {
  type        = number
  default     = 5
  description = "In case lambda fails to delete the old key, how long should it wait before the next try"
}

variable "mail_client" {
  type        = string
  default     = "ses"
  description = "Mail client to use. **Supported Clients:** smtp, ses and mailgun"
}

variable "mail_from" {
  type        = string
  description = "Email address which should be used for sending mails. **Note:** Prior setup of mail client is required"
}

variable "smtp_protocol" {
  type        = string
  default     = null
  description = "Security protocol to use for SMTP connection. **Supported values:** ssl and tls. **Note:** Required if mail client is set to smtp"
}

variable "smtp_port" {
  type        = number
  default     = null
  description = "Secure port number to use for SMTP connection. **Note:** Required if mail client is set to smtp"
}

variable "smtp_server" {
  type        = string
  default     = null
  description = "Host name of SMTP server. **Note:** Required if mail client is set to smtp"
}

variable "smtp_password" {
  type        = string
  default     = null
  description = "Password to use with `mail_from` address for SMTP authentication. **Note:** Required if mail client is set to smtp"
}

variable "mailgun_api_url" {
  type        = string
  default     = null
  description = "Mailgun API url for sending email. **Note:** Required if mail client is set to mailgun"
}

variable "mailgun_api_key" {
  type        = string
  default     = null
  description = "API key for authenticating requests to Mailgun API. **Note:** Required if mail client is set to mailgun"
}
