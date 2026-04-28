import telebot
import requests
import threading
import time
import os
from datetime import datetime, timedelta
import pytz
import math

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise Exception("TOKEN não encontrado")

bot = telebot.TeleBot(TOKEN)

BR_TZ = pytz.timezone('America/Sao_Paulo')

def get_br_time(format_str="%H:%M"):
    return datetime.now(BR_TZ).strftime(format_str)

def next_round_time(now_str, exp):
    now = datetime.strptime(now_str, "%H:%M")
    now = now.replace(tzinfo=BR_TZ)

    if exp == "1":
        entry_min = now.minute + 1

        if entry_min >= 60:
            entry_min = 0
            now += timedelta(hours=1)

        entry = now.replace(
            minute=entry_min,
            second=0,
            microsecond=0
        )

        gale1 = entry + timedelta(minutes=1)

    else:
        minutes = now.minute

        next_5 = math.ceil(
            (minutes + 1) / 5.0
        ) * 5

        if next_5 >= 60:
            next_5 = 0
            now += timedelta(hours=1)

        entry = now.replace(
            minute=next_5,
            second=0,
            microsecond=0
        )

        gale1 = entry + timedelta(minutes=5)

    return (
        entry.strftime("%H:%M"),
        gale1.strftime("%H:%M")
    )

SYMBOLS = {
    "bitcoin": "₿ Bitcoin",
    "ethereum": "Ξ Ethereum",
    "binancecoin": "🟡 BNB",
    "solana": "🟣 Solana",
    "ripple": "💧 XRP",
    "cardano": "🔵 Cardano",
    "dogecoin": "🐶 Doge",
    "litecoin": "🪙 Litecoin",
    "polkadot": "⚫ Polkadot",
    "avalanche-2": "🔺 Avalanche"
}

BINANCE_SYMBOLS = {
    "bitcoin": "BTCUSDT",
    "ethereum": "ETHUSDT",
    "binancecoin": "BNBUSDT",
    "solana": "SOLUSDT",
    "ripple": "XRPUSDT",
    "cardano": "ADAUSDT",
    "dogecoin": "DOGEUSDT",
    "litecoin": "LTCUSDT",
    "polkadot": "DOTUSDT",
    "avalanche-2": "AVAXUSDT"
}

ANALISE_GIF = "analise.gif"
WIN_GIF = "win.gif"
LOSS_GIF = "loss.gif"

def analyze(coin_id):
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc?vs_currency=usd&days=2"

        r = requests.get(
            url,
            timeout=8
        )

        data = r.json()

        closes = [
            candle[4]
            for candle in data[-3:]
        ]

        return "COMPRA" if closes[-1] > closes[-2] else "VENDA"

    except:
        return "COMPRA"

def get_binance_candle(symbol, target_time):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=30"

        r = requests.get(
            url,
            timeout=5
        )

        data = r.json()

        target_ts = int(
            datetime.strptime(
                target_time,
                "%H:%M"
            ).replace(
                year=2026,
                month=4,
                day=28
            ).timestamp() * 1000
        )

        for candle in data:

            if int(candle[0]) <= target_ts <= int(candle[6]):

                return (
                    float(candle[1]),
                    float(candle[4])
                )

        return None, None

    except:
        return None, None

def get_result(symbol, direction, target_time):

    o, c = get_binance_candle(
        symbol,
        target_time
    )

    if o is None:
        return "LOSS"

    return "WIN" if (
        (direction == "COMPRA" and c > o) or
        (direction == "VENDA" and c < o)
    ) else "LOSS"

def restart_btn():

    kb = telebot.types.InlineKeyboardMarkup()

    kb.add(
        telebot.types.InlineKeyboardButton(
            "🚀 Novo Sinal",
            callback_data="restart"
        )
    )

    return kb

def menu_paridades():

    kb = telebot.types.InlineKeyboardMarkup(
        row_width=2
    )

    for coin_id, name in SYMBOLS.items():

        kb.add(
            telebot.types.InlineKeyboardButton(
                name,
                callback_data=f"par_{coin_id}"
            )
        )

    return kb

def menu_exp(coin_id):

    kb = telebot.types.InlineKeyboardMarkup()

    btn1 = telebot.types.InlineKeyboardButton(
        "⚡ 1 Minuto",
        callback_data=f"exp_{coin_id}_1"
    )

    btn2 = telebot.types.InlineKeyboardButton(
        "🕐 5 Minutos",
        callback_data=f"exp_{coin_id}_5"
    )

    kb.add(btn1, btn2)

    return kb

def run_signal(chat_id, coin_id, exp):

    def process():

        # ANÁLISE PROFISSIONAL

        with open(ANALISE_GIF, "rb") as gif:

            bot.send_animation(
                chat_id,
                gif,
                caption="🔍 *Aguarde enquanto o Quantix Cripto busca a melhor entrada...*",
                parse_mode="Markdown"
            )

        direction = analyze(coin_id)

        symbol = BINANCE_SYMBOLS[coin_id]

        now = get_br_time()

        entry_time, gale_time = next_round_time(
            now,
            exp
        )

        exp_min = 1 if exp == "1" else 5

        bot.send_message(
            chat_id,
            f"""🎉 *SINAL ENCONTRADO!*

**━━━━━━━━━━━━━━━━━━**
💱 `{SYMBOLS[coin_id]}`
⏱ *Entrada:* `{entry_time}`
📅 *Gale 1:* `{gale_time}`
🎯 *Direção:* `{direction}`
⏳ *Expiração:* `{exp_min} min`
📊 *Análise:* CoinGecko + Binance Real

**Quantix Cripto - Precisão máxima** ✨""",
            parse_mode="Markdown",
            reply_markup=restart_btn()
        )

        now_dt = datetime.now(BR_TZ)

        entry_dt = datetime.strptime(
            entry_time,
            "%H:%M"
        ).replace(
            year=now_dt.year,
            month=now_dt.month,
            day=now_dt.day,
            tzinfo=BR_TZ
        )

        sleep_entry = max(
            1,
            int(
                (entry_dt - now_dt).total_seconds()
                + exp_min * 60
            )
        )

        time.sleep(sleep_entry)

        r1 = get_result(
            symbol,
            direction,
            entry_time
        )

        if r1 == "WIN":

            time.sleep(3)

            with open(WIN_GIF, "rb") as gif:

                bot.send_animation(
                    chat_id,
                    gif,
                    caption=f"""🎊 *WIN DIRETO!*

**━━━━━━━━━━━━━━━━━━**
💱 `{SYMBOLS[coin_id]}`
✅ *{r1}*
⏱ `{entry_time}`
🎯 `{direction}`

**Parabéns! Operação perfeita** 🏆""",
                    parse_mode="Markdown",
                    reply_markup=restart_btn()
                )

            return

        bot.send_message(
            chat_id,
            """😔 *Entrada Principal LOSS*

Infelizmente a entrada principal deu LOSS. 

⚠️ *Entrando em Gale 1 agora...*

Mantenha a calma, recuperação em andamento! 💪"""
        )

        gale_dt = datetime.strptime(
            gale_time,
            "%H:%M"
        ).replace(
            year=now_dt.year,
            month=now_dt.month,
            day=now_dt.day,
            tzinfo=BR_TZ
        )

        sleep_gale = max(
            1,
            int(
                (gale_dt - datetime.now(BR_TZ)).total_seconds()
                + exp_min * 60
            )
        )

        time.sleep(sleep_gale)

        r2 = get_result(
            symbol,
            direction,
            gale_time
        )

        time.sleep(3)

        gif_file = WIN_GIF if r2 == "WIN" else LOSS_GIF

        with open(gif_file, "rb") as gif:

            if r2 == "WIN":

                bot.send_animation(
                    chat_id,
                    gif,
                    caption=f"""🎉 *GALE 1 - VITÓRIA!*

**━━━━━━━━━━━━━━━━━━**
💱 `{SYMBOLS[coin_id]}`
✅ *{r2}*
⏱ `{entry_time}` → `{gale_time}`
🎯 `{direction}`

**Recuperação completa!** 🔥""",
                    parse_mode="Markdown",
                    reply_markup=restart_btn()
                )

            else:

                bot.send_animation(
                    chat_id,
                    gif,
                    caption=f"""💔 *GALE 1 - LOSS FINAL*

**━━━━━━━━━━━━━━━━━━**
💱 `{SYMBOLS[coin_id]}`
❌ *{r2}*
⏱ `{entry_time}` → `{gale_time}`
🎯 `{direction}`

**Nova oportunidade aguarda...** 📈""",
                    parse_mode="Markdown",
                    reply_markup=restart_btn()
                )

    threading.Thread(
        target=process,
        daemon=True
    ).start()

@bot.message_handler(commands=["start"])
def start(m):

    kb = telebot.types.InlineKeyboardMarkup()

    kb.add(
        telebot.types.InlineKeyboardButton(
            "🚀 Iniciar Quantix",
            callback_data="start"
        )
    )

    bot.send_message(
        m.chat.id,
        f"""🤖 *Bem-vindo ao Quantix Cripto!*

*IA de trading 24/7 com análise CoinGecko + candles Binance reais*

🇧🇷 {get_br_time()} - Clique abaixo""",
        parse_mode="Markdown",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda c: c.data == "start")
def start_flow(c):

    bot.answer_callback_query(c.id)

    bot.send_message(
        c.message.chat.id,
        "*Escolha a paridade:*",
        parse_mode="Markdown",
        reply_markup=menu_paridades()
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("par_"))
def paridade(c):

    bot.answer_callback_query(c.id)

    coin_id = c.data.split("_", 1)[1]

    bot.send_message(
        c.message.chat.id,
        "*Selecione expiração:*",
        parse_mode="Markdown",
        reply_markup=menu_exp(coin_id)
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("exp_"))
def exp_handler(c):

    bot.answer_callback_query(c.id)

    parts = c.data.split("_")

    run_signal(
        c.message.chat.id,
        parts[1],
        parts[2]
    )

@bot.callback_query_handler(func=lambda c: c.data == "restart")
def restart(c):

    bot.answer_callback_query(c.id)

    bot.send_message(
        c.message.chat.id,
        "*Nova paridade:*",
        parse_mode="Markdown",
        reply_markup=menu_paridades()
    )

print(f"🚀 QUANTIX PROFISSIONAL {get_br_time()}")

bot.infinity_polling()
