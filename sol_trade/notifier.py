"""Telegram ειδοποιήσεις — προαιρετικές (αν έχουν οριστεί τα env vars)."""

from __future__ import annotations

import requests

from .config import Config
from .logger import setup_logger

log = setup_logger("sol_trade.telegram")


class Notifier:
    def __init__(self, cfg: Config):
        self.bot_token = cfg.telegram_bot_token
        self.chat_id = cfg.telegram_chat_id
        self.enabled = bool(self.bot_token and self.chat_id)
        if not self.enabled:
            log.info("Οι Telegram ειδοποιήσεις είναι απενεργοποιημένες (λείπουν env vars)")

    def send(self, message: str) -> bool:
        """Στέλνει μήνυμα. Επιστρέφει True αν στάλθηκε επιτυχώς."""
        log.info("[ΕΙΔΟΠΟΙΗΣΗ] %s", message)
        if not self.enabled:
            return False
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

    def notify_trade(self, side: str, details: str, mode: str) -> None:
        tag = "LIVE" if mode == "live" else "PAPER"
        self.send(f"<b>[{tag}] {side}</b>\n{details}")
