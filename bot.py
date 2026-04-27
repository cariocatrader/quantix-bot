import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
from datetime import datetime, timedelta
import pytz
import os

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

def send_gif(chat_id, path, caption, reply_markup=None):
    with open(path, "rb") as f:
        return bot.send_animation(chat_id, f, caption=caption, reply_markup=reply_markup)

def buscar_candles(paridade, outputsize=40):
    url = (
        f"https://api.twelvedata.com/time_series?"
        f"symbol={paridade}&interval=1min&outputsize={outputsize}"
        f"&timezone=America/Sao_Paulo&order=desc&apikey={API_KEY}"
    )
    try:
        r = requests.get(url, timeout=5)
        data = r.json()

        if "values" not in data:
            print("Erro API:", data)
            return None

        candles = data["values"]
        candles.reverse()
        return candles

    except Exception as e:
        print("Erro buscar candles:", e)
        return None

def analisar(candles):
    if len(candles) < 4:
        return None

    ultimos = candles[-3:]
    altas = sum(float(c["close"]) > float(c["open"]) for c in ultimos)
    baixas = 3 - altas

    if altas >= 2:
        return "CALL"
    if baixas >= 2:
        return "PUT"

    return None

def proxima_entrada_real():
    agora = datetime.now(timezone)
    return agora.replace(second=0, microsecond=0) + timedelta(minutes=1)

def esperar_ate(timestamp):
    while datetime.now(timezone) < timestamp:
        time.sleep(0.1)

def parse_candle_time(dt_str):
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    return timezone.localize(dt)

def encontrar_candle(paridade, horario_alvo, timeout_seg=150):
    alvo = datetime.strptime(horario_alvo, "%H:%M").time()
    fim = time.time() + timeout_seg

    while time.time() < fim:
        candles = buscar_candles(paridade, outputsize=80)

        if candles:
            for c in candles:
                try:
                    ct = parse_candle_time(c["datetime"])

                    if ct.time().hour == alvo.hour and ct.time().minute == alvo.minute:
                        return {
                            "datetime": ct,
                            "open": float(c["open"]),
                            "close": float(c["close"])
                        }

                except:
                    pass

        time.sleep(0.5)

    return None

def calcular_resultado(candle, direcao):
    open_price = candle["open"]
    close_price = candle["close"]

    if abs(close_price - open_price) < 0.00001:
        return "DOJI"

    candle_dir = "CALL" if close_price > open_price else "PUT"

    if candle_dir == direcao:
        return "WIN"

    return "LOSS"

def menu_paridades():
    kb = InlineKeyboardMarkup(row_width=2)

    for par in PARIDADES:
        kb.add(InlineKeyboardButton(f"{BANDERAS[par]} {par}", callback_data=f"p_{par}"))

    return kb

def botao_novo_sinal():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Novo Sinal", callback_data="gerar"))
    return kb

@bot.message_handler(commands=["start"])
def start(m):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Gerar Sinal", callback_data="gerar"))
    bot.send_message(m.chat.id, "👋 Quantix Signals", reply_markup=kb)

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

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_"))
def run(c):
    par = c.data.split("_", 1)[1]

    try:
        bot.delete_message(c.message.chat.id, c.message.message_id)
    except:
        pass

    send_gif(c.message.chat.id, GIF_ANALISE, "🔎 Analisando...")

    sinal = None
    inicio = time.time()

    while time.time() - inicio < 35:
        candles = buscar_candles(par, outputsize=40)

        if candles:
            sinal = analisar(candles)

            if sinal:
                break

        time.sleep(1)

    if not sinal:
        bot.send_message(c.message.chat.id, "❌ Sem sinal válido.", reply_markup=botao_novo_sinal())
        return

    entrada = proxima_entrada_real()
    gale = entrada + timedelta(minutes=1)

    horario_entrada = entrada.strftime("%H:%M")
    horario_gale = gale.strftime("%H:%M")

    bot.send_message(
        c.message.chat.id,
        f"🚀 SINAL ENVIADO\n"
        f"━━━━━━━━━━━━━━\n"
        f"💱 Paridade: {BANDERAS[par]} {par}\n"
        f"⏱ Entrada: {horario_entrada}\n"
        f"🎯 Direção: {sinal}\n"
        f"⏳ Gale: {horario_gale}"
    )

    esperar_ate(entrada + timedelta(minutes=1))
    time.sleep(0.5)

    candle_entrada = encontrar_candle(par, horario_entrada, timeout_seg=150)

    if not candle_entrada:
        bot.send_message(
            c.message.chat.id,
            f"⚠️ Não consegui confirmar a entrada {horario_entrada}.",
            reply_markup=botao_novo_sinal()
        )
        return

    resultado_entrada = calcular_resultado(candle_entrada, sinal)

    if resultado_entrada == "WIN":
        texto_resultado = (
            f"🏁 RESULTADO FINAL 🟢\n"
            f"━━━━━━━━━━━━━━\n"
            f"💱 Paridade: {BANDERAS[par]} {par}\n"
            f"⏱ Entrada: {horario_entrada}\n"
            f"🎯 Direção: {sinal}\n"
            f"🕒 Fechamento: {horario_entrada}\n"
            f"📊 Resultado: WIN"
        )

        send_gif(c.message.chat.id, GIF_WIN, texto_resultado, reply_markup=botao_novo_sinal())
        return

    bot.send_message(
        c.message.chat.id,
        f"⚠️ {horario_entrada} LOSS -> GALE {horario_gale}..."
    )

    esperar_ate(gale + timedelta(minutes=1))
    time.sleep(0.5)

    candle_gale = encontrar_candle(par, horario_gale, timeout_seg=150)

    if not candle_gale:
        bot.send_message(
            c.message.chat.id,
            f"⚠️ Não consegui confirmar o Gale {horario_gale}.",
            reply_markup=botao_novo_sinal()
        )
        return

    resultado_gale = calcular_resultado(candle_gale, sinal)
    gif = GIF_WIN if resultado_gale == "WIN" else GIF_LOSS
    emoji = "🟢" if resultado_gale == "WIN" else "🔴"

    texto_resultado = (
        f"🏁 RESULTADO FINAL {emoji}\n"
        f"━━━━━━━━━━━━━━\n"
        f"💱 Paridade: {BANDERAS[par]} {par}\n"
        f"⏱ Entrada: {horario_entrada}\n"
        f"🎯 Direção: {sinal}\n"
        f"🕒 Fechamento: {horario_gale}\n"
        f"📊 Resultado: {resultado_gale}"
    )

    send_gif(c.message.chat.id, gif, texto_resultado, reply_markup=botao_novo_sinal())

print("BOT ONLINE - QUANTIX")

while True:
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5, skip_pending=True)
    except Exception as e:
        print("Polling caiu:", e)
        time.sleep(3)
