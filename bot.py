import telebot
import os
import time
import requests
import pytz

from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")

bot = telebot.TeleBot(TOKEN)

# FUSO HORÁRIO BRASIL
fuso_brasil = pytz.timezone("America/Sao_Paulo")

# PARIDADES
paridades = [
    ("🇪🇺 EUR/USD", "EURUSD"),
    ("🇬🇧 GBP/USD", "GBPUSD"),
    ("🇺🇸 USD/JPY", "USDJPY"),
    ("🇦🇺 AUD/USD", "AUDUSD"),
    ("🇨🇦 USD/CAD", "USDCAD"),
    ("🇳🇿 NZD/USD", "NZDUSD"),
    ("🇪🇺 EUR/JPY", "EURJPY"),
    ("🇪🇺 EUR/GBP", "EURGBP"),
    ("🇬🇧 GBP/JPY", "GBPJPY"),
    ("🇦🇺 AUD/JPY", "AUDJPY"),
    ("🇪🇺 EUR/AUD", "EURAUD"),
    ("🇬🇧 GBP/AUD", "GBPAUD"),
    ("🇦🇺 AUD/CAD", "AUDCAD"),
    ("🇪🇺 EUR/CAD", "EURCAD"),
    ("🇬🇧 GBP/CAD", "GBPCAD")
]

# OBTER CANDLES
def obter_candles(paridade):

    url = f"https://api.twelvedata.com/time_series?symbol={paridade}&interval=1min&outputsize=3&apikey={API_KEY}"

    try:

        response = requests.get(url)
        data = response.json()

        if "values" not in data:
            return None

        return data["values"]

    except:

        return None


# ANALISAR 3 VELAS
def analisar_velas(candles):

    positivas = 0
    negativas = 0

    for candle in candles:

        open_price = float(candle["open"])
        close_price = float(candle["close"])

        if close_price > open_price:
            positivas += 1

        elif close_price < open_price:
            negativas += 1

    if positivas == 3:
        return "PUT"

    if negativas == 3:
        return "CALL"

    return None


# START
@bot.message_handler(commands=['start'])
def start(message):

    markup = InlineKeyboardMarkup()

    botao = InlineKeyboardButton(
        "🚀 GERAR SINAL",
        callback_data="gerar_sinal"
    )

    markup.add(botao)

    bot.send_message(
        message.chat.id,
        "Olá, seja bem vindo ao Quantix 🤖\n\nClique abaixo para gerar seu sinal:",
        reply_markup=markup
    )


# GERAR SINAL
@bot.callback_query_handler(func=lambda call: call.data == "gerar_sinal")
def gerar_sinal(call):

    bot.answer_callback_query(call.id)

    markup = InlineKeyboardMarkup(row_width=2)

    botoes = []

    for nome, codigo in paridades:

        botoes.append(
            InlineKeyboardButton(
                nome,
                callback_data=f"par_{codigo}"
            )
        )

    markup.add(*botoes)

    bot.send_message(
        call.message.chat.id,
        "📊 Escolha a paridade:",
        reply_markup=markup
    )


# ESCOLHER PARIDADE
@bot.callback_query_handler(func=lambda call: call.data.startswith("par_"))
def escolher_paridade(call):

    bot.answer_callback_query(call.id)

    paridade = call.data.replace("par_", "")

    paridade_formatada = paridade[:3] + "/" + paridade[3:]

    # GIF ANALISE
    try:

        bot.send_animation(
            call.message.chat.id,
            open("analise.gif", "rb"),
            caption="🔍 Aguarde enquanto o Quantix procura a melhor entrada..."
        )

    except:

        bot.send_message(
            call.message.chat.id,
            "🔍 Analisando mercado..."
        )

    # PROCURAR SINAL POR ATÉ 2 MINUTOS
    tempo_inicio = time.time()
    direcao = None

    while time.time() - tempo_inicio < 120:

        candles = obter_candles(paridade_formatada)

        if candles:

            direcao = analisar_velas(candles)

            if direcao:
                break

        time.sleep(5)

    if direcao is None:

        bot.send_message(
            call.message.chat.id,
            "❌ Sinal não encontrado."
        )

        return

    # HORA BRASIL
    agora = datetime.now(fuso_brasil)

    entrada = agora.strftime("%H:%M")

    gale1 = (agora + timedelta(minutes=1)).strftime("%H:%M")

    mensagem = f"""
🚨 SINAL ENCONTRADO 🚨

📊 Paridade: {paridade_formatada}
⏰ Entrada: {entrada}
⏳ Expiração: 1 minuto
♻️ Gale 1: {gale1}

📈 Direção: {direcao}
"""

    # GIF SINAL
    try:

        bot.send_animation(
            call.message.chat.id,
            open("sinal.gif", "rb"),
            caption=mensagem
        )

    except:

        bot.send_message(
            call.message.chat.id,
            mensagem
        )

    # AGUARDAR RESULTADO
    time.sleep(60)

    resultado = verificar_resultado(
        paridade_formatada,
        direcao
    )

    mostrar_resultado(
        call.message.chat.id,
        resultado
    )


# VERIFICAR RESULTADO
def verificar_resultado(paridade, direcao):

    candles = obter_candles(paridade)

    if candles is None:
        return "LOSS"

    ultimo = candles[0]

    open_price = float(ultimo["open"])
    close_price = float(ultimo["close"])

    if direcao == "CALL" and close_price > open_price:
        return "WIN"

    if direcao == "PUT" and close_price < open_price:
        return "WIN"

    return "LOSS"


# MOSTRAR RESULTADO
def mostrar_resultado(chat_id, resultado):

    markup = InlineKeyboardMarkup()

    botao = InlineKeyboardButton(
        "🔄 GERAR NOVO SINAL",
        callback_data="gerar_sinal"
    )

    markup.add(botao)

    if resultado == "WIN":

        try:

            bot.send_animation(
                chat_id,
                open("win.gif", "rb"),
                caption="🟢 RESULTADO: WIN"
            )

        except:

            bot.send_message(
                chat_id,
                "🟢 RESULTADO: WIN"
            )

    else:

        try:

            bot.send_animation(
                chat_id,
                open("loss.gif", "rb"),
                caption="🔴 RESULTADO: LOSS"
            )

        except:

            bot.send_message(
                chat_id,
                "🔴 RESULTADO: LOSS"
            )

    bot.send_message(
        chat_id,
        "Clique abaixo para gerar outro sinal:",
        reply_markup=markup
    )


print("Bot rodando...")

while True:

    try:

        bot.infinity_polling(
            timeout=60,
            long_polling_timeout=60
        )

    except Exception as e:

        print("Erro detectado:", e)

        time.sleep(5)
