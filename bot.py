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

HEADERS = {"Accept-Encoding": "gzip, deflate", "User-Agent": "QuantixBot/1.0"}

# =============================
# UTILITÁRIOS
# =============================

def send_gif(chat_id, path, caption, reply_markup=None):
    with open(path, "rb") as f:
        return bot.send_animation(chat_id, f, caption=caption, reply_markup=reply_markup)

def delete_msg(chat_id, msg_id):
    try:
        bot.delete_message(chat_id, msg_id)
    except Exception:
        pass

# =============================
# MENUS
# =============================

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

def botao_novo_sinal():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Novo Sinal", callback_data="gerar"))
    return kb

# =============================
# START
# =============================

@bot.message_handler(commands=["start"])
def start(m):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Gerar Sinal", callback_data="gerar"))
    bot.send_message(m.chat.id, "👋 Quantix Signals", reply_markup=kb)

# =============================
# CALLBACKS
# =============================

@bot.callback_query_handler(func=lambda c: c.data == "gerar")
def gerar(c):
    bot.answer_callback_query(c.id)
    try:
        bot.edit_message_text(
            "Escolha o par:",
            c.message.chat.id,
            c.message.message_id,
            reply_markup=menu_paridades()
        )
    except:
        bot.send_message(c.message.chat.id, "Escolha o par:", reply_markup=menu_paridades())

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_"))
def escolher_expiracao(c):
    coin_id = c.data.split("_", 1)[1]
    bot.answer_callback_query(c.id)

    kb, nome, emoji = menu_expiracao(coin_id)

    try:
        bot.edit_message_text(
            f"Par: {emoji} {nome}\nEscolha a expiração:",
            c.message.chat.id,
            c.message.message_id,
            reply_markup=kb
        )
    except:
        bot.send_message(
            c.message.chat.id,
            f"Par: {emoji} {nome}\nEscolha a expiração:",
            reply_markup=kb
        )

# =============================
# FLUXO 1 MINUTO
# =============================

def fluxo_1min(chat_id, coin_id, msg_analise_id):
    nome, emoji = DISPLAY[coin_id]

    delete_msg(chat_id, msg_analise_id)

    bot.send_message(
        chat_id,
        f"""🚀 SINAL ENVIADO
━━━━━━━━━━━━━━
💱 Paridade: {emoji} {nome}
⏱ Expiração: 1 minuto"""
    )

# =============================
# CALLBACK EXECUÇÃO
# =============================

@bot.callback_query_handler(func=lambda c: c.data.startswith("e_"))
def run(c):
    _, coin_id, exp = c.data.split("_")
    exp = int(exp)

    bot.answer_callback_query(c.id)
    delete_msg(c.message.chat.id, c.message.message_id)

    msg = send_gif(c.message.chat.id, GIF_ANALISE, "🔎 Analisando mercado...")

    threading.Thread(
        target=fluxo_1min,
        args=(c.message.chat.id, coin_id, msg.message_id),
        daemon=True
    ).start()

# =============================
# LOOP
# =============================

print("BOT ONLINE - QUANTIX CRIPTO")

while True:
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=15)
    except Exception as e:
        print("Polling caiu:", e)
        time.sleep(5)
