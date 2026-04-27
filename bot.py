import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import time
import threading
from datetime import datetime, timedelta
import pytz
import os

TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN, threaded=False)

tz = pytz.timezone("America/Sao_Paulo")

GIF_ANALISE = "analise.gif"
GIF_WIN = "win.gif"
GIF_LOSS = "loss.gif"

# =========================
# PARIDADES
# =========================

PARIDADES = {
    "btc": "BTC/USDT",
    "eth": "ETH/USDT",
    "bnb": "BNB/USDT",
    "sol": "SOL/USDT",
    "xrp": "XRP/USDT",
    "ada": "ADA/USDT",
    "doge": "DOGE/USDT",
    "ltc": "LTC/USDT",
    "dot": "DOT/USDT",
    "avax": "AVAX/USDT"
}

# =========================
# UTILS
# =========================

def now():
    return datetime.now(tz)

def delete(chat, msg):
    try:
        bot.delete_message(chat, msg)
    except:
        pass

def btn_final():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Gerar novo sinal", callback_data="start"))
    return kb

def send_gif(chat, gif, text, kb=None):
    with open(gif, "rb") as f:
        return bot.send_animation(chat, f, caption=text, reply_markup=kb)

# =========================
# MENUS
# =========================

def menu_paridade():
    kb = InlineKeyboardMarkup(row_width=2)
    for k, v in PARIDADES.items():
        kb.add(InlineKeyboardButton(v, callback_data=f"p_{k}"))
    return kb

def menu_exp(coin):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("⚡ 1 MIN", callback_data=f"e_{coin}_1"),
        InlineKeyboardButton("🕐 5 MIN", callback_data=f"e_{coin}_5")
    )
    return kb

# =========================
# TEMPO
# =========================

def next_1m():
    n = now()
    return n.replace(second=0, microsecond=0) + timedelta(minutes=1)

def next_5m():
    n = now().replace(second=0, microsecond=0)
    return n + timedelta(minutes=(5 - n.minute % 5) % 5)

# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(m):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Gerar Sinal", callback_data="start"))
    bot.send_message(m.chat.id, "📊 Bot de Sinais Ativo", reply_markup=kb)

# =========================
# INÍCIO
# =========================

@bot.callback_query_handler(func=lambda c: c.data == "start")
def st(c):
    bot.answer_callback_query(c.id)
    delete(c.message.chat.id, c.message.message_id)

    bot.send_message(c.message.chat.id, "📊 Escolha a paridade:", reply_markup=menu_paridade())

# =========================
# PARIDADE
# =========================

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_"))
def par(c):
    coin = c.data.split("_")[1]
    bot.answer_callback_query(c.id)
    delete(c.message.chat.id, c.message.message_id)

    bot.send_message(
        c.message.chat.id,
        f"📈 Par: {PARIDADES[coin]}\nEscolha expiração:",
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
    gale = entrada + timedelta(minutes=exp)

    direcao = "COMPRA"

    send_gif(c.message.chat.id, GIF_ANALISE, "🔎 Analisando mercado...")

    bot.send_message(
        c.message.chat.id,
        f"""🚀 SINAL ENVIADO
━━━━━━━━━━━━━━
💱 Par: {PARIDADES[coin]}
📍 Entrada: {entrada.strftime('%H:%M')}
🎯 Direção: {direcao}
🔁 Gale: {gale.strftime('%H:%M')}
⏳ Expiração: {exp} min"""
    )

    # =========================
    # EXECUÇÃO REAL
    # =========================

    def run():
        try:
            time.sleep(exp * 60)

            resultado = "LOSS"  # substitui pela sua lógica real depois

            if resultado == "WIN":
                time.sleep(3)
                send_gif(
                    c.message.chat.id,
                    GIF_WIN,
                    f"""🏁 RESULTADO FINAL
━━━━━━━━━━━━━━
💱 Par: {PARIDADES[coin]}
📍 Entrada: {entrada.strftime('%H:%M')}
🎯 Direção: {direcao}
📊 Resultado: WIN""",
                    btn_final()
                )
                return

            # LOSS → GALE
            bot.send_message(
                c.message.chat.id,
                f"""⚠️ LOSS DETECTADO
━━━━━━━━━━━━━━
🔁 Entrando em GALE 1
📍 Entrada: {entrada.strftime('%H:%M')}
🔁 Gale: {gale.strftime('%H:%M')}"""
            )

            time.sleep(exp * 60)

            gale_result = "WIN"

            time.sleep(3)

            gif = GIF_WIN if gale_result == "WIN" else GIF_LOSS

            send_gif(
                c.message.chat.id,
                gif,
                f"""🏁 RESULTADO FINAL
━━━━━━━━━━━━━━
💱 Par: {PARIDADES[coin]}
📍 Entrada: {entrada.strftime('%H:%M')}
🔁 Gale: {gale.strftime('%H:%M')}
🎯 Direção: {direcao}
📊 Resultado: {gale_result}""",
                btn_final()
            )

        except Exception:
            send_gif(
                c.message.chat.id,
                GIF_LOSS,
                "⚠️ ERRO NO MERCADO - SINAL CANCELADO",
                btn_final()
            )

    threading.Thread(target=run).start()

# =========================
# LOOP
# =========================

print("BOT ONLINE - FLUXO FINAL LIMPO")

while True:
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=15)
    except Exception as e:
        print("Erro:", e)
        time.sleep(5)
