import telebot
import os
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.getenv("TOKEN")

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
        "Olá, seja bem vindo ao Quantix 🤖\n\nClique no botão abaixo para gerar seu sinal.",
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

    bot.send_message(
        call.message.chat.id,
        f"🔍 Aguarde... O Quantix está analisando {paridade} 👀"
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
