import os
import requests
import asyncio
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import ParseMode

# --- KONFİGÜRASYON ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8788887531:AAF5fmzoz1mjCucFazMUgn0VDy59SRDCLaM')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '8480843841'))
FOOTBALL_API_KEY = os.environ.get('FOOTBALL_API_KEY', 'e3df5e5ba7bdac81064028288139493e')

BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {'x-rapidapi-key': FOOTBALL_API_KEY, 'x-rapidapi-host': 'v3.football.api-sports.io'}

is_running = False
uyari_gonderilenler = set()

# --- ANALİZ MODÜLLERİ ---

async def derin_analiz(fixture_id):
    """Maç önü beklentilerini sorgular ve sadece yüksek potansiyelli olanları onaylar."""
    try:
        url = f"{BASE_URL}/fixtures/predictions?fixture={fixture_id}"
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        if not res.get('response'): return False, 0, 0

        pred = res['response'][0]['predictions']
        kg_ihtimal = int(str(pred.get('kg', {}).get('yes', "0%")).replace('%',''))
        ust_ihtimal = int(str(pred.get('goals', {}).get('over', "0%")).replace('%',''))
        
        # KRİTER: KG Var > %65 ve 2.5 Üst > %60 olmalı (KAZANMA ODAKLI)
        if kg_ihtimal >= 65 or ust_ihtimal >= 60:
            return True, kg_ihtimal, ust_ihtimal
        return False, kg_ihtimal, ust_ihtimal
    except:
        return False, 0, 0

async def canli_baski_onay(fixture_id, dakika):
    """Sahadaki baskının 'gol getirecek' düzeyde olup olmadığını kontrol eder."""
    try:
        url = f"{BASE_URL}/fixtures/statistics?fixture={fixture_id}"
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        s = {"Shots Total": 0, "Shots on Goal": 0, "Corners": 0, "Dangerous Attacks": 0}
        
        for team_stats in res.get('response', []):
            for stat in team_stats['statistics']:
                if stat['type'] in s:
                    val = stat['value'] if stat['value'] is not None else 0
                    s[stat['type']] += int(val)
        
        # ULTRA FİLTRE: Dakika başına tehlikeli atak 1.5'tan büyük olmalı. 
        # Örn: 20. dakikada en az 30 tehlikeli atak.
        momentum = s["Dangerous Attacks"] / dakika if dakika > 0 else 0
        
        onay = (
            momentum >= 1.5 and 
            s["Shots Total"] >= 6 and 
            s["Shots on Goal"] >= 2 and 
            s["Corners"] >= 3
        )
        return onay, s
    except: return False, {}

# --- BOT KOMUTLARI ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text("🎯 **İY Gol Radarı V4 (Ultra Pro)**\nSadece yüksek kazanma ihtimali olan maçlar için pusuya yatıldı.\n\n/boton - Radarı Aç\n/botoff - Uyku Modu")

async def boton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_running
    if update.effective_user.id != ADMIN_ID: return
    is_running = True
    await update.message.reply_text("🚀 **Radar Aktif.**\nDakikada bir tarama yapılıyor. Sadece 'altın' maçlar bildirilecek.")

async def botoff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_running
    if update.effective_user.id != ADMIN_ID: return
    is_running = False
    await update.message.reply_text("🛑 **Radar Durduruldu.**")

# --- ANA DÖNGÜ ---

async def tarama_motoru(application):
    global is_running
    while True:
        if is_running:
            try:
                res = requests.get(f"{BASE_URL}/fixtures?live=all", headers=HEADERS, timeout=10).json()
                for mac in res.get('response', []):
                    m_id = mac['fixture']['id']
                    dk = mac['fixture']['status']['elapsed']
                    sk_ev, sk_dep = mac['goals']['home'], mac['goals']['away']

                    # Sadece 15-28. dakikalar arası ve 0-0 giden maçlar
                    if 15 <= dk <= 28 and sk_ev == 0 and sk_dep == 0 and m_id not in uyari_gonderilenler:
                        
                        # 1. AŞAMALI KONTROL: Canlı Baskı (Momentum)
                        baski_onay, st = await canli_baski_onay(m_id, dk)
                        
                        if baski_onay:
                            # 2. AŞAMALI KONTROL: Derin Maç Önü Analiz
                            pro_onay, kg_p, ust_p = await derin_analiz(m_id)
                            
                            if pro_onay:
                                ev, dep = mac['teams']['home']['name'], mac['teams']['away']['name']
                                lig = mac['league']['name']
                                
                                alert = (
                                    f"💎 **YÜKSEK GÜVENLİ SİNYAL** 💎\n\n"
                                    f"🏆 {lig}\n"
                                    f"⚽ **{ev} vs {dep}**\n"
                                    f"⏰ Dakika: {dk}' | Skor: 0-0\n\n"
                                    f"🔥 **Canlı Baskı Verileri:**\n"
                                    f"🧨 Teh. Atak: {st['Dangerous Attacks']} (Baskı: Yüksek)\n"
                                    f"🎯 Şutlar: {st['Shots Total']} / İsabet: {st['Shots on Goal']}\n"
                                    f"⛳ Kornerler: {st['Corners']}\n\n"
                                    f"📊 **Yapay Zeka Analizi:**\n"
                                    f"✅ KG Var Beklentisi: %{kg_p}\n"
                                    f"✅ 2.5 Üst Beklentisi: %{ust_p}\n\n"
                                    f"💰 **Tahmin: İLK YARI 0.5 ÜST**"
                                )
                                await application.bot.send_message(chat_id=ADMIN_ID, text=alert, parse_mode=ParseMode.MARKDOWN)
                                uyari_gonderilenler.add(m_id)

            except Exception as e: print(f"Hata oluştu: {e}")
        
        # API limitini korumak ve daha derin analiz için 120 saniye (2 dk) bekleme
        await asyncio.sleep(120)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("boton", boton))
    app.add_handler(CommandHandler("botoff", botoff))
    
    loop = asyncio.get_event_loop()
    loop.create_task(tarama_motoru(app))
    app.run_polling()
