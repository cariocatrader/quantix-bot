import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
from datetime import datetime, timedelta
import pytz
import os

from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt

# ==============================
# CONFIG
# ==============================

TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")

bot = telebot.TeleBot(TOKEN)

timezone = pytz.timezone("America/Sao_Paulo")

PARIDADES = [
    "EUR/USD","GBP/USD","USD/JPY","AUD/USD","USD/CAD",
    "USD/CHF","NZD/USD","EUR/GBP","EUR/JPY","GBP/JPY"
]

BANDERAS = {
    "EUR/USD":"🇪🇺🇺🇸","GBP/USD":"🇬🇧🇺🇸","USD/JPY":"🇺🇸🇯🇵",
    "AUD/USD":"🇦🇺🇺🇸","USD/CAD":"🇺🇸🇨🇦","USD/CHF":"🇺🇸🇨🇭",
    "NZD/USD":"🇳🇿🇺🇸","EUR/GBP":"🇪🇺🇬🇧","EUR/JPY":"🇪🇺🇯🇵","GBP/JPY":"🇬🇧🇯🇵"
}

GIF_ANALISE = "analise.gif"
GIF_WIN = "win.gif"
GIF_LOSS = "loss.gif"

AUDIO_WIN = "win.mp3"
AUDIO_LOSS = "loss.mp3"

# ==============================
# API
# ==============================

def buscar_candles(paridade):
    try:
        url = f"https://api.twelvedata.com/time_series?symbol={paridade}&interval=1min&outputsize=10&apikey={API_KEY}"
        r = requests.get(url)
        data = r.json()

        if "values" not in data:
            return None

        return data["values"]

    except:
        return None

# ==============================
# SINAL
# ==============================

def gerar_sinal(candles):
    try:
        c = candles[:3]

        alta = sum(float(x["close"]) > float(x["open"]) for x in c)
        baixa = 3 - alta

        if alta >= 2:
            return "CALL"
        if baixa >= 2:
            return "PUT"

        return None

    except:
        return None

# ==============================
# RESULTADO CORRETO
# ==============================

def verificar_resultado(paridade, direcao):
    candles = buscar_candles(paridade)

    if not candles:
        return None

    candle = candles[0]

    open_price = float(candle["open"])
    close_price = float(candle["close"])

    if direcao == "CALL":
        return "WIN" if close_price > open_price else "LOSS"

    if direcao == "PUT":
        return "WIN" if close_price < open_price else "LOSS"

# ==============================
# IMAGEM PRO
# ==============================

def gerar_imagem_pro(paridade, direcao, entrada, candles=None):

    img = Image.new("RGB", (800, 450), (10, 12, 18))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.load_default()
    except:
        font = None

    draw.text((30, 30), "QUANTIX PRO SIGNAL", fill="white", font=font)
    draw.text((30, 120), f"{paridade}", fill="white", font=font)

    cor = (0,255,120) if direcao=="CALL" else (255,60,60)

    draw.text((30, 180), f"Direção: {direcao}", fill=cor, font=font)
    draw.text((30, 230), f"Entrada: {entrada}", fill="white", font=font)

    file = "signal.png"
    img.save(file)

    return file

# ==============================
# BOT
# ==============================

@bot.message_handler(commands=["start"])
def start(m):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Gerar Sinal", callback_data="gerar"))

    bot.send_message(m.chat.id, "Quantix PRO", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data=="gerar")
def paridades(c):

    bot.delete_message(c.message.chat.id, c.message.message_id)

    kb = InlineKeyboardMarkup()

    for p in PARIDADES:
        kb.add(InlineKeyboardButton(f"{BANDERAS[p]} {p}", callback_data=f"p_{p}"))

    bot.send_message(c.message.chat.id, "Escolha:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_"))
def run(c):

    par = c.data.split("_")[1]

    bot.delete_message(c.message.chat.id, c.message.message_id)

    msg = bot.send_animation(c.message.chat.id, open(GIF_ANALISE,"rb"))

    candles = None
    sinal = None

    start = time.time()

    while time.time()-start < 60:

        candles = buscar_candles(par)

        if candles:
            sinal = gerar_sinal(candles)
            if sinal:
                break

        time.sleep(2)

    bot.delete_message(c.message.chat.id, msg.message_id)

    if not sinal:
        bot.send_message(c.message.chat.id, "Sem sinal")
        return

    entrada = datetime.now(timezone).strftime("%H:%M")

    img = gerar_imagem_pro(par, sinal, entrada)

    with open(img,"rb") as f:
        bot.send_photo(c.message.chat.id, f)

    time.sleep(1)

    result = verificar_resultado(par, sinal)

    if result == "LOSS":
        bot.send_message(c.message.chat.id, "⚠️ GALE 1 entrando...")

        time.sleep(60)

        result = verificar_resultado(par, sinal)

    gif = GIF_WIN if result=="WIN" else GIF_LOSS
    audio = AUDIO_WIN if result=="WIN" else AUDIO_LOSS

    bot.send_animation(c.message.chat.id, open(gif,"rb"))

    bot.send_audio(c.message.chat.id, open(audio,"rb"))

    bot.send_message(c.message.chat.id, f"RESULTADO: {result}")

print("BOT ONLINE")
bot.infinity_polling()
