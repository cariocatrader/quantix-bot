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
        return "COMPRA" if closes[-1] > closes[-3] else "VENDA"
    except:
        return "COMPRA"

def get_candle_exact(symbol, target_time_str, interval="1m"):
    try:
        r = requests.get(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=50", timeout=10)
        data = r.json()
        
        print(f"🔍 Analisando {symbol} {target_time_str}")
        
        # SEMPRE usa a ÚLTIMA VELA FECHADA (penúltima da lista)
        if len(data) >= 2:
            last_closed_candle = data[-2]
            last_closed_ts = int(last_closed_candle[0])
            o = float(last_closed_candle[1])
            c = float(last_closed_candle[4])
            
            # Horário BR da vela
            candle_time = datetime.fromtimestamp(last_closed_ts/1000, tz=UTC_TZ).astimezone(BR_TZ).strftime("%H:%M")
            
            print(f"✅ ÚLTIMA VELA FECHADA {symbol}: {candle_time} O={o:.4f} C={c:.4f}")
            return o, c, candle_time
        
        print(f"❌ NENHUMA VELA {symbol}")
        return None, None, None
        
    except Exception as e:
        print(f"❌ ERRO {symbol}: {e}")
        return None, None, None

def get_result(symbol, direction, target_time_str, interval="1m"):
    o, c, actual_time = get_candle_exact(symbol, target_time_str, interval)
    
    if o is None or c is None:
        return None
    
    is_win = (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o)
    result = "WIN" if is_win else "LOSS"
    print(f"🏆 {symbol}: {actual_time} O={o:.4f} C={c:.4f} → {result}")
    return result

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

# UI - MESMO LAYOUT
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

def send_not_verified(chat_id, symbol_name, direction, entry_time):
    text = f"""
⚠️ ERRO DE VERIFICAÇÃO

━━━━━━━━━━━━━━━━━━
💱 {symbol_name}
⏱ {entry_time}
🎯 {direction}
📊 Sem dados do gráfico

Quantix Cripto ✨
"""
    bot.send_message(chat_id, text, reply_markup=final_btn())

def process_trade(chat_id, coin_id, direction, entry_time, exp, is_gale=False):
    def check():
        wait_time = 65 if exp == "1" else 310
        print(f"⏳ Aguardando {wait_time}s para {SYMBOLS[coin_id]}...")
        time.sleep(wait_time)
        
        symbol = BINANCE_SYMBOLS[coin_id]
        interval = "1m" if exp == "1" else "5m"
        
        for attempt in range(5):
            result = get_result(symbol, direction, entry_time, interval)
            if result is not None:
                break
            if attempt < 4:
                print(f"⏳ Tentativa {attempt+2}/5 - 10s...")
                time.sleep(10)
        
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
    except:
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
        'coin_id': coin_id, 'direction': direction,
        'entry_time': entry_time, 'gale_time': gale_time,
        'exp': exp, 'gale_active': False
    }
    
    process_trade(chat_id, coin_id, direction, entry_time, exp, False)

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
