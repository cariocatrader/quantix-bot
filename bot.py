import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import threading
import time
import os
from datetime import datetime, timedelta
import pytz

# 1. CoinGecko API (sem chave)
COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"

TOKEN = os.getenv("TOKEN") or "SEU_TOKEN_AQUI"
bot = telebot.TeleBot(TOKEN)

BR_TZ = pytz.timezone('America/Sao_Paulo')
UTC_TZ = pytz.timezone('UTC')

# 2. Mapeamento de CoinGecko
COINGECKO_COINS = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "dot": "polkadot",
    "avax": "avalanche-2",
    "sol": "solana",
}

SYMBOLS = {
    "btc": "₿ BTC/USD",
    "eth": "Ξ ETH/USD",
    "dot": "🟣 DOT/USD",
    "avax": "🔺 AVAX/USD",
    "sol": "☀️ SOL/USD",
}

ANALISE_GIF = "analise.gif"
WIN_GIF = "win.gif"
LOSS_GIF = "loss.gif"

user_state = {}


# =========================
# ANALYZE - TENDÊNCIA 1m COM COINGECKO
# =========================
def analyze_coingecko(coin_id):
    if coin_id not in COINGECKO_COINS:
        print("❌ analyze_coingecko: moeda não suportada")
        return "COMPRA"

    coin = COINGECKO_COINS[coin_id]

    params = {
        "vs_currency": "usd",
        "days": 1,
        "interval": "hourly",
        "precision": "full",
    }

    for tentativa in range(3):
        try:
            r = requests.get(
                COINGECKO_URL.format(coin_id=coin),
                params=params,
                timeout=10
            )

            if r.status_code != 200:
                print("❌ CoinGecko HTTP", r.status_code)
                time.sleep(3)
                continue

            data = r.json()
            if not data or not isinstance(data, list):
                time.sleep(3)
                continue

            closes = [d[4] for d in data if isinstance(d, list) and len(d) >= 5]
            if len(closes) < 10:
                time.sleep(3)
                continue

            short5 = closes[-5:]
            short15 = closes[-15:]

            ma5 = sum(short5) / len(short5)
            ma15 = sum(short15) / len(short15)

            long_trend_up = closes[-1] > ma15
            long_trend_down = closes[-1] < ma15
            short_trend_up = closes[-1] > ma5
            short_trend_down = closes[-1] < ma5

            if long_trend_up and short_trend_up:
                return "COMPRA"
            if long_trend_down and short_trend_down:
                return "VENDA"

            return "COMPRA"

        except Exception as e:
            print("Erro analyze_coingecko (tentativa):", e)
            time.sleep(3)

    print("⚠️ analyze_coingecko falhou, usando fallback COMPRA")
    return "COMPRA"


# =========================
# GET_RESULT_RAW - 1m COM COINGECKO
# =========================
def get_result_raw(direction, coin_id, target_time_dt):
    if coin_id not in COINGECKO_COINS:
        print("❌ Moeda não suportada")
        return "LOSS"

    coin = COINGECKO_COINS[coin_id]

    target_time_dt_utc = target_time_dt.astimezone(UTC_TZ)
    target_candle_start_ms = int(target_time_dt_utc.timestamp()) * 1000

    params = {
        "vs_currency": "usd",
        "days": 1,
        "interval": "minute",
        "precision": "full"
    }

    for tentativa in range(3):
        try:
            r = requests.get(
                COINGECKO_URL.format(coin_id=coin),
                params=params,
                timeout=20
            )

            if r.status_code != 200:
                print("❌ CoinGecko HTTP", r.status_code)
                time.sleep(5)
                continue

            data = r.json()
            if not data or not isinstance(data, list):
                time.sleep(5)
                continue

            closes = [d[4] for d in data if isinstance(d, list) and len(d) >= 5]
            if len(closes) < 1:
                time.sleep(5)
                continue

            o = closes[0]
            c = closes[-1]
            candle_time = target_time_dt.strftime("%H:%M")

            is_win = (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o)
            res = "WIN" if is_win else "LOSS"

            print(
                f"✅ CoinGecko: CANDLE 1m CONFIRMADO {candle_time} | O={o:.2f} C={c:.2f} | RESULTADO: {res}"
            )
            return res

        except Exception as e:
            print("Erro get_result_raw CoinGecko:", e)
            time.sleep(5)

    print("⏰ Não conseguimos obter o candle 1m no tempo especificado, tratando como LOSS")
    return "LOSS"


# =========================
# MENU START
# =========================
def start_menu(chat_id):
    try:
        if chat_id in user_state and "msg_id" in user_state[chat_id]:
            bot.delete_message(chat_id, user_state[chat_id]["msg_id"])
    except Exception:
        pass

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Gerar Sinal", callback_data="gen"))

    msg = bot.send_message(
        chat_id,
        "Seja Bem Vindo ao Quantix Cripto Pro.\nClique abaixo para gerar o sinal.",
        reply_markup=kb,
    )

    if chat_id not in user_state:
        user_state[chat_id] = {}
    user_state[chat_id]["msg_id"] = msg.message_id
    user_state[chat_id]["trading"] = False


# =========================
# MENU PARIDADES
# =========================
def menu_paridades(chat_id):
    try:
        bot.delete_message(chat_id, user_state[chat_id]["msg_id"])
    except Exception:
        pass

    kb = InlineKeyboardMarkup(row_width=1)
    for key, _ in SYMBOLS.items():
        kb.add(
            InlineKeyboardButton(
                SYMBOLS[key],
                callback_data=f"par_{key}",
            )
        )

    msg = bot.send_message(
        chat_id, "📊 Escolha a paridade (CoinGecko 1m):", reply_markup=kb
    )

    if chat_id not in user_state:
        user_state[chat_id] = {}
    user_state[chat_id]["msg_id"] = msg.message_id


# =========================
# ANALISE VISUAL
# =========================
def send_analise(chat_id):
    try:
        bot.delete_message(chat_id, user_state[chat_id]["msg_id"])
    except Exception:
        pass

    if chat_id not in user_state:
        user_state[chat_id] = {}

    msg = bot.send_message(
        chat_id, "🔍 Aguarde enquanto o Quantix analisa o gráfico..."
    )

    try:
        with open(ANALISE_GIF, "rb") as gif:
            bot.send_animation(chat_id, gif)
    except Exception:
        pass

    user_state[chat_id]["msg_id"] = msg.message_id


# =========================
# RESULTADO (SEM GALE)
# =========================
def send_result(chat_id, coin_id, direction, entry, gale, status):
    try:
        bot.delete_message(chat_id, user_state[chat_id]["msg_id"])
    except Exception:
        pass

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔄 Gerar Novo Sinal", callback_data="gen"))

    text = f"""
🎯 RESULTADO

━━━━━━━━━━━━━━━━━━
📊 {SYMBOLS[coin_id]}
⏱ {entry}
🎯 {direction}
🏆 {'✅ WIN' if status == 'WIN' else '❌ LOSS'}
"""

    gif = WIN_GIF if status == "WIN" else LOSS_GIF

    try:
        with open(gif, "rb") as g:
            bot.send_animation(chat_id, g, caption=text, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)

    user_state[chat_id] = {"trading": False}


# =========================
# FLOW SINAL (SEM GALE 1)
# =========================
def flow_sinal(chat_id, coin_id):
    direction = analyze_coingecko(coin_id)

    now = datetime.now(BR_TZ)
    entry = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
    entry_str = entry.strftime("%H:%M")

    try:
        bot.delete_message(chat_id, user_state[chat_id]["msg_id"])
    except Exception:
        pass

    if chat_id not in user_state:
        user_state[chat_id] = {}

    sinal = bot.send_message(
        chat_id,
        f"""
🚗 SINAL ÚNICO (ENTRADA) – CoinGecko 1m

━━━━━━━━━━━━━━━━━━
📊 {SYMBOLS[coin_id]}
⏱ Entrada: {entry_str}
🎯 {direction}
""",
    )

    user_state[chat_id]["msg_id"] = sinal.message_id

    result = get_result_raw(direction, coin_id, entry)
    send_result(chat_id, coin_id, direction, entry_str, False, result)


# =========================
# HANDLERS PRINCIPAIS
# =========================
@bot.message_handler(commands=["start"])
def start(m):
    start_menu(m.chat.id)


@bot.callback_query_handler(func=lambda c: c.data == "gen")
def gen(c):
    bot.answer_callback_query(c.id)
    chat_id = c.message.chat.id

    if user_state.get(chat_id, {}).get("trading"):
        bot.send_message(chat_id, "❌ Aguarde o sinal atual.")
        return

    menu_paridades(chat_id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("par_"))
def par(c):
    bot.answer_callback_query(c.id)
    chat_id = c.message.chat.id

    if user_state.get(chat_id, {}).get("trading"):
        bot.send_message(chat_id, "❌ Aguarde o sinal atual.")
        return

    key = c.data.split("_")[1]
    coin_id = key

    if chat_id not in user_state:
        user_state[chat_id] = {}

    user_state[chat_id]["trading"] = True
    user_state[chat_id]["coin_id"] = coin_id

    send_analise(chat_id)

    def flow():
        flow_sinal(chat_id, coin_id)

    threading.Thread(target=flow, daemon=True).start()


print("🚀 QUANTIX PRO ATIVO (CoinGecko 1m, sem Gale 1, sem chave API)")
bot.infinity_polling()
