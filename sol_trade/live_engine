"""Live execution engine — πραγματικές συναλλαγές μέσω Jupiter Swap API v2.

ΠΡΟΕΙΔΟΠΟΙΗΣΗ: Σε αυτή τη λειτουργία δαπανώνται ΠΡΑΓΜΑΤΙΚΑ κεφάλαια.
- Χρειάζεται SOL_PRIVATE_KEY στο .env (νέο πορτοφόλι με μικρό ποσό!)
- Χρειάζεται JUPITER_API_KEY (δωρεάν από https://developers.jup.ag/portal)
- Χρειάζεται USDC στο πορτοφόλι για αγορές / token για πωλήσεις
- Το πορτοφόλι θέλει και λίγα SOL για priority fees
"""

from __future__ import annotations

from .config import Config
from .jupiter_client import JupiterClient, JupiterError
from .logger import setup_logger
from .risk import Position, RiskManager
from .strategy import Signal
from .utils import utc_now_iso
from .wallet import Wallet

log = setup_logger("sol_trade.live")

LAMPORTS_PER_SOL = 1_000_000_000


class LiveEngine:
    def __init__(self, cfg: Config, jupiter: JupiterClient | None = None, wallet: Wallet | None = None):
        if cfg.mode != "live":
            raise ValueError("Το LiveEngine προορίζεται μόνο για mode='live'")
        self.cfg = cfg
        self.jupiter = jupiter or JupiterClient(api_key=cfg.jupiter_api_key)
        if not self.jupiter.session.headers.get("x-api-key"):
            raise ValueError(
                "Λείπει το JUPITER_API_KEY στο .env — δωρεάν από https://developers.jup.ag/portal"
            )
        self.wallet = wallet or Wallet(cfg)

    # ---------------------------------------------------- ΥΠΟΛΟΓΙΣΜΟΙ
    def usd_to_raw(self, usd_amount: float, usd_price: float) -> int:
        """Μετατρέπει USD ποσό σε raw units του quote token (USDC decimals)."""
        token_amount = usd_amount / usd_price if usd_price > 0 else usd_amount
        return int(round(token_amount * (10 ** self.cfg.quote.decimals)))

    def token_to_raw(self, token_amount: float) -> int:
        return int(round(token_amount * (10 ** self.cfg.token.decimals)))

    # ---------------------------------------------------- ΣΥΝΑΛΛΑΓΕΣ
    def _do_swap(self, input_mint: str, output_mint: str, amount_raw: int, what: str) -> str:
        log.info("LIVE %s: ζητάω quote (%d raw units)...", what, amount_raw)
        order = self.jupiter.get_quote(
            input_mint=input_mint,
            output_mint=output_mint,
            amount_raw=amount_raw,
            slippage_bps=50,
            taker=self.wallet.pubkey,
        )
        out_amount = order.get("outAmount", "?")
        log.info("LIVE %s: quote OK, αναμενόμενο out=%s — υπογράφω...", what, out_amount)

        signed = self.wallet.sign_transaction(order["transaction"])
        request_id = order.get("requestId")
        signature = self.jupiter.execute_swap(signed, request_id=request_id)
        log.info("LIVE %s: υποβλήθηκε, signature=%s", what, signature)

        ok = self.wallet.wait_confirmation(self.cfg.rpc_url, signature)
        if not ok:
            log.error("LIVE %s: δεν επιβεβαιώθηκε εντός 60s (ελέγξτε στο explorer)", what)
        return signature

    def buy(self, signal: Signal, usd_price_of_quote: float, risk_manager: RiskManager) -> dict:
        """Αγορά token: swap USDC -> token."""
        fee = self.cfg.trading.fee_pct + self.cfg.trading.slippage_pct
        eff_price = signal.price * (1 + fee / 100.0)
        size_token = risk_manager.position_size_token(signal.price, self.cfg.trading.fee_pct, self.cfg.trading.slippage_pct)

        amount_raw = self.usd_to_raw(self.cfg.risk.trade_amount_usd, usd_price_of_quote)
        signature = self._do_swap(
            input_mint=self.cfg.quote.mint,
            output_mint=self.cfg.token.mint,
            amount_raw=amount_raw,
            what=f"BUY {self.cfg.token.symbol}",
        )
        risk_manager.register_trade()
        return {
            "side": "BUY",
            "signature": signature,
            "entry_price": eff_price,
            "size_token": size_token,
            "size_usd": self.cfg.risk.trade_amount_usd,
            "opened_at": utc_now_iso(),
        }

    def sell(self, position: Position, reason: str, risk_manager: RiskManager) -> dict:
        """Πώληση όλης της θέσης: swap token -> USDC."""
        amount_raw = self.token_to_raw(position.size_token)
        signature = self._do_swap(
            input_mint=self.cfg.token.mint,
            output_mint=self.cfg.quote.mint,
            amount_raw=amount_raw,
            what=f"SELL {self.cfg.token.symbol}",
        )
        risk_manager.register_trade()
        return {"side": "SELL", "signature": signature, "reason": reason}

    def balances(self, sol_price: float) -> dict:
        sol = self.wallet.get_sol_balance(self.cfg.rpc_url)
        return {"sol": sol, "sol_usd_value": sol * sol_price}
