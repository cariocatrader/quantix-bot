import telebot
import requests
import threading
import time
import os
from datetime import datetime, timedelta, timezone
import pytz

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    TOKEN = "8516808804:AAFvv383G9LqDZ3BXjeMpQOc26i0JI6W6Pk"  # só para teste
bot = telebot.TeleBot(TOKEN)

BR_TZ = pytz.timezone('America/Sao_Paro')
UTC_TZ = pytz.timezone('UTC')

COINGECKO_URL = "https://api.coingecko.com/api/v3"

# 5 criptos mais líquidas
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

user_state = {}

ANALISE_GIF = "analise.gif"
WIN_GIF = "win.gif"
LOSS_GIF = "loss.gif"


def get_br_time(fmt="%H:%M"):
    return datetime.now(BR_TZ).strftime(fmt)


last_call = None


def analyze(coin_id):
    global last_call
    if last_call is not None:
        diff = (datetime.now() - last_call).total_seconds()
        if diff < 45:
            time.sleep(45 - diff)
    last_call = datetime.now()

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


def get_result(chat_id, direction, coin_id, target_time_dt):
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

                    text = f"""
🎯 RESULTADO FINAL

━━━━━━━━━━━━━━━━━━
📊 Paridade: {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time_text}
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
                    is_win = (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o)
                    status = "✅ WIN" if is_win else "❌ LOSS"

                    text = f"""
🎯 RESULTADO FINAL

━━━━━━━━━━━━━━━━━━
📊 Paridade: {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time_text}
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


def start_menu(chat_id):
    text = "Seja bem-vindo ao Quantix Cripto Pro. Clique abaixo para gerar o sinal."
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("Gerar Sinal", callback_data="gen_signal"))
    msg = bot.send_message(chat_id, text, reply_markup=kb)
    user_state[chat_id] = {"stage": "start", "msg_id": msg.message_id}


def menu_paridades(chat_id):
    if chat_id in user_state and "msg_id" in user_state[chat_id]:
        try:
            bot.delete_message(chat_id, user_state[chat_id]["msg_id"])
        except Exception:
            pass

    text = "📊 Escolha a paridade:"
    kb = telebot.types.InlineKeyboardMarkup(row_width=1)
    for key, coin_id in COIN_IDS.items():
        kb.add(
            telebot.types.InlineKeyboardButton(
                f"{SYMBOLS[coin_id]}",
                callback_data=f"pair_{key}")
        )
    msg = bot.send_message(chat_id, text, reply_markup=kb)
    user_state[chat_id] = {"stage": "choose_pair", "msg_id": msg.message_id}


def send_analise_gif(chat_id):
    if chat_id in user_state and "msg_id" in user_state[chat_id]:
        try:
            bot.delete_message(chat_id, user_state[chat_id]["msg_id"])
        except Exception:
            pass

    text = "🔍 Aguarde enquanto o Quantix está analisando o mercado..."
    try:
        with open(ANALISE_GIF, 'rb') as gif:
            bot.send_animation(chat_id, gif, caption=text, timeout=30)
    except Exception as e:
        print(f"❌ Erro enviando GIF analise.gif: {e}")

    user_state[chat_id]["stage"] = "analyzing"
    user_state[chat_id]["msg_id"] = None  # GIF não precisa de ID de mensagem


def send_sinal_msg(chat_id, coin_id, entry_time, direction, gale_time):
    if chat_id in user_state and "msg_id" in user_state[chat_id]:
        try:
            bot.delete_message(chat_id, user_state[chat_id]["msg_id"])
        except Exception:
            pass

    text = f"""
🚂 SINAL ENCONTRADO

━━━━━━━━━━━━━━━━━━
📊 Paridade: {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time}
🎯 Direção: {direction}
♻️ Gale 1: {gale_time}
    """
    msg = bot.send_message(chat_id, text)
    user_state[chat_id]["stage"] = "signal"
    user_state[chat_id]["msg_id"] = msg.message_id


def handle_gale1(chat_id, coin_id, direction, entry_time_dt):
    gale_time = (entry_time_dt + timedelta(minutes=1)).strftime("%H:%M")

    if chat_id in user_state and "msg_id" in user_state[chat_id]:
        try:
            bot.delete_message(chat_id, user_state[chat_id]["msg_id"])
        except Exception:
            pass

    text = f"""
❌ Loss na entrada, realizando Gale 1...
━━━━━━━━━━━━━━━━━━
📊 Paridade: {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time_dt.strftime("%H:%M")}
🎉 Gale 1: {gale_time}
🎯 Direção: {direction}
    """
    try:
        with open(LOSS_GIF, 'rb') as gif:
            bot.send_animation(chat_id, gif, caption="🔥 Entrando em Gale 1", timeout=30)
    except Exception:
        bot.send_message(chat_id, "🔥 Entrando em Gale 1")

    msg = bot.send_message(chat_id, text)
    user_state[chat_id]["stage"] = "gale1"
    user_state[chat_id]["msg_id"] = msg.message_id


def finalize_result(chat_id, coin_id, direction, entry_time, gale, status):
    if chat_id in user_state and "msg_id" in user_state[chat_id]:
        try:
            bot.delete_message(chat_id, user_state[chat_id]["msg_id"])
        except Exception:
            pass

    result_text = "WIN" if "WIN" in status else "LOSS"
    emoji = "✅" if "WIN" in status else "❌"
    is_gale = " (Gale 1)" if gale else ""

    text = f"""
🎯 RESULTADO FINAL{is_gale}

━━━━━━━━━━━━━━━━━━
📊 Paridade: {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time}
🎯 {direction}
🏆 {emoji} {result_text}
    """
    btn = telebot.types.InlineKeyboardButton("Gerar Novo Sinal", callback_data="new_signal")
    kb = telebot.types.InlineKeyboardMarkup().add(btn)

    if result_text == "WIN":
        path = WIN_GIF
    else:
        path = LOSS_GIF

    try:
        with open(path, 'rb') as gif:
            bot.send_animation(chat_id, gif, caption=text, reply_markup=kb, timeout=30)
    except Exception:
        bot.send_message(chat_id, text, reply_markup=kb)

    user_state[chat_id] = {"stage": "finished", "msg_id": None}


@bot.message_handler(commands=["start"])
def start_handler(m):
    start_menu(m.chat.id)


@bot.callback_query_handler(func=lambda c: c.data == "gen_signal")
def gen_signal(c):
    bot.answer_callback_query(c.id)
    menu_paridades(c.message.chat.id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("pair_"))
def choose_pair(c):
    bot.answer_callback_query(c.id)
    key = c.data.split("_")[1]
    coin_id = COIN_IDS[key]

    if c.message.chat.id not in user_state:
        user_state[c.message.chat.id] = {}

    user_state[c.message.chat.id]["coin_id"] = coin_id

    send_analise_gif(c.message.chat.id)

    def do_analyze():
        direction = analyze(coin_id)
        user_state[c.message.chat.id]["direction"] = direction

        now = datetime.now(BR_TZ)
        entry = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        entry_time = entry.strftime("%H:%M")
        gale_time = (entry + timedelta(minutes=1)).strftime("%H:%M")

        user_state[c.message.chat.id]["entry_time_dt"] = entry
        user_state[c.message.chat.id]["entry_time"] = entry_time

        send_sinal_msg(c.message.chat.id, coin_id, entry_time, direction, gale_time)

        threading.Thread(
            target=get_result,
            args=(c.message.chat.id, direction, coin_id, entry),
            daemon=True
        ).start()

    threading.Thread(target=do_analyze, daemon=True).start()


@bot.callback_query_handler(func=lambda c: c.data == "new_signal")
def new_signal(c):
    bot.answer_callback_query(c.id)
    start_menu(c.message.chat.id)


print("🚀 Quantix Cripto Pro Ativo (1m - 65s, múltiplas criptos, layout 100%)")
bot.remove_webhook()
time.sleep(2)
bot.infinity_polling()
