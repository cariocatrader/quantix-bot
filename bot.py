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
# TEMPO PROFISSIONAL
# ==============================

def entrada():

    agora = datetime.now(timezone)

    base = agora.replace(second=0, microsecond=0)

    if agora.second > 0:
        base += timedelta(minutes=1)

    return base + timedelta(minutes=1)

def gale_time(ent):

    return ent + timedelta(minutes=1)

# ==============================
# API
# ==============================

def candles(par):

    try:
        url = f"https://api.twelvedata.com/time_series?symbol={par}&interval=1min&outputsize=10&apikey={API_KEY}"
        r = requests.get(url, timeout=10)
        data = r.json()

        if "values" not in data:
            return None

        return data["values"]

    except:
        return None

# ==============================
# ANÁLISE REAL (3 candles)
# ==============================

def sinal(c):

    ult = c[:3]

    alta = sum(float(x["close"]) > float(x["open"]) for x in ult)
    baixa = 3 - alta

    if alta >= 2:
        return "CALL"

    if baixa >= 2:
        return "PUT"

    return None

# ==============================
# RESULTADO REAL
# ==============================

def result(par, dir):

    c = candles(par)

    if not c:
        return None

    candle = c[1]

    if float(candle["close"]) > float(candle["open"]):
        return "WIN" if dir == "CALL" else "LOSS"
    else:
        return "WIN" if dir == "PUT" else "LOSS"

# ==============================
# START
# ==============================

@bot.message_handler(commands=["start"])
def start(m):

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Gerar Sinal", callback_data="gerar"))

    bot.send_message(
        m.chat.id,
        "👋 Bem-vindo ao Quantix PRO\n\nClique abaixo para iniciar.",
        reply_markup=kb
    )

# ==============================
# PARIDADES
# ==============================

@bot.callback_query_handler(func=lambda c: c.data == "gerar")
def pares(c):

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

    # ================= ANALISE (30s mínimo) =================

    msg = bot.send_animation(
        c.message.chat.id,
        open(GIF_ANALISE, "rb"),
        caption="🔎 Analisando mercado... (30s mínimo)"
    )

    sinal_final = None
    candles_data = None

    start = time.time()

    # 🔥 FORÇA 30 SEGUNDOS DE ANÁLISE
    while time.time() - start < 30:

        candles_data = candles(par)

        if candles_data:
            sinal_final = sinal(candles_data)

        time.sleep(2)

    bot.delete_message(c.message.chat.id, msg.message_id)

    if not sinal_final:
        bot.send_message(c.message.chat.id, "❌ Sem tendência forte no mercado.")
        return

    # ================= HORÁRIOS =================

    ent = entrada()
    gale = gale_time(ent)

    bot.send_message(
        c.message.chat.id,
        f"""
📊 SINAL ENCONTRADO 📊 

💱 {par}
🎯 Direção: {sinal_final}

⏱ Entrada: {ent.strftime('%H:%M')}
⚠️ GALE 1: {gale.strftime('%H:%M')}

📈 Análise: 3 candles + confirmação
"""
    )

    # ================= ESPERA =================

    time.sleep(60)

    res = result(par, sinal_final)

    gale_used = 0

    if res == "LOSS":

        gale_used = 1

        bot.send_message(
            c.message.chat.id,
            f"⚠️ LOSS detectado\n🔄 Entrando em GALE 1 às {gale.strftime('%H:%M')}..."
        )

        time.sleep(60)

        res = result(par, sinal_final)

    # ================= RESULTADO FINAL =================

    time.sleep(3)

    gif = GIF_WIN if res == "WIN" else GIF_LOSS

    bot.send_animation(
        c.message.chat.id,
        open(gif, "rb"),
        caption=f"📊 RESULTADO: {res}"
    )

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Novo Sinal", callback_data="gerar"))

    bot.send_message(
        c.message.chat.id,
        f"""
📊 RESULTADO FINAL

💱 {par}
🎯 Resultado: {res}
🔥 Gale usado: {gale_used}
""",
        reply_markup=kb
    )

# ==============================

print("BOT ONLINE")
bot.infinity_polling()
