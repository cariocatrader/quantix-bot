import telebot
import requests
import threading
import time
import os
from datetime import datetime

# =========================
# TOKEN
# =========================

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise Exception("TOKEN não encontrado")

bot = telebot.TeleBot(TOKEN)

# =========================
# CRIPTOS
# =========================

SYMBOLS = {
    "BTCUSDT": "₿ Bitcoin",
    "ETHUSDT": "Ξ Ethereum",
    "BNBUSDT": "🟡 BNB",
    "SOLUSDT": "🟣 Solana",
    "XRPUSDT": "💧 XRP",
    "ADAUSDT": "🔵 Cardano",
    "DOGEUSDT": "🐶 Doge",
    "LTCUSDT": "🪙 Litecoin",
    "DOTUSDT": "⚫ Polkadot",
    "AVAXUSDT": "🔺 Avalanche"
}

# =========================
# GIFS
# =========================

ANALISE_GIF = "analise.gif"
WIN_GIF = "win.gif"
LOSS_GIF = "loss.gif"

# =========================
# API MEXC / BINANCE FALLBACK
# =========================

def get_candle(symbol, limit=5):
    try:
        url = f"https://api.mexc.com/api/v3/klines?symbol={symbol}&interval=1m&limit={limit}"
        r = requests.get(url, timeout=10)
        data = r.json()

        if not data or len(data) < 3:
            raise Exception("MEXC vazio")

        return data

    except:
        try:
            url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit={limit}"
            r = requests.get(url, timeout=5)
            return r.json()
        except:
            return None

# =========================
# ANALISE
# =========================

def analyze(symbol):
    data = get_candle(symbol, limit=10)

    if not data or len(data) < 4:
        return None

    for i in range(-4, -1):
        try:
            o = float(data[i][1])
            c = float(data[i][4])

            pct = abs((c - o) / o * 100)

            if pct >= 0.01:
                return "COMPRA" if c > o else "VENDA"

        except:
            continue

    return None

# =========================
# RESULTADO
# =========================

def result(symbol, direction):
    data = get_candle(symbol, limit=3)

    if not data:
        return "LOSS"

    try:
        o = float(data[-2][1])
        c = float(data[-2][4])

        if direction == "COMPRA":
            return "WIN" if c >= o else "LOSS"

        return "WIN" if c <= o else "LOSS"

    except:
        return "LOSS"

# =========================
# BOTÕES
# =========================

def restart_btn():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Gerar novo sinal", callback_data="restart"))
    return kb


def menu_paridades():
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)

    for sym, name in SYMBOLS.items():
        kb.add(telebot.types.InlineKeyboardButton(name, callback_data=f"par_{sym}"))

    return kb


def menu_exp(symbol):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(
        telebot.types.InlineKeyboardButton("⚡ 1 Minuto", callback_data=f"exp_{symbol}_1"),
        telebot.types.InlineKeyboardButton("🕐 5 Minutos", callback_data=f"exp_{symbol}_5")
    )
    return kb

# =========================
# FLUXO
# =========================

def run_signal(chat_id, symbol, exp):

    def process():

        try:
            with open(ANALISE_GIF, "rb") as gif:
                bot.send_animation(chat_id, gif, caption="⏳ Analisando mercado...")
        except:
            bot.send_message(chat_id, "⏳ Analisando...")

        time.sleep(2)

        direction = analyze(symbol)

        if not direction:
            bot.send_message(chat_id, "❌ Sem sinal no momento")
            return

        entry_time = datetime.now().strftime("%H:%M:%S")

        bot.send_message(
            chat_id,
            f"""🚀 SINAL GERADO
━━━━━━━━━━━━━━
💱 {SYMBOLS[symbol]}
⏱ Entrada: {entry_time}
🎯 Direção: {direction}
⏳ Expiração: {exp} min""",
            reply_markup=restart_btn()
        )

        time.sleep(int(exp) * 60)

        r1 = result(symbol, direction)

        if r1 == "WIN":
            time.sleep(2)

            try:
                with open(WIN_GIF, "rb") as gif:
                    bot.send_animation(chat_id, gif,
                        caption=f"""🏁 WIN
━━━━━━━━━━━━━━
💱 {SYMBOLS[symbol]}
⏱ {entry_time}
🎯 {direction}""",
                        reply_markup=restart_btn()
                    )
            except:
                bot.send_message(chat_id, "🏁 WIN")

            return

        bot.send_message(chat_id, "⚠️ Entrando em Gale 1...")

        time.sleep(int(exp) * 60)

        r2 = result(symbol, direction)

        gif_path = WIN_GIF if r2 == "WIN" else LOSS_GIF

        time.sleep(2)

        try:
            with open(gif_path, "rb") as gif:
                bot.send_animation(chat_id, gif,
                    caption=f"""🏁 FINAL {r2}
━━━━━━━━━━━━━━
💱 {SYMBOLS[symbol]}
⏱ {entry_time}
🎯 {direction}
🔁 Gale 1""",
                    reply_markup=restart_btn()
                )
        except:
            bot.send_message(chat_id, f"🏁 {r2}")

    threading.Thread(target=process, daemon=True).start()

# =========================
# HANDLERS
# =========================

@bot.message_handler(commands=["start"])
def start(m):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Gerar sinal", callback_data="start"))

    bot.send_message(
        m.chat.id,
        "👋 Quantix Cripto pronto",
        reply_markup=kb
    )


@bot.callback_query_handler(func=lambda c: c.data == "start")
def start_flow(c):
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id, "📊 Escolha a paridade:", reply_markup=menu_paridades())


@bot.callback_query_handler(func=lambda c: c.data.startswith("par_"))
def paridade(c):
    bot.answer_callback_query(c.id)
    symbol = c.data.split("_")[1]
    bot.send_message(c.message.chat.id, "⏳ Expiração:", reply_markup=menu_exp(symbol))


@bot.callback_query_handler(func=lambda c: c.data.startswith("exp_"))
def exp(c):
    bot.answer_callback_query(c.id)
    _, symbol, exp_time = c.data.split("_")
    run_signal(c.message.chat.id, symbol, exp_time)


@bot.callback_query_handler(func=lambda c: c.data == "restart")
def restart(c):
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id, "📊 Escolha a paridade:", reply_markup=menu_paridades())

print("🚀 BOT ONLINE OK")
bot.infinity_polling()
