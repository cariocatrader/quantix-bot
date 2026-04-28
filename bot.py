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


def analyze(coin_id):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc?vs_currency=usd&days=2"
        r = requests.get(url, timeout=8)
        data = r.json()

        closes = [candle[4] for candle in data[-3:]]

        if closes[-1] > closes[-2]:
            return "COMPRA"
        elif closes[-1] < closes[-2]:
            return "VENDA"
        else:
            return "COMPRA" if closes[-2] > closes[-3] else "VENDA"
    except:
        return "COMPRA"


def get_binance_result(symbol, direction, target_time):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=30"
        r = requests.get(url, timeout=5)
        data = r.json()

        target = int(datetime.strptime(target_time, "%H:%M").replace(
            year=2026, month=4, day=28
        ).timestamp() * 1000)

        for candle in data:
            open_ts, close_ts = int(candle[0]), int(candle[6])

            if open_ts <= target <= close_ts:
                o, c = float(candle[1]), float(candle[4])

                if direction == "COMPRA":
                    return "WIN" if c > o else "LOSS"
                return "WIN" if c < o else "LOSS"

        return "LOSS"
    except:
        return "LOSS"


def restart_btn():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Novo sinal", callback_data="restart"))
    return kb


def menu_paridades():
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    for coin_id, name in SYMBOLS.items():
        kb.add(telebot.types.InlineKeyboardButton(name, callback_data=f"par_{coin_id}"))
    return kb


def menu_exp(coin_id):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.row(
        telebot.types.InlineKeyboardButton("1 Min", callback_data=f"exp_{coin_id}_1"),
        telebot.types.InlineKeyboardButton("5 Min", callback_data=f"exp_{coin_id}_5")
    )
    return kb


def run_signal(chat_id, coin_id, exp):
    def process():
        direction = analyze(coin_id)
        symbol = BINANCE_SYMBOLS[coin_id]

        now = get_br_time()
        entry_time, gale1_time = next_round_5(now)

        with open(ANALISE_GIF, "rb") as f:
            bot.send_animation(chat_id, f, caption="🎯 Análise...")

        bot.send_message(
            chat_id,
            f"""🚀 SINAL
━━━━━━━━━━━━━━
💱 {SYMBOLS[coin_id]}
⏱ {entry_time}
📅 {gale1_time}
🎯 {direction}""",
            reply_markup=restart_btn()
        )

        time.sleep(int(exp) * 60)

        r1 = get_binance_result(symbol, direction, entry_time)

        if r1 == "WIN":
            time.sleep(3)
            with open(WIN_GIF, "rb") as f:
                bot.send_animation(
                    chat_id,
                    f,
                    caption=f"WIN {SYMBOLS[coin_id]} | {entry_time}",
                    reply_markup=restart_btn()
                )
            return

        bot.send_message(chat_id, "⚠️ Gale 1...")

        time.sleep(int(exp) * 60)

        r2 = get_binance_result(symbol, direction, gale1_time)

        gif = WIN_GIF if r2 == "WIN" else LOSS_GIF

        with open(gif, "rb") as f:
            bot.send_animation(
                chat_id,
                f,
                caption=f"FINAL {r2}\n{SYMBOLS[coin_id]}",
                reply_markup=restart_btn()
            )

    threading.Thread(target=process, daemon=True).start()


@bot.message_handler(commands=["start"])
def start(m):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Sinal", callback_data="start"))
    bot.send_message(m.chat.id, "👋 Quantix Híbrido", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data == "start")
def start_flow(c):
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id, "📊 Paridade:", reply_markup=menu_paridades())


@bot.callback_query_handler(func=lambda c: c.data.startswith("par_"))
def paridade(c):
    bot.answer_callback_query(c.id)
    coin_id = c.data.split("_", 1)[1]
    bot.send_message(c.message.chat.id, "⏳ Tempo:", reply_markup=menu_exp(coin_id))


@bot.callback_query_handler(func=lambda c: c.data.startswith("exp_"))
def exp_handler(c):
    bot.answer_callback_query(c.id)
    parts = c.data.split("_")
    run_signal(c.message.chat.id, parts[1], parts[2])


@bot.callback_query_handler(func=lambda c: c.data == "restart")
def restart(c):
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id, "📊 Paridade:", reply_markup=menu_paridades())


print("🚀 BOT OK")
bot.infinity_polling()
