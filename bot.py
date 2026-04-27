import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
import threading
from datetime import datetime, timedelta
import pytz
import os

TOKEN = os.getenv("TOKEN")  # sem API_KEY — CoinCap é gratuita e sem chave

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

# IDs da CoinCap (diferentes dos do CoinGecko)
COINCAP_ID = {
    "bitcoin":      "bitcoin",
    "ethereum":     "ethereum",
    "binancecoin":  "binance-coin",
    "solana":       "solana",
    "ripple":       "xrp",
    "cardano":      "cardano",
    "dogecoin":     "dogecoin",
    "litecoin":     "litecoin",
    "polkadot":     "polkadot",
    "avalanche-2":  "avalanche",
}

HEADERS = {"Accept-Encoding": "gzip, deflate", "User-Agent": "QuantixBot/1.0"}


# ─────────────────────────────────────────────────────────────────────────────
# COINCAP API  — gratuita, sem chave, sem rate limit agressivo, funciona em cloud
# Endpoint: GET /v2/assets/{id}/history?interval=m1&start=...&end=...
# ─────────────────────────────────────────────────────────────────────────────

def buscar_candles(coin_id, limit=40):
    """
    CoinCap retorna histórico de preço minuto a minuto.
    Como só há um preço por minuto (sem OHLC real), construímos
    open/close usando o preço do minuto anterior como open.
    """
    cap_id = COINCAP_ID.get(coin_id, coin_id)
    agora  = int(time.time() * 1000)
    inicio = agora - (limit + 5) * 60 * 1000  # margem de 5min extra

    url = f"https://api.coincap.io/v2/assets/{cap_id}/history"
    params = {"interval": "m1", "start": inicio, "end": agora}

    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])

        if not data or len(data) < 2:
            print(f"CoinCap sem dados suficientes para {cap_id}: {len(data)} pontos")
            return None

        candles = []
        for i in range(1, len(data)):
            dt    = datetime.fromtimestamp(data[i]["time"] / 1000, tz=timezone)
            open_ = float(data[i - 1]["priceUsd"])
            close = float(data[i]["priceUsd"])
            candles.append({"datetime": dt, "open": open_, "close": close})

        candles.sort(key=lambda c: c["datetime"])
        return candles[-limit:]

    except Exception as e:
        print(f"Erro buscar_candles ({cap_id}):", e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# ANÁLISE  (2 de 3 últimas velas na mesma direção)
# ─────────────────────────────────────────────────────────────────────────────

def analisar(candles):
    if not candles or len(candles) < 3:
        return None

    ultimos = candles[-3:]
    altas   = sum(c["close"] > c["open"] for c in ultimos)
    baixas  = 3 - altas

    print(f"  Análise → altas={altas} baixas={baixas}")
    for c in ultimos:
        dir_ = "▲ CALL" if c["close"] > c["open"] else "▼ PUT"
        print(f"    {c['datetime'].strftime('%H:%M')} open={c['open']:.4f} close={c['close']:.4f} {dir_}")

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
# BUSCA CANDLE ESPECÍFICO  (tolerância ±2min para cobrir granularidade da API)
# ─────────────────────────────────────────────────────────────────────────────

def encontrar_candle(coin_id, alvo_dt, timeout_seg=150):
    fim        = time.time() + timeout_seg
    tolerancia = 120  # segundos

    while time.time() < fim:
        candles = buscar_candles(coin_id, limit=20)

        if candles:
            candidatos = [
                c for c in candles
                if abs((c["datetime"] - alvo_dt).total_seconds()) <= tolerancia
            ]

            if candidatos:
                melhor = min(candidatos, key=lambda c: abs((c["datetime"] - alvo_dt).total_seconds()))
                print(f"  ✅ Candle encontrado: {melhor['datetime'].strftime('%H:%M')} "
                      f"(alvo={alvo_dt.strftime('%H:%M')}) "
                      f"open={melhor['open']:.4f} close={melhor['close']:.4f}")
                return melhor

            mais_recente = candles[-1]
            print(f"  ⏳ Aguardando {alvo_dt.strftime('%H:%M')}... "
                  f"mais recente={mais_recente['datetime'].strftime('%H:%M')}")

        time.sleep(10)  # 10s entre tentativas — respeita rate limit

    print(f"  ❌ Timeout: candle de {alvo_dt.strftime('%H:%M')} não encontrado.")
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
# FLUXO PRINCIPAL  (thread separada por usuário)
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
    time.sleep(5)  # margem para API atualizar

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
    time.sleep(5)

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
