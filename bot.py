import telebot
import requests
import threading
import time
import os
from datetime import datetime, timedelta
import pytz
import math

# =========================
# TOKEN
# =========================

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise Exception("TOKEN não encontrado")

bot = telebot.TeleBot(TOKEN)

# =========================
# TIMEZONE BR
# =========================

BR_TZ = pytz.timezone('America/Sao_Paulo')

def get_br_time(format_str="%H:%M"):
    return datetime.now(BR_TZ).strftime(format_str)

def next_round_5(now_str):
    """Próximo múltiplo de 5 minutos"""
    now = datetime.strptime(now_str, "%H:%M")
    now = BR_TZ.localize(now)

    minutes = now.minute
    next_5 = math.ceil((minutes + 1) / 5.0) * 5

    if next_5 >= 60:
        next_5 = 0
        now = now + timedelta(hours=1)

    entry = now.replace(minute=next_5, second=0, microsecond=0)
    gale1 = entry + timedelta(minutes=5)

    return entry.strftime("%H:%M"), gale1.strftime("%H:%M")

# =========================
# CRIPTOS
# =========================

SYMBOLS = {
    "bitcoin": "₿ Bitcoin",
    "ethereum": "Ξ Ethereum",
    "binancecoin": "🟡 BNB",
    "solana": "🟣 Solana",
    "ripple": "💧 XRP",
    "cardano": "🔵 Cardano",
    "dogecoin": "🐶 Doge",
    "litecoin": "🪙 Litecoin",
    "polkadot": "⚫ Polkadot",
    "avalanche-2": "🔺 Avalanche"
}

# =========================
# GIFS
# =========================

ANALISE_GIF = "analise.gif"
WIN_GIF = "win.gif"
LOSS_GIF = "loss.gif"

# =========================
# COINGECKO
# =========================

def get_ohlc(coin_id):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc?vs_currency=usd&days=2"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()

        if not data or len(data) < 2:
            return None

        prev = data[-2]
        return float(prev[1]), float(prev[2]), float(prev[3]), float(prev[4])

    except:
        return None

# =========================
# ANALYSE
# =========================

def analyze(coin_id):
    candle = get_ohlc(coin_id)
    if not candle:
        return None

    o, h, l, c = candle

    pct_change = abs((c - o) / o * 100)
    if pct_change < 0.005:
        return None

    body_size = abs(c - o)
    range_size = h - l

    if range_size == 0 or body_size / range_size < 0.2:
        return None

    return "COMPRA" if c > o else "VENDA"

# =========================
# RESULTADO
# =========================

def result(coin_id, direction):
    candle = get_ohlc(coin_id)
    if not candle:
        return "LOSS"

    o, _, _, c = candle

    if direction == "COMPRA":
        return "WIN" if c > o else "LOSS"

    return "WIN" if c < o else "LOSS"

# =========================
# BOTÕES
# =========================

def restart_btn():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Gerar novo sinal", callback_data="restart"))
    return kb


def menu_paridades():
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    for coin_id, name in SYMBOLS.items():
        kb.add(telebot.types.InlineKeyboardButton(name, callback_data=f"par_{coin_id}"))
    return kb


def menu_exp(coin_id):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(
        telebot.types.InlineKeyboardButton("⚡ 1 Minuto", callback_data=f"exp_{coin_id}_1"),
        telebot.types.InlineKeyboardButton("🕐 5 Minutos", callback_data=f"exp_{coin_id}_5")
    )
    return kb

# =========================
# FLUXO PRINCIPAL
# =========================

def run_signal(chat_id, coin_id, exp):

    def process():

        try:
            bot.send_animation(chat_id, open(ANALISE_GIF, "rb"), caption="⏳ Calculando horários...")
        except:
            bot.send_message(chat_id, "⏳ Analisando...")

        direction = analyze(coin_id)

        if not direction:
            bot.send_message(chat_id, "❌ Sem sinal forte agora!", reply_markup=restart_btn())
            return

        now = get_br_time()
        entry_time, gale1_time = next_round_5(now)

        bot.send_message(
            chat_id,
            f"""🚀 SINAL GERADO
━━━━━━━━━━━━━━
💱 {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time}
📅 Gale 1: {gale1_time}
🎯 Direção: {direction}
⏳ Expiração: 5 min""",
            reply_markup=restart_btn()
        )

        now_dt = datetime.strptime(now, "%H:%M")
        entry_dt = datetime.strptime(entry_time, "%H:%M")

        wait_entry = max(0, int((entry_dt - now_dt).total_seconds()))
        time.sleep(wait_entry + int(exp) * 60)

        r1 = result(coin_id, direction)

        if r1 == "WIN":
            time.sleep(3)
            bot.send_animation(
                chat_id,
                open(WIN_GIF, "rb"),
                caption=f"""🏁 WIN DIRETO!
━━━━━━━━━━━━━━
💱 {SYMBOLS[coin_id]}
📊 {r1}
⏱ {entry_time}
🎯 {direction}""",
                reply_markup=restart_btn()
            )
            return

        bot.send_message(chat_id, "⚠️ Entrando em Gale 1...")

        gale1_dt = datetime.strptime(gale1_time, "%H:%M")
        wait_gale = max(0, int((gale1_dt - datetime.now(BR_TZ).replace(tzinfo=None)).total_seconds()))

        time.sleep(wait_gale + int(exp) * 60)

        r2 = result(coin_id, direction)
        time.sleep(3)

        gif = WIN_GIF if r2 == "WIN" else LOSS_GIF

        bot.send_animation(
            chat_id,
            open(gif, "rb"),
            caption=f"""🏁 RESULTADO FINAL
━━━━━━━━━━━━━━
💱 {SYMBOLS[coin_id]}
📊 {r2}
⏱ Entrada: {entry_time} | Gale: {gale1_time}
🎯 {direction} 🔁 Gale 1""",
            reply_markup=restart_btn()
        )

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
        f"""👋 Quantix Cripto
🇧🇷 {get_br_time()}""",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda c: c.data == "start")
def start_flow(c):
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id, "📊 Paridade:", reply_markup=menu_paridades())

@bot.callback_query_handler(func=lambda c: c.data.startswith("par_"))
def paridade(c):
    bot.answer_callback_query(c.id)
    coin_id = c.data.split("_", 1)[1]
    bot.send_message(c.message.chat.id, "⏳ Expiração:", reply_markup=menu_exp(coin_id))

@bot.callback_query_handler(func=lambda c: c.data.startswith("exp_"))
def exp_handler(c):
    bot.answer_callback_query(c.id)
    parts = c.data.split("_")
    coin_id, exp = parts[1], parts[2]
    run_signal(c.message.chat.id, coin_id, exp)

@bot.callback_query_handler(func=lambda c: c.data == "restart")
def restart(c):
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id, "📊 Paridade:", reply_markup=menu_paridades())

print(f"🚀 BOT ONLINE - QUANTIX PREVISTO {get_br_time()}")
bot.infinity_polling()
