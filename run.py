#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DASK+ Parametrik Sigorta - Ana Giriş Noktası
==============================================
Bu script Flask backend'i başlatır.
"""

import sys
import os
from pathlib import Path
from multiprocessing import freeze_support

# Multiprocessing için Windows desteği
freeze_support()

# Unicode encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# src/ klasörünü Python path'ine ekle
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

# Flask app'i başlat
if __name__ == '__main__':
    from app import app, initialize_backend
    
    # ASCII Art Banner
    print("="*80)
    print("                                                                               ")
    print("                    DASK+ PARAMETRİK SİGORTA SİSTEMİ                        ")
    print("                                                                               ")
    print("                Blockchain + AI Destekli Deprem Sigortası               ")
    print("                                                                               ")
    print("="*80)
    sys.stdout.flush()  # Banner'ı hemen göster
    
    # Backend'i başlat - Sadece bir kez!
    print(" Backend Servisleri Başlatılıyor...\n")
    sys.stdout.flush()
    
    initialize_backend()
    
    print("="*80)
    print("")
    print("                          FLASK SERVER BAŞLATILIYOR                         ")
    print("")
    print("                                                                               ")
    print("   Ana Sayfa:        http://localhost:5000                                  ")
    print("   Admin Panel:      http://localhost:5000/admin                            ")
    print("   Blockchain API:   http://localhost:5000/api/blockchain/stats             ")
    print("                                                                               ")
    print("   Çıkmak için CTRL+C tuşlarına basın                                       ")
    print("                                                                               ")
    print("="*80)
    sys.stdout.flush()  # Server başlangıç mesajını hemen göster
    
    try:
        # Flask sunucusunu başlat (blocking - sunucu kapanana kadar bekler)
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,        # Production mode - Temiz çıktı
            threaded=True,      # Thread desteği
            use_reloader=False  # Auto-reload kapalı - Tek başlatma
        )
    except KeyboardInterrupt:
        print("\n")
        print("")
        print("                           SERVER KAPATILIYOR...                            ")
        print("")
    finally:
        print()
        print(" DASK+ Backend başarıyla kapatıldı.")
        print()
