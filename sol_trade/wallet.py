"""Διαχείριση πορτοφολιού Solana (μόνο για live mode).

Το solders/solana εγκαθίστανται ξεχωριστά (βλ. requirements.txt), γι' αυτό
τα imports είναι μέσα στις συναρτήσεις — το paper mode δεν τα χρειάζεται.
"""

from __future__ import annotations

from .config import Config
from .logger import setup_logger

log = setup_logger("sol_trade.wallet")


class Wallet:
    """Αναβλύει το keypair από το .env (base58 string ή πίνακας 64 ακεραίων)."""

    def __init__(self, cfg: Config):
        if not cfg.private_key:
            raise ValueError(
                "Λείπει το SOL_PRIVATE_KEY στο .env — απαραίτητο για live mode."
            )
        self.keypair = self._load_keypair(cfg.private_key)
        self.pubkey = str(self.keypair.pubkey())

    @staticmethod
    def _load_keypair(raw: str):
        raw = raw.strip()
        if raw.startswith("["):
            import json

            from solders.keypair import Keypair  # type: ignore

            seed = bytes(json.loads(raw)[:32])
            return Keypair.from_seed(seed)
        import base58  # type: ignore

        from solders.keypair import Keypair  # type: ignore

        return Keypair.from_bytes(base58.b58decode(raw))

    # ---------------------------------------------------- ΥΠΟΛΟΙΠΑ
    def get_sol_balance(self, rpc_url: str) -> float:
        import requests  # lazy import για να μη χρειάζεται στο paper mode

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [self.pubkey],
        }
        r = requests.post(rpc_url, json=payload, timeout=15)
        r.raise_for_status()
        lamports = r.json()["result"]["value"]
        return lamports / 1e9

    def sign_transaction(self, tx_b64: str) -> str:
        """Υπογράφει base64 versioned transaction και επιστρέφει base64."""
        import base64

        from solders.transaction import VersionedTransaction  # type: ignore

        raw = base64.b64decode(tx_b64)
        tx = VersionedTransaction.deserialize(raw)
        signed = VersionedTransaction(tx.message, [self.keypair])
        return base64.b64encode(bytes(signed)).decode()

    @staticmethod
    def wait_confirmation(rpc_url: str, signature: str, timeout: int = 60) -> bool:
        import time

        import requests

        deadline = time.time() + timeout
        while time.time() < deadline:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignatureStatuses",
                "params": [[signature], {"searchTransactionHistory": False}],
            }
            try:
                r = requests.post(rpc_url, json=payload, timeout=15)
                statuses = r.json().get("result", {}).get("value") or []
                if statuses and statuses[0] is not None:
                    if statuses[0].get("err"):
                        return False
                    confirmations = statuses[0].get("confirmations", 0)
                    if confirmations >= 1 or statuses[0].get("confirmationStatus") == "finalized":
                        return True
            except Exception:  # noqa: BLE001
                pass
            time.sleep(2)
        return False
