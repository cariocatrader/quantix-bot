import telebot
import requests
import time
from datetime import datetime, timedelta, timezone
import pytz

TOKEN = "SEU_TOKEN_AQUI"  # mude isso
bot = telebot.TeleBot(TOKEN)

# Fuso Brasil
BR_TZ = pytz.timezone('America/Sao_Paulo')
UTC_TZ = pytz.timezone('UTC')

COINGECKO_URL = "https://api.coingecko.com/api/v3"
COIN_ID = "bitcoin"
SYMBOL = "₿ Bitcoin"

def get_br_time():
    return datetime.now(BR_TZ).strftime("%H:%M")

last_call = None

# 1) Análise simples (1 chamada CoinGecko)
def analyze():
    global last_call
    if last_call is not None:
        diff = (datetime.now() - last_call).total_seconds()
        if diff < 45:
            time.sleep(45 - diff)
    last_call = datetime.now()

    try:
        params = {"vs_currency": "usd", "days": "1"}
        r = requests.get(
            f"{COINGECKO_URL}/coins/{COIN_ID}/ohlc",
            params=params,
            timeout=20
        )
        if r.status_code != 200:
            print(f"❌ CoinGecko HTTP {r.status_code}")
            return "COMPRA"

        data = r.json()
        if not data or not isinstance(data, list) or len(data) == 0:
            return "COMPRA"

        closes = []
        for i in range(len(data)-1, max(-1, len(data)-5), -1):
            if i < 0:
                break
            row = data[i]
            if isinstance(row, list) and len(row) >= 5:
                try:
                    c = float(row[4])
                    closes.append(c)
                except:
                    continue

        if len(closes) < 5:
            return "COMPRA"
        return "COMPRA" if closes[-1] > closes[-3] else "VENDA"

    except Exception as e:
        print(f"❌ Erro analyze: {str(e)[:80]}")
        return "COMPRA"


# 2) Resultado só depois de 65s (sem inventar antes)
def get_result(chat_id, direction, entry_time_dt):
    time.sleep(65)  # espera 65s REAIS

    try:
        params = {"vs_currency": "usd", "days": "1"}
        r = requests.get(
            f"{COINGECKO_URL}/coins/{COIN_ID}/ohlc",
            params=params,
            timeout=20
        )
        if r.status_code != 200:
            print(f"❌ CoinGecko HTTP {r.status_code} (get_result)")
            bot.send_message(chat_id, "❌ ERRO ao verificar resultado.")
            return

        data = r.json()
        if not data or not isinstance(data, list) or len(data) == 0:
            bot.send_message(chat_id, "❌ Sem dados para BTC, não foi possível definir resultado.")
            return

        # pega a última vela fechada
        row = data[-1]
        ts = row[0] / 1000
        o = float(row[1])
        c = float(row[4])

        is_win = (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o)
        status = "✅ WIN" if is_win else "❌ LOSS"
        candle_dt = datetime.fromtimestamp(ts, tz=UTC_TZ).astimezone(BR_TZ)
        candle_time = candle_dt.strftime("%H:%M")

        text = f"""
🎯 RESULTADO FINAL

━━━━━━━━━━━━━━━━━━
商贸 {SYMBOL}
⏱ Entrada: {candle_time}
🎯 {direction}
🏆 {status}
        """
        bot.send_message(chat_id, text)
    except Exception as e:
        print(f"❌ Erro get_result: {str(e)[:80]}")
        bot.send_message(chat_id, "❌ ERRO ao computar resultado.")


# 3) Comando /start + gera sinal
@bot.message_handler(commands=["start"])
def start(m):
    text = f"""
🤖 Bot Simples de Sinais (BITCOIN)

Use /sinal para gerar 1 sinal de 1m.

Tudo após 65s, sem mensagem de erro prematura.
    """
    bot.send_message(m.chat.id, text)


@bot.message_handler(commands=["sinal"])
def gerar_sinal(m):
    entry_time = get_br_time()
    direction = analyze()
    text = f"""
🚂 SINAL GERADO

━━━━━━━━━━━━━━━━━━
商贸 {SYMBOL}
⏱ Entrada: {entry_time}
🎯 {direction}

Aguardando 65s para resultado...
    """
    bot.send_message(m.chat.id, text)

    # roda o resultado só após 65s, sem enviar nada antes
    threading.Thread(
        target=get_result,
        args=(m.chat.id, direction, datetime.now(BR_TZ)),
        daemon=True
    ).start()


print("🚀 Bot Simples Ativo (1 sinal de BTC a cada 45s, 1m)")
bot.polling()
