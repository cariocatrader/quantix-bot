import telebot
import requests
import threading
import time
import os
from datetime import datetime, timedelta
import pytz
import math
import logging
import signal
import sys

# Configuração de log mais limpa
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise Exception("TOKEN não encontrado")

# PID file para controle de instância única
PID_FILE = "/tmp/quantix_bot.pid"

def check_single_instance():
    """Verifica se já existe instância rodando"""
    if os.path.exists(PID_FILE):
        with open(PID_FILE, 'r') as f:
            old_pid = int(f.read().strip())
        try:
            os.kill(old_pid, 0)
            logger.error("❌ Bot já está rodando (PID: %s)", old_pid)
            sys.exit(1)
        except OSError:
            os.remove(PID_FILE)
    
    # Cria PID file
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))

def cleanup(signum=None, frame=None):
    """Limpa PID file ao encerrar"""
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
    logger.info("🧹 Cleanup executado")
    sys.exit(0)

# Registra handlers de sinal
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

check_single_instance()
logger.info("✅ Instância única confirmada (PID: %s)", os.getpid())

BR_TZ = pytz.timezone('America/Sao_Paulo')
UTC_TZ = pytz.timezone('UTC')

# URLs dos GIFs (use os seus reais)
ANALYSIS_GIF = "https://media.giphy.com/media/YOUR_ANALYSIS_GIF_ID/giphy.gif"
WIN_GIF = "https://media.giphy.com/media/YOUR_WIN_GIF_ID/giphy.gif"
LOSS_GIF = "https://media.giphy.com/media/YOUR_LOSS_GIF_ID/giphy.gif"

def get_br_time(format_str="%H:%M"):
    return datetime.now(BR_TZ).strftime(format_str)

def br_to_utc_timestamp(br_time_str):
    now_br = datetime.now(BR_TZ)
    br_dt = datetime.strptime(br_time_str, "%H:%M").replace(
        year=now_br.year, month=now_br.month, day=now_br.day,
        second=0, microsecond=0
    )
    br_dt = BR_TZ.localize(br_dt)
    utc_dt = br_dt.astimezone(UTC_TZ)
    return int(utc_dt.timestamp() * 1000)

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

def analyze(coin_id):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc?vs_currency=usd&days=2"
        r = requests.get(url, timeout=8)
        data = r.json()
        closes = [c[4] for c in data[-3:]]
        return "COMPRA" if closes[-1] > closes[-2] else "VENDA"
    except:
        return "COMPRA"

def get_binance_candle(symbol, br_time_str, interval="1m"):
    try:
        target_ts = br_to_utc_timestamp(br_time_str)
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=10"
        r = requests.get(url, timeout=10)
        data = r.json()
        if not isinstance(data, list): return None
        
        for candle in data:
            if int(candle[0]) == target_ts:
                return float(candle[1]), float(candle[4])
        return None
    except:
        return None

def get_result(symbol, direction, br_time_str, interval="1m"):
    result = get_binance_candle(symbol, br_time_str, interval)
    if not result: return "LOSS"
    o, c = result
    return "WIN" if (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o) else "LOSS"

# Estado global dos usuários
user_state = {}

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

def send_result_final(chat_id, symbol_name, direction, result, entry_time):
    status = "✅ WIN" if result == "WIN" else "❌ LOSS"
    gif_url = WIN_GIF if result == "WIN" else LOSS_GIF
    
    try:
        bot.send_animation(chat_id, gif_url, caption=f"""
🎯 RESULTADO FINAL
━━━━━━━━━━━━━━━━━━
💱 {symbol_name}
⏱ {entry_time}
🎯 {direction}
🏆 {status}
Quantix Cripto ✨""", reply_markup=final_btn())
    except:
        pass  # Fallback silencioso
    
    user_state[chat_id] = None

def process_trade(chat_id, coin_id, direction, entry_time, exp):
    def check():
        interval = "1m" if exp == "1" else "5m"
        wait = 65 if exp == "1" else 305
        time.sleep(wait)
        
        symbol = BINANCE_SYMBOLS[coin_id]
        result = get_result(symbol, direction, entry_time, interval)
        
        if result == "WIN":
            send_result_final(chat_id, SYMBOLS[coin_id], direction, result, entry_time)
        else:
            gale_time = entry_time
            text = f"""❌ LOSS!
🔥 GALE 1 Disponível
💱 {SYMBOLS[coin_id]}
⏱ {gale_time}
🎯 {direction}"""
            bot.send_message(chat_id, text, reply_markup=gale_menu(coin_id, direction, gale_time))
            user_state[chat_id] = {'awaiting_gale': True, 'coin_id': coin_id, 'direction': direction, 'entry_time': gale_time, 'exp': exp}
    
    threading.Thread(target=check, daemon=True).start()

def run_signal(chat_id, coin_id, exp):
    try:
        bot.send_animation(chat_id, ANALYSIS_GIF, caption=f"🔬 Analisando {SYMBOLS[coin_id]}...")
        
        direction = analyze(coin_id)
        now = datetime.now(BR_TZ)
        if exp == "1":
            entry = now + timedelta(minutes=1)
        else:
            m = math.ceil(now.minute / 5) * 5
            entry = now.replace(minute=m)
        entry_time = entry.strftime("%H:%M")
        
        text = f"""🎉 SINAL GERADO
━━━━━━━━━━━━━━━━━━
💱 {SYMBOLS[coin_id]}
⏱ Entrada: {entry_time}
🎯 {direction}
Aguardando..."""
        
        bot.send_message(chat_id, text)
        user_state[chat_id] = {'coin_id': coin_id, 'direction': direction, 'entry_time': entry_time, 'exp': exp, 'awaiting_gale': False}
        process_trade(chat_id, coin_id, direction, entry_time, exp)
    except:
        pass

# HANDLERS
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=["start"])
def start(m):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Gerar Sinal", callback_data="start"))
    bot.send_message(m.chat.id, "🤖 Quantix Cripto", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: True)
def callback_handler(c):
    try:
        bot.answer_callback_query(c.id)
        chat_id = c.message.chat.id
        
        if c.data == "start" or c.data == "new_signal":
            bot.edit_message_text("Escolha paridade:", chat_id, c.message.message_id, reply_markup=menu_paridades())
        elif c.data.startswith("par_"):
            coin_id = c.data.split("_")[1]
            bot.edit_message_text("Escolha expiração:", chat_id, c.message.message_id, reply_markup=menu_exp(coin_id))
        elif c.data.startswith("exp_"):
            parts = c.data.split("_")
            run_signal(chat_id, parts[1], parts[2])
        elif c.data.startswith("gale1_"):
            parts = c.data.split("_")
            coin_id, direction, entry_time = parts[1], parts[2], "_".join(parts[3:])
            bot.edit_message_text(f"🔥 Gale 1 ativado!\n{SYMBOLS[coin_id]} {direction} {entry_time}", chat_id, c.message.message_id)
            exp = user_state.get(chat_id, {}).get('exp', '1')
            process_trade(chat_id, coin_id, direction, entry_time, exp)
            user_state[chat_id] = None
        elif c.data == "skip_gale":
            bot.edit_message_text("⏭️ Gale pulado!", chat_id, c.message.message_id, reply_markup=final_btn())
            user_state[chat_id] = None
    except Exception as e:
        logger.error(f"Callback error: {e}")

# Inicialização segura
print(f"🚀 QUANTIX ATIVO {get_br_time()} (PID: {os.getpid()})")

try:
    bot.remove_webhook()
    time.sleep(3)  # Aguarda webhook limpar
    logger.info("✅ Webhook removido, iniciando polling...")
    bot.infinity_polling(none_stop=True, interval=1, timeout=30)
except KeyboardInterrupt:
    cleanup()
except Exception as e:
    logger.error(f"Erro fatal: {e}")
    cleanup()
