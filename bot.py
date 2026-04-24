import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
from datetime import datetime, timedelta
import pytz
import random
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
    "EUR/JPY",
    "AUD/USD"
]

GIF_ANALISE = "analise.gif"
GIF_WIN = "win.gif"
GIF_LOSS = "loss.gif"

# ==============================
# FUNÇÕES AUXILIARES
# ==============================

def calcular_proximo_minuto():

    agora = datetime.now(timezone)

    if agora.second >= 30:
        minuto_entrada = agora + timedelta(minutes=2)
    else:
        minuto_entrada = agora + timedelta(minutes=1)

    minuto_entrada = minuto_entrada.replace(
        second=0,
        microsecond=0
    )

    return minuto_entrada


def aguardar_resultado(minuto_entrada):

    fechamento = minuto_entrada + timedelta(minutes=1)

    envio = fechamento + timedelta(seconds=5)

    tempo = (envio - datetime.now(timezone)).total_seconds()

    if tempo > 0:
        time.sleep(tempo)


def buscar_candles(paridade):

    try:

        url = f"https://api.twelvedata.com/time_series?symbol={paridade}&interval=1min&outputsize=3&apikey={API_KEY}"

        r = requests.get(url)
        data = r.json()

        if "values" not in data:
            return None

        candles = data["values"]

        return candles

    except Exception as e:
        print("Erro buscar candles:", e)
        return None


def gerar_sinal(candles):

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


def verificar_resultado_real(paridade, direcao):

    candles = buscar_candles(paridade)

    if candles is None:
        return None

    candle = candles[1]

    open_price = float(candle["open"])
    close_price = float(candle["close"])

    if direcao == "CALL":
        if close_price > open_price:
            return "WIN"
        else:
            return "LOSS"

    if direcao == "PUT":
        if close_price < open_price:
            return "WIN"
        else:
            return "LOSS"


def gerar_grafico(paridade):

    url = f"https://api.twelvedata.com/time_series?symbol={paridade}&interval=1min&outputsize=30&apikey={API_KEY}"

    r = requests.get(url)

    with open("grafico.png", "wb") as f:
        f.write(r.content)

    return "grafico.png"

# ==============================
# MENU INICIAL
# ==============================

@bot.message_handler(commands=["start"])
def start(message):

    markup = InlineKeyboardMarkup()

    btn = InlineKeyboardButton(
        "🚀 Gerar Sinal",
        callback_data="gerar"
    )

    markup.add(btn)

    bot.send_message(
        message.chat.id,
        "👋 Olá, seja bem-vindo ao *Quantix*\n\nClique abaixo para gerar seu sinal.",
        parse_mode="Markdown",
        reply_markup=markup
    )

# ==============================
# GERAR SINAL
# ==============================

@bot.callback_query_handler(func=lambda call: call.data == "gerar")
def escolher_paridade(call):

    bot.delete_message(
        call.message.chat.id,
        call.message.message_id
    )

    markup = InlineKeyboardMarkup()

    for p in PARIDADES:

        markup.add(
            InlineKeyboardButton(
                p,
                callback_data=f"par_{p}"
            )
        )

    bot.send_message(
        call.message.chat.id,
        "📊 Escolha a paridade:",
        reply_markup=markup
    )

# ==============================
# SELEÇÃO PARIDADE
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
        caption="🔎 Aguarde enquanto o Quantix procura a melhor entrada..."
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

    minuto_entrada = calcular_proximo_minuto()

    grafico = gerar_grafico(paridade)

    with open(grafico, "rb") as g:

        sinal_msg = bot.send_photo(
            call.message.chat.id,
            g,
            caption=f"""
📊 NOVO SINAL

💱 Paridade: {paridade}
🕐 Entrada: {minuto_entrada.strftime('%H:%M')}

🎯 Direção: {sinal}
🔥 Gale: 1
"""
        )

    aguardar_resultado(minuto_entrada)

    resultado = verificar_resultado_real(
        paridade,
        sinal
    )

    gale_usado = 0

    if resultado == "LOSS":

        gale_usado = 1

        aguardar_resultado(
            minuto_entrada + timedelta(minutes=1)
        )

        resultado = verificar_resultado_real(
            paridade,
            sinal
        )

    bot.delete_message(
        call.message.chat.id,
        sinal_msg.message_id
    )

    fechamento = minuto_entrada + timedelta(minutes=1)

    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton(
            "🚀 Gerar Novo Sinal",
            callback_data="gerar"
        )
    )

    gif = GIF_WIN if resultado == "WIN" else GIF_LOSS

    with open(gif, "rb") as g:

        bot.send_animation(
            call.message.chat.id,
            g,
            caption=f"""
📊 RESULTADO DA OPERAÇÃO

💱 Paridade: {paridade}

🕐 Entrada: {minuto_entrada.strftime('%H:%M')}
🕐 Fechamento: {fechamento.strftime('%H:%M')}

🎯 Resultado: {resultado}

🔥 Gale usado: {gale_usado}
""",
            reply_markup=markup
        )

# ==============================
# LOOP BOT
# ==============================

print("BOT ONLINE...")

bot.infinity_polling()
