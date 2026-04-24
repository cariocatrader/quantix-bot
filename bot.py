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
# TEMPO
# ==============================

def entrada():
    agora = datetime.now(timezone)
    base = agora.replace(second=0, microsecond=0)

    if agora.second > 0:
        base += timedelta(minutes=1)

    return base + timedelta(minutes=1)

def gale_entrada(ent):
    return ent + timedelta(minutes=1)

def fechamento(base):
    return base + timedelta(minutes=1, seconds=5)

# ==============================
# API
# ==============================

def candles(par, tf="1min", limit=20):
    try:
        url = f"https://api.twelvedata.com/time_series?symbol={par}&interval={tf}&outputsize={limit}&apikey={API_KEY}"
        r = requests.get(url, timeout=10)
        data = r.json()

        if "values" not in data:
            return None

        return data["values"]

    except:
        return None

# ==============================
# RSI SIMPLES
# ==============================

def rsi(candles, period=14):

    closes = [float(c["close"]) for c in candles[:period+1]]

    gain = 0
    loss = 0

    for i in range(1, len(closes)):

        diff = closes[i] - closes[i-1]

        if diff > 0:
            gain += diff
        else:
            loss += abs(diff)

    if loss == 0:
        return 100

    rs = gain / loss

    return 100 - (100 / (1 + rs))

# ==============================
# M15 TENDÊNCIA (PRINCIPAL)
# ==============================

def tendencia_m15(c):

    ult = c[:5]

    altas = sum(float(x["close"]) > float(x["open"]) for x in ult)
    baixas = 5 - altas

    if altas > baixas:
        return "CALL"
    elif baixas > altas:
        return "PUT"

    return None

# ==============================
# M1 CONFIRMAÇÃO
# ==============================

def tendencia_m1(c):

    ult = c[:3]

    altas = sum(float(x["close"]) > float(x["open"]) for x in ult)
    baixas = 3 - altas

    if altas >= 2:
        return "CALL"
    if baixas >= 2:
        return "PUT"

    return None

# ==============================
# SINAL FINAL (AJUSTADO)
# ==============================

def sinal(par):

    m1 = candles(par, "1min", 10)
    m15 = candles(par, "15min", 10)

    if not m1 or not m15:
        return None, None

    t15 = tendencia_m15(m15)
    t1 = tendencia_m1(m1)

    r = rsi(m1)

    analise = {
        "M15": t15,
        "M1": t1,
        "RSI": round(r, 2)
    }

    # filtro leve RSI (não bloqueia tudo)
    if r > 80:
        t15 = "PUT" if t15 == "CALL" else t15
    if r < 20:
        t15 = "CALL" if t15 == "PUT" else t15

    # decisão principal
    if t15:
        return t15, analise

    return None, analise

# ==============================
# RESULTADO
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

    bot.send_message(m.chat.id, "👋 Quantix PRO", reply_markup=kb)

# ==============================
# PARIDADES
# ==============================

@bot.callback_query_handler(func=lambda c: c.data == "gerar")
def pares(c):

    bot.delete_message(c.message.chat.id, c.message.message_id)

    kb = InlineKeyboardMarkup()

    for p in PARIDADES:
        kb.add(InlineKeyboardButton(f"{BANDERAS[p]} {p}", callback_data=f"p_{p}"))

    bot.send_message(c.message.chat.id, "📊 Escolha:", reply_markup=kb)

# ==============================
# EXECUÇÃO
# ==============================

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_"))
def run(c):

    par = c.data.split("_")[1]

    bot.delete_message(c.message.chat.id, c.message.message_id)

    msg = bot.send_animation(
        c.message.chat.id,
        open(GIF_ANALISE, "rb"),
        caption="🔎 Analisando mercado..."
    )

    sig, analise = sinal(par)

    bot.delete_message(c.message.chat.id, msg.message_id)

    if not sig:
        bot.send_message(
            c.message.chat.id,
            f"""
📊 ANÁLISE

M15: {analise['M15']}
M1: {analise['M1']}
RSI: {analise['RSI']}

❌ Sem entrada no momento
"""
        )
        return

    ent = entrada()
    gale_ent = gale_entrada(ent)

    bot.send_message(
        c.message.chat.id,
        f"""
📊 SINAL GERADO:

💱 {par}
🎯 {sig}

📈 ANÁLISE:
M15: {analise['M15']}
M1: {analise['M1']}
RSI: {analise['RSI']}

⏱ Entrada: {ent.strftime('%H:%M')}
⚠️ GALE 1: {gale_ent.strftime('%H:%M')}
"""
    )

    time.sleep((fechamento(ent) - datetime.now(timezone)).total_seconds())

    res = result(par, sig)

    gale = 0

    if res == "LOSS":

        gale = 1

        bot.send_message(c.message.chat.id, "⚠️ LOSS → GALE 1")

        time.sleep((fechamento(gale_ent) - datetime.now(timezone)).total_seconds())

        res = result(par, sig)

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
📊 RESULTADO FINAL:

💱 {par}
🎯 Resultado: {res}
🔥 GALE: {gale}
""",
        reply_markup=kb
    )

# ==============================

print("BOT ONLINE")
bot.infinity_polling()
