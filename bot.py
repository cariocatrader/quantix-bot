import telebot
import os
import time
import requests
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")

bot = telebot.TeleBot(TOKEN)

# LISTA DAS 15 PARIDADES
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

# FUNÇÃO PARA OBTER CANDLES
def obter_candles(paridade):

    url = f"https://api.twelvedata.com/time_series?symbol={paridade}&interval=1min&outputsize=3&apikey={API_KEY}"

    response = requests.get(url)
    data = response.json()

    print("Resposta da API:", data)

    if "values" not in data:
        return None

    candles = data["values"]

    return candles


# COMANDO START
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
        "Olá, seja bem vindo ao Quantix 🤖\n\nClique no botão abaixo para gerar seu sinal."
    )

    bot.send_message(
        message.chat.id,
        "🚀 Clique abaixo para iniciar:",
        reply_markup=markup
    )


# BOTÃO GERAR SINAL
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


# QUANDO ESCOLHER PARIDADE
@bot.callback_query_handler(func=lambda call: call.data.startswith("par_"))
def escolher_paridade(call):

    bot.answer_callback_query(call.id)

    paridade = call.data.replace("par_", "")

    # Converter formato (EURUSD → EUR/USD)
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

    # DEBUG
    print("Candles recebidos:", candles)

    bot.send_message(
        call.message.chat.id,
        f"📊 Candles encontrados para {paridade_formatada} ✅"
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
