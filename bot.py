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
# API
# ==============================

def buscar_candles(paridade):
    url = f"https://api.twelvedata.com/time_series?symbol={paridade}&interval=1min&outputsize=5&apikey={API_KEY}"

    try:
        r = requests.get(url, timeout=10)
        data = r.json()

        if "values" not in data:
            return None

        return data["values"]

    except:
        return None

# ==============================
# ANALISE (3 CANDLES)
# ==============================

def analisar(candles):

    ultimos = candles[:3]

    altas = sum(float(c["close"]) > float(c["open"]) for c in ultimos)
    baixas = 3 - altas

    if altas >= 2:
        return "CALL"
    if baixas >= 2:
        return "PUT"

    return None

# ==============================
# SINCRONIZAÇÃO REAL POR TIMESTAMP
# ==============================

def proxima_entrada_real(candle):

    t = datetime.strptime(candle["datetime"], "%Y-%m-%d %H:%M:%S")
    t = t.replace(tzinfo=timezone)

    return t + timedelta(minutes=1)

def esperar_ate(timestamp):

    while True:

        agora = datetime.now(timezone)

        if agora >= timestamp:
            break

        time.sleep(0.2)

# ==============================
# RESULTADO REAL
# ==============================

def resultado_real(paridade, direcao):

    url = f"https://api.twelvedata.com/time_series?symbol={paridade}&interval=1min&outputsize=2&apikey={API_KEY}"

    r = requests.get(url, timeout=10)
    data = r.json()

    candle = data["values"][0]

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

    bot.send_message(m.chat.id, "👋 Bem-vindo ao Quantix", reply_markup=kb)

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

    candles = None
    sinal = None

    start = time.time()

    while time.time() - start < 60:

        candles = buscar_candles(par)

        if candles:
            sinal = analisar(candles)
            if sinal:
                break

        time.sleep(2)

    try:
        bot.delete_message(c.message.chat.id, msg.message_id)
    except:
        pass

    if not sinal:
        bot.send_message(c.message.chat.id, "❌ Sem sinal válido.")
        return

    # ==============================
    # SINCRONIZAÇÃO REAL
    # ==============================

    candle_atual = candles[0]
    entrada = proxima_entrada_real(candle_atual)
    gale = entrada + timedelta(minutes=1)

    # ==============================
    # SINAL FORMATADO
    # ==============================

    bot.send_message(
        c.message.chat.id,
        f"""
📊 SINAL GERADO:

📊 Paridade: {BANDERAS[par]} {par}
⏱ Timeframe: M1
🎯 Entrada: {entrada.strftime('%H:%M')} ({sinal})
⏳ Gale: {gale.strftime('%H:%M')}
"""
    )

    # ==============================
    # ESPERA SINCRONIZADA (API)
    # ==============================

    esperar_ate(entrada)

    # ==============================
    # RESULTADO
    # ==============================

    res = resultado_real(par, sinal)

    if res == "LOSS":

        bot.send_message(c.message.chat.id, "⚠️ Entrando em GALE 1...")

        esperar_ate(gale)

        res = resultado_real(par, sinal)

    # ==============================
    # FINAL
    # ==============================

    gif = GIF_WIN if res == "WIN" else GIF_LOSS

    bot.send_animation(
        c.message.chat.id,
        open(gif, "rb"),
        caption=f"""
📊 SINAL GERADO:

📊 Paridade: {BANDERAS[par]} {par}
⏱ Timeframe: M1
🎯 Entrada: {entrada.strftime('%H:%M')} ({sinal})
⏳ Gale: {gale.strftime('%H:%M')}

📊 Resultado: {res}
"""
    )

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Novo Sinal", callback_data="gerar"))

    bot.send_message(c.message.chat.id, "🔁 Operação finalizada", reply_markup=kb)

# ==============================

print("BOT ONLINE")
bot.infinity_polling()
