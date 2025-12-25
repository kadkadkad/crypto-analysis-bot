import subprocess
import time
import sys

def start_bot():
    print("📊 Bot (Analiz Döngüsü) başlatılıyor...")
    # main.py analiz döngüsünü başlatır
    return subprocess.Popen([sys.executable, "main.py"])

def start_web():
    print("🌐 Web Dashboard başlatılıyor...")
    # web_dashboard.py flask sunucusunu başlatır
    return subprocess.Popen([sys.executable, "web_dashboard.py"])

if __name__ == "__main__":
    p1 = start_bot()
    p2 = start_web()

    try:
        while True:
            # Her iki process'in de canlı olup olmadığını kontrol et
            if p1.poll() is not None:
                print("⚠️ Bot durdu! Yeniden başlatılıyor...")
                p1 = start_bot()
            if p2.poll() is not None:
                print("⚠️ Web sunucusu durdu! Yeniden başlatılıyor...")
                p2 = start_web()
            
            time.sleep(60) # Her dakika kontrol et
    except KeyboardInterrupt:
        print("Durduruluyor...")
        p1.terminate()
        p2.terminate()
