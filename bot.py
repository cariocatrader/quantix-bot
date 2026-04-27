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

def buscar_candles(paridade):
    url = (
        f"https://api.twelvedata.com/time_series?"
        f"symbol={paridade}&interval=1min&outputsize=50"
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

def proxima_entrada_real():
    agora = datetime.now(timezone)
    return agora.replace(second=0, microsecond=0) + timedelta(minutes=1)

def esperar_ate(timestamp):
    while datetime.now(timezone) < timestamp:
        time.sleep(0.1)

def parse_candle_time(dt_str):
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    return timezone.localize(dt)

def encontrar_candle(paridade, horario_alvo, timeout_seg=120):
    fim = time.time() + timeout_seg
    while time.time() < fim:
        candles = buscar_candles(paridade)
        if candles:
            for c in candles:
                try:
                    ct = parse_candle_time(c["datetime"])
                    if ct.strftime("%H:%M") == horario_alvo:
                        return {
                            "datetime": ct,
                            "open": float(c["open"]),
                            "close": float(c["close"]),
                            "high": float(c["high"]) if "high" in c else None,
                            "low": float(c["low"]) if "low" in c else None
                        }
                except:
                    continue
        time.sleep(0.5)
    return None

def calcular_resultado(candle, direcao):
    open_price = candle["open"]
    close_price = candle["close"]
    if abs(close_price - open_price) < 0.00001:
        return "DOJI", "DOJI"
    candle_dir = "CALL" if close_price > open_price else "PUT"
    resultado = "WIN" if candle_dir == direcao else "LOSS"
    return resultado, candle_dir

def montar_debug(candle, direcao, resultado, candle_dir):
    dt = candle["datetime"].strftime("%H:%M")
    return (
        f"🔎 DEBUG DO CANDLE
"
        f"⏱ Horário: {dt}
"
        f"📈 Open: {candle['open']}
"
        f"📉 Close: {candle['close']}
"
        f"➡️ Direção do candle: {candle_dir}
"
        f"🎯 Sinal: {direcao}
"
        f"📊 Resultado: {resultado}"
    )

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

    esperar_ate(entrada + timedelta(minutes=1))
    time.sleep(1.0)

    candle_entrada = encontrar_candle(par, horario_entrada, timeout_seg=120)
    if not candle_entrada:
        bot.send_message(
            c.message.chat.id,
            f"⚠️ Não consegui confirmar o candle da entrada {horario_entrada}.",
            reply_markup=botao_novo_sinal()
        )
        return

    resultado, candle_dir = calcular_resultado(candle_entrada, sinal)

    bot.send_message(c.message.chat.id, montar_debug(candle_entrada, sinal, resultado, candle_dir))

    if resultado != "WIN":
        bot.send_message(
            c.message.chat.id,
            f"⚠️ {horario_entrada} LOSS → GALE {horario_gale}..."
        )

        esperar_ate(gale + timedelta(minutes=1))
        time.sleep(1.0)

        candle_gale = encontrar_candle(par, horario_gale, timeout_seg=120)
        if not candle_gale:
            bot.send_message(
                c.message.chat.id,
                f"⚠️ Não consegui confirmar o candle do Gale {horario_gale}.",
                reply_markup=botao_novo_sinal()
            )
            return

        resultado, candle_dir = calcular_resultado(candle_gale, sinal)
        bot.send_message(c.message.chat.id, montar_debug(candle_gale, sinal, resultado, candle_dir))

    gif = GIF_WIN if resultado == "WIN" else GIF_LOSS

    bot.send_animation(
        c.message.chat.id,
        open(gif, "rb"),
        caption=f"📊 Final: {resultado}",
        reply_markup=botao_novo_sinal()
    )

print("BOT ONLINE - QUANTIX COMPLETO COM DEBUG")

bot.infinity_polling(timeout=15, long_polling_timeout=15, skip_pending=True)
