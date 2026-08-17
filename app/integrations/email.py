import smtplib
from email.message import EmailMessage

from app.core.config import get_settings


def send_invitation_email(to_email: str, organization_name: str, invitation_token: str) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["Subject"] = f"Invitation to {organization_name}"
    message["From"] = settings.mail_from
    message["To"] = to_email
    message.set_content(
        "You have been invited to join an organization in TenantFlow.\n\n"
        f"Invitation token: {invitation_token}\n"
        "This local-development message is captured by Mailpit."
    )
    with smtplib.SMTP(settings.mail_host, settings.mail_port, timeout=10) as smtp:
        smtp.send_message(message)
