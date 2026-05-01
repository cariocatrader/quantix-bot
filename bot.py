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
# ANALYZE
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
            return "COMPRA"

        data = r.json()

        closes = []
        for row in data[-5:]:
            closes.append(float(row[4]))

        if len(closes) < 5:
            return "COMPRA"

        return "COMPRA" if closes[-1] > closes[-3] else "VENDA"

    except Exception as e:
        print("Erro analyze:", e)
        return "COMPRA"


# =========================
# GET_RESULT - A MESMA LÓGICA VALIDADA DO CÓDIGO SIMPLES (BTC)
# =========================
def get_result(chat_id, direction, coin_id, target_time_dt):
    target_start = target_time_dt.replace(second=0, microsecond=0)
    target_65s = target_start + timedelta(seconds=65)
    now = datetime.now(BR_TZ)

    wait = (target_65s - now).total_seconds()
    if wait < 0:
        wait = 0

    print(f"🕒 get_result: wait = {wait:.1f}s, target_start = {target_start}, target_65s = {target_65s}")
    if wait > 0:
        time.sleep(wait)

    try:
        params = {"vs_currency": "usd", "days": "1"}
        r = requests.get(f"{COINGECKO_URL}/coins/{coin_id}/ohlc", params=params, timeout=20)

        if r.status_code != 200:
            print(f"❌ CoinGecko HTTP {r.status_code} - {r.text[:100]}")
            if r.status_code == 429:
                bot.send_message(chat_id, "❌ ERRO 429: limite de requisições excedido no CoinGecko.")
            elif r.status_code == 500:
                bot.send_message(chat_id, "❌ ERRO 500: problema temporário no CoinGecko.")
            else:
                bot.send_message(chat_id, f"❌ Erro HTTP {r.status_code} ao verificar o CoinGecko.")
            return

        data = r.json()
        if not isinstance(data, list) or len(data) == 0:
            print("❌ CoinGecko retornou data vazia ou inválida")
            bot.send_message(chat_id, "❌ Sem dados para o ativo (API).")
            return

        target_year = target_time_dt.year
        target_month = target_time_dt.month
        target_day = target_time_dt.day
        target_hour = target_time_dt.hour
        target_minute = target_time_dt.minute

        for i in range(len(data)-1, max(-1, len(data)-100), -1):
            row = data[i]
            if not isinstance(row, list) or len(row) < 5:
                continue
            try:
                ts = row[0] / 1000
                o = float(row[1])
                c = float(row[4])
                candle_dt = datetime.fromtimestamp(ts, tz=UTC_TZ).astimezone(BR_TZ)

                if (candle_dt.year == target_year and
                    candle_dt.month == target_month and
                    candle_dt.day == target_day and
                    candle_dt.hour == target_hour and
                    candle_dt.minute in [target_minute, target_minute + 1]):
                    is_win = (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o)
                    status = "✅ WIN" if is_win else "❌ LOSS"
                    entry_time_text = target_time_dt.strftime("%H:%M")
                    candle_time = candle_dt.strftime("%H:%M")

                    text = f"""
🎯 RESULTADO FINAL

━━━━━━━━━━━━━━━━━━
📊 {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time_text}
🕯️ {candle_time}
🎯 {direction}
🏆 {status}
                    """
                    bot.send_message(chat_id, text)
                    return
            except Exception as e:
                print(f"❌ Erro processando vela: {str(e)[:80]}")

        if data:
            row = data[-1]
            if isinstance(row, list) and len(row) >= 5:
                try:
                    ts = row[0] / 1000
                    o = float(row[1])
                    c = float(row[4])
                    candle_dt = datetime.fromtimestamp(ts, tz=UTC_TZ).astimezone(BR_TZ)
                    entry_time_text = target_time_dt.strftime("%H:%M")
                    candle_time = candle_dt.strftime("%H:%M")
                    is_win = (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o)
                    status = "✅ WIN" if is_win else "❌ LOSS"

                    text = f"""
🎯 RESULTADO FINAL (ÚLTIMA VELA)

━━━━━━━━━━━━━━━━━━
📊 {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time_text}
🕯️ {candle_time}
🎯 {direction}
🏆 {status}
                    """
                    bot.send_message(chat_id, text)
                    return
                except Exception as e:
                    print(f"❌ Erro lendo última vela: {str(e)[:80]}")

        bot.send_message(chat_id, "❌ Não foi possível validar o resultado (sem vela clara).")

    except Exception as e:
        print(f"❌ Erro completo em get_result: {str(e)[:120]}")
        bot.send_message(chat_id, "❌ ERRO inesperado ao calcular resultado.")


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
# RESULTADO FINAL (GIF + NOVO SINAL)
# =========================
def send_result(chat_id, coin_id, direction, entry, gale, status):
    try:
        bot.delete_message(chat_id, user_state[chat_id]["msg_id"])
    except Exception:
        pass

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔄 Gerar Novo Sinal", callback_data="gen"))

    text = f"""
🎯 RESULTADO {'(GALE)' if gale else ''}

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
# FLOW DE SINAL + GALE (USANDO get_result VALIDADA)
# =========================
def flow_sinal(chat_id, coin_id):
    direction = analyze(coin_id)

    now = datetime.now(BR_TZ)
    entry = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)

    entry_str = entry.strftime("%H:%M")
    gale_str = (entry + timedelta(minutes=1)).strftime("%H:%M")

    print(f"🟢 Entrada gerada: {entry_str} | {SYMBOLS[coin_id]}")

    try:
        bot.delete_message(chat_id, user_state[chat_id]["msg_id"])
    except Exception:
        pass

    msg_sinal = bot.send_message(
        chat_id,
        f"""
🚂 SINAL ENCONTRADO

━━━━━━━━━━━━━━━━━━
📊 {SYMBOLS[coin_id]}
⏱ Entrada: {entry_str}
🎯 {direction}
♻️ Gale 1: {gale_str}
"""
    )
    user_state[chat_id]["msg_id"] = msg_sinal.message_id

    # --- RESULTADO ENTRADA PRINCIPAL ---
    get_result(chat_id, direction, coin_id, entry)
    # aqui o bot já envia mensagem de resultado com WIN/LOSS e candle
    return


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

    user_state[chat_id]["trading"] = True

    send_analise(chat_id)

    def flow():
        flow_sinal(chat_id, coin_id)

    threading.Thread(target=flow, daemon=True).start()


print("🚀 QUANTIX PRO ATIVO (65s, múltiplas criptos, get_result validado do código simples)")
bot.infinity_polling()
