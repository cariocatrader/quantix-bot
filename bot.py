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

GIF_ANALISE = "analise.gif"
GIF_WIN = "win.gif"
GIF_LOSS = "loss.gif"

PARIDADES = [
    "EUR/USD","GBP/USD","USD/JPY","AUD/USD","USD/CAD",
    "USD/CHF","NZD/USD","EUR/GBP","EUR/JPY","GBP/JPY"
]

BANDERAS = {
    "EUR/USD":"🇪🇺🇺🇸","GBP/USD":"🇬🇧🇺🇸","USD/JPY":"🇺🇸🇯🇵",
    "AUD/USD":"🇦🇺🇺🇸","USD/CAD":"🇺🇸🇨🇦","USD/CHF":"🇺🇸🇨🇭",
    "NZD/USD":"🇳🇿🇺🇸","EUR/GBP":"🇪🇺🇬🇧",
    "EUR/JPY":"🇪🇺🇯🇵","GBP/JPY":"🇬🇧🇯🇵"
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
            return None

        return data["values"]

    except:
        return None

# ==============================
# ANALISE (mantida igual)
# ==============================

def analisar(candles):

    if len(candles) < 4:
        return None

    ultimos = candles[1:4]

    altas = sum(
        float(c["close"]) > float(c["open"])
        for c in ultimos
    )

    baixas = 3 - altas

    if altas >= 2:
        return "CALL"

    if baixas >= 2:
        return "PUT"

    return None

# ==============================
# HORÁRIO ENTRADA
# ==============================

def proxima_entrada_real():

    agora = datetime.now(timezone)

    entrada = agora.replace(
        second=0,
        microsecond=0
    ) + timedelta(minutes=1)

    return entrada

# ==============================
# ESPERA
# ==============================

def esperar_ate(timestamp):

    while True:

        agora = datetime.now(timezone)

        if agora >= timestamp:
            break

        time.sleep(0.2)

# ==============================
# RESULTADO SINCRONIZADO
# ==============================

def resultado_real(paridade, direcao, horario_entrada):

    time.sleep(5)  # segurança extra

    candles = buscar_candles(paridade)

    if not candles:
        return "LOSS"

    horario_str = horario_entrada.strftime("%Y-%m-%d %H:%M:%S")

    candle_encontrado = None

    for c in candles:

        if c["datetime"] == horario_str:

            candle_encontrado = c
            break

    if not candle_encontrado:

        print("CANDLE NÃO ENCONTRADO:", horario_str)

        return "LOSS"

    open_price = float(candle_encontrado["open"])
    close_price = float(candle_encontrado["close"])

    print(
        "DEBUG:",
        candle_encontrado["datetime"],
        open_price,
        close_price
    )

    if close_price > open_price:

        return "WIN" if direcao == "CALL" else "LOSS"

    elif close_price < open_price:

        return "WIN" if direcao == "PUT" else "LOSS"

    else:

        return "LOSS"

# ==============================
# START
# ==============================

@bot.message_handler(commands=["start"])
def start(m):

    kb = InlineKeyboardMarkup()

    kb.add(
        InlineKeyboardButton(
            "🚀 Gerar Sinal",
            callback_data="gerar"
        )
    )

    bot.send_message(
        m.chat.id,
        "👋 Bem-vindo ao Quantix",
        reply_markup=kb
    )

# ==============================
# PARIDADES
# ==============================

@bot.callback_query_handler(func=lambda c: c.data == "gerar")
def paridades(c):

    bot.delete_message(
        c.message.chat.id,
        c.message.message_id
    )

    kb = InlineKeyboardMarkup()

    for p in PARIDADES:

        kb.add(
            InlineKeyboardButton(
                f"{BANDERAS[p]} {p}",
                callback_data=f"p_{p}"
            )
        )

    bot.send_message(
        c.message.chat.id,
        "📊 Escolha a paridade:",
        reply_markup=kb
    )

# ==============================
# EXECUÇÃO
# ==============================

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_"))
def run(c):

    par = c.data.split("_")[1]

    bot.delete_message(
        c.message.chat.id,
        c.message.message_id
    )

    msg = bot.send_animation(
        c.message.chat.id,
        open(GIF_ANALISE, "rb"),
        caption="🔎 Quantix está analisando o mercado..."
    )

    candles = None
    sinal = None

    start_time = time.time()

    while time.time() - start_time < 60:

        candles = buscar_candles(par)

        if candles:

            sinal = analisar(candles)

            if sinal:
                break

        time.sleep(2)

    try:
        bot.delete_message(
            c.message.chat.id,
            msg.message_id
        )
    except:
        pass

    if not sinal:

        bot.send_message(
            c.message.chat.id,
            "❌ Nenhum sinal válido encontrado."
        )

        return

    entrada = proxima_entrada_real()

    gale = entrada + timedelta(minutes=1)

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

    esperar_ate(entrada)

    fechamento = entrada + timedelta(minutes=1)

    esperar_ate(fechamento)

    resultado = resultado_real(
        par,
        sinal,
        entrada
    )

    if resultado == "LOSS":

        bot.send_message(
            c.message.chat.id,
            "⚠️ Entrando em GALE 1..."
        )

        fechamento_gale = gale + timedelta(minutes=1)

        esperar_ate(fechamento_gale)

        resultado = resultado_real(
            par,
            sinal,
            gale
        )

    gif = GIF_WIN if resultado == "WIN" else GIF_LOSS

    bot.send_animation(
        c.message.chat.id,
        open(gif, "rb"),
        caption=f"""
📊 SINAL GERADO:

📊 Paridade: {BANDERAS[par]} {par}
⏱ Timeframe: M1
🎯 Entrada: {entrada.strftime('%H:%M')} ({sinal})
⏳ Gale: {gale.strftime('%H:%M')}

📊 Resultado: {resultado}
"""
    )

    kb = InlineKeyboardMarkup()

    kb.add(
        InlineKeyboardButton(
            "🚀 Novo Sinal",
            callback_data="gerar"
        )
    )

    bot.send_message(
        c.message.chat.id,
        "🔁 Operação finalizada",
        reply_markup=kb
    )

print("BOT ONLINE")

bot.infinity_polling(
    timeout=60,
    long_polling_timeout=60,
    skip_pending=True
)
