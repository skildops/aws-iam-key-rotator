data "template_file" "creator" {
  template = file("../src/creator.py")
}

data "template_file" "destructor" {
  template = file("../src/destructor.py")
}

data "template_file" "ses_mailer" {
  template = file("../src/ses_mailer.py")
}

data "template_file" "mailgun_mailer" {
  template = file("../src/mailgun_mailer.py")
}

data "template_file" "smtp_mailer" {
  template = file("../src/smtp_mailer.py")
}

data "archive_file" "creator" {
  type        = "zip"
  output_path = "${path.module}/creator.zip"
  source {
    content  = data.template_file.creator.rendered
    filename = "creator.py"
  }
  source {
    content  = data.template_file.ses_mailer.rendered
    filename = "ses_mailer.py"
  }
  source {
    content  = data.template_file.mailgun_mailer.rendered
    filename = "mailgun_mailer.py"
  }
  source {
    content  = data.template_file.smtp_mailer.rendered
    filename = "smtp_mailer.py"
  }
}

data "archive_file" "destructor" {
  type        = "zip"
  output_path = "${path.module}/destructor.zip"
  source {
    content  = data.template_file.destructor.rendered
    filename = "destructor.py"
  }
  source {
    content  = data.template_file.ses_mailer.rendered
    filename = "ses_mailer.py"
  }
  source {
    content  = data.template_file.mailgun_mailer.rendered
    filename = "mailgun_mailer.py"
  }
  source {
    content  = data.template_file.smtp_mailer.rendered
    filename = "smtp_mailer.py"
  }
}
