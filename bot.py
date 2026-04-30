import telebot
import requests
import threading
import time
import os
import sys
import math
from datetime import datetime, timedelta
import pytz

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    sys.exit("❌ TOKEN não encontrado")

BR_TZ = pytz.timezone('America/Sao_Paulo')
UTC_TZ = pytz.timezone('UTC')

# GIFs LOCAIS do seu repositório
ANALYSIS_GIF = "analise.gif"
WIN_GIF = "win.gif"
LOSS_GIF = "loss.gif"

print(f"🚀 QUANTIX ATIVO {datetime.now(BR_TZ).strftime('%H:%M')}")

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

def get_br_time(format_str="%H:%M"):
    return datetime.now(BR_TZ).strftime(format_str)

def br_to_utc_timestamp(br_time_str):
    now_br = datetime.now(BR_TZ)
    br_dt = datetime.strptime(br_time_str, "%H:%M").replace(
        year=now_br.year, month=now_br.month, day=now_br.day,
        second=0, microsecond=0
    )
    return int(BR_TZ.localize(br_dt).astimezone(UTC_TZ).timestamp() * 1000)

def analyze(coin_id):
    try:
        r = requests.get(f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc?vs_currency=usd&days=2", timeout=8)
        closes = [c[4] for c in r.json()[-3:]]
        return "COMPRA" if closes[-1] > closes[-2] else "VENDA"
    except:
        return "COMPRA"

def get_binance_candle(symbol, br_time_str, interval="1m"):
    try:
        target_ts = br_to_utc_timestamp(br_time_str)
        r = requests.get(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=10", timeout=10)
        for candle in r.json():
            if int(candle[0]) == target_ts:
                return float(candle[1]), float(candle[4])
        return None
    except:
        return None

def get_result(symbol, direction, br_time_str, interval="1m"):
    result = get_binance_candle(symbol, br_time_str, interval)
    if not result:
        return "LOSS"
    o, c = result
    return "WIN" if (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o) else "LOSS"

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

# BOT
bot = telebot.TeleBot(TOKEN)

def send_result_final(chat_id, symbol_name, direction, result, entry_time, is_gale=False):
    status = "✅ WIN" if result == "WIN" else "❌ LOSS"
    gif_file = WIN_GIF if result == "WIN" else LOSS_GIF
    
    gale_text = " (Gale 1)" if is_gale else ""
    
    caption = f"""🎯 RESULTADO FINAL{gale_text}

━━━━━━━━━━━━━━━━━━
💱 {symbol_name}
⏱ {entry_time}
🎯 {direction}
🏆 {status}

Quantix Cripto ✨"""
    
    try:
        with open(gif_file, 'rb') as gif:
            bot.send_animation(chat_id, gif, caption=caption, reply_markup=final_btn())
    except:
        # Fallback se GIF falhar
        bot.send_message(chat_id, caption, reply_markup=final_btn())

def process_trade(chat_id, coin_id, direction, entry_time, exp, is_gale=False):
    def check():
        # Espera + 3s extras para resultado
        wait_time = (65 if exp == "1" else 305) + 3
        time.sleep(wait_time)
        
        symbol = BINANCE_SYMBOLS[coin_id]
        interval = "1m" if exp == "1" else "5m"
        result = get_result(symbol, direction, entry_time, interval)
        
        # SEMPRE envia resultado final
        send_result_final(chat_id, SYMBOLS[coin_id], direction, result, entry_time, is_gale)
        
        # Limpa estado
        if chat_id in user_state:
            del user_state[chat_id]
    
    threading.Thread(target=check, daemon=True).start()

def run_signal(chat_id, coin_id, exp):
    try:
        # GIF análise LOCAL
        try:
            with open(ANALYSIS_GIF, 'rb') as gif:
                bot.send_animation(chat_id, gif, caption=f"🔬 Analisando {SYMBOLS[coin_id]}...")
        except:
            bot.send_message(chat_id, f"🔬 Analisando {SYMBOLS[coin_id]}...")
        
        direction = analyze(coin_id)
        now = datetime.now(BR_TZ)
        if exp == "1":
            entry = now + timedelta(minutes=1)
        else:
            m = math.ceil(now.minute / 5) * 5
            entry = now.replace(minute=m, second=0, microsecond=0)
        
        entry_time = entry.strftime("%H:%M")
        
        bot.send_message(
            chat_id,
            f"""🎉 SINAL GERADO!

━━━━━━━━━━━━━━━━━━
💱 {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time}
🎯 {direction}

Aguardando resultado..."""
        )
        
        user_state[chat_id] = {'coin_id': coin_id, 'direction': direction, 'entry_time': entry_time, 'exp': exp, 'gale_count': 0}
        process_trade(chat_id, coin_id, direction, entry_time, exp, is_gale=False)
        
    except:
        pass

# GALE AUTOMÁTICO
def auto_gale(chat_id):
    if chat_id not in user_state:
        return
    
    state = user_state[chat_id]
    if state['gale_count'] >= 1:  # Máximo 1 gale
        return
    
    state['gale_count'] += 1
    coin_id = state['coin_id']
    direction = state['direction']
    entry_time = state['entry_time']
    exp = state['exp']
    
    # ENVIA MENSAGEM GALE AUTOMÁTICO
    bot.send_message(
        chat_id,
        f"""🔥 ENTRANDO EM GALE 1 AUTOMATICAMENTE!

━━━━━━━━━━━━━━━━━━
💱 {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time}
🎯 {direction}

Aguardando resultado do Gale..."""
    )
    
    process_trade(chat_id, coin_id, direction, entry_time, exp, is_gale=True)

# HANDLERS
@bot.message_handler(commands=["start"])
def start(message):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Gerar Sinal", callback_data="start"))
    bot.send_message(message.chat.id, "🤖 Quantix Cripto - Sinais Automáticos", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    try:
        bot.answer_callback_query(call.id)
        chat_id = call.message.chat.id
        
        if call.data in ["start", "new_signal"]:
            bot.edit_message_text("👇 Escolha a paridade:", chat_id, call.message.message_id, reply_markup=menu_paridades())
        elif call.data.startswith("par_"):
            coin_id = call.data.split("_")[1]
            bot.edit_message_text("⏰ Escolha expiração:", chat_id, call.message.message_id, reply_markup=menu_exp(coin_id))
        elif call.data.startswith("exp_"):
            parts = call.data.split("_")
            run_signal(chat_id, parts[1], parts[2])
            
    except:
        pass

# SOBRESCREVE RESULTADO PARA GALE AUTOMÁTICO
def send_result_final(chat_id, symbol_name, direction, result, entry_time, is_gale=False):
    status = "✅ WIN" if result == "WIN" else "❌ LOSS"
    gale_text = " (Gale 1)" if is_gale else ""
    
    caption = f"""🎯 RESULTADO FINAL{gale_text}

━━━━━━━━━━━━━━━━━━
💱 {symbol_name}
⏱ {entry_time}
🎯 {direction}
🏆 {status}

Quantix Cripto ✨"""
    
    gif_file = WIN_GIF if result == "WIN" else LOSS_GIF
    
    try:
        with open(gif_file, 'rb') as gif:
            bot.send_animation(chat_id, gif, caption=caption, reply_markup=final_btn())
    except:
        bot.send_message(chat_id, caption, reply_markup=final_btn())
    
    # SE LOSS E NÃO É GALE -> Inicia Gale AUTOMÁTICO
    if result == "LOSS" and not is_gale:
        time.sleep(1)  # Pequena pausa
        auto_gale(chat_id)

# START
try:
    requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")
    time.sleep(2)
    print("✅ Bot 100% operacional!")
    bot.infinity_polling(none_stop=True, interval=1, timeout=20)
except KeyboardInterrupt:
    print("\n👋 Bot finalizado")
except Exception as e:
    print(f"❌ Erro: {e}")
