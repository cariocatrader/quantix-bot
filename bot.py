import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
from datetime import datetime, timedelta
import pytz
import os

# ==============================
# CONFIG
# ==============================

TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")

bot = telebot.TeleBot(TOKEN)
timezone = pytz.timezone("America/Sao_Paulo")

GIF_ANALISE = "analise.gif"
GIF_WIN = "win.gif"
GIF_LOSS = "loss.gif"

PARIDADES = [
    "EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD",
    "USD/CHF", "NZD/USD", "EUR/GBP", "EUR/JPY", "GBP/JPY"
]

BANDERAS = {
    "EUR/USD": "🇪🇺🇺🇸",
    "GBP/USD": "🇬🇧🇺🇸",
    "USD/JPY": "🇺🇸🇯🇵",
    "AUD/USD": "🇦🇺🇺🇸",
    "USD/CAD": "🇺🇸🇨🇦",
    "USD/CHF": "🇺🇸🇨🇭",
    "NZD/USD": "🇳🇿🇺🇸",
    "EUR/GBP": "🇪🇺🇬🇧",
    "EUR/JPY": "🇪🇺🇯🇵",
    "GBP/JPY": "🇬🇧🇯🇵"
}

# ==============================
# API
# ==============================

def buscar_candles(paridade):
    url = (
        f"https://api.twelvedata.com/time_series?"
        f"symbol={paridade}&interval=1min&outputsize=30"
        f"&timezone=America/Sao_Paulo&apikey={API_KEY}"
    )
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        if "values" not in data:
            print("Erro API:", data)
            return None
        return data["values"]
    except Exception as e:
        print("Erro buscar candles:", e)
        return None

# ==============================
# ANÁLISE
# ==============================

def analisar(candles):
    if len(candles) < 4:
        return None

    ultimos = candles[0:3]
    altas = sum(float(c["close"]) > float(c["open"]) for c in ultimos)
    baixas = 3 - altas

    if altas >= 2:
        return "CALL"
    if baixas >= 2:
        return "PUT"
    return None

# ==============================
# TEMPO
# ==============================

def proxima_entrada_real():
    agora = datetime.now(timezone)
    return agora.replace(second=0, microsecond=0) + timedelta(minutes=1)

def esperar_ate(timestamp):
    while datetime.now(timezone) < timestamp:
        time.sleep(0.1)

def parse_candle_time(dt_str):
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    return timezone.localize(dt)

# ==============================
# RESULTADO
# ==============================

def resultado_real(paridade, direcao, horario_alvo):
    alvo_hhmm = horario_alvo.strftime("%H:%M") if isinstance(horario_alvo, datetime) else horario_alvo

    for tentativa in range(40):
        candles = buscar_candles(paridade)
        if not candles:
            time.sleep(0.25)
            continue

        for c in candles:
            try:
                candle_time = parse_candle_time(c["datetime"])
                if candle_time.strftime("%H:%M") != alvo_hhmm:
                    continue

                open_price = float(c["open"])
                close_price = float(c["close"])

                if abs(close_price - open_price) < 0.00001:
                    return "DOJI"

                candle_dir = "CALL" if close_price > open_price else "PUT"
                return "WIN" if candle_dir == direcao else "LOSS"

            except Exception as e:
                print("Erro candle:", e)
                continue

        time.sleep(0.25)

    return "TIMEOUT"

# ==============================
# MENU
# ==============================

def menu_paridades():
    kb = InlineKeyboardMarkup(row_width=2)
    for par in PARIDADES:
        kb.add(InlineKeyboardButton(f"{BANDERAS[par]} {par}", callback_data=f"p_{par}"))
    return kb

def botao_novo_sinal():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Novo Sinal", callback_data="gerar"))
    return kb

# ==============================
# START
# ==============================

@bot.message_handler(commands=["start"])
def start(m):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Gerar Sinal", callback_data="gerar"))
    bot.send_message(m.chat.id, "👋 Quantix Signals", reply_markup=kb)

# ==============================
# GERAR
# ==============================

@bot.callback_query_handler(func=lambda c: c.data == "gerar")
def gerar(c):
    try:
        bot.edit_message_text(
            "Escolha a paridade:",
            c.message.chat.id,
            c.message.message_id,
            reply_markup=menu_paridades()
        )
    except:
        bot.send_message(c.message.chat.id, "Escolha a paridade:", reply_markup=menu_paridades())

# ==============================
# EXECUÇÃO
# ==============================

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_"))
def run(c):
    par = c.data.split("_", 1)[1]

    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
    except:
        pass

    anim = bot.send_animation(
        c.message.chat.id,
        open(GIF_ANALISE, "rb"),
        caption="🔎 Analisando..."
    )

    sinal = None
    inicio = time.time()

    while time.time() - inicio < 35:
        candles = buscar_candles(par)
        if candles:
            sinal = analisar(candles)
            if sinal:
                break
        time.sleep(1)

    try:
        bot.delete_message(c.message.chat.id, anim.message_id)
    except:
        pass

    if not sinal:
        bot.send_message(
            c.message.chat.id,
            "❌ Sem sinal válido.",
            reply_markup=botao_novo_sinal()
        )
        return

    entrada = proxima_entrada_real()
    gale = entrada + timedelta(minutes=1)

    horario_entrada = entrada.strftime("%H:%M")
    horario_gale = gale.strftime("%H:%M")

    bot.send_message(
        c.message.chat.id,
        f"""
📊 SINAL:
📊 {BANDERAS[par]} {par}
⏱ M1
🎯 {horario_entrada} ({sinal})
⏳ Gale: {horario_gale}
"""
    )

    # ENTRADA 1
    esperar_ate(entrada + timedelta(minutes=1))
    time.sleep(1.5)
    resultado = resultado_real(par, sinal, horario_entrada)

    # GALE
    if resultado != "WIN":
        bot.send_message(
            c.message.chat.id,
            f"⚠️ {horario_entrada} LOSS → GALE {horario_gale}..."
        )
        esperar_ate(gale + timedelta(minutes=1))
        time.sleep(1.5)
        resultado = resultado_real(par, sinal, horario_gale)

    gif = GIF_WIN if resultado == "WIN" else GIF_LOSS

    bot.send_animation(
        c.message.chat.id,
        open(gif, "rb"),
        caption=f"📊 Final: {resultado}",
        reply_markup=botao_novo_sinal()
    )

print("BOT ONLINE - QUANTIX VERSÃO 2")

bot.infinity_polling(timeout=15, long_polling_timeout=15, skip_pending=True)
