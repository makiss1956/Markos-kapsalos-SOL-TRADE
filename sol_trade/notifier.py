"""Ειδοποιήσεις Telegram + Email — και οι δύο προαιρετικές (env vars).

  • Telegram: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID
  • Email (Gmail): GMAIL_USER + GMAIL_APP_PASSWORD + EMAIL_TO
    (στο GitHub Actions μπαίνουν ως Secrets — βλ. ΟΔΗΓΟΣ_ΑΝΑΒΑΘΜΙΣΗΣ.md)

Αν δεν έχει οριστεί ΚΑΜΙΑ πηγή, το bot απλώς γράφει τα μηνύματα στα logs.
"""

from __future__ import annotations

import os
import re
import smtplib
from email.mime.text import MIMEText

import requests

from .config import Config
from .logger import setup_logger

log = setup_logger("sol_trade.notifier")


class Notifier:
    def __init__(self, cfg: Config):
        # ── Telegram ──────────────────────────────────────────────
        self.bot_token = cfg.telegram_bot_token
        self.chat_id = cfg.telegram_chat_id
        self.enabled = bool(self.bot_token and self.chat_id)

        # ── Email (Gmail App Password) ────────────────────────────
        self.mail_user = os.getenv("GMAIL_USER", "")
        self.mail_pass = os.getenv("GMAIL_APP_PASSWORD", "")
        self.mail_to = os.getenv("EMAIL_TO", "")
        self.email_enabled = bool(self.mail_user and self.mail_pass and self.mail_to)
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "465"))

        if self.enabled and self.email_enabled:
            log.info("Ειδοποιήσεις: Telegram ✔ + Email ✔ (%s)", self.mail_to)
        elif self.enabled:
            log.info("Ειδοποιήσεις: Telegram ✔ | Email ✖ (λείπουν τα GMAIL_*/EMAIL_TO)")
        elif self.email_enabled:
            log.info("Ειδοποιήσεις: Email ✔ (%s) | Telegram ✖", self.mail_to)
        else:
            log.info("Ειδοποιήσεις απενεργοποιημένες (λείπουν Telegram ΚΑΙ email env vars)")

    # ─────────────────────────────────────────────── δημόσιο API
    def send(self, message: str) -> bool:
        """Στέλνει σε κάθε ενεργή πηγή. True αν πήγε τουλάχιστον σε μία."""
        log.info("[ΕΙΔΟΠΟΙΗΣΗ] %s", message)
        ok_tg = self._send_telegram(message) if self.enabled else False
        ok_mail = self._send_email(message) if self.email_enabled else False
        return ok_tg or ok_mail

    def notify_trade(self, side: str, details: str, mode: str) -> None:
        tag = "LIVE" if mode == "live" else "PAPER"
        self.send(f"<b>[{tag}] {side}</b>\n{details}")

    # ─────────────────────────────────────────────────── Telegram
    def _send_telegram(self, message: str) -> bool:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            r = requests.post(
                url,
                json={"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"},
                timeout=10,
            )
            if r.status_code == 200:
                return True
            log.warning("Telegram HTTP %d: %s", r.status_code, r.text[:200])
            return False
        except Exception as e:  # noqa: BLE001
            log.warning("Telegram αποτυχία: %s", e)
            return False

    # ───────────────────────────────────────────────────── Email
    def _send_email(self, message: str) -> bool:
        try:
            plain = re.sub(r"<[^>]+>", "", message).strip()
            first_line = plain.splitlines()[0][:80] if plain else "sol_trade"
            msg = MIMEText(plain, "plain", "utf-8")
            msg["Subject"] = f"sol_trade: {first_line}"
            msg["From"] = self.mail_user
            msg["To"] = self.mail_to
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=25) as s:
                s.login(self.mail_user, self.mail_pass)
                s.sendmail(self.mail_user, [self.mail_to], msg.as_string())
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("Email αποτυχία: %s", e)
            return False
