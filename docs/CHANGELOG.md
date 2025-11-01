# Changelog

Tüm önemli değişiklikler bu dosyada belgelenecektir.

Format [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) standardına,
ve versiyonlama [Semantic Versioning](https://semver.org/spec/v2.0.0.html) standardına dayanır.

## [2.0.0] - 2025-10-20

### 🎉 İlk Stabil Sürüm

#### Added
- ✅ Tam entegre Flask backend API (`app.py`)
- ✅ Kandilli Rasathanesi gerçek zamanlı deprem entegrasyonu
- ✅ AI destekli dinamik fiyatlandırma sistemi (`pricing_only.py`)
- ✅ Parametrik tetikleme motoru (`main.py`)
- ✅ Gerçekçi veri üretici (`data_generator.py`)
- ✅ Modern responsive web arayüzü (`index.html`, `admin.html`)
- ✅ Admin dashboard - istatistikler, grafikler, monitoring
- ✅ 3 paket yapısı (Temel/Standard/Premium)
- ✅ 8 risk faktörü ile hassas fiyatlandırma
- ✅ PGA/PGV bazlı otomatik tetikleme
- ✅ Mahalle düzeyinde risk analizi
- ✅ Gerçek zamanlı deprem feed
- ✅ CSV fallback mekanizması
- ✅ Comprehensive logging sistemi
- ✅ API health check endpoint
- ✅ Debug endpoint'leri

#### Features

**Backend API:**
- `/api/earthquakes` - Gerçek zamanlı deprem verisi
- `/api/calculate-premium` - AI destekli prim hesaplama
- `/api/simulate-trigger` - Parametrik simülasyon
- `/api/dashboard/stats` - Dashboard istatistikleri
- `/api/policies` - Poliçe yönetimi
- `/api/pgv-monitor` - PGV monitoring
- `/api/health` - Sistem sağlık kontrolü
- `/api/earthquakes/debug` - Kandilli ham veri

**Pricing System:**
- Hiper-granüler risk modelleme
- 8 parametreli dinamik fiyatlandırma
- Mahalle bazında seismik risk haritası
- ML tabanlı prim optimizasyonu
- Fine-grained location validation

**Parametric Engine:**
- PGA/PGV eşik bazlı tetikleme
- Çoklu parametre optimizasyonu
- Basis risk minimizasyonu
- 10-14 gün ödeme garantisi
- Max-per-building aggregation

**Data Generation:**
- 10,000+ gerçekçi bina verisi
- İstanbul 2025 gerçek istatistikleri
- Otomatik data quality validation
- Duplicate prevention
- Range validation & consistency checks

**Frontend:**
- Modern, responsive UI
- Smooth scroll navigation
- Interactive pricing calculator
- Real-time earthquake feed
- Admin dashboard - charts & stats
- Mobile-friendly design

#### Technical

**Dependencies:**
- Flask 3.0.0 - Web framework
- Pandas 2.1.4 - Data processing
- Scikit-learn 1.3.2 - Machine learning
- Requests 2.31.0 - HTTP client
- Geopy 2.4.1 - Geospatial calculations
- Chart.js - Frontend visualization
- Folium 0.15.1 - Interactive maps

**Data Sources:**
- Kandilli Rasathanesi - Real-time earthquakes
- AFAD - Historical earthquake records
- TÜİK - Building statistics

**Performance:**
- API response time: <500ms avg
- Kandilli fetch: ~2-3s
- Premium calculation: <100ms
- Data generation: 10K buildings ~30s
- Memory footprint: ~500MB active

#### Documentation
- ✅ Comprehensive README.md
- ✅ Detailed SETUP.md
- ✅ CONTRIBUTING.md guidelines
- ✅ LICENSE (MIT)
- ✅ .env.example template
- ✅ UPDATE_REPORT.md
- ✅ Inline code documentation

#### Infrastructure
- ✅ .gitignore for Python projects
- ✅ requirements.txt with pinned versions
- ✅ data/ directory structure
- ✅ Logging configuration
- ✅ Error handling & fallbacks
- ✅ CORS support
- ✅ Environment variables support

### Known Issues
- Kandilli API bazen timeout olabiliyor (otomatik fallback mevcut)
- CSV encoding bazen manuel düzeltme gerektirebiliyor
- Large dataset'lerde (50K+ bina) yavaşlama olabilir

### Future Roadmap
- [ ] Docker containerization
- [ ] PostgreSQL database integration
- [ ] User authentication system
- [ ] Email notification service
- [ ] SMS alerts for triggers
- [ ] Mobile app (React Native)
- [ ] RESTful API v2
- [ ] GraphQL support
- [ ] Real-time WebSocket updates
- [ ] Advanced analytics dashboard
- [ ] Multi-language support
- [ ] PDF report generation
- [ ] Payment gateway integration
- [ ] Blockchain verification (optional)

## [1.0.0] - 2025-01-15

### Initial Development
- Backend prototipi
- Basic pricing algoritması
- Temel UI tasarımı

---

## Versiyon Formatı

Versiyonlar MAJOR.MINOR.PATCH formatındadır:
- **MAJOR:** Breaking changes
- **MINOR:** Yeni özellikler (backward compatible)
- **PATCH:** Bug fixes

## Kategori Tanımları

- **Added:** Yeni özellikler
- **Changed:** Mevcut fonksiyonlarda değişiklikler
- **Deprecated:** Yakında kaldırılacak özellikler
- **Removed:** Kaldırılan özellikler
- **Fixed:** Hata düzeltmeleri
- **Security:** Güvenlik iyileştirmeleri

---

[2.0.0]: https://github.com/erd0gan/dask-plus-parametrik/releases/tag/v2.0.0
[1.0.0]: https://github.com/erd0gan/dask-plus-parametrik/releases/tag/v1.0.0
