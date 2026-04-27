import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
import threading
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


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def send_gif(chat_id, path, caption, reply_markup=None):
    with open(path, "rb") as f:
        return bot.send_animation(chat_id, f, caption=caption, reply_markup=reply_markup)


def delete_msg(chat_id, msg_id):
    """Apaga mensagem silenciosamente."""
    try:
        bot.delete_message(chat_id, msg_id)
    except Exception:
        pass


def buscar_candles(paridade, outputsize=40):
    """
    Busca candles de 1min na TwelveData.
    Retorna lista ordenada do mais antigo para o mais novo, ou None em caso de erro.
    """
    url = (
        f"https://api.twelvedata.com/time_series?"
        f"symbol={paridade}&interval=1min&outputsize={outputsize}"
        f"&timezone=America/Sao_Paulo&order=desc&apikey={API_KEY}"
    )
    try:
        r = requests.get(url, timeout=10)
        data = r.json()

        # FIX: trata rate limit explicitamente
        if data.get("code") == 429 or "rate limit" in str(data).lower():
            print("⚠️ Rate limit atingido. Aguardando 15s...")
            time.sleep(15)
            return None

        if "values" not in data:
            print("Erro API:", data)
            return None

        candles = data["values"]
        candles.reverse()  # mais antigo → mais novo
        return candles

    except Exception as e:
        print("Erro buscar_candles:", e)
        return None


def analisar(candles):
    """
    Estratégia simples: 2 de 3 últimas velas na mesma direção.
    FIX: chamada única — sem loop externo. Se não tiver sinal, retorna None direto.
    """
    if not candles or len(candles) < 4:
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
        time.sleep(0.2)


def parse_candle_time(dt_str):
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    return timezone.localize(dt)


def encontrar_candle(paridade, horario_alvo_dt, timeout_seg=150):
    """
    FIX: recebe datetime completo (não só HH:MM) para evitar
    colisão com candles de outros minutos do mesmo horário.
    """
    fim = time.time() + timeout_seg

    while time.time() < fim:
        candles = buscar_candles(paridade, outputsize=80)

        if candles:
            for c in reversed(candles):
                try:
                    ct = parse_candle_time(c["datetime"])
                    # compara ano/mês/dia/hora/minuto — sem bug de meia-noite
                    if (ct.year == horario_alvo_dt.year and
                            ct.month == horario_alvo_dt.month and
                            ct.day == horario_alvo_dt.day and
                            ct.hour == horario_alvo_dt.hour and
                            ct.minute == horario_alvo_dt.minute):
                        return {
                            "datetime": ct,
                            "open": float(c["open"]),
                            "close": float(c["close"])
                        }
                except Exception:
                    pass

        time.sleep(3)  # FIX: 0.5s gerava centenas de req/min → rate limit

    return None


def calcular_resultado(candle, direcao):
    open_price = candle["open"]
    close_price = candle["close"]

    if abs(close_price - open_price) < 0.00001:
        return "DOJI"

    candle_dir = "CALL" if close_price > open_price else "PUT"
    return "WIN" if candle_dir == direcao else "LOSS"


# ─────────────────────────────────────────────
# TECLADOS
# ─────────────────────────────────────────────

def menu_paridades():
    kb = InlineKeyboardMarkup(row_width=2)
    for par in PARIDADES:
        kb.add(InlineKeyboardButton(f"{BANDERAS[par]} {par}", callback_data=f"p_{par}"))
    return kb


def botao_novo_sinal():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Novo Sinal", callback_data="gerar"))
    return kb


# ─────────────────────────────────────────────
# FLUXO PRINCIPAL (roda em thread separada)
# FIX: evita bloquear o bot para outros usuários
# ─────────────────────────────────────────────

def fluxo_sinal(chat_id, par, msg_analise_id):
    """Toda a lógica de sinal roda numa thread própria."""

    # ── 1. Análise ───────────────────────────
    # FIX: UMA única chamada à API. Se não tiver sinal, avisa e encerra.
    # O loop de 35s original nunca mudava o resultado porque os candles
    # históricos não mudam — e esgotava o rate limit da TwelveData.
    candles = buscar_candles(par, outputsize=40)
    sinal = analisar(candles) if candles else None

    # Apaga o GIF de análise após obter (ou não) o sinal
    delete_msg(chat_id, msg_analise_id)

    if not sinal:
        bot.send_message(
            chat_id,
            "❌ Mercado lateral — sem sinal válido no momento.",
            reply_markup=botao_novo_sinal()
        )
        return

    # ── 2. Calcula horários ──────────────────
    entrada_dt = proxima_entrada_real()
    gale_dt = entrada_dt + timedelta(minutes=1)

    horario_entrada = entrada_dt.strftime("%H:%M")
    horario_gale = gale_dt.strftime("%H:%M")

    bot.send_message(
        chat_id,
        f"🚀 SINAL ENVIADO\n"
        f"━━━━━━━━━━━━━━\n"
        f"💱 Paridade: {BANDERAS[par]} {par}\n"
        f"⏱ Entrada: {horario_entrada}\n"
        f"🎯 Direção: {sinal}\n"
        f"⏳ Gale: {horario_gale}"
    )

    # ── 3. Aguarda fechamento da vela de entrada ──
    esperar_ate(entrada_dt + timedelta(minutes=1))
    time.sleep(2)  # margem para a API atualizar

    candle_entrada = encontrar_candle(par, entrada_dt, timeout_seg=150)

    if not candle_entrada:
        bot.send_message(
            chat_id,
            f"⚠️ Não consegui confirmar a entrada {horario_entrada}.",
            reply_markup=botao_novo_sinal()
        )
        return

    resultado_entrada = calcular_resultado(candle_entrada, sinal)

    if resultado_entrada in ("WIN", "DOJI"):
        emoji = "🟢" if resultado_entrada == "WIN" else "⚪"
        texto = (
            f"🏁 RESULTADO FINAL {emoji}\n"
            f"━━━━━━━━━━━━━━\n"
            f"💱 Paridade: {BANDERAS[par]} {par}\n"
            f"⏱ Entrada: {horario_entrada}\n"
            f"🎯 Direção: {sinal}\n"
            f"🕒 Fechamento: {horario_entrada}\n"
            f"📊 Resultado: {resultado_entrada}"
        )
        gif = GIF_WIN
        send_gif(chat_id, gif, texto, reply_markup=botao_novo_sinal())
        return

    # ── 4. Gale ──────────────────────────────
    bot.send_message(
        chat_id,
        f"⚠️ {horario_entrada} LOSS → GALE em {horario_gale}..."
    )

    esperar_ate(gale_dt + timedelta(minutes=1))
    time.sleep(2)

    candle_gale = encontrar_candle(par, gale_dt, timeout_seg=150)

    if not candle_gale:
        bot.send_message(
            chat_id,
            f"⚠️ Não consegui confirmar o Gale {horario_gale}.",
            reply_markup=botao_novo_sinal()
        )
        return

    resultado_gale = calcular_resultado(candle_gale, sinal)
    gif = GIF_WIN if resultado_gale in ("WIN", "DOJI") else GIF_LOSS
    emoji = "🟢" if resultado_gale == "WIN" else ("⚪" if resultado_gale == "DOJI" else "🔴")

    texto = (
        f"🏁 RESULTADO FINAL {emoji}\n"
        f"━━━━━━━━━━━━━━\n"
        f"💱 Paridade: {BANDERAS[par]} {par}\n"
        f"⏱ Entrada: {horario_entrada}\n"
        f"🎯 Direção: {sinal}\n"
        f"🕒 Fechamento: {horario_gale}\n"
        f"📊 Resultado: {resultado_gale}"
    )
    send_gif(chat_id, gif, texto, reply_markup=botao_novo_sinal())


# ─────────────────────────────────────────────
# HANDLERS
# ─────────────────────────────────────────────

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
    except Exception:
        bot.send_message(c.message.chat.id, "Escolha a paridade:", reply_markup=menu_paridades())
    bot.answer_callback_query(c.id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("p_"))
def run(c):
    par = c.data.split("_", 1)[1]
    bot.answer_callback_query(c.id)

    delete_msg(c.message.chat.id, c.message.message_id)

    # Envia GIF de análise e guarda o ID para apagar depois
    msg_analise = send_gif(c.message.chat.id, GIF_ANALISE, "🔎 Analisando mercado...")

    # FIX: roda em thread separada para não travar o bot
    t = threading.Thread(
        target=fluxo_sinal,
        args=(c.message.chat.id, par, msg_analise.message_id),
        daemon=True
    )
    t.start()


# ─────────────────────────────────────────────
# POLLING
# ─────────────────────────────────────────────

print("BOT ONLINE - QUANTIX")

while True:
    try:
        bot.infinity_polling(timeout=20, long_polling_timeout=10, skip_pending=True)
    except Exception as e:
        print("Polling caiu:", e)
        time.sleep(5)
