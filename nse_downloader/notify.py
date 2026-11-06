from __future__ import annotations
import logging, os, smtplib
from email.message import EmailMessage
import requests

class Notifier:
    """Best-effort only: notification failure cannot fail data processing."""
    def __init__(self, logger: logging.Logger, webhook_url: str | None = None): self.logger, self.webhook_url = logger, webhook_url or os.getenv("NSE_WEBHOOK_URL")
    def failure(self, dataset: str, error: str) -> None:
        text = f"NSE downloader failed for {dataset}: {error}"; self.logger.error("NOTIFICATION: %s", text)
        if self.webhook_url:
            try: requests.post(self.webhook_url, json={"text": text}, timeout=10).raise_for_status()
            except requests.RequestException as exc: self.logger.warning("Webhook notification failed: %s", exc)
        host, sender, recipient = os.getenv("NSE_SMTP_HOST"), os.getenv("NSE_SMTP_FROM"), os.getenv("NSE_SMTP_TO")
        if host and sender and recipient:
            try:
                email = EmailMessage(); email.set_content(text); email["Subject"] = "NSE downloader failure"; email["From"] = sender; email["To"] = recipient
                with smtplib.SMTP(host, int(os.getenv("NSE_SMTP_PORT", "587")), timeout=10) as smtp: smtp.send_message(email)
            except (OSError, smtplib.SMTPException) as exc: self.logger.warning("SMTP notification failed: %s", exc)
