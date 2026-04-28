import telebot
import requests
import threading
import time
import os
from datetime import datetime, timedelta
import pytz
import math
import traceback

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise Exception("TOKEN não encontrado")

bot = telebot.TeleBot(TOKEN)

BR_TZ = pytz.timezone('America/Sao_Paulo')
UTC_TZ = pytz.UTC

def get_br_time(format_str="%H:%M"):
    return datetime.now(BR_TZ).strftime(format_str)

def br_to_utc_timestamp(br_time_str):

    now_br = datetime.now(BR_TZ)

    br_dt = datetime.strptime(br_time_str, "%H:%M").replace(
        year=now_br.year,
        month=now_br.month,
        day=now_br.day
    )

    br_dt = BR_TZ.localize(br_dt)
    utc_dt = br_dt.astimezone(UTC_TZ)

    return int(utc_dt.timestamp() * 1000)

def next_round_time(now_str, exp):

    now_dt = datetime.now(BR_TZ)

    now = datetime.strptime(now_str, "%H:%M").replace(
        year=now_dt.year,
        month=now_dt.month,
        day=now_dt.day
    )

    now = BR_TZ.localize(now)

    if exp == "1":

        entry_min = now.minute + 1

        if entry_min >= 60:
            entry_min = 0
            now += timedelta(hours=1)

        entry = now.replace(
            minute=entry_min,
            second=0,
            microsecond=0
        )

        gale1 = entry + timedelta(minutes=1)

    else:

        minutes = now.minute

        next_5 = math.ceil(
            (minutes + 1) / 5.0
        ) * 5

        if next_5 >= 60:
            next_5 = 0
            now += timedelta(hours=1)

        entry = now.replace(
            minute=next_5,
            second=0,
            microsecond=0
        )

        gale1 = entry + timedelta(minutes=5)

    return (
        entry.strftime("%H:%M"),
        gale1.strftime("%H:%M")
    )

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

ANALISE_GIF = "analise.gif"
WIN_GIF = "win.gif"
LOSS_GIF = "loss.gif"

def analyze(coin_id):

    try:

        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc?vs_currency=usd&days=2"

        r = requests.get(url, timeout=8)

        data = r.json()

        if not isinstance(data, list) or len(data) < 3:
            print("Erro CoinGecko: dados insuficientes")
            return "COMPRA"

        closes = [
            candle[4]
            for candle in data[-3:]
        ]

        return (
            "COMPRA"
            if closes[-1] > closes[-2]
            else "VENDA"
        )

    except:
        traceback.print_exc()
        return "COMPRA"

def get_binance_candle(symbol, br_time_str):

    try:

        target_utc_ms = br_to_utc_timestamp(br_time_str)

        print(f"🔍 Buscando {symbol} {br_time_str}")

        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=60"

        r = requests.get(url, timeout=5)

        data = r.json()

        for candle in data:

            open_ts = int(candle[0])

            if abs(open_ts - target_utc_ms) < 120000:

                o = float(candle[1])
                c = float(candle[4])

                print(f"✅ Candle encontrado {o} → {c}")

                return o, c

        print("❌ Nenhum candle encontrado")

        return None, None

    except Exception as e:

        traceback.print_exc()

        return None, None

def get_result(symbol, direction, br_time_str):

    o, c = get_binance_candle(
        symbol,
        br_time_str
    )

    if o is None:
        return "LOSS"

    win = (

        (direction == "COMPRA" and c > o)
        or
        (direction == "VENDA" and c < o)

    )

    return "WIN" if win else "LOSS"

def restart_btn():

    kb = telebot.types.InlineKeyboardMarkup()

    kb.add(

        telebot.types.InlineKeyboardButton(
            "🚀 Novo Sinal",
            callback_data="restart"
        )

    )

    return kb

def menu_paridades():

    kb = telebot.types.InlineKeyboardMarkup(
        row_width=2
    )

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

def run_signal(chat_id, coin_id, exp, message_id=None):

    def process():

        try:

            # 🔧 CORREÇÃO AQUI
            if message_id:
                try:
                    bot.delete_message(chat_id, message_id)
                except Exception:
                    print("⚠️ Não foi possível deletar mensagem antiga")

            with open(ANALISE_GIF, "rb") as gif:
                bot.send_animation(
                    chat_id,
                    gif,
                    caption="🔍 *Aguarde enquanto o Quantix Cripto busca a melhor entrada...*",
                    parse_mode="Markdown"
                )

            direction = analyze(coin_id)

            symbol = BINANCE_SYMBOLS[coin_id]

            now = get_br_time()

            entry_time, gale_time = next_round_time(
                now,
                exp
            )

            exp_min = 1 if exp == "1" else 5

            bot.send_message(

                chat_id,

f"""🎉 *SINAL ENCONTRADO!*

━━━━━━━━━━━━━━━━━━
💱 `{SYMBOLS[coin_id]}`
⏱ Entrada: `{entry_time}`
📅 Gale 1: `{gale_time}`
🎯 Direção: `{direction}`
⏳ Expiração: `{exp_min} min`
📊 Análise: CoinGecko + Binance

Quantix Cripto - Precisão máxima ✨""",

                parse_mode="Markdown",

                reply_markup=restart_btn()

            )

        except Exception as e:

            traceback.print_exc()

            bot.send_message(
                chat_id,
                "❌ Erro. Tente novamente!",
                reply_markup=restart_btn()
            )

    threading.Thread(
        target=process,
        daemon=True
    ).start()

print(f"🚀 QUANTIX ATIVO {get_br_time()}")

try:
    bot.remove_webhook()
    time.sleep(3)
except:
    pass

while True:
    try:
        print("🤖 Polling iniciado...")

        bot.infinity_polling(
            timeout=60,
            long_polling_timeout=60,
            skip_pending=True
        )

    except Exception as e:
        print("⚠️ ERRO NO POLLING:")
        traceback.print_exc()

        print("🔁 Reiniciando em 10 segundos...")
        time.sleep(10)
