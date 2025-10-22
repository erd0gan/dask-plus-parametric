# 🏠 DASK+ Parametrik Sigorta Sistemi

## 📋 Genel Bakış

**DASK+ Parametrik**, Türkiye'nin ilk yapay zeka destekli parametrik deprem sigortası sistemidir. Geleneksel DASK sigortasına modern bir alternatif sunarak, deprem sonrası hızlı ödeme garantisi sağlar.

### 🎯 Ana Özellikler

- ✅ **Hızlı Ödeme:** Deprem sonrası 10-14 gün içinde ödeme garantisi
- 🤖 **Yapay Zeka Destekli:** ML bazlı risk modelleme ve dinamik fiyatlandırma
- 📊 **Gerçek Zamanlı Veri:** Kandilli Rasathanesi canlı deprem verisi
- 🎯 **Parametrik Tetikleme:** PGA/PGV eşikleri ile otomatik ödeme
- 💰 **Esnek Paketler:** 250K - 1.5M TL arası teminat seçenekleri
- 📍 **Hassas Lokasyon:** Mahalle bazında risk analizi

## 🚀 Hızlı Başlangıç

### Gereksinimler

- Python 3.8+
- pip (Python paket yöneticisi)
- 4GB+ RAM

### Kurulum

```powershell
# 1. Repository'yi klonlayın
git clone https://github.com/[kullanici-adi]/dask-plus-parametrik.git
cd dask-plus-parametrik

# 2. Virtual environment oluşturun
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Bağımlılıkları yükleyin
pip install -r requirements.txt

# 4. Uygulamayı başlatın
python app.py
```

### İlk Çalıştırma

Uygulama ilk çalıştırıldığında otomatik olarak:
- ✅ `data/` klasörünü oluşturur
- ✅ 10,000 gerçekçi bina verisi üretir
- ✅ Kandilli servisini başlatır
- ✅ AI modellerini hazırlar

```
================================================================================
DASK+ BACKEND BAŞLATILIYOR...
================================================================================
✅ Kandilli Service hazır
📊 Bina verisi oluşturuluyor...
✅ 10000 bina verisi oluşturuldu
✅ Pricing System hazır
✅ Earthquake Analyzer hazır
✅ Building Loader hazır
✅ Trigger Engine hazır
================================================================================
✅ BACKEND BAŞLATILDI!
================================================================================
```

## 🌐 Kullanım

### Web Arayüzü

Uygulama başlatıldıktan sonra:

- **Ana Sayfa:** http://localhost:5000
- **Admin Panel:** http://localhost:5000/admin

### API Endpoint'leri

#### 1. Deprem Verileri (Gerçek Zamanlı)
```bash
GET /api/earthquakes?min_magnitude=2.0&limit=10
```

#### 2. Prim Hesaplama
```bash
POST /api/calculate-premium
Content-Type: application/json

{
  "il": "İstanbul",
  "ilce": "Kadıköy",
  "mahalle": "Fenerbahçe",
  "package": "temel"
}
```

#### 3. Parametrik Simülasyon
```bash
POST /api/simulate-trigger
Content-Type: application/json

{
  "coverage": 250000,
  "location": "İstanbul/Kadıköy"
}
```

#### 4. Dashboard İstatistikleri
```bash
GET /api/dashboard/stats
```

### Test

```powershell
# API testleri
python tests/test_api.py

# Blockchain testleri
python tests/test_blockchain.py
```

### Blockchain Toplu Senkronizasyon

```python
# Python'dan doğrudan çalıştır
from src.blockchain_manager import BlockchainManager

blockchain = BlockchainManager(enable_blockchain=True, async_mode=True)

# Basit toplu kayıt
blockchain.bulk_record_policies(limit=100)

# Detaylı loglama ile
blockchain.bulk_sync_with_logging(batch_size=100)

blockchain.shutdown()
```

## 📁 Proje Yapısı

```
UI-Latest/
│
├── run.py                  # Ana giriş noktası
│
├── src/                    # Backend kaynak kodları
│   ├── app.py              # Flask backend API
│   ├── auth.py             # Authentication
│   ├── pricing.py          # AI fiyatlandırma sistemi
│   ├── trigger.py          # Parametrik trigger engine
│   ├── generator.py        # Veri üretici
│   ├── blockchain_manager.py      # Blockchain yöneticisi (toplu sync dahil)
│   ├── blockchain_service.py      # Blockchain servisi
│   └── dask_plus_simulator.py     # Blockchain simulator
│
├── static/                 # Frontend dosyaları
│   ├── index.html          # Ana sayfa
│   ├── dashboard.html      # Müşteri paneli
│   ├── admin.html          # Admin paneli
│   ├── styles.css          # Stil dosyası
│   └── dashboard.css       # Dashboard stilleri
│
├── tests/                  # Test dosyaları
│   ├── test_api.py         # API testleri
│   ├── test_blockchain.py  # Blockchain testleri
│   └── README.md           # Test dokümantasyonu
│
├── data/                   # Veri klasörü (otomatik oluşturulur)
│   ├── buildings.csv       # Bina verisi
│   ├── customers.csv       # Müşteri verisi
│   ├── earthquakes.csv     # Deprem verisi
│   ├── blockchain_records.csv     # Blockchain kayıt listesi
│   └── blockchain_operations.log  # Blockchain işlem logu
│
├── docs/                   # Dokümantasyon
│   └── README.md           # Bu dosya
│
└── config/
    └── requirements.txt    # Python bağımlılıkları
```

## 🧪 Teknoloji Yığını

### Backend
- **Flask:** Web framework
- **Pandas/NumPy:** Veri işleme
- **Scikit-learn:** Machine learning
- **Requests:** HTTP client (Kandilli entegrasyonu)
- **Geopy:** Coğrafi hesaplamalar

### Frontend
- **HTML5/CSS3:** Modern UI
- **JavaScript:** Dinamik içerik
- **Chart.js:** Grafikler
- **Leaflet/Folium:** Haritalar
- **Font Awesome:** İkonlar

### Veri Kaynakları
- **Kandilli Rasathanesi:** Gerçek zamanlı deprem verisi
- **AFAD:** Tarihi deprem kayıtları
- **TÜİK:** Bina istatistikleri

## 💼 Paket Yapısı

### 🥉 Temel Paket
- **Teminat:** 250,000 TL
- **Prim Oranı:** %1.0 + risk faktörleri
- **PGA Eşikleri:** 0.10g / 0.20g / 0.35g
- **Ödeme Süresi:** 14 gün

### 🥈 Standard Paket
- **Teminat:** 750,000 TL
- **Prim Oranı:** %1.0 + risk faktörleri
- **PGA Eşikleri:** 0.12g / 0.25g / 0.40g
- **Ödeme Süresi:** 14 gün

### 🥇 Premium Paket
- **Teminat:** 1,500,000 TL
- **Prim Oranı:** %1.0 + risk faktörleri
- **PGA Eşikleri:** 0.15g / 0.30g / 0.50g
- **Ödeme Süresi:** 10 gün

## 🎯 Risk Faktörleri (8 Parametre)

1. **Bina Yaşı:** 0-80 yıl arası
2. **Fay Mesafesi:** 0-500 km arası
3. **Zemin Büyütme:** 1.0-2.5x faktör
4. **Sıvılaşma Riski:** 0-0.8 olasılık
5. **Yapı Kalitesi:** 1-10 skor
6. **Kat Sayısı:** 1-40 kat
7. **Bina Alanı:** 30-2000 m²
8. **Kullanım Tipi:** Konut/Ticari/Karma

## 📊 Performans Metrikleri

- **API Yanıt Süresi:** <500ms (ortalaması)
- **Kandilli Çekimi:** ~2-3 saniye
- **Prim Hesaplama:** <100ms
- **Veri Üretimi:** 10K bina ~30 saniye
- **Bellek Kullanımı:** ~500MB (backend aktif)

## 🔧 Geliştirme

### Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/AmazingFeature`)
3. Commit edin (`git commit -m 'Add some AmazingFeature'`)
4. Push edin (`git push origin feature/AmazingFeature`)
5. Pull Request açın

### Debugging

```python
# app.py içinde debug mode aktif
if __name__ == '__main__':
    initialize_backend()
    print("\n🌐 FLASK SERVER BAŞLATILIYOR...")
    app.run(debug=True, host='0.0.0.0', port=5000)
```

### Logging

```python
# Kandilli API çağrıları
logger.info("✅ Kandilli'den 10 deprem alındı")
logger.warning("⚠️ Kandilli verisi alınamadı, CSV fallback")
logger.error("❌ Deprem API hatası: ConnectionError")
```

## 📝 Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Detaylar için [LICENSE](LICENSE) dosyasına bakın.

## 👥 İletişim

**Proje Sahibi:** Neovasyon Team  
**Email:** info@daskplus.com.tr  
**Website:** https://daskplus.com.tr

## 🙏 Teşekkürler

- **Kandilli Rasathanesi:** Gerçek zamanlı deprem verisi
- **AFAD:** Deprem veritabanı
- **TÜİK:** Bina istatistikleri
- **Açık Kaynak Topluluk:** Kullanılan tüm kütüphaneler

---

**⚠️ Önemli Not:** Bu sistem eğitim ve araştırma amaçlıdır. Gerçek sigorta uygulamaları için lütfen lisanslı sigorta şirketleriyle çalışın.

---

Made with ❤️ by Neovasyon Team | © 2025 DASK+ Parametrik
