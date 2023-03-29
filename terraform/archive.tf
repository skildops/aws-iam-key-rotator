data "archive_file" "creator" {
  type        = "zip"
  output_path = "${path.module}/creator.zip"
  source {
    content  = file("../src/creator.py")
    filename = "creator.py"
  }
  source {
    content  = file("../src/shared_functions.py")
    filename = "shared_functions.py"
  }
  source {
    content  = file("../src/encryption.py")
    filename = "encryption.py"
  }
  source {
    content  = file("../src/ses_mailer.py")
    filename = "ses_mailer.py"
  }
  source {
    content  = file("../src/mailgun_mailer.py")
    filename = "mailgun_mailer.py"
  }
  source {
    content  = file("../src/smtp_mailer.py")
    filename = "smtp_mailer.py"
  }
}

data "archive_file" "destructor" {
  type        = "zip"
  output_path = "${path.module}/destructor.zip"
  source {
    content  = file("../src/destructor.py")
    filename = "destructor.py"
  }
  source {
    content  = file("../src/shared_functions.py")
    filename = "shared_functions.py"
  }
  source {
    content  = file("../src/ses_mailer.py")
    filename = "ses_mailer.py"
  }
  source {
    content  = file("../src/mailgun_mailer.py")
    filename = "mailgun_mailer.py"
  }
  source {
    content  = file("../src/smtp_mailer.py")
    filename = "smtp_mailer.py"
  }
}
