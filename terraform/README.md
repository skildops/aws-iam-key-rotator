# IAM Key Rotator

![Test](https://img.shields.io/github/workflow/status/skildops/aws-iam-key-rotator/test/main?label=Test&style=for-the-badge) ![Checkov](https://img.shields.io/github/workflow/status/skildops/aws-iam-key-rotator/checkov/main?label=Checkov&style=for-the-badge)

This terraform module will deploy the following services:
- DynamoDB Table
- IAM Role
- IAM Role Policy
- CloudWatch Event
- Lambda

**Note:** You need to implement [remote backend](https://www.terraform.io/docs/language/settings/backends/index.html) by yourself and is recommended for state management.

## Requirements

| Name | Version |
|------|---------|
| aws | >= 3.42.0 |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| region | AWS region in which you want to create resources | `string` | `"us-east-1"` | no |
| profile | AWS CLI profile to use as authentication method | `string` | `null` | no |
| access_key | AWS access key to use as authentication method | `string` | `null` | no |
| secret_key | AWS secret key to use as authentication method | `string` | `null` | no |
| session_token | AWS session token to use as authentication method | `string` | `null` | no |
| table_name | Name of dynamodb table to store access keys to be deleted | `string` | `"iam-key-rotator"` | no |
| enable_sse | Whether to enable server-side encryption | `bool` | `true` | no |
| kms_key_arn | ARN of customer owned CMK to use instead of AWS owned key | `string` | `null` | no |
| enable_pitr | Enable point-in time recovery for dynamodb table | `bool` | `false` | no |
| key_creator_role_name | Name for IAM role to assocaite with key creator lambda function | `string` | `"iam-key-creator"` | no |
| key_creator_function_name | Name for lambda function responsible for creating new access key pair | `string` | `"iam-key-creator"` | no |
| key_destructor_role_name | Name for IAM role to assocaite with key destructor lambda function | `string` | `"iam-key-destructor"` | no |
| key_destructor_function_name | Name for lambda function responsible for deleting existing access key pair | `string` | `"iam-key-destructor"` | no |
| cron_expression | [CRON expression](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-schedule-expressions.html) to determine how frequently `key creator` function will be invoked to check if new key pair needs to be generated for an IAM user | `string` | `"0 12 * * ? *"` | no |
| lambda_runtime | Lambda runtime to use for code execution for both creator and destructor function | `string` | `"python3.8"` | no |
| function_memory_size | Amount of memory to allocate to both creator and destructor function | `number` | `128` | no |
| function_timeout | Timeout to set for both creator and destructor function | `number` | `10` | no |
| reserved_concurrent_executions | Amount of reserved concurrent executions for this lambda function. A value of `0` disables lambda from being triggered and `-1` removes any concurrency limitations | `number` | `-1` | no |
| xray_tracing_mode | Whether to sample and trace a subset of incoming requests with AWS X-Ray. **Possible values:** `PassThrough` and `Active` | `string` | `"PassThrough"` | no |
| tags | Key value pair to assign to resources | `map(string)` | `{}` | no |
| rotate_after_days | Days after which a new access key pair should be generated. **Note:** If `IKR:ROTATE_AFTER_DAYS` tag is set for the IAM user, this is ignored | `number` | `85` | no |
| delete_after_days | No. of days to wait for deleting existing key pair after a new key pair is generated. **Note:** If `IKR:DELETE_AFTER_DAYS` tag is set for the IAM user, this is ignored | `number` | `5` | no |
| retry_after_mins | In case lambda fails to delete the old key, how long should it wait before the next try | `number` | `5` | no |
| mail_client | Mail client to use. **Supported Clients:** smtp, ses and mailgun | `string` | `"ses"` | no |
| mail_from | Email address which should be used for sending mails. **Note:** Prior setup of mail client is required | `string` | n/a | yes |
| smtp_protocol | Security protocol to use for SMTP connection. **Supported values:** ssl and tls. **Note:** Required if mail client is set to smtp | `string` | `null` | no |
| smtp_port | Secure port number to use for SMTP connection. **Note:** Required if mail client is set to smtp | `number` | `null` | no |
| smtp_server | Host name of SMTP server. **Note:** Required if mail client is set to smtp | `string` | `null` | no |
| smtp_password | Password to use with `mail_from` address for SMTP authentication. **Note:** Required if mail client is set to smtp | `string` | `null` | no |
| mailgun_api_url | Mailgun API url for sending email. **Note:** Required if mail client is set to mailgun | `string` | `null` | no |
| mailgun_api_key | API key for authenticating requests to Mailgun API. **Note:** Required if mail client is set to mailgun | `string` | `null` | no |
| cw_log_group_retention | Number of days to store the logs in a log group. Valid values are: 1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653, and 0. To never expire the logs provide 0 | `number` | `90` | no |
| cw_logs_kms_key_arn | ARN of KMS key to use for encrypting CloudWatch logs at rest | `string` | `null` | no |

## Outputs

| Name | Description |
|------|-------------|
| table_name | Name of dynamodb table created for storing access keys to be deleted |
| key_creator_function_name | Name of lambda function created to create a set of new key pair for IAM user |
| key_destructor_function_name | Name of lambda function created to delete existing key pair which has reached its expiry |
| cron_expression | Interval at which `key creator` function will be invoked |
| mailgun_ssm_parameter_arn | ARN of SSM parameter that stores mailgun API key. Available only if mail client is set to Mailgun |
| smtp_ssm_parameter_arn | ARN of SSM parameter that stores SMTP password. Available only if mail client is set to SMTP |
