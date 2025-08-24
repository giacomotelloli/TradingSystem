# trading_system/utils/portfolio_manager.py
from __future__ import annotations
from typing import Dict, Any
import os
import yaml
from copy import deepcopy

from .interface_factory import get_trading_interface
from .stock_state_manager import StockStateManager

def _norm(sym: str) -> str:
    return sym.lower().replace("/", "_").strip()

def _real(sym: str) -> str:
    return sym.upper().replace("_", "/")

# === NUOVO: trader che non fa nulla (silenzioso) ===
class _NoOpTrader:
    def buy(self, symbol: str, qty: float): 
        pass
    def sell(self, symbol: str, qty: float):
        pass
    def get_account(self):
        class A: pass
        a = A(); a.cash = 0.0
        return a
    def get_last_price(self, symbol: str):
        return 0.0

class PortfolioManager:
    def __init__(self, config_path: str = "config/portfolio.yaml",
                 broker_enabled: bool = True,        # <-- NUOVO
                 trader=None):                        # <-- opzionale override trader
        self.config_path = config_path
        self.broker_enabled = bool(broker_enabled)    # <-- NUOVO

        # stato e config
        self.stock_state = StockStateManager()
        self.initial_budget: float = 0.0
        self.allocations: Dict[str, float] = {}
        self.stock_cash: Dict[str, float] = {}
        self.realized_pnl_pool: float = 0.0

        self.reinvest_ratio: Dict[str, float] = {}
        self.default_reinvest_ratio: float = 1.0

        self._load_config()

        # trader: reale o no-op
        if trader is not None:
            self.trader = trader
        else:
            self.trader = get_trading_interface() if self.broker_enabled else _NoOpTrader()

    def _load_config(self):
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Portfolio config non trovata: {self.config_path}")
        import yaml
        with open(self.config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        self.initial_budget = float(cfg.get("initial_budget", 0.0))
        alloc = cfg.get("allocations", {}) or {}
        self.allocations = { _norm(k): float(v) for k, v in alloc.items() }

        reinv = cfg.get("reinvest", {}) or {}
        self.default_reinvest_ratio = float(reinv.get("default", 1.0))
        per_asset = reinv.get("per_asset", {}) or {}
        self.reinvest_ratio = { _norm(k): float(v) for k, v in per_asset.items() }

    def bootstrap(self):
        self.stock_cash = { s: self.initial_budget * w for s, w in self.allocations.items() }

    # --- policy reinvestimento ---
    def set_reinvest_ratio(self, stock: str, ratio: float):
        self.reinvest_ratio[_norm(stock)] = max(0.0, min(1.0, float(ratio)))
    def get_reinvest_ratio(self, stock: str) -> float:
        return self.reinvest_ratio.get(_norm(stock), self.default_reinvest_ratio)

    # --- booking trade ---
    def book_buy(self, stock: str, qty: float, price: float):
        s = _norm(stock)
        notional = qty * price
        cash = self.stock_cash.get(s, 0.0)
        if notional > cash + 1e-9:
            print(f"[Portfolio] WARN: cash insufficiente per {s}: need {notional:.2f}, have {cash:.2f}")

        # SOLO se broker abilitato inviamo l'ordine reale
        if self.broker_enabled:
            self.trader.buy(_real(s), qty)
        # Aggiorna lo stato interno sempre
        self.stock_state.update_on_buy(s, qty, notional)
        self.stock_cash[s] = cash - notional

    def book_sell(self, stock: str, qty: float, price: float):
        s = _norm(stock)
        st = deepcopy(self.stock_state.get_state(s)) or {}
        cur_qty = float(st.get("quantity", 0))
        invested = float(st.get("money_invested", 0.0))
        avg_cost = (invested / cur_qty) if cur_qty > 0 else 0.0

        proceeds = qty * price
        principal = qty * avg_cost
        profit = proceeds - principal

        if self.broker_enabled:
            self.trader.sell(_real(s), qty)
        self.stock_state.update_on_sell(s, qty, proceeds)

        rratio = self.get_reinvest_ratio(s)
        reinvest_profit = max(0.0, profit) * rratio
        pnl_pool_part = profit - reinvest_profit

        self.stock_cash[s] = self.stock_cash.get(s, 0.0) + principal + reinvest_profit
        self.realized_pnl_pool += pnl_pool_part

    def snapshot(self) -> Dict[str, Any]:
        rows = {}
        total_holdings = total_cash_alloc = 0.0
        for s, w in self.allocations.items():
            st = self.stock_state.get_state(s) or {}
            qty = float(st.get("quantity", 0))
            last = self.trader.get_last_price(_real(s)) or 0.0
            val = qty * last
            cash = self.stock_cash.get(s, 0.0)
            rows[s] = {
                "symbol": _real(s), "quantity": qty, "last_price": float(last),
                "holding_value": val, "cash_alloc": cash, "target_weight": float(w),
            }
            total_holdings += val
            total_cash_alloc += cash
        total_total = total_holdings + total_cash_alloc
        for s, r in rows.items():
            hv, ca, tw = r["holding_value"], r["cash_alloc"], r["target_weight"]
            r["weight_exposure"] = (hv / total_holdings) if total_holdings > 0 else 0.0
            r["weight_total"] = ((hv + ca) / total_total) if total_total > 0 else 0.0
            r["weight_diff"] = r["weight_total"] - tw
        return {
            "rows": rows,
            "totals": {
                "total_holdings": total_holdings,
                "total_cash_alloc": total_cash_alloc,
                "total_value": total_total,
                "realized_pnl_pool": self.realized_pnl_pool,
            }
        }
