# trading_system/utils/historical_downloader.py
from __future__ import annotations
import os
import time
import requests
from typing import Dict, List, Any

ALPACA_DATA_BASE = "https://data.alpaca.markets/v1beta3/crypto/us/bars"

def _norm_symbol(sym: str) -> str:
    s = sym.strip().upper().replace("_", "/").replace("-", "/")
    if "/" not in s and len(s) >= 6:
        s = f"{s[:3]}/{s[3:]}"
    return s

def fetch_crypto_bars(
    symbols: List[str],
    start_iso: str,
    end_iso: str,
    timeframe_minutes: int,
    api_key: str | None = None,
    api_secret: str | None = None,
) -> Dict[str, List[dict]]:
    """
    Scarica barre storiche crypto per più simboli da Alpaca v1beta3.
    Ritorna: { "BTC/USD": [ {t: iso, o:..., h:..., l:..., c:..., v:...}, ... ], ... }
    """
    api_key = api_key or os.getenv("PAPER_API_KEY_ID") or os.getenv("APCA_API_KEY_ID")
    api_secret = api_secret or os.getenv("PAPER_API_SECRET_KEY") or os.getenv("APCA_API_SECRET_KEY")
    if not api_key or not api_secret:
        raise RuntimeError("API key/secret Alpaca mancanti (env PAPER_API_* o APCA_API_*).")

    headers = {
        "Apca-Api-Key-Id": api_key,
        "Apca-Api-Secret-Key": api_secret,
    }

    tf = f"{int(timeframe_minutes)}Min"
    syms = [_norm_symbol(s) for s in symbols]
    result: Dict[str, List[dict]] = {s: [] for s in syms}

    params = {
        "symbols": ",".join(syms),
        "timeframe": tf,
        "start": start_iso,
        "end": end_iso,
        "limit": 10_000,  # massimo consentito per pagina
    }

    next_page_token = None
    while True:
        p = dict(params)
        if next_page_token:
            p["page_token"] = next_page_token
        r = requests.get(ALPACA_DATA_BASE, headers=headers, params=p, timeout=30)
        r.raise_for_status()
        data = r.json() or {}

        # formato: {"bars": {"BTC/USD":[{t:..., o:...,h:...,l:...,c:...,v:...}, ...], "ETH/USD":[...]}, "next_page_token": ...}
        bars = (data.get("bars") or {}) if isinstance(data, dict) else {}
        for sym, arr in bars.items():
            if not isinstance(arr, list):
                continue
            result.setdefault(sym, [])
            result[sym].extend(arr)

        next_page_token = data.get("next_page_token")
        if not next_page_token:
            break
        # Piccolo respiro per non saturare
        time.sleep(0.05)

    # Ordina per timestamp
    for sym in result:
        result[sym].sort(key=lambda x: x.get("t", ""))

    return result
