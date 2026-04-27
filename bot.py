import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
import threading
from datetime import datetime, timedelta
import pytz
import os

TOKEN = os.getenv("TOKEN")

bot = telebot.TeleBot(TOKEN)
timezone = pytz.timezone("America/Sao_Paulo")

GIF_ANALISE = "analise.gif"
GIF_WIN     = "win.gif"
GIF_LOSS    = "loss.gif"

PARIDADES = [
    "bitcoin", "ethereum", "binancecoin", "solana", "ripple",
    "cardano", "dogecoin", "litecoin", "polkadot", "avalanche-2"
]

DISPLAY = {
    "bitcoin":      ("BTC/USDT", "₿🟡"),
    "ethereum":     ("ETH/USDT", "Ξ🔵"),
    "binancecoin":  ("BNB/USDT", "🟠"),
    "solana":       ("SOL/USDT", "🟣"),
    "ripple":       ("XRP/USDT", "💧"),
    "cardano":      ("ADA/USDT", "🔷"),
    "dogecoin":     ("DOGE/USDT","🐶"),
    "litecoin":     ("LTC/USDT", "🪙"),
    "polkadot":     ("DOT/USDT", "⚫"),
    "avalanche-2":  ("AVAX/USDT","🔺"),
}

HEADERS = {"User-Agent": "Mozilla/5.0"}

# ─────────────────────────────────────────────────────────────────────────────
# COINGECKO API  — candles de 1 minuto via /ohlc (grátis, sem chave, sem bloqueio)
# ─────────────────────────────────────────────────────────────────────────────

def buscar_candles(coin_id, limit=40):
    """
    CoinGecko /ohlc retorna velas de 1min para janela de 1 dia.
    Cada vela: [timestamp_ms, open, high, low, close]
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
    params = {"vs_currency": "usd", "days": "1"}

    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        r.raise_for_status()
        raw = r.json()

        if not isinstance(raw, list) or len(raw) == 0:
            print(f"CoinGecko sem dados para {coin_id}:", raw)
            return None

        candles = []
        for k in raw:
            dt    = datetime.fromtimestamp(k[0] / 1000, tz=timezone)
            open_ = float(k[1])
            close = float(k[4]) if len(k) > 4 else float(k[3])
            candles.append({"datetime": dt, "open": open_, "close": close})

        # ordena do mais antigo ao mais novo e retorna os últimos `limit`
        candles.sort(key=lambda c: c["datetime"])
        return candles[-limit:]

    except Exception as e:
        print(f"Erro buscar_candles ({coin_id}):", e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# ANÁLISE
# ─────────────────────────────────────────────────────────────────────────────

def analisar(candles):
    if not candles or len(candles) < 3:
        return None

    ultimos = candles[-3:]
    altas   = sum(c["close"] > c["open"] for c in ultimos)
    baixas  = 3 - altas

    print(f"  Análise → altas={altas} baixas={baixas}")
    for c in ultimos:
        print(f"    {c['datetime'].strftime('%H:%M')} open={c['open']:.4f} close={c['close']:.4f} {'▲' if c['close']>c['open'] else '▼'}")

    if altas >= 2:
        return "CALL"
    if baixas >= 2:
        return "PUT"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# TEMPO
# ─────────────────────────────────────────────────────────────────────────────

def proxima_entrada():
    agora = datetime.now(timezone)
    return agora.replace(second=0, microsecond=0) + timedelta(minutes=1)


def esperar_ate(ts):
    while datetime.now(timezone) < ts:
        time.sleep(0.2)


# ─────────────────────────────────────────────────────────────────────────────
# BUSCA CANDLE ESPECÍFICO
# ─────────────────────────────────────────────────────────────────────────────

def encontrar_candle(coin_id, alvo_dt, timeout_seg=150):
    fim = time.time() + timeout_seg

    while time.time() < fim:
        candles = buscar_candles(coin_id, limit=10)

        if candles:
            for c in reversed(candles):
                cd = c["datetime"]
                if (cd.year   == alvo_dt.year  and
                    cd.month  == alvo_dt.month  and
                    cd.day    == alvo_dt.day    and
                    cd.hour   == alvo_dt.hour   and
                    cd.minute == alvo_dt.minute):
                    return c

        time.sleep(5)

    return None


# ─────────────────────────────────────────────────────────────────────────────
# RESULTADO
# ─────────────────────────────────────────────────────────────────────────────

def calcular_resultado(candle, direcao):
    diff = candle["close"] - candle["open"]
    if abs(diff) < 1e-8:
        return "DOJI"
    return "WIN" if (diff > 0 and direcao == "CALL") or (diff < 0 and direcao == "PUT") else "LOSS"


# ─────────────────────────────────────────────────────────────────────────────
# TECLADOS
# ─────────────────────────────────────────────────────────────────────────────

def menu_paridades():
    kb = InlineKeyboardMarkup(row_width=2)
    for coin in PARIDADES:
        nome, emoji = DISPLAY[coin]
        kb.add(InlineKeyboardButton(f"{emoji} {nome}", callback_data=f"p_{coin}"))
    return kb


def botao_novo_sinal():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Novo Sinal", callback_data="gerar"))
    return kb


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS TELEGRAM
# ─────────────────────────────────────────────────────────────────────────────

def send_gif(chat_id, path, caption, reply_markup=None):
    with open(path, "rb") as f:
        return bot.send_animation(chat_id, f, caption=caption, reply_markup=reply_markup)


def delete_msg(chat_id, msg_id):
    try:
        bot.delete_message(chat_id, msg_id)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# FLUXO PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def fluxo_sinal(chat_id, coin_id, msg_analise_id):
    nome, emoji = DISPLAY[coin_id]

    # ── 1. Análise ────────────────────────────────────────────────────────────
    candles = buscar_candles(coin_id, limit=40)
    sinal   = analisar(candles) if candles else None

    delete_msg(chat_id, msg_analise_id)

    if not sinal:
        bot.send_message(
            chat_id,
            "❌ Mercado lateral — sem sinal válido no momento.",
            reply_markup=botao_novo_sinal()
        )
        return

    # ── 2. Horários ───────────────────────────────────────────────────────────
    entrada_dt = proxima_entrada()
    gale_dt    = entrada_dt + timedelta(minutes=1)

    bot.send_message(
        chat_id,
        f"🚀 SINAL ENVIADO\n"
        f"━━━━━━━━━━━━━━\n"
        f"💱 Paridade: {emoji} {nome}\n"
        f"⏱ Entrada: {entrada_dt.strftime('%H:%M')}\n"
        f"🎯 Direção: {sinal}\n"
        f"⏳ Gale: {gale_dt.strftime('%H:%M')}"
    )

    # ── 3. Aguarda fechamento da vela de entrada ──────────────────────────────
    esperar_ate(entrada_dt + timedelta(minutes=1))
    time.sleep(3)

    candle_entrada = encontrar_candle(coin_id, entrada_dt, timeout_seg=120)

    if not candle_entrada:
        bot.send_message(
            chat_id,
            f"⚠️ Não consegui confirmar a entrada {entrada_dt.strftime('%H:%M')}.",
            reply_markup=botao_novo_sinal()
        )
        return

    resultado = calcular_resultado(candle_entrada, sinal)

    if resultado in ("WIN", "DOJI"):
        emoji_res = "🟢" if resultado == "WIN" else "⚪"
        send_gif(
            chat_id, GIF_WIN,
            f"🏁 RESULTADO FINAL {emoji_res}\n"
            f"━━━━━━━━━━━━━━\n"
            f"💱 Paridade: {emoji} {nome}\n"
            f"⏱ Entrada: {entrada_dt.strftime('%H:%M')}\n"
            f"🎯 Direção: {sinal}\n"
            f"📊 Resultado: {resultado}",
            reply_markup=botao_novo_sinal()
        )
        return

    # ── 4. Gale ───────────────────────────────────────────────────────────────
    bot.send_message(
        chat_id,
        f"⚠️ {entrada_dt.strftime('%H:%M')} LOSS → GALE em {gale_dt.strftime('%H:%M')}..."
    )

    esperar_ate(gale_dt + timedelta(minutes=1))
    time.sleep(3)

    candle_gale = encontrar_candle(coin_id, gale_dt, timeout_seg=120)

    if not candle_gale:
        bot.send_message(
            chat_id,
            f"⚠️ Não consegui confirmar o Gale {gale_dt.strftime('%H:%M')}.",
            reply_markup=botao_novo_sinal()
        )
        return

    resultado_gale = calcular_resultado(candle_gale, sinal)
    gif       = GIF_WIN if resultado_gale in ("WIN", "DOJI") else GIF_LOSS
    emoji_res = "🟢" if resultado_gale == "WIN" else ("⚪" if resultado_gale == "DOJI" else "🔴")

    send_gif(
        chat_id, gif,
        f"🏁 RESULTADO FINAL {emoji_res}\n"
        f"━━━━━━━━━━━━━━\n"
        f"💱 Paridade: {emoji} {nome}\n"
        f"⏱ Entrada: {entrada_dt.strftime('%H:%M')}\n"
        f"🎯 Direção: {sinal}\n"
        f"🕒 Gale: {gale_dt.strftime('%H:%M')}\n"
        f"📊 Resultado: {resultado_gale}",
        reply_markup=botao_novo_sinal()
    )


# ─────────────────────────────────────────────────────────────────────────────
# HANDLERS
# ─────────────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["start"])
def start(m):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚀 Gerar Sinal", callback_data="gerar"))
    bot.send_message(m.chat.id, "👋 *Quantix Signals*", parse_mode="Markdown", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data == "gerar")
def gerar(c):
    bot.answer_callback_query(c.id)
    try:
        bot.edit_message_text(
            "Escolha o par:",
            c.message.chat.id,
            c.message.message_id,
            reply_markup=menu_paridades()
        )
    except Exception:
        bot.send_message(c.message.chat.id, "Escolha o par:", reply_markup=menu_paridades())


@bot.callback_query_handler(func=lambda c: c.data.startswith("p_"))
def run(c):
    coin_id = c.data.split("_", 1)[1]
    bot.answer_callback_query(c.id)

    delete_msg(c.message.chat.id, c.message.message_id)

    msg_analise = send_gif(c.message.chat.id, GIF_ANALISE, "🔎 Analisando mercado...")

    threading.Thread(
        target=fluxo_sinal,
        args=(c.message.chat.id, coin_id, msg_analise.message_id),
        daemon=True
    ).start()


# ─────────────────────────────────────────────────────────────────────────────
# POLLING
# ─────────────────────────────────────────────────────────────────────────────

print("BOT ONLINE - QUANTIX CRIPTO")

while True:
    try:
        bot.infinity_polling(timeout=20, long_polling_timeout=10, skip_pending=True)
    except Exception as e:
        print("Polling caiu:", e)
        time.sleep(5)
