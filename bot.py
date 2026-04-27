import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import threading
from datetime import datetime, timedelta
import pytz
import os

TOKEN = os.getenv("TOKEN")

# Session com retry para CoinCap
_session = requests.Session()
_retry   = Retry(total=4, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
_session.mount("https://", HTTPAdapter(max_retries=_retry))

# threaded=False: cada handler lanca sua propria thread
# evita que excecoes em workers derrubem o infinity_polling
bot = telebot.TeleBot(TOKEN, threaded=False)
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
# COINCAP API
# ─────────────────────────────────────────────────────────────────────────────

def buscar_candles(coin_id, limit=40):
    """
    Busca histórico de preço minuto a minuto via CoinCap.
    Constrói open/close usando o preço do minuto anterior como open.
    """
    cap_id = COINCAP_ID.get(coin_id, coin_id)
    agora  = int(time.time() * 1000)
    inicio = agora - (limit + 10) * 60 * 1000

    url    = f"https://api.coincap.io/v2/assets/{cap_id}/history"
    params = {"interval": "m1", "start": inicio, "end": agora}

    try:
        r = _session.get(url, params=params, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])

        if not data or len(data) < 2:
            print(f"CoinCap sem dados para {cap_id}: {len(data)} pontos")
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
# ANÁLISE
# ─────────────────────────────────────────────────────────────────────────────

def analisar(candles, expiracao):
    """
    1min → analisa as 3 últimas velas de 1min.
    5min → agrupa as últimas 15 velas de 1min em 3 blocos de 5min
           e verifica a direção de cada bloco.
    """
    if not candles or len(candles) < 3:
        return None

    if expiracao == 1:
        ultimos = candles[-3:]
        grupos  = [{"open": c["open"], "close": c["close"]} for c in ultimos]

    else:  # expiracao == 5
        if len(candles) < 15:
            return None
        # agrupa em 3 blocos de 5 velas (open do 1º, close do último)
        grupos = []
        for b in range(3):
            bloco = candles[-(15 - b * 5): -(10 - b * 5)] if b < 2 else candles[-5:]
            grupos.append({"open": bloco[0]["open"], "close": bloco[-1]["close"]})

    altas  = sum(g["close"] > g["open"] for g in grupos)
    baixas = 3 - altas

    print(f"  Análise ({expiracao}min) → altas={altas} baixas={baixas}")
    for i, g in enumerate(grupos):
        dir_ = "▲ CALL" if g["close"] > g["open"] else "▼ PUT"
        print(f"    Bloco {i+1}: open={g['open']:.4f} close={g['close']:.4f} {dir_}")

    if altas >= 2:
        return "CALL"
    if baixas >= 2:
        return "PUT"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# HORÁRIOS DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────

def proxima_entrada_1min():
    """Próximo minuto cheio."""
    agora = datetime.now(timezone)
    return agora.replace(second=0, microsecond=0) + timedelta(minutes=1)


def proxima_entrada_5min():
    """Próximo minuto que seja múltiplo de 5 (ex: 14:25, 14:30...)."""
    agora   = datetime.now(timezone)
    base    = agora.replace(second=0, microsecond=0) + timedelta(minutes=1)
    resto   = base.minute % 5
    avanco  = (5 - resto) % 5  # quantos minutos faltam pro próximo múltiplo de 5
    return base + timedelta(minutes=avanco)


def esperar_ate(ts):
    while datetime.now(timezone) < ts:
        time.sleep(0.2)


# ─────────────────────────────────────────────────────────────────────────────
# BUSCA CANDLE ESPECÍFICO
# ─────────────────────────────────────────────────────────────────────────────

def encontrar_candle(coin_id, alvo_dt, tolerancia_seg=120, timeout_seg=180):
    """
    Retorna o candle mais próximo de alvo_dt dentro da tolerância.
    Para 5min, a tolerância é maior pois buscamos o candle de fechamento
    que pode ser alguns segundos depois do esperado.
    """
    fim = time.time() + timeout_seg

    while time.time() < fim:
        candles = buscar_candles(coin_id, limit=20)

        if candles:
            candidatos = [
                c for c in candles
                if abs((c["datetime"] - alvo_dt).total_seconds()) <= tolerancia_seg
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

        time.sleep(10)

    print(f"  ❌ Timeout: candle de {alvo_dt.strftime('%H:%M')} não encontrado.")
    return None


def encontrar_candle_5min(coin_id, entrada_dt, tolerancia_seg=120, timeout_seg=180):
    """
    Para expiração de 5min, busca o candle do momento de fechamento
    (entrada + 5min) e constrói open/close a partir de velas de 1min
    agrupadas nessa janela de 5 minutos.
    """
    fechamento_dt = entrada_dt + timedelta(minutes=5)
    fim           = time.time() + timeout_seg

    while time.time() < fim:
        candles = buscar_candles(coin_id, limit=40)

        if candles:
            # filtra velas dentro da janela entrada → fechamento
            janela = [
                c for c in candles
                if entrada_dt <= c["datetime"] <= fechamento_dt + timedelta(seconds=tolerancia_seg)
            ]

            # aguarda pelo menos a vela de fechamento aparecer
            tem_fechamento = any(
                abs((c["datetime"] - fechamento_dt).total_seconds()) <= tolerancia_seg
                for c in janela
            )

            if janela and tem_fechamento:
                open_5  = janela[0]["open"]
                close_5 = janela[-1]["close"]
                candle  = {
                    "datetime": janela[-1]["datetime"],
                    "open":     open_5,
                    "close":    close_5,
                }
                print(f"  ✅ Candle 5min: {entrada_dt.strftime('%H:%M')}→{fechamento_dt.strftime('%H:%M')} "
                      f"open={open_5:.4f} close={close_5:.4f}")
                return candle

            mais_recente = candles[-1] if candles else None
            if mais_recente:
                print(f"  ⏳ Aguardando fechamento {fechamento_dt.strftime('%H:%M')}... "
                      f"mais recente={mais_recente['datetime'].strftime('%H:%M')}")

        time.sleep(10)

    print(f"  ❌ Timeout: candle 5min de {entrada_dt.strftime('%H:%M')} não encontrado.")
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


def menu_expiracao(coin_id):
    nome, emoji = DISPLAY[coin_id]
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⚡ 1 Minuto",  callback_data=f"e_{coin_id}_1"),
        InlineKeyboardButton("🕐 5 Minutos", callback_data=f"e_{coin_id}_5"),
    )
    return kb, nome, emoji


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
# FLUXO 1 MINUTO
# ─────────────────────────────────────────────────────────────────────────────

def fluxo_1min(chat_id, coin_id, msg_analise_id):
    nome, emoji = DISPLAY[coin_id]

    candles = buscar_candles(coin_id, limit=40)
    sinal   = analisar(candles, expiracao=1) if candles else None

    delete_msg(chat_id, msg_analise_id)

    if not sinal:
        bot.send_message(chat_id, "❌ Mercado lateral — sem sinal válido.", reply_markup=botao_novo_sinal())
        return

    entrada_dt = proxima_entrada_1min()
    gale_dt    = entrada_dt + timedelta(minutes=1)

    bot.send_message(
        chat_id,
        f"🚀 SINAL ENVIADO\n"
        f"━━━━━━━━━━━━━━\n"
        f"💱 Paridade: {emoji} {nome}\n"
        f"⏱ Entrada: {entrada_dt.strftime('%H:%M')}\n"
        f"🎯 Direção: {sinal}\n"
        f"⏳ Expiração: 1 minuto\n"
        f"🔄 Gale: {gale_dt.strftime('%H:%M')}"
    )

    # aguarda fechamento da vela de entrada
    esperar_ate(entrada_dt + timedelta(minutes=1))
    time.sleep(5)

    candle_entrada = encontrar_candle(coin_id, entrada_dt, tolerancia_seg=120, timeout_seg=120)

    if not candle_entrada:
        bot.send_message(chat_id, f"⚠️ Não consegui confirmar a entrada {entrada_dt.strftime('%H:%M')}.", reply_markup=botao_novo_sinal())
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
            f"⏳ Expiração: 1 minuto\n"
            f"📊 Resultado: {resultado}",
            reply_markup=botao_novo_sinal()
        )
        return

    # Gale
    bot.send_message(chat_id, f"⚠️ {entrada_dt.strftime('%H:%M')} LOSS → GALE em {gale_dt.strftime('%H:%M')}...")

    esperar_ate(gale_dt + timedelta(minutes=1))
    time.sleep(5)

    candle_gale = encontrar_candle(coin_id, gale_dt, tolerancia_seg=120, timeout_seg=120)

    if not candle_gale:
        bot.send_message(chat_id, f"⚠️ Não consegui confirmar o Gale {gale_dt.strftime('%H:%M')}.", reply_markup=botao_novo_sinal())
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
        f"⏳ Expiração: 1 minuto\n"
        f"🔄 Gale: {gale_dt.strftime('%H:%M')}\n"
        f"📊 Resultado: {resultado_gale}",
        reply_markup=botao_novo_sinal()
    )


# ─────────────────────────────────────────────────────────────────────────────
# FLUXO 5 MINUTOS
# ─────────────────────────────────────────────────────────────────────────────

def fluxo_5min(chat_id, coin_id, msg_analise_id):
    nome, emoji = DISPLAY[coin_id]

    candles = buscar_candles(coin_id, limit=40)
    sinal   = analisar(candles, expiracao=5) if candles else None

    delete_msg(chat_id, msg_analise_id)

    if not sinal:
        bot.send_message(chat_id, "❌ Mercado lateral — sem sinal válido.", reply_markup=botao_novo_sinal())
        return

    entrada_dt    = proxima_entrada_5min()
    fechamento_dt = entrada_dt + timedelta(minutes=5)
    gale_dt       = fechamento_dt  # entrada do gale = próximo múltiplo de 5 após o loss
    gale_fecha_dt = gale_dt + timedelta(minutes=5)

    bot.send_message(
        chat_id,
        f"🚀 SINAL ENVIADO\n"
        f"━━━━━━━━━━━━━━\n"
        f"💱 Paridade: {emoji} {nome}\n"
        f"⏱ Entrada: {entrada_dt.strftime('%H:%M')}\n"
        f"🎯 Direção: {sinal}\n"
        f"⏳ Expiração: 5 minutos\n"
        f"🏁 Fechamento: {fechamento_dt.strftime('%H:%M')}\n"
        f"🔄 Gale: {gale_dt.strftime('%H:%M')} → {gale_fecha_dt.strftime('%H:%M')}"
    )

    # aguarda fechamento da vela de 5min
    esperar_ate(fechamento_dt)
    time.sleep(5)

    candle_entrada = encontrar_candle_5min(coin_id, entrada_dt, tolerancia_seg=120, timeout_seg=180)

    if not candle_entrada:
        bot.send_message(chat_id, f"⚠️ Não consegui confirmar a entrada {entrada_dt.strftime('%H:%M')}.", reply_markup=botao_novo_sinal())
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
            f"⏳ Expiração: 5 minutos\n"
            f"🏁 Fechamento: {fechamento_dt.strftime('%H:%M')}\n"
            f"📊 Resultado: {resultado}",
            reply_markup=botao_novo_sinal()
        )
        return

    # Gale
    bot.send_message(
        chat_id,
        f"⚠️ {entrada_dt.strftime('%H:%M')} LOSS → GALE {gale_dt.strftime('%H:%M')} → {gale_fecha_dt.strftime('%H:%M')}..."
    )

    esperar_ate(gale_fecha_dt)
    time.sleep(5)

    candle_gale = encontrar_candle_5min(coin_id, gale_dt, tolerancia_seg=120, timeout_seg=180)

    if not candle_gale:
        bot.send_message(chat_id, f"⚠️ Não consegui confirmar o Gale {gale_dt.strftime('%H:%M')}.", reply_markup=botao_novo_sinal())
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
        f"⏳ Expiração: 5 minutos\n"
        f"🔄 Gale: {gale_dt.strftime('%H:%M')} → {gale_fecha_dt.strftime('%H:%M')}\n"
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
def escolher_expiracao(c):
    coin_id = c.data.split("_", 1)[1]
    bot.answer_callback_query(c.id)

    kb, nome, emoji = menu_expiracao(coin_id)

    try:
        bot.edit_message_text(
            f"Par: {emoji} {nome}\nEscolha a expiração:",
            c.message.chat.id,
            c.message.message_id,
            reply_markup=kb
        )
    except Exception:
        bot.send_message(
            c.message.chat.id,
            f"Par: {emoji} {nome}\nEscolha a expiração:",
            reply_markup=kb
        )


@bot.callback_query_handler(func=lambda c: c.data.startswith("e_"))
def run(c):
    # formato: e_{coin_id}_{expiracao}
    partes     = c.data.split("_", 2)   # ["e", coin_id, "1" ou "5"]
    # coin_id pode ter hífen (ex: avalanche-2), então dividimos só pelos 2 primeiros "_"
    _, coin_id, exp_str = c.data.split("_", 2)
    expiracao  = int(exp_str)

    bot.answer_callback_query(c.id)
    delete_msg(c.message.chat.id, c.message.message_id)

    msg_analise = send_gif(c.message.chat.id, GIF_ANALISE, "🔎 Analisando mercado...")

    fluxo = fluxo_1min if expiracao == 1 else fluxo_5min

    threading.Thread(
        target=fluxo,
        args=(c.message.chat.id, coin_id, msg_analise.message_id),
        daemon=True
    ).start()


# ─────────────────────────────────────────────────────────────────────────────
# POLLING
# ─────────────────────────────────────────────────────────────────────────────

print("BOT ONLINE - QUANTIX CRIPTO")

while True:
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=15, skip_pending=True, allowed_updates=["message","callback_query"])
    except Exception as e:
        print("Polling caiu:", e)
        time.sleep(5)
