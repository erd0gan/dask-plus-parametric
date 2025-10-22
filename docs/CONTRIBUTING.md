# 🤝 Katkıda Bulunma Rehberi - DASK+ Parametrik

## İçindekiler
- [Davranış Kuralları](#davranış-kuralları)
- [Nasıl Katkıda Bulunurum?](#nasıl-katkıda-bulunurum)
- [Geliştirme Ortamı](#geliştirme-ortamı)
- [Code Style](#code-style)
- [Commit Mesajları](#commit-mesajları)
- [Pull Request Süreci](#pull-request-süreci)
- [Test Yazma](#test-yazma)

## Davranış Kuralları

### Topluluk Değerlerimiz

- ✅ Saygılı ve yapıcı iletişim
- ✅ Farklı bakış açılarına açık olma
- ✅ Yapıcı eleştiri ve geri bildirim
- ✅ Topluluk odaklı düşünme
- ❌ Hakaret, ayrımcılık, taciz

### İletişim Kanalları

- **GitHub Issues:** Hata raporları ve özellik istekleri
- **Pull Requests:** Kod katkıları
- **Email:** info@daskplus.com.tr

## Nasıl Katkıda Bulunurum?

### 1. Hata Bildirme (Bug Report)

Bir hata bulduysanız:

1. **Issue açmadan önce kontrol edin:**
   - Benzer bir issue var mı?
   - Güncel versiyonu mu kullanıyorsunuz?
   - Dokümantasyonu okudunuz mu?

2. **Issue şablonu:**
   ```markdown
   ## Hata Açıklaması
   Kısa ve net hata açıklaması

   ## Tekrar Oluşturma Adımları
   1. '...' sayfasına gidin
   2. '...' butonuna tıklayın
   3. Aşağı kaydırın
   4. Hata görünüyor

   ## Beklenen Davranış
   Ne olmasını bekliyordunuz?

   ## Ekran Görüntüleri
   Varsa ekran görüntüsü ekleyin

   ## Ortam Bilgileri
   - OS: [örn. Windows 11]
   - Python: [örn. 3.10.5]
   - Browser: [örn. Chrome 120]
   ```

### 2. Özellik İsteği (Feature Request)

Yeni bir özellik mi istiyorsunuz?

1. **Issue açın:**
   ```markdown
   ## Özellik Açıklaması
   Hangi özelliği istiyorsunuz?

   ## Problem
   Bu özellik hangi problemi çözüyor?

   ## Önerilen Çözüm
   Nasıl çalışmalı?

   ## Alternatifler
   Başka çözümler düşündünüz mü?
   ```

### 3. Kod Katkısı

#### Başlamadan Önce

1. Issue açın veya mevcut bir issue'ya yorum yapın
2. Maintainer'lardan onay bekleyin
3. Fork ve branch oluşturun

#### Fork ve Clone

```bash
# 1. GitHub'da Fork edin (sağ üst köşe)

# 2. Fork'u klonlayın
git clone https://github.com/[sizin-kullanici-adiniz]/dask-plus-parametrik.git
cd dask-plus-parametrik

# 3. Upstream ekleyin
git remote add upstream https://github.com/[orijinal-kullanici]/dask-plus-parametrik.git

# 4. Upstream'i çekin
git fetch upstream
```

## Geliştirme Ortamı

### Kurulum

```bash
# Virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# .\venv\Scripts\activate  # Windows

# Bağımlılıklar
pip install -r requirements.txt

# Development bağımlılıkları
pip install pytest black flake8 mypy
```

### Branch Stratejisi

```bash
# Yeni feature için
git checkout -b feature/amazing-feature

# Bug fix için
git checkout -b fix/bug-description

# Dokümantasyon için
git checkout -b docs/update-readme
```

Branch isimlendirme:
- `feature/` - Yeni özellikler
- `fix/` - Hata düzeltmeleri
- `docs/` - Dokümantasyon
- `refactor/` - Kod iyileştirme
- `test/` - Test eklemeleri

## Code Style

### Python (PEP 8)

```python
# ✅ İyi
def calculate_premium(building_age: int, distance: float) -> float:
    """
    Prim hesaplama fonksiyonu.
    
    Args:
        building_age: Bina yaşı (yıl)
        distance: Fay mesafesi (km)
    
    Returns:
        Hesaplanan prim (TL)
    """
    risk_score = building_age * 0.01 + distance * 0.02
    return risk_score * 1000

# ❌ Kötü
def calc(a,b):
    return a*0.01+b*0.02*1000
```

### Docstring Formatı

```python
def function_name(param1: type1, param2: type2) -> return_type:
    """
    Kısa bir satırda fonksiyon açıklaması.
    
    Daha detaylı açıklama buraya. Birden fazla satır
    olabilir.
    
    Args:
        param1: İlk parametre açıklaması
        param2: İkinci parametre açıklaması
    
    Returns:
        Dönüş değeri açıklaması
    
    Raises:
        ValueError: Hata durumu açıklaması
    
    Example:
        >>> function_name(10, 20)
        30
    """
    pass
```

### JavaScript (Frontend)

```javascript
// ✅ İyi
async function fetchEarthquakes(minMagnitude = 2.0, limit = 10) {
    try {
        const response = await fetch(
            `/api/earthquakes?min_magnitude=${minMagnitude}&limit=${limit}`
        );
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Deprem verisi çekilemedi:', error);
        throw error;
    }
}

// ❌ Kötü
function f(a,b){
    return fetch('/api/earthquakes?min_magnitude='+a+'&limit='+b).then(r=>r.json())
}
```

### Formatting

```bash
# Black ile otomatik formatlama
black app.py data_generator.py main.py pricing_only.py

# Flake8 ile linting
flake8 app.py --max-line-length=100

# MyPy ile type checking
mypy app.py
```

## Commit Mesajları

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type
- `feat:` Yeni özellik
- `fix:` Hata düzeltmesi
- `docs:` Dokümantasyon
- `style:` Kod formatı (logic değişikliği yok)
- `refactor:` Kod iyileştirme
- `test:` Test eklemesi
- `chore:` Build/config değişiklikleri

### Örnekler

```bash
# ✅ İyi
feat(pricing): add dynamic risk factor calculation

Added 8-parameter risk model for premium calculation.
Includes building age, fault distance, soil amplification.

Closes #42

# ✅ İyi
fix(kandilli): handle Turkish encoding errors

Fixed character encoding issues when parsing Kandilli data.
Added automatic fallback to ISO-8859-9.

# ✅ İyi
docs(readme): update installation instructions

Added Docker setup and troubleshooting section.

# ❌ Kötü
fixed bug
update code
changes
```

## Pull Request Süreci

### 1. Hazırlık

```bash
# Upstream'den son değişiklikleri çekin
git fetch upstream
git rebase upstream/main

# Testleri çalıştırın
python test_backend.py
pytest tests/

# Linting
black .
flake8 .
```

### 2. Pull Request Oluşturma

1. GitHub'da "New Pull Request" tıklayın
2. Şablonu doldurun:

```markdown
## Değişiklik Özeti
Ne değişti?

## Değişiklik Tipi
- [ ] Bug fix (breaking değil)
- [ ] Yeni feature (breaking değil)
- [ ] Breaking change
- [ ] Dokümantasyon

## Test Edildi Mi?
- [ ] Testler başarılı
- [ ] Yeni testler eklendi
- [ ] Manuel olarak test edildi

## Checklist
- [ ] Kod PEP 8'e uygun
- [ ] Docstring'ler eklendi
- [ ] README güncellendi (gerekirse)
- [ ] CHANGELOG.md güncellendi

## Ekran Görüntüleri (UI değişikliği varsa)
Ekran görüntüsü ekleyin

## İlgili Issue
Closes #123
```

### 3. Review Süreci

- Maintainer'lar kodu inceleyecek
- Değişiklik isteyebilir
- Onaylandıktan sonra merge edilir

### 4. Değişiklik Yapma

```bash
# Aynı branch'te değişiklik yapın
git add .
git commit -m "fix: address review comments"
git push origin feature/amazing-feature
```

## Test Yazma

### Test Klasörü Yapısı

```
tests/
├── test_pricing.py
├── test_trigger.py
├── test_api.py
└── test_data_generator.py
```

### Test Örneği

```python
import pytest
from app import app

@pytest.fixture
def client():
    """Test client fixture"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_health_endpoint(client):
    """Test health check endpoint"""
    response = client.get('/api/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True

def test_premium_calculation(client):
    """Test premium calculation API"""
    payload = {
        'il': 'İstanbul',
        'ilce': 'Kadıköy',
        'mahalle': 'Fenerbahçe',
        'package': 'temel'
    }
    response = client.post('/api/calculate-premium', json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert 'annual_premium' in data
    assert data['annual_premium'] > 0
```

### Test Çalıştırma

```bash
# Tüm testler
pytest

# Belirli bir dosya
pytest tests/test_api.py

# Coverage ile
pytest --cov=. --cov-report=html
```

## Dokümantasyon

### README Güncellemeleri

Yeni özellik eklerseniz README.md'yi güncelleyin:
- API endpoint'leri
- Kullanım örnekleri
- Konfigürasyon seçenekleri

### Kod Yorumları

```python
# ✅ İyi - Neden yapıldığını açıkla
# Kandilli encoding hatası nedeniyle fallback
if response.status_code != 200:
    return self.get_csv_fallback()

# ❌ Kötü - Ne yapıldığını açıklama
# Return CSV
return self.get_csv_fallback()
```

## İletişim

Sorularınız için:
- **GitHub Discussions:** Genel sorular
- **GitHub Issues:** Spesifik problemler
- **Email:** info@daskplus.com.tr

---

**Katkılarınız için teşekkürler! 🙏**

Made with ❤️ by Neovasyon Team
