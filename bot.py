import telebot
import requests
import threading
import time
import os
from datetime import datetime

# =========================
# TOKEN
# =========================

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise Exception("TOKEN não encontrado")

bot = telebot.TeleBot(TOKEN)

# =========================
# CRIPTOS
# =========================

SYMBOLS = {
    "BTCUSDT": "₿ Bitcoin",
    "ETHUSDT": "Ξ Ethereum",
    "BNBUSDT": "🟡 BNB",
    "SOLUSDT": "🟣 Solana",
    "XRPUSDT": "💧 XRP",
    "ADAUSDT": "🔵 Cardano",
    "DOGEUSDT": "🐶 Doge",
    "LTCUSDT": "🪙 Litecoin",
    "DOTUSDT": "⚫ Polkadot",
    "AVAXUSDT": "🔺 Avalanche"
}

# =========================
# GIFS
# =========================

ANALISE_GIF = "analise.gif"
WIN_GIF = "win.gif"
LOSS_GIF = "loss.gif"

# =========================
# BINANCE SAFE REQUEST
# =========================

def get_candle(symbol):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=2"
        r = requests.get(url, timeout=5)
        data = r.json()

        candle = data[-2]

        open_price = float(candle[1])
        close_price = float(candle[4])

        return open_price, close_price

    except Exception as e:
        print("Erro candle:", e)
        return None

# =========================
# DIREÇÃO
# =========================

def analyze(symbol):
    candle = get_candle(symbol)

    if not candle:
        return None

    o, c = candle

    if c > o:
        return "COMPRA"
    elif c < o:
        return "VENDA"

    return None

# =========================
# RESULTADO REAL
# =========================

def result(symbol, direction):
    candle = get_candle(symbol)

    if not candle:
        return "LOSS"

    o, c = candle

    if direction == "COMPRA":
        return "WIN" if c > o else "LOSS"

    if direction == "VENDA":
        return "WIN" if c < o else "LOSS"

    return "LOSS"

# =========================
# BOTÃO RESTART
# =========================

def restart_btn():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(
        telebot.types.InlineKeyboardButton(
            "🚀 Gerar novo sinal",
            callback_data="restart"
        )
    )
    return kb

# =========================
# MENUS
# =========================

def menu_paridades():
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)

    for sym, name in SYMBOLS.items():
        kb.add(
            telebot.types.InlineKeyboardButton(
                name,
                callback_data=f"par_{sym}"
            )
        )

    return kb


def menu_exp(symbol):
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(
        telebot.types.InlineKeyboardButton("⚡ 1 Minuto", callback_data=f"exp_{symbol}_1"),
        telebot.types.InlineKeyboardButton("🕐 5 Minutos", callback_data=f"exp_{symbol}_5")
    )
    return kb

# =========================
# FLUXO PRINCIPAL
# =========================

def run_signal(chat_id, symbol, exp):

    # =========================
    # ANÁLISE (NÃO BLOQUEIA)
    # =========================

    bot.send_animation(
        chat_id,
        open(ANALISE_GIF, "rb"),
        caption="⏳ Aguarde enquanto o Quantix Cripto analisa a melhor entrada..."
    )

    def process():

        time.sleep(2)

        direction = analyze(symbol)

        if not direction:
            bot.send_message(chat_id, "❌ Sem sinal no momento")
            return

        entry_time = datetime.now().strftime("%H:%M:%S")

        bot.send_message(
            chat_id,
            f"""🚀 SINAL GERADO
━━━━━━━━━━━━━━
💱 {SYMBOLS[symbol]}
⏱ Entrada: {entry_time}
🎯 Direção: {direction}
⏳ Expiração: {exp} min"""
        )

        # =========================
        # ESPERA EXPIRAÇÃO
        # =========================

        time.sleep(int(exp) * 60)

        r1 = result(symbol, direction)

        # =========================
        # WIN DIRETO
        # =========================

        if r1 == "WIN":

            time.sleep(3)

            bot.send_animation(
                chat_id,
                open(WIN_GIF, "rb"),
                caption=f"""🏁 RESULTADO FINAL
━━━━━━━━━━━━━━
💱 {SYMBOLS[symbol]}
📊 WIN
⏱ Entrada: {entry_time}
🎯 Direção: {direction}""",
                reply_markup=restart_btn()
            )
            return

        # =========================
        # GALE 1
        # =========================

        bot.send_message(chat_id, "⚠️ Entrando em Gale 1...")

        time.sleep(int(exp) * 60)

        r2 = result(symbol, direction)

        gif = WIN_GIF if r2 == "WIN" else LOSS_GIF

        time.sleep(3)

        bot.send_animation(
            chat_id,
            open(gif, "rb"),
            caption=f"""🏁 RESULTADO FINAL
━━━━━━━━━━━━━━
💱 {SYMBOLS[symbol]}
📊 {r2}
⏱ Entrada: {entry_time}
🎯 Direção: {direction}
🔁 Gale 1""",
            reply_markup=restart_btn()
        )

    threading.Thread(target=process, daemon=True).start()

# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(m):

    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(
        telebot.types.InlineKeyboardButton("🚀 Gerar sinal", callback_data="start")
    )

    bot.send_message(
        m.chat.id,
        "👋 Bem-vindo ao Quantix Cripto\nClique abaixo para começar",
        reply_markup=kb
    )

# =========================
# INICIAR FLUXO
# =========================

@bot.callback_query_handler(func=lambda c: c.data == "start")
def start_flow(c):
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id, "📊 Escolha a paridade:", reply_markup=menu_paridades())

# =========================
# PARIDADE
# =========================

@bot.callback_query_handler(func=lambda c: c.data.startswith("par_"))
def paridade(c):
    bot.answer_callback_query(c.id)

    symbol = c.data.split("_")[1]

    bot.send_message(
        c.message.chat.id,
        "⏳ Escolha a expiração:",
        reply_markup=menu_exp(symbol)
    )

# =========================
# EXPIRAÇÃO
# =========================

@bot.callback_query_handler(func=lambda c: c.data.startswith("exp_"))
def exp(c):
    bot.answer_callback_query(c.id)

    _, symbol, exp = c.data.split("_")

    run_signal(c.message.chat.id, symbol, exp)

# =========================
# RESTART
# =========================

@bot.callback_query_handler(func=lambda c: c.data == "restart")
def restart(c):
    bot.answer_callback_query(c.id)

    bot.send_message(
        c.message.chat.id,
        "📊 Escolha a paridade:",
        reply_markup=menu_paridades()
    )

# =========================
# LOOP
# =========================

print("BOT ONLINE - QUANTIX CRIPTO")
bot.infinity_polling()
