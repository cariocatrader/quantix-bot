import telebot
import requests
import threading
import time
import os
from datetime import datetime, timedelta
import pytz
import math

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise Exception("TOKEN não encontrado")

bot = telebot.TeleBot(TOKEN)

BR_TZ = pytz.timezone('America/Sao_Paulo')
UTC_TZ = pytz.timezone('UTC')

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

BINANCE_SYMBOLS = {
    "bitcoin": "BTCUSDT", "ethereum": "ETHUSDT", "binancecoin": "BNBUSDT",
    "solana": "SOLUSDT", "ripple": "XRPUSDT", "cardano": "ADAUSDT",
    "dogecoin": "DOGEUSDT", "litecoin": "LTCUSDT",
    "polkadot": "DOTUSDT", "avalanche-2": "AVAXUSDT"
}

user_state = {}
message_ids = {}

def br_to_utc_timestamp(br_time_str):
    now_br = datetime.now(BR_TZ)
    br_dt = datetime.strptime(br_time_str, "%H:%M").replace(
        year=now_br.year, month=now_br.month, day=now_br.day,
        second=0, microsecond=0
    )
    return int(BR_TZ.localize(br_dt).astimezone(UTC_TZ).timestamp() * 1000)

def analyze(coin_id):
    try:
        symbol = BINANCE_SYMBOLS[coin_id]
        r = requests.get(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=10", timeout=10)
        data = r.json()
        closes = [float(c[4]) for c in data[-5:]]
        # Simples: último > antepenúltimo
        return "COMPRA" if closes[-1] > closes[-3] else "VENDA"
    except:
        return "COMPRA"

def get_candle_exact(symbol, target_time_str, interval="1m"):
    try:
        target_ts = br_to_utc_timestamp(target_time_str)
        r = requests.get(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=30", timeout=10)
        data = r.json()
        
        for candle in data:
            candle_ts = int(candle[0])
            if abs(candle_ts - target_ts) <= 30000:  # ±30s tolerância
                o = float(candle[1])
                c = float(candle[4])
                print(f"✅ VELA {symbol} {target_time_str}: O={o} C={c}")
                return o, c
        
        # Última fechada como fallback
        if len(data) >= 2:
            candle = data[-2]
            o, c = float(candle[1]), float(candle[4])
            print(f"📈 FALLBACK {symbol}: O={o} C={c}")
            return o, c
            
        return None, None
    except:
        return None, None

def get_result(symbol, direction, target_time_str, interval="1m"):
    o, c = get_candle_exact(symbol, target_time_str, interval)
    if o is None:
        print(f"⚠️ Sem vela {symbol}")
        return "LOSS"
    
    is_win = (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o)
    print(f"🏆 {symbol}: O={o} C={c} → {'WIN' if is_win else 'LOSS'}")
    return "WIN" if is_win else "LOSS"

def get_next_times(exp):
    now = datetime.now(BR_TZ)
    if exp == "1":
        entry = (now + timedelta(minutes=1)).replace(second=0)
        gale = entry + timedelta(minutes=1)
    else:
        m = math.ceil(now.minute / 5.0) * 5
        entry = now.replace(minute=int(m), second=0)
        if entry <= now:
            entry += timedelta(hours=1)
        gale = entry + timedelta(minutes=5)
    return entry.strftime("%H:%M"), gale.strftime("%H:%M")

# UI - MESMO LAYOUT ORIGINAL
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
    except:
        bot.send_message(chat_id, text, reply_markup=final_btn())

def process_trade(chat_id, coin_id, direction, entry_time, exp, is_gale=False):
    def check():
        wait = 68 if exp == "1" else 308  # +8s margem
        time.sleep(wait)
        
        symbol = BINANCE_SYMBOLS[coin_id]
        interval = "1m" if exp == "1" else "5m"
        result = get_result(symbol, direction, entry_time, interval)
        
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
    # GIF análise
    try:
        with open(ANALYSIS_GIF, 'rb') as gif:
            msg = bot.send_animation(chat_id, gif, caption=f"🔬 Analisando {SYMBOLS[coin_id]}...")
            msg_id = msg.message_id
    except:
        msg = bot.send_message(chat_id, f"🔬 Analisando {SYMBOLS[coin_id]}...")
        msg_id = msg.message_id
    
    # Análise
    direction = analyze(coin_id)
    entry_time, gale_time = get_next_times(exp)
    
    # APAGA análise
    try:
        bot.delete_message(chat_id, msg_id)
    except:
        pass
    
    # SINAL c/ horários
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
        'coin_id': coin_id, 'direction': direction,
        'entry_time': entry_time, 'gale_time': gale_time,
        'exp': exp, 'gale_active': False
    }
    
    process_trade(chat_id, coin_id, direction, entry_time, exp, False)

# HANDLERS - MESMO LAYOUT ORIGINAL
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

print(f"🚀 QUANTIX ATIVO {get_br_time()}")
bot.remove_webhook()
time.sleep(2)
bot.infinity_polling()
