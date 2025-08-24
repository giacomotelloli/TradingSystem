from .base import StrategyBase
import numpy as np
from collections import deque
import os, csv
from datetime import datetime, timezone

class Strategy(StrategyBase):
    def __init__(
        self,
        stock,
        starting_capital,
        window=14,
        rsi_buy=30,
        rsi_exit=55,
        trailing_pct=0.02,
        fee_buy_pct=0.0005,
        fee_sell_pct=0.0005,
        slippage_pct=0.0005,
        edge_min_pct=0.001,
        hard_tp_pct=None,
        max_buffer=600,
        cooldown_bars=1,
        size_fraction=1.0,
        log_path: str | None = None,     # <-- nuovo: CSV path
    ):
        super().__init__(stock)
        self.window = int(window)
        self.rsi_buy = float(rsi_buy)
        self.rsi_exit = float(rsi_exit)
        self.trailing_pct = float(trailing_pct)
        self.fee_buy_pct = float(fee_buy_pct)
        self.fee_sell_pct = float(fee_sell_pct)
        self.slippage_pct = float(slippage_pct)
        self.edge_min_pct = float(edge_min_pct)
        self.hard_tp_pct = None if hard_tp_pct is None else float(hard_tp_pct)
        self.cooldown_bars = int(cooldown_bars)
        self.size_fraction = float(size_fraction)

        self.prices = deque(maxlen=max(max_buffer, self.window + 5))
        self.position_qty = 0.0
        self.entry_price = None
        self.highest_price = None
        self.cooldown = 0

        # RSI Wilder
        self._avg_gain = None
        self._avg_loss = None
        self._last_price = None

        # sizing
        self.notional_per_trade = starting_capital * self.size_fraction

        # trailing “armed” solo dopo copertura costi+edge
        self.armed = False
        self.min_profitable_price = None

        # ---------- logging ----------
        fname = f"rsi_{stock}.csv".replace("/", "_")
        self.log_path = log_path or os.path.join("logs", fname)
        self._ensure_log_header()

    # ========== utils logging ==========
    def _ensure_log_header(self):
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        need_header = not os.path.exists(self.log_path) or os.path.getsize(self.log_path) == 0
        if need_header:
            with open(self.log_path, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=self._log_fields())
                w.writeheader()

    def _log_fields(self):
        return [
            "ts_wall", "bar_ts", "stock", "action", "reason", "price", "rsi", "qty",
            "in_position", "entry_price", "highest_price", "armed",
            "min_profitable_price", "trailing_floor", "protected_floor",
            "rsi_buy", "rsi_exit", "trailing_pct",
            "fee_buy_pct", "fee_sell_pct", "slippage_pct", "edge_min_pct", "hard_tp_pct",
            "window"
        ]

    def _to_iso(self, t):
        if t is None:
            return ""
        if isinstance(t, (int, float)):
            return datetime.fromtimestamp(float(t), tz=timezone.utc).isoformat()
        if isinstance(t, str):
            return t
        if isinstance(t, datetime):
            return t.astimezone(timezone.utc).isoformat()
        return str(t)

    def _write_log(self, data: dict, action: str, reason: str = "", qty: float | None = None,
                   trailing_floor: float | None = None, protected_floor: float | None = None, rsi_val: float | None = None):
        row = {
            "ts_wall": datetime.now(timezone.utc).isoformat(),
            "bar_ts": self._to_iso(data.get("timestamp")),
            "stock": self.stock,
            "action": action,
            "reason": reason or "",
            "price": float(data["price"]) if "price" in data and data["price"] is not None else "",
            "rsi": "" if rsi_val is None else float(rsi_val),
            "qty": "" if qty is None else float(qty),
            "in_position": int(self.position_qty > 0),
            "entry_price": "" if self.entry_price is None else float(self.entry_price),
            "highest_price": "" if self.highest_price is None else float(self.highest_price),
            "armed": int(bool(self.armed)),
            "min_profitable_price": "" if self.min_profitable_price is None else float(self.min_profitable_price),
            "trailing_floor": "" if trailing_floor is None else float(trailing_floor),
            "protected_floor": "" if protected_floor is None else float(protected_floor),
            "rsi_buy": self.rsi_buy,
            "rsi_exit": self.rsi_exit,
            "trailing_pct": self.trailing_pct,
            "fee_buy_pct": self.fee_buy_pct,
            "fee_sell_pct": self.fee_sell_pct,
            "slippage_pct": self.slippage_pct,
            "edge_min_pct": self.edge_min_pct,
            "hard_tp_pct": "" if self.hard_tp_pct is None else self.hard_tp_pct,
            "window": self.window,
        }
        with open(self.log_path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=self._log_fields())
            w.writerow(row)

    # ========== RSI Wilder ==========
    def _update_rsi_wilder(self, price):
        if self._last_price is None:
            self._last_price = price
            return None

        change = price - self._last_price
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        self._last_price = price

        if self._avg_gain is None or self._avg_loss is None:
            self.prices.append(price)
            if len(self.prices) < self.window + 1:
                return None
            import numpy as np
            deltas = np.diff(np.array(self.prices)[-self.window-1:])
            gains = np.clip(deltas, 0, None)
            losses = np.clip(-deltas, 0, None)
            self._avg_gain = gains.mean()
            self._avg_loss = losses.mean()
        else:
            n = self.window
            self._avg_gain = (self._avg_gain*(n-1) + gain) / n
            self._avg_loss = (self._avg_loss*(n-1) + loss) / n

        if self._avg_loss == 0:
            return 100.0
        rs = self._avg_gain / self._avg_loss
        return float(100 - (100 / (1 + rs)))

    def _required_net_edge(self):
        return self.fee_buy_pct + self.fee_sell_pct + 2.0 * self.slippage_pct + self.edge_min_pct

    # ========== Decisioni ==========
    def on_data(self, data):
        price = float(data["price"])
        self.prices.append(price)

        if self.cooldown > 0:
            self.cooldown -= 1

        rsi = self._update_rsi_wilder(price)
        if rsi is None:
            self._write_log(data, action="hold", rsi_val=None)   # log anche in warm-up
            return {"action": "hold", "confidence": 0.0}

        # ===== ENTRY =====
        if self.position_qty == 0 and self.cooldown == 0 and rsi < self.rsi_buy:
            if price > 0:
                qty = max(self.notional_per_trade / price, 0.0)
            else:
                qty = 0.0

            if qty > 0:
                self.position_qty = qty
                self.entry_price = price
                self.highest_price = price
                self.cooldown = self.cooldown_bars

                self.armed = False
                req = self._required_net_edge()
                self.min_profitable_price = self.entry_price * (1.0 + req)

                self._write_log(data, action="buy", qty=qty, rsi_val=rsi)
                return {"action": "buy", "confidence": 1.0, "quantity": qty}

        # ===== IN POSITION =====
        trailing_floor = None
        protected_floor = None

        if self.position_qty > 0:
            self.highest_price = max(self.highest_price, price)

            if not self.armed:
                if price >= self.min_profitable_price :
                    self.armed = True

            if self.armed:
                trailing_floor = self.highest_price * (1.0 - self.trailing_pct)
                #protected_floor = max(trailing_floor, self.min_profitable_price or trailing_floor)

                if price >= self.min_profitable_price :
                    qty = self.position_qty
                    self.position_qty = 0.0
                    self.entry_price = None
                    self.highest_price = None
                    self.cooldown = self.cooldown_bars
                    self.armed = False
                    self.min_profitable_price = None

                    self._write_log(data, action="sell", reason="trailing_protected", qty=qty,
                                    trailing_floor=trailing_floor, protected_floor=protected_floor, rsi_val=rsi)
                    return {"action": "sell", "confidence": 1.0, "quantity": qty, "reason": "trailing_protected"}

            # opzionale: hard TP
            if self.hard_tp_pct is not None and self.entry_price is not None:
                hard_tp_price = self.entry_price * (1.0 + self.hard_tp_pct)
                if price >= hard_tp_price:
                    qty = self.position_qty
                    self.position_qty = 0.0
                    self.entry_price = None
                    self.highest_price = None
                    self.cooldown = self.cooldown_bars
                    self.armed = False
                    self.min_profitable_price = None

                    self._write_log(data, action="sell", reason="hard_tp", qty=qty,
                                    trailing_floor=trailing_floor, protected_floor=protected_floor, rsi_val=rsi)
                    return {"action": "sell", "confidence": 1.0, "quantity": qty, "reason": "hard_tp"}

        # default: hold
        self._write_log(data, action="hold", rsi_val=rsi,
                        trailing_floor=trailing_floor, protected_floor=protected_floor)
        return {"action": "hold", "confidence": 0.0}
