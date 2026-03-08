import os
import requests
import asyncio
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import ParseMode

# --- AYARLAR ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8788887531:AAF5fmzoz1mjCucFazMUgn0VDy59SRDCLaM')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '8480843841'))
FOOTBALL_API_KEY = os.environ.get('FOOTBALL_API_KEY', 'e3df5e5ba7bdac81064028288139493e')

BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {'x-rapidapi-key': FOOTBALL_API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

# Global Değişkenler
is_running = False  # Botun maç arayıp aramadığını kontrol eder
uyari_gonderilenler = set()
bekleyen_maclar = {}

# --- KOMUTLAR ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    hosgeldin_metni = (
        "👋 **İlkyarı Gol Radarı'na Hoş Geldin!**\n\n"
        "Sistem şu an hazır bekliyor. Komutları kullanarak kontrol edebilirsin:\n\n"
        "🔹 `/boton` - Maç taramasını başlatır.\n"
        "🔸 `/botoff` - Maç taramasını durdurur.\n"
        "ℹ️ `/durum` - Botun çalışma durumunu gösterir."
    )
    await update.message.reply_text(hosgeldin_metni, parse_mode=ParseMode.MARKDOWN)

async def boton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_running
    if update.effective_user.id != ADMIN_ID: return
    if not is_running:
        is_running = True
        await update.message.reply_text("🚀 **Radar Aktif!**\nSistem dünyadaki maçları taramaya başladı. Kriterlere uygun müsabaka aranıyor...", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("⚠️ Bot zaten çalışır durumda.")

async def botoff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_running
    if update.effective_user.id != ADMIN_ID: return
    is_running = False
    await update.message.reply_text("🛑 **Radar Durduruldu.**\nMaç taraması askıya alındı. API istekleri kesildi.", parse_mode=ParseMode.MARKDOWN)

async def durum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "🟢 Çalışıyor" if is_running else "🔴 Durduruldu"
    await update.message.reply_text(f"📊 **Bot Durumu:** {status}", parse_mode=ParseMode.MARKDOWN)

# --- ANALİZ MOTORU ---

async def canli_istatistik_kontrol(fixture_id):
    try:
        url = f"{BASE_URL}/fixtures/statistics?fixture={fixture_id}"
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        stats = {"Shots Total": 0, "Shots on Goal": 0, "Corners": 0, "Dangerous Attacks": 0, "Red Cards": 0}
        for team_stats in res.get('response', []):
            for s in team_stats['statistics']:
                if s['type'] in stats:
                    val = s['value'] if s['value'] is not None else 0
                    stats[s['type']] += int(val)
        onay = (stats["Dangerous Attacks"] >= 30 and stats["Shots Total"] >= 5 and 
                stats["Shots on Goal"] >= 2 and stats["Corners"] >= 2 and stats["Red Cards"] == 0)
        return onay, stats
    except: return False, {}

async def tarama_loop(application):
    global is_running
    while True:
        if is_running:
            try:
                res = requests.get(f"{BASE_URL}/fixtures?live=all", headers=HEADERS, timeout=10).json()
                for mac in res.get('response', []):
                    m_id, dk = mac['fixture']['id'], mac['fixture']['status']['elapsed']
                    sk_ev, sk_dep = mac['goals']['home'], mac['goals']['away']
                    ev_ad, dep_ad = mac['teams']['home']['name'], mac['teams']['away']['name']

                    if m_id in bekleyen_maclar:
                        if sk_ev > 0 or sk_dep > 0:
                            await application.bot.send_message(CHAT_ID=ADMIN_ID, text=f"✅ GOL! {ev_ad}-{dep_ad}")
                            del bekleyen_maclar[m_id]

                    if 15 <= dk <= 25 and sk_ev == 0 and sk_dep == 0 and m_id not in uyari_gonderilenler:
                        onay, st = await canli_istatistik_kontrol(m_id)
                        if onay:
                            msg = f"🚨 **SİNYAL:** {ev_ad}-{dep_ad} ({dk}')"
                            await application.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
                            uyari_gonderilenler.add(m_id)
                            bekleyen_maclar[m_id] = True
            except Exception as e: print(f"Hata: {e}")
        await asyncio.sleep(60)

# --- ANA ÇALIŞTIRICI ---

if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("boton", boton))
    application.add_handler(CommandHandler("botoff", botoff))
    application.add_handler(CommandHandler("durum", durum))

    loop = asyncio.get_event_loop()
    loop.create_task(tarama_loop(application))
    application.run_polling()
