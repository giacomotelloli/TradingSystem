# trading_system/utils/bar_aggregator_stream.py
from __future__ import annotations
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional, Dict, Any, List

from trading_system.utils.alpaca_bars_adapter import AlpacaBars1mAdapter

def _floor_to_minute(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)

def _parse_ts(ts_iso: str) -> datetime:
    # supporta ...Z o +00:00
    return datetime.fromisoformat(ts_iso.replace("Z", "+00:00")).astimezone(timezone.utc)

class AggregatingBarStream:
    """
    Riceve barre 1m via AlpacaBars1mAdapter e aggrega in barre di N minuti.
    Chiama `on_bar_agg( dict )` alla CHIUSURA della candela aggregata.
    """
    def __init__(
        self,
        symbol: str,
        timeframe_minutes: int,
        on_bar_agg: Callable[[Dict[str, Any]], None],
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ):
        if timeframe_minutes < 1:
            raise ValueError("timeframe_minutes deve essere >= 1")

        self.symbol = symbol
        self.tf = timeframe_minutes
        self.on_bar_agg = on_bar_agg

        self._adapter = AlpacaBars1mAdapter(
            symbol=symbol,
            on_bar_callback=self._on_bar_1m,
            api_key=api_key,
            api_secret=api_secret,
        )

        self._lock = threading.Lock()
        self._bucket_start: Optional[datetime] = None
        self._o = self._h = self._l = self._c = None
        self._v = 0.0

    def start(self):
        self._adapter.start()

    def stop(self):
        self._adapter.stop()

    # ---- handler interno su barre 1m Alpaca ----
    def _on_bar_1m(self, bar: Dict[str, Any]):
        """
        bar: {"timestamp": iso, "open":..., "high":..., "low":..., "close":..., "volume":...}
        """
        ts = _parse_ts(bar["timestamp"])
        o = float(bar["open"]); h = float(bar["high"])
        l = float(bar["low"]);  c = float(bar["close"]); v = float(bar.get("volume", 0.0))

        # bucket di aggregazione: floor all'inizio minuto, poi blocchi da tf minuti
        t0 = _floor_to_minute(ts)
        bucket_start = t0 - timedelta(minutes=(t0.minute % self.tf))

        with self._lock:
            # se cambiamo bucket, chiudiamo il precedente (se esiste)
            if self._bucket_start is not None and bucket_start != self._bucket_start:
                self._emit_current_locked(end_time=self._bucket_start + timedelta(minutes=self.tf))

                # reset per nuovo bucket
                self._bucket_start = bucket_start
                self._o = o; self._h = h; self._l = l; self._c = c; self._v = v
            else:
                # stesso bucket (o primo)
                if self._bucket_start is None:
                    self._bucket_start = bucket_start
                    self._o = o; self._h = h; self._l = l; self._c = c; self._v = v
                else:
                    self._h = max(self._h, h)
                    self._l = min(self._l, l)
                    self._c = c
                    self._v += v

            # NOTA: qui NON emettiamo ancora; emettiamo alla PRIMA 1m bar del bucket successivo
            # (quindi la candela è "consuntivata"). In alternativa potresti usare timer.

    def _emit_current_locked(self, end_time: datetime):
        if self._bucket_start is None:
            return
        payload = {
            "symbol": self.symbol.upper().replace("_","/"),
            "timeframe": f"{self.tf}Min",
            "start": self._bucket_start.isoformat(),
            "end": end_time.isoformat(),
            "open": self._o,
            "high": self._h,
            "low": self._l,
            "close": self._c,
            "volume": self._v,
        }
        # callback utente
        try:
            self.on_bar_agg(payload)
        except Exception as e:
            print(f"[AggregatingBarStream] on_bar_agg error: {e}")

    # opzionale: chiama per flush finale quando stoppi lo stream
    def flush(self):
        with self._lock:
            if self._bucket_start is not None:
                self._emit_current_locked(self._bucket_start + timedelta(minutes=self.tf))
                self._bucket_start = None
