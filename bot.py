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

print(f"🚀 QUANTIX ATIVO {datetime.now(BR_TZ).strftime('%H:%M')}")

# ===== CONFIGS =====
ANALYSIS_GIF = "https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif"
WIN_GIF = "https://media.giphy.com/media/l0HlRnAWXxn0MhKLK/giphy.gif"
LOSS_GIF = "https://media.giphy.com/media/26ufnwz3wDUllqRxC/giphy.gif"

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

# ===== FUNÇÕES =====
def get_br_time(format_str="%H:%M"):
    return datetime.now(BR_TZ).strftime(format_str)

def br_to_utc_timestamp(br_time_str):
    now_br = datetime.now(BR_TZ)
    br_dt = datetime.strptime(br_time_str, "%H:%M").replace(
        year=now_br.year, month=now_br.month, day=now_br.day, second=0, microsecond=0
    )
    return int(BR_TZ.localize(br_dt).astimezone(UTC_TZ).timestamp() * 1000)

def analyze(coin_id):
    try:
        r = requests.get(f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc?vs_currency=usd&days=2", timeout=8)
        closes = [c[4] for c in r.json()[-3:]]
        return "COMPRA" if closes[-1] > closes[-2] else "VENDA"
    except: return "COMPRA"

def get_binance_candle(symbol, br_time_str, interval="1m"):
    try:
        target_ts = br_to_utc_timestamp(br_time_str)
        r = requests.get(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=10", timeout=10)
        for candle in r.json():
            if int(candle[0]) == target_ts:
                return float(candle[1]), float(candle[4])
        return None
    except: return None

def get_result(symbol, direction, br_time_str, interval="1m"):
    result = get_binance_candle(symbol, br_time_str, interval)
    if not result: return "LOSS"
    o, c = result
    return "WIN" if (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o) else "LOSS"

# ===== UI =====
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

def gale_menu(coin_id, direction, entry_time):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton(f"🔥 GALE 1 - {direction} {entry_time}", callback_data=f"gale1_{coin_id}_{direction}_{entry_time}"))
    kb.add(telebot.types.InlineKeyboardButton("⏭️ Pular Gale", callback_data="skip_gale"))
    return kb

def final_btn():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Gerar Novo Sinal", callback_data="new_signal"))
    return kb

# ===== BOT =====
bot = telebot.TeleBot(TOKEN)

def send_result_final(chat_id, symbol_name, direction, result, entry_time):
    status = "✅ WIN" if result == "WIN" else "❌ LOSS"
    gif_url = WIN_GIF if result == "WIN" else LOSS_GIF
    try:
        bot.send_animation(
            chat_id, gif_url,
            caption=f"""🎯 RESULTADO FINAL
━━━━━━━━━━━━━━━━━━
💱 {symbol_name}
⏱ {entry_time}
🎯 {direction}
🏆 {status}

Quantix Cripto ✨""",
            reply_markup=final_btn()
        )
    except: pass
    user_state[chat_id] = None

def process_trade(chat_id, coin_id, direction, entry_time, exp):
    def check():
        time.sleep(65 if exp == "1" else 305)
        result = get_result(BINANCE_SYMBOLS[coin_id], direction, entry_time, "1m" if exp == "1" else "5m")
        if result == "WIN":
            send_result_final(chat_id, SYMBOLS[coin_id], direction, result, entry_time)
        else:
            bot.send_message(
                chat_id,
                f"""❌ LOSS Detectado!

🔥 GALE 1 Disponível
💱 {SYMBOLS[coin_id]}
⏱ {entry_time}
🎯 {direction}

Deseja entrar no Gale 1?""",
                reply_markup=gale_menu(coin_id, direction, entry_time)
            )
            user_state[chat_id] = {'coin_id': coin_id, 'direction': direction, 'entry_time': entry_time, 'exp': exp}
    threading.Thread(target=check, daemon=True).start()

def run_signal(chat_id, coin_id, exp):
    bot.send_animation(chat_id, ANALYSIS_GIF, caption=f"🔬 Analisando {SYMBOLS[coin_id]}...")
    direction = analyze(coin_id)
    now = datetime.now(BR_TZ)
    entry = now + timedelta(minutes=1) if exp == "1" else now.replace(minute=math.ceil(now.minute / 5) * 5)
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
    user_state[chat_id] = {'coin_id': coin_id, 'direction': direction, 'entry_time': entry_time, 'exp': exp}
    process_trade(chat_id, coin_id, direction, entry_time, exp)

# ===== HANDLERS =====
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "🤖 Quantix Cripto - Bot de Sinais Cripto",
        reply_markup=telebot.types.InlineKeyboardMarkup().add(
            telebot.types.InlineKeyboardButton("🚀 Gerar Sinal", callback_data="start")
        )
    )

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
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
        elif call.data.startswith("gale1_"):
            parts = call.data.split("_")
            coin_id = parts[1]
            direction = parts[2]
            entry_time = parts[3]
            bot.edit_message_text(f"🔥 GALE 1 ATIVADO!\n{SYMBOLS[coin_id]} {direction} {entry_time}", chat_id, call.message.message_id)
            exp = user_state.get(chat_id, {}).get('exp', '1')
            process_trade(chat_id, coin_id, direction, entry_time, exp)
        elif call.data == "skip_gale":
            bot.edit_message_text("⏭️ Gale pulado com sucesso!", chat_id, call.message.message_id, reply_markup=final_btn())
    except Exception as e:
        pass

# ===== START SEGURO =====
try:
    bot.remove_webhook(drop_pending_updates=True)
    print("✅ Bot iniciado com sucesso!")
    bot.infinity_polling(none_stop=True, interval=1, timeout=20)
except KeyboardInterrupt:
    print("👋 Bot parado pelo usuário")
except Exception as e:
    print(f"❌ Erro: {e}")
