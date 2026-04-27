import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
from datetime import datetime, timedelta
import pytz
import os
import threading

# ==============================
# CONFIG
# ==============================

TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")

bot = telebot.TeleBot(TOKEN, threaded=True)

timezone = pytz.timezone("America/Sao_Paulo")

GIF_ANALISE = "analise.gif"
GIF_WIN = "win.gif"
GIF_LOSS = "loss.gif"

PARIDADES = [
    "EUR/USD","GBP/USD","USD/JPY","AUD/USD","USD/CAD",
    "USD/CHF","NZD/USD","EUR/GBP","EUR/JPY","GBP/JPY"
]

BANDERAS = {
    "EUR/USD":"🇪🇺🇺🇸",
    "GBP/USD":"🇬🇧🇺🇸",
    "USD/JPY":"🇺🇸🇯🇵",
    "AUD/USD":"🇦🇺🇺🇸",
    "USD/CAD":"🇺🇸🇨🇦",
    "USD/CHF":"🇺🇸🇨🇭",
    "NZD/USD":"🇳🇿🇺🇸",
    "EUR/GBP":"🇪🇺🇬🇧",
    "EUR/JPY":"🇪🇺🇯🇵",
    "GBP/JPY":"🇬🇧🇯🇵"
}

# ==============================
# API
# ==============================

def buscar_candles(paridade):
    url = f"https://api.twelvedata.com/time_series?symbol={paridade}&interval=1min&outputsize=10&apikey={API_KEY}"

    try:
        r = requests.get(url, timeout=10)
        data = r.json()

        if "values" not in data:
            print("Erro API:", data)
            return None

        return data["values"]

    except Exception as e:
        print("Erro buscar candles:", e)
        return None

# ==============================
# ANALISE
# ==============================

def analisar(candles):
    if len(candles) < 4:
        return None

    ultimos = candles[1:4]

    altas = sum(float(c["close"]) > float(c["open"]) for c in ultimos)
    baixas = 3 - altas

    if altas >= 2:
        return "CALL"
    if baixas >= 2:
        return "PUT"

    return None

# ==============================
# TEMPO
# ==============================

def proxima_entrada_real():
    agora = datetime.now(timezone)
    entrada = agora.replace(second=0, microsecond=0) + timedelta(minutes=1)
    return entrada

def esperar_ate(timestamp):
    while True:
        if datetime.now(timezone) >= timestamp:
            break
        time.sleep(0.5)

# ==============================
# RESULTADO
# ==============================

def resultado_real(paridade, direcao, horario_base):
    horario_candle = (
        datetime.strptime(horario_base, "%H:%M") + timedelta(minutes=1)
    ).strftime("%H:%M")

    for _ in range(6):

        candles = buscar_candles(paridade)
        if not candles:
            time.sleep(2)
            continue

        for c in candles:
            try:
                candle_time = datetime.strptime(c["datetime"], "%Y-%m-%d %H:%M:%S")
                candle_time = pytz.utc.localize(candle_time).astimezone(timezone)

                if candle_time.strftime("%H:%M") == horario_candle:

                    open_price = float(c["open"])
                    close_price = float(c["close"])

                    if close_price > open_price:
                        result = "CALL"
                    elif close_price < open_price:
                        result = "PUT"
                    else:
                        return "DOJI"

                    return "WIN" if result == direcao else "LOSS"

            except:
                continue

        time.sleep(2)

    return "LOSS"

# ==============================
# START
# ==============================

@bot.message_handler(commands=["start"])
def start(m):

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Gerar Sinal", callback_data="gerar"))

    bot.send_message(
        m.chat.id,
        "👋 Bem-vindo ao Quantix",
        reply_markup=kb
    )

# ==============================
# MENU PARIDADES
# ==============================

@bot.callback_query_handler(func=lambda c: c.data == "gerar")
def escolher_par(c):
    bot.answer_callback_query(c.id)

    kb = InlineKeyboardMarkup(row_width=2)

    for par in PARIDADES:
        kb.add(InlineKeyboardButton(par, callback_data=f"p_{par}"))

    bot.send_message(c.message.chat.id, "📊 Escolha a paridade:", reply_markup=kb)

# ==============================
# EXECUÇÃO EM THREAD (CORREÇÃO PRINCIPAL)
# ==============================

def executar_sinal(chat_id, par):

    try:
        msg = bot.send_animation(
            chat_id,
            open(GIF_ANALISE, "rb"),
            caption="🔎 Analisando mercado..."
        )
    except:
        msg = None

    sinal = None
    start_time = time.time()

    while time.time() - start_time < 40:

        candles = buscar_candles(par)
        if candles:
            sinal = analisar(candles)
            if sinal:
                break

        time.sleep(2)

    if msg:
        try:
            bot.delete_message(chat_id, msg.message_id)
        except:
            pass

    if not sinal:
        bot.send_message(chat_id, "❌ Nenhum sinal válido encontrado.")
        return

    entrada = proxima_entrada_real()
    gale = entrada + timedelta(minutes=1)

    horario_entrada = entrada.strftime("%H:%M")
    horario_gale = gale.strftime("%H:%M")

    bot.send_message(
        chat_id,
        f"""
📊 SINAL GERADO:

📊 Paridade: {par}
⏱ Timeframe: M1
🎯 Entrada: {horario_entrada} ({sinal})
⏳ Gale: {horario_gale}
"""
    )

    esperar_ate(entrada + timedelta(minutes=1))
    time.sleep(10)

    resultado = resultado_real(par, sinal, horario_entrada)

    if resultado == "LOSS":

        bot.send_message(chat_id, "⚠️ Entrando em GALE 1...")

        esperar_ate(gale + timedelta(minutes=1))
        time.sleep(10)

        resultado = resultado_real(par, sinal, horario_gale)

    gif = GIF_WIN if resultado == "WIN" else GIF_LOSS

    try:
        bot.send_animation(
            chat_id,
            open(gif, "rb"),
            caption=f"📊 Resultado: {resultado}"
        )
    except:
        bot.send_message(chat_id, f"📊 Resultado: {resultado}")

# ==============================
# CALLBACK PARIDADE
# ==============================

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_"))
def run(c):

    bot.answer_callback_query(c.id)

    par = c.data.split("_")[1]

    threading.Thread(
        target=executar_sinal,
        args=(c.message.chat.id, par)
    ).start()

# ==============================
# START BOT
# ==============================

print("BOT ONLINE")

bot.infinity_polling(
    timeout=60,
    long_polling_timeout=60,
    skip_pending=True
)
