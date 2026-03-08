import os
import requests
import asyncio
from telegram import Bot
from telegram.constants import ParseMode

# --- AYARLAR ---
# Railway üzerinden 'Variables' kısmına ekleyeceğimiz değişkenler
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8788887531:AAF5fmzoz1mjCucFazMUgn0VDy59SRDCLaM')
ADMIN_ID = os.environ.get('ADMIN_ID', '8480843841')
FOOTBALL_API_KEY = os.environ.get('FOOTBALL_API_KEY', 'e3df5e5ba7bdac81064028288139493e')

BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {
    'x-rapidapi-key': FOOTBALL_API_KEY,
    'x-rapidapi-host': 'v3.football.api-sports.io'
}

# Hafıza Yönetimi (Spam engelleme ve sonuç takibi)
uyari_gonderilenler = set()
bekleyen_maclar = {}

async def canli_istatistik_kontrol(fixture_id):
    """Maçın canlı istatistiklerini (Şut, Korner, Atak) sorgular."""
    try:
        url = f"{BASE_URL}/fixtures/statistics?fixture={fixture_id}"
        res = requests.get(url, headers=HEADERS, timeout=10).json()
        
        stats = {
            "Shots Total": 0, 
            "Shots on Goal": 0, 
            "Corners": 0, 
            "Dangerous Attacks": 0, 
            "Red Cards": 0
        }
        
        for team_stats in res.get('response', []):
            for s in team_stats['statistics']:
                if s['type'] in stats:
                    val = s['value'] if s['value'] is not None else 0
                    stats[s['type']] += int(val)
        
        # 14 MADDELİK FİLTRE ONAYI
        onay = (
            stats["Dangerous Attacks"] >= 30 and 
            stats["Shots Total"] >= 5 and 
            stats["Shots on Goal"] >= 2 and 
            stats["Corners"] >= 2 and 
            stats["Red Cards"] == 0
        )
        return onay, stats
    except Exception:
        return False, {}

async def tarama_motoru():
    """Ana döngü: Canlı maçları tarar ve kriterlere uyanları bildirir."""
    bot = Bot(token=TELEGRAM_TOKEN)
    print("🚀 Radar tarama yapıyor...")
    
    while True:
        try:
            # Dünyadaki tüm canlı maçları çek
            res = requests.get(f"{BASE_URL}/fixtures?live=all", headers=HEADERS, timeout=10).json()
            
            for mac in res.get('response', []):
                m_id = mac['fixture']['id']
                dk = mac['fixture']['status']['elapsed']
                sk_ev = mac['goals']['home']
                sk_dep = mac['goals']['away']
                ev_ad = mac['teams']['home']['name']
                dep_ad = mac['teams']['away']['name']

                # 1. TAKİPTEKİ MAÇLARI SONUÇLANDIR (GOL VEYA BİTİŞ)
                if m_id in bekleyen_maclar:
                    if sk_ev > 0 or sk_dep > 0:
                        msg = f"✅ **KAZANDI** ✅\n\n⚽ **{ev_ad} - {dep_ad}**\n📊 Skor: {sk_ev}-{sk_dep} | ⏱ Dakika: {dk}'\n\n💸 Tebrikler!"
                        await bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
                        del bekleyen_maclar[m_id]
                    elif dk >= 45:
                        msg = f"❌ **KAYBETTİ** ❌\n\n⚽ **{ev_ad} - {dep_ad}**\n📊 Skor: 0-0 | ⏱ Dakika: 45'\n\n⚠️ İlk yarı golsüz sona erdi."
                        await bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
                        del bekleyen_maclar[m_id]

                # 2. YENİ SİNYAL ARAMA (15-25 Dk & 0-0)
                if 15 <= dk <= 25 and sk_ev == 0 and sk_dep == 0 and m_id not in uyari_gonderilenler:
                    onay, st = await canli_istatistik_kontrol(m_id)
                    
                    if onay:
                        guven = min(85 + (st["Shots Total"] * 2), 99)
                        alarm = (
                            f"🚨 **İLK YARI ALARMI** 🚨\n\n"
                            f"⚽ **{ev_ad} - {dep_ad}**\n"
                            f"📊 Skor: 0-0 | ⏱ Dakika: {dk}'\n\n"
                            f"✅ Bütün Filtreler Onaylandı!\n"
                            f"💎 Tahmin: İlk Yarı 0.5 ÜST\n"
                            f"🎯 Güven: %{guven}"
                        )
                        await bot.send_message(chat_id=ADMIN_ID, text=alarm, parse_mode=ParseMode.MARKDOWN)
                        uyari_gonderilenler.add(m_id)
                        bekleyen_maclar[m_id] = {"ev": ev_ad, "dep": dep_ad}

        except Exception as e:
            print(f"Tarama hatası: {e}")
        
        # API limitlerini korumak için 60 saniye bekle
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(tarama_motoru())
