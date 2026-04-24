import telebot
import os
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.getenv("TOKEN")

bot = telebot.TeleBot(TOKEN)

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

# QUANDO CLICAR NO BOTÃO
@bot.callback_query_handler(func=lambda call: call.data == "gerar_sinal")
def gerar_sinal(call):

    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,
        "🔍 Aguarde... O Quantix está procurando a melhor entrada 👀"
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
