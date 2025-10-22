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
    
    print("\n" + "="*80)
    print("🚀 DASK+ PARAMETRIK SIGORTA BACKEND")
    print("="*80)
    
    # Backend initialize - Sadece ana process'te çalıştır
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        # Bu reload worker'ı (asıl çalışan process)
        initialize_backend()
    
    # Flask çalıştır
    print("\n🌐 FLASK SERVER BAŞLATILIYOR...")
    print("="*80)
    print("📍 Ana Sayfa: http://localhost:5000")
    print("📍 Admin Panel: http://localhost:5000/admin")
    print("💡 Çıkmak için: CTRL+C")
    print("="*80 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
