import telebot
import requests
import threading
import time
import os
from datetime import datetime

# =========================
# TOKEN (RAILWAY ENV)
# =========================

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise Exception("TOKEN não encontrado nas variáveis de ambiente")

bot = telebot.TeleBot(TOKEN)

# =========================
# CRIPTOS
# =========================

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "LTCUSDT", "DOTUSDT", "AVAXUSDT"
]

# =========================
# MENU PARIDADES
# =========================

def menu_paridades():
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)

    for s in SYMBOLS:
        kb.add(
            telebot.types.InlineKeyboardButton(
                s.replace("USDT", "/USDT"),
                callback_data=f"par_{s}"
            )
        )

    return kb

# =========================
# BOTÃO NOVO SINAL
# =========================

def btn():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(
        telebot.types.InlineKeyboardButton("🚀 Gerar novo sinal", callback_data="novo")
    )
    return kb

# =========================
# BINANCE CANDLE
# =========================

def get_candle(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=2"
    data = requests.get(url).json()

    candle = data[-2]

    open_price = float(candle[1])
    close_price = float(candle[4])

    return open_price, close_price

# =========================
# ANALISE
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
# FLUXO PRINCIPAL
# =========================

def run_signal(chat_id, symbol):

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
    # EXPIRAÇÃO 1 MIN
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
# START
# =========================

@bot.message_handler(commands=["start"])
def start(m):
    bot.send_message(
        m.chat.id,
        "📊 Escolha a paridade:",
        reply_markup=menu_paridades()
    )

# =========================
# ESCOLHER PARIDADE
# =========================

@bot.callback_query_handler(func=lambda c: c.data.startswith("par_"))
def escolher_paridade(c):
    bot.answer_callback_query(c.id)

    symbol = c.data.split("_")[1]

    threading.Thread(
        target=run_signal,
        args=(c.message.chat.id, symbol),
        daemon=True
    ).start()

# =========================
# NOVO SINAL
# =========================

@bot.callback_query_handler(func=lambda c: c.data == "novo")
def novo(c):
    bot.answer_callback_query(c.id)

    bot.send_message(
        c.message.chat.id,
        "📊 Escolha a paridade:",
        reply_markup=menu_paridades()
    )

# =========================
# LOOP
# =========================

print("BOT ONLINE")

bot.infinity_polling()
