import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
from datetime import datetime, timedelta
import pytz
import os

# ==============================
# CONFIGURAÇÕES
# ==============================

TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")

bot = telebot.TeleBot(TOKEN)

timezone = pytz.timezone("America/Sao_Paulo")

PARIDADES = [
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "AUD/USD",
    "USD/CAD",
    "USD/CHF",
    "NZD/USD",
    "EUR/GBP",
    "EUR/JPY",
    "GBP/JPY"
]

# ==============================
# BANDEIRAS
# ==============================

BANDERAS = {
    "EUR/USD": "🇪🇺🇺🇸",
    "GBP/USD": "🇬🇧🇺🇸",
    "USD/JPY": "🇺🇸🇯🇵",
    "AUD/USD": "🇦🇺🇺🇸",
    "USD/CAD": "🇺🇸🇨🇦",
    "USD/CHF": "🇺🇸🇨🇭",
    "NZD/USD": "🇳🇿🇺🇸",
    "EUR/GBP": "🇪🇺🇬🇧",
    "EUR/JPY": "🇪🇺🇯🇵",
    "GBP/JPY": "🇬🇧🇯🇵"
}

GIF_ANALISE = "analise.gif"
GIF_WIN = "win.gif"
GIF_LOSS = "loss.gif"

# ==============================
# 🔊 NOVO: ÁUDIOS
# ==============================

AUDIO_WIN = "win.mp3"
AUDIO_LOSS = "loss.mp3"

# ==============================

def calcular_proximo_minuto():

    agora = datetime.now(timezone)

    if agora.second >= 30:
        minuto = agora + timedelta(minutes=2)
    else:
        minuto = agora + timedelta(minutes=1)

    return minuto.replace(second=0, microsecond=0)

# ==============================

def aguardar_resultado(minuto):

    fechamento = minuto + timedelta(minutes=1)

    envio = fechamento + timedelta(seconds=5)

    tempo = (envio - datetime.now(timezone)).total_seconds()

    if tempo > 0:
        time.sleep(tempo)

# ==============================

def buscar_candles(paridade):

    try:

        url = f"https://api.twelvedata.com/time_series?symbol={paridade}&interval=1min&outputsize=4&apikey={API_KEY}"

        r = requests.get(url)

        data = r.json()

        if "values" not in data:
            print("API sem values")
            return None

        candles = data["values"]

        if len(candles) < 3:
            print("Poucos candles")
            return None

        return candles

    except Exception as e:

        print("Erro buscar candles:", e)

        return None

# ==============================

def gerar_sinal(candles):

    try:

        c1 = candles[2]
        c2 = candles[1]
        c3 = candles[0]

        o1 = float(c1["open"])
        c1f = float(c1["close"])

        o2 = float(c2["open"])
        c2f = float(c2["close"])

        o3 = float(c3["open"])
        c3f = float(c3["close"])

        alta = sum([
            c1f > o1,
            c2f > o2,
            c3f > o3
        ])

        baixa = sum([
            c1f < o1,
            c2f < o2,
            c3f < o3
        ])

        if alta >= 2:
            return "CALL"

        if baixa >= 2:
            return "PUT"

        return None

    except:

        return None

# ==============================

def verificar_resultado(paridade, direcao):

    candles = buscar_candles(paridade)

    if not candles:
        return None

    candle = candles[1]

    open_price = float(candle["open"])
    close_price = float(candle["close"])

    if direcao == "CALL":
        return "WIN" if close_price > open_price else "LOSS"

    if direcao == "PUT":
        return "WIN" if close_price < open_price else "LOSS"

# ==============================

@bot.message_handler(commands=["start"])
def start(message):

    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton(
            "🚀 Gerar Sinal",
            callback_data="gerar"
        )
    )

    bot.send_message(
        message.chat.id,
        "👋 Olá, seja bem-vindo ao Quantix\n\nClique abaixo para gerar seu sinal.",
        reply_markup=markup
    )

# ==============================

@bot.callback_query_handler(func=lambda call: call.data == "gerar")
def escolher_paridade(call):

    bot.delete_message(
        call.message.chat.id,
        call.message.message_id
    )

    markup = InlineKeyboardMarkup()

    for p in PARIDADES:

        texto = f"{BANDERAS.get(p, '')} {p}"

        markup.add(
            InlineKeyboardButton(
                texto,
                callback_data=f"par_{p}"
            )
        )

    bot.send_message(
        call.message.chat.id,
        "📊 Escolha a paridade:",
        reply_markup=markup
    )

# ==============================

@bot.callback_query_handler(func=lambda call: call.data.startswith("par_"))
def analisar(call):

    paridade = call.data.split("_")[1]

    bot.delete_message(
        call.message.chat.id,
        call.message.message_id
    )

    msg = bot.send_animation(
        call.message.chat.id,
        open(GIF_ANALISE, "rb"),
        caption="🔎 Analisando o mercado..."
    )

    inicio = time.time()

    sinal = None

    while time.time() - inicio < 120:

        candles = buscar_candles(paridade)

        if candles:

            sinal = gerar_sinal(candles)

            if sinal:
                break

        time.sleep(2)

    bot.delete_message(
        call.message.chat.id,
        msg.message_id
    )

    if not sinal:

        markup = InlineKeyboardMarkup()

        markup.add(
            InlineKeyboardButton(
                "🔁 Gerar Novo Sinal",
                callback_data="gerar"
            )
        )

        bot.send_message(
            call.message.chat.id,
            "❌ Sinal não encontrado.",
            reply_markup=markup
        )

        return

    minuto = calcular_proximo_minuto()

    sinal_msg = bot.send_message(
        call.message.chat.id,
        f"""
📊 NOVO SINAL

💱 Paridade: {paridade}
🕐 Entrada: {minuto.strftime('%H:%M')}

🎯 Direção: {sinal}
🔥 Gale: 1
"""
    )

    aguardar_resultado(minuto)

    resultado = verificar_resultado(paridade, sinal)

    gale = 0

    if resultado == "LOSS":

        gale = 1

        aguardar_resultado(
            minuto + timedelta(minutes=1)
        )

        resultado = verificar_resultado(paridade, sinal)

    bot.delete_message(
        call.message.chat.id,
        sinal_msg.message_id
    )

    fechamento = minuto + timedelta(minutes=1)

    # ==============================
    # GIF RESULTADO
    # ==============================

    gif = GIF_WIN if resultado == "WIN" else GIF_LOSS

    bot.send_animation(
        call.message.chat.id,
        open(gif, "rb"),
        caption="📊 Resultado processado"
    )

    # ==============================
    # 🔊 SOM RESULTADO (NOVO)
    # ==============================

    audio = AUDIO_WIN if resultado == "WIN" else AUDIO_LOSS

    bot.send_audio(
        call.message.chat.id,
        open(audio, "rb")
    )

    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton(
            "🚀 Gerar Novo Sinal",
            callback_data="gerar"
        )
    )

    bot.send_message(
        call.message.chat.id,
        f"""
📊 RESULTADO

💱 {paridade}

🕐 Entrada: {minuto.strftime('%H:%M')}
🕐 Fechamento: {fechamento.strftime('%H:%M')}

🎯 Resultado: {resultado}

🔥 Gale usado: {gale}
""",
        reply_markup=markup
    )

# ==============================

print("BOT ONLINE...")

bot.infinity_polling()
