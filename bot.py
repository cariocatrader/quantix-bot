import telebot
import requests
import threading
import time
import os
from datetime import datetime, timedelta, timezone
import pytz
import math

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise Exception("TOKEN não encontrado")
bot = telebot.TeleBot(TOKEN)

BR_TZ = pytz.timezone('America/Sao_Paulo')
UTC_TZ = pytz.timezone('UTC')

COINGECKO_URL = "https://api.coingecko.com/api/v3"
WIN_GIF = "win.gif"
LOSS_GIF = "loss.gif"

SYMBOLS = {
    "bitcoin": "₿ Bitcoin", "ethereum": "Ξ Ethereum",
    "binancecoin": "🟡 BNB", "solana": "🟣 Solana",
    "ripple": "💧 XRP", "cardano": "🔵 Cardano",
    "dogecoin": "🐶 Doge", "litecoin": "🪙 Litecoin",
    "polkadot": "⚫ Polkadot", "avalanche-2": "🔺 Avalanche"
}
VALID_COIN_IDS = set(SYMBOLS.keys())

user_state = {}

def get_br_time(fmt="%H:%M"):
    return datetime.now(BR_TZ).strftime(fmt)

class Timer:
    last_call = None

def analyze(coin_id):
    if coin_id not in VALID_COIN_IDS:
        return "COMPRA"
    if Timer.last_call:
        diff = (datetime.now(BR_TZ) - Timer.last_call).total_seconds()
        if diff < 45:
            time.sleep(45 - diff)
    Timer.last_call = datetime.now(BR_TZ)

    try:
        params = {"vs_currency": "usd", "days": "1"}
        r = requests.get(
            f"{COINGECKO_URL}/coins/{coin_id}/ohlc",
            params=params,
            timeout=20
        )
        if r.status_code != 200:
            return "COMPRA"
        data = r.json()
        if not data or not isinstance(data, list):
            return "COMPRA"
        closes = [float(row[4]) for row in data[-5:] if isinstance(row, list) and len(row) >= 5]
        if len(closes) < 5:
            return "COMPRA"
        return "COMPRA" if closes[-1] > closes[-3] else "VENDA"
    except Exception as e:
        return "COMPRA"

def get_result(coin_id, direction, entry_time_dt):
    exp = user_state.get("exp", "1")
    wait_time = 65 if exp == "1" else 310
    entry_time_str = entry_time_dt.strftime("%H:%M")

    now = datetime.now(BR_TZ)
    entry_time = BR_TZ.localize(datetime.strptime(entry_time_str, "%H:%M"))
    entry_time = entry_time.replace(second=0, microsecond=0)
    target_time = entry_time + timedelta(seconds=wait_time)

    wait = (target_time - now).total_seconds()
    if wait < 0:
        wait = 0

    if wait > 0:
        time.sleep(wait)

    try:
        params = {"vs_currency": "usd", "days": "1"}
        r = requests.get(
            f"{COINGECKO_URL}/coins/{coin_id}/ohlc",
            params=params,
            timeout=20
        )
        if r.status_code != 200:
            return None

        data = r.json()
        if not data or not isinstance(data, list):
            return None

        target_year = target_time.year
        target_month = target_time.month
        target_day = target_time.day
        target_hour = target_time.hour
        target_minute = target_time.minute

        for i in range(len(data)-1, max(-1, len(data)-100), -1):
            row = data[i]
            if not isinstance(row, list) or len(row) < 5:
                continue
            try:
                ts = row[0] / 1000
                o = float(row[1])
                c = float(row[4])
                candle_dt = datetime.fromtimestamp(ts, tz=UTC_TZ).astimezone(BR_TZ)
                if (candle_dt.year == target_year and
                    candle_dt.month == target_month and
                    candle_dt.day == target_day and
                    candle_dt.hour == target_hour and
                    candle_dt.minute in [target_minute, target_minute + 1]):
                    return "WIN" if (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o) else "LOSS"
            except Exception as e:
                pass
        if data:
            row = data[-1]
            if isinstance(row, list) and len(row) >= 5:
                try:
                    ts = row[0] / 1000
                    o = float(row[1])
                    c = float(row[4])
                    if (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o):
                        return "WIN"
                    else:
                        return "LOSS"
                except Exception as e:
                    pass
    except Exception as e:
        pass
    return None

@bot.message_handler(commands=["start"])
def start(m):
    bot.send_message(m.chat.id, "🤖 Bot Ativo")
    bot.send_message(m.chat.id, "Use /sinal para gerar sinal")

@bot.message_handler(commands=["sinal"])
def sinal(m):
    if m.chat.id not in VALID_COIN_IDS:
        bot.send_message(m.chat.id, "Escolha ativo")
        return

    coin_id = m.chat.id
    direction = analyze(coin_id)
    text = f"""
🎉 SINAL GERADO!

━━━━━━━━━━━━━━━━━━━
商贸 {SYMBOLS[coin_id]}
⏱ Entrada: {get_br_time()}
🎯 {direction}
    """
    bot.send_message(m.chat.id, text)

    def check_result():
        entry_time_dt = datetime.now(BR_TZ)
        result = get_result(coin_id, direction, entry_time_dt)
        if result is None:
            bot.send_message(coin_id, f"❌ Não foi possível validar o resultado para {SYMBOLS[coin_id]} às {entry_time_dt.strftime('%H:%M')}.")
        else:
            status = "✅ WIN" if result == "WIN" else "❌ LOSS"
            text = f"""
🎯 RESULTADO FINAL

━━━━━━━━━━━━━━━━━━
商贸 {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time_dt.strftime('%H:%M')}
🎯 {direction}
🏆 {status}
            """
            gif_file = WIN_GIF if result == "WIN" else LOSS_GIF
            send_animation_safe(coin_id, gif_BINARY, text)

    threading.Thread(target=check_result, daemon=True).start()

print("🚀 Bot Ativo - 1 chamada CoinGecko, resultado só após 65/310s")
bot.remove_webhook()
time.sleep(2)
bot.infinity_polling()
