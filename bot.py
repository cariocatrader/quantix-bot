import telebot
import requests
import threading
import time
import os
from datetime import datetime, timedelta
import pytz
import math

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise Exception("TOKEN não encontrado")

bot = telebot.TeleBot(TOKEN)

BR_TZ = pytz.timezone('America/Sao_Paulo')

def get_br_time(format_str="%H:%M"):
    return datetime.now(BR_TZ).strftime(format_str)

def next_round_5(now_str):
    now = datetime.strptime(now_str, "%H:%M")
    now = BR_TZ.localize(now)

    minutes = now.minute
    next_5 = math.ceil((minutes + 1) / 5.0) * 5

    if next_5 >= 60:
        next_5 = 0
        now += timedelta(hours=1)

    entry = now.replace(minute=next_5, second=0, microsecond=0)
    gale1 = entry + timedelta(minutes=5)

    return entry.strftime("%H:%M"), gale1.strftime("%H:%M")

SYMBOLS = {
    "bitcoin": "₿ Bitcoin", "ethereum": "Ξ Ethereum", "binancecoin": "🟡 BNB",
    "solana": "🟣 Solana", "ripple": "💧 XRP", "cardano": "🔵 Cardano",
    "dogecoin": "🐶 Doge", "litecoin": "🪙 Litecoin", "polkadot": "⚫ Polkadot",
    "avalanche-2": "🔺 Avalanche"
}

BINANCE_SYMBOLS = {
    "bitcoin": "BTCUSDT", "ethereum": "ETHUSDT", "binancecoin": "BNBUSDT",
    "solana": "SOLUSDT", "ripple": "XRPUSDT", "cardano": "ADAUSDT",
    "dogecoin": "DOGEUSDT", "litecoin": "LTCUSDT", "polkadot": "DOTUSDT",
    "avalanche-2": "AVAXUSDT"
}

ANALISE_GIF = "analise.gif"
WIN_GIF = "win.gif"
LOSS_GIF = "loss.gif"

# =========================
# BINANCE CANDLE
# =========================
def get_candle_at_time(symbol, target_time_str):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=20"
        r = requests.get(url, timeout=5)
        data = r.json()

        if not data:
            return None

        target_dt = datetime.strptime(target_time_str, "%H:%M")

        target_dt = target_dt.replace(year=2026, month=4, day=28)
        target_timestamp = int(target_dt.timestamp() * 1000)

        for candle in data:
            candle_open_ts = int(candle[0])
            candle_close_ts = int(candle[6])

            if candle_open_ts <= target_timestamp <= candle_close_ts:
                return {
                    'open': float(candle[1]),
                    'close': float(candle[4]),
                    'complete': candle_close_ts <= int(time.time() * 1000)
                }

        return None
    except:
        return None


def analyze(coin_id):
    symbol = BINANCE_SYMBOLS[coin_id]
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=5"
        r = requests.get(url, timeout=5)
        data = r.json()

        candle = data[-3]
        o, c = float(candle[1]), float(candle[4])

        pct = abs((c - o) / o * 100)

        if pct >= 0.0005:
            return "COMPRA" if c > o else "VENDA"

    except:
        pass

    return None


def get_real_result(symbol, entry_open, direction, target_time):
    candle = get_candle_at_time(symbol, target_time)

    if not candle:
        return "LOSS"

    entry_close = candle['close']

    if direction == "COMPRA":
        return "WIN" if entry_close > entry_open else "LOSS"
    else:
        return "WIN" if entry_close < entry_open else "LOSS"


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


def run_signal(chat_id, coin_id, exp):
    def process():
        bot.send_animation(chat_id, open(ANALISE_GIF, "rb"), caption="🔍 Análise...")

        direction = None
        for _ in range(5):
            direction = analyze(coin_id)
            if direction:
                break
            time.sleep(2)

        if not direction:
            bot.send_message(chat_id, "❌ Sem sinal forte", reply_markup=restart_btn())
            return

        symbol = BINANCE_SYMBOLS[coin_id]
        now = get_br_time()
        entry_time, gale1_time = next_round_5(now)

        entry_candle = get_candle_at_time(symbol, entry_time)
        if not entry_candle:
            bot.send_message(chat_id, "❌ Erro candle entrada", reply_markup=restart_btn())
            return

        entry_open = entry_candle['open']

        bot.send_message(
            chat_id,
            f"""🚀 SINAL GERADO
━━━━━━━━━━━━━━
💱 {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time}
📅 Gale 1: {gale1_time}
🎯 Direção: {direction}
💰 Open: {entry_open:.4f}""",
            reply_markup=restart_btn()
        )

        time.sleep(int(exp) * 60)

        r1 = get_real_result(symbol, entry_open, direction, entry_time)

        if r1 == "WIN":
            time.sleep(3)
            bot.send_animation(chat_id, open(WIN_GIF, "rb"),
                               caption=f"🏁 WIN {SYMBOLS[coin_id]}\n⏱ {entry_time}",
                               reply_markup=restart_btn())
            return

        bot.send_message(chat_id, "⚠️ Entrando em Gale 1...")

        time.sleep(int(exp) * 60)

        r2 = get_real_result(symbol, entry_open, direction, gale1_time)

        gif = WIN_GIF if r2 == "WIN" else LOSS_GIF

        bot.send_animation(chat_id, open(gif, "rb"),
                           caption=f"""🏁 RESULTADO FINAL
━━━━━━━━━━━━━━
💱 {SYMBOLS[coin_id]}
📊 {r2}
⏱ Entrada: {entry_time}
📅 Gale 1: {gale1_time}
🎯 {direction}""",
                           reply_markup=restart_btn())

    threading.Thread(target=process, daemon=True).start()


@bot.message_handler(commands=["start"])
def start(m):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Gerar sinal", callback_data="start"))
    bot.send_message(m.chat.id, "👋 Quantix REAL", reply_markup=kb)


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


print(f"🚀 BOT ONLINE")
bot.infinity_polling()
