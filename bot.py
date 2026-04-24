import telebot
import os
import time
import requests
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")

bot = telebot.TeleBot(TOKEN)

# LISTA PARIDADES
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

    response = requests.get(url)
    data = response.json()

    if "values" not in data:
        return None

    return data["values"]

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
        "Olá, seja bem vindo ao Quantix 🤖\n\nClique no botão abaixo para gerar seu sinal.",
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

    bot.send_message(
        call.message.chat.id,
        f"🔍 Aguarde... O Quantix está analisando {paridade_formatada} 👀"
    )

    candles = obter_candles(paridade_formatada)

    if candles is None:

        bot.send_message(
            call.message.chat.id,
            "❌ Erro ao buscar dados do mercado."
        )

        return

    direcao = analisar_velas(candles)

    if direcao is None:

        bot.send_message(
            call.message.chat.id,
            "❌ Nenhum sinal encontrado."
        )

        return

    agora = datetime.now()

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

    bot.send_message(
        call.message.chat.id,
        mensagem
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
