import telebot
import requests
import threading
import time
import os
from datetime import datetime, timedelta, timezone
import pytz
import math
import random

# Configurações do bot
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise Exception("TOKEN não encontrado")
bot = telebot.TeleBot(TOKEN)

# Fuso horário Brasil
BR_TZ = pytz.timezone('America/Sao_Paulo')
UTC_TZ = pytz.timezone('UTC')

# === NOVAS APIs: COINGECKO + BYBIT (sem bloqueio 451) ===
COINGECKO_URL = "https://api.coingecko.com/api/v3"
BYBIT_URL = "https://api.bybit.com"

# GIFs locais (mantidos iguais)
ANALYSIS_GIF = "analise.gif"
WIN_GIF = "win.gif"
LOSS_GIF = "loss.gif"

def get_br_time(format_str="%H:%M"):
    return datetime.now(BR_TZ).strftime(format_str)

# Mapeamento de IDs da CoinGecko (mesmo que antes)
SYMBOLS = {
    "bitcoin": "₿ Bitcoin", "ethereum": "Ξ Ethereum", "binancecoin": "🟡 BNB",
    "solana": "🟣 Solana", "ripple": "💧 XRP", "cardano": "🔵 Cardano",
    "dogecoin": "🐶 Doge", "litecoin": "🪙 Litecoin",
    "polkadot": "⚫ Polkadot", "avalanche-2": "🔺 Avalanche"
}

# Map de símbolos Bybit para cada par
BYBIT_SYMBOLS = {
    "bitcoin": "BTCUSDT",
    "ethereum": "ETHUSDT",
    "binancecoin": "BNBUSDT",
    "solana": "SOLUSDT",
    "ripple": "XRPUSDT",
    "cardano": "ADAUSDT",
    "dogecoin": "DOGEUSDT",
    "litecoin": "LTCUSDT",
    "polkadot": "DOTUSDT",
    "avalanche-2": "AVAXUSDT",
}

user_state = {}

# === NOVA FUNÇÃO: pega dados de vela (1m ou 5m) via CoinGecko + Bybit fallback ===
def get_candle_cg(coin_id, days=1):
    """Pega OHLC de 1m da CoinGecko. Granularidade é automática."""
    try:
        endpoint = f"{COINGECKO_URL}/coins/{coin_id}/ohlc"
        params = {"vs_currency": "usd", "days": str(days)}  # 1 ou 2 dias
        r = requests.get(endpoint, params=params, timeout=15)
        if r.status_code != 200:
            print(f"❌ CoinGecko HTTP {r.status_code} para {coin_id}")
            return None
        data = r.json()
        if not data:
            return None
        # CoinGecko retorna lista de [timestamp_ms, open, high, low, close]
        last = data[-1]
        ts = last[0] / 1000
        o = float(last[1])
        c = float(last[4])
        return ts, o, c
    except Exception as e:
        print(f"❌ Erro CoinGecko {coin_id}: {str(e)[:50]}")
        return None

def get_candle_bybit(symbol, interval="1"):
    """Pega 1 candle fechado via Bybit (1m ou 5m)."""
    try:
        # calcula `from` como 60s atrás (para garantir vela fechada)
        now = int(datetime.now(tz=UTC_TZ).timestamp())
        if interval == "1":
            from_ts = now - 60
        else:
            from_ts = now - 300

        params = {
            "category": "spot",
            "symbol": symbol,
            "interval": interval,
            "start": from_ts * 1000,
            "end": now * 1000,
            "limit": 1
        }
        r = requests.get(f"{BYBIT_URL}/v5/market/kline", params=params, timeout=15)
        if r.status_code != 200:
            print(f"❌ Bybit HTTP {r.status_code} para {symbol}")
            return None
        j = r.json()
        if not j.get("retCode") == 0:
            return None
        data = j["result"]["list"]
        if not data:
            return None
        row = data[0]
        ts = int(row[0]) / 1000
        o = float(row[1])
        c = float(row[4])
        return ts, o, c
    except Exception as e:
        print(f"❌ Erro Bybit {symbol}: {str(e)[:50]}")
        return None

def get_candle_exact(coin_id, exp="1"):
    """
    Tenta:
    1) CoinGecko (1m)
    2) Bybit (1m ou 5m)
    Retorna: open, close, time_br
    """
    symbol = BYBIT_SYMBOLS.get(coin_id)
    if not symbol:
        return None, None, None

    interval = "1" if exp == "1" else "5"

    # Tentar CoinGecko primeiro
    for _ in range(2):  # 2 tentativas
        result = get_candle_cg(coin_id, days=1)
        if result:
            ts, o, c = result
            dt = datetime.fromtimestamp(ts, tz=UTC_TZ).astimezone(BR_TZ)
            candle_time = dt.strftime("%H:%M")
            print(f"✅ CG Vela {coin_id}: {candle_time} O={o:.4f} C={c:.4f}")
            return o, c, candle_time

    # Fallback: Bybit
    for _ in range(2):
        result = get_candle_bybit(symbol, interval)
        if result:
            ts, o, c = result
            dt = datetime.fromtimestamp(ts, tz=UTC_TZ).astimezone(BR_TZ)
            candle_time = dt.strftime("%H:%M")
            print(f"✅ Bybit Vela {symbol}: {candle_time} O={o:.4f} C={c:.4f}")
            return o, c, candle_time

    print(f"❌ FALHOU CoinGecko + Bybit para {coin_id}")
    return None, None, None

# === MANTIDO SEM MUDANÇA: lógica de análise de entrada (agora usa apenas CoinGecko/Bybit) ===
def analyze(coin_id):
    try:
        # 5 velas fechadas recentes (1m)
        closes = []
        for _ in range(5):
            o, c, _ = get_candle_exact(coin_id, "1")
            if o is None:
                time.sleep(0.5)
                continue
            closes.append(c)
            time.sleep(0.3)
        if len(closes) < 5:
            return "COMPRA"
        return "COMPRA" if closes[-1] > closes[-3] else "VENDA"
    except:
        return "COMPRA"

def get_result(coin_id, direction):
    o, c, actual_time = get_candle_exact(coin_id, "1")
    if o is None or c is None:
        return None
    is_win = (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o)
    result = "WIN" if is_win else "LOSS"
    print(f"🏆 {SYMBOLS[coin_id]}: {actual_time} O={o:.4f} C={c:.4f} → {result}")
    return result

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

# === UI FUNCTIONS (mantidas EXATAMENTE iguais) ===
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
📡 APIs (CoinGecko/Bybit) indisponíveis

Quantix Cripto ✨
"""
    bot.send_message(chat_id, text, reply_markup=final_btn())

def process_trade(chat_id, coin_id, direction, entry_time, exp, is_gale=False):
    def check():
        wait_time = 65 if exp == "1" else 310
        print(f"⏳ Aguardando {wait_time}s para {SYMBOLS[coin_id]}...")
        time.sleep(wait_time)

        result = get_result(coin_id, direction)

        if result is None:
            send_not_verified(chat_id, SYMBOLS[coin_id], direction, entry_time)
            return

        send_result_final(chat_id, SYMBOLS[coin_id], direction, result, entry_time, is_gale)

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
    process_trade(chat_id, state['coin_id'], state['direction'], state['gale_time'], state['exp'], True)

def run_signal(chat_id, coin_id, exp):
    try:
        with open(ANALYSIS_GIF, 'rb') as gif:
            msg = bot.send_animation(chat_id, gif, caption=f"🔬 Analisando {SYMBOLS[coin_id]}...")
            msg_id = msg.message_id
    except Exception as e:
        print(f"❌ Erro GIF: {e}")
        msg = bot.send_message(chat_id, f"🔬 Analisando {SYMBOLS[coin_id]}...")
        msg_id = msg.message_id

    direction = analyze(coin_id)
    entry_time, gale_time = get_next_times(exp)

    try:
        bot.delete_message(chat_id, msg_id)
    except:
        pass

    text = f"""
🎉 SINAL GERADO!

━━━━━━━━━━━━━━━━━━━
💱 {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time}
🔥 Gale 1: {gale_time}
🎯 {direction}

Aguardando resultado...
"""
    bot.send_message(chat_id, text)

    user_state[chat_id] = {
        'coin_id': coin_id,
        'direction': direction,
        'entry_time': entry_time,
        'gale_time': gale_time,
        'exp': exp,
        'gale_active': False
    }

    process_trade(chat_id, coin_id, direction, entry_time, exp, False)

# === HANDLERS TELEGRAM (iguais) ===
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

print(f"🚀 QUANTIX ATIVO {get_br_time()} - Usando CoinGecko + Bybit")
bot.remove_webhook()
time.sleep(2)
bot.infinity_polling()
