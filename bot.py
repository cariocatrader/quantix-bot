import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import websocket
import json
import threading
import time
from datetime import datetime, timedelta
import pytz
import os

TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN, threaded=True)

tz = pytz.timezone("America/Sao_Paulo")

# =========================
# PARIDADES
# =========================

SYMBOLS = {
    "BTCUSDT": "BTC/USDT",
    "ETHUSDT": "ETH/USDT",
    "BNBUSDT": "BNB/USDT",
    "SOLUSDT": "SOL/USDT",
    "XRPUSDT": "XRP/USDT",
    "ADAUSDT": "ADA/USDT",
    "DOGEUSDT": "DOGE/USDT",
    "LTCUSDT": "LTC/USDT",
    "DOTUSDT": "DOT/USDT",
    "AVAXUSDT": "AVAX/USDT"
}

# =========================
# ESTADO GLOBAL
# =========================

active_signals = {}

# =========================
# UTIL
# =========================

def now():
    return datetime.now(tz)

def btn_final():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Novo Sinal", callback_data="start"))
    return kb

# =========================
# WEBSOCKET BINANCE
# =========================

STREAM = "wss://stream.binance.com:9443/ws/!kline_1m@arr"

def on_message(ws, message):
    data = json.loads(message)

    for asset in data:
        symbol = asset["s"]

        if symbol not in SYMBOLS:
            continue

        k = asset["k"]

        # candle FECHADO
        if k["x"]:

            open_price = float(k["o"])
            close_price = float(k["c"])

            diff = close_price - open_price

            if abs(diff) < 0.00001:
                continue

            direction = "COMPRA" if diff > 0 else "VENDA"

            # evita spam
            last = active_signals.get(symbol, {}).get("time")

            if last and (now() - last).seconds < 60:
                continue

            chat_id = 123456789  # 👈 TROQUE PELO SEU ID OU SISTEMA MULTIUSUÁRIO

            send_signal(chat_id, symbol, direction)

def on_error(ws, error):
    print("WS ERROR:", error)

def on_close(ws, *args):
    print("WS reconnect...")
    time.sleep(3)
    start_ws()

def on_open(ws):
    print("WEBSOCKET CONECTADO BINANCE")

def start_ws():
    ws = websocket.WebSocketApp(
        STREAM,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open
    )
    ws.run_forever()

# =========================
# SINAL TELEGRAM
# =========================

def send_signal(chat_id, symbol, direction):

    entry = now() + timedelta(seconds=5)
    gale = entry + timedelta(minutes=1)

    active_signals[symbol] = {
        "chat_id": chat_id,
        "direction": direction,
        "entry": entry,
        "gale": gale,
        "time": now()
    }

    bot.send_message(
        chat_id,
        f"""🚀 SINAL GERADO
━━━━━━━━━━━━━━
💱 Par: {symbol}
⏱ Entrada: {entry.strftime('%H:%M:%S')}
🎯 Direção: {direction}
🔁 Gale 1: {gale.strftime('%H:%M:%S')}
⏳ Expiração: 1m"""
    )

    threading.Thread(
        target=run_result,
        args=(chat_id, symbol),
        daemon=True
    ).start()

# =========================
# RESULTADO
# =========================

def run_result(chat_id, symbol):

    sig = active_signals.get(symbol)
    if not sig:
        return

    exp = 60  # 1 min fixo

    time.sleep(exp)

    # 🔥 aqui entra lógica real futura (Binance candle validation)
    result = "LOSS"

    if result == "WIN":

        time.sleep(3)

        bot.send_message(
            chat_id,
            f"""🏁 RESULTADO FINAL
━━━━━━━━━━━━━━
💱 Par: {symbol}
📊 Resultado: WIN
🎯 Direção: {sig['direction']}
⏱ Entrada: {sig['entry'].strftime('%H:%M:%S')}""",
            reply_markup=btn_final()
        )
        return

    # =========================
    # LOSS → GALE
    # =========================

    bot.send_message(chat_id, "⚠️ Entrando em Gale 1...")

    time.sleep(exp)

    gale_result = "WIN"

    time.sleep(3)

    bot.send_message(
        chat_id,
        f"""🏁 RESULTADO FINAL
━━━━━━━━━━━━━━
💱 Par: {symbol}
📊 Resultado: {gale_result}
🎯 Direção: {sig['direction']}
⏱ Entrada: {sig['entry'].strftime('%H:%M:%S')}
🔁 Gale: {sig['gale'].strftime('%H:%M:%S')}""",
        reply_markup=btn_final()
    )

# =========================
# TELEGRAM START
# =========================

@bot.message_handler(commands=["start"])
def start(m):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Ativar Sinais", callback_data="start"))
    bot.send_message(m.chat.id, "📊 Bot Binance WS ativo", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "start")
def st(c):
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id, "🔥 Sistema ativo. Monitorando mercado...")

# =========================
# START SYSTEM
# =========================

threading.Thread(target=start_ws, daemon=True).start()

print("BOT + BINANCE WS ONLINE")

while True:
    try:
        bot.infinity_polling()
    except Exception as e:
        print("ERR:", e)
        time.sleep(5)
