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
    "EUR/USD":"🇪🇺🇺🇸", "GBP/USD":"🇬🇧🇺🇸", "USD/JPY":"🇺🇸🇯🇵", "AUD/USD":"🇦🇺🇺🇸",
    "USD/CAD":"🇺🇸🇨🇦", "USD/CHF":"🇺🇸🇨🇭", "NZD/USD":"🇳🇿🇺🇸", "EUR/GBP":"🇪🇺🇬🇧",
    "EUR/JPY":"🇪🇺🇯🇵", "GBP/JPY":"🇬🇧🇯🇵"
}

# ==============================
# API (COM TIMEZONE FIX)
# ==============================

def buscar_candles(paridade):
    url = f"https://api.twelvedata.com/time_series?symbol={paridade}&interval=1min&outputsize=25&timezone=America/Sao_Paulo&apikey={API_KEY}"
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        print(f"API response for {paridade}: {data.get('status')}")
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
    ultimos = candles[0:3]  # Recentes primeiro
    altas = sum(float(c["close"]) > float(c["open"]) for c in ultimos)
    if altas >= 2:
        return "CALL"
    baixas = 3 - altas
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

# ==============================
# RESULTADO REAL (CORRIGIDO: VERIFICA CANDLE DA ENTRADA)
# ==============================

def resultado_real(paridade, direcao, horario_entrada):  # horario_entrada ex: "13:16"
    print(f"🔍 Verificando resultado {paridade} {direcao} em {horario_entrada}")
    
    for tentativa in range(30):  # ~9s total
        candles = buscar_candles(paridade)
        if not candles:
            time.sleep(0.3)
            continue

        for c in candles:
            try:
                # datetime agora em SP timezone da API
                candle_time = datetime.strptime(c["datetime"], "%Y-%m-%d %H:%M:%S")
                candle_time = timezone.localize(candle_time)  # Já em SP
                
                if candle_time.strftime("%H:%M") == horario_entrada:
                    open_price = float(c["open"])
                    close_price = float(c["close"])
                    print(f"✅ Candle {horario_entrada} encontrado: O={open_price:.5f} C={close_price:.5f}")

                    if abs(close_price - open_price) < 0.00001:
                        print("DOJI")
                        return "DOJI"

                    candle_dir = "CALL" if close_price > open_price else "PUT"
                    resultado = "WIN" if candle_dir == direcao else "LOSS"
                    print(f"🎯 RESULTADO: {resultado} (candle {candle_dir})")
                    return resultado
            except (ValueError, KeyError) as e:
                continue

        time.sleep(0.3)

    print("❌ TIMEOUT")
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
# EXECUÇÃO
# ==============================

@bot.callback_query_handler(func=lambda c: c.data.startswith("p_"))
def run(c):
    par = c.data.split("_")[1]
    bot.delete_message(c.message.chat.id, c.message.message_id)

    msg = bot.send_animation(c.message.chat.id, open(GIF_ANALISE, "rb"), caption="🔎 Analisando...")

    sinal = None
    start_time = time.time()
    while time.time() - start_time < 35:
        candles = buscar_candles(par)
        if candles and (sinal := analisar(candles)):
            break
        time.sleep(1)

    try:
        bot.delete_message(c.message.chat.id, msg.message_id)
    except:
        pass

    if not sinal:
        bot.send_message(c.message.chat.id, "❌ Sem sinal válido.")
        return

    entrada = proxima_entrada_real()
    gale = entrada + timedelta(minutes=1)
    horario_entrada = entrada.strftime("%H:%M")
    horario_gale = gale.strftime("%H:%M")

    bot.send_message(c.message.chat.id, f"""
📊 SINAL:
📊 {BANDERAS[par]} {par}
⏱ M1
🎯 {horario_entrada} ({sinal})
⏳ Gale: {horario_gale}
""")

    # ENTRADA 1
    esperar_ate(entrada + timedelta(minutes=1))
    time.sleep(2)  # Candle fecha
    resultado = resultado_real(par, sinal, horario_entrada)

    # GALE se necessário
    if resultado != "WIN":
        bot.send_message(c.message.chat.id, f"⚠️ {horario_entrada} LOSS → GALE {horario_gale}...")
        esperar_ate(gale + timedelta(minutes=1))
        time.sleep(2)
        resultado = resultado_real(par, sinal, horario_gale)

    gif = GIF_WIN if resultado == "WIN" else GIF_LOSS
    bot.send_animation(c.message.chat.id, open(gif, "rb"), caption=f"📊 Final: {resultado}")

@bot.callback_query_handler(func=lambda c: c.data == "gerar")
def gerar(c):
    kb = InlineKeyboardMarkup(row_width=2)
    for par in PARIDADES:
        kb.add(InlineKeyboardButton(f"{BANDERAS[par]} {par}", callback_data=f"p_{par}"))
    bot.edit_message_text("Paridade:", c.message.chat.id, c.message.message_id, reply_markup=kb)

print("BOT ONLINE - WIN FIX (Timezone + Candle Entrada)")

bot.infinity_polling(timeout=15, long_polling_timeout=15, skip_pending=True)
