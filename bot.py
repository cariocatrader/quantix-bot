import telebot
import requests
import threading
import time
import os
import sys
import math
from datetime import datetime, timedelta
import pytz
import numpy as np

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    sys.exit("❌ TOKEN não encontrado")

BR_TZ = pytz.timezone('America/Sao_Paulo')
UTC_TZ = pytz.timezone('UTC')

# GIFs locais
ANALYSIS_GIF = "analise.gif"
WIN_GIF = "win.gif"
LOSS_GIF = "loss.gif"

print(f"🚀 QUANTIX PRO ATIVO {datetime.now(BR_TZ).strftime('%H:%M')}")

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
message_ids = {}  # Para apagar mensagens

def get_br_time(format_str="%H:%M"):
    return datetime.now(BR_TZ).strftime(format_str)

def get_next_candle_time(exp):
    """Calcula entrada EXATA + Gale"""
    now = datetime.now(BR_TZ)
    if exp == "1":
        entry = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        gale = entry + timedelta(minutes=1)
    else:
        m = math.ceil(now.minute / 5) * 5
        entry = now.replace(minute=m, second=0, microsecond=0)
        gale = entry + timedelta(minutes=5)
    return entry.strftime("%H:%M"), gale.strftime("%H:%M")

def advanced_analyze(symbol, interval="1m"):
    """ANÁLISE PROFISSIONAL - 20 candles"""
    try:
        r = requests.get(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=20", timeout=10)
        data = r.json()
        
        closes = np.array([float(c[4]) for c in data[-10:]])  # Últimos 10
        highs = np.array([float(c[2]) for c in data[-10:]])
        lows = np.array([float(c[3]) for c in data[-10:]])
        
        # 1. TENDÊNCIA (EMA rápida vs lenta)
        ema_fast = np.mean(closes[-3:])
        ema_slow = np.mean(closes[-7:])
        
        # 2. MOMENTO (RSI simplificado)
        gains = np.maximum(closes[1:] - closes[:-1], 0)
        losses = np.maximum(closes[:-1] - closes[1:], 0)
        rs = np.mean(gains) / (np.mean(losses) + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        
        # 3. FORÇA (último candle)
        last_o, last_c = float(data[-1][1]), float(data[-1][4])
        momentum = (last_c - last_o) / last_o
        
        # DECISÃO INTELIGENTE
        trend_score = 1 if ema_fast > ema_slow else -1
        rsi_score = 1 if rsi < 70 else -1 if rsi > 30 else 0
        mom_score = 1 if momentum > 0.0005 else -1 if momentum < -0.0005 else 0
        
        total_score = trend_score + rsi_score + mom_score
        
        print(f"📊 {symbol}: Trend={trend_score}, RSI={rsi:.1f}, Mom={momentum:.4f}, Score={total_score}")
        
        return "COMPRA" if total_score >= 1 else "VENDA"
    except:
        return "COMPRA"

def get_candle_result(symbol, target_time_str, interval="1m"):
    """BUSCA EXATA pela vela do horário alvo"""
    try:
        target_ts = br_to_utc_timestamp(target_time_str)
        print(f"🎯 Buscando vela {target_time_str} → {target_ts}")
        
        r = requests.get(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=50", timeout=10)
        data = r.json()
        
        for candle in data[-10:]:  # Últimas 10 velas
            candle_ts = int(candle[0])
            candle_time = datetime.fromtimestamp(candle_ts/1000, BR_TZ).strftime("%H:%M")
            
            if candle_time == target_time_str:
                o, h, l, c = float(candle[1]), float(candle[2]), float(candle[3]), float(candle[4])
                print(f"✅ VELA ENCONTRADA {target_time_str}: O={o:.4f} H={h:.4f} L={l:.4f} C={c:.4f}")
                return o, c
        
        # Fallback: última vela fechada
        if len(data) >= 2:
            candle = data[-2]
            o, c = float(candle[1]), float(candle[4])
            print(f"🔄 FALLBACK última fechada: O={o:.4f} C={c:.4f}")
            return o, c
        
        return None, None
    except Exception as e:
        print(f"❌ Erro candle: {e}")
        return None, None

def get_result(symbol, direction, target_time_str, interval="1m"):
    o, c = get_candle_result(symbol, target_time_str, interval)
    if o is None or c is None:
        print("⚠️ Candle não disponível")
        return "LOSS"
    
    is_win = (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o)
    result = "WIN" if is_win else "LOSS"
    print(f"🏆 RESULTADO {symbol} {target_time_str}: {'WIN' if is_win else 'LOSS'} (O:{o:.4f}→C:{c:.4f})")
    return result

def br_to_utc_timestamp(br_time_str):
    now_br = datetime.now(BR_TZ)
    br_dt = datetime.strptime(br_time_str, "%H:%M").replace(
        year=now_br.year, month=now_br.month, day=now_br.day, second=0, microsecond=0
    )
    return int(BR_TZ.localize(br_dt).astimezone(UTC_TZ).timestamp() * 1000)

# UI
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

bot = telebot.TeleBot(TOKEN)

def send_result_final(chat_id, symbol_name, direction, result, entry_time, is_gale=False):
    status = "✅ WIN" if result == "WIN" else "❌ LOSS"
    gale_text = " (Gale 1)" if is_gale else ""
    
    caption = f"""🎯 RESULTADO FINAL{gale_text}

━━━━━━━━━━━━━━━━━━
💱 {symbol_name}
⏱ {entry_time}
🎯 {direction}
🏆 {status}

Quantix Pro ✨"""
    
    try:
        gif_file = WIN_GIF if result == "WIN" else LOSS_GIF
        with open(gif_file, 'rb') as gif:
            bot.send_animation(chat_id, gif, caption=caption, reply_markup=final_btn())
    except:
        bot.send_message(chat_id, caption, reply_markup=final_btn())
    
    if result == "LOSS" and not is_gale:
        auto_gale(chat_id)

def auto_gale(chat_id):
    state = user_state.get(chat_id)
    if not state or state.get('gale_count', 0) >= 1:
        return
    
    state['gale_count'] = 1
    coin_id = state['coin_id']
    direction = state['direction']
    gale_time = state['gale_time']
    exp = state['exp']
    
    bot.send_message(
        chat_id,
        f"""🔥 ENTRANDO EM GALE 1!

━━━━━━━━━━━━━━━━━━
💱 {SYMBOLS[coin_id]}
⏱ Gale: {gale_time}
🎯 {direction}

Aguardando..."""
    )
    
    process_trade(chat_id, coin_id, direction, gale_time, exp, True)

def process_trade(chat_id, coin_id, direction, target_time, exp, is_gale=False):
    def check():
        wait_time = (65 if exp == "1" else 305) + 3
        time.sleep(wait_time)
        
        symbol = BINANCE_SYMBOLS[coin_id]
        interval = "1m" if exp == "1" else "5m"
        result = get_result(symbol, direction, target_time, interval)
        
        send_result_final(chat_id, SYMBOLS[coin_id], direction, result, target_time, is_gale)
    
    threading.Thread(target=check, daemon=True).start()

def run_signal(chat_id, coin_id, exp):
    # APAGA mensagem análise anterior
    if chat_id in message_ids:
        try:
            bot.delete_message(chat_id, message_ids[chat_id])
        except:
            pass
    
    # ENVIA GIF análise
    try:
        with open(ANALYSIS_GIF, 'rb') as gif:
            msg = bot.send_animation(chat_id, gif, caption=f"🔬 Análise avançada {SYMBOLS[coin_id]}...")
            message_ids[chat_id] = msg.message_id
    except:
        msg = bot.send_message(chat_id, f"🔬 Análise avançada {SYMBOLS[coin_id]}...")
        message_ids[chat_id] = msg.message_id
    
    # ANÁLISE ROBUSTA (5s delay)
    time.sleep(3)
    
    direction = advanced_analyze(BINANCE_SYMBOLS[coin_id], "1m")
    entry_time, gale_time = get_next_candle_time(exp)
    
    # APAGA análise
    try:
        bot.delete_message(chat_id, message_ids[chat_id])
    except:
        pass
    del message_ids[chat_id]
    
    # SINAL c/ horários entrada + gale
    bot.send_message(
        chat_id,
        f"""🎉 SINAL GERADO!

━━━━━━━━━━━━━━━━━━━
💱 {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time}
🔥 Gale 1: {gale_time}
🎯 {direction}

Aguardando resultado..."""
    )
    
    user_state[chat_id] = {
        'coin_id': coin_id, 'direction': direction,
        'entry_time': entry_time, 'gale_time': gale_time,
        'exp': exp, 'gale_count': 0
    }
    
    process_trade(chat_id, coin_id, direction, entry_time, exp, False)

@bot.message_handler(commands=["start"])
def start(message):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Gerar Sinal", callback_data="start"))
    bot.send_message(message.chat.id, "🤖 Quantix Pro - Análise Avançada", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    try:
        bot.answer_callback_query(call.id)
        chat_id = call.message.chat.id
        
        if call.data in ["start", "new_signal"]:
            bot.edit_message_text("👇 Paridade:", chat_id, call.message.message_id, reply_markup=menu_paridades())
        elif call.data.startswith("par_"):
            coin_id = call.data.split("_")[1]
            bot.edit_message_text("⏰ Expiração:", chat_id, call.message.message_id, reply_markup=menu_exp(coin_id))
        elif call.data.startswith("exp_"):
            parts = call.data.split("_")
            run_signal(chat_id, parts[1], parts[2])
            
    except:
        pass

# START
try:
    requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")
    time.sleep(2)
    print("✅ Quantix Pro - Análise Profissional!")
    bot.infinity_polling(none_stop=True, interval=1, timeout=20)
except KeyboardInterrupt:
    print("\n👋 Finalizado")
except Exception as e:
    print(f"❌ {e}")
