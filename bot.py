import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import threading
import time
import os
from datetime import datetime, timedelta
import pytz

TOKEN = os.getenv("TOKEN") or "SEU_TOKEN_AQUI"
bot = telebot.TeleBot(TOKEN)

BR_TZ = pytz.timezone('America/Sao_Paulo')
UTC_TZ = pytz.timezone('UTC')

# Bybit Spot 1m kline
BYBIT_URL = "https://api.bybit.com/spot/v3/public/quote/kline"

COIN_IDS_BYBIT = {
    "btc": "BTCUSDT",
    "eth": "ETHUSDT",
    "dot": "DOTUSDT",
    "avax": "AVAXUSDT",
    "sol": "SOLUSDT"
}

SYMBOLS = {
    "btc": "₿ BTC/USDT",
    "eth": "Ξ ETH/USDT",
    "dot": "🟣 DOT/USDT",
    "avax": "🔺 AVAX/USDT",
    "sol": "☀️ SOL/USDT"
}

ANALISE_GIF = "analise.gif"
WIN_GIF = "win.gif"
LOSS_GIF = "loss.gif"

user_state = {}
last_call = None


# =========================
# ANALYZE - TENDÊNCIA COM BYBIT (sem CoinGecko)
# =========================
def analyze_bybit(coin_id):
    if coin_id not in COIN_IDS_BYBIT:
        return "COMPRA"

    symbol = COIN_IDS_BYBIT[coin_id]

    # 1m candles para 100 velas
    end_time_ms = int(datetime.now().timestamp() * 1000)
    start_time_ms = end_time_ms - 100 * 60 * 1000

    try:
        params = {
            "symbol": symbol,
            "interval": "1m",
            "from": start_time_ms,
            "to": end_time_ms,
            "limit": 100
        }

        r = requests.get(BYBIT_URL, params=params, timeout=20)
        if r.status_code != 200:
            print("❌ Bybit HTTP em analyze_bybit")
            return "COMPRA"

        data = r.json()
        if data.get("retCode") != 0:
            print("❌ Bybit erro em analyze_bybit:", data.get("retMsg", ""))
            return "COMPRA"

        klines = data.get("result", {}).get("list", [])
        if len(klines) < 100:
            return "COMPRA"

        closes = []
        for k in klines:
            try:
                c = float(k[4])
                closes.append(c)
            except:
                pass

        if len(closes) < 10:
            return "COMPRA"

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
        print("Erro analyze_bybit:", e)
        return "COMPRA"


# =========================
# GET_RESULT_RAW - USANDO BYBIT 1m (CANDLE CERTO, RESULTADO CERTO)
# =========================
def get_result_raw(direction, coin_id, target_time_dt):
    if coin_id not in COIN_IDS_BYBIT:
        print("❌ Moeda não suportada no Bybit")
        return "LOSS"

    symbol = COIN_IDS_BYBIT[coin_id]

    target_start = target_time_dt.replace(second=0, microsecond=0)
    target_65s = target_start + timedelta(seconds=65)
    max_wait = 120.0
    intervalo = 10
    start_wait = datetime.now(BR_TZ)

    while True:
        now = datetime.now(BR_TZ)
        elapsed = (now - start_wait).total_seconds()

        if elapsed > max_wait:
            print(f"⏰ Timeout 120s atingido para {target_time_dt.strftime('%H:%M')}, tratando como LOSS.")
            return "LOSS"

        wait = (target_65s - now).total_seconds()
        if wait > 0:
            time.sleep(wait)

        try:
            end_time_ms = int(target_65s.timestamp() * 1000)
            start_time_ms = int((target_start - timedelta(minutes=5)).timestamp() * 1000)

            params = {
                "symbol": symbol,
                "interval": "1m",
                "from": start_time_ms,
                "to": end_time_ms,
                "limit": 100
            }

            r = requests.get(BYBIT_URL, params=params, timeout=20)

            if r.status_code != 200:
                print(f"❌ Bybit HTTP {r.status_code}")
                time.sleep(intervalo)
                continue

            data = r.json()
            if data.get("retCode") != 0:
                print("❌ Bybit retornou erro:", data.get("retMsg", ""))
                time.sleep(intervalo)
                continue

            klines = data.get("result", {}).get("list", [])
            if not klines:
                print("❌ Bybit não retornou candles 1m")
                time.sleep(intervalo)
                continue

            target_time_dt_utc = target_time_dt.astimezone(UTC_TZ)
            target_minute = target_time_dt_utc.minute
            target_hour = target_time_dt_utc.hour

            candle_found = None
            for k in klines:
                try:
                    start_time_ms = int(k[0])
                    start_time_dt = datetime.fromtimestamp(start_time_ms / 1000, tz=UTC_TZ)

                    if (start_time_dt.minute == target_minute and
                        start_time_dt.hour == target_hour):

                        candle_found = {
                            "open": float(k[1]),
                            "close": float(k[4]),
                            "start_time_dt": start_time_dt
                        }
                        break
                except Exception as e:
                    print("❌ Erro processando kline Bybit:", e)
                    continue

            if not candle_found:
                print(f"⏳ Procurando candle 1m de {target_time_dt.strftime('%H:%M')} no Bybit...")
                time.sleep(intervalo)
                continue

            o = candle_found["open"]
            c = candle_found["close"]
            candle_time = candle_found["start_time_dt"].strftime("%H:%M")

            is_win = (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o)
            res = "WIN" if is_win else "LOSS"
            print(f"✅ Bybit: CANDLE 1m CONFIRMADO {candle_time} | O={o:.2f} C={c:.2f} | RESULTADO: {res}")
            return res

        except Exception as e:
            print("Erro get_result_raw Bybit:", e)
            time.sleep(intervalo)

    print(f"⏰ Timeout 120s atingido buscando candle 1m {target_time_dt.strftime('%H:%M')} no Bybit, tratando como LOSS.")
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
        reply_markup=kb
    )

    user_state[chat_id] = {"msg_id": msg.message_id, "trading": False}


# =========================
# MENU PARIDADES (CORRETO, SEM KeyError)
# =========================
def menu_paridades(chat_id):
    try:
        bot.delete_message(chat_id, user_state[chat_id]["msg_id"])
    except Exception:
        pass

    kb = InlineKeyboardMarkup(row_width=1)
    for key, _ in COIN_IDS_BYBIT.items():
        kb.add(
            InlineKeyboardButton(
                SYMBOLS[key],
                callback_data=f"pair_{key}"
            )
        )

    msg = bot.send_message(chat_id, "📊 Escolha a paridade (Bybit):", reply_markup=kb)
    user_state[chat_id]["msg_id"] = msg.message_id


# =========================
# ANALISE VISUAL
# =========================
def send_analise(chat_id):
    try:
        bot.delete_message(chat_id, user_state[chat_id]["msg_id"])
    except Exception:
        pass

    msg = bot.send_message(chat_id, "🔍 Aguarde enquanto o Quantix analisa o gráfico...")

    try:
        with open(ANALISE_GIF, 'rb') as gif:
            bot.send_animation(chat_id, gif)
    except Exception:
        pass

    user_state[chat_id]["msg_id"] = msg.message_id


# =========================
# RESULTADO FINAL (SEM GALE)
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
        with open(gif, 'rb') as g:
            bot.send_animation(chat_id, g, caption=text, reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)

    user_state[chat_id] = {"trading": False}


# =========================
# FLOW SINAL (SEM GALE 1, SÓ ENTRADA)
# =========================
def flow_sinal(chat_id, coin_id):
    direction = analyze_bybit(coin_id)

    now = datetime.now(BR_TZ)
    entry = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
    entry_str = entry.strftime("%H:%M")

    try:
        bot.delete_message(chat_id, user_state[chat_id]["msg_id"])
    except Exception:
        pass

    sinal = bot.send_message(
        chat_id,
        f"""
🚗 SINAL ÚNICO (ENTRADA) – Bybit

━━━━━━━━━━━━━━━━━━
📊 {SYMBOLS[coin_id]}
⏱ Entrada: {entry_str}
🎯 {direction}
"""
    )
    user_state[chat_id]["msg_id"] = sinal.message_id

    result = get_result_raw(direction, coin_id, entry)
    send_result(chat_id, coin_id, direction, entry_str, False, result)


# =========================
# HANDLERS PRINCIPAIS
# =========================
@bot.message_handler(commands=['start'])
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


@bot.callback_query_handler(func=lambda c: c.data.startswith("pair_"))
def pair(c):
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


print("🚀 QUANTIX PRO ATIVO (Bybit 1m, sem Gale 1, análise 5m–15m–100m, até 120s de espera)")
bot.infinity_polling()
