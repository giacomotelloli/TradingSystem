# alpaca_bars_adapter.py
import os
import threading
from datetime import datetime, timezone
from typing import Callable, Optional

# pip install alpaca-py
from alpaca.data.live.crypto import CryptoDataStream  # type: ignore


def to_alpaca_symbol(sym: str) -> str:
    s = sym.strip().upper().replace("-", "/").replace("_", "/")
    if "/" not in s and len(s) >= 6:
        s = f"{s[:3]}/{s[3:]}"
    return s


class AlpacaBars1mAdapter:
    """
    Sottoscrive le **minute bars (1m)** crypto di Alpaca e chiama on_bar_callback(dict).
    Implementazione thread-based, senza event loop personalizzati.
    """
    def __init__(
        self,
        symbol: str,
        on_bar_callback: Callable[[dict], None],
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        feed: str = "us",
    ):
        self.symbol = to_alpaca_symbol(symbol)
        self.on_bar_callback = on_bar_callback
        self.api_key = api_key or os.environ.get("APCA_API_KEY_ID", "")
        self.api_secret = api_secret or os.environ.get("APCA_API_SECRET_KEY", "")
        self.feed = feed

        if not self.api_key or not self.api_secret:
            raise RuntimeError("Manca APCA_API_KEY_ID o APCA_API_SECRET_KEY (env o parametri).")

        self._stream: Optional[CryptoDataStream] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

    def _build_stream(self) -> CryptoDataStream:
        # CryptoDataStream gestisce auth e loop internamente
        stream = CryptoDataStream(api_key=self.api_key, secret_key=self.api_secret)

        async def handle_bar(bar):
            # bar: alpaca.data.models.Bar
            ts = getattr(bar, "timestamp", None)
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            elif not isinstance(ts, datetime):
                ts = datetime.now(timezone.utc)

            payload = {
                "symbol": getattr(bar, "symbol", None) or self.symbol,
                "timestamp": ts.astimezone(timezone.utc).isoformat(),
                "open": float(getattr(bar, "open", 0.0)),
                "high": float(getattr(bar, "high", 0.0)),
                "low":  float(getattr(bar, "low", 0.0)),
                "close": float(getattr(bar, "close", 0.0)),
                "volume": float(getattr(bar, "volume", 0.0)),
                "timeframe": "1Min",
                "source": "alpaca_ws",
            }
            self.on_bar_callback(payload)

        # subscribe alle **minute bars**
        stream.subscribe_bars(handle_bar, self.symbol)

        # opzionale: correzioni tardive
        # stream.subscribe_updated_bars(handle_bar, self.symbol)

        return stream

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True

        def _runner():
            try:
                self._stream = self._build_stream()
                # BLOCCANTE: mantiene aperto il websocket e il suo event loop interno
                self._stream.run()
            except Exception as e:
                print(f"[AlpacaBars1mAdapter] stream.run() exception: {e}")
            finally:
                with self._lock:
                    self._running = False

        self._thread = threading.Thread(target=_runner, name="AlpacaBars1mThread", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0):
        with self._lock:
            if not self._running:
                return
        try:
            if self._stream:
                self._stream.stop()
        except Exception:
            pass
        if self._thread:
            self._thread.join(timeout=timeout)
        with self._lock:
            self._running = False
