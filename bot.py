import telebot
import requests
import threading
import time
import os
from datetime import datetime, timedelta
import pytz
import math
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise Exception("TOKEN não encontrado")

bot = telebot.TeleBot(TOKEN)

BR_TZ = pytz.timezone('America/Sao_Paulo')
UTC_TZ = pytz.timezone('UTC')

def get_br_time(format_str="%H:%M"):
    return datetime.now(BR_TZ).strftime(format_str)

# ===============================
# TIMESTAMP CORRIGIDO
# ===============================

def br_to_utc_timestamp(br_time_str):

    now_br = datetime.now(BR_TZ)

    br_dt = datetime.strptime(
        br_time_str,
        "%H:%M"
    ).replace(
        year=now_br.year,
        month=now_br.month,
        day=now_br.day,
        second=0,
        microsecond=0
    )

    br_dt = BR_TZ.localize(br_dt)

    utc_dt = br_dt.astimezone(UTC_TZ)

    return int(utc_dt.timestamp() * 1000)

# ===============================
# PARIDADES
# ===============================

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

BINANCE_SYMBOLS = {
    "bitcoin": "BTCUSDT",
    "ethereum": "ETHUSDT",
    "binancecoin": "BNBUSDT",
    "solana": "SOLUSDT",
    "ripple": "XRPUSDT",
    "cardano": "ADAUSDT",
    "dogecoin": "DOGEUSDT",
    "litecoin": "LTCUSDT",
    "polkadot": "DOTUSDT",
    "avalanche-2": "AVAXUSDT"
}

# ===============================
# ANALISE DIREÇÃO
# ===============================

def analyze(coin_id):

    try:

        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc?vs_currency=usd&days=2"

        r = requests.get(url, timeout=8)

        data = r.json()

        closes = [c[4] for c in data[-3:]]

        return "COMPRA" if closes[-1] > closes[-2] else "VENDA"

    except:

        return "COMPRA"

# ===============================
# LEITURA VELA (CORRIGIDO)
# ===============================

def get_binance_candle(symbol, br_time_str, interval="1m"):

    try:

        target_ts = br_to_utc_timestamp(br_time_str)

        url = (
            f"https://api.binance.com/api/v3/klines"
            f"?symbol={symbol}"
            f"&interval={interval}"
            f"&limit=10"
        )

        r = requests.get(url, timeout=10)

        data = r.json()

        if not isinstance(data, list):

            return None

        for candle in data:

            open_ts = int(candle[0])

            # 🎯 MATCH EXATO (CORREÇÃO)

            if open_ts == target_ts:

                o = float(candle[1])
                c = float(candle[4])

                logger.info(
                    f"📊 {br_time_str} "
                    f"O:{o} C:{c}"
                )

                return o, c

        logger.warning("⚠️ Candle não encontrada")

        return None

    except Exception as e:

        logger.error(e)

        return None

# ===============================
# RESULTADO REAL
# ===============================

def get_result(symbol, direction, br_time_str, interval="1m"):

    result = get_binance_candle(
        symbol,
        br_time_str,
        interval
    )

    if not result:

        return "LOSS"

    o, c = result

    if direction == "COMPRA":

        return "WIN" if c > o else "LOSS"

    else:

        return "WIN" if c < o else "LOSS"

# ===============================
# UI
# ===============================

def menu_paridades():

    kb = telebot.types.InlineKeyboardMarkup(row_width=2)

    for coin_id, name in SYMBOLS.items():

        kb.add(
            telebot.types.InlineKeyboardButton(
                name,
                callback_data=f"par_{coin_id}"
            )
        )

    return kb

def menu_exp(coin_id):

    kb = telebot.types.InlineKeyboardMarkup()

    kb.add(

        telebot.types.InlineKeyboardButton(
            "⚡ 1 Minuto",
            callback_data=f"exp_{coin_id}_1"
        ),

        telebot.types.InlineKeyboardButton(
            "🕐 5 Minutos",
            callback_data=f"exp_{coin_id}_5"
        )

    )

    return kb

def final_btn():

    kb = telebot.types.InlineKeyboardMarkup()

    kb.add(
        telebot.types.InlineKeyboardButton(
            "🚀 Gerar Novo Sinal",
            callback_data="new_signal"
        )
    )

    return kb

# ===============================
# RESULTADO FINAL
# ===============================

def send_result_final(
    chat_id,
    symbol_name,
    direction,
    result,
    entry_time
):

    status = "✅ WIN" if result == "WIN" else "❌ LOSS"

    text = f"""
🎯 RESULTADO FINAL

━━━━━━━━━━━━━━━━━━
💱 {symbol_name}
⏱ {entry_time}
🎯 {direction}
🏆 {status}

Quantix Cripto ✨
"""

    bot.send_message(
        chat_id,
        text,
        reply_markup=final_btn()
    )

# ===============================
# PROCESSO TRADE
# ===============================

def process_trade(
    chat_id,
    coin_id,
    direction,
    entry_time,
    exp
):

    def check():

        interval = "1m" if exp == "1" else "5m"

        wait = 65 if exp == "1" else 305

        logger.info(f"⏳ Esperando {wait}s")

        time.sleep(wait)

        symbol = BINANCE_SYMBOLS[coin_id]

        result = get_result(
            symbol,
            direction,
            entry_time,
            interval
        )

        send_result_final(
            chat_id,
            SYMBOLS[coin_id],
            direction,
            result,
            entry_time
        )

    threading.Thread(
        target=check,
        daemon=True
    ).start()

# ===============================
# GERAR SINAL
# ===============================

def run_signal(
    chat_id,
    coin_id,
    exp
):

    direction = analyze(coin_id)

    now = datetime.now(BR_TZ)

    if exp == "1":

        entry = now + timedelta(minutes=1)

    else:

        m = math.ceil(now.minute / 5) * 5

        entry = now.replace(minute=m)

    entry_time = entry.strftime("%H:%M")

    text = f"""
🎉 SINAL GERADO

━━━━━━━━━━━━━━━━━━
💱 {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time}
🎯 {direction}

Aguardando...
"""

    bot.send_message(chat_id, text)

    process_trade(
        chat_id,
        coin_id,
        direction,
        entry_time,
        exp
    )

# ===============================
# HANDLERS
# ===============================

@bot.message_handler(commands=["start"])
def start(m):

    kb = telebot.types.InlineKeyboardMarkup()

    kb.add(
        telebot.types.InlineKeyboardButton(
            "🚀 Gerar Sinal",
            callback_data="start"
        )
    )

    bot.send_message(
        m.chat.id,
        "🤖 Quantix Cripto",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda c: c.data == "start")
def start_flow(c):

    bot.answer_callback_query(c.id)

    bot.send_message(
        c.message.chat.id,
        "Escolha paridade:",
        reply_markup=menu_paridades()
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("par_"))
def paridade(c):

    coin_id = c.data.split("_")[1]

    bot.send_message(
        c.message.chat.id,
        "Escolha expiração:",
        reply_markup=menu_exp(coin_id)
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("exp_"))
def exp_handler(c):

    parts = c.data.split("_")

    run_signal(
        c.message.chat.id,
        parts[1],
        parts[2]
    )

# ===============================
# START
# ===============================

print(
    f"🚀 QUANTIX ATIVO {get_br_time()}"
)

bot.remove_webhook()

time.sleep(2)

bot.infinity_polling()
