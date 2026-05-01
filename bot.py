import telebot
import requests
import time
import threading
from datetime import datetime, timedelta, timezone
import pytz

TOKEN = "8516808804:AAFvv383G9LqDZ3BXjeMpQOc26i0JI6W6Pk"  # <<< SUBSTITUA PELO SEU TOKEN REAL
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


# 2) Resultado só depois de 65s a partir do minuto exato de entrada (ex: 21:26:00)
def get_result(chat_id, direction, target_time_dt):
    # 65s a partir de 21:26:00
    target_start = target_time_dt.replace(second=0, microsecond=0)  # 21:26:00
    target_65s = target_start + timedelta(seconds=65)
    now = datetime.now(BR_TZ)

    wait = (target_65s - now).total_seconds()
    if wait < 0:
        wait = 0  # não volta no tempo

    print(f"🕒 get_result: wait = {wait:.1f}s, target_start = {target_start}, target_65s = {target_65s}")
    if wait > 0:
        time.sleep(wait)

    try:
        params = {"vs_currency": "usd", "days": "1"}
        r = requests.get(
            f"{COINGECKO_URL}/coins/{COIN_ID}/ohlc",
            params=params,
            timeout=20
        )
        if r.status_code != 200:
            print(f"❌ CoinGecko HTTP {r.status_code} - {r.text[:100]}")
            if r.status_code == 429:
                bot.send_message(chat_id, "❌ ERRO 429: limite de requisições excedido no CoinGecko. Tente novamente mais tarde.")
            elif r.status_code == 500:
                bot.send_message(chat_id, "❌ ERRO 500: problema temporário no CoinGecko.")
            else:
                bot.send_message(chat_id, f"❌ Erro HTTP {r.status_code} ao verificar o CoinGecko.")
            return

        data = r.json()
        if not isinstance(data, list) or len(data) == 0:
            print("❌ CoinGecko retornou data vazia ou inválida")
            bot.send_message(chat_id, "❌ Sem dados para BTC (API).")
            return

        target_year = target_time_dt.year
        target_month = target_time_dt.month
        target_day = target_time_dt.day
        target_hour = target_time_dt.hour
        target_minute = target_time_dt.minute

        # Tenta achar a vela 21:26 ou 21:27
        for i in range(len(data)-1, max(-1, len(data)-100), -1):
            row = data[i]
            if not isinstance(row, list) or len(row) < 5:
                continue
            try:
                ts = row[0] / 1000
                o = float(row[1])
                c = float(row[4])
                candle_dt = datetime.fromtimestamp(ts, tz=UTC_TZ).astimezone(BR_TZ)

                if (candle_dt.year == target_year and
                    candle_dt.month == target_month and
                    candle_dt.day == target_day and
                    candle_dt.hour == target_hour and
                    candle_dt.minute in [target_minute, target_minute + 1]):
                    is_win = (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o)
                    status = "✅ WIN" if is_win else "❌ LOSS"
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
                    return

            except Exception as e:
                print(f"❌ Erro processando vela: {str(e)[:80]}")

        # Se não achar 21:26/21:27, tenta a última vela
        if data:
            row = data[-1]
            if isinstance(row, list) and len(row) >= 5:
                try:
                    ts = row[0] / 1000
                    o = float(row[1])
                    c = float(row[4])
                    candle_dt = datetime.fromtimestamp(ts, tz=UTC_TZ).astimezone(BR_TZ)
                    candle_time = candle_dt.strftime("%H:%M")
                    is_win = (direction == "COMPRA" and c > o) or (direction == "VENDA" and c < o)
                    status = "✅ WIN" if is_win else "❌ LOSS"

                    text = f"""
🎯 RESULTADO FINAL (ÚLTIMA VELA)

━━━━━━━━━━━━━━━━━━
商贸 {SYMBOL}
⏱ Entrada estimada: {candle_time}
🎯 {direction}
🏆 {status}
                    """
                    bot.send_message(chat_id, text)
                    return
                except Exception as e:
                    print(f"❌ Erro lendo última vela: {str(e)[:80]}")

        bot.send_message(chat_id, "❌ Não foi possível validar o resultado (sem vela clara).")

    except Exception as e:
        print(f"❌ Erro completo em get_result: {str(e)[:120]}")
        bot.send_message(chat_id, "❌ ERRO inesperado ao calcular resultado.")


# 3) Comando /start + gera sinal
@bot.message_handler(commands=["start"])
def start(m):
    text = f"""
🤖 Bot Simples de Sinais (BITCOIN)

Use /sinal para gerar 1 sinal de 1m.

Se você pedir o sinal às 21:25:
✨ Entrada = 21:26
📅 O resultado aparece após 65s a partir de 21:26:00 (≈ 21:27:05)
🎯 Só usa vela 21:26 ou 21:27 do mesmo dia
🎯 Se CoinGecko falhar, manda mensagem de erro clara
    """
    bot.send_message(m.chat.id, text)


@bot.message_handler(commands=["sinal"])
def gerar_sinal(m):
    now = datetime.now(BR_TZ)
    entry = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
    entry_time = entry.strftime("%H:%M")

    direction = analyze()
    text = f"""
🚂 SINAL GERADO

━━━━━━━━━━━━━━━━━━
商贸 {SYMBOL}
⏱ Entrada: {entry_time}
🎯 {direction}

Resultado após 65s a partir do minuto exato.
    """
    bot.send_message(m.chat.id, text)

    threading.Thread(
        target=get_result,
        args=(m.chat.id, direction, entry),
        daemon=True
    ).start()


print("🚀 Bot Simples Ativo (1 sinal de BTC a cada 45s, 1m)")
bot.polling()
