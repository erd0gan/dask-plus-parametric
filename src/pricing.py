"""
DASK+ Parametrik Sigorta - Yapay Zeka Destekli Dinamik Fiyatlandırma Sistemi
==============================================================================
Bu sistem, yapay zeka ve makine öğrenmesi kullanarak:
1. Hiper-granüler risk modellemesi ve dinamik fiyatlandırma
2. Gerçek deprem verisi bazlı bölgesel risk analizi
3. Paket-tabanlı akıllı prim hesaplama (0.6x - 1.5x dinamik faktör)
sağlar.
"""

import numpy as np
import pandas as pd
import random
from datetime import datetime, timedelta
import warnings
import os
warnings.filterwarnings('ignore')
from multiprocessing import Pool, cpu_count
from functools import partial
from pathlib import Path

# Makine Öğrenmesi Kütüphaneleri
from sklearn.model_selection import train_test_split, cross_val_score, KFold
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
from sklearn.neural_network import MLPRegressor
import xgboost as xgb
import lightgbm as lgb

# Görselleştirme
import matplotlib.pyplot as plt
import seaborn as sns
import folium
from folium import plugins

# Progress bar
from tqdm import tqdm

# Coğrafi analiz
from geopy.distance import geodesic, great_circle

# Ek modüller (improvements içinden taşındı)
from dataclasses import dataclass
from typing import Dict, List, Tuple
from pyproj import Transformer, CRS
import math

# İYİLEŞTİRİLMİŞ MODÜLLER ARTIK DAHİLİ
IMPROVEMENTS_AVAILABLE = True

# =============================================================================
# İMPROVEMENTS SINIFLAR (fine_grained_pricing.py'den)
# =============================================================================

@dataclass
class RiskFactorConfig:
    """Risk faktör konfigürasyonu"""
    name: str
    min_multiplier: float
    max_multiplier: float
    neutral_value: float
    distribution: str
    weight: float


class FineGrainedPricingEngine:
    """İnce taneli (fine-grained) fiyatlandırma motoru - 8 Risk Faktörü"""
    
    def __init__(self):
        self.factors = {
            'seismicity': RiskFactorConfig('Seismicity', 0.7, 1.5, 0.5, 'exponential', 0.25),
            'building_age': RiskFactorConfig('Building Age', 0.8, 1.4, 15, 'linear', 0.15),
            'building_quality': RiskFactorConfig('Building Quality', 0.6, 1.3, 2, 'exponential', 0.20),
            'soil_type': RiskFactorConfig('Soil Type', 0.9, 1.2, 2, 'linear', 0.10),
            'elevation': RiskFactorConfig('Elevation', 0.95, 1.1, 100, 'sigmoid', 0.05),
            'population_density': RiskFactorConfig('Population Density', 0.85, 1.15, 5000, 'sigmoid', 0.08),
            'distance_to_fault': RiskFactorConfig('Distance to Fault', 0.8, 1.4, 50, 'exponential', 0.12),
            'historical_damage': RiskFactorConfig('Historical Damage', 0.9, 1.5, 0.3, 'exponential', 0.05)
        }
        
        total_weight = sum(f.weight for f in self.factors.values())
        assert abs(total_weight - 1.0) < 0.01, f"Total weight must be 1.0, got {total_weight}"
    
    def calculate_factor_multiplier(self, factor_name: str, value: float, normalized: bool = False) -> Dict:
        """Tek bir risk faktörü için çarpan hesapla"""
        if factor_name not in self.factors:
            raise ValueError(f"Unknown factor: {factor_name}")
        
        config = self.factors[factor_name]
        norm_value = self._normalize_value(factor_name, value) if not normalized else value
        
        if config.distribution == 'linear':
            multiplier = self._linear_distribution(norm_value, config.min_multiplier, config.max_multiplier)
        elif config.distribution == 'exponential':
            multiplier = self._exponential_distribution(norm_value, config.min_multiplier, config.max_multiplier)
        elif config.distribution == 'sigmoid':
            multiplier = self._sigmoid_distribution(norm_value, config.min_multiplier, config.max_multiplier)
        else:
            raise ValueError(f"Unknown distribution: {config.distribution}")
        
        multiplier = np.clip(multiplier, config.min_multiplier, config.max_multiplier)
        
        return {
            'factor': factor_name,
            'raw_value': value,
            'normalized_value': norm_value,
            'multiplier': round(multiplier, 4),
            'min': config.min_multiplier,
            'max': config.max_multiplier,
            'weight': config.weight,
            'distribution': config.distribution
        }
    
    def _normalize_value(self, factor_name: str, value: float) -> float:
        """Değeri 0-1 arasına normalize et"""
        if factor_name == 'seismicity':
            return np.clip(value, 0, 1)
        elif factor_name == 'building_age':
            return np.clip(value / 50.0, 0, 1)
        elif factor_name == 'building_quality':
            return 1.0 - np.clip(value / 3.0, 0, 1)
        elif factor_name == 'soil_type':
            return np.clip(value / 3.0, 0, 1)
        elif factor_name == 'elevation':
            return np.clip(value / 1000.0, 0, 1)
        elif factor_name == 'population_density':
            return np.clip(value / 20000.0, 0, 1)
        elif factor_name == 'distance_to_fault':
            return 1.0 - np.clip(value / 200.0, 0, 1)
        elif factor_name == 'historical_damage':
            return np.clip(value, 0, 1)
        else:
            return np.clip(value, 0, 1)
    
    def _linear_distribution(self, norm_value: float, min_mult: float, max_mult: float) -> float:
        """Linear dağılım"""
        return min_mult + (max_mult - min_mult) * norm_value
    
    def _exponential_distribution(self, norm_value: float, min_mult: float, max_mult: float) -> float:
        """Exponential dağılım"""
        exp_max = np.exp(2) - 1
        exp_value = (np.exp(2 * norm_value) - 1) / exp_max
        return min_mult + (max_mult - min_mult) * exp_value
    
    def _sigmoid_distribution(self, norm_value: float, min_mult: float, max_mult: float) -> float:
        """Sigmoid dağılım"""
        k = 10
        sigmoid_value = 1 / (1 + np.exp(-k * (norm_value - 0.5)))
        return min_mult + (max_mult - min_mult) * sigmoid_value


# =============================================================================
# İMPROVEMENTS SINIFLAR (location_precision.py'den)
# =============================================================================

class LocationPrecisionValidator:
    """Konum hassasiyeti ve GPS accuracy doğrulayıcı"""
    
    def __init__(self):
        self.wgs84 = CRS("EPSG:4326")
        self.utm36n = CRS("EPSG:32636")
        self.transformer_to_utm = Transformer.from_crs(self.wgs84, self.utm36n, always_xy=True)
        self.transformer_to_wgs84 = Transformer.from_crs(self.utm36n, self.wgs84, always_xy=True)
        
        self.turkey_bounds = {
            'lat_min': 36.0, 'lat_max': 42.0,
            'lon_min': 26.0, 'lon_max': 45.0
        }
        
        self.accuracy_thresholds = {
            'high_precision': 10,
            'standard': 50,
            'low_precision': 100
        }
    
    def validate_wgs84_coordinates(self, lat: float, lon: float) -> dict:
        """WGS84 koordinatlarını doğrula"""
        results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'normalized_lat': lat,
            'normalized_lon': lon
        }
        
        if not (-90 <= lat <= 90):
            results['valid'] = False
            results['errors'].append(f"Latitude {lat} out of range [-90, 90]")
        
        if not (-180 <= lon <= 180):
            results['valid'] = False
            results['errors'].append(f"Longitude {lon} out of range [-180, 180]")
        
        if not (self.turkey_bounds['lat_min'] <= lat <= self.turkey_bounds['lat_max']):
            results['warnings'].append(f"Latitude {lat} outside Turkey bounds")
        
        if not (self.turkey_bounds['lon_min'] <= lon <= self.turkey_bounds['lon_max']):
            results['warnings'].append(f"Longitude {lon} outside Turkey bounds")
        
        lat_precision = len(str(lat).split('.')[-1]) if '.' in str(lat) else 0
        lon_precision = len(str(lon).split('.')[-1]) if '.' in str(lon) else 0
        
        if lat_precision < 4 or lon_precision < 4:
            results['warnings'].append(
                f"Low precision: lat={lat_precision} decimals, lon={lon_precision} decimals. "
                "Recommend at least 4 decimals (~11m accuracy)"
            )
        
        if lon > 180:
            results['normalized_lon'] = lon - 360
            results['warnings'].append(f"Longitude normalized from {lon} to {results['normalized_lon']}")
        elif lon < -180:
            results['normalized_lon'] = lon + 360
            results['warnings'].append(f"Longitude normalized from {lon} to {results['normalized_lon']}")
        
        return results
    
    def calculate_distance_multiple_methods(self, point1: tuple, point2: tuple) -> dict:
        """Çoklu yöntemle mesafe hesapla ve karşılaştır"""
        lat1, lon1 = point1
        lat2, lon2 = point2
        
        dist_geodesic = geodesic(point1, point2).km
        dist_great_circle = great_circle(point1, point2).km
        dist_euclidean = math.sqrt((lat2-lat1)**2 + (lon2-lon1)**2) * 111
        
        try:
            x1, y1 = self.transformer_to_utm.transform(lon1, lat1)
            x2, y2 = self.transformer_to_utm.transform(lon2, lat2)
            dist_utm = math.sqrt((x2-x1)**2 + (y2-y1)**2) / 1000
        except Exception as e:
            dist_utm = None
        
        differences = {
            'geodesic_vs_great_circle': abs(dist_geodesic - dist_great_circle),
            'geodesic_vs_euclidean': abs(dist_geodesic - dist_euclidean),
            'geodesic_vs_utm': abs(dist_geodesic - dist_utm) if dist_utm else None
        }
        
        return {
            'geodesic_km': round(dist_geodesic, 3),
            'great_circle_km': round(dist_great_circle, 3),
            'euclidean_km': round(dist_euclidean, 3),
            'utm_km': round(dist_utm, 3) if dist_utm else None,
            'differences': differences,
            'recommended': 'geodesic',
            'max_error_meters': max([d for d in differences.values() if d is not None]) * 1000
        }


# =============================================================================
# PAKET YAPISI: Gerçekçi Teminat Limitleri (Uluslararası Standartlar)
# =============================================================================

COVERAGE_PACKAGES = {
    'temel': {
        'max_coverage': 250_000,
        'base_premium_rate': 0.0100,  # %1.0 (TÜM PAKETLER AYNI ORAN - sadece teminat farkı)
        'description': 'Acil Likidite Paketi - İlk yardım çantası gibi',
        'target': 'Genç aileler, ilk ev sahipleri'
    },
    'standard': {
        'max_coverage': 750_000,
        'base_premium_rate': 0.0100,  # %1.0 (TÜM PAKETLER AYNI ORAN - sadece teminat farkı)
        'description': 'DASK Tamamlayıcı - En popüler paket',
        'target': 'Orta gelir, tek konut sahipleri'
    },
    'premium': {
        'max_coverage': 1_500_000,
        'base_premium_rate': 0.0100,  # %1.0 (TÜM PAKETLER AYNI ORAN - sadece teminat farkı)
        'description': 'Yüksek Değerli Mülkler - Lüks konut koruması',
        'target': 'Yüksek net değer, premium lokasyonlar'
    }
}

# =============================================================================
# GERÇEK DEPREM VERİSİ ANALİZİ - SİSMİK RİSK HARİTASI
# =============================================================================

class RealEarthquakeDataAnalyzer:
    """Gerçek deprem verilerini analiz ederek bölgesel risk haritası oluşturur"""
    
    def __init__(self, earthquake_file=None):
        if earthquake_file is None:
            # Default path - src/ içinden parent/data/ klasörüne
            earthquake_file = str(Path(__file__).parent.parent / 'data' / 'earthquakes.csv')
        
        self.earthquake_file = earthquake_file
        self.earthquakes_df = None
        self.regional_risk_map = {}
        
    def load_real_earthquake_data(self):
        """Gerçek deprem verisini yükle"""
        print("\n🌍 Gerçek deprem verisi yükleniyor...")
        
        try:
            # Farklı encoding'leri dene
            encodings = ['latin-1', 'windows-1254', 'utf-8', 'iso-8859-9']
            df = None
            
            for enc in encodings:
                try:
                    df = pd.read_csv(
                        self.earthquake_file,
                        encoding=enc,
                        on_bad_lines='skip'
                    )
                    print(f"✅ Dosya '{enc}' encoding ile yüklendi")
                    break
                except Exception as e:
                    continue
            
            if df is None:
                print("❌ Dosya hiçbir encoding ile yüklenemedi!")
                return None
            
            # Sütun isimlerini temizle
            df.columns = df.columns.str.strip()
            
            # Gerekli sütunları kontrol et
            required_cols = ['Enlem', 'Boylam', 'xM']
            if not all(col in df.columns for col in required_cols):
                print(f"⚠️ Gerekli sütunlar bulunamadı: {df.columns.tolist()}")
                return None
            
            # Veri temizleme
            df = df[df['Enlem'].notna() & df['Boylam'].notna() & df['xM'].notna()].copy()
            
            # Sayısal değerlere dönüştür
            df['Enlem'] = pd.to_numeric(df['Enlem'], errors='coerce')
            df['Boylam'] = pd.to_numeric(df['Boylam'], errors='coerce')
            df['xM'] = pd.to_numeric(df['xM'], errors='coerce')
            
            # NaN değerleri temizle
            df = df.dropna(subset=['Enlem', 'Boylam', 'xM'])
            
            # Türkiye sınırları içinde olanları filtrele
            df = df[
                (df['Enlem'] >= 36.0) & (df['Enlem'] <= 42.0) &
                (df['Boylam'] >= 26.0) & (df['Boylam'] <= 45.0)
            ]
            
            self.earthquakes_df = df
            
            print(f"✅ {len(df)} gerçek deprem kaydı yüklendi")
            
            if 'Olus tarihi' in df.columns:
                print(f"   Tarih aralığı: {df['Olus tarihi'].min()} - {df['Olus tarihi'].max()}")
            
            print(f"   Büyüklük aralığı: M{df['xM'].min():.1f} - M{df['xM'].max():.1f}")
            print(f"   Ortalama büyüklük: M{df['xM'].mean():.2f}")
            
            return df
            
        except Exception as e:
            print(f"❌ Deprem verisi yüklenirken hata: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def calculate_regional_seismic_density(self, grid_size_km=50):
        """Bölgesel deprem yoğunluğu haritası oluştur"""
        print(f"\n📊 Bölgesel deprem yoğunluğu hesaplanıyor (Grid: {grid_size_km}km)...")
        
        if self.earthquakes_df is None or len(self.earthquakes_df) == 0:
            print("⚠️ Deprem verisi bulunamadı!")
            return {}
        
        # Grid oluştur (Türkiye)
        lat_range = np.arange(36.0, 42.1, grid_size_km / 111)  # 1° ≈ 111km
        lon_range = np.arange(26.0, 45.1, grid_size_km / 111)
        
        regional_risk_map = {}
        
        for lat in lat_range:
            for lon in lon_range:
                # Bu grid hücresindeki depremleri say
                nearby_earthquakes = self.earthquakes_df[
                    (self.earthquakes_df['Enlem'] >= lat - 0.5) & 
                    (self.earthquakes_df['Enlem'] <= lat + 0.5) &
                    (self.earthquakes_df['Boylam'] >= lon - 0.5) & 
                    (self.earthquakes_df['Boylam'] <= lon + 0.5)
                ]
                
                if len(nearby_earthquakes) > 0:
                    # Deprem sayısı ve büyüklükleri ile risk hesapla
                    count = len(nearby_earthquakes)
                    avg_magnitude = nearby_earthquakes['xM'].mean()
                    max_magnitude = nearby_earthquakes['xM'].max()
                    
                    # Seismik yoğunluk skoru
                    density_score = (
                        np.log10(count + 1) * 
                        avg_magnitude * 
                        (max_magnitude / 10)
                    )
                    
                    regional_risk_map[(round(lat, 2), round(lon, 2))] = {
                        'density_score': density_score,
                        'earthquake_count': count,
                        'avg_magnitude': avg_magnitude,
                        'max_magnitude': max_magnitude
                    }
        
        self.regional_risk_map = regional_risk_map
        
        print(f"✅ {len(regional_risk_map)} bölge için risk haritası oluşturuldu")
        print(f"   En yüksek risk: {max([v['density_score'] for v in regional_risk_map.values()]):.2f}")
        print(f"   En düşük risk: {min([v['density_score'] for v in regional_risk_map.values()]):.2f}")
        
        return regional_risk_map
    
    def get_location_seismic_risk(self, latitude, longitude, distance_to_fault=None):
        """
        Belirli bir koordinat için seismik risk skoru hesapla (0-1 arası)
        
        ✨ YENİ: Fay mesafesi ile değişken risk
        """
        if not self.regional_risk_map:
            # Eğer harita yoksa, fay mesafesine göre hesapla
            if distance_to_fault is not None:
                return self._calculate_fault_based_risk(distance_to_fault)
            return 0.5  # Varsayılan orta risk
        
        # En yakın grid hücresini bul
        lat_rounded = round(latitude / 0.5) * 0.5
        lon_rounded = round(longitude / 0.5) * 0.5
        
        # Yakındaki grid hücrelerini kontrol et
        nearby_cells = []
        for dlat in [-0.5, 0, 0.5]:
            for dlon in [-0.5, 0, 0.5]:
                key = (round(lat_rounded + dlat, 2), round(lon_rounded + dlon, 2))
                if key in self.regional_risk_map:
                    nearby_cells.append(self.regional_risk_map[key]['density_score'])
        
        if not nearby_cells:
            # Veri yoksa, en yakın depremlere bak
            if self.earthquakes_df is not None:
                nearby_earthquakes = self.earthquakes_df[
                    (abs(self.earthquakes_df['Enlem'] - latitude) <= 1.0) &
                    (abs(self.earthquakes_df['Boylam'] - longitude) <= 1.0)
                ]
                
                if len(nearby_earthquakes) > 0:
                    count = len(nearby_earthquakes)
                    avg_mag = nearby_earthquakes['xM'].mean()
                    density_risk = min((count * avg_mag) / 100, 1.0)
                    
                    # Fay mesafesi ile kombine et
                    if distance_to_fault is not None:
                        fault_risk = self._calculate_fault_based_risk(distance_to_fault)
                        return (density_risk * 0.6 + fault_risk * 0.4)
                    
                    return density_risk
            
            # Hiç veri yoksa fay mesafesi kullan
            if distance_to_fault is not None:
                return self._calculate_fault_based_risk(distance_to_fault)
            
            return 0.3  # Varsayılan düşük risk
        
        # Ortalama risk skoru
        avg_risk = np.mean(nearby_cells)
        
        # Kademeli normalizasyon (daha geniş aralık için)
        if avg_risk <= 1.0:
            normalized_risk = avg_risk * 0.20
        elif avg_risk <= 2.0:
            normalized_risk = 0.20 + ((avg_risk - 1.0) * 0.15)
        elif avg_risk <= 3.0:
            normalized_risk = 0.35 + ((avg_risk - 2.0) * 0.15)
        elif avg_risk <= 4.0:
            normalized_risk = 0.50 + ((avg_risk - 3.0) * 0.15)
        elif avg_risk <= 5.0:
            normalized_risk = 0.65 + ((avg_risk - 4.0) * 0.10)
        elif avg_risk <= 6.0:
            normalized_risk = 0.75 + ((avg_risk - 5.0) * 0.10)
        elif avg_risk <= 7.0:
            normalized_risk = 0.85 + ((avg_risk - 6.0) * 0.08)
        else:
            normalized_risk = 0.93 + min((avg_risk - 7.0) * 0.05, 0.07)
        
        # Fay mesafesi varsa kombine et
        if distance_to_fault is not None:
            fault_risk = self._calculate_fault_based_risk(distance_to_fault)
            normalized_risk = (normalized_risk * 0.7 + fault_risk * 0.3)
        
        return np.clip(normalized_risk, 0, 1)
    
    def _calculate_fault_based_risk(self, distance_km):
        """
        Fay mesafesine göre risk hesapla - GERÇEKÇI İSTANBUL DEĞERLERİ
        
        İstanbul geneli yüksek riskli olduğu için daha yumuşak bir skala:
        - < 10 km: Çok yüksek risk (0.85-0.95)
        - 10-30 km: Yüksek risk (0.70-0.85)
        - 30-60 km: Orta-Yüksek risk (0.55-0.70)
        - 60-100 km: Orta risk (0.45-0.55)
        - 100-120 km: Düşük-Orta risk (0.35-0.45)
        - > 120 km: Düşük risk (0.25-0.35)
        """
        if distance_km < 10:
            return 0.85 + (10 - distance_km) * 0.01  # 0.85-0.95
        elif distance_km < 30:
            return 0.70 + (30 - distance_km) / 20 * 0.15  # 0.70-0.85
        elif distance_km < 60:
            return 0.55 + (60 - distance_km) / 30 * 0.15  # 0.55-0.70
        elif distance_km < 100:
            return 0.45 + (100 - distance_km) / 40 * 0.10  # 0.45-0.55
        elif distance_km < 120:
            return 0.35 + (120 - distance_km) / 20 * 0.10  # 0.35-0.45
        else:
            return max(0.25, 0.35 - (distance_km - 120) / 50 * 0.10)  # 0.25-0.35

# =============================================================================
# VERİ YÜKLEME - BİNA STOĞU (CSV'DEN)
# =============================================================================

class BuildingDataLoader:
    """CSV dosyasından bina verisi yükleyici"""
    
    def __init__(self, data_dir=None):
        if data_dir is None:
            data_dir = str(Path(__file__).parent.parent / 'data')
        self.data_dir = data_dir
        import os
        if not os.path.exists(self.data_dir):
            raise FileNotFoundError(f"❌ Veri dizini bulunamadı: {self.data_dir}")
    
    def load_building_data(self, filepath=None):
        """CSV dosyasından bina verilerini yükle"""
        if filepath is None:
            filepath = str(Path(__file__).parent.parent / 'data' / 'buildings.csv')
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"❌ Bina verisi bulunamadı: {filepath}\n"
                                  f"Lütfen önce data_generator.py çalıştırarak veri oluşturun.")
        
        print(f"\n📂 Bina verisi yükleniyor: {filepath}")
        
        try:
            # CSV'yi yükle
            df = pd.read_csv(filepath, encoding='utf-8-sig')
            
            print(f"✅ {len(df):,} bina kaydı yüklendi")
            
            # Temel sütun kontrolü
            required_cols = ['building_id', 'latitude', 'longitude', 'structure_type', 
                           'construction_year', 'floors', 'insurance_value_tl']
            
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                print(f"⚠️ Eksik sütunlar: {missing_cols}")
            
            # Veri tiplerini düzelt
            numeric_cols = [
                'latitude', 'longitude', 'construction_year', 'building_age',
                'floors', 'building_area_m2', 'apartment_count', 'residents',
                'commercial_units', 'insurance_value_tl', 'annual_premium_tl',
                'monthly_premium_tl', 'quality_score', 'city_risk_factor',
                'soil_amplification', 'liquefaction_risk', 'damage_factor',
                'risk_score', 'previous_damage_count'
            ]
            
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Boolean sütunları düzelt
            if 'has_previous_damage' in df.columns:
                df['has_previous_damage'] = df['has_previous_damage'].astype(str).str.lower()
                df['has_previous_damage'] = df['has_previous_damage'].map({
                    'true': True, '1': True, 'yes': True, 'evet': True,
                    'false': False, '0': False, 'no': False, 'hayir': False
                }).fillna(False)
            
            # Bina yaşını güncelle (eğer yoksa)
            if 'building_age' not in df.columns and 'construction_year' in df.columns:
                current_year = datetime.now().year
                df['building_age'] = current_year - df['construction_year']
            
            # NaN değerleri temizle
            df.fillna({
                'insurance_value_tl': 0,
                'annual_premium_tl': 0,
                'monthly_premium_tl': 0,
                'residents': 0,
                'commercial_units': 0,
                'apartment_count': 0,
                'quality_score': 5,
                'city_risk_factor': 1.0,
                'damage_factor': 0.5,
                'risk_score': 0.5,
                'previous_damage_count': 0,
                'construction_year': 2000,
                'building_age': 25,
                'floors': 5,
                'soil_amplification': 1.0,
                'liquefaction_risk': 0.0,
                'has_previous_damage': False,
                'policy_status': 'Aktif'
            }, inplace=True)
            
            # Paket tipini ata (eğer yoksa)
            if 'package_type' not in df.columns or df['package_type'].isna().any():
                df = self._assign_package_types(df)
            
            # Veri kalitesi özeti
            print(f"\n📊 Veri Özeti:")
            print(f"   - Şehir Sayısı: {df['city'].nunique() if 'city' in df.columns else 'N/A'}")
            print(f"   - Yapı Tipi Çeşidi: {df['structure_type'].nunique() if 'structure_type' in df.columns else 'N/A'}")
            print(f"   - Ortalama Bina Yaşı: {df['building_age'].mean():.1f} yıl" if 'building_age' in df.columns else "")
            print(f"   - Ortalama Sigorta Değeri: {df['insurance_value_tl'].mean():,.0f} TL" if 'insurance_value_tl' in df.columns else "")
            print(f"   - Aktif Poliçe Sayısı: {(df['policy_status']=='Aktif').sum():,}" if 'policy_status' in df.columns else "")
            
            return df
            
        except Exception as e:
            print(f"❌ Veri yüklenirken hata: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _assign_package_types(self, buildings_df):
        """Binalara paket tipi ata"""
        
        def assign_package(row):
            value = row.get('insurance_value_tl', 0)
            risk = row.get('risk_score', 0.5)
            quality = row.get('quality_score', 5.0)
            age = row.get('building_age', 30)
            
            # GERÇEKÇİ DAĞILIM: Temel %40-45, Standard %45-50, Premium %8-12
            # Premium: Sadece çok yüksek değer VE düşük risk
            if (value > 3_200_000 and risk < 0.30) or (quality > 9.2 and age < 4):
                return 'premium'
            # Standard: Orta değer ve düşük-orta risk
            elif (value >= 1_500_000 and value <= 3_200_000 and
                  risk >= 0.25 and risk <= 0.60):
                return 'standard'
            # Temel: Düşük değer veya yüksek risk
            else:
                return 'temel'
        
        buildings_df['package_type'] = buildings_df.apply(assign_package, axis=1)
        
        # Paket detaylarını ekle
        for package_type in ['temel', 'standard', 'premium']:
            pkg = COVERAGE_PACKAGES[package_type]
            mask = buildings_df['package_type'] == package_type
            
            buildings_df.loc[mask, 'max_coverage'] = pkg['max_coverage']
            buildings_df.loc[mask, 'package_description'] = pkg['description']
        
        return buildings_df

# =============================================================================
# YAPAY ZEKA DESTEKLİ RİSK MODELLEMESİ VE DİNAMİK FİYATLANDIRMA
# =============================================================================

class AIRiskPricingModel:
    """AI destekli risk modellemesi ve dinamik fiyatlandırma (Fine-Grained 0.6x-2.0x)"""
    
    def __init__(self, config=None):
        self.risk_model = None
        self.scaler = StandardScaler()
        self.feature_importance = None
        self.mse = None
        self.r2 = None
        self.model_metrics = None
        
        # Eğitim konfigürasyonu
        self.config = config or {
            'xgb_n_estimators': 200,
            'xgb_max_depth': 8,
            'xgb_learning_rate': 0.05,
            'lgb_n_estimators': 200,
            'lgb_max_depth': 8,
            'lgb_learning_rate': 0.05,
            'nn_hidden_layers': (100, 50, 25),
            'nn_max_iter': 500,
            'test_size': 0.3,
            'random_state': 42
        }
        
        # İyileştirilmiş pricing engine
        if IMPROVEMENTS_AVAILABLE:
            self.fine_grained_engine = FineGrainedPricingEngine()
            self.location_validator = LocationPrecisionValidator()
            print("✅ AIRiskPricingModel: Fine-grained pricing aktif (0.6x-2.0x)")
        else:
            print("⚠️ AIRiskPricingModel: Fine-grained pricing devre dışı (improvements paketi eksik)")
            self.fine_grained_engine = None
            self.location_validator = None
        
    def prepare_features(self, buildings_df):
        """
        Risk modellemesi için özellikler hazırla
        
        ✨ YENİ: 12 Ek Parametre Eklenmiş Hali ✨
        - Konum detayları: district, neighborhood (granular risk)
        - Yapısal detaylar: structure_type, apartment_count, residents, commercial_units
        - Jeolojik detaylar: soil_type, nearest_fault
        - Spatial features: lat/lon bazlı mesafe hesaplamaları
        - Müşteri faktörü: customer_score (fraud/güvenilirlik)
        """
        
        features = buildings_df.copy()
        
        # =========================================================================
        # BÖLÜM 1: TEMEL VE MEVCUT FEATURES
        # =========================================================================
        
        # damage_factor ekle (structure_type'a göre)
        if 'damage_factor' not in features.columns:
            structure_damage_map = {
                'betonarme_cok_yeni': 0.2,
                'betonarme_yeni': 0.35,
                'betonarme_orta': 0.6,
                'betonarme_eski': 0.9,
                'yigma': 1.3,
                'celik': 0.15
            }
            features['damage_factor'] = features['structure_type'].map(structure_damage_map).fillna(0.6)
        
        # Temel risk skoru hesapla (başlangıç)
        features['base_risk_score'] = (
            (features['building_age'] / 100) * 0.3 +
            features['damage_factor'] * 0.3 +
            features['liquefaction_risk'] * 0.2 +
            features.get('city_risk_factor', 1.0) * 0.2
        ).clip(0, 1)
        
        # Türev özellikler (mevcut)
        features['premium_to_value_ratio'] = features.get('annual_premium_tl', 0) / features['insurance_value_tl'].replace({0: np.nan})
        features['premium_to_value_ratio'].replace([np.inf, -np.inf], np.nan, inplace=True)
        features['premium_to_value_ratio'].fillna(0.008, inplace=True)
        
        features['coverage_per_resident'] = features['insurance_value_tl'] / features['residents'].replace({0: np.nan})
        features['coverage_per_resident'].replace([np.inf, -np.inf], np.nan, inplace=True)
        features['coverage_per_resident'].fillna(features['insurance_value_tl'], inplace=True)
        
        features['occupancy_density'] = features['residents'] / (features['building_area_m2'] / 100)
        features['occupancy_density'].replace([np.inf, -np.inf], 0, inplace=True)
        
        features['commercial_ratio'] = features['commercial_units'] / (features['apartment_count'] + features['commercial_units']).replace({0: np.nan})
        features['commercial_ratio'].fillna(0, inplace=True)
        
        # Eksik kolonları ekle (eğer yoksa)
        if 'has_previous_damage' not in features.columns:
            features['has_previous_damage'] = 0
        if 'previous_damage_count' not in features.columns:
            features['previous_damage_count'] = 0
        if 'city_risk_factor' not in features.columns:
            # Şehir bazlı risk faktörü (İstanbul için 1.8, diğerleri için 1.0)
            features['city_risk_factor'] = features['city'].map({
                'İstanbul': 1.8,
                'İzmir': 1.5,
                'Ankara': 1.2
            }).fillna(1.0)
        
        features['has_previous_damage_flag'] = features['has_previous_damage'].astype(int)
        
        # =========================================================================
        # BÖLÜM 2: YENİ EK PARAMETRELER (12 ADET)
        # =========================================================================
        
        # 1-2. DISTRICT & NEIGHBORHOOD RISK FACTORS (Granular konum riski)
        # İlçe bazında risk haritası (örnek: İstanbul ilçeleri için AFAD verileri bazlı)
        district_risk_map = {
            'Fatih': 1.9, 'Beyoğlu': 1.85, 'Kadıköy': 1.75, 'Üsküdar': 1.8,
            'Beşiktaş': 1.7, 'Şişli': 1.75, 'Bakırköy': 1.6, 'Zeytinburnu': 1.95,
            'Avcılar': 2.0, 'Bahçelievler': 1.7, 'Esenler': 1.85, 'Gaziosmanpaşa': 1.8
        }
        features['district_risk_factor'] = features.get('district', pd.Series(dtype=str)).map(district_risk_map).fillna(1.5)
        
        # Mahalle yoğunluk faktörü (örnek: yüksek nüfuslu mahalleler için artış)
        # Gerçek uygulamada mahalle bazında census verisi kullanılabilir
        features['neighborhood_density_factor'] = 1.0  # Placeholder (veri varsa hesaplanabilir)
        
        # 3-4. SPATIAL FEATURES (Lat/Lon bazlı mesafe hesaplamaları)
        # Fay hatlarına mesafe (mevcut distance_to_fault_km kullanılıyor, ek spatial analiz ekleyelim)
        # Örnek: İstanbul merkezi (Fatih: 41.0186, 28.9498) uzaklık
        istanbul_center = (41.0186, 28.9498)
        if 'latitude' in features.columns and 'longitude' in features.columns:
            features['distance_to_city_center_km'] = features.apply(
                lambda row: geodesic((row['latitude'], row['longitude']), istanbul_center).km 
                if pd.notna(row['latitude']) and pd.notna(row['longitude']) else 0,
                axis=1
            )
            # Merkeze yakınlık faktörü (yüksek yoğunluk = yüksek risk)
            features['proximity_risk_factor'] = np.where(
                features['distance_to_city_center_km'] < 10, 1.3,
                np.where(features['distance_to_city_center_km'] < 30, 1.1, 1.0)
            )
        else:
            features['distance_to_city_center_km'] = 0
            features['proximity_risk_factor'] = 1.0
        
        # 5. STRUCTURE_TYPE INTERACTION (Yapı tipi ile yaş etkileşimi)
        # Zaten encoding yapılacak, ek türev feature ekleyelim
        features['structure_age_interaction'] = features['damage_factor'] * (features['building_age'] / 50)
        
        # 6-7-8. APARTMENT_COUNT, RESIDENTS, COMMERCIAL_UNITS (Yoğunluk metrikleri)
        # Bina komplekslik skoru
        features['building_complexity_score'] = (
            np.log1p(features.get('apartment_count', 1)) * 0.4 +
            np.log1p(features.get('residents', 1)) * 0.3 +
            np.log1p(features.get('commercial_units', 0)) * 0.3
        )
        
        # Ticari/residential miksi (değiştirilmiş commercial_ratio - daha sofistike)
        total_units = features.get('apartment_count', 1) + features.get('commercial_units', 0)
        features['mixed_use_factor'] = np.where(
            features.get('commercial_units', 0) > 0,
            1.1,  # Karma kullanım riski artırır (evacuation kompleksliği)
            1.0
        )
        
        # 9-10. SOIL_TYPE & NEAREST_FAULT (Jeolojik detaylar)
        # Zemin tipi risk haritası (A=en sağlam, E=en zayıf)
        soil_risk_map = {
            'A': 0.8, 'B': 1.0, 'C': 1.2, 'D': 1.5, 'E': 1.8,
            'ZA': 0.9, 'ZB': 1.1, 'ZC': 1.3, 'ZD': 1.6, 'ZE': 2.0
        }
        features['soil_risk_factor'] = features.get('soil_type', pd.Series(dtype=str)).map(soil_risk_map).fillna(1.2)
        
        # Fay hattı tipi risk faktörü
        fault_risk_map = {
            'KAF': 1.9,   # Kuzey Anadolu Fayı (en aktif)
            'DAF': 1.7,   # Doğu Anadolu Fayı
            'BZBF': 1.6,  # Batı Anadolu Fay Bölgesi
            'Other': 1.0
        }
        features['fault_type_risk_factor'] = features.get('nearest_fault', pd.Series(dtype=str)).map(fault_risk_map).fillna(1.0)
        
        # Fay mesafesi + fay tipi kombinasyonu
        if 'distance_to_fault_km' in features.columns:
            features['fault_combined_risk'] = (
                features['fault_type_risk_factor'] * 
                np.exp(-features['distance_to_fault_km'] / 100)  # Exponential decay
            )
        else:
            features['fault_combined_risk'] = 1.0
        
        # 11. CUSTOMER_SCORE (Müşteri güvenilirlik - fraud/personalization için)
        # Yüksek skor = düşük fraud riski = prim indirimi olabilir
        if 'customer_score' not in features.columns:
            features['customer_score'] = 75  # Default (orta seviye)
        
        features['customer_reliability_factor'] = np.where(
            features['customer_score'] >= 80, 0.95,  # Güvenilir müşteri - %5 indirim
            np.where(features['customer_score'] >= 60, 1.0,  # Normal
                    1.1)  # Düşük skor - %10 artış
        )
        
        # 12. MULTI-PARAMETER COMPOSITE INDEX (Kombinasyon metrikleri)
        # Jeolojik+Yapısal+Demografik faktörlerin weighted kombinasyonu
        features['composite_risk_index'] = (
            features['soil_risk_factor'] * 0.25 +
            features['fault_combined_risk'] * 0.25 +
            features['district_risk_factor'] / 2 * 0.20 +  # Normalize to ~1.0
            features['building_complexity_score'] / 5 * 0.15 +  # Normalize
            features['structure_age_interaction'] / 2 * 0.15  # Normalize
        ).clip(0, 3)
        
        # =========================================================================
        # BÖLÜM 3: GELİŞTİRİLMİŞ AI RISK SKORU
        # =========================================================================
        
        # AI risk skoru (kapsamlı feature set ile hesaplama)
        features['ai_risk_score'] = (
            (features['building_age'] / 100) * 0.12 +
            features['damage_factor'] * 0.10 +
            features['liquefaction_risk'] * 0.10 +
            (1 - features['quality_score'] / 10) * 0.10 +
            features['city_risk_factor'] / 2 * 0.08 +  # Normalize to ~1.0
            features['has_previous_damage_flag'] * 0.08 +
            (features['previous_damage_count'] / 5) * 0.05 +
            # Ek parametreler (toplam %37 ağırlık)
            features['district_risk_factor'] / 2 * 0.08 +
            features['soil_risk_factor'] / 2 * 0.07 +
            features['fault_combined_risk'] * 0.07 +
            features['proximity_risk_factor'] * 0.05 +
            features['building_complexity_score'] / 5 * 0.05 +
            features['composite_risk_index'] / 3 * 0.05
        ).clip(0, 1)
        
        # Final risk skoru (AI + Base kombinasyonu)
        features['risk_score'] = (
            features['ai_risk_score'] * 0.7 +  # AI ağırlığı artırıldı (daha fazla feature)
            features['base_risk_score'] * 0.3
        ).clip(0, 1)
        
        # =========================================================================
        # TEMİZLİK VE NORMALIZASYON
        # =========================================================================
        
        features.replace([np.inf, -np.inf], 0, inplace=True)
        features.fillna(0, inplace=True)
        
        return features
    
    def train_risk_model(self, features_df):
        """
        Risk tahmin modeli eğit
        
        Kapsamlı feature set ve ensemble learning kullanarak risk tahmini yapar
        """
        
        print("\n🤖 AI Risk Modeli Eğitiliyor...")
        print(f"   📊 Toplam veri: {len(features_df)} bina")
        
        # =========================================================================
        # ÖZELLIK SÜTUNLARI (MEVCUT + 12 YENİ PARAMETRE)
        # =========================================================================
        
        # Mevcut features
        feature_cols = [
            'latitude', 'longitude', 'floors', 'soil_amplification',
            'liquefaction_risk', 'damage_factor', 'building_area_m2',
            'building_age', 'insurance_value_tl', 'apartment_count',
            'residents', 'commercial_units', 'quality_score', 'city_risk_factor',
            'premium_to_value_ratio', 'coverage_per_resident', 'occupancy_density',
            'base_risk_score', 'has_previous_damage_flag', 'commercial_ratio',
            'previous_damage_count'
        ]
        
        # ✨ YENİ PARAMETRELER (12 adet)
        new_features = [
            # Granular konum riski
            'district_risk_factor',
            'neighborhood_density_factor',
            # Spatial features
            'distance_to_city_center_km',
            'proximity_risk_factor',
            # Yapısal etkileşimler
            'structure_age_interaction',
            # Yoğunluk metrikleri
            'building_complexity_score',
            'mixed_use_factor',
            # Jeolojik detaylar
            'soil_risk_factor',
            'fault_type_risk_factor',
            'fault_combined_risk',
            # Müşteri faktörü
            'customer_reliability_factor',
            # Composite index
            'composite_risk_index'
        ]
        
        feature_cols.extend(new_features)
        print(f"   ✨ Numerik feature sayısı: {len(feature_cols)}")
        
        # =========================================================================
        # KATEGORİK DEĞİŞKENLERİ ENCODE ET
        # =========================================================================
        
        le_struct = LabelEncoder()
        le_soil = LabelEncoder()
        le_city = LabelEncoder()
        le_policy = LabelEncoder()
        le_district = LabelEncoder()
        le_neighborhood = LabelEncoder()
        le_fault = LabelEncoder()
        
        features_df['structure_type_encoded'] = le_struct.fit_transform(features_df['structure_type'])
        features_df['soil_type_encoded'] = le_soil.fit_transform(features_df['soil_type'])
        features_df['city_encoded'] = le_city.fit_transform(features_df['city'])
        features_df['policy_status_encoded'] = le_policy.fit_transform(features_df['policy_status'])
        
        # District, Neighborhood, Fault encoding
        if 'district' in features_df.columns:
            features_df['district_encoded'] = le_district.fit_transform(features_df['district'].fillna('Unknown'))
        else:
            features_df['district_encoded'] = 0
        
        if 'neighborhood' in features_df.columns:
            features_df['neighborhood_encoded'] = le_neighborhood.fit_transform(features_df['neighborhood'].fillna('Unknown'))
        else:
            features_df['neighborhood_encoded'] = 0
        
        if 'nearest_fault' in features_df.columns:
            features_df['fault_encoded'] = le_fault.fit_transform(features_df['nearest_fault'].fillna('Unknown'))
        else:
            features_df['fault_encoded'] = 0
        
        feature_cols.extend([
            'structure_type_encoded', 'soil_type_encoded',
            'city_encoded', 'policy_status_encoded',
            'district_encoded', 'neighborhood_encoded', 'fault_encoded'
        ])
        
        print(f"   ✨ Encoded feature sayısı: 7")
        print(f"   🎯 TOPLAM FEATURE: {len(feature_cols)} (33 numerik + 7 encoded)")
        
        # Veri hazırlığı
        X = features_df[feature_cols]
        y = features_df['risk_score']
        
        # Train-test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, 
            test_size=self.config['test_size'], 
            random_state=self.config['random_state']
        )
        
        # Ölçeklendirme
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Model 1: XGBoost
        with tqdm(total=3, desc="🤖 Model Eğitimi", unit="model", bar_format='{l_bar}{bar:30}| {n_fmt}/{total_fmt}', colour='cyan', ncols=100) as pbar:
            pbar.set_postfix_str("XGBoost")
            xgb_model = xgb.XGBRegressor(
                n_estimators=self.config['xgb_n_estimators'],
                max_depth=self.config['xgb_max_depth'],
                learning_rate=self.config['xgb_learning_rate'],
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=self.config['random_state']
            )
            xgb_model.fit(X_train_scaled, y_train, verbose=False)
            pbar.update(1)
            
            # Model 2: LightGBM
            pbar.set_postfix_str("LightGBM")
            lgb_model = lgb.LGBMRegressor(
                n_estimators=self.config['lgb_n_estimators'],
                max_depth=self.config['lgb_max_depth'],
                learning_rate=self.config['lgb_learning_rate'],
                subsample=0.8,
                random_state=self.config['random_state'],
                verbose=-1
            )
            lgb_model.fit(X_train_scaled, y_train)
            pbar.update(1)
            
            # Model 3: Neural Network
            pbar.set_postfix_str("Neural Network")
            nn_model = MLPRegressor(
                hidden_layer_sizes=self.config['nn_hidden_layers'],
                activation='relu',
                learning_rate_init=0.001,
                max_iter=self.config['nn_max_iter'],
                random_state=self.config['random_state']
            )
            nn_model.fit(X_train_scaled, y_train)
            pbar.update(1)
        
        # Ensemble model
        print("  ✅ Ensemble model oluşturuluyor...")
        predictions = np.column_stack([
            xgb_model.predict(X_test_scaled),
            lgb_model.predict(X_test_scaled),
            nn_model.predict(X_test_scaled)
        ])
        ensemble_pred = np.mean(predictions, axis=1)
        
        # =========================================================================
        # MODEL PERFORMANSI - DETAYLI METRİKLER
        # =========================================================================
        
        # Test seti metrikleri
        mse = mean_squared_error(y_test, ensemble_pred)
        r2 = r2_score(y_test, ensemble_pred)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y_test, ensemble_pred)
        
        # Cross-validation (5-fold)
        print("\n🔄 Cross-Validation (5-Fold) yapılıyor...")
        kfold = KFold(n_splits=5, shuffle=True, random_state=self.config['random_state'])
        
        # Her model için CV skoru
        cv_scores_xgb = cross_val_score(xgb_model, X_train_scaled, y_train, cv=kfold, scoring='r2')
        cv_scores_lgb = cross_val_score(lgb_model, X_train_scaled, y_train, cv=kfold, scoring='r2')
        
        cv_mean_xgb = cv_scores_xgb.mean()
        cv_std_xgb = cv_scores_xgb.std()
        cv_mean_lgb = cv_scores_lgb.mean()
        cv_std_lgb = cv_scores_lgb.std()
        
        # Training seti metrikleri (overfitting kontrolü)
        train_pred = np.mean(np.column_stack([
            xgb_model.predict(X_train_scaled),
            lgb_model.predict(X_train_scaled),
            nn_model.predict(X_train_scaled)
        ]), axis=1)
        
        train_r2 = r2_score(y_train, train_pred)
        train_mse = mean_squared_error(y_train, train_pred)
        
        self.mse = mse
        self.r2 = r2
        
        # Geliştirilmiş model metrikleri
        self.model_metrics = {
            # Test metrikleri
            'test_mse': round(float(mse), 6),
            'test_rmse': round(float(rmse), 6),
            'test_mae': round(float(mae), 6),
            'test_r2_score': round(float(r2), 4),
            
            # Training metrikleri
            'train_r2_score': round(float(train_r2), 4),
            'train_mse': round(float(train_mse), 6),
            
            # Cross-validation
            'cv_xgb_mean': round(float(cv_mean_xgb), 4),
            'cv_xgb_std': round(float(cv_std_xgb), 4),
            'cv_lgb_mean': round(float(cv_mean_lgb), 4),
            'cv_lgb_std': round(float(cv_std_lgb), 4),
            
            # Overfitting kontrolü
            'overfitting_gap': round(float(train_r2 - r2), 4),
            
            # Genel bilgiler
            'training_samples': len(X_train),
            'test_samples': len(X_test),
            'features_count': len(feature_cols),
            'models': ['XGBoost', 'LightGBM', 'Neural Network'],
            'ensemble_method': 'mean',
            'train_test_split': f"{int((1-self.config['test_size'])*100)}/{int(self.config['test_size']*100)}",
            
            # 🕒 Timestamp (model eğitim tarihi)
            'timestamp': pd.Timestamp.now().isoformat(),
            'last_trained': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        print(f"\n✅ Model Performansı:")
        print(f"  📊 Test Metrikleri:")
        print(f"    - MSE: {mse:.6f}")
        print(f"    - RMSE: {rmse:.6f}")
        print(f"    - MAE: {mae:.6f}")
        print(f"    - R² Score: {r2:.4f}")
        print(f"\n  📊 Training Metrikleri:")
        print(f"    - R² Score: {train_r2:.4f}")
        print(f"    - Overfitting Gap: {train_r2 - r2:.4f}")
        print(f"\n  📊 Cross-Validation (5-Fold):")
        print(f"    - XGBoost R²: {cv_mean_xgb:.4f} (±{cv_std_xgb:.4f})")
        print(f"    - LightGBM R²: {cv_mean_lgb:.4f} (±{cv_std_lgb:.4f})")
        
        # =========================================================================
        # FEATURE IMPORTANCE ANALİZİ (GELİŞTİRİLMİŞ)
        # =========================================================================
        
        print(f"\n⭐ Feature Importance Analizi:")
        
        # XGBoost feature importance
        self.feature_importance = pd.DataFrame({
            'feature': feature_cols,
            'xgb_importance': xgb_model.feature_importances_,
            'lgb_importance': lgb_model.feature_importances_
        }).sort_values('xgb_importance', ascending=False)
        
        # Ensemble importance (ortalama)
        self.feature_importance['ensemble_importance'] = (
            self.feature_importance['xgb_importance'] * 0.5 +
            self.feature_importance['lgb_importance'] * 0.5
        )
        self.feature_importance = self.feature_importance.sort_values('ensemble_importance', ascending=False)
        
        print(f"\n  📊 Top 10 En Önemli Features:")
        for idx, row in self.feature_importance.head(10).iterrows():
            print(f"    {idx+1}. {row['feature']}: {row['ensemble_importance']:.4f}")
        
        # Final modeli kaydet
        self.risk_model = {
            'xgb': xgb_model,
            'lgb': lgb_model,
            'nn': nn_model,
            'feature_cols': feature_cols,
            'le_struct': le_struct,
            'le_soil': le_soil,
            'le_city': le_city,
            'le_policy': le_policy,
            'le_district': le_district,
            'le_neighborhood': le_neighborhood,
            'le_fault': le_fault
        }
        
        return self.risk_model
    
    def predict_risk(self, features_df):
        """
        Eğitilmiş AI modeli ile risk skorlarını tahmin et
        
        Args:
            features_df: Prepare edilmiş features DataFrame
            
        Returns:
            numpy.array: Tahmin edilen risk skorları
        """
        if self.risk_model is None:
            raise ValueError("❌ Risk modeli henüz eğitilmemiş!")
        
        # Encoder'ları al
        le_struct = self.risk_model['le_struct']
        le_soil = self.risk_model['le_soil']
        le_city = self.risk_model['le_city']
        le_policy = self.risk_model['le_policy']
        le_district = self.risk_model['le_district']
        le_neighborhood = self.risk_model['le_neighborhood']
        le_fault = self.risk_model['le_fault']
        
        # Kategorik değişkenleri encode et (eğer yoksa)
        if 'structure_type_encoded' not in features_df.columns:
            features_df = features_df.copy()
            
            # Safe transform: unknown değerleri handle et
            def safe_transform(encoder, values, default_value=0):
                """LabelEncoder'ı güvenli şekilde uygula - yeni değerleri handle eder"""
                result = []
                known_classes = set(encoder.classes_)
                for val in values:
                    if pd.isna(val) or val not in known_classes:
                        result.append(default_value)
                    else:
                        result.append(encoder.transform([val])[0])
                return result
            
            features_df['structure_type_encoded'] = safe_transform(le_struct, features_df['structure_type'])
            features_df['soil_type_encoded'] = safe_transform(le_soil, features_df['soil_type'])
            features_df['city_encoded'] = safe_transform(le_city, features_df['city'])
            features_df['policy_status_encoded'] = safe_transform(le_policy, features_df['policy_status'])
            
            if 'district' in features_df.columns:
                features_df['district_encoded'] = safe_transform(le_district, features_df['district'].fillna('Unknown'))
            else:
                features_df['district_encoded'] = 0
            
            if 'neighborhood' in features_df.columns:
                features_df['neighborhood_encoded'] = safe_transform(le_neighborhood, features_df['neighborhood'].fillna('Unknown'))
            else:
                features_df['neighborhood_encoded'] = 0
            
            if 'nearest_fault' in features_df.columns:
                features_df['fault_encoded'] = safe_transform(le_fault, features_df['nearest_fault'].fillna('Unknown'))
            else:
                features_df['fault_encoded'] = 0
        
        # Feature kolonları al
        feature_cols = self.risk_model['feature_cols']
        
        # Veriyi hazırla
        X = features_df[feature_cols]
        
        # Ölçeklendir
        X_scaled = self.scaler.transform(X)
        
        # Ensemble prediction
        xgb_pred = self.risk_model['xgb'].predict(X_scaled)
        lgb_pred = self.risk_model['lgb'].predict(X_scaled)
        nn_pred = self.risk_model['nn'].predict(X_scaled)
        
        # Ortalama al (ensemble)
        ensemble_pred = np.mean([xgb_pred, lgb_pred, nn_pred], axis=0)
        
        # 0-1 arasına normalize et
        ensemble_pred = np.clip(ensemble_pred, 0.0, 1.0)
        
        return ensemble_pred
    
    def calculate_dynamic_premium(self, building_features, seismic_analyzer=None):
        """
        ✨ YAPAY ZEKA DESTEKLİ DİNAMİK PRİM HESAPLAYICI ✨
        
        GERÇEKTEn DİNAMİK:
        - Risk bazlı prim (sabit değil!)
        - PAKET BAZLI Dinamik Faktör Aralıkları:
          * Temel Paket: 1.5x - 3.0x (daha yüksek primler)
          * Standart Paket: 0.75x - 2.5x (orta seviye)
          * Premium Paket: 0.75x - 2.0x (düşük primler)
        - 8 farklı risk faktörü entegrasyonu
        
        Returns:
            Dict: Detaylı fiyatlandırma bilgileri
        """
        
        if self.risk_model is None:
            raise ValueError("❌ Risk modeli henüz eğitilmemiş!")
        
        # ADIM 1: PAKET BELİRLE (Akıllı Yükseltme)
        initial_package = building_features.get('package_type', 'standard')
        insurance_value = building_features.get('insurance_value_tl', 1_000_000)
        
        if initial_package not in COVERAGE_PACKAGES:
            initial_package = 'standard'
        
        # Risk-based package upgrade logic - DAHA KONSERVATIF
        base_risk = building_features.get('risk_score', 0.5)
        
        # Paket yükseltme sadece çok spesifik durumlarda yapılır
        # Çok yüksek değer VE çok yüksek risk kombinasyonu
        if insurance_value > 4_000_000 and base_risk > 0.80:
            recommended_package = 'premium'
        elif insurance_value > 3_500_000 and base_risk > 0.75:
            recommended_package = 'premium' if initial_package == 'standard' else initial_package
        elif insurance_value > 2_500_000 and base_risk > 0.70:
            recommended_package = 'standard' if initial_package == 'temel' else initial_package
        else:
            # Çoğu durumda mevcut paketi koru
            recommended_package = initial_package
        
        # Final paket seçimi (başlangıç paketi ile karşılaştır)
        package_hierarchy = {'temel': 0, 'standard': 1, 'premium': 2}
        
        if package_hierarchy.get(recommended_package, 1) > package_hierarchy.get(initial_package, 1):
            # Sadece gerçekten gerekli olduğunda yükselt
            final_package = recommended_package
            package_upgraded = True
        else:
            final_package = initial_package
            package_upgraded = False
        
        max_coverage = COVERAGE_PACKAGES[final_package]['max_coverage']
        
        # ADIM 2: KATEGORİK ÖZELLİKLERİ ENCODE ET
        if 'structure_type' in building_features:
            try:
                building_features['structure_type_encoded'] = \
                    self.risk_model['le_struct'].transform([building_features['structure_type']])[0]
            except (ValueError, KeyError):
                building_features['structure_type_encoded'] = 0
        
        if 'soil_type' in building_features:
            try:
                building_features['soil_type_encoded'] = \
                    self.risk_model['le_soil'].transform([building_features['soil_type']])[0]
            except (ValueError, KeyError):
                building_features['soil_type_encoded'] = 0
        
        if 'city' in building_features:
            try:
                building_features['city_encoded'] = \
                    self.risk_model['le_city'].transform([building_features['city']])[0]
            except (ValueError, KeyError):
                building_features['city_encoded'] = 0
        else:
            building_features['city_encoded'] = 0
        
        policy_value = building_features.get('policy_status', 'Pasif')
        try:
            building_features['policy_status_encoded'] = \
                self.risk_model['le_policy'].transform([policy_value])[0]
        except (ValueError, KeyError):
            building_features['policy_status_encoded'] = 0
        
        # ADIM 3: TÜREV ÖZELLİKLERİ HESAPLA
        if 'premium_to_value_ratio' not in building_features:
            building_features['premium_to_value_ratio'] = 0.008
        
        if 'coverage_per_resident' not in building_features:
            residents = building_features.get('residents', 1)
            building_features['coverage_per_resident'] = insurance_value / residents if residents else insurance_value
        
        if 'occupancy_density' not in building_features:
            building_area = building_features.get('building_area_m2', 100)
            residents = building_features.get('residents', 0)
            building_features['occupancy_density'] = residents / (building_area / 100) if building_area else 0
        
        if 'commercial_ratio' not in building_features:
            apt_count = building_features.get('apartment_count', 1)
            comm_units = building_features.get('commercial_units', 0)
            denom = apt_count + comm_units
            building_features['commercial_ratio'] = comm_units / denom if denom else 0
        
        if 'base_risk_score' not in building_features:
            building_features['base_risk_score'] = building_features.get('risk_score', 0.5)
        
        if 'has_previous_damage_flag' not in building_features:
            history_val = building_features.get('has_previous_damage', False)
            building_features['has_previous_damage_flag'] = int(history_val)
        
        # Eksik özellikleri 0 ile doldur
        for col in self.risk_model['feature_cols']:
            if col not in building_features:
                building_features[col] = 0
        
        # Özellik vektörü oluştur
        X = pd.DataFrame([building_features])[self.risk_model['feature_cols']]
        X_scaled = self.scaler.transform(X)
        
        # Risk skoru tahminleri (AI Ensemble)
        risk_scores = []
        for model_name in ['xgb', 'lgb', 'nn']:
            score = self.risk_model[model_name].predict(X_scaled)[0]
            risk_scores.append(score)
        
        final_risk_score = np.mean(risk_scores)
        final_risk_score = np.clip(final_risk_score, 0, 1)
        
        # ADIM 4: İYİLEŞTİRİLMİŞ DİNAMİK FAKTÖR HESAPLA (Paket Bazlı Dinamik Aralıklar)
        # Temel: 1.5-3.0x, Standart: 0.75-2.5x, Premium: 0.75-2.0x
        
        building_age = building_features.get('building_age', 0)
        floors = building_features.get('floors', 1)
        structure_type = building_features.get('structure_type', '')
        soil_type = building_features.get('soil_type', '')
        building_area = building_features.get('building_area_m2', 100)
        distance_to_fault = building_features.get('distance_to_fault_km')
        latitude = building_features.get('latitude', 41.0)
        longitude = building_features.get('longitude', 29.0)
        
        # PAKET BAZLI ARALIK BELİRLEME
        if final_package == 'temel':
            # Temel paket: 1.5x - 3.0x (daha yüksek primler)
            min_multiplier = 1.5
            max_multiplier = 3.0
            multiplier_range = 1.5  # 3.0 - 1.5
        elif final_package == 'standard':
            # Standart paket: 0.75x - 2.5x (orta)
            min_multiplier = 0.75
            max_multiplier = 2.5
            multiplier_range = 1.75  # 2.5 - 0.75
        else:  # premium
            # Premium paket: 0.75x - 2.0x (en düşük primler)
            min_multiplier = 0.75
            max_multiplier = 2.0
            multiplier_range = 1.25  # 2.0 - 0.75
        
        # GELIŞMIŞ DİNAMİK FAKTÖR HESAPLAMA (Paket bazlı aralıklarda)
        # 1. MODEL RİSK FAKTÖRÜ (AI Tahmin) - paket bazlı aralıkta
        model_risk_factor = min_multiplier + (final_risk_score * multiplier_range)
        
        # 2. BİNA YAŞI FAKTÖRÜ - paket bazlı normalize edilmiş
        if building_age < 3:
            age_normalized = 0.0
        elif building_age < 7:
            age_normalized = 0.15
        elif building_age < 12:
            age_normalized = 0.30
        elif building_age < 18:
            age_normalized = 0.45
        elif building_age < 25:
            age_normalized = 0.60
        elif building_age < 35:
            age_normalized = 0.75
        elif building_age < 50:
            age_normalized = 0.90
        else:
            age_normalized = 1.0
        
        age_factor = min_multiplier + (age_normalized * multiplier_range)
        
        # 3. KAT SAYISI FAKTÖRÜ - paket bazlı normalize edilmiş
        if floors <= 2:
            floor_normalized = 0.0
        elif floors <= 4:
            floor_normalized = 0.20
        elif floors <= 6:
            floor_normalized = 0.40
        elif floors <= 10:
            floor_normalized = 0.60
        elif floors <= 15:
            floor_normalized = 0.75
        elif floors <= 20:
            floor_normalized = 0.90
        else:
            floor_normalized = 1.0
        
        floor_factor = min_multiplier + (floor_normalized * multiplier_range)
        
        # 4. YAPI TİPİ FAKTÖRÜ - paket bazlı normalize edilmiş
        structure_lower = structure_type.lower() if structure_type else ''
        
        if 'celik' in structure_lower or 'çelik' in structure_lower:
            structure_normalized = 0.0
        elif 'cok_yeni' in structure_lower or 'çok yeni' in structure_lower:
            structure_normalized = 0.15
        elif 'yeni' in structure_lower:
            structure_normalized = 0.35
        elif 'orta' in structure_lower:
            structure_normalized = 0.55
        elif 'eski' in structure_lower:
            structure_normalized = 0.80
        elif 'yigma' in structure_lower or 'yığma' in structure_lower:
            structure_normalized = 1.0
        else:
            structure_normalized = 0.50
        
        structure_factor = min_multiplier + (structure_normalized * multiplier_range)
        
        # 5. ZEMİN TİPİ FAKTÖRÜ - paket bazlı normalize edilmiş
        soil_lower = soil_type.lower() if soil_type else ''
        
        if 'a' in soil_lower or 'sağlam kaya' in soil_lower or 'sagla' in soil_lower:
            soil_normalized = 0.0
        elif 'b' in soil_lower or 'kaya' in soil_lower:
            soil_normalized = 0.20
        elif 'c' in soil_lower or 'sert' in soil_lower:
            soil_normalized = 0.45
        elif 'd' in soil_lower or 'yumuşak' in soil_lower or 'yumusak' in soil_lower:
            soil_normalized = 0.75
        elif 'e' in soil_lower or 'çok yumuşak' in soil_lower or 'cok yumusak' in soil_lower:
            soil_normalized = 1.0
        else:
            soil_normalized = 0.45
        
        soil_factor = min_multiplier + (soil_normalized * multiplier_range)
        
        # 6. BİNA BÜYÜKLÜĞÜ FAKTÖRÜ - paket bazlı normalize edilmiş
        if building_area < 80:
            area_normalized = 0.0
        elif building_area < 150:
            area_normalized = 0.20
        elif building_area < 250:
            area_normalized = 0.40
        elif building_area < 400:
            area_normalized = 0.60
        elif building_area < 600:
            area_normalized = 0.80
        else:
            area_normalized = 1.0
        
        area_factor = min_multiplier + (area_normalized * multiplier_range)
        
        # 7. SİSMİK RİSK FAKTÖRÜ (GERÇEK DEPREM VERİSİ) - paket bazlı normalize edilmiş
        seismic_risk_score = 0.5
        
        if seismic_analyzer is not None:
            latitude_val = building_features.get('latitude')
            longitude_val = building_features.get('longitude')
            
            if latitude_val is not None and longitude_val is not None:
                try:
                    # Fay mesafesi ile birlikte hesapla
                    seismic_risk_score = seismic_analyzer.get_location_seismic_risk(
                        latitude_val, longitude_val, distance_to_fault
                    )
                except:
                    pass
        
        # Sismik riski paket bazlı aralığa çevir
        seismic_risk_factor = min_multiplier + (seismic_risk_score * multiplier_range)
        
        # 8. SİGORTA DEĞERİ FAKTÖRÜ - paket bazlı normalize edilmiş (ters orantılı)
        if insurance_value < 600_000:
            value_normalized = 0.60  # Yüksek değer = düşük çarpan
        elif insurance_value < 1_200_000:
            value_normalized = 0.50
        elif insurance_value < 2_500_000:
            value_normalized = 0.40
        else:
            value_normalized = 0.30
        
        value_factor = min_multiplier + (value_normalized * multiplier_range)
        
        # ADIM 5: FAKTÖRLERI BİRLEŞTİR - Çarpımsal Model (Paket bazlı dinamik)
        combined_risk_factor = (
            (model_risk_factor ** 0.35) *  # AI modeli (ana faktör)
            (structure_factor ** 0.28) *    # Yapı tipi (çok önemli)
            (soil_factor ** 0.25) *         # Zemin (çok önemli)
            (age_factor ** 0.20) *          # Yaş (önemli)
            (seismic_risk_factor ** 0.18) * # Sismik risk
            (floor_factor ** 0.10) *        # Kat sayısı
            (area_factor ** 0.05) *         # Alan
            (value_factor ** 0.05)          # Değer
        )
        
        # Paket bazlı aralığa kısıtla
        # Temel: 1.5-3.0x, Standart: 0.75-2.5x, Premium: 0.75-2.0x
        combined_risk_factor = np.clip(combined_risk_factor, min_multiplier, max_multiplier)
        
        # ADIM 6: PRİM HESAPLA - Paket bağımsız, risk bazlı gerçek hesaplama
        # Her paketin base rate'i aynı (%1.0), tek fark teminat miktarı
        base_rate = 0.0100  # Sabit %1.0 oran
        base_premium = max_coverage * base_rate
        annual_premium = base_premium * combined_risk_factor
        monthly_premium = annual_premium / 12
        
        # Return dictionary - tüm faktörleri dahil et (varsa)
        result = {
            'package_type': final_package,
            'initial_package': initial_package,
            'package_upgraded': package_upgraded,
            'max_coverage': max_coverage,
            'base_premium': base_premium,
            'combined_risk_factor': combined_risk_factor,
            'annual_premium': annual_premium,
            'monthly_premium': monthly_premium,
            'risk_score': final_risk_score,
            'seismic_risk_score': seismic_risk_score,
            'risk_level': self._get_risk_level(final_risk_score),
            'seismic_risk_level': self._get_seismic_risk_level(seismic_risk_score)
        }
        
        # Fallback faktörlerini ekle (eğer tanımlıysa)
        if 'model_risk_factor' in locals():
            result['model_risk_factor'] = model_risk_factor
        if 'age_factor' in locals():
            result['age_factor'] = age_factor
        if 'floor_factor' in locals():
            result['floor_factor'] = floor_factor
        if 'structure_factor' in locals():
            result['structure_factor'] = structure_factor
        if 'soil_factor' in locals():
            result['soil_factor'] = soil_factor
        if 'seismic_risk_factor' in locals():
            result['seismic_risk_factor'] = seismic_risk_factor
        if 'area_factor' in locals():
            result['area_factor'] = area_factor
        if 'value_factor' in locals():
            result['value_factor'] = value_factor
        
        return result
    
    def _get_risk_level(self, risk_score):
        """Risk seviyesi belirleme"""
        if risk_score < 0.2:
            return 'Çok Düşük'
        elif risk_score < 0.4:
            return 'Düşük'
        elif risk_score < 0.6:
            return 'Orta'
        elif risk_score < 0.8:
            return 'Yüksek'
        else:
            return 'Çok Yüksek'
    
    def _get_seismic_risk_level(self, seismic_score):
        """Sismik risk seviyesi"""
        if seismic_score < 0.15:
            return 'Çok Düşük Sismik Risk'
        elif seismic_score < 0.35:
            return 'Düşük Sismik Risk'
        elif seismic_score < 0.55:
            return 'Orta Sismik Risk'
        elif seismic_score < 0.75:
            return 'Yüksek Sismik Risk'
        else:
            return 'Çok Yüksek Sismik Risk'

# =============================================================================
# GÖRSELLEŞTİRME
# =============================================================================

class PricingVisualization:
    """Fiyatlandırma görselleştirme"""
    
    def __init__(self, results_dir='results'):
        self.results_dir = results_dir
        import os
        os.makedirs(self.results_dir, exist_ok=True)
    
    def create_pricing_dashboard(self, buildings_df, risk_model):
        """Fiyatlandırma dashboard"""
        
        print("\n📊 Fiyatlandırma dashboard oluşturuluyor...")
        
        fig = plt.figure(figsize=(20, 12))
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
        
        fig.suptitle('DASK+ Yapay Zeka Destekli Dinamik Fiyatlandırma Analizi', 
                    fontsize=22, fontweight='bold')
        
        # 1. Paket Dağılımı
        ax1 = fig.add_subplot(gs[0, 0])
        package_counts = buildings_df['package_type'].value_counts()
        colors = ['#3498db', '#2ecc71', '#f39c12']
        wedges, texts, autotexts = ax1.pie(
            package_counts.values,
            labels=package_counts.index,
            autopct='%1.1f%%',
            colors=colors,
            startangle=90,
            textprops={'fontsize': 11, 'weight': 'bold'}
        )
        ax1.set_title('Paket Dağılımı', fontsize=14, fontweight='bold')
        
        # 2. Risk Skoru Dağılımı
        ax2 = fig.add_subplot(gs[0, 1])
        ax2.hist(buildings_df['risk_score'], bins=30, color='#e74c3c', 
                alpha=0.7, edgecolor='black')
        ax2.axvline(buildings_df['risk_score'].mean(), color='blue', 
                   linestyle='--', linewidth=2, 
                   label=f'Ortalama: {buildings_df["risk_score"].mean():.3f}')
        ax2.set_xlabel('Risk Skoru', fontweight='bold')
        ax2.set_ylabel('Bina Sayısı', fontweight='bold')
        ax2.set_title('Risk Skoru Dağılımı', fontsize=14, fontweight='bold')
        ax2.legend()
        ax2.grid(alpha=0.3)
        
        # 3. Prim Dağılımı
        ax3 = fig.add_subplot(gs[0, 2])
        if 'annual_premium_tl' in buildings_df.columns:
            ax3.hist(buildings_df['annual_premium_tl'], bins=30, color='#2ecc71',
                    alpha=0.7, edgecolor='black')
            ax3.axvline(buildings_df['annual_premium_tl'].mean(), color='red',
                       linestyle='--', linewidth=2,
                       label=f'Ortalama: {buildings_df["annual_premium_tl"].mean():,.0f} TL')
            ax3.set_xlabel('Yıllık Prim (TL)', fontweight='bold')
            ax3.set_ylabel('Bina Sayısı', fontweight='bold')
            ax3.set_title('Prim Dağılımı', fontsize=14, fontweight='bold')
            ax3.legend()
            ax3.grid(alpha=0.3)
        
        # 4. Feature Importance
        ax4 = fig.add_subplot(gs[1, :2])
        if risk_model.feature_importance is not None:
            top_12 = risk_model.feature_importance.head(12)
            colors_fi = plt.cm.viridis(np.linspace(0.2, 0.9, len(top_12)))
            # YENİ: ensemble_importance kullan (importance yerine)
            importance_col = 'ensemble_importance' if 'ensemble_importance' in top_12.columns else 'importance'
            bars = ax4.barh(range(len(top_12)), top_12[importance_col],
                           color=colors_fi, alpha=0.85, edgecolor='black')
            ax4.set_yticks(range(len(top_12)))
            ax4.set_yticklabels(top_12['feature'], fontsize=10)
            ax4.set_xlabel('Importance Score', fontweight='bold')
            ax4.set_title('En Önemli Risk Faktörleri', fontsize=14, fontweight='bold')
            ax4.grid(axis='x', alpha=0.3)
            ax4.invert_yaxis()
        
        # 5. Model Performansı
        ax5 = fig.add_subplot(gs[1, 2])
        
        # Model metrikleri varsa göster
        if hasattr(risk_model, 'model_metrics') and risk_model.model_metrics:
            test_r2 = risk_model.model_metrics.get('test_r2_score', 0)
            test_mse = risk_model.model_metrics.get('test_mse', 0)
            metrics_names = ['MSE', 'R² Score']
            metrics_values = [test_mse, test_r2]
            colors_metrics = ['#e74c3c', '#2ecc71']
            bars = ax5.bar(metrics_names, metrics_values, color=colors_metrics,
                          alpha=0.8, edgecolor='black', width=0.6)
            ax5.set_title('Model Performansı', fontsize=14, fontweight='bold')
            ax5.set_ylabel('Değer', fontweight='bold')
            ax5.grid(axis='y', alpha=0.3)
            for bar, val in zip(bars, metrics_values):
                height = bar.get_height()
                ax5.text(bar.get_x() + bar.get_width()/2., height,
                        f'{val:.4f}', ha='center', va='bottom', fontweight='bold')
        else:
            ax5.text(0.5, 0.5, 'Model metrikleri\nmevcut değil', 
                    ha='center', va='center', fontsize=12, transform=ax5.transAxes)
            ax5.axis('off')
        
        # 6. Şehir Bazlı Ortalama Risk
        ax6 = fig.add_subplot(gs[2, 0])
        city_risk = buildings_df.groupby('city')['risk_score'].mean().sort_values()
        bars = ax6.barh(range(len(city_risk)), city_risk.values,
                       color=plt.cm.Reds(np.linspace(0.3, 0.9, len(city_risk))))
        ax6.set_yticks(range(len(city_risk)))
        ax6.set_yticklabels(city_risk.index)
        ax6.set_xlabel('Ortalama Risk Skoru', fontweight='bold')
        ax6.set_title('Şehir Bazlı Risk', fontsize=14, fontweight='bold')
        ax6.grid(axis='x', alpha=0.3)
        
        # 7. Bina Yaşı vs Risk (KONTROL EDİLMİŞ)
        ax7 = fig.add_subplot(gs[2, 1])
        
        # Building age kontrolü - yoksa construction_year'dan hesapla
        if 'building_age' not in buildings_df.columns and 'construction_year' in buildings_df.columns:
            import datetime
            current_year = datetime.datetime.now().year
            buildings_df['building_age'] = current_year - buildings_df['construction_year']
        
        if 'building_age' in buildings_df.columns and 'risk_score' in buildings_df.columns:
            sample = buildings_df.sample(min(1000, len(buildings_df)))
            scatter = ax7.scatter(sample['building_age'], sample['risk_score'],
                                c=sample['risk_score'], cmap='RdYlGn_r',
                                alpha=0.6, s=40, edgecolors='black', linewidth=0.5)
            ax7.set_xlabel('Bina Yaşı (Yıl)', fontweight='bold')
            ax7.set_ylabel('Risk Skoru', fontweight='bold')
            ax7.set_title('Bina Yaşı vs Risk', fontsize=14, fontweight='bold')
            ax7.grid(alpha=0.3)
            plt.colorbar(scatter, ax=ax7, label='Risk Skoru')
        else:
            ax7.text(0.5, 0.5, 'Veri Eksik', ha='center', va='center', fontsize=16)
            ax7.axis('off')
        
        # 8. İstatistikler
        ax8 = fig.add_subplot(gs[2, 2])
        ax8.axis('off')
        
        total_buildings = len(buildings_df)
        total_premium = buildings_df.get('annual_premium_tl', pd.Series([0])).sum()
        avg_premium = buildings_df.get('annual_premium_tl', pd.Series([0])).mean()
        total_coverage = buildings_df['max_coverage'].sum()
        avg_risk = buildings_df['risk_score'].mean()
        
        stats_text = f"""
        GENEL İSTATİSTİKLER
        ══════════════════════════
        
        Portföy Bilgileri:
        • Toplam Bina: {total_buildings:,}
        • Toplam Teminat: {total_coverage:,.0f} TL
        • Yıllık Prim Geliri: {total_premium:,.0f} TL
        • Ortalama Prim: {avg_premium:,.0f} TL/yıl
        
        Risk Profili:
        • Ortalama Risk Skoru: {avg_risk:.3f}
        • En Yüksek Risk: {buildings_df['risk_score'].max():.3f}
        • En Düşük Risk: {buildings_df['risk_score'].min():.3f}
        
        Paket Dağılımı:
        • Temel: {(buildings_df['package_type']=='temel').sum():,}
        • Standard: {(buildings_df['package_type']=='standard').sum():,}
        • Premium: {(buildings_df['package_type']=='premium').sum():,}
        """
        
        ax8.text(0.05, 0.5, stats_text, fontsize=11, verticalalignment='center',
                fontfamily='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
        
        plt.tight_layout()
        
        filename = f'{self.results_dir}/pricing_dashboard.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✅ Dashboard kaydedildi: {filename}")
        
        return filename

# =============================================================================
# ANA SİSTEM
# =============================================================================

class DASKPlusPricingSystem:
    """DASK+ Dinamik Fiyatlandırma Ana Sistemi"""
    
    def __init__(self):
        print("="*70)
        print("DASK+ YAPAY ZEKA DESTEKLİ DİNAMİK FİYATLANDIRMA SİSTEMİ")
        print("="*70)
        
        import os
        from pathlib import Path
        
        # Ana proje dizinine göre results klasörü
        SRC_DIR = Path(__file__).parent
        ROOT_DIR = SRC_DIR.parent
        self.results_dir = ROOT_DIR / 'results'
        os.makedirs(self.results_dir, exist_ok=True)
        
        self.data_loader = BuildingDataLoader()
        self.seismic_analyzer = RealEarthquakeDataAnalyzer()
        self.pricing_model = AIRiskPricingModel()
        self.visualization = PricingVisualization(results_dir=str(self.results_dir))
        
        self.buildings_df = None
        self.features_df = None
    
    def initialize_system(self):
        """Sistemi başlat"""
        
        print("\n1️⃣ Veri yükleniyor...")
        
        # Gerçek deprem verisini yükle
        self.seismic_analyzer.load_real_earthquake_data()
        self.seismic_analyzer.calculate_regional_seismic_density()
        
        # Bina verisi yükle (CSV'den) - Path otomatik ayarlanır
        self.buildings_df = self.data_loader.load_building_data()
        print(f"✅ {len(self.buildings_df):,} bina kaydı yüklendi")
        
        # Risk özelliklerini hazırla
        print("\n2️⃣ Risk özellikleri hazırlanıyor...")
        self.features_df = self.pricing_model.prepare_features(self.buildings_df)
        print(f"✅ {len(self.features_df):,} bina için risk özellikleri hazırlandı")
        
        # Seismik riski ekle
        print("\n3️⃣ Seismik risk skorları hesaplanıyor...")
        tqdm.pandas(desc="🌍 Seismik Risk", bar_format='{l_bar}{bar:30}| {n_fmt}/{total_fmt}', colour='blue', ncols=100)
        self.features_df['seismic_risk'] = self.features_df.progress_apply(
            lambda row: self.seismic_analyzer.get_location_seismic_risk(
                row['latitude'], row['longitude'], 
                distance_to_fault=row.get('distance_to_fault_km')
            ), axis=1
        )
        print("✅ Seismik risk skorları eklendi")
    
    def train_model(self):
        """Model eğit"""
        
        print("\n4️⃣ AI Risk Modeli eğitiliyor...")
        self.pricing_model.train_risk_model(self.features_df)
    
    def _calculate_single_premium(self, row_dict):
        """Tek bir bina için prim hesapla (multiprocessing için)"""
        try:
            pricing = self.pricing_model.calculate_dynamic_premium(
                row_dict,
                seismic_analyzer=self.seismic_analyzer
            )
            
            return {
                'building_id': row_dict['building_id'],
                'annual_premium_tl': pricing['annual_premium'],
                'monthly_premium_tl': pricing['monthly_premium'],
                'combined_risk_factor': pricing['combined_risk_factor'],
                'package_type_new': pricing['package_type'],
                'package_upgraded': pricing['package_upgraded'],
                'max_coverage_new': pricing['max_coverage'],
                'risk_level': pricing['risk_level'],
                'seismic_risk_level': pricing['seismic_risk_level']
            }
        except Exception as e:
            print(f"⚠️ Hata (building_id={row_dict.get('building_id')}): {e}")
            return None
    
    def calculate_all_premiums(self):
        """Tüm binalar için prim hesapla (Multiprocessing ile hızlandırılmış)"""
        
        print("\n5️⃣ Tüm binalar için dinamik prim hesaplanıyor...")
        
        # CPU sayısını al
        num_cores = cpu_count()
        print(f"   🚀 {num_cores} CPU core kullanılacak (Paralel işlem)")
        
        # DataFrame'i dict listesine çevir
        building_dicts = [row.to_dict() for _, row in self.features_df.iterrows()]
        
        # Multiprocessing ile paralel hesaplama
        premium_results = []
        chunk_size = max(1, len(building_dicts) // (num_cores * 4))  # Optimal chunk size
        
        with Pool(processes=num_cores) as pool:
            # imap_unordered kullanarak progress bar ile paralel işlem
            for result in tqdm(
                pool.imap_unordered(self._calculate_single_premium, building_dicts, chunksize=chunk_size),
                total=len(building_dicts),
                desc="💰 Prim Hesaplama",
                unit="bina",
                bar_format='{l_bar}{bar:30}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}] {rate_fmt}',
                colour='green',
                ncols=100
            ):
                if result is not None:
                    premium_results.append(result)
        
        premium_df = pd.DataFrame(premium_results)
        
        # Bina datasına ekle
        self.features_df = self.features_df.merge(
            premium_df,
            on='building_id',
            how='left',
            suffixes=('_old', '')
        )
        
        # Eski kolonları temizle
        cols_to_drop = [col for col in self.features_df.columns if col.endswith('_old')]
        self.features_df.drop(columns=cols_to_drop, inplace=True)
        
        print(f"✅ {len(premium_results):,} bina için prim hesaplandı")
        print(f"   Toplam Yıllık Prim: {self.features_df['annual_premium_tl'].sum():,.0f} TL")
        print(f"   Ortalama Yıllık Prim: {self.features_df['annual_premium_tl'].mean():,.0f} TL")
        print(f"   Min Prim: {self.features_df['annual_premium_tl'].min():,.0f} TL")
        print(f"   Max Prim: {self.features_df['annual_premium_tl'].max():,.0f} TL")
        print(f"   Ortalama Risk Faktörü: {self.features_df['combined_risk_factor'].mean():.2f}x")
        print(f"   Paket Yükseltme Sayısı: {self.features_df['package_upgraded'].sum():,}")
    
    def generate_reports(self):
        """Raporlar oluştur ve tüm sonuçları kaydet"""
        
        print("\n6️⃣ Görsel raporlar oluşturuluyor...")
        
        # Dashboard - pricing_model.features_df kullan (hata olursa devam et)
        try:
            if hasattr(self.pricing_model, 'features_df') and self.pricing_model.features_df is not None:
                self.visualization.create_pricing_dashboard(self.pricing_model.features_df, self.pricing_model)
                print("✅ Dashboard oluşturuldu")
        except Exception as e:
            print(f"⚠️ Dashboard oluşturulamadı: {e}")
            print("💡 Diğer raporlar oluşturuluyor...")
        
        # =========================================================================
        # 1. ANA SONUÇLAR CSV (Tüm Features + Prim Bilgileri)
        # =========================================================================
        if hasattr(self.pricing_model, 'features_df') and self.pricing_model.features_df is not None:
            output_file = f'{self.results_dir}/dynamic_pricing_results.csv'
            self.pricing_model.features_df.to_csv(output_file, index=False, encoding='utf-8-sig')
            print(f"✅ Fiyatlandırma sonuçları kaydedildi: {output_file}")
        
        # =========================================================================
        # 2. FEATURE IMPORTANCE (Detaylı)
        # =========================================================================
        if hasattr(self.pricing_model, 'feature_importance') and self.pricing_model.feature_importance is not None:
            importance_file = f'{self.results_dir}/feature_importance_detailed.csv'
            self.pricing_model.feature_importance.to_csv(importance_file, index=False, encoding='utf-8-sig')
            print(f"✅ Feature importance kaydedildi: {importance_file}")
        
        # =========================================================================
        # 3. MODEL METRİKLERİ (JSON)
        # =========================================================================
        if hasattr(self.pricing_model, 'model_metrics') and self.pricing_model.model_metrics is not None:
            import json
            metrics_file = f'{self.results_dir}/model_metrics.json'
            with open(metrics_file, 'w', encoding='utf-8') as f:
                json.dump(self.pricing_model.model_metrics, f, indent=2, ensure_ascii=False)
            print(f"✅ Model metrikleri kaydedildi: {metrics_file}")
        
        # Features DataFrame kontrolü
        features_df = self.pricing_model.features_df if hasattr(self.pricing_model, 'features_df') else None
        if features_df is None:
            print("⚠️ Features DataFrame bulunamadı, raporlar kısıtlı oluşturulacak")
            return
        
        print(f"📊 Features DataFrame: {len(features_df)} satır, {len(features_df.columns)} sütun")
        print(f"   Sütunlar: {', '.join(features_df.columns[:10])}..." if len(features_df.columns) > 10 else f"   Sütunlar: {', '.join(features_df.columns)}")
        
        # =========================================================================
        # 4. ÖZETLENMİŞ İSTATİSTİKLER (Özet Rapor)
        # =========================================================================
        summary_stats = {
            'Genel Bilgiler': {
                'Toplam Bina': len(features_df),
                'Aktif Poliçe': int(features_df[features_df['policy_status'] == 'active'].shape[0]) if 'policy_status' in features_df.columns else 0,
                'Şehir Sayısı': int(features_df['city'].nunique()) if 'city' in features_df.columns else 0,
                'İlçe Sayısı': int(features_df['district'].nunique() if 'district' in features_df.columns else 0),
            },
            'Finansal Özet': {
                'Toplam Yıllık Prim (TL)': float(features_df['annual_premium_tl'].sum()) if 'annual_premium_tl' in features_df.columns else 0,
                'Ortalama Yıllık Prim (TL)': float(features_df['annual_premium_tl'].mean()) if 'annual_premium_tl' in features_df.columns else 0,
                'Medyan Yıllık Prim (TL)': float(features_df['annual_premium_tl'].median()) if 'annual_premium_tl' in features_df.columns else 0,
                'Min Prim (TL)': float(features_df['annual_premium_tl'].min()) if 'annual_premium_tl' in features_df.columns else 0,
                'Max Prim (TL)': float(features_df['annual_premium_tl'].max()) if 'annual_premium_tl' in features_df.columns else 0,
                'Toplam Teminat (TL)': float(features_df['insurance_value_tl'].sum()) if 'insurance_value_tl' in features_df.columns else 0,
            },
            'Risk Analizi': {
                'Ortalama Risk Skoru': float(features_df['risk_score'].mean()) if 'risk_score' in features_df.columns else 0,
                'Medyan Risk Skoru': float(features_df['risk_score'].median()) if 'risk_score' in features_df.columns else 0,
                'Ortalama Risk Faktörü': float(features_df['combined_risk_factor'].mean()) if 'combined_risk_factor' in features_df.columns else 0,
                'Yüksek Risk Binalar (>0.7)': int((features_df['risk_score'] > 0.7).sum()) if 'risk_score' in features_df.columns else 0,
                'Düşük Risk Binalar (<0.3)': int((features_df['risk_score'] < 0.3).sum()) if 'risk_score' in features_df.columns else 0,
            },
            'Paket Dağılımı': {
                paket: int((features_df['package_type'] == paket).sum())
                for paket in features_df['package_type'].unique()
            } if 'package_type' in features_df.columns else {},
            'Paket Yükseltme': {
                'Toplam Yükseltme': int(features_df['package_upgraded'].sum()) if 'package_upgraded' in features_df.columns else 0,
                'Yükseltme Oranı (%)': float((features_df['package_upgraded'].sum() / len(features_df)) * 100) if 'package_upgraded' in features_df.columns else 0,
            },
            'Model Performansı': self.pricing_model.model_metrics if hasattr(self.pricing_model, 'model_metrics') else {},
            'Feature Count': len(self.pricing_model.risk_model['feature_cols']) if hasattr(self.pricing_model, 'risk_model') else 0
        }
        
        summary_file = f'{self.results_dir}/summary_statistics.json'
        import json
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_stats, f, indent=2, ensure_ascii=False)
        print(f"✅ Özet istatistikler kaydedildi: {summary_file}")
        
        # =========================================================================
        # 5. PAKET BAZINDA DETAYLI ANALİZ
        # =========================================================================
        if 'package_type' in features_df.columns:
            package_analysis = features_df.groupby('package_type').agg({
                'building_id': 'count',
                'annual_premium_tl': ['mean', 'median', 'min', 'max', 'sum'],
                'risk_score': ['mean', 'median'],
                'insurance_value_tl': ['mean', 'sum'],
                'combined_risk_factor': 'mean',
                'package_upgraded': 'sum'
            }).round(2)
            
            package_analysis.columns = ['_'.join(col).strip() for col in package_analysis.columns.values]
            package_file = f'{self.results_dir}/package_analysis.csv'
            package_analysis.to_csv(package_file, encoding='utf-8-sig')
            print(f"✅ Paket analizi kaydedildi: {package_file}")
        
        # =========================================================================
        # 6. ŞEHİR/İLÇE BAZINDA ANALİZ
        # =========================================================================
        if 'district' in features_df.columns:
            district_analysis = features_df.groupby(['city', 'district']).agg({
                'building_id': 'count',
                'annual_premium_tl': 'mean',
                'risk_score': 'mean',
                'district_risk_factor': 'first',
                'soil_risk_factor': 'mean',
                'fault_combined_risk': 'mean',
            }).round(4)
            
            district_analysis.columns = ['Bina_Sayisi', 'Ort_Prim_TL', 'Ort_Risk_Skoru', 
                                         'District_Risk', 'Ort_Soil_Risk', 'Ort_Fault_Risk']
            district_file = f'{self.results_dir}/district_risk_analysis.csv'
            district_analysis.to_csv(district_file, encoding='utf-8-sig')
            print(f"✅ İlçe bazlı analiz kaydedildi: {district_file}")
        
        # =========================================================================
        # 7. YAPI TİPİ ANALİZİ
        # =========================================================================
        if 'structure_type' in features_df.columns:
            structure_analysis = features_df.groupby('structure_type').agg({
                'building_id': 'count',
                'annual_premium_tl': 'mean',
                'risk_score': 'mean',
                'building_age': 'mean',
                'damage_factor': 'first',
                'quality_score': 'mean',
            }).round(2)
        
        structure_analysis.columns = ['Bina_Sayisi', 'Ort_Prim_TL', 'Ort_Risk_Skoru', 
                                      'Ort_Bina_Yasi', 'Damage_Factor', 'Ort_Kalite']
        structure_file = f'{self.results_dir}/structure_type_analysis.csv'
        structure_analysis.to_csv(structure_file, encoding='utf-8-sig')
        print(f"✅ Yapı tipi analizi kaydedildi: {structure_file}")
        
        # =========================================================================
        # 8. PARAMETRE İSTATİSTİKLERİ
        # =========================================================================
        params_list = [
            'composite_risk_index', 'district_risk_factor', 'building_complexity_score',
            'fault_combined_risk', 'soil_risk_factor', 'proximity_risk_factor',
            'distance_to_city_center_km', 'structure_age_interaction', 'mixed_use_factor',
            'fault_type_risk_factor', 'customer_reliability_factor', 'neighborhood_density_factor'
        ]
        
        params_analysis = pd.DataFrame({
            'Parametre': params_list,
            'Ortalama': [
                features_df[col].mean() if col in features_df.columns else 0
                for col in params_list
            ],
            'Std': [
                features_df[col].std() if col in features_df.columns else 0
                for col in params_list
            ],
            'Min': [
                features_df[col].min() if col in features_df.columns else 0
                for col in params_list
            ],
            'Max': [
                features_df[col].max() if col in features_df.columns else 0
                for col in params_list
            ]
        }).round(4)
        
        params_file = f'{self.results_dir}/parameters_statistics.csv'
        params_analysis.to_csv(params_file, index=False, encoding='utf-8-sig')
        print(f"✅ Parametre istatistikleri kaydedildi: {params_file}")
        
        # =========================================================================
        # 9. ÖZET RAPOR (TXT - İnsan Okunabilir)
        # =========================================================================
        report_file = f'{self.results_dir}/PRICING_REPORT.txt'
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("DASK+ PARAMETRİK SİGORTA - FİYATLANDIRMA RAPORU\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"Rapor Tarihi: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Sistem Versiyonu: 2.0 (Enhanced Features)\n\n")
            
            f.write("1. GENEL BİLGİLER\n")
            f.write("-" * 80 + "\n")
            f.write(f"Toplam Bina: {len(features_df):,}\n")
            f.write(f"Aktif Poliçe: {(features_df['policy_status'] == 'active').sum() if 'policy_status' in features_df.columns else 'N/A':,}\n")
            f.write(f"Şehir Sayısı: {features_df['city'].nunique() if 'city' in features_df.columns else 'N/A'}\n")
            f.write(f"İlçe Sayısı: {features_df['district'].nunique() if 'district' in features_df.columns else 'N/A'}\n\n")
            
            f.write("2. FİNANSAL ÖZET\n")
            f.write("-" * 80 + "\n")
            if 'annual_premium_tl' in features_df.columns:
                f.write(f"Toplam Yıllık Prim: {features_df['annual_premium_tl'].sum():,.2f} TL\n")
                f.write(f"Ortalama Yıllık Prim: {features_df['annual_premium_tl'].mean():,.2f} TL\n")
                f.write(f"Medyan Yıllık Prim: {features_df['annual_premium_tl'].median():,.2f} TL\n")
                f.write(f"Min Prim: {features_df['annual_premium_tl'].min():,.2f} TL\n")
                f.write(f"Max Prim: {features_df['annual_premium_tl'].max():,.2f} TL\n")
            if 'insurance_value_tl' in features_df.columns:
                f.write(f"Toplam Teminat: {features_df['insurance_value_tl'].sum():,.2f} TL\n\n")
            
            f.write("3. RİSK ANALİZİ\n")
            f.write("-" * 80 + "\n")
            if 'risk_score' in features_df.columns:
                f.write(f"Ortalama Risk Skoru: {features_df['risk_score'].mean():.4f}\n")
                f.write(f"Yüksek Risk Binalar (>0.7): {(features_df['risk_score'] > 0.7).sum():,}\n")
                f.write(f"Düşük Risk Binalar (<0.3): {(features_df['risk_score'] < 0.3).sum():,}\n")
            if 'combined_risk_factor' in features_df.columns:
                f.write(f"Ortalama Risk Faktörü: {features_df['combined_risk_factor'].mean():.2f}x\n\n")
            
            f.write("4. PAKET DAĞILIMI\n")
            f.write("-" * 80 + "\n")
            if 'package_type' in features_df.columns:
                for paket, count in features_df['package_type'].value_counts().items():
                    pct = (count / len(features_df)) * 100
                    f.write(f"{paket.upper()}: {count:,} bina ({pct:.1f}%)\n")
                if 'package_upgraded' in features_df.columns:
                    f.write(f"\nPaket Yükseltme: {features_df['package_upgraded'].sum():,} bina\n\n")
            
            f.write("5. MODEL PERFORMANSI\n")
            f.write("-" * 80 + "\n")
            if hasattr(self.pricing_model, 'model_metrics') and self.pricing_model.model_metrics:
                metrics = self.pricing_model.model_metrics
                f.write(f"R² Score: {metrics.get('test_r2_score', metrics.get('r2_score', 'N/A'))}\n")
                f.write(f"MAE: {metrics.get('test_mae', metrics.get('mae', 'N/A'))}\n")
                f.write(f"RMSE: {metrics.get('test_rmse', metrics.get('rmse', 'N/A'))}\n")
                f.write(f"Feature Count: {metrics.get('features_count', 'N/A')}\n")
                f.write(f"Eğitim Örnekleri: {metrics.get('training_samples', 'N/A')}\n")
                f.write(f"Test Örnekleri: {metrics.get('test_samples', 'N/A')}\n\n")
            
            f.write("6. YENİ PARAMETRELER (12 ADET)\n")
            f.write("-" * 80 + "\n")
            f.write("✅ composite_risk_index - Multi-dimensional ensemble risk\n")
            f.write("✅ district_risk_factor - İlçe bazlı risk haritası\n")
            f.write("✅ building_complexity_score - Yapı kompleksliği\n")
            f.write("✅ fault_combined_risk - Fay tipi × mesafe\n")
            f.write("✅ soil_risk_factor - Zemin sınıfı riski\n")
            f.write("✅ proximity_risk_factor - Merkeze yakınlık\n")
            f.write("✅ distance_to_city_center_km - Geodesic mesafe\n")
            f.write("✅ structure_age_interaction - Yapı × yaş sinerjisi\n")
            f.write("✅ mixed_use_factor - Karma kullanım\n")
            f.write("✅ fault_type_risk_factor - Fay hattı tipi\n")
            f.write("✅ customer_reliability_factor - Müşteri güvenilirlik\n")
            f.write("✅ neighborhood_density_factor - Mahalle yoğunluğu\n\n")
            
            f.write("="*80 + "\n")
            f.write("✅ RAPOR TAMAMLANDI\n")
            f.write("="*80 + "\n")
        
        print(f"✅ Özet rapor kaydedildi: {report_file}")
        
        print(f"\n📁 Tüm sonuçlar '{self.results_dir}' klasörüne kaydedildi:")
        print(f"   • dynamic_pricing_results.csv (Ana sonuçlar)")
        print(f"   • feature_importance_detailed.csv (Feature önem sıralaması)")
        print(f"   • model_metrics.json (Model performans metrikleri)")
        print(f"   • summary_statistics.json (Özet istatistikler)")
        print(f"   • package_analysis.csv (Paket bazlı analiz)")
        print(f"   • district_risk_analysis.csv (İlçe bazlı risk)")
        print(f"   • structure_type_analysis.csv (Yapı tipi analizi)")
        print(f"   • parameters_statistics.csv (Parametre istatistikleri)")
        print(f"   • PRICING_REPORT.txt (İnsan okunabilir özet)")
        print(f"   • pricing_dashboard.png (Görsel dashboard)")

    
    def run_full_cycle(self):
        """Tüm sistem döngüsünü çalıştır"""
        
        self.initialize_system()
        self.train_model()
        self.calculate_all_premiums()
        self.generate_reports()
        
        print("\n" + "="*70)
        print("✅ SİSTEM BAŞARIYLA TAMAMLANDI!")
        print("="*70)


if __name__ == "__main__":
    system = DASKPlusPricingSystem()
    system.run_full_cycle()
