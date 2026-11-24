from __future__ import annotations

import aiosmtplib
from email.message import EmailMessage

from auth.core.settings import settings


class MailService:
    """Envío de correo via SMTP.

    En dev, si APP_MAIL_ENABLED=false, no envía pero tampoco rompe el flujo.
    """

    async def send_email(self, *, to_email: str, subject: str, html_body: str, text_body: str | None = None) -> None:
        if not settings.app_mail_enabled:
            return

        msg = EmailMessage()
        msg["From"] = settings.app_mail_from
        msg["To"] = to_email
        msg["Subject"] = subject

        if text_body:
            msg.set_content(text_body)
            msg.add_alternative(html_body, subtype="html")
        else:
            msg.set_content(html_body, subtype="html")

        await aiosmtplib.send(
            msg,
            hostname=settings.mail_host,
            port=settings.mail_port,
            start_tls=settings.mail_use_tls,
            username=settings.mail_username or None,
            password=settings.mail_password or None,
        )


mail_service = MailService()
