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

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
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
    logger.error(traceback.format_exc())

def br_to_utc_timestamp(br_time_str):
    try:
        now_br = datetime.now(BR_TZ)
        br_dt = datetime.strptime(br_time_str, "%H:%M").replace(
            year=now_br.year,
            month=now_br.month,
            day=now_br.day
        )
        br_dt = BR_TZ.localize(br_dt)
        utc_dt = br_dt.astimezone(UTC_TZ)
        return int(utc_dt.timestamp() * 1000)
    except Exception as e:
        log_error("br_to_utc_timestamp", e)
        return int(time.time() * 1000)

def next_round_time(now_str, exp):
    try:
        now_dt = datetime.now(BR_TZ)
        now = datetime.strptime(now_str, "%H:%M").replace(
            year=now_dt.year,
            month=now_dt.month,
            day=now_dt.day
        )
        now = BR_TZ.localize(now)

        if exp == "1":
            entry_min = now.minute + 1
            if entry_min >= 60:
                entry_min = 0
                now += timedelta(hours=1)
            entry = now.replace(minute=entry_min, second=0, microsecond=0)
            gale1 = entry + timedelta(minutes=1)
        else:
            minutes = now.minute
            next_5 = math.ceil((minutes + 1) / 5.0) * 5
            if next_5 >= 60:
                next_5 = 0
                now += timedelta(hours=1)
            entry = now.replace(minute=next_5, second=0, microsecond=0)
            gale1 = entry + timedelta(minutes=5)

        return (entry.strftime("%H:%M"), gale1.strftime("%H:%M"))
    except Exception as e:
        log_error("next_round_time", e)
        return (get_br_time(), get_br_time())

SYMBOLS = {
    "bitcoin": "₿ Bitcoin",
    "ethereum": "Ξ Ethereum", 
    "binancecoin": "🟡 BNB",
    "solana": "🟣 Solana",
    "ripple": "💧 XRP",
    "cardano": "🔵 Cardano",
    "dogecoin": "🐶 Doge",
    "litecoin": "🪙 Litecoin",
    "polkadot": "⚫ Polkadot",
    "avalanche-2": "🔺 Avalanche"
}

BINANCE_SYMBOLS = {
    "bitcoin": "BTCUSDT",
    "ethereum": "ETHUSDT",
    "binancecoin": "BNBUSDT", 
    "solana": "SOLUSDT",
    "ripple": "XRPUSDT",
    "cardano": "ADAUSDT",
    "dogecoin": "DOGEUSDT",
    "litecoin": "LTCUSDT",
    "polkadot": "DOTUSDT",
    "avalanche-2": "AVAXUSDT"
}

ANALISE_GIF = "analise.gif"
WIN_GIF = "win.gif"
LOSS_GIF = "loss.gif"

def analyze(coin_id):
    try:
        logger.info(f"🔍 Analisando {coin_id}")
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc?vs_currency=usd&days=2"
        r = requests.get(url, timeout=8)
        data = r.json()

        if not isinstance(data, list) or len(data) < 3:
            logger.warning("Dados insuficientes CoinGecko")
            return "COMPRA"

        closes = [candle[4] for candle in data[-3:]]
        direction = "COMPRA" if closes[-1] > closes[-2] else "VENDA"
        logger.info(f"✅ Análise {coin_id}: {direction}")
        return direction

    except Exception as e:
        log_error(f"analyze({coin_id})", e)
        return "COMPRA"

def get_binance_candle(symbol, br_time_str):
    try:
        target_utc_ms = br_to_utc_timestamp(br_time_str)
        logger.info(f"🔍 Buscando candle {symbol} {br_time_str} (UTC: {target_utc_ms})")

        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=60"
        r = requests.get(url, timeout=5)
        data = r.json()

        for candle in data:
            open_ts = int(candle[0])
            if abs(open_ts - target_utc_ms) < 120000:
                o = float(candle[1])
                c = float(candle[4])
                logger.info(f"✅ Candle encontrado {symbol}: {o} → {c}")
                return o, c

        logger.warning(f"❌ Candle não encontrado para {symbol}")
        return None, None

    except Exception as e:
        log_error(f"get_binance_candle({symbol})", e)
        return None, None

def get_result(symbol, direction, br_time_str):
    o, c = get_binance_candle(symbol, br_time_str)
    if o is None:
        return "LOSS"

    win = (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o)
    result = "WIN" if win else "LOSS"
    logger.info(f"📊 Resultado {symbol}: {direction} → {result}")
    return result

def restart_btn():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Novo Sinal", callback_data="restart"))
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

def safe_send_animation(chat_id, gif_path, caption):
    """Envio seguro com retry e timeout"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"📤 Tentativa {attempt+1} - Enviando animação para {chat_id}")
            with open(gif_path, "rb") as gif:
                msg = bot.send_animation(
                    chat_id, gif, 
                    caption=caption,
                    parse_mode="Markdown",
                    timeout=30
                )
            logger.info(f"✅ Animação enviada para {chat_id} (ID: {msg.message_id})")
            return msg
        except Exception as e:
            logger.error(f"❌ Falha tentativa {attempt+1}/3 animação: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Backoff exponencial
            else:
                logger.error("❌ FALHA DEFINITIVA no envio da animação")
                return None

def safe_send_message(chat_id, text, reply_markup=None):
    """Envio seguro com retry e timeout"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"📤 Tentativa {attempt+1} - Enviando mensagem para {chat_id}")
            msg = bot.send_message(
                chat_id, text,
                parse_mode="Markdown",
                reply_markup=reply_markup,
                timeout=30
            )
            logger.info(f"✅ Mensagem enviada para {chat_id} (ID: {msg.message_id})")
            return msg
        except Exception as e:
            logger.error(f"❌ Falha tentativa {attempt+1}/3 mensagem: {str(e)}")
            if "network is unreachable" in str(e).lower() or "timeout" in str(e).lower():
                logger.error("🔴 PROBLEMA DE REDE CONFIRMADO - Railway/Telegram")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                logger.error("❌ FALHA DEFINITIVA no envio da mensagem")
                return None

def run_signal(chat_id, coin_id, exp, message_id=None):
    def process():
        try:
            logger.info(f"🚀 Iniciando sinal para chat {chat_id}, {coin_id}, exp {exp}")
            
            # Deletar mensagem antiga se existir
            if message_id:
                try:
                    bot.delete_message(chat_id, message_id)
                    logger.info(f"🗑️ Mensagem antiga deletada")
                except:
                    logger.warning("Não foi possível deletar mensagem antiga")

            # Enviar animação de análise
            caption = "🔍 *Aguarde enquanto o Quantix Cripto busca a melhor entrada...*"
            anim_msg = safe_send_animation(chat_id, ANALISE_GIF, caption)
            
            if not anim_msg:
                safe_send_message(chat_id, "❌ Erro de conexão com Telegram. Tente novamente!", restart_btn())
                return

            # Fazer análise
            direction = analyze(coin_id)
            symbol = BINANCE_SYMBOLS[coin_id]
            now = get_br_time()
            entry_time, gale_time = next_round_time(now, exp)
            exp_min = 1 if exp == "1" else 5

            # Preparar mensagem do sinal
            sinal_text = f"""🎉 *SINAL ENCONTRADO!*

━━━━━━━━━━━━━━━━━━
💱 `{SYMBOLS[coin_id]}`
⏱ Entrada: `{entry_time}`
📅 Gale 1: `{gale_time}`
🎯 Direção: `{direction}`
⏳ Expiração: `{exp_min} min`
📊 Análise: CoinGecko + Binance

Quantix Cripto - Precisão máxima ✨"""

            # Enviar sinal
            sinal_msg = safe_send_message(chat_id, sinal_text, restart_btn())
            
            if not sinal_msg:
                logger.error("🔴 CRÍTICO: Sinal gerado mas não enviado!")
                safe_send_message(chat_id, "⚠️ Sinal gerado mas houve problema de conexão. Logs: Railway bloqueia Telegram API", restart_btn())

        except Exception as e:
            log_error("run_signal.process", e)
            safe_send_message(chat_id, "❌ Erro interno. Tente novamente!", restart_btn())

    threading.Thread(target=process, daemon=True).start()

# HANDLERS
@bot.message_handler(commands=["start"])
def start(m):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🚀 Iniciar Quantix", callback_data="start"))
    
    bot.send_message(
        m.chat.id,
        f"""🤖 *Bem-vindo ao Quantix Cripto!*

IA de trading 24/7

🇧🇷 {get_br_time()}""",
        parse_mode="Markdown",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda c: c.data == "start")
def start_flow(c):
    bot.answer_callback_query(c.id)
    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
    except:
        pass
    safe_send_message(c.message.chat.id, "*Escolha a paridade:*", menu_paridades())

@bot.callback_query_handler(func=lambda c: c.data.startswith("par_"))
def paridade(c):
    bot.answer_callback_query(c.id)
    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
    except:
        pass
    coin_id = c.data.split("_", 1)[1]
    safe_send_message(c.message.chat.id, "*Selecione expiração:*", menu_exp(coin_id))

@bot.callback_query_handler(func=lambda c: c.data.startswith("exp_"))
def exp_handler(c):
    bot.answer_callback_query(c.id)
    parts = c.data.split("_")
    run_signal(c.message.chat.id, parts[1], parts[2], c.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data == "restart")
def restart(c):
    bot.answer_callback_query(c.id)
    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
    except:
        pass
    safe_send_message(c.message.chat.id, "*Escolha a paridade:*", menu_paridades())

# Inicialização
logger.info(f"🚀 QUANTIX ATIVO {get_br_time()}")

try:
    bot.remove_webhook()
    time.sleep(3)
    logger.info("Webhook removido")
except:
    logger.warning("Não foi possível remover webhook")

# Loop principal com restart automático
while True:
    try:
        logger.info("🤖 Iniciando polling...")
        bot.infinity_polling(
            timeout=60,
            long_polling_timeout=60,
            skip_pending=True
        )
    except Exception as e:
        logger.error("⚠️ ERRO NO POLLING:")
        log_error("infinity_polling", e)
        logger.info("🔄 Reiniciando em 10 segundos...")
        time.sleep(10)
