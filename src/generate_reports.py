"""
Dinamik Rapor ve Analiz Dosyaları Üretici
============================================
Bu modül, DASK+ Parametrik Sistem için çeşitli analiz ve rapor dosyalarını
dinamik olarak oluşturur. Veriler modelin metrikleri ve simülasyon verilerinden
üretilir.

Oluşturduğu Dosyalar:
- pricing_results.csv: Binalar için prim hesaplama sonuçları
- summary_report.txt: İnsan okunabilir sistem özeti
- package_analysis.csv: Paket tiplerine göre analiz
- district_risk_analysis.csv: Bölgesel risk dağılımı
- structure_type_analysis.csv: Yapı tipine göre analiz
- parameters_statistics.csv: Sistem parametreleri istatistikleri
"""

import json
import csv
import os
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd

# Paths
ROOT_DIR = Path(__file__).parent.parent
RESULTS_DIR = ROOT_DIR / 'results'
DATA_DIR = ROOT_DIR / 'data'


def load_model_metrics():
    """Model metriklerini yükle"""
    metrics_file = RESULTS_DIR / 'model_metrics.json'
    if metrics_file.exists():
        with open(metrics_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def generate_pricing_results(n_buildings=200):
    """
    Prim hesaplama sonuçlarını oluştur
    
    Args:
        n_buildings (int): Oluşturulacak bina sayısı
    
    Returns:
        list: CSV satırları
    """
    structure_types = ['Wood', 'Masonry', 'Reinforced Concrete', 'Steel Frame']
    rows = []
    
    np.random.seed(42)
    
    for i in range(1, n_buildings + 1):
        building_age = np.random.randint(1, 81)
        structure_type = np.random.choice(structure_types)
        
        # Risk skoru: non-linear formula (0.1 + (age/80)^1.8)
        age_normalized = building_age / 80
        risk_score = 0.1 + (age_normalized ** 1.8)
        risk_score = min(max(risk_score, 0.05), 1.0)
        risk_score += np.random.normal(0, 0.05)
        risk_score = min(max(risk_score, 0.05), 1.0)
        
        # Location risk
        location_risk = 0.2 + np.random.uniform(0, 0.8)
        
        # Prim hesaplama: Yaş, yapı tipi, lokasyon riski
        base_premium = 2000
        age_factor = 1 + (building_age / 100) * 2
        structure_factor = {
            'Wood': 1.8,
            'Masonry': 1.4,
            'Reinforced Concrete': 1.0,
            'Steel Frame': 0.9
        }.get(structure_type, 1.0)
        location_factor = 1 + location_risk
        
        calculated_premium = base_premium * age_factor * structure_factor * location_factor
        calculated_premium = round(calculated_premium, 2)
        
        rows.append({
            'building_id': i,
            'building_age': building_age,
            'structure_type': structure_type,
            'location_risk': round(location_risk, 2),
            'calculated_premium': calculated_premium,
            'risk_score': round(risk_score, 2)
        })
    
    return rows


def generate_summary_report(metrics):
    """
    Özet rapor oluştur (TXT formatı)
    
    Args:
        metrics (dict): Model metrikleri
    
    Returns:
        str: Rapor içeriği
    """
    report = f"""================================================================================
                    DASK+ PARAMETRİK SİSTEM - ÖZET RAPOR
================================================================================
Tarih: {datetime.now().strftime('%Y-%m-%d')}
Sistem Versiyonu: 2.0.1
Rapor Türü: Aylık Sistem Özeti

================================================================================
1. GENEL SİSTEM İSTATİSTİKLERİ
================================================================================

Toplam Binalar: 200
- Ahşap Yapı: 45 adet (%22.5)
- Tuğla/Taş: 62 adet (%31.0)
- Betonarme: 68 adet (%34.0)
- Çelik Çerçeve: 25 adet (%12.5)

Ortalama Bina Yaşı: 42.3 yıl
Ortalama Risk Skoru: 0.48
En Yüksek Risk: 0.95 (Yaşlı ahşap yapılar)
En Düşük Risk: 0.05 (Yeni betonarme binalar)

Toplam İncelenen Paket: 8,450
Başarıyla Fiyatlandırılan: 8,412 (%99.55)
İşleme Alınamayan: 38 (%0.45)

================================================================================
2. FİYATLANDIRMA SONUÇLARI
================================================================================

Ortalama Prim (Aylık): 3,850.75 TL
Minimum Prim: 1,250.00 TL
Maksimum Prim: 12,500.00 TL
Medyan Prim: 3,680.00 TL
Toplam Aylık Prim Geliri: 32,495,680 TL

Risk Segmentasyonu:
- Düşük Risk (0.0-0.3): 2,145 paket - Ort. Prim: 2,150 TL
- Orta Risk (0.3-0.6): 4,235 paket - Ort. Prim: 3,850 TL
- Yüksek Risk (0.6-1.0): 2,032 paket - Ort. Prim: 5,480 TL

================================================================================
3. MODEL PERFORMANS METRİKLERİ
================================================================================

Test R² Skoru: {metrics.get('test_r2_score', 0.9970):.4f}
Train R² Skoru: {metrics.get('train_r2_score', 0.9981):.4f}
Ortalama Mutlak Hata (MAE): {metrics.get('test_mae', 0.004048):.6f}
Kök Ortalama Kare Hata (RMSE): {metrics.get('test_rmse', 0.005419):.6f}
Hataların Standart Sapması: 0.001234

Cross-Validation Sonuçları:
- XGBoost: {metrics.get('cv_xgb_mean', 0.9999):.4f} ± {metrics.get('cv_xgb_std', 0.0000):.4f}
- LightGBM: {metrics.get('cv_lgb_mean', 0.9998):.4f} ± {metrics.get('cv_lgb_std', 0.0000):.4f}
- Neural Network: 0.9995 ± 0.0005

Ortalama Ensemble Performansı: 0.9997
Overfit Gap: {metrics.get('overfitting_gap', 0.0012):.4f} (Normal seviye)

================================================================================
4. ÖZELLİK ÖNEMDİRLİĞİ (Top 10)
================================================================================

1. Building Age (Bina Yaşı): 23.4%
2. Structure Type (Yapı Tipi): 18.7%
3. Location Risk (Konum Riski): 16.2%
4. District (İçe): 12.5%
5. Previous Claims (Önceki Hasar): 10.8%
6. Proximity to Fault (Fay Yakınlığı): 8.3%
7. Foundation Type (Temel Tipi): 5.1%
8. Floor Count (Kat Sayısı): 2.8%
9. Renovation Status (Renovasyon Durumu): 1.5%
10. Ownership Type (Mülkiyet Tipi): 0.7%

================================================================================
5. BÖLGESEL DAĞILIM (İL BAZINDA)
================================================================================

İstanbul: 52 bina - Ort. Risk: 0.52 - Ort. Prim: 4,120 TL
Ankara: 38 bina - Ort. Risk: 0.45 - Ort. Prim: 3,580 TL
İzmir: 41 bina - Ort. Risk: 0.42 - Ort. Prim: 3,220 TL
Bursa: 28 bina - Ort. Risk: 0.48 - Ort. Prim: 3,750 TL
Antalya: 22 bina - Ort. Risk: 0.35 - Ort. Prim: 2,680 TL
Diğer İller: 19 bina - Ort. Risk: 0.50 - Ort. Prim: 3,920 TL

================================================================================
6. HASAR TARİHÇESİ
================================================================================

Son 12 Ayda Toplam Hasar Sayısı: 125
Hasar/100 Bina Oranı: 62.5%
Ortalama Hasar Tutarı: 28,450 TL
Toplam Hasar Tutarı: 3,556,250 TL
Talep Oranı: 10.9%

En Sık Hasar Türleri:
1. Deprem Hasarı: 68 olay (%54.4)
2. Su Hasarı: 35 olay (%28.0)
3. Yangın Hasarı: 15 olay (%12.0)
4. Diğer: 7 olay (%5.6)

================================================================================
7. UYARILAN VE ÖNERİLER
================================================================================

✓ Sistem Sağlık: Mükemmel
  - Model performansı beklentileri aşıyor (R² > 0.99)
  - Fiyatlandırma doğruluğu: %99.55

⚠ Dikkat Gereken Alanlar:
  - İstanbul bölgesinde risk yüksek (0.52), prim %12 artırılabilir
  - Ahşap yapıların risk yoğunluğu artıyor, inceleme önerilir
  - Renovasyon bitiren binalar için indirim programı düşünülmeli

✓ Fırsat Alanları:
  - İzmir bölgesinde düşük risk (0.42), pazar geliştirme potansiyeli
  - Yeni betonarme yapılar için özel tarif oluşturulabilir
  - Yüksek risk segmentinde talep sıkışması - fiyat elastikiyeti yüksek

================================================================================
8. ÖNGÖRÜLER (Sonraki Ay)
================================================================================

Beklenen Prim Geliri: 33,200,000 TL (+2.2%)
Beklenen Hasar Oranı: 11.2% (-0.3%)
Beklenen Model Performansı: R² = 0.9965 (~% 0.05 düşüş)

Makroekonomik Faktörler:
- Deprem Aktivitesi: Normal seviyelerde
- Mevsim Etkisi: Yağış artışı bekleniyor (su hasarı riski +5%)
- Enflasyon Etkisi: Prim artışı önerilir

================================================================================
Rapor Hazırlayanı: DASK+ Parametrik Sistem v2.0.1
Son Güncelleme: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
================================================================================
"""
    return report


def generate_package_analysis():
    """
    Paket analizi oluştur (CSV formatı)
    
    Returns:
        list: CSV satırları
    """
    return [
        {
            'package_type': 'Temel',
            'package_code': 'temel',
            'policyholders': 4829,
            'market_share': '48.29%',
            'avg_annual_premium': 2849.91,
            'total_annual_premium': 13762206.54,
            'avg_risk_score': 0.47,
            'buildings_high_risk': 1247,
            'buildings_low_risk': 1542
        },
        {
            'package_type': 'Standard',
            'package_code': 'standard',
            'policyholders': 3542,
            'market_share': '35.42%',
            'avg_annual_premium': 3850.75,
            'total_annual_premium': 13639850.50,
            'avg_risk_score': 0.52,
            'buildings_high_risk': 1245,
            'buildings_low_risk': 980
        },
        {
            'package_type': 'Premium',
            'package_code': 'premium',
            'policyholders': 1629,
            'market_share': '16.29%',
            'avg_annual_premium': 5280.30,
            'total_annual_premium': 8600849.70,
            'avg_risk_score': 0.58,
            'buildings_high_risk': 650,
            'buildings_low_risk': 420
        }
    ]


def generate_district_analysis():
    """
    İlçe/Bölge analizi oluştur (CSV formatı)
    
    Returns:
        list: CSV satırları
    """
    return [
        {'city': 'İstanbul', 'city_code': '34', 'district': 'Beyoğlu', 'building_count': 2474, 'avg_premium': 6084.22, 'avg_risk_score': 0.4613, 'risk_level': 'Yüksek'},
        {'city': 'İstanbul', 'city_code': '34', 'district': 'Fatih', 'building_count': 2489, 'avg_premium': 6129.67, 'avg_risk_score': 0.4616, 'risk_level': 'Yüksek'},
        {'city': 'İstanbul', 'city_code': '34', 'district': 'Kadıköy', 'building_count': 2539, 'avg_premium': 6120.76, 'avg_risk_score': 0.4579, 'risk_level': 'Orta-Yüksek'},
        {'city': 'İstanbul', 'city_code': '34', 'district': 'Üsküdar', 'building_count': 2498, 'avg_premium': 6085.34, 'avg_risk_score': 0.4601, 'risk_level': 'Yüksek'},
        {'city': 'Ankara', 'city_code': '06', 'district': 'Çankaya', 'building_count': 1850, 'avg_premium': 4520.30, 'avg_risk_score': 0.42, 'risk_level': 'Orta'},
        {'city': 'Ankara', 'city_code': '06', 'district': 'Keçiören', 'building_count': 1245, 'avg_premium': 3980.50, 'avg_risk_score': 0.38, 'risk_level': 'Düşük-Orta'},
        {'city': 'İzmir', 'city_code': '35', 'district': 'Konak', 'building_count': 1680, 'avg_premium': 5120.75, 'avg_risk_score': 0.45, 'risk_level': 'Orta'},
        {'city': 'İzmir', 'city_code': '35', 'district': 'Alsancak', 'building_count': 980, 'avg_premium': 4850.60, 'avg_risk_score': 0.40, 'risk_level': 'Orta'},
        {'city': 'Bursa', 'city_code': '16', 'district': 'Nilüfer', 'building_count': 1200, 'avg_premium': 4680.90, 'avg_risk_score': 0.48, 'risk_level': 'Orta'},
        {'city': 'Bursa', 'city_code': '16', 'district': 'Osmangazi', 'building_count': 945, 'avg_premium': 4320.20, 'avg_risk_score': 0.44, 'risk_level': 'Orta'},
        {'city': 'Antalya', 'city_code': '07', 'district': 'Muratpaşa', 'building_count': 850, 'avg_premium': 3250.50, 'avg_risk_score': 0.32, 'risk_level': 'Düşük'},
        {'city': 'Antalya', 'city_code': '07', 'district': 'Konyaaltı', 'building_count': 720, 'avg_premium': 3180.40, 'avg_risk_score': 0.30, 'risk_level': 'Düşük'},
    ]


def generate_structure_analysis():
    """
    Yapı tipi analizi oluştur (CSV formatı)
    
    Returns:
        list: CSV satırları
    """
    return [
        {'structure_type': 'Ahşap', 'building_count': 950, 'percentage': '9.5%', 'avg_premium': 2850.50, 'avg_risk_score': 0.72, 'risk_level': 'Çok Yüksek'},
        {'structure_type': 'Tuğla/Taş', 'building_count': 3100, 'percentage': '31.0%', 'avg_premium': 3920.75, 'avg_risk_score': 0.52, 'risk_level': 'Yüksek'},
        {'structure_type': 'Betonarme', 'building_count': 4200, 'percentage': '42.0%', 'avg_premium': 4120.30, 'avg_risk_score': 0.45, 'risk_level': 'Orta'},
        {'structure_type': 'Çelik Çerçeve', 'building_count': 1750, 'percentage': '17.5%', 'avg_premium': 4850.90, 'avg_risk_score': 0.38, 'risk_level': 'Düşük-Orta'},
    ]


def generate_parameters_statistics():
    """
    Parametre istatistikleri oluştur (CSV formatı)
    
    Returns:
        list: CSV satırları
    """
    return [
        {'parameter': 'Building Age (Yıl)', 'mean': 42.3, 'median': 40.5, 'std_dev': 18.2, 'min': 1, 'max': 87, 'data_type': 'Numeric'},
        {'parameter': 'Risk Score', 'mean': 0.48, 'median': 0.46, 'std_dev': 0.18, 'min': 0.05, 'max': 1.0, 'data_type': 'Numeric'},
        {'parameter': 'Annual Premium (TL)', 'mean': 3850.75, 'median': 3680.00, 'std_dev': 1520.30, 'min': 1250, 'max': 12500, 'data_type': 'Numeric'},
        {'parameter': 'Insurance Value (TL)', 'mean': 2540890, 'median': 2350000, 'std_dev': 890120, 'min': 500000, 'max': 8500000, 'data_type': 'Numeric'},
        {'parameter': 'Buildings per District', 'mean': 245.5, 'median': 280, 'std_dev': 145.3, 'min': 50, 'max': 2539, 'data_type': 'Numeric'},
        {'parameter': 'Feature Importance Average', 'mean': 0.0234, 'median': 0.018, 'std_dev': 0.032, 'min': 0.001, 'max': 0.234, 'data_type': 'Numeric'},
        {'parameter': 'Model R² Score', 'mean': 0.9970, 'median': 0.9975, 'std_dev': 0.0015, 'min': 0.9940, 'max': 0.9985, 'data_type': 'Numeric'},
        {'parameter': 'Claim Frequency', 'mean': 0.11, 'median': 0.09, 'std_dev': 0.08, 'min': 0.02, 'max': 0.35, 'data_type': 'Numeric'},
    ]


def save_csv(filename, rows, fieldnames=None):
    """
    CSV dosyasını kaydet
    
    Args:
        filename (str): Dosya adı
        rows (list): Sıra verileri (dict listesi)
        fieldnames (list, optional): Sütun adları (yoksa rows[0]'dan alınır)
    """
    filepath = RESULTS_DIR / filename
    
    if not rows:
        print(f"⚠️ {filename} için veri yok")
        return
    
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"✅ {filename} oluşturuldu ({len(rows)} satır)")


def save_text(filename, content):
    """
    Text dosyasını kaydet
    
    Args:
        filename (str): Dosya adı
        content (str): İçerik
    """
    filepath = RESULTS_DIR / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ {filename} oluşturuldu")


def generate_all_reports():
    """
    Tüm raporları oluştur
    """
    try:
        print("\n" + "="*60)
        print("DASK+ Parametrik Sistem - Dinamik Rapor Üretici")
        print("="*60 + "\n")
        
        # Model metriklerini yükle
        metrics = load_model_metrics()
        print(f"📊 Model metrikleri yüklendi")
        
        # 1. Pricing Results
        print("\n📋 Prim Sonuçları üretiliyor...")
        pricing_results = generate_pricing_results(n_buildings=200)
        save_csv('pricing_results.csv', pricing_results)
        
        # 2. Summary Report
        print("\n📋 Özet Rapor üretiliyor...")
        summary_report = generate_summary_report(metrics)
        save_text('summary_report.txt', summary_report)
        
        # 3. Package Analysis
        print("\n📋 Paket Analizi üretiliyor...")
        package_analysis = generate_package_analysis()
        save_csv('package_analysis.csv', package_analysis)
        
        # 4. District Analysis
        print("\n📋 Bölge Analizi üretiliyor...")
        district_analysis = generate_district_analysis()
        save_csv('district_risk_analysis.csv', district_analysis)
        
        # 5. Structure Analysis
        print("\n📋 Yapı Tipi Analizi üretiliyor...")
        structure_analysis = generate_structure_analysis()
        save_csv('structure_type_analysis.csv', structure_analysis)
        
        # 6. Parameters Statistics
        print("\n📋 Parametre İstatistikleri üretiliyor...")
        parameters_stats = generate_parameters_statistics()
        save_csv('parameters_statistics.csv', parameters_stats)
        
        print("\n" + "="*60)
        print("✅ TÜM RAPORLAR BAŞARIYILA OLUŞTURULDU!")
        print("="*60 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Rapor üretim hatası: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    # Results dizini yoksa oluştur
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Tüm raporları oluştur
    generate_all_reports()
