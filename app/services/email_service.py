import asyncio
import smtplib
from email.message import EmailMessage

from app.core.config import Settings


class EmailService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send_code(self, recipient: str, *, purpose: str, code: str) -> bool:
        if not self.settings.smtp_enabled:
            return False
        subject = "昭星斋邮箱验证" if purpose == "verify_email" else "昭星斋密码重置"
        action = "验证邮箱" if purpose == "verify_email" else "重置密码"
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.settings.smtp_from_email
        message["To"] = recipient
        message.set_content(
            f"你正在{action}。一次性验证码为：\n\n{code}\n\n"
            f"验证码将在 {self.settings.app_email_token_minutes} 分钟后失效。"
            "如果不是你本人操作，请忽略此邮件。"
        )
        await asyncio.to_thread(self._send, message)
        return True

    def _send(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=20) as smtp:
            if self.settings.smtp_use_tls:
                smtp.starttls()
            if self.settings.smtp_username:
                smtp.login(self.settings.smtp_username, self.settings.smtp_password)
            smtp.send_message(message)
