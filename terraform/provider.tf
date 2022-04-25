terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 3.42.0"
    }
  }
}

provider "aws" {
  region     = var.region
  profile    = var.profile
  access_key = var.access_key
  secret_key = var.secret_key
  token      = var.session_token
}
