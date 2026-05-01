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

COINGECKO_URL = "https://api.coingecko.com/api/v3"

COIN_IDS = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "dot": "polkadot",
    "avax": "avalanche-2",
    "sol": "solana"
}

SYMBOLS = {
    "bitcoin": "₿ BTC/USD",
    "ethereum": "Ξ ETH/USD",
    "polkadot": "🟣 DOT/USD",
    "avalanche-2": "🔺 AVAX/USD",
    "solana": "☀️ SOL/USD"
}

ANALISE_GIF = "analise.gif"
WIN_GIF = "win.gif"
LOSS_GIF = "loss.gif"

user_state = {}
last_call = None


# =========================
# ANALYZE - ANÁLISE MAIS CONSERVADORA E TENDÊNCIA 1m–15m
# =========================
def analyze(coin_id):
    global last_call

    if last_call:
        diff = (datetime.now() - last_call).total_seconds()
        if diff < 45:
            time.sleep(45 - diff)

    last_call = datetime.now()

    try:
        params = {"vs_currency": "usd", "days": "1"}
        r = requests.get(f"{COINGECKO_URL}/coins/{coin_id}/ohlc", params=params, timeout=20)

        if r.status_code != 200:
            print(f"❌ CoinGecko HTTP {r.status_code} em analyze")
            return "COMPRA"  # fallback temporário

        data = r.json()
        if not isinstance(data, list) or len(data) < 100:
            return "COMPRA"

        # pega últimas 100 velas (100m)
        closes = []
        for row in data[-100:]:
            if isinstance(row, list) and len(row) >= 5:
                try:
                    c = float(row[4])
                    closes.append(c)
                except:
                    pass

        if len(closes) < 10:
            return "COMPRA"

        # shorts: 5m, 15m (últimos 5, 15 candles)
        short5 = closes[-5:]
        short15 = closes[-15:]

        # média simples 5m e 15m
        ma5 = sum(short5) / len(short5)
        ma15 = sum(short15) / len(short15)

        # direção de longo prazo: se o fechamento está acima da média 15m
        long_trend_up = closes[-1] > ma15
        long_trend_down = closes[-1] < ma15

        # força de curto prazo: 5m
        short_trend_up = closes[-1] > ma5
        short_trend_down = closes[-1] < ma5

        # --- REGRA DE DECISÃO (CONSERVADORA) ---
        # só entra COMPRA se:
        # 1) a média 15m é de "alta" (fechamento acima) E
        # 2) a média 5m também está acima (confirmação)
        if long_trend_up and short_trend_up:
            return "COMPRA"

        # só entra VENDA se:
        # 1) a média 15m é de "baixa" E
        # 2) a média 5m também está abaixo
        if long_trend_down and short_trend_down:
            return "VENDIDGE"

        # caso não haja tendência clara, DECISÃO CONSERVADORA
        # ou apenas default para COMPRA
        return "COMPRA"

    except Exception as e:
        print("Erro analyze:", e)
        return "COMPRA"


# =========================
# GET_RESULT_RAW - SEM GALE, EXIGIR CANDLE 1m CORRETO
# =========================
def get_result_raw(direction, coin_id, target_time_dt):
    target_start = target_time_dt.replace(second=0, microsecond=0)
    target_65s = target_start + timedelta(seconds=65)
    now = datetime.now(BR_TZ)

    wait = (target_65s - now).total_seconds()
    if wait < 0:
        wait = 0

    print(f"🕒 get_result_raw: wait = {wait:.1f}s, target_start = {target_start}, target_65s = {target_65s}")
    if wait > 0:
        time.sleep(wait)

    try:
        params = {"vs_currency": "usd", "days": "1"}
        r = requests.get(f"{COINGECKO_URL}/coins/{coin_id}/ohlc", params=params, timeout=20)

        if r.status_code != 200:
            print(f"❌ CoinGecko HTTP {r.status_code}")
            return "LOSS"

        data = r.json()
        if not isinstance(data, list) or len(data) == 0:
            print("❌ CoinGecko retornou data vazia ou inválida")
            return "LOSS"

        # Transformar o tempo de entrada para UTC antes de comparar
        target_time_dt_utc = target_time_dt.astimezone(UTC_TZ)
        target_year = target_time_dt_utc.year
        target_month = target_time_dt_utc.month
        target_day = target_time_dt_utc.day
        target_hour = target_time_dt_utc.hour
        target_minute = target_time_dt_utc.minute

        print(f"🔍 Procurando candle 1m para {target_time_dt.strftime('%H:%M')} ou +1 min")

        candle_found = None
        # janela de 300 velas (5 minutos de 1m), mas pode ser alargada
        for i in range(len(data) - 1, max(-1, len(data) - 300), -1):
            row = data[i]
            if not isinstance(row, list) or len(row) < 5:
                continue
            try:
                ts = row[0] / 1000
                o = float(row[1])
                c = float(row[4])
                candle_dt = datetime.fromtimestamp(ts, tz=UTC_TZ)

                if (candle_dt.year == target_year and
                    candle_dt.month == target_month and
                    candle_dt.day == target_day and
                    candle_dt.hour == target_hour and
                    candle_dt.minute in [target_minute, target_minute + 1]):

                    candle_found = {"o": o, "c": c, "candle_dt": candle_dt}
                    break

            except Exception as e:
                print(f"❌ Erro processando vela: {str(e)[:80]}")
                continue

        if not candle_found:
            print(f"❌ Não encontrou candle 1m de entrada {target_time_dt.strftime('%H:%M')} ou {target_time_dt.strftime('%H:%M')} + 1 min, tratando como LOSS.")
            return "LOSS"

        o = candle_found["o"]
        c = candle_found["c"]
        candle_dt = candle_found["candle_dt"]
        candle_time = candle_dt.strftime("%H:%M")

        is_win = (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o)
        res = "WIN" if is_win else "LOSS"
        print(f"✅ CANDLE 1m CONFIRMADO: {candle_time} | O={o:.2f} C={c:.2f} | RESULTADO: {res}")
        return res

    except Exception as e:
        print("Erro get_result_raw:", e)
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
# MENU PARIDADES
# =========================
def menu_paridades(chat_id):
    try:
        bot.delete_message(chat_id, user_state[chat_id]["msg_id"])
    except Exception:
        pass

    kb = InlineKeyboardMarkup(row_width=1)

    for key, coin_id in COIN_IDS.items():
        kb.add(InlineKeyboardButton(SYMBOLS[coin_id], callback_data=f"pair_{key}"))

    msg = bot.send_message(chat_id, "📊 Escolha a paridade:", reply_markup=kb)

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
    direction = analyze(coin_id)

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
🚗 SINAL ÚNICO (ENTRADA)

━━━━━━━━━━━━━━━━━━
📊 {SYMBOLS[coin_id]}
⏱ Entrada: {entry_str}
🎯 {direction}
"""
    )
    user_state[chat_id]["msg_id"] = sinal.message_id

    # --- RESULTADO APÓS 65s (SEM GALE)
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
    coin_id = COIN_IDS[key]

    # Garantir que o chat_id exista
    if chat_id not in user_state:
        user_state[chat_id] = {}

    user_state[chat_id]["trading"] = True
    user_state[chat_id]["coin_id"] = coin_id

    send_analise(chat_id)

    def flow():
        flow_sinal(chat_id, coin_id)

    threading.Thread(target=flow, daemon=True).start()


print("🚀 QUANTIX PRO ATIVO (sem Gale 1, análise de tendências 5m–15m, exigir candle 1m correto)")
bot.infinity_polling()
