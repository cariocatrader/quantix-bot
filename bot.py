import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import threading
from datetime import datetime, timedelta
import pytz
import os

TOKEN = os.getenv("TOKEN")

_session = requests.Session()
_retry = Retry(total=4, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
_session.mount("https://", HTTPAdapter(max_retries=_retry))

bot = telebot.TeleBot(TOKEN, threaded=False)
timezone = pytz.timezone("America/Sao_Paulo")

GIF_ANALISE = "analise.gif"
GIF_WIN = "win.gif"
GIF_LOSS = "loss.gif"

PARIDADES = [
    "bitcoin", "ethereum", "binancecoin", "solana", "ripple",
    "cardano", "dogecoin", "litecoin", "polkadot", "avalanche-2"
]

DISPLAY = {
    "bitcoin": ("BTC/USDT", "₿🟡"),
    "ethereum": ("ETH/USDT", "Ξ🔵"),
    "binancecoin": ("BNB/USDT", "🟠"),
    "solana": ("SOL/USDT", "🟣"),
    "ripple": ("XRP/USDT", "💧"),
    "cardano": ("ADA/USDT", "🔷"),
    "dogecoin": ("DOGE/USDT", "🐶"),
    "litecoin": ("LTC/USDT", "🪙"),
    "polkadot": ("DOT/USDT", "⚫"),
    "avalanche-2": ("AVAX/USDT", "🔺"),
}

COINCAP_ID = {
    "bitcoin": "bitcoin",
    "ethereum": "ethereum",
    "binancecoin": "binance-coin",
    "solana": "solana",
    "ripple": "xrp",
    "cardano": "cardano",
    "dogecoin": "dogecoin",
    "litecoin": "litecoin",
    "polkadot": "polkadot",
    "avalanche-2": "avalanche",
}

HEADERS = {"User-Agent": "QuantixBot/1.0"}

# =========================
# TEMPO AJUSTADO
# =========================

def proxima_entrada_1min():
    agora = datetime.now(timezone)
    return agora.replace(second=0, microsecond=0) + timedelta(minutes=1)

def proxima_entrada_5min():
    agora = datetime.now(timezone)
    base = agora.replace(second=0, microsecond=0) + timedelta(minutes=1)

    resto = base.minute % 5
    ajuste = (5 - resto) % 5
    return base + timedelta(minutes=ajuste)

def esperar_ate(ts):
    while datetime.now(timezone) < ts:
        time.sleep(0.2)

# =========================
# UTIL
# =========================

def send_gif(chat_id, path, caption, reply_markup=None):
    with open(path, "rb") as f:
        return bot.send_animation(chat_id, f, caption=caption, reply_markup=reply_markup)

def delete_msg(chat_id, msg_id):
    try:
        bot.delete_message(chat_id, msg_id)
    except:
        pass

# =========================
# MENUS
# =========================

def menu_paridades():
    kb = InlineKeyboardMarkup(row_width=2)
    for coin in PARIDADES:
        nome, emoji = DISPLAY[coin]
        kb.add(InlineKeyboardButton(f"{emoji} {nome}", callback_data=f"p_{coin}"))
    return kb

def menu_expiracao(coin_id):
    nome, emoji = DISPLAY[coin_id]
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⚡ 1 Minuto", callback_data=f"e_{coin_id}_1"),
        InlineKeyboardButton("🕐 5 Minutos", callback_data=f"e_{coin_id}_5"),
    )
    return kb, nome, emoji

def botao_novo():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Novo Sinal", callback_data="gerar"))
    return kb

# =========================
# ANALISE SIMPLIFICADA (mantida)
# =========================

def calcular_resultado(candle, direcao):
    diff = candle["close"] - candle["open"]
    if abs(diff) < 1e-8:
        return "DOJI"
    return "WIN" if (diff > 0 and direcao == "CALL") or (diff < 0 and direcao == "PUT") else "LOSS"

# =========================
# FLUXO 1 MIN
# =========================

def fluxo_1min(chat_id, coin_id, msg_id):
    nome, emoji = DISPLAY[coin_id]

    delete_msg(chat_id, msg_id)

    entrada = proxima_entrada_1min()
    gale1 = entrada + timedelta(minutes=1)

    direcao = "COMPRA"  # placeholder visual (CALL/PUT interno mantido se quiser expandir)

    bot.send_message(
        chat_id,
        f"""🚀 SINAL 1M
━━━━━━━━━━━━━━
💱 Par: {emoji} {nome}
📍 Entrada: {entrada.strftime('%H:%M')}
🎯 Direção: {direcao}
⏳ Expiração: 1 minuto
🔁 Gale: {gale1.strftime('%H:%M')}"""
    )

# =========================
# FLUXO 5 MIN (AJUSTADO MÚLTIPLOS DE 5)
# =========================

def fluxo_5min(chat_id, coin_id, msg_id):
    nome, emoji = DISPLAY[coin_id]

    delete_msg(chat_id, msg_id)

    entrada = proxima_entrada_5min()
    fechamento = entrada + timedelta(minutes=5)
    gale1 = fechamento
    gale2 = gale1 + timedelta(minutes=5)

    bot.send_message(
        chat_id,
        f"""🚀 SINAL 5M
━━━━━━━━━━━━━━
💱 Par: {emoji} {nome}
📍 Entrada: {entrada.strftime('%H:%M')}
🎯 Direção: COMPRA/VENDA
⏳ Expiração: 5 minutos
🏁 Fechamento: {fechamento.strftime('%H:%M')}
🔁 Gale 1: {gale1.strftime('%H:%M')}
🔁 Gale 2: {gale2.strftime('%H:%M')}"""
    )

# =========================
# HANDLERS
# =========================

@bot.message_handler(commands=["start"])
def start(m):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Gerar Sinal", callback_data="gerar"))
    bot.send_message(m.chat.id, "👋 Bot de Sinais Online", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "gerar")
def gerar(c):
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id, "Escolha o par:", reply_markup=menu_paridades())

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_"))
def par(c):
    coin = c.data.split("_")[1]
    bot.answer_callback_query(c.id)

    kb, nome, emoji = menu_expiracao(coin)

    bot.send_message(
        c.message.chat.id,
        f"Par: {emoji} {nome}\nEscolha expiração:",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("e_"))
def exec(c):
    _, coin, exp = c.data.split("_")
    exp = int(exp)

    bot.answer_callback_query(c.id)
    delete_msg(c.message.chat.id, c.message.message_id)

    msg = send_gif(c.message.chat.id, GIF_ANALISE, "🔎 Analisando...")

    if exp == 1:
        threading.Thread(target=fluxo_1min, args=(c.message.chat.id, coin, msg.message_id)).start()
    else:
        threading.Thread(target=fluxo_5min, args=(c.message.chat.id, coin, msg.message_id)).start()

# =========================
# LOOP
# =========================

print("BOT ONLINE")

while True:
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=15)
    except Exception as e:
        print("Erro polling:", e)
        time.sleep(5)
