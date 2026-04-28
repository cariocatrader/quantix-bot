import telebot
import requests
import threading
import time
import os
from datetime import datetime, timedelta
import pytz
import math
import traceback
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise Exception("TOKEN não encontrado")

bot = telebot.TeleBot(TOKEN)

BR_TZ = pytz.timezone('America/Sao_Paulo')
UTC_TZ = pytz.timezone('UTC')

def get_br_time(format_str="%H:%M"):
    return datetime.now(BR_TZ).strftime(format_str)

def log_error(func_name, error):
    logger.error(f"❌ ERRO em {func_name}: {str(error)}")

def br_to_utc_timestamp(br_time_str):
    try:
        now_br = datetime.now(BR_TZ)
        br_dt = datetime.strptime(br_time_str, "%H:%M").replace(
            year=now_br.year, month=now_br.month, day=now_br.day
        )
        br_dt = BR_TZ.localize(br_dt)
        utc_dt = br_dt.astimezone(UTC_TZ)
        return int(utc_dt.timestamp() * 1000)
    except:
        return int(time.time() * 1000)

SYMBOLS = {
    "bitcoin": "₿ Bitcoin", "ethereum": "Ξ Ethereum", "binancecoin": "🟡 BNB",
    "solana": "🟣 Solana", "ripple": "💧 XRP", "cardano": "🔵 Cardano",
    "dogecoin": "🐶 Doge", "litecoin": "🪙 Litecoin", "polkadot": "⚫ Polkadot",
    "avalanche-2": "🔺 Avalanche"
}

BINANCE_SYMBOLS = {
    "bitcoin": "BTCUSDT", "ethereum": "ETHUSDT", "binancecoin": "BNBUSDT",
    "solana": "SOLUSDT", "ripple": "XRPUSDT", "cardano": "ADAUSDT",
    "dogecoin": "DOGEUSDT", "litecoin": "LTCUSDT", "polkadot": "DOTUSDT",
    "avalanche-2": "AVAXUSDT"
}

def analyze(coin_id):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc?vs_currency=usd&days=2"
        r = requests.get(url, timeout=8)
        data = r.json()
        if not isinstance(data, list) or len(data) < 3:
            return "COMPRA"
        closes = [candle[4] for candle in data[-3:]]
        return "COMPRA" if closes[-1] > closes[-2] else "VENDA"
    except:
        return "COMPRA"

def get_binance_candle(symbol, br_time_str, interval="1m"):
    """Otimizada: endTime + última vela próxima ao target"""
    try:
        target_utc_ms = br_to_utc_timestamp(br_time_str)
        end_time = target_utc_ms + 120000
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&endTime={end_time}&limit=10"
        r = requests.get(url, timeout=10)
        data = r.json()
        
        logger.info(f"📊 Velas ts: {[int(c[0]) for c in data]} | Target: {target_utc_ms}")
        
        if not data:
            return None, None
        
        last_candle = data[-1]
        open_ts = int(last_candle[0])
        if abs(open_ts - target_utc_ms) > 90000:
            logger.warning(f"❌ Ts mismatch {open_ts} vs {target_utc_ms}")
            return None, None
        
        o, c = float(last_candle[1]), float(last_candle[4])
        logger.info(f"✅ {br_time_str} ({interval}): O:{o:.4f}→C:{c:.4f}")
        return o, c
    except Exception as e:
        logger.error(f"❌ Candle erro: {e}")
        return None, None

def get_result(symbol, direction, br_time_str, interval="1m"):
    o, c = get_binance_candle(symbol, br_time_str, interval)
    if o is None:
        return "LOSS"
    win = (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o)
    return "WIN" if win else "LOSS"

def restart_btn():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Gerar Novo Sinal", callback_data="restart"))
    return kb

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

def send_gif_safe(chat_id, gif_filename, caption, reply_markup=None):
    try:
        if os.path.exists(gif_filename):
            with open(gif_filename, "rb") as gif:
                bot.send_animation(chat_id, gif, caption=caption, parse_mode="Markdown", reply_markup=reply_markup)
            return True
        else:
            bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=reply_markup)
            return False
    except:
        bot.send_message(chat_id, caption, parse_mode="Markdown", reply_markup=reply_markup)

def safe_send_text(chat_id, text, reply_markup=None):
    try:
        bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=reply_markup)
    except:
        pass

def send_result_final(chat_id, symbol_name, direction, result, entry_time, is_gale=False, interval="1m"):
    status_emoji = "✅ WIN" if result == "WIN" else "❌ LOSS"
    gale_text = f"\n🛡️ *Gale 1*" if is_gale else ""
    
    result_text = f"""🎯 *RESULTADO FINAL*

━━━━━━━━━━━━━━━━━━
💱 `{symbol_name}`
⏱ Operação: `{entry_time}` ({interval})
🎯 Direção: `{direction}`
🏆 `{status_emoji}`{gale_text}

Quantix Cripto ✨"""
    
    gif_filename = "win.gif" if result == "WIN" else "loss.gif"
    send_gif_safe(chat_id, gif_filename, result_text, final_btn())

def send_gale_notification(chat_id, symbol_name, direction):
    gale_text = f"""🔄 *Entrando no Gale 1, aguarde o final da operação*

━━━━━━━━━━━━━━━━━━
💱 `{symbol_name}`
🎯 Direção: `{direction}`

🛡️ *Processando Gale...*"""
    safe_send_text(chat_id, gale_text)

def process_trade(chat_id, coin_id, direction, entry_time, exp, is_gale=False):
    """OTIMIZADA: Espera precisa + resultado imediato + gale sem delay extra"""
    def check():
        interval = "1m" if exp == "1" else "5m"
        interval_secs = 60 if exp == "1" else 300
        
        # Tempo exato de espera (só +3s pós-fechamento)
        entry_dt = datetime.strptime(entry_time, "%H:%M")
        now_dt = datetime.now(BR_TZ)
        entry_full = now_dt.replace(hour=entry_dt.hour, minute=entry_dt.minute, second=0, microsecond=0)
        wait_until = entry_full + timedelta(seconds=interval_secs) + timedelta(seconds=3)
        
        seconds_to_wait = max(0, (wait_until - now_dt).total_seconds())
        if seconds_to_wait > 0:
            logger.info(f"⏳ Espera {seconds_to_wait:.0f}s até fim candle")
            time.sleep(seconds_to_wait)
        
        # API + resultado IMEDIATO
        symbol = BINANCE_SYMBOLS[coin_id]
        result = get_result(symbol, direction, entry_time, interval)
        logger.info(f"📊 {entry_time} ({'Gale' if is_gale else 'Principal'} {interval}): {result}")
        send_result_final(chat_id, SYMBOLS[coin_id], direction, result, entry_time, is_gale, interval)
        
        # Gale só se principal LOSS (direto, sem thread extra)
        if not is_gale and result == "LOSS":
            logger.info("🚫 LOSS principal → Gale")
            send_gale_notification(chat_id, SYMBOLS[coin_id], direction)
            
            # Próxima vela imediata
            now_br = datetime.now(BR_TZ)
            now_minute = now_br.replace(second=0, microsecond=0)
            if exp == "1":
                gale_time_obj = now_minute + timedelta(minutes=1)
            else:
                minutes = now_minute.minute
                next_5 = math.ceil((minutes + 1) / 5.0) * 5
                if next_5 >= 60:
                    next_5 = 0
                    now_minute += timedelta(hours=1)
                gale_time_obj = now_minute.replace(minute=next_5)
            gale_time = gale_time_obj.strftime("%H:%M")
            
            logger.info(f"🛡️ Gale: {gale_time}")
            process_trade(chat_id, coin_id, direction, gale_time, exp, True)  # Direto!
    
    threading.Thread(target=check, daemon=True).start()

def run_signal(chat_id, coin_id, exp, message_id=None):
    def process():
        try:
            if message_id:
                try:
                    bot.delete_message(chat_id, message_id)
                except:
                    pass

            send_gif_safe(chat_id, "analise.gif", "🔍 *Analisando mercado...*", None)
            
            direction = analyze(coin_id)
            now = get_br_time()
            interval = "1m" if exp == "1" else "5m"
            
            now_dt = datetime.now(BR_TZ)
            now_obj = datetime.strptime(now, "%H:%M").replace(
                year=now_dt.year, month=now_dt.month, day=now_dt.day
            )
            now_obj = BR_TZ.localize(now_obj)
            
            if exp == "1":
                entry_min = now_obj.minute + 1
                if entry_min >= 60:
                    entry_min = 0
                    now_obj += timedelta(hours=1)
                entry_time_obj = now_obj.replace(minute=entry_min, second=0, microsecond=0)
            else:
                minutes = now_obj.minute
                next_5 = math.ceil((minutes + 1) / 5.0) * 5
                if next_5 >= 60:
                    next_5 = 0
                    now_obj += timedelta(hours=1)
                entry_time_obj = now_obj.replace(minute=next_5, second=0, microsecond=0)
            
            entry_time = entry_time_obj.strftime("%H:%M")
            gale_time_obj = entry_time_obj + timedelta(minutes=1 if exp=="1" else 5)
            gale_time = gale_time_obj.strftime("%H:%M")

            sinal_text = f"""🎉 *SINAL GERADO!*

━━━━━━━━━━━━━━━━━━
💱 `{SYMBOLS[coin_id]}`
⏱ *Entrada:* `{entry_time}`
📅 *Gale 1:* `{gale_time}`
🎯 Direção: `{direction}`
⏳ `{1 if exp == "1" else 5} min`

*Aguardando...* ✨"""

            safe_send_text(chat_id, sinal_text)
            process_trade(chat_id, coin_id, direction, entry_time, exp, False)

        except Exception as e:
            log_error("run_signal", e)

    threading.Thread(target=process, daemon=True).start()

# HANDLERS
@bot.message_handler(commands=["start"])
def start(m):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Gerar Sinal", callback_data="start"))
    bot.send_message(m.chat.id, f"""🤖 *Quantix Cripto*

Gales automáticos RÁPIDOS

🇧🇷 {get_br_time()}""", parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "start")
def start_flow(c):
    bot.answer_callback_query(c.id)
    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
    except:
        pass
    safe_send_text(c.message.chat.id, "*Escolha paridade:*", menu_paridades())

@bot.callback_query_handler(func=lambda c: c.data.startswith("par_"))
def paridade(c):
    bot.answer_callback_query(c.id)
    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
    except:
        pass
    coin_id = c.data.split("_", 1)[1]
    safe_send_text(c.message.chat.id, "*Escolha expiração:*", menu_exp(coin_id))

@bot.callback_query_handler(func=lambda c: c.data.startswith("exp_"))
def exp_handler(c):
    bot.answer_callback_query(c.id)
    parts = c.data.split("_")
    run_signal(c.message.chat.id, parts[1], parts[2], c.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data == "new_signal")
def new_signal_handler(c):
    bot.answer_callback_query(c.id)
    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
    except:
        pass
    safe_send_text(c.message.chat.id, "*Escolha paridade:*", menu_paridades())

print(f"🚀 QUANTIX v2.0 ATIVO {get_br_time()} - Matching OK + Gale RÁPIDO!")

try:
    bot.remove_webhook()
    time.sleep(3)
except:
    pass

while True:
    try:
        print("🤖 Polling...")
        bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)
    except Exception as e:
        print("⚠️ ERRO:", str(e))
        time.sleep(10)
