import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import threading
import time
import pytz
import os
from datetime import datetime, timedelta

TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN, threaded=False)

tz = pytz.timezone("America/Sao_Paulo")

PARIDADES = {
    "btc": "BTC/USDT",
    "eth": "ETH/USDT",
    "sol": "SOL/USDT"
}

# =========================
# UTILS
# =========================

def now():
    return datetime.now(tz)

def delete(chat_id, msg_id):
    try:
        bot.delete_message(chat_id, msg_id)
    except:
        pass

def btn_new():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Gerar novo sinal", callback_data="start"))
    return kb

# =========================
# MENU PARIDADE
# =========================

def menu_paridade():
    kb = InlineKeyboardMarkup()
    for k, v in PARIDADES.items():
        kb.add(InlineKeyboardButton(v, callback_data=f"p_{k}"))
    return kb

# =========================
# MENU EXPIRAÇÃO
# =========================

def menu_exp(coin):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("⚡ 1 min", callback_data=f"e_{coin}_1"),
        InlineKeyboardButton("🕐 5 min", callback_data=f"e_{coin}_5")
    )
    return kb

# =========================
# TEMPOS
# =========================

def next_1m():
    n = now()
    return n.replace(second=0, microsecond=0) + timedelta(minutes=1)

def next_5m():
    n = now().replace(second=0, microsecond=0) + timedelta(minutes=1)
    return n + timedelta(minutes=(5 - n.minute % 5) % 5)

# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(m):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Gerar Sinal", callback_data="start"))
    bot.send_message(m.chat.id, "📊 Bot de Sinais", reply_markup=kb)

# =========================
# FLUXO INICIAL
# =========================

@bot.callback_query_handler(func=lambda c: c.data == "start")
def st(c):
    bot.answer_callback_query(c.id)
    delete(c.message.chat.id, c.message.message_id)

    msg = bot.send_message(c.message.chat.id, "📊 Escolha a paridade:", reply_markup=menu_paridade())
    bot.register_next_step_handler(msg, lambda _: None)

# =========================
# PARIDADE
# =========================

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_"))
def paridade(c):
    coin = c.data.split("_")[1]
    bot.answer_callback_query(c.id)

    delete(c.message.chat.id, c.message.message_id)

    bot.send_message(
        c.message.chat.id,
        f"📈 Par selecionado: {PARIDADES[coin]}\nAgora escolha expiração:",
        reply_markup=menu_exp(coin)
    )

# =========================
# EXECUÇÃO
# =========================

@bot.callback_query_handler(func=lambda c: c.data.startswith("e_"))
def exec(c):
    _, coin, exp = c.data.split("_")
    exp = int(exp)

    bot.answer_callback_query(c.id)
    delete(c.message.chat.id, c.message.message_id)

    entrada = next_1m() if exp == 1 else next_5m()
    direcao = "COMPRA"

    # SIMULAÇÃO DE ANÁLISE
    def run():
        time.sleep(2)

        resultado = "WIN"  # aqui depois você conecta sua lógica real

        bot.send_message(
            c.message.chat.id,
            f"""📊 RESULTADO FINAL
━━━━━━━━━━━━━━
💱 Par: {PARIDADES[coin]}
⏱ Entrada: {entrada.strftime('%H:%M')}
🎯 Direção: {direcao}
📊 Resultado: {resultado}""",
            reply_markup=btn_new()
        )

    bot.send_message(c.message.chat.id, "🔎 Analisando mercado...")
    threading.Thread(target=run).start()

# =========================
# LOOP
# =========================

print("BOT ONLINE")

while True:
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=15)
    except Exception as e:
        print("Erro:", e)
        time.sleep(5)
