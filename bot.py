import telebot
import requests
import time
import threading
from datetime import datetime

TOKEN = "8516808804:AAF9zu8zHqIAI2yAaFl77poNpLpsDVoZ9Kc"
bot = telebot.TeleBot(TOKEN)

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "LTCUSDT", "DOTUSDT", "AVAXUSDT"
]

# =========================
# PEGAR CANDLE REAL
# =========================

def get_candle(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=2"
    data = requests.get(url).json()

    candle = data[-2]

    open_price = float(candle[1])
    close_price = float(candle[4])

    return open_price, close_price

# =========================
# ANALISE DO SINAL
# =========================

def analyze(symbol):
    o, c = get_candle(symbol)

    if c > o:
        return "COMPRA"
    elif c < o:
        return "VENDA"

    return None

# =========================
# RESULTADO REAL
# =========================

def result(symbol, direction):
    o, c = get_candle(symbol)

    if direction == "COMPRA":
        return "WIN" if c > o else "LOSS"

    if direction == "VENDA":
        return "WIN" if c < o else "LOSS"

    return "LOSS"

# =========================
# BOTÃO NOVO SINAL
# =========================

def btn():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("🚀 Gerar novo sinal", callback_data="novo"))
    return markup

# =========================
# FLUXO DO SINAL
# =========================

def run_signal(chat_id):

    symbol = SYMBOLS[0]  # pode random depois

    direction = analyze(symbol)

    if not direction:
        bot.send_message(chat_id, "❌ Sem sinal no momento")
        return

    entry_time = datetime.now().strftime("%H:%M:%S")

    bot.send_message(
        chat_id,
        f"""🚀 SINAL GERADO
━━━━━━━━━━━━━━
💱 {symbol}
⏱ Entrada: {entry_time}
🎯 Direção: {direction}
⏳ Expiração: 1 minuto"""
    )

    # =========================
    # ESPERA 1 MIN
    # =========================

    time.sleep(60)

    r1 = result(symbol, direction)

    # =========================
    # WIN DIRETO
    # =========================

    if r1 == "WIN":

        time.sleep(3)

        bot.send_message(
            chat_id,
            f"""🏁 RESULTADO FINAL
━━━━━━━━━━━━━━
💱 {symbol}
📊 WIN
🎯 Direção: {direction}
⏱ Entrada: {entry_time}""",
            reply_markup=btn()
        )
        return

    # =========================
    # GALE 1
    # =========================

    bot.send_message(chat_id, "⚠️ Entrando em Gale 1...")

    time.sleep(60)

    r2 = result(symbol, direction)

    time.sleep(3)

    bot.send_message(
        chat_id,
        f"""🏁 RESULTADO FINAL
━━━━━━━━━━━━━━
💱 {symbol}
📊 {r2}
🎯 Direção: {direction}
⏱ Entrada: {entry_time}
🔁 Gale 1 aplicado""",
        reply_markup=btn()
    )

# =========================
# TELEGRAM
# =========================

@bot.message_handler(commands=["start"])
def start(m):
    bot.send_message(
        m.chat.id,
        "📊 Quantix Cripto Trader",
        reply_markup=telebot.types.InlineKeyboardMarkup().add(
            telebot.types.InlineKeyboardButton("🚀 Gerar sinal", callback_data="gerar")
        )
    )

@bot.callback_query_handler(func=lambda c: c.data == "gerar")
def gerar(c):
    bot.answer_callback_query(c.id)
    run_signal(c.message.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "novo")
def novo(c):
    bot.answer_callback_query(c.id)
    run_signal(c.message.chat.id)

bot.infinity_polling()
