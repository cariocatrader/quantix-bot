import telebot
import os
import time

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    print("ERRO: TOKEN não encontrado")
    exit()

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

while True:
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)

    except Exception as e:
        print("Erro detectado:", e)
        time.sleep(5)
