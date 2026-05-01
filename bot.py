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
    TOKEN = "8516808804:AAFvv383G9LqDZ3BXjeMpQOc26i0JI6W6Pk"  # <<< só para testar local; no Railway usa env
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
        diff = (datetime.now() - Timer.last_call).total_seconds()
        if diff < 45:
            time.sleep(45 - diff)
    Timer.last_call = datetime.now()

    try:
        params = {"vs_currency": "usd", "days": "1"}
        r = requests.get(
            f"{COINGECKO_URL}/coins/{coin_id}/ohlc",
            params=params,
            timeout=20
        )
        if r.status_code != 200:
            print(f"❌ CoinGecko HTTP {r.status_code}")
            return "COMPRA"

        data = r.json()
        if not data or not isinstance(data, list) or len(data) == 0:
            return "COMPRA"

        closes = []
        for i in range(len(data)-1, max(-1, len(data)-5), -1):
            if i < 0:
                break
            row = data[i]
            if isinstance(row, list) and len(row) >= 5:
                try:
                    c = float(row[4])
                    closes.append(c)
                except:
                    continue

        if len(closes) < 5:
            return "COMPRA"
        return "COMPRA" if closes[-1] > closes[-3] else "VENDA"

    except Exception as e:
        print(f"❌ Erro analyze: {str(e)[:80]}")
        return "COMPRA"


def get_result(chat_id, coin_id, direction, target_time_dt):
    target_start = target_time_dt.replace(second=0, microsecond=0)
    target_65s = target_start + timedelta(seconds=65)
    now = datetime.now(BR_TZ)

    wait = (target_65s - now).total_seconds()
    if wait < 0:
        wait = 0

    print(f"🕒 get_result: wait = {wait:.1f}s, target_start = {target_start}, 65s = {target_65s}")

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
商贸 {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time_text}
🕯️ Candle verificado: {candle_time}
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
商贸 {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time_text}
🕯️ Candle verificado (último): {candle_time}
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


def get_next_times(exp):
    now = datetime.now(BR_TZ)
    entry = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
    gale = entry + timedelta(minutes=1)
    return entry.strftime("%H:%M"), gale.strftime("%H:%M")


def get_result_with_gale_check(chat_id, coin_id, direction, entry_time_dt):
    get_result(chat_id, coin_id, direction, entry_time_dt)
    if chat_id in user_state:
        user_state[chat_id]["trading"] = False


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
        telebot.types.InlineKeyboardButton("⚡ 1 Minuto", callback_data=f"exp_{coin_id}_1")
    )
    return kb


def final_btn():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Gerar Novo Sinal", callback_data="new_signal"))
    return kb


@bot.message_handler(commands=["start"])
def start(m):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Gerar Novo Sinal", callback_data="start"))
    text = f"""
🤖 Quantix Cripto (1m - 65s)

Use o botão abaixo para gerar sinal.
    """
    bot.send_message(m.chat.id, text, reply_markup=kb)


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
    if exp != "1":
        bot.answer_callback_query(c.id, "Apenas 1m está habilitado", show_alert=True)
        return

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
        'exp': exp,
        'trading': True,
        'gale_active': False
    })

    # chama o get_result limpo em thread (1m, 65s)
    threading.Thread(
        target=get_result_with_gale_check,
        args=(c.message.chat.id, coin_id, direction, entry_time_dt),
        daemon=True
    ).start()


@bot.callback_query_handler(func=lambda c: c.data == "new_signal")
def new_signal(c):
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id, "Escolha paridade:", reply_markup=menu_paridades())


print("🚀 QUANTIX ATIVO - 1 chamada CoinGecko, resultado só após 65s (1m)")
bot.remove_webhook()
time.sleep(2)
bot.infinity_polling()
