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
    "EUR/USD","GBP/USD","USD/JPY","AUD/USD","USD/CAD",
    "USD/CHF","NZD/USD","EUR/GBP","EUR/JPY","GBP/JPY"
]

BANDERAS = {
    "EUR/USD":"🇪🇺🇺🇸",
    "GBP/USD":"🇬🇧🇺🇸",
    "USD/JPY":"🇺🇸🇯🇵",
    "AUD/USD":"🇦🇺🇺🇸",
    "USD/CAD":"🇺🇸🇨🇦",
    "USD/CHF":"🇺🇸🇨🇭",
    "NZD/USD":"🇳🇿🇺🇸",
    "EUR/GBP":"🇪🇺🇬🇧",
    "EUR/JPY":"🇪🇺🇯🇵",
    "GBP/JPY":"🇬🇧🇯🇵"
}

# ==============================
# API
# ==============================

def buscar_candles(paridade):
    url = f"https://api.twelvedata.com/time_series?symbol={paridade}&interval=1min&outputsize=20&apikey={API_KEY}"

    try:
        r = requests.get(url, timeout=6)
        data = r.json()
        if "values" not in data:
            print("Erro API:", data)
            return None
        return data["values"]
    except Exception as e:
        print("Erro buscar candles:", e)
        return None

# ==============================
# ANALISE
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
    while True:
        if datetime.now(timezone) >= timestamp:
            break
        time.sleep(0.1)

# ==============================
# RESULTADO REAL (SUPER ROBUSTO)
# ==============================

def resultado_real(paridade, direcao, horario_base):
    horario_candle = (datetime.strptime(horario_base, "%H:%M") + timedelta(minutes=1)).strftime("%H:%M")
    print(f"Verificando candle {horario_candle} para {paridade} {direcao}")

    for tentativa in range(20):  # 20 retries ~10s total
        candles = buscar_candles(paridade)
        if not candles:
            time.sleep(0.5)
            continue

        for c in candles:
            try:
                candle_time = datetime.strptime(c["datetime"], "%Y-%m-%d %H:%M:%S")
                candle_time = pytz.utc.localize(candle_time).astimezone(timezone)
                if candle_time.strftime("%H:%M") == horario_candle:
                    open_price = float(c["open"])
                    close_price = float(c["close"])
                    print(f"Candle encontrado: open={open_price}, close={close_price}")

                    if abs(close_price - open_price) < 0.00001:
                        print("DOJI detectado")
                        return "DOJI"

                    candle_result = "CALL" if close_price > open_price else "PUT"
                    resultado = "WIN" if candle_result == direcao else "LOSS"
                    print(f"Resultado: {resultado}")
                    return resultado
            except (ValueError, KeyError) as e:
                print(f"Erro parse candle: {e}")
                continue

        time.sleep(0.5)

    print("TIMEOUT após 20 tentativas")
    return "TIMEOUT"

# ==============================
# START
# ==============================

@bot.message_handler(commands=["start"])
def start(m):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Gerar Sinal", callback_data="gerar"))
    bot.send_message(m.chat.id, "👋 Bem-vindo ao Quantix", reply_markup=kb)

# ==============================
# EXECUÇÃO (GALE SEMPRE SE LOSS)
# ==============================

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_"))
def run(c):
    par = c.data.split("_")[1]
    bot.delete_message(c.message.chat.id, c.message.message_id)

    msg = bot.send_animation(c.message.chat.id, open(GIF_ANALISE, "rb"), caption="🔎 Quantix analisando...")

    sinal = None
    start_time = time.time()
    while time.time() - start_time < 40:
        candles = buscar_candles(par)
        if candles:
            sinal = analisar(candles)
            if sinal:
                break
        time.sleep(1)

    try:
        bot.delete_message(c.message.chat.id, msg.message_id)
    except:
        pass

    if not sinal:
        bot.send_message(c.message.chat.id, "❌ Nenhum sinal válido encontrado.")
        return

    entrada = proxima_entrada_real()
    gale = entrada + timedelta(minutes=1)
    horario_entrada = entrada.strftime("%H:%M")
    horario_gale = gale.strftime("%H:%M")

    bot.send_message(c.message.chat.id, f"""
📊 SINAL GERADO:
📊 Paridade: {BANDERAS[par]} {par}
⏱ Timeframe: M1
🎯 Entrada: {horario_entrada} ({sinal})
⏳ Gale: {horario_gale}
""")

    # PRIMEIRA ENTRADA
    esperar_ate(entrada + timedelta(minutes=1))
    time.sleep(3)  # Mínimo para candle fechar
    resultado = resultado_real(par, sinal, horario_entrada)

    # SEMPRE TENTA GALE SE NÃO WIN
    if resultado != "WIN":
        bot.send_message(c.message.chat.id, "⚠️ Primeira entrada LOSS - Entrando em GALE...")
        esperar_ate(gale + timedelta(minutes=1))
        time.sleep(3)
        resultado = resultado_real(par, sinal, horario_gale)
        # Se ainda LOSS, mantém resultado final

    gif = GIF_WIN if resultado == "WIN" else GIF_LOSS
    bot.send_animation(c.message.chat.id, open(gif, "rb"), caption=f"📊 Resultado Final: {resultado}")

@bot.callback_query_handler(func=lambda c: c.data == "gerar")
def gerar(c):
    kb = InlineKeyboardMarkup(row_width=2)
    for par in PARIDADES:
        kb.add(InlineKeyboardButton(f"{BANDERAS[par]} {par}", callback_data=f"p_{par}"))
    bot.edit_message_text("Escolha a paridade:", c.message.chat.id, c.message.message_id, reply_markup=kb)

print("BOT ONLINE - VERSÃO FINAL (Gale Forçado + Anti-Timeout)")

bot.infinity_polling(timeout=20, long_polling_timeout=20, skip_pending=True)
