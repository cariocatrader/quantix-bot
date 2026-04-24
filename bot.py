import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
from datetime import datetime, timedelta
import pytz
import os

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

# ==============================
# SINCRONIZAÇÃO PROFISSIONAL
# ==============================

def esperar_candle_fechar():

    agora = datetime.now(timezone)

    prox = agora.replace(second=0, microsecond=0) + timedelta(minutes=1)

    alvo = prox + timedelta(seconds=3)

    diff = (alvo - datetime.now(timezone)).total_seconds()

    if diff > 0:
        time.sleep(diff)

# ==============================
# API
# ==============================

def buscar_candles(paridade):

    try:
        url = f"https://api.twelvedata.com/time_series?symbol={paridade}&interval=1min&outputsize=15&apikey={API_KEY}"
        r = requests.get(url, timeout=10)
        data = r.json()

        if "values" not in data:
            return None

        return data["values"]

    except:
        return None

# ==============================
# CAMADA 1 (3 candles)
# ==============================

def micro_tendencia(candles):

    ultimos = candles[1:4]

    altas = sum(float(c["close"]) > float(c["open"]) for c in ultimos)
    baixas = 3 - altas

    if altas >= 2:
        return "CALL"
    if baixas >= 2:
        return "PUT"

    return None

# ==============================
# CAMADA 2 (FILTRO 5 candles)
# ==============================

def macro_tendencia(candles):

    ultimos = candles[1:6]

    altas = sum(float(c["close"]) > float(c["open"]) for c in ultimos)
    baixas = 5 - altas

    if altas >= 3:
        return "CALL"
    if baixas >= 3:
        return "PUT"

    return None

# ==============================
# DECISÃO FINAL (PRO)
# ==============================

def gerar_sinal(candles):

    micro = micro_tendencia(candles)
    macro = macro_tendencia(candles)

    if micro == macro:
        return micro

    return None

# ==============================
# RESULTADO REAL (CANDLE FECHADO)
# ==============================

def resultado(paridade, direcao):

    candles = buscar_candles(paridade)

    if not candles:
        return None

    candle = candles[1]  # fechado

    if float(candle["close"]) > float(candle["open"]):
        return "WIN" if direcao == "CALL" else "LOSS"
    else:
        return "WIN" if direcao == "PUT" else "LOSS"

# ==============================
# START
# ==============================

@bot.message_handler(commands=["start"])
def start(m):

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Gerar Sinal PRO", callback_data="gerar"))

    bot.send_message(
        m.chat.id,
        "👋 Quantix PRO\n\nSistema de análise avançada ativo.",
        reply_markup=kb
    )

# ==============================
# PARIDADES
# ==============================

@bot.callback_query_handler(func=lambda c: c.data == "gerar")
def paridades(c):

    bot.delete_message(c.message.chat.id, c.message.message_id)

    kb = InlineKeyboardMarkup()

    for p in PARIDADES:
        kb.add(InlineKeyboardButton(f"{BANDERAS[p]} {p}", callback_data=f"p_{p}"))

    bot.send_message(c.message.chat.id, "📊 Escolha a paridade:", reply_markup=kb)

# ==============================
# EXECUÇÃO PRO
# ==============================

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_"))
def run(c):

    par = c.data.split("_")[1]

    bot.delete_message(c.message.chat.id, c.message.message_id)

    # ================= ANALISE =================

    msg = bot.send_animation(
        c.message.chat.id,
        open(GIF_ANALISE, "rb"),
        caption="🔎 Análise profissional em andamento..."
    )

    sinal = None
    candles = None

    start = time.time()

    while time.time() - start < 60:

        candles = buscar_candles(par)

        if candles:
            sinal = gerar_sinal(candles)
            if sinal:
                break

        time.sleep(2)

    bot.delete_message(c.message.chat.id, msg.message_id)

    if not sinal:
        bot.send_message(c.message.chat.id, "❌ Sem tendência forte no mercado.")
        return

    bot.send_message(
        c.message.chat.id,
        f"""
📊 SINAL PRO

💱 {par}
🎯 Direção: {sinal}
⏱ Base: micro + macro tendência
"""
    )

    # ================= ESPERA REAL =================

    esperar_candle_fechar()

    res = resultado(par, sinal)

    gale = 0

    if res == "LOSS":

        gale = 1

        bot.send_message(
            c.message.chat.id,
            "⚠️ LOSS detectado\n🔄 GALE 1 ativado..."
        )

        esperar_candle_fechar()

        res = resultado(par, sinal)

    # ================= RESULTADO FINAL =================

    gif = GIF_WIN if res == "WIN" else GIF_LOSS

    bot.send_animation(
        c.message.chat.id,
        open(gif, "rb"),
        caption=f"📊 RESULTADO: {res}"
    )

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Novo Sinal PRO", callback_data="gerar"))

    bot.send_message(
        c.message.chat.id,
        f"""
📊 RESULTADO FINAL

💱 {par}
🎯 Resultado: {res}
🔥 Gale: {gale}
""",
        reply_markup=kb
    )

# ==============================

print("BOT PRO ONLINE")
bot.infinity_polling()
