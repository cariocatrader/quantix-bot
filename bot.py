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
            print("❌ HTTP analyze:", r.status_code)
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
# RESULTADO (RAW) - COM LOG EXPLICADO
# =========================
def get_result_raw(direction, coin_id, target_time_dt):
    # Alinhar com o minuto cheio da entrada
    target_start = target_time_dt.replace(second=0, microsecond=0)
    target_65s = target_start + timedelta(seconds=65)

    now = datetime.now(BR_TZ)
    wait = (target_65s - now).total_seconds()
    if wait > 0:
        print(f"⏳ Esperando {wait:.1f}s até 65s da entrada {target_time_dt.strftime('%H:%M')}...")
        time.sleep(wait)
    else:
        print("⏱ Entrada já passou 65s, buscando candle imediatamente.")

    try:
        params = {"vs_currency": "usd", "days": "1"}
        r = requests.get(f"{COINGECKO_URL}/coins/{coin_id}/ohlc", params=params, timeout=20)

        if r.status_code != 200:
            print(f"❌ get_result_raw: HTTP {r.status_code}")
            return "LOSS"

        data = r.json()

        target_year = target_time_dt.year
        target_month = target_time_dt.month
        target_day = target_time_dt.day
        target_hour = target_time_dt.hour
        target_minute = target_time_dt.minute

        print(f"🔍 Procurando candle para: {target_time_dt.strftime('%H:%M')} (ou {target_minute+1})...")

        for row in reversed(data):
            if not isinstance(row, list) or len(row) < 5:
                continue

            ts = row[0] / 1000
            o = float(row[1])
            c = float(row[4])
            candle_dt = datetime.fromtimestamp(ts, tz=UTC_TZ).astimezone(BR_TZ)
            candle_min = candle_dt.minute
            candle_text = candle_dt.strftime("%H:%M")

            # Verificar se é o candle da entrada (ou o próximo 1m)
            if (candle_dt.year == target_year and
                candle_dt.month == target_month and
                candle_dt.day == target_day and
                candle_dt.hour == target_hour and
                candle_min in [target_minute, target_minute + 1]):

                print(f"✅ CANDLE ENCONTRADO: {candle_text} | O={o:.2f} C={c:.2f}")
                print(f"🎯 Direção: {direction}")

                is_win = (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o)
                res = "WIN" if is_win else "LOSS"
                print(f"🏆 Resultado: {res} (c > o: {c > o}, direção COMPRA/VENDA)")

                return res

        # Se não encontrou vela alinhada, usa a última vela
        if data:
            row = data[-1]
            if len(row) >= 5:
                ts = row[0] / 1000
                o = float(row[1])
                c = float(row[4])
                candle_dt = datetime.fromtimestamp(ts, tz=UTC_TZ).astimezone(BR_TZ)
                candle_text = candle_dt.strftime("%H:%M")

                print(f"🔁 Fallback: última vela {candle_text} | O={o:.2f} C={c:.2f}")
                is_win = (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o)
                res = "WIN" if is_win else "LOSS"
                print(f"🏆 Resultado fallback: {res}")
                return res

        return "LOSS"

    except Exception as e:
        print("Erro result:", e)
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
# RESULTADO FINAL
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
# HANDLERS
# =========================
@bot.message_handler(commands=['start'])
def start(m):
    start_menu(m.chat.id)


@bot.callback_query_handler(func=lambda c: c.data == "gen")
def gen(c):
    bot.answer_callback_query(c.id)

    if user_state.get(c.message.chat.id, {}).get("trading"):
        bot.send_message(c.message.chat.id, "❌ Aguarde o sinal atual.")
        return

    menu_paridades(c.message.chat.id)


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
        direction = analyze(coin_id)

        now = datetime.now(BR_TZ)
        entry = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)

        entry_str = entry.strftime("%H:%M")
        gale_str = (entry + timedelta(minutes=1)).strftime("%H:%M")

        print(f"🟢 Entrada gerada: {entry_str}")

        try:
            bot.delete_message(chat_id, user_state[chat_id]["msg_id"])
        except Exception:
            pass

        sinal = bot.send_message(
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

        user_state[chat_id]["msg_id"] = sinal.message_id

        result = get_result_raw(direction, coin_id, entry)

        if result == "WIN":
            send_result(chat_id, coin_id, direction, entry_str, False, "WIN")
            return

        # GALE
        try:
            bot.delete_message(chat_id, sinal.message_id)
        except Exception:
            pass

        gale_msg = bot.send_message(chat_id, "❌ Loss na entrada, realizando Gale 1...")

        gale_entry = entry + timedelta(minutes=1)
        result_gale = get_result_raw(direction, coin_id, gale_entry)

        try:
            bot.delete_message(chat_id, gale_msg.message_id)
        except Exception:
            pass

        if result_gale == "WIN":
            send_result(chat_id, coin_id, direction, entry_str, True, "WIN")
        else:
            send_result(chat_id, coin_id, direction, entry_str, True, "LOSS")

    threading.Thread(target=flow, daemon=True).start()


print("🚀 BOT RODANDO...")
bot.infinity_polling()
