import requests
from datetime import datetime
import pytz

timezone = pytz.timezone("America/Sao_Paulo")

def buscar_candles(symbol, limit=40):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": "1m", "limit": limit}
    r = requests.get(url, params=params, timeout=10)
    raw = r.json()
    
    candles = []
    for k in raw:
        dt    = datetime.fromtimestamp(k[0] / 1000, tz=timezone)
        open_ = float(k[1])
        close = float(k[4])
        candles.append({"datetime": dt, "open": open_, "close": close})
    
    return candles[:-1]  # descarta vela aberta

candles = buscar_candles("BTCUSDT")

print(f"Total candles: {len(candles)}")
print("\nÚltimas 3 velas:")
for c in candles[-3:]:
    direcao = "🟢 CALL" if c["close"] > c["open"] else "🔴 PUT"
    print(f"  {c['datetime'].strftime('%H:%M')} | open={c['open']} close={c['close']} | {direcao}")

altas  = sum(c["close"] > c["open"] for c in candles[-3:])
baixas = 3 - altas
print(f"\nAltas: {altas} | Baixas: {baixas}")
print(f"Sinal: {'CALL' if altas >= 2 else 'PUT' if baixas >= 2 else 'Nenhum (lateral)'}")
