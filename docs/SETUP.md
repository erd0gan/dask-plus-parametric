# 🚀 Kurulum Rehberi - DASK+ Parametrik

## İçindekiler
- [Sistem Gereksinimleri](#sistem-gereksinimleri)
- [Hızlı Kurulum](#hızlı-kurulum)
- [Detaylı Kurulum](#detaylı-kurulum)
- [Sorun Giderme](#sorun-giderme)
- [Docker Kurulumu](#docker-kurulumu)

## Sistem Gereksinimleri

### Minimum Gereksinimler
- **OS:** Windows 10/11, macOS 10.14+, Ubuntu 18.04+
- **Python:** 3.8 veya üzeri
- **RAM:** 4GB
- **Disk:** 500MB boş alan
- **İnternet:** Kandilli API erişimi için

### Önerilen
- **Python:** 3.10+
- **RAM:** 8GB+
- **CPU:** 4 çekirdek
- **SSD:** Daha hızlı veri işleme için

## Hızlı Kurulum

### Windows (PowerShell)

```powershell
# 1. Repository klonlama
git clone https://github.com/[kullanici-adi]/dask-plus-parametrik.git
cd dask-plus-parametrik

# 2. Virtual environment
python -m venv venv
.\venv\Scripts\activate

# 3. Bağımlılıklar
pip install -r requirements.txt

# 4. Çalıştırma
python app.py
```

### Linux/macOS (Bash)

```bash
# 1. Repository klonlama
git clone https://github.com/[kullanici-adi]/dask-plus-parametrik.git
cd dask-plus-parametrik

# 2. Virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Bağımlılıklar
pip install -r requirements.txt

# 4. Çalıştırma
python app.py
```

## Detaylı Kurulum

### 1. Python Kurulumu

#### Windows
1. [Python.org](https://www.python.org/downloads/) adresinden Python 3.10+ indirin
2. Kurulumda "Add Python to PATH" seçeneğini işaretleyin
3. Komut satırında doğrulayın:
   ```powershell
   python --version
   ```

#### macOS
```bash
# Homebrew ile
brew install python@3.10
```

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install python3.10 python3-pip python3-venv
```

### 2. Git Kurulumu

#### Windows
[Git for Windows](https://git-scm.com/download/win) indirin ve kurun

#### macOS
```bash
brew install git
```

#### Ubuntu/Debian
```bash
sudo apt install git
```

### 3. Repository Klonlama

```bash
# HTTPS ile
git clone https://github.com/[kullanici-adi]/dask-plus-parametrik.git

# veya SSH ile
git clone git@github.com:[kullanici-adi]/dask-plus-parametrik.git

cd dask-plus-parametrik
```

### 4. Virtual Environment Oluşturma

Virtual environment kullanmanız önemle tavsiye edilir:

```bash
# Oluşturma
python -m venv venv

# Aktivasyon - Windows
.\venv\Scripts\activate

# Aktivasyon - Linux/macOS
source venv/bin/activate

# Başarılı aktivasyonda komut satırında (venv) görünür
```

### 5. Bağımlılıkları Yükleme

```bash
# requirements.txt ile
pip install -r requirements.txt

# Veya tek tek
pip install flask flask-cors pandas numpy scikit-learn scipy geopy pyproj matplotlib seaborn folium tqdm python-dateutil requests openpyxl
```

### 6. Environment Variables (Opsiyonel)

```bash
# .env.example dosyasını kopyalayın
cp .env.example .env

# .env dosyasını düzenleyin (opsiyonel)
# Not: Varsayılan ayarlar çalışır durumda
```

### 7. İlk Çalıştırma

```bash
python app.py
```

İlk çalıştırmada sistem otomatik olarak:
1. `data/` klasörünü oluşturur
2. 10,000 gerçekçi bina verisi üretir (~30 saniye)
3. Tüm servisleri başlatır

Konsol çıktısı:
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

🌐 FLASK SERVER BAŞLATILIYOR...
 * Running on http://0.0.0.0:5000
```

### 8. Tarayıcıda Açma

- **Ana Sayfa:** http://localhost:5000
- **Admin Panel:** http://localhost:5000/admin

## Sorun Giderme

### Python bulunamadı

**Hata:** `'python' is not recognized...`

**Çözüm:**
```powershell
# Windows - Python yolunu PATH'e ekleyin
# veya python yerine py kullanın
py --version
```

### Port zaten kullanımda

**Hata:** `Address already in use: 5000`

**Çözüm:**
```bash
# Port'u değiştirin (app.py son satırı)
app.run(debug=True, host='0.0.0.0', port=5001)
```

### Kandilli bağlantı hatası

**Hata:** `Kandilli API hatası: ConnectionError`

**Çözüm:**
- İnternet bağlantınızı kontrol edin
- Sistem otomatik olarak CSV fallback'e geçer
- Manuel test: http://localhost:5000/api/earthquakes/debug

### Bağımlılık yükleme hatası

**Hata:** `error: Microsoft Visual C++ 14.0 is required`

**Çözüm:**
```bash
# Windows - C++ Build Tools yükleyin
# https://visualstudio.microsoft.com/visual-cpp-build-tools/

# macOS
xcode-select --install

# Linux
sudo apt install build-essential python3-dev
```

### Import hatası

**Hata:** `ModuleNotFoundError: No module named 'flask'`

**Çözüm:**
```bash
# Virtual environment aktif mi kontrol edin
# Komut satırında (venv) görünmeli

# Bağımlılıkları yeniden yükleyin
pip install --force-reinstall -r requirements.txt
```

### CSV dosyası bulunamadı

**Hata:** `FileNotFoundError: data/buildings.csv`

**Çözüm:**
```bash
# Veri dosyalarını manuel oluşturun
python data_generator.py
```

## Docker Kurulumu (Gelişmiş)

### Dockerfile (Projeye eklenecek)

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python data_generator.py

EXPOSE 5000

CMD ["python", "app.py"]
```

### Docker ile çalıştırma

```bash
# Image oluşturma
docker build -t dask-plus .

# Container çalıştırma
docker run -p 5000:5000 dask-plus
```

### Docker Compose (Gelişmiş)

```yaml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
    environment:
      - FLASK_ENV=production
```

## Production Deployment

### Gunicorn ile (Linux)

```bash
# Gunicorn yükleme
pip install gunicorn

# Çalıştırma
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Nginx ile (Reverse Proxy)

```nginx
server {
    listen 80;
    server_name daskplus.com.tr;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Test

```bash
# API testleri
python test_backend.py

# Manuel test endpoint'leri
curl http://localhost:5000/api/health
curl http://localhost:5000/api/earthquakes?min_magnitude=2.0&limit=5
```

## Yardım ve Destek

- **Issues:** [GitHub Issues](https://github.com/[kullanici-adi]/dask-plus-parametrik/issues)
- **Email:** info@daskplus.com.tr
- **Dokümantasyon:** [README.md](README.md)

---

**Son Güncelleme:** Ekim 2025  
**Versiyon:** 2.0
