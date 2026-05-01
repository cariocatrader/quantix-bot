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

# 1. Kraken Spot 1m OHLC
KRAKEN_URL = "https://api.kraken.com/0/public/OHLC"

COIN_IDS_KRAKEN = {
    "btc": "XBTUSD",
    "eth": "ETHUSD",
    "dot": "DOTUSD",
    "avax": "AVAXUSD",
    "sol": "SOLUSD"
}

SYMBOLS = {
    "btc": "₿ BTC/USD",
    "eth": "Ξ ETH/USD",
    "dot": "🟣 DOT/USD",
    "avax": "🔺 AVAX/USD",
    "sol": "☀️ SOL/USD"
}

ANALISE_GIF = "analise.gif"
WIN_GIF = "win.gif"
LOSS_GIF = "loss.gif"

user_state = {}


# =========================
# ANALYZE - TENDÊNCIA COM KRAKEN 1m
# =========================
def analyze_kraken(coin_id):
    if coin_id not in COIN_IDS_KRAKEN:
        return "COMPRA"

    pair = COIN_IDS_KRAKEN[coin_id]

    # 10 minutos de histórico
    now = datetime.now()
    since = int(now.timestamp()) - 10 * 60

    for tentativa in range(3):
        try:
            params = {
                "pair": pair,
                "since": since,
                "interval": 1  # 1m
            }

            r = requests.get(
                KRAKEN_URL,
                params=params,
                timeout=10
            )

            if r.status_code != 200:
                print(f"❌ Kraken HTTP {r.status_code} em analyze_kraken")
                time.sleep(3)
                continue

            data = r.json()
            if not data:
                time.sleep(3)
                continue

            errors = data.get("error", [])
            if errors:
                print("❌ Kraken erros:", errors)
                time.sleep(3)
                continue

            result = data.get("result", {})
            if not result or pair not in result:
                print("⚠️ Kraken: par não encontrado no result, tentando novamente...")
                time.sleep(3)
                continue

            ohlc = result[pair]
            if not isinstance(ohlc, list) or len(ohlc) < 10:
                print("⚠️ Kraken: poucas velas (<10), tentando novamente...")
                time.sleep(3)
                continue

            closes = []
            for k in ohlc:
                if isinstance(k, list) and len(k) >= 5:
                    try:
                        c = float(k[4])
                        closes.append(c)
                    except:
                        pass

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
            print("Erro analyze_kraken (tentativa):", e)
            time.sleep(3)

    print("⚠️ analyze_kraken falhou totalmente, usando fallback COMPRA")
    return "COMPRA"


# =========================
# GET_RESULT_RAW - KRAKEN 1m (CORRIGIDO PARA CANDLE CERTO)
# =========================
def get_result_raw(direction, coin_id, target_time_dt):
    if coin_id not in COIN_IDS_KRAKEN:
        print("❌ Moeda não suportada na Kraken")
        return "LOSS"

    pair = COIN_IDS_KRAKEN[coin_id]

    # 1. Converta para UTC e arredonde para o minuto ZERADO
    target_time_dt_utc = target_time_dt.astimezone(UTC_TZ)
    target_candle_start_s = int(
        target_time_dt_utc.replace(second=0, microsecond=0).timestamp()
    )

    max_wait = 120.0
    intervalo = 10
    start_wait = datetime.now(BR_TZ)

    while True:
        now = datetime.now(BR_TZ)
        elapsed = (now - start_wait).total_seconds()

        if elapsed > max_wait:
            print(f"⏰ Timeout 120s atingido para {target_time_dt.strftime('%H:%M')}, tratando como LOSS.")
            return "LOSS"

        wait = (target_time_dt_utc.replace(second=0, microsecond=0) + timedelta(seconds=65) - now).total_seconds()
        if wait > 0:
            time.sleep(max(wait, 2))

        try:
            # Buscar 10 minutos de histórico
            since = target_candle_start_s - 10 * 60

            params = {
                "pair": pair,
                "since": since,
                "interval": 1
            }

            r = requests.get(
                KRAKEN_URL,
                params=params,
                timeout=20
            )

            if r.status_code != 200:
                print(f"❌ Kraken HTTP {r.status_code}")
                time.sleep(intervalo)
                continue

            data = r.json()
            if not data:
                print("⚠️ Kraken: resposta vazia, tentando novamente...")
                time.sleep(intervalo)
                continue

            errors = data.get("error", [])
            if errors:
                print("❌ Kraken retornou erro:", errors)
                time.sleep(intervalo)
                continue

            result = data.get("result", {})
            if not result or pair not in result:
                print("⏳ Kraken: par não encontrado no result, tentando novamente...")
                time.sleep(intervalo)
                continue

            ohlc = result[pair]
            if not isinstance(ohlc, list) or len(ohlc) < 1:
                print("⏳ Kraken não retornou candles 1m, tentando novamente...")
                time.sleep(intervalo)
                continue

            # 2. Procurar o candle pelo timestamp exato
            candle_found = None
            for k in ohlc:
                try:
                    if isinstance(k, list) and len(k) >= 5:
                        candle_time_s = int(k[0])  # timestamp em segundos

                        if candle_time_s == target_candle_start_s:
                            candle_found = {
                                "open": float(k[1]),
                                "close": float(k[4]),
                                "start_time_dt": datetime.fromtimestamp(
                                    candle_time_s, tz=UTC_TZ
                                ),
                            }
                            break
                except Exception as e:
                    print("❌ Erro processando kline Kraken:", e)
                    continue

            if not candle_found:
                print(f"⏳ Procurando candle 1m de {target_time_dt.strftime('%H:%M')} na Kraken...")
                time.sleep(intervalo)
                continue

            o = candle_found["open"]
            c = candle_found["close"]
            candle_time = candle_found["start_time_dt"].strftime("%H:%M")

            is_win = (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o)
            res = "WIN" if is_win else "LOSS"
            print(
                f"✅ Kraken: CANDLE 1m CONFIRMADO {candle_time} | O={o:.2f} C={c:.2f} | RESULTADO: {res}"
            )
            return res

        except Exception as e:
            print("Erro get_result_raw Kraken:", e)
            time.sleep(intervalo)

    print(
        f"⏰ Timeout 120s atingido buscando candle 1m {target_time_dt.strftime('%H:%M')} na Kraken, tratando como LOSS."
    )
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
    for key, _ in COIN_IDS_KRAKEN.items():
        kb.add(
            InlineKeyboardButton(
                SYMBOLS[key],
                callback_data=f"par_{key}",
            )
        )

    msg = bot.send_message(
        chat_id, "📊 Escolha a paridade (Kraken Spot):", reply_markup=kb
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
    direction = analyze_kraken(coin_id)

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
🚗 SINAL ÚNICO (ENTRADA) – Kraken

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


print("🚀 QUANTIX PRO ATIVO (Kraken 1m, sem Gale 1, até 120s de espera)")
bot.infinity_polling()
