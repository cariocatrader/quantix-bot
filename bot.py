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
# TIME ENGINE (CORREÇÃO PRINCIPAL)
# ==============================

def proximo_minuto_operacao():

    agora = datetime.now(timezone)

    # 🔥 SE ESTIVER NO MEIO DO MINUTO, VAI PARA O PRÓXIMO +1
    if agora.second > 0:
        base = agora.replace(second=0, microsecond=0) + timedelta(minutes=1)
    else:
        base = agora.replace(second=0, microsecond=0)

    # 🔥 SEMPRE +1 MINUTO DE SEGURANÇA (NUNCA ENTRA NO MESMO MINUTO)
    return base + timedelta(minutes=1)

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
# SINAL (3 CANDLES)
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
    kb.add(InlineKeyboardButton("🚀 Gerar Sinal", callback_data="gerar"))

    bot.send_message(
        m.chat.id,
        "👋 Bem-vindo ao Quantix\n\nClique abaixo para gerar seu sinal.",
        reply_markup=kb
    )

# ==============================
# PARIDADES
# ==============================

@bot.callback_query_handler(func=lambda c: c.data=="gerar")
def paridades(c):

    bot.delete_message(c.message.chat.id, c.message.message_id)

    kb = InlineKeyboardMarkup()

    for p in PARIDADES:
        kb.add(InlineKeyboardButton(f"{BANDERAS[p]} {p}", callback_data=f"p_{p}"))

    bot.send_message(c.message.chat.id, "📊 Escolha a paridade:", reply_markup=kb)

# ==============================
# EXECUÇÃO
# ==============================

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_"))
def run(c):

    par = c.data.split("_")[1]

    bot.delete_message(c.message.chat.id, c.message.message_id)

    # ================= ANALISE =================
    msg = bot.send_animation(
        c.message.chat.id,
        open(GIF_ANALISE, "rb"),
        caption="🔎 Analisando mercado..."
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
        bot.send_message(c.message.chat.id, "❌ Sem sinal no momento.")
        return

    # ================= TEMPO CORRETO =================

    entrada = proximo_minuto_operacao()

    bot.send_message(
        c.message.chat.id,
        f"""
📊 NOVO SINAL

💱 {par}
🕐 Entrada: {entrada.strftime('%H:%M')}
🎯 Direção: {sinal}
🔥 Gale: 1
"""
    )

    # ================= ESPERA =================

    time.sleep(60)

    result = verificar_resultado(par, sinal)

    gale = 0

    if result == "LOSS":

        gale = 1

        bot.send_message(
            c.message.chat.id,
            "⚠️ LOSS detectado\n🔄 Entrando em GALE 1..."
        )

        time.sleep(60)

        result = verificar_resultado(par, sinal)

    # ================= RESULTADO FINAL =================

    time.sleep(3)

    gif = GIF_WIN if result == "WIN" else GIF_LOSS

    bot.send_animation(
        c.message.chat.id,
        open(gif, "rb"),
        caption=f"📊 RESULTADO: {result}"
    )

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Novo Sinal", callback_data="gerar"))

    bot.send_message(
        c.message.chat.id,
        f"""
📊 RESULTADO FINAL

💱 {par}
🎯 Resultado: {result}
🔥 Gale usado: {gale}
""",
        reply_markup=kb
    )

# ==============================

print("BOT ONLINE")
bot.infinity_polling()
