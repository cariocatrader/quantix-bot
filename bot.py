import telebot

TOKEN = "COLOQUE_SEU_TOKEN_AQUI"

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):

    bot.send_message(
        message.chat.id,
        """
Olá, seja bem vindo ao Quantix 🤖

Clique no botão abaixo para gerar seu sinal.
"""
    )

print("Bot rodando...")

bot.infinity_polling()
