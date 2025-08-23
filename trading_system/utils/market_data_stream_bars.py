# market_data_stream_bars.py
from typing import Callable, Optional, Deque, Tuple, List
from collections import deque
from datetime import datetime, timedelta
import threading

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Rectangle

from trading_system.utils.alpaca_bars_adapter import AlpacaBars1mAdapter


def _parse_iso_ts(ts_iso: str) -> datetime:
    # accetta "...Z" o offset +00:00
    return datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))


class _BarBuffer:
    """
    Buffer thread-safe di barre (timestamp, o,h,l,c,vol) con finestra temporale scorrevole.
    Le barre in ingresso sono già 1m: manteniamo solo l'ultima finestra (es. 24h).
    """
    def __init__(self, window: timedelta = timedelta(hours=24)):
        self._lock = threading.Lock()
        self.window = window
        # deques allineati
        self.ts: Deque[datetime] = deque()
        self.o: Deque[float] = deque()
        self.h: Deque[float] = deque()
        self.l: Deque[float] = deque()
        self.c: Deque[float] = deque()
        self.v: Deque[float] = deque()

    def add_bar(self, ts_iso: str, o: float, h: float, l: float, c: float, v: float):
        t = _parse_iso_ts(ts_iso)
        with self._lock:
            self.ts.append(t)
            self.o.append(float(o))
            self.h.append(float(h))
            self.l.append(float(l))
            self.c.append(float(c))
            self.v.append(float(v))
            # purge vecchi
            cutoff = t - self.window
            while self.ts and self.ts[0] < cutoff:
                self.ts.popleft()
                self.o.popleft()
                self.h.popleft()
                self.l.popleft()
                self.c.popleft()
                self.v.popleft()

    def snapshot(self) -> Tuple[List[datetime], List[float], List[float], List[float], List[float], List[float]]:
        with self._lock:
            return (list(self.ts), list(self.o), list(self.h), list(self.l), list(self.c), list(self.v))


class _LiveCandlestickChart:
    """
    Grafico live delle candele 1m + linea dei close sovrapposta.
    - Niente dipendenze esterne: candlestick disegnate con Rectangle + vlines.
    - refresh_ms: ogni quanto aggiornare il grafico (di solito 5–15s è ok; i dati arrivano 1/min).
    """
    def __init__(
        self,
        buffer: _BarBuffer,
        title: str = "Candlestick (1m) — Close line",
        refresh_ms: int = 10_000,
    ):
        self.buffer = buffer
        self.refresh_ms = refresh_ms
        self.fig, self.ax = plt.subplots()
        self.ax.set_title(title)
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Price")
        self.ax.grid(True)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%m %H:%M'))
        self.ax.xaxis.set_major_locator(mdates.AutoDateLocator())

        # linea dei close
        (self.close_line,) = self.ax.plot([], [], linewidth=1.3)

        # per aggiornare pulito, teniamo traccia delle patch disegnate
        self._candle_patches: List[Rectangle] = []
        self._wick_lines = []

    def _clear_candles(self):
        for p in self._candle_patches:
            p.remove()
        self._candle_patches.clear()
        for ln in self._wick_lines:
            try:
                ln.remove()
            except Exception:
                pass
        self._wick_lines.clear()

    def _draw_candles(self, x: List[float], o: List[float], h: List[float], l: List[float], c: List[float]):
        """
        Disegna le candele: corpo = rettangolo, stoppini = linee verticali.
        Non imposto colori specifici (up/down seguirà il default di Matplotlib se cambiato globalmente).
        """
        # larghezza corpo: frazione dello spacing medio (usiamo 0.6 del passo)
        width = 0.6 * (x[1] - x[0]) if len(x) >= 2 else 0.6

        for xi, oi, hi, li, ci in zip(x, o, h, l, c):
            # stoppino
            ln = self.ax.vlines(xi, li, hi, linewidth=1.0)
            self._wick_lines.append(ln)

            # corpo
            lower = min(oi, ci)
            height = abs(ci - oi)
            rect = Rectangle(
                (xi - width/2, lower),  # (x left, y bottom)
                width,
                max(height, 1e-9),      # evita height=0
                linewidth=1.0,
                fill=True,
                alpha=0.8,
            )
            self.ax.add_patch(rect)
            self._candle_patches.append(rect)

    def _update(self, _frame):
        ts, o, h, l, c, _v = self.buffer.snapshot()
        if not ts:
            return self.close_line,

        # converti timestamp a numeri matplotlib (per posizionare i rettangoli)
        x = mdates.date2num(ts)

        # ripulisci e ridisegna candele
        self._clear_candles()
        self._draw_candles(x, o, h, l, c)

        # linea dei close (evidenziata)
        self.close_line.set_data(ts, c)

        # limiti assi
        self.ax.set_xlim(ts[0], ts[-1])
        ymin, ymax = min(l), max(h)
        pad = (ymax - ymin) * 0.07 if ymax > ymin else max(1e-6, ymin * 0.001)
        self.ax.set_ylim(ymin - pad, ymax + pad)

        # titolo con last close
        last = c[-1]
        self.ax.set_title(f"Candlestick (1m) — last close: {last}")

        self.fig.autofmt_xdate()
        return self.close_line,

    def show(self):
        # salvo l'oggetto in un attributo per non farlo eliminare dal GC
        self.anim = FuncAnimation(
            self.fig,
            self._update,
            interval=self.refresh_ms,
            blit=False,
            cache_frame_data=False   # <-- aggiunto per sopprimere il warning
        )
        plt.tight_layout()
        plt.show()



class MarketDataStreamBars:
    """
    Sostituto drop-in della tua MarketDataStream per **minute bars (1m)** Alpaca,
    con integrazione del grafico live a candele + linea dei close.

    Modalità d'uso:
      1) start()/stop(): solo streaming senza grafico (come prima).
      2) run_with_chart(): avvia stream + finestra grafico; chiudendo il grafico ferma lo stream.
    """
    def __init__(
        self,
        stock: str,
        on_data_callback: Callable[[dict], None] | None = None,
        trading_interface=None,   # compatibilità
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        chart_window: timedelta = timedelta(hours=24),
        chart_refresh_ms: int = 10_000,
        chart_title: Optional[str] = None,
    ):
        self.stock = stock
        self.on_data_callback = on_data_callback
        self.trading_interface = trading_interface

        # buffer per il grafico
        self._buffer = _BarBuffer(window=chart_window)

        # adapter Alpaca
        self._adapter = AlpacaBars1mAdapter(
            symbol=stock,
            on_bar_callback=self._on_bar,  # nostro handler interno che alimenta buffer + inoltra
            api_key=api_key,
            api_secret=api_secret
        )

        self._chart = _LiveCandlestickChart(
            buffer=self._buffer,
            title=chart_title or f"{stock.upper().replace('_','/')}: Candlestick (1m) — Close line",
            refresh_ms=chart_refresh_ms,
        )

    # ==== STREAM LIFECYCLE ====================================================
    def start(self):
        self._adapter.start()

    def stop(self):
        self._adapter.stop()

    # ==== CALLBACK INTERNO ====================================================
    def _on_bar(self, bar: dict):
        """
        bar tipico:
          {
            "symbol":"BTC/USD", "timestamp":"...+00:00",
            "open":..., "high":..., "low":..., "close":..., "volume":...,
            "timeframe":"1Min", "source":"alpaca_ws"
          }
        """
        ts = bar.get("timestamp")
        if ts:
            try:
                self._buffer.add_bar(
                    ts_iso=ts,
                    o=bar.get("open", 0.0),
                    h=bar.get("high", 0.0),
                    l=bar.get("low", 0.0),
                    c=bar.get("close", 0.0),
                    v=bar.get("volume", 0.0),
                )
            except Exception as e:
                print(f"[MarketDataStreamBars] Errore buffer.add_bar: {e}")

        # inoltra al callback utente (se presente)
        if self.on_data_callback:
            try:
                self.on_data_callback(bar)
            except Exception as e:
                print(f"[MarketDataStreamBars] on_data_callback error: {e}")

    # ==== MODALITÀ CON GRAFICO ===============================================
    def run_with_chart(self):
        """
        Avvia lo stream e mostra la finestra del grafico live.
        Quando chiudi la finestra, lo stream viene stoppato.
        """
        print("Starting Alpaca 1m bars stream + live candlestick chart…")
        self.start()
        try:
            self._chart.show()  # blocca finché la finestra è aperta
        finally:
            self.stop()
            print("Stopped.")
