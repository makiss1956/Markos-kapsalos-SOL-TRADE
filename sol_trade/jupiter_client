"""Πελάτης για το Jupiter API (τιμές + swaps) και το Solana RPC.

Endpoints (τεκμηρίωση: https://developers.jup.ag):
- Price API v3:  GET <base>/price/v3?ids=<mint>[,<mint2>]
- Swap API v2:   GET <base>/swap/v2/order?...
                 POST <base>/swap/v2/execute

Base URL επιλέγεται αυτόματα:
- Χωρίς API key  ->  https://lite-api.jup.ag  (δωρεάν, χωρίς κλειδί)
- Με API key     ->  https://api.jup.ag       (επίσημο paid/free tier με key)
"""

from __future__ import annotations

import time
from typing import Any

import requests

from .logger import setup_logger

DEFAULT_BASE_FREE = "https://lite-api.jup.ag"
DEFAULT_BASE_KEYED = "https://api.jup.ag"
SOL_MINT = "So11111111111111111111111111111111111111112"

log = setup_logger("sol_trade.jupiter")


class JupiterError(RuntimeError):
    """Σφάλμα κλήσης προς το Jupiter API."""


class JupiterClient:
    def __init__(self, api_key: str = "", timeout: int = 15, max_retries: int = 3,
                 base_url: str | None = None):
        self.session = requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        if api_key:
            self.session.headers.update({"x-api-key": api_key})
        # Base URL: ρητή παράμετρος > api.jup.ag με key > lite-api χωρίς key
        if base_url:
            self.base = base_url.rstrip("/")
        else:
            self.base = DEFAULT_BASE_KEYED if api_key else DEFAULT_BASE_FREE
        self.price_url = f"{self.base}/price/v3"
        self.swap_order_url = f"{self.base}/swap/v2/order"
        self.swap_execute_url = f"{self.base}/swap/v2/execute"

    # ---------------------------------------------------- ΤΙΜΕΣ
    def get_prices(self, mints: list[str]) -> dict[str, float]:
        """Επιστρέφει {mint: usdPrice}. Ρίξει JupiterError αν αποτύχει."""
        params = {"ids": ",".join(mints)}
        last_err: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                r = self.session.get(self.price_url, params=params, timeout=self.timeout)
                r.raise_for_status()
                body = r.json()
                data = body.get("data", body) if isinstance(body, dict) else body
                out: dict[str, float] = {}
                for mint in mints:
                    entry = data.get(mint)
                    if entry and entry.get("usdPrice") is not None:
                        out[mint] = float(entry["usdPrice"])
                if out:
                    return out
                raise JupiterError(f"Κενή απάντηση τιμών για {mints}")
            except Exception as e:  # noqa: BLE001
                last_err = e
                log.warning("Προσπάθεια %d/%d απέτυχε: %s", attempt, self.max_retries, e)
                time.sleep(min(2 ** attempt, 8))
        raise JupiterError(f"Αποτυχία λήψης τιμών: {last_err}")

    def get_price(self, mint: str) -> float:
        return self.get_prices([mint])[mint]

    def get_quote(self, input_mint: str, output_mint: str, amount_raw: int,
                  slippage_bps: int = 50, taker: str | None = None) -> dict[str, Any]:
        """Ζητά quote + συναρμολογημένο transaction από το Swap API v2."""
        params: dict[str, Any] = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount_raw),
            "slippageBps": slippage_bps,
            "swapMode": "ExactIn",
        }
        if taker:
            params["taker"] = taker
        r = self.session.get(self.swap_order_url, params=params, timeout=self.timeout)
        if r.status_code != 200:
            raise JupiterError(f"Swap order HTTP {r.status_code}: {r.text[:300]}")
        order = r.json()
        if order.get("error") or not order.get("transaction"):
            raise JupiterError(f"Swap order σφάλμα: {order.get('errorMessage') or order.get('error')}")
        return order

    def execute_swap(self, signed_tx_b64: str, request_id: str | None = None) -> str:
        """Αποστέλλει το υπογεγραμμένο transaction. Επιστρέφει το signature."""
        payload: dict[str, Any] = {"signedTransaction": signed_tx_b64}
        if request_id:
            payload["requestId"] = request_id
        r = self.session.post(self.swap_execute_url, json=payload, timeout=self.timeout)
        if r.status_code != 200:
            raise JupiterError(f"Swap execute HTTP {r.status_code}: {r.text[:300]}")
        body = r.json()
        signature = body.get("signature") or body.get("swapTransaction")
        if not signature:
            raise JupiterError(f"Swap execute χωρίς signature: {str(body)[:300]}")
        return signature
