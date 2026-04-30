import telebot
import requests
import threading
import time
import os
from datetime import datetime, timedelta, timezone
import pytz
import math
import random

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise Exception("TOKEN não encontrado")

bot = telebot.TeleBot(TOKEN)

BR_TZ = pytz.timezone('America/Sao_Paulo')
UTC_TZ = pytz.timezone('UTC')

# === COINGECKO (única API agora) ===
COINGECKO_URL = "https://api.coingecko.com/api/v3"

# GIFs locais
ANALYSIS_GIF = "analise.gif"
WIN_GIF = "win.gif"
LOSS_GIF = "loss.gif"

def get_br_time(format_str="%H:%M"):
    return datetime.now(BR_TZ).strftime(format_str)

SYMBOLS = {
    "bitcoin": "₿ Bitcoin", "ethereum": "Ξ Ethereum", "binancecoin": "🟡 BNB",
    "solana": "🟣 Solana", "ripple": "💧 XRP", "cardano": "🔵 Cardano",
    "dogecoin": "🐶 Doge", "litecoin": "🪙 Litecoin",
    "polkadot": "⚫ Polkadot", "avalanche-2": "🔺 Avalanche"
}

user_state = {}

# === ANALISE INICIAL (1m) ===
def get_candle_cg(coin_id, days=2):
    try:
        endpoint = f"{COINGECKO_URL}/coins/{coin_id}/ohlc"
        params = {"vs_currency": "usd", "days": str(days)}
        r = requests.get(endpoint, params=params, timeout=15)
        if r.status_code != 200:
            print(f"❌ CoinGecko HTTP {r.status_code} para {coin_id}")
            return None
        data = r.json()
        if not data:
            return None
        last = data[-1]
        ts = last[0] / 1000  # timestamp de fechamento
        o = float(last[1])
        c = float(last[4])
        return ts, o, c
    except Exception as e:
        print(f"❌ Erro CoinGecko {coin_id}: {str(e)[:50]}")
        return None

def analyze(coin_id):
    """
    Usa 5 velas recentes (até 2 dias) para definir COMPRA/VENDA.
    """
    closes = []
    for _ in range(5):
        result = get_candle_cg(coin_id, days=2)
        if not result:
            time.sleep(0.5)
            continue
        ts, o, c = result
        closes.append(c)
        time.sleep(0.3)
    if len(closes) < 5:
        return "COMPRA"
    return "COMPRA" if closes[-1] > closes[-3] else "VENDA"

# === FUNÇÃO PARA BUSCAR O CANDLE EXATO DO HORÁRIO DE ENTRADA ===
def get_candle_exact_by_time(coin_id, target_time_dt):
    """
    Tenta pegar o candle exatamente do minuto de target_time_dt (BR_TZ).
    Verifica se o candle de fechamento bate com o mesmo minuto/hora.
    """
    try:
        # 1) CoinGecko: busca 2 dias e percorre de trás para frente
        endpoint = f"{COINGECKO_URL}/coins/{coin_id}/ohlc"
        params = {"vs_currency": "usd", "days": "2"}
        r = requests.get(endpoint, params=params, timeout=15)
        if r.status_code != 200:
            print(f"❌ CoinGecko HTTP {r.status_code} para {coin_id} (by_time)")
            return None, None, None
        data = r.json()
        if not data:
            return None, None, None

        # CoinGecko retorna [ts_ms, open, high, low, close]
        for i in range(len(data)-1, max(-1, len(data)-100), -1):
            row = data[i]
            ts = row[0] / 1000
            o = float(row[1])
            c = float(row[4])
            candle_dt = datetime.fromtimestamp(ts, tz=UTC_TZ).astimezone(BR_TZ)
            # Se o candle acabou no mesmo minuto que o horário de entrada
            if (candle_dt.hour == target_time_dt.hour and
                candle_dt.minute == target_time_dt.minute):
                candle_time = candle_dt.strftime("%H:%M")
                print(f"✅ CG Vela {coin_id} {candle_time} O={o:.4f} C={c:.4f}")
                return o, c, candle_time

    except Exception as e:
        print(f"❌ Erro busca candle exato {coin_id}: {str(e)[:50]}")

    return None, None, None

def get_result(coin_id, direction, entry_time_dt):
    """
    Avalia WIN/LOSS apenas no candle que corresponde ao horário de entrada.
    """
    o, c, actual_time = get_candle_exact_by_time(coin_id, entry_time_dt)
    if o is None or c is None:
        return None
    is_win = (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o)
    result = "WIN" if is_win else "LOSS"
    print(f"🏆 {SYMBOLS[coin_id]}: {actual_time} O={o:.4f} C={c:.4f} → {result}")
    return result

# === TEMPO DE ENTRADA/GALE (1m ou 5m) ===
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

# === UI FUNCTIONS (iguais) ===
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

def send_result_final(chat_id, symbol_name, direction, result, entry_time, is_gale=False):
    status = "✅ WIN" if result == "WIN" else "❌ LOSS"
    gale_text = " (Gale 1)" if is_gale else ""

    text = f"""
🎯 RESULTADO FINAL{gale_text}

━━━━━━━━━━━━━━━━━━
💱 {symbol_name}
⏱ {entry_time}
🎯 {direction}
🏆 {status}

Quantix Cripto ✨
"""

    try:
        gif_file = WIN_GIF if result == "WIN" else LOSS_GIF
        with open(gif_file, 'rb') as gif:
            bot.send_animation(chat_id, gif, caption=text, reply_markup=final_btn())
    except Exception as e:
        print(f"❌ Erro envio GIF: {e}")
        bot.send_message(chat_id, text, reply_markup=final_btn())

def send_not_verified(chat_id, symbol_name, direction, entry_time):
    text = f"""
⚠️ ERRO DE CONEXÃO

━━━━━━━━━━━━━━━━━━
💱 {symbol_name}
⏱ {entry_time}
🎯 {direction}
📡 API CoinGecko indisponível

Quantix Cripto ✨
"""
    bot.send_message(chat_id, text, reply_markup=final_btn())

def process_trade(chat_id, coin_id, direction, entry_time_dt, exp, is_gale=False):
    """
    Só avalia o resultado APÓS o candle de entrada fechar no gráfico.
    """
    def check():
        wait_time = 65 if exp == "1" else 310
        entry_time_str = entry_time_dt.strftime("%H:%M")
        print(f"⏳ Aguardando {wait_time}s para {SYMBOLS[coin_id]} (entrada {entry_time_str})...")
        time.sleep(wait_time)

        result = get_result(coin_id, direction, entry_time_dt)

        if result is None:
            send_not_verified(chat_id, SYMBOLS[coin_id], direction, entry_time_str)
            return

        send_result_final(chat_id, SYMBOLS[coin_id], direction, result, entry_time_str, is_gale)

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
    bot.send_message(
        chat_id,
        f"""
🔥 ENTRANDO EM GALE 1!

━━━━━━━━━━━━━━━━━━
💱 {SYMBOLS[state['coin_id']]}
⏱ {state['gale_time']}
🎯 {state['direction']}

Aguardando...
        """
    )
    # dummy: gale usa o mesmo exp (1m/5m) do sinal original
    process_trade(chat_id, state['coin_id'], state['direction'], state['gale_time_dt'], state['exp'], True)

def run_signal(chat_id, coin_id, exp):
    entry_time_str, gale_time_str = get_next_times(exp)
    entry_time_dt = BR_TZ.localize(datetime.strptime(entry_time_str, "%H:%M"))
    gale_time_dt = BR_TZ.localize(datetime.strptime(gale_time_str, "%H:%M"))

    try:
        with open(ANALYSIS_GIF, 'rb') as gif:
            msg = bot.send_animation(chat_id, gif, caption=f"🔬 Analisando {SYMBOLS[coin_id]}...")
            msg_id = msg.message_id
    except Exception as e:
        print(f"❌ Erro GIF: {e}")
        msg = bot.send_message(chat_id, f"🔬 Analisando {SYMBOLS[coin_id]}...")
        msg_id = msg.message_id

    direction = analyze(coin_id)

    try:
        bot.delete_message(chat_id, msg_id)
    except:
        pass

    text = f"""
🎉 SINAL GERADO!

━━━━━━━━━━━━━━━━━━━
💱 {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time_str}
🔥 Gale 1: {gale_time_str}
🎯 {direction}

Aguardando resultado...
"""
    bot.send_message(chat_id, text)

    user_state[chat_id] = {
        'coin_id': coin_id,
        'direction': direction,
        'entry_time': entry_time_str,
        'gale_time': gale_time_str,
        'exp': exp,
        'gale_active': False,
        'entry_time_dt': entry_time_dt,
        'gale_time_dt': gale_time_dt   # gale também é tratado como candle real
    }

    process_trade(chat_id, coin_id, direction, entry_time_dt, exp, False)

# === HANDLERS TELEGRAM ===
@bot.message_handler(commands=["start"])
def start(m):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Gerar Sinal", callback_data="start"))
    bot.send_message(m.chat.id, "🤖 Quantix Cripto", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "start")
def start_flow(c):
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id, "Escolha paridade:", reply_markup=menu_paridades())

@bot.callback_query_handler(func=lambda c: c.data.startswith("par_"))
def paridade(c):
    coin_id = c.data.split("_")[1]
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id, "Escolha expiração:", reply_markup=menu_exp(coin_id))

@bot.callback_query_handler(func=lambda c: c.data.startswith("exp_"))
def exp_handler(c):
    parts = c.data.split("_")
    bot.answer_callback_query(c.id)
    run_signal(c.message.chat.id, parts[1], parts[2])

@bot.callback_query_handler(func=lambda c: c.data == "new_signal")
def new_signal(c):
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id, "Escolha paridade:", reply_markup=menu_paridades())

print(f"🚀 QUANTIX ATIVO {get_br_time()} - Usando apenas CoinGecko (candle exato)")
bot.remove_webhook()
time.sleep(2)
bot.infinity_polling()
