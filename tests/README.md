# DASK+ Test Dosyaları

Bu klasör, sistem testlerini içerir.

## Test Dosyaları

### 1. test_api.py
Flask API endpoint'lerini test eder.

**Kullanım:**
```bash
python tests/test_api.py
```

**Test Edilenler:**
- `/api/customer/<customer_id>`
- `/api/policy-details/<customer_id>`
- `/api/customer-policies/<customer_id>`
- `/api/dashboard/stats/<customer_id>`
- `/api/login`

### 2. test_blockchain.py
Blockchain entegrasyonunu test eder.

**Kullanım:**
```bash
python tests/test_blockchain.py
```

**Test Edilenler:**
- Blockchain Manager başlatma
- Poliçe kaydı
- Deprem kaydı
- İstatistik toplama

## Blockchain Toplu Senkronizasyon

Toplu blockchain senkronizasyonu için `blockchain_manager.py` modülünü kullanın:

```python
from src.blockchain_manager import BlockchainManager

# Blockchain manager başlat
blockchain = BlockchainManager(enable_blockchain=True, async_mode=True)

# Toplu kayıt (ilk 100 poliçe)
result = blockchain.bulk_record_policies(limit=100)

# Detaylı loglama ile (tüm poliçeler)
result = blockchain.bulk_sync_with_logging(batch_size=100)

# Kapatma
blockchain.shutdown()
```

**Çıktılar:**
- `data/blockchain_records.csv` - Kayıt listesi
- `data/blockchain_operations.log` - Detaylı log

## Gereksinimler

Tests çalıştırmadan önce:

1. Flask backend'in çalışıyor olması gerekir (API testleri için):
   ```bash
   python run.py
   ```

2. Gerekli paketler yüklü olmalı:
   ```bash
   pip install -r config/requirements.txt
   ```

## Notlar

- API testleri için backend'in aktif olması gerekir
- Blockchain testleri bağımsız çalışır
- Test verileri `data/` klasöründen okunur
- Blockchain senkronizasyon fonksiyonları `src/blockchain_manager.py` içinde bulunur
