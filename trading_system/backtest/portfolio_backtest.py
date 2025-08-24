# trading_system/backtest/portfolio_backtest.py
from __future__ import annotations
import os
import csv
from datetime import datetime, timezone
import importlib
from typing import Dict, List, Any

from trading_system.utils.historical_downloader import fetch_crypto_bars
from trading_system.utils.stock_state_manager import StockStateManager
from trading_system.state import PortfolioState

# Trader simulato (no I/O broker)
class SimTrader:
    def __init__(self, starting_cash: float):
        self._cash = float(starting_cash)

    # opzionale: tieni traccia della cassa; qui non è strettamente usata dal tuo sistema
    def buy(self, symbol: str, qty: float):
        # no-op (il PnL “realized” viene gestito dal tuo StockStateManager)
        pass

    def sell(self, symbol: str, qty: float):
        pass

    def get_account(self):
        class A: pass
        a = A()
        a.cash = self._cash
        return a

    def get_last_price(self, symbol: str):
        return None

# StrategyRunner “like” ma guidato da barre storiche già scaricate
class BacktestStrategyRunner:
    def __init__(self, stock: str, strategy_cls, initial_capital: float,
                 trader: SimTrader, stock_state: StockStateManager,
                 state: PortfolioState, bars: List[dict], backtest_log_suffix: str = "backtest"):
        self.stock = stock.lower().replace("/", "_")
        self.strategy = strategy_cls(self.stock, initial_capital,
                                     log_path=os.path.join("logs", f"{backtest_log_suffix}_rsi_{self.stock}.csv"))
        self.trader = trader
        self.stock_state = stock_state
        self.state = state
        self.bars = bars  # [{t,o,h,l,c,v}, ...]

    def run(self):
        stock_name = self.stock.upper().replace("_", "/")
        print(f"[{stock_name}] BacktestRunner starting on {len(self.bars)} bars...")
        self.state.update_status(self.stock, "backtest_running")

        for b in self.bars:
            # tick sintetico con la CLOSE
            data = {
                "symbol": self.stock,
                "price": float(b["c"]),
                "timestamp": b.get("t"),
            }
            signal = self.strategy.on_data(data)

            if signal["action"] == "buy":
                price = data["price"]
                qty = float(signal.get("quantity", 0.0))
                if qty > 0:
                    self.trader.buy(stock_name, qty)
                    self.stock_state.update_on_buy(self.stock, qty, price * qty)
                    print(f"[{stock_name}] BUY @{price:.2f} qty={qty}")

            elif signal["action"] == "sell":
                current = self.stock_state.get_state(self.stock)
                qty = float(current.get("quantity", 0))
                if qty > 0:
                    price = data["price"]
                    self.trader.sell(stock_name, qty)
                    self.stock_state.update_on_sell(self.stock, qty, price * qty)
                    print(f"[{stock_name}] SELL @{price:.2f} qty={qty}")

        self.state.update_status(self.stock, "backtest_done")
        print(f"[{stock_name}] BacktestRunner done.")

# Orchestratore di portafoglio: scarica dati, avvia tutti i runner, logga PnL
class PortfolioBacktester:
    def __init__(self, strategies_map: Dict[str, str], allocations: Dict[str, float],
                 initial_budget: float, timeframe_minutes: int,
                 start_iso: str, end_iso: str,
                 api_key: str | None, api_secret: str | None):
        self.strategies_map = strategies_map
        self.allocations = allocations
        self.initial_budget = float(initial_budget)
        self.tf = int(timeframe_minutes)
        self.start_iso = start_iso
        self.end_iso = end_iso
        self.api_key = api_key
        self.api_secret = api_secret

        self.stock_state = StockStateManager()
        self.portfolio_state = PortfolioState()
        self.pnl_log_path = os.path.join("logs", "backtest_pnl.csv")
        os.makedirs("logs", exist_ok=True)
        self._ensure_pnl_header()

    def _ensure_pnl_header(self):
        if not os.path.exists(self.pnl_log_path) or os.path.getsize(self.pnl_log_path) == 0:
            with open(self.pnl_log_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["ts_wall", "symbol", "realized_pnl_total"])

    def _append_pnl(self, symbol: str):
        # somma realized_pnl su tutte le stock
        total = 0.0
        all_states = self.stock_state.get_all_states()
        for s, st in all_states.items():
            total += float(st.get("realized_pnl", 0.0))
        with open(self.pnl_log_path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([datetime.now(timezone.utc).isoformat(), symbol, total])

    def run(self):
        symbols = list(self.strategies_map.keys())
        # scarica dati: dict { "BTC/USD": [bars...] }
        print(f"[Backtest] Downloading {self.tf}m bars for {symbols} from {self.start_iso} to {self.end_iso} ...")
        bars_by_sym = fetch_crypto_bars(
            symbols=symbols,
            start_iso=self.start_iso,
            end_iso=self.end_iso,
            timeframe_minutes=self.tf,
            api_key=self.api_key,
            api_secret=self.api_secret,
        )
        print("[Backtest] Download done.")

        # crea trader simulato (cassa non fondamentale per realized PnL del tuo sistema)
        sim_trader = SimTrader(starting_cash=self.initial_budget)

        # esegui ogni strategia in sequenza (semplice e deterministico)
        for stock, module_name in self.strategies_map.items():
            sym_norm = stock.lower().replace("/", "_")
            budget_for_stock = float(self.allocations.get(stock, 0.0)) * self.initial_budget

            try:
                m = importlib.import_module(f"trading_system.strategies.{module_name}")
                strategy_cls = getattr(m, "Strategy")
            except Exception as e:
                print(f"[Backtest] Cannot load strategy {module_name} for {stock}: {e}")
                continue

            # prendi la serie di barre (potrebbe essere vuota se l'API non ha dato dati)
            series = bars_by_sym.get(stock.upper().replace("_","/")) or bars_by_sym.get(stock.upper()) or []
            if not series:
                print(f"[Backtest] No bars for {stock}, skipping.")
                continue

            # runner
            runner = BacktestStrategyRunner(
                stock=sym_norm,
                strategy_cls=strategy_cls,
                initial_capital=budget_for_stock,
                trader=sim_trader,
                stock_state=self.stock_state,
                state=self.portfolio_state,
                bars=series,
                backtest_log_suffix="backtest"
            )

            # hook PnL logging: logga dopo ogni SELL (e anche dopo ogni BUY per traccia)
            # qui lo facciamo “a valle” semplicemente richiamandolo dopo il run di ciascun asset
            runner.run()
            self._append_pnl(stock)

        # stampa riepilogo
        all_states = self.stock_state.get_all_states()
        total_realized = sum(float(st.get("realized_pnl", 0.0)) for st in all_states.values())
        print("\n[Backtest] Summary:")
        for s, st in all_states.items():
            print(f"  - {s.upper()}: realized PnL = {float(st.get('realized_pnl', 0.0)):.2f}")
        print(f"  TOTAL realized PnL = {total_realized:.2f}")
        print(f"  PnL log written to: {self.pnl_log_path}")
