import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
from datetime import datetime, timedelta
import pytz
import os

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
def entrada():
    agora = datetime.now(timezone)
    return agora.replace(second=0, microsecond=0) + timedelta(minutes=1)

def gale_entrada(ent):
    return ent + timedelta(minutes=1)

# ==============================
def candles(par, tf="1min", limit=10):
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
def sinal(par):

    m15 = candles(par, "15min", 10)
    m1 = candles(par, "1min", 10)

    if not m15 or not m1:
        return None, None

    t15 = "CALL" if sum(float(c["close"]) > float(c["open"]) for c in m15[:5]) > 2 else "PUT"
    t1 = "CALL" if sum(float(c["close"]) > float(c["open"]) for c in m1[:3]) >= 2 else "PUT"

    return t15, {"M15": t15, "M1": t1}

# ==============================
def esperar_horario(target_time):

    while True:

        agora = datetime.now(timezone)

        if agora >= target_time:
            break

        time.sleep(0.5)

# ==============================
def resultado(par, direcao):

    for _ in range(5):  # retry seguro

        c = candles(par)

        if c and len(c) > 1:

            candle = c[1]

            if float(candle["close"]) > float(candle["open"]):
                return "WIN" if direcao == "CALL" else "LOSS"

            else:
                return "WIN" if direcao == "PUT" else "LOSS"

        time.sleep(1)

    return "LOSS"

# ==============================
@bot.message_handler(commands=["start"])
def start(m):

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Gerar Sinal", callback_data="gerar"))

    bot.send_message(m.chat.id, "👋 Olá seja bem vindo (a) ao Quantix PRO", reply_markup=kb)

# ==============================
@bot.callback_query_handler(func=lambda c: c.data == "gerar")
def pares(c):

    bot.delete_message(c.message.chat.id, c.message.message_id)

    kb = InlineKeyboardMarkup()

    for p in PARIDADES:
        kb.add(InlineKeyboardButton(f"{BANDERAS[p]} {p}", callback_data=f"p_{p}"))

    bot.send_message(c.message.chat.id, "📊 Escolha a paridade para operar:", reply_markup=kb)

# ==============================
@bot.callback_query_handler(func=lambda c: c.data.startswith("p_"))
def run(c):

    par = c.data.split("_")[1]

    bot.delete_message(c.message.chat.id, c.message.message_id)

    bot.send_animation(
        c.message.chat.id,
        open(GIF_ANALISE, "rb"),
        caption="🔎 Analisando mercado..."
    )

    sig, info = sinal(par)

    if not sig:
        bot.send_message(c.message.chat.id, "❌ Sem sinal")
        return

    ent = entrada()
    gale_ent = gale_entrada(ent)

    bot.send_message(
        c.message.chat.id,
        f"""
📊 SINAL GERADO:

💱 {par}
🎯 {sig}

📈 M15: {info['M15']}
📈 M1: {info['M1']}

⏱ Entrada: {ent.strftime('%H:%M')}
⚠️ GALE: {gale_ent.strftime('%H:%M')}
"""
    )

    # ==============================
    # RESULTADO 1
    # ==============================

    esperar_horario(ent + timedelta(minutes=1, seconds=5))

    res = resultado(par, sig)

    gale = 0

    # ==============================
    # GALE
    # ==============================

    if res == "LOSS":

        gale = 1

        bot.send_message(c.message.chat.id, "⚠️ LOSS → GALE 1")

        esperar_horario(gale_ent + timedelta(minutes=1, seconds=5))

        res = resultado(par, sig)

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
🎯 {res}
🔥 GALE: {gale}
""",
        reply_markup=kb
    )

# ==============================

print("BOT ONLINE")
bot.infinity_polling()
