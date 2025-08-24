# trading_system/backtest/portfolio_backtest.py
from __future__ import annotations
import os
import re
import csv
import importlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple

from trading_system.utils.portfolio_manager import PortfolioManager
from trading_system.utils.historical_downloader import fetch_crypto_bars

# ===================== UTIL LOCAL DATA =====================

def _norm_symbol(sym: str) -> str:
    return sym.lower().replace("/", "_").strip()

def _real_symbol(sym: str) -> str:
    return sym.upper().replace("_", "/")

def _file_symbol(sym_norm: str) -> str:
    # nome file con trattino: BTC-USD
    return sym_norm.upper().replace("_", "-")

def _parse_iso(ts: str) -> datetime:
    ts = ts.strip()
    if ts.endswith("Z"):
        ts = ts.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(ts)
    except Exception:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(ts, fmt)
                break
            except Exception:
                dt = None
        if dt is None:
            raise
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def _floor_min(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)

def _bucket_start(dt: datetime, tf_min: int) -> datetime:
    base = _floor_min(dt)
    return base - timedelta(minutes=(base.minute % tf_min))

def _infer_tf_from_path(path: str) -> Optional[int]:
    m = re.search(r'[/\\](\d{1,3})m[/\\]', path, re.IGNORECASE)
    if m: return int(m.group(1))
    m = re.search(r'_(\d{1,3})m(?:\.[A-Za-z0-9]+)?$', os.path.basename(path), re.IGNORECASE)
    if m: return int(m.group(1))
    return None

def _candidate_paths(symbol_variants: List[str], tf_min: int, data_dirs: List[str]) -> List[str]:
    cands: List[str] = []
    for root in data_dirs:
        for sym in symbol_variants:
            cands += [
                os.path.join(root, f"{sym}_{tf_min}m.csv"),
                os.path.join(root, f"{sym.replace('_','-')}_{tf_min}m.csv"),
                os.path.join(root, f"{sym.replace('_','')}_{tf_min}m.csv"),
                os.path.join(root, f"{tf_min}m", f"{sym}.csv"),
                os.path.join(root, f"{tf_min}m", f"{sym.replace('_','-')}.csv"),
                os.path.join(root, f"{tf_min}m", f"{sym.replace('_','')}.csv"),
            ]
    # fallback: 1m
    for root in data_dirs:
        for sym in symbol_variants:
            cands += [
                os.path.join(root, f"{sym}_1m.csv"),
                os.path.join(root, f"{sym.replace('_','-')}_1m.csv"),
                os.path.join(root, f"{sym.replace('_','')}_1m.csv"),
                os.path.join(root, "1m", f"{sym}.csv"),
                os.path.join(root, "1m", f"{sym.replace('_','-')}.csv"),
                os.path.join(root, "1m", f"{sym.replace('_','')}.csv"),
            ]
    # de-dup mantenendo ordine
    seen = set(); out = []
    for p in cands:
        if p not in seen:
            seen.add(p); out.append(p)
    return out

def _read_csv_bars(path: str) -> List[dict]:
    bars: List[dict] = []
    with open(path, "r", newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        def pick(row: dict, keys: List[str], default=None):
            for k in keys:
                if k in row and row[k] not in (None, ""):
                    return row[k]
            return default
        for row in rdr:
            t = pick(row, ["t","timestamp","time","datetime","date"])
            o = pick(row, ["o","open","Open"])
            h = pick(row, ["h","high","High"])
            l = pick(row, ["l","low","Low"])
            c = pick(row, ["c","close","Close","adj_close"])
            v = pick(row, ["v","volume","Volume"], "0")
            if t is None or o is None or h is None or l is None or c is None:
                continue
            try:
                bars.append({
                    "t": _parse_iso(str(t)).isoformat(),
                    "o": float(o), "h": float(h), "l": float(l), "c": float(c), "v": float(v or 0.0)
                })
            except Exception:
                continue
    bars.sort(key=lambda x: x["t"])
    return bars

def _aggregate_bars(bars: List[dict], tf_in_min: int, tf_out_min: int) -> List[dict]:
    if tf_in_min == tf_out_min:
        return bars[:]
    out: List[dict] = []
    cur_start: Optional[datetime] = None
    o = h = l = c = v = None
    for b in bars:
        ts = _parse_iso(b["t"])
        bstart = _bucket_start(ts, tf_out_min)
        if cur_start is None:
            cur_start = bstart
            o = b["o"]; h = b["h"]; l = b["l"]; c = b["c"]; v = b["v"]
        elif bstart != cur_start:
            out.append({
                "t": (cur_start + timedelta(minutes=tf_out_min)).isoformat(),
                "o": float(o), "h": float(h), "l": float(l), "c": float(c), "v": float(v or 0.0)
            })
            cur_start = bstart
            o = b["o"]; h = b["h"]; l = b["l"]; c = b["c"]; v = b["v"]
        else:
            h = max(h, b["h"])
            l = min(l, b["l"])
            c = b["c"]
            v = (v or 0.0) + (b.get("v") or 0.0)
    if cur_start is not None:
        out.append({
            "t": (cur_start + timedelta(minutes=tf_out_min)).isoformat(),
            "o": float(o), "h": float(h), "l": float(l), "c": float(c), "v": float(v or 0.0)
        })
    return out

def _filter_range(bars: List[dict], start_iso: str, end_iso: str) -> List[dict]:
    if not bars: return bars
    start_dt = _parse_iso(start_iso)
    end_dt   = _parse_iso(end_iso)
    return [b for b in bars if start_dt <= _parse_iso(b["t"]) <= end_dt]

def _save_bars_csv(path: str, bars: List[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t","o","h","l","c","v"])
        for b in bars:
            w.writerow([b["t"], b["o"], b["h"], b["l"], b["c"], b.get("v", 0.0)])

def fetch_local_bars(
    symbols: List[str],
    start_iso: str,
    end_iso: str,
    timeframe_minutes: int,
    data_dirs: Optional[List[str]] = None,
    allow_download: bool = True,
) -> Dict[str, List[dict]]:
    """
    Carica barre DA CSV locali. Se mancano e allow_download=True:
      - scarica da Alpaca al tf richiesto
      - salva in data/<TF>m/<SYMBOL>.csv (SYMBOL come BTC-USD)
      - ricarica e restituisce.
    Restituisce: { "BTC/USD": [ {t,o,h,l,c,v}, ...], ... }
    """
    data_dirs = data_dirs or ["data", os.path.join("data", "crypto")]
    res: Dict[str, List[dict]] = {}
    missing: List[str] = []           # simboli (formato 'BTC/USD') da scaricare

    # 1) tenta lettura locale
    for sym in symbols:
        sym_norm = _norm_symbol(sym)
        sym_real = _real_symbol(sym_norm)  # BTC/USD
        file_sym = _file_symbol(sym_norm)  # BTC-USD
        variants = [
            sym_norm.upper(),                   # BTC_USD
            file_sym,                           # BTC-USD
            sym_norm.upper().replace("_",""),   # BTCUSD
        ]
        cands = _candidate_paths(variants, timeframe_minutes, data_dirs)
        picked = None; tf_file = None
        for p in cands:
            if os.path.isfile(p):
                picked = p
                tf_file = _infer_tf_from_path(p) or timeframe_minutes
                break

        if picked:
            rows = _read_csv_bars(picked)
            if tf_file != timeframe_minutes:
                rows = _aggregate_bars(rows, tf_file, timeframe_minutes)
            rows = _filter_range(rows, start_iso, end_iso)
            res[sym_real] = rows
            print(f"[Backtest/LOCAL] {sym} <- {os.path.relpath(picked)}  bars={len(rows)} (tf={timeframe_minutes}m)")
        else:
            print(f"[Backtest/LOCAL] CSV non trovato per {sym}. Proverò a scaricare…" if allow_download else
                  f"[Backtest/LOCAL] CSV non trovato per {sym}.")
            res[sym_real] = []
            if allow_download:
                missing.append(sym_real)

    # 2) se mancano e consentito, scarica e salva
    if allow_download and missing:
        print(f"[Backtest/DL] Scarico {timeframe_minutes}m bars per: {missing}")
        try:
            bars_remote = fetch_crypto_bars(
                symbols=missing,                 # formati 'BTC/USD'
                start_iso=start_iso,
                end_iso=end_iso,
                timeframe_minutes=timeframe_minutes,
                api_key=None,                    # usa env PAPER_API_* o APCA_API_*
                api_secret=None,
            )
        except Exception as e:
            print(f"[Backtest/DL] ERRORE download: {e}")
            bars_remote = {}

        for sym_real in missing:
            arr = bars_remote.get(sym_real, []) or []
            if not arr:
                print(f"[Backtest/DL] Nessun dato per {sym_real} dall'API.")
                continue
            # normalizza chiavi remote -> locali
            rows = [{"t": b["t"], "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"], "v": b.get("v", 0.0)} for b in arr]
            # salva su data/<TF>m/<SYMBOL>.csv
            file_sym = sym_real.replace("/", "-")  # BTC-USD
            out_path = os.path.join("data", f"{timeframe_minutes}m", f"{file_sym}.csv")
            _save_bars_csv(out_path, rows)
            print(f"[Backtest/DL] Salvato {len(rows)} barre in {os.path.relpath(out_path)}")

            # carica in memoria (già filtrate per data dall'API, ma filtro comunque)
            rows = _filter_range(rows, start_iso, end_iso)
            res[sym_real] = rows

    return res

# ===================== RUNNER BACKTEST =====================

class BacktestStrategyRunner:
    def __init__(self, stock: str, strategy_cls, initial_capital: float,
                 portfolio: PortfolioManager, bars: List[dict], backtest_log_suffix: str = "backtest"):
        self.stock = stock.lower().replace("/", "_")
        self.portfolio = portfolio
        self.strategy = strategy_cls(
            self.stock,
            initial_capital,
            log_path=os.path.join("logs", f"{backtest_log_suffix}_rsi_{self.stock}.csv")
        )
        self.bars = bars

    def run(self):
        stock_name = self.stock.upper().replace("_", "/")
        print(f"[{stock_name}] BacktestRunner starting on {len(self.bars)} bars...")
        for b in self.bars:
            price = float(b["c"])
            data = {"symbol": self.stock, "price": price, "timestamp": b.get("t")}
            signal = self.strategy.on_data(data)

            if signal["action"] == "buy":
                qty = float(signal.get("quantity", 0.0))
                if qty > 0:
                    self.portfolio.book_buy(self.stock, qty, price)

            elif signal["action"] == "sell":
                cur = self.portfolio.stock_state.get_state(self.stock) or {}
                qty = float(cur.get("quantity", 0))
                if qty > 0:
                    self.portfolio.book_sell(self.stock, qty, price)
        print(f"[{stock_name}] BacktestRunner done.")

class PortfolioBacktester:
    def __init__(self, portfolio: PortfolioManager, strategies_map: Dict[str, str],
                 timeframe_minutes: int, start_iso: str, end_iso: str,
                 data_dirs: Optional[List[str]] = None,
                 allow_download: bool = True):
        self.portfolio = portfolio
        self.strategies_map = strategies_map
        self.tf = int(timeframe_minutes)
        self.start_iso = start_iso
        self.end_iso = end_iso
        self.data_dirs = data_dirs or ["data", os.path.join("data", "crypto")]
        self.allow_download = allow_download

        self.pnl_log_path = os.path.join("logs", "backtest_pnl.csv")
        os.makedirs("logs", exist_ok=True)
        if not os.path.exists(self.pnl_log_path) or os.path.getsize(self.pnl_log_path) == 0:
            with open(self.pnl_log_path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(["ts_wall", "symbol", "realized_pnl_total"])

    def _append_pnl(self, symbol: str):
        total = 0.0
        all_states = self.portfolio.stock_state.get_all_states()
        for _, st in all_states.items():
            total += float(st.get("realized_pnl", 0.0))
        with open(self.pnl_log_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([datetime.now(timezone.utc).isoformat(), symbol, total])

    def run(self):
        # 1) carica (o scarica+salva) i dati
        symbols = list(self.strategies_map.keys())
        print(f"[Backtest] Loading {self.tf}m bars for {symbols} from {self.start_iso} to {self.end_iso} ...")
        bars_by_sym = fetch_local_bars(
            symbols=symbols,
            start_iso=self.start_iso,
            end_iso=self.end_iso,
            timeframe_minutes=self.tf,
            data_dirs=self.data_dirs,
            allow_download=self.allow_download,
        )
        print("[Backtest] Data ready.")

        # 2) esecuzione sequenziale delle strategie
        for stock, module_name in self.strategies_map.items():
            sym_norm = stock.lower().replace("/", "_")
            budget_for_stock = float(self.portfolio.allocations.get(sym_norm, 0.0)) * self.portfolio.initial_budget

            try:
                mod = importlib.import_module(f"trading_system.strategies.{module_name}")
                strategy_cls = getattr(mod, "Strategy")
            except Exception as e:
                print(f"[Backtest] Cannot load strategy {module_name} for {stock}: {e}")
                continue

            series = bars_by_sym.get(_real_symbol(sym_norm)) or []
            if not series:
                print(f"[Backtest] No bars for {stock}, skipping.")
                continue

            runner = BacktestStrategyRunner(
                stock=sym_norm,
                strategy_cls=strategy_cls,
                initial_capital=budget_for_stock,
                portfolio=self.portfolio,
                bars=series,
                backtest_log_suffix="backtest"
            )
            runner.run()
            self._append_pnl(stock)

        # 3) riepilogo
        all_states = self.portfolio.stock_state.get_all_states()
        total_realized = sum(float(st.get("realized_pnl", 0.0)) for st in all_states.values())
        print("\n[Backtest] Summary:")
        for s, st in all_states.items():
            print(f"  - {s.upper()}: realized PnL = {float(st.get('realized_pnl', 0.0)):.2f}")
        print(f"  TOTAL realized PnL = {total_realized:.2f}")
        print(f"  PnL log written to: {self.pnl_log_path}")
