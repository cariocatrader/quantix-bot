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

fuso_brasil = pytz.timezone("America/Sao_Paulo")

mensagens_ativas = {}

paridades = [
    ("🇪🇺 EUR/USD", "EURUSD"),
    ("🇬🇧 GBP/USD", "GBPUSD"),
    ("🇺🇸 USD/JPY", "USDJPY"),
    ("🇪🇺 EUR/JPY", "EURJPY"),
    ("🇬🇧 GBP/JPY", "GBPJPY")
]

# BOTÃO NOVO SINAL

def botao_novo_sinal():

    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton(
            "🔄 GERAR NOVO SINAL",
            callback_data="gerar_sinal"
        )
    )

    return markup


# HORÁRIO ENTRADA

def calcular_horario_entrada():

    agora = datetime.now(fuso_brasil)

    if agora.second >= 30:

        entrada = agora + timedelta(minutes=2)

    else:

        entrada = agora + timedelta(minutes=1)

    entrada = entrada.replace(second=0, microsecond=0)

    gale1 = entrada + timedelta(minutes=1)

    return entrada, gale1


# ESPERAR RESULTADO

def esperar_ate(horario):

    while True:

        agora = datetime.now(fuso_brasil)

        if agora >= horario:
            break

        time.sleep(1)


# OBTER CANDLES

def obter_candles(paridade):

    url = f"https://api.twelvedata.com/time_series?symbol={paridade}&interval=1min&outputsize=3&apikey={API_KEY}"

    try:

        r = requests.get(url)
        data = r.json()

        if "values" not in data:
            return None

        return data["values"]

    except:

        return None


# ANALISAR 3 VELAS

def analisar_velas(candles):

    positivas = 0
    negativas = 0

    for c in candles:

        o = float(c["open"])
        cl = float(c["close"])

        if cl > o:
            positivas += 1

        elif cl < o:
            negativas += 1

    if positivas == 3:
        return "PUT"

    if negativas == 3:
        return "CALL"

    return None


# GERAR GRÁFICO

def gerar_grafico(paridade):

    par_tv = paridade.replace("/", "")

    url = f"https://s.tradingview.com/widgetembed/?symbol=FX:{par_tv}&interval=1&theme=dark"

    return url


# START

@bot.message_handler(commands=['start'])
def start(message):

    msg = bot.send_message(
        message.chat.id,
        "Olá, seja bem vindo ao Quantix 🤖",
        reply_markup=botao_novo_sinal()
    )

    mensagens_ativas[message.chat.id] = msg.message_id


# GERAR SINAL

@bot.callback_query_handler(func=lambda call: call.data == "gerar_sinal")
def gerar_sinal(call):

    chat_id = call.message.chat.id

    if chat_id in mensagens_ativas:

        try:
            bot.delete_message(chat_id, mensagens_ativas[chat_id])
        except:
            pass

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

    msg = bot.send_message(
        chat_id,
        "📊 Escolha a paridade:",
        reply_markup=markup
    )

    mensagens_ativas[chat_id] = msg.message_id


# ESCOLHER PARIDADE

@bot.callback_query_handler(func=lambda call: call.data.startswith("par_"))
def escolher_paridade(call):

    chat_id = call.message.chat.id

    if chat_id in mensagens_ativas:

        try:
            bot.delete_message(chat_id, mensagens_ativas[chat_id])
        except:
            pass

    paridade = call.data.replace("par_", "")

    par_formatada = paridade[:3] + "/" + paridade[3:]

    msg = bot.send_message(
        chat_id,
        "🔍 Analisando mercado..."
    )

    mensagens_ativas[chat_id] = msg.message_id

    tempo_inicio = time.time()
    direcao = None

    while time.time() - tempo_inicio < 120:

        candles = obter_candles(par_formatada)

        if candles:

            direcao = analisar_velas(candles)

            if direcao:
                break

        time.sleep(5)

    if direcao is None:

        bot.delete_message(chat_id, mensagens_ativas[chat_id])

        msg = bot.send_message(
            chat_id,
            "❌ Sinal não encontrado.",
            reply_markup=botao_novo_sinal()
        )

        mensagens_ativas[chat_id] = msg.message_id

        return

    entrada, gale1 = calcular_horario_entrada()

    fechamento_1 = entrada + timedelta(minutes=1)
    envio_1 = fechamento_1 + timedelta(seconds=5)

    fechamento_gale = gale1 + timedelta(minutes=1)
    envio_gale = fechamento_gale + timedelta(seconds=5)

    entrada_str = entrada.strftime("%H:%M")
    gale_str = gale1.strftime("%H:%M")

    bot.delete_message(chat_id, mensagens_ativas[chat_id])

    grafico_url = gerar_grafico(par_formatada)

    msg = bot.send_photo(
        chat_id,
        grafico_url,
        caption=f"""
🚨 SINAL ENCONTRADO 🚨

📊 Paridade: {par_formatada}
⏰ Entrada: {entrada_str}
♻️ Gale 1: {gale_str}
📈 Direção: {direcao}
"""
    )

    mensagens_ativas[chat_id] = msg.message_id

    # ESPERA PRIMEIRO RESULTADO

    esperar_ate(envio_1)

    resultado = verificar_resultado(
        par_formatada,
        direcao
    )

    if resultado == "WIN":

        bot.delete_message(chat_id, mensagens_ativas[chat_id])

        mostrar_resultado(chat_id, "WIN")

        return

    # GALE

    bot.send_message(
        chat_id,
        "♻️ LOSS — entrando em Gale 1..."
    )

    esperar_ate(envio_gale)

    resultado_gale = verificar_resultado(
        par_formatada,
        direcao
    )

    bot.delete_message(chat_id, mensagens_ativas[chat_id])

    if resultado_gale == "WIN":

        mostrar_resultado(chat_id, "WIN (GALE 1)")

    else:

        mostrar_resultado(chat_id, "LOSS")


def verificar_resultado(paridade, direcao):

    candles = obter_candles(paridade)

    if candles is None:
        return "LOSS"

    ultimo = candles[0]

    o = float(ultimo["open"])
    c = float(ultimo["close"])

    if direcao == "CALL" and c > o:
        return "WIN"

    if direcao == "PUT" and c < o:
        return "WIN"

    return "LOSS"


def mostrar_resultado(chat_id, resultado):

    msg = bot.send_message(
        chat_id,
        f"Resultado: {resultado}",
        reply_markup=botao_novo_sinal()
    )

    mensagens_ativas[chat_id] = msg.message_id


print("Bot rodando...")

while True:

    try:

        bot.infinity_polling()

    except Exception as e:

        print("Erro:", e)

        time.sleep(5)
