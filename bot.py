import telebot
import requests
import threading
import time
import os
from datetime import datetime, timedelta, timezone
import pytz
import math

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise Exception("TOKEN não encontrado")
bot = telebot.TeleBot(TOKEN)

BR_TZ = pytz.timezone('America/Sao_Paulo')
UTC_TZ = pytz.timezone('UTC')

COINGECKO_URL = "https://api.coingecko.com/api/v3"
WIN_GIF = "win.gif"
LOSS_GIF = "loss.gif"

SYMBOLS = {
    "bitcoin": "₿ Bitcoin", "ethereum": "Ξ Ethereum",
    "binancecoin": "🟡 BNB", "solana": "🟣 Solana",
    "ripple": "💧 XRP", "cardano": "🔵 Cardano",
    "dogecoin": "🐶 Doge", "litecoin": "🪙 Litecoin",
    "polkadot": "⚫ Polkadot", "avalanche-2": "🔺 Avalanche"
}
VALID_COIN_IDS = set(SYMBOLS.keys())

user_state = {}

def get_br_time(fmt="%H:%M"):
    return datetime.now(BR_TZ).strftime(fmt)

class Timer:
    last_call = None

def analyze(coin_id):
    if coin_id not in VALID_COIN_IDS:
        return "COMPRA"
    if Timer.last_call:
        diff = (datetime.now(BR_TZ) - Timer.last_call).total_seconds()
        if diff < 45:
            time.sleep(45 - diff)
    Timer.last_call = datetime.now(BR_TZ)

    try:
        params = {"vs_currency": "usd", "days": "1"}
        r = requests.get(
            f"{COINGECKO_URL}/coins/{coin_id}/ohlc",
            params=params,
            timeout=20
        )
        if r.status_code != 200:
            return "COMPRA"
        data = r.json()
        if not data or not isinstance(data, list):
            return "COMPRA"
        closes = [float(row[4]) for row in data[-5:] if isinstance(row, list) and len(row) >= 5]
        if len(closes) < 5:
            return "COMPRA"
        return "COMPRA" if closes[-1] > closes[-3] else "VENDA"
    except Exception as e:
        return "COMPRA"

def get_result(coin_id, direction, target_time_dt):
    exp = user_state.get("exp", "1")
    wait_time = 65 if exp == "1" else 310
    target_start = target_time_dt.replace(second=0, microsecond=0)
    target_65s = target_start + timedelta(seconds=wait_time)
    now = datetime.now(BR_TZ)
    wait = (target_65s - now).total_seconds()
    if wait < 0:
        wait = 0
    if wait > 0:
        time.sleep(wait)

    try:
        params = {"vs_currency": "usd", "days": "1"}
        r = requests.get(
            f"{COINGECKO_URL}/coins/{coin_id}/ohlc",
            params=params,
            timeout=20
        )
        if r.status_code != 200:
            return None

        data = r.json()
        if not data or not isinstance(data, list):
            return None

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
                    return "WIN" if (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o) else "LOSS"
            except Exception as e:
                pass
        if data:
            row = data[-1]
            if isinstance(row, list) and len(row) >= 5:
                try:
                    ts = row[0] / 1000
                    o = float(row[1])
                    c = float(row[4])
                    if (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o):
                        return "WIN"
                    else:
                        return "LOSS"
                except Exception as e:
                    pass
    except Exception as e:
        pass
    return None

def get_next_times(exp):
    now = datetime.now(BR_TZ)
    if exp == "1":
        entry = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        gale = entry + timedelta(minutes=1)
    else:
        m = math.ceil(now.minute / 5.0) * 5
        entry = now.replace(minute=int(m), second=0, microsecond=0)
        if entry <= now:
            entry += timedelta(hours=1)
        gale = entry + timedelta(minutes=5)
    return entry.strftime("%H:%M"), gale.strftime("%H:%M")

def send_animation_safe(chat_id, gif_path, caption, markup=None):
    try:
        with open(gif_path, 'rb') as gif:
            bot.send_animation(chat_id, gif, caption=caption, reply_markup=markup, timeout=30)
    except Exception as e:
        bot.send_message(chat_id, caption, reply_markup=markup)

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

def final_btn():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Gerar Novo Sinal", callback_data="new_signal"))
    return kb

def process_trade(chat_id, coin_id, direction, entry_time_dt, exp, is_gale=False):
    def check():
        wait_time = 65 if exp == "1" else 310
        entry_time_str = entry_time_dt.strftime("%H:%M")

        time.sleep(wait_time)
        result = get_result(coin_id, direction, entry_time_dt)
        if result is None:
            bot.send_message(chat_id, f"❌ Não foi possível validar o resultado para {SYMBOLS[coin_id]} às {entry_time_str}.")
        else:
            status = "✅ WIN" if result == "WIN" else "❌ LOSS"
            text = f"""
🎯 RESULTADO FINAL

━━━━━━━━━━━━━━━━━━
商贸 {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time_str}
🎯 {direction}
🏆 {status}
            """
            gif_file = WIN_GIF if result == "WIN" else LOSS_GIF
            send_animation_safe(chat_id, gif_file, text, final_btn())
        if chat_id in user_state:
            user_state[chat_id]["trading"] = False
        if result == "LOSS" and not is_gale:
            auto_gale(chat_id)
    threading.Thread(target=check, daemon=True).start()

def auto_gale(chat_id):
    if chat_id not in user_state:
        return
    state = user_state[chat_id]
    if state.get('gale_active', False):
        return
    state['gale_active'] = True
    bot.send_message(chat_id, f"""
🔥 ENTRANDO EM GALE 1!

━━━━━━━━━━━━━━━━━━
商贸 {SYMBOLS[state['coin_id']]}
⏱ {state['gale_time']}
🎯 {state['direction']}
    """)

@bot.message_handler(commands=["start"])
def start(m):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Gerar Novo Sinal", callback_data="start"))
    bot.send_message(m.chat.id, "🤖 Quantix Cripto", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "start")
def start_flow(c):
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id, "Escolha paridade:", reply_markup=menu_paridades())

@bot.callback_query_handler(func=lambda c: c.data.startswith("par_"))
def paridade(c):
    coin_id = c.data.split("_")[1]
    if coin_id not in VALID_COIN_IDS:
        bot.answer_callback_query(c.id, "Paridade inválida", show_alert=True)
        return
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id, "Escolha expiração:", reply_markup=menu_exp(coin_id))

@bot.callback_query_handler(func=lambda c: c.data.startswith("exp_"))
def exp_handler(c):
    parts = c.data.split("_")
    if len(parts) != 3:
        bot.answer_callback_query(c.id, "Erro de sinal", show_alert=True)
        return
    coin_id, exp = parts[1], parts[2]
    user_state[c.message.chat.id] = {'coin_id': coin_id, 'exp': exp}
    entry_time_str, gale_time_str = get_next_times(exp)
    entry_time_dt = BR_TZ.localize(datetime.strptime(entry_time_str, "%H:%M"))

    direction = analyze(coin_id)
    text = f"""
🎉 SINAL GERADO!

━━━━━━━━━━━━━━━━━━━
商贸 {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time_str}
🔥 Gale 1: {gale_time_str}
🎯 {direction}
    """
    bot.send_message(c.message.chat.id, text)
    user_state[c.message.chat.id].update({
        'direction': direction,
        'entry_time': entry_time_str,
        'gale_time': gale_time_str,
        'entry_time_dt': entry_time_dt,
        'trading': True,
        'gale_active': False
    })
    process_trade(c.message.chat.id, coin_id, direction, entry_time_dt, exp, False)

@bot.callback_query_handler(func=lambda c: c.data == "new_signal")
def new_signal(c):
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id, "Escolha paridade:", reply_markup=menu_paridades())

print("🚀 QUANTIX ATIVO - 1 chamada CoinGecko, resultado só após 65/310s")
bot.remove_webhook()
time.sleep(2)
bot.infinity_polling()
