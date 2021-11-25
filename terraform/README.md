# IAM Key Rotator

![Test](https://img.shields.io/github/workflow/status/paliwalvimal/aws-iam-key-rotator/test/main?label=Test&style=for-the-badge) ![Checkov](https://img.shields.io/github/workflow/status/paliwalvimal/aws-iam-key-rotator/checkov/main?label=Checkov&style=for-the-badge)

This terraform module will deploy the following services:
- DynamoDB Table
- IAM Role
- IAM Role Policy
- CloudWatch Event
- Lambda

**Note:** You need to implement [remote backend](https://www.terraform.io/docs/language/settings/backends/index.html) by yourself and is recommended.

# Usage Instructions

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
| mail_client | Mail client to use. **Supported Clients:** ses and mailgun | `string` | `"ses"` | no |
| mail_from | Email address which should be used for sending mails. **Note:** Prior setup of mail client is required | `string` | n/a | yes |
| mailgun_api_url | Mailgun API url for sending email. **Note:** Required if you want to use Mailgun as mail client | `string` | `null` | no |
| mailgun_api_key | API key for authenticating requests to Mailgun API. **Note:** Required if you want to use Mailgun as mail client | `string` | `""` | no |

## Outputs

| Name | Description |
|------|-------------|
| table_name | Name of dynamodb table created for storing access keys to be deleted |
| key_creator_function_name | Name of lambda function created to create a set of new key pair for IAM user |
| key_destructor_function_name | Name of lambda function created to delete existing key pair which has reached its expiry |
| cron_expression | Interval at which `key creator` function will be invoked |
