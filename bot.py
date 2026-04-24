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
# TIME ENGINE (PRÓXIMO MINUTO REAL)
# ==============================

def proximo_minuto():

    agora = datetime.now(timezone)

    base = agora.replace(second=0, microsecond=0)

    if agora.second > 0:
        base += timedelta(minutes=1)

    return base + timedelta(minutes=1)

# ==============================
# API REAL (SEM FALLBACK)
# ==============================

def buscar_candles(paridade):

    url = f"https://api.twelvedata.com/time_series?symbol={paridade}&interval=1min&outputsize=10&apikey={API_KEY}"

    try:
        r = requests.get(url, timeout=10)
        data = r.json()

        if "values" not in data:
            return None

        return data["values"]

    except:
        return None

# ==============================
# ANÁLISE REAL (3 CANDLES)
# ==============================

def analisar(candles):

    ultimos = candles[:3]

    altas = 0
    baixas = 0

    for c in ultimos:

        if float(c["close"]) > float(c["open"]):
            altas += 1
        else:
            baixas += 1

    if altas >= 2:
        return "CALL"

    if baixas >= 2:
        return "PUT"

    return None

# ==============================
# RESULTADO REAL
# ==============================

def resultado(paridade, direcao):

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

@bot.callback_query_handler(func=lambda c: c.data == "gerar")
def paridades(c):

    bot.delete_message(c.message.chat.id, c.message.message_id)

    kb = InlineKeyboardMarkup()

    for p in PARIDADES:
        kb.add(InlineKeyboardButton(f"{BANDERAS[p]} {p}", callback_data=f"p_{p}"))

    bot.send_message(c.message.chat.id, "📊 Escolha a paridade:", reply_markup=kb)

# ==============================
# EXECUÇÃO PRINCIPAL
# ==============================

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_"))
def run(c):

    par = c.data.split("_")[1]

    bot.delete_message(c.message.chat.id, c.message.message_id)

    # ================= ANALISE =================
    try:
        msg = bot.send_animation(
            c.message.chat.id,
            open(GIF_ANALISE, "rb"),
            caption="🔎 Analisando mercado..."
        )
    except:
        msg = bot.send_message(c.message.chat.id, "🔎 Analisando mercado...")

    candles = None
    sinal = None

    start = time.time()
    tentativas = 0

    while time.time() - start < 60 and tentativas < 20:

        candles = buscar_candles(par)

        if candles:
            sinal = analisar(candles)

            if sinal:
                break

        tentativas += 1
        time.sleep(2)

    try:
        bot.delete_message(c.message.chat.id, msg.message_id)
    except:
        pass

    if not sinal:
        bot.send_message(c.message.chat.id, "❌ Sem sinal válido (mercado lateral ou API indisponível).")
        return

    entrada = proximo_minuto()

    bot.send_message(
        c.message.chat.id,
        f"""
📊 NOVO SINAL

💱 {par}
🕐 Entrada: {entrada.strftime('%H:%M')}
🎯 Direção: {sinal}
🔥 Base: 3 candles reais
"""
    )

    # ================= ESPERA =================

    time.sleep(60)

    res = resultado(par, sinal)

    gale = 0

    if res == "LOSS":

        gale = 1

        bot.send_message(
            c.message.chat.id,
            "⚠️ LOSS detectado\n🔄 Entrando em GALE 1..."
        )

        time.sleep(60)

        res = resultado(par, sinal)

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
🔥 Gale usado: {gale}
""",
        reply_markup=kb
    )

# ==============================

print("BOT ONLINE")
bot.infinity_polling()
