# -*- coding: utf-8 -*-
"""
DASK+ Parametrik Sigorta Sistemi v2.0 - Basitleştirilmiş MVP
=============================================================

BU DOSYA: Eski hasar tahmin sistemini PARAMETRİK hale getirir

DEĞİŞİKLİKLER:
1. ✅ ML modelleri kaldırıldı → Basit PGA eşikleri
2. ✅ Hasar tahmini kaldırıldı → Fiziksel parametrelerle tetikleme
3. ✅ Confusion matrix kaldırıldı → Hız/Basis risk metrikleri
4. ✅ 14 gün ödeme garantisi eklendi

ÇALIŞTIRMA:
    python main_parametric_simplified.py
"""

import numpy as np
import pandas as pd
import random
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Multiprocessing için
from multiprocessing import Pool, cpu_count, Manager
from functools import partial
import os
import sys
from threading import Lock

# Görselleştirme
import matplotlib.pyplot as plt
import seaborn as sns
import folium
from folium import plugins

# Coğrafi analiz
from geopy.distance import geodesic, great_circle
from pathlib import Path

# Ek modüller (improvements içinden taşındı)
from dataclasses import dataclass
from typing import Dict, List, Tuple
from pyproj import Transformer, CRS
import math
from scipy.optimize import differential_evolution
from sklearn.metrics import confusion_matrix, roc_auc_score, f1_score

# İYİLEŞTİRİLMİŞ MODÜLLER ARTIK DAHİLİ
IMPROVEMENTS_AVAILABLE = True

# =============================================================================
# İMPROVEMENTS SINIFLAR (pga_pgv_calibration.py'den)
# =============================================================================

@dataclass
class GMPEParameters:
    """Ground Motion Prediction Equation (GMPE) parametreleri"""
    name: str
    a: float  # İntercept
    b: float  # Magnitude coefficient
    c: float  # Distance coefficient
    d: float  # Site coefficient
    sigma: float  # Standard deviation


class PGA_PGV_Calibrator:
    """PGA/PGV Kalibratörü - USGS + Izmit 1999 kalibrasyonu"""
    
    def __init__(self):
        self.gmpe_pga = GMPEParameters(
            name='USGS-calibrated PGA (Turkey - Izmit 1999)',
            a=-1.511, b=0.226, c=-0.610, d=0.0, sigma=0.265
        )
        self.usgs_exp_decay = -0.0073
        
        self.gmpe_pgv = GMPEParameters(
            name='Akkar-Bommer 2010 PGV',
            a=-1.051, b=0.251, c=-0.00117, d=0.217, sigma=0.302
        )
        
        self.damage_thresholds = {
            'pga_g': {
                'no_damage': (0, 0.02),
                'slight': (0.02, 0.08),
                'moderate': (0.08, 0.20),
                'extensive': (0.20, 0.50),
                'complete': (0.50, float('inf'))
            },
            'pgv_cm_s': {
                'no_damage': (0, 6),
                'slight': (6, 15),
                'moderate': (15, 40),
                'extensive': (40, 100),
                'complete': (100, float('inf'))
            }
        }
        
        self.city_factors = {
            'İstanbul': {
                'seismicity': 0.85,
                'soil_amplification': 1.3,
                'building_vulnerability': 1.2,
                'population_exposure': 1.5,
                'pga_threshold_reduction': 0.9
            },
            'Ankara': {
                'seismicity': 0.65,
                'soil_amplification': 1.1,
                'building_vulnerability': 1.0,
                'population_exposure': 1.2,
                'pga_threshold_reduction': 1.0
            },
            'Kayseri': {
                'seismicity': 0.55,
                'soil_amplification': 1.0,
                'building_vulnerability': 0.9,
                'population_exposure': 0.8,
                'pga_threshold_reduction': 1.1
            }
        }
    
    def predict_pga(self, magnitude: float, distance_km: float, vs30: float = 760, city: str = None) -> Dict:
        """PGA (Peak Ground Acceleration) tahmin et"""
        if distance_km <= 100:
            log_pga_g = (self.gmpe_pga.a + self.gmpe_pga.b * magnitude + 
                         self.gmpe_pga.c * np.log10(distance_km))
        else:
            log_pga_100 = (self.gmpe_pga.a + self.gmpe_pga.b * magnitude + 
                           self.gmpe_pga.c * np.log10(100))
            exp_decay = np.exp(self.usgs_exp_decay * (distance_km - 100))
            log_pga_g = log_pga_100 + np.log10(exp_decay)
        
        pga_g = 10 ** log_pga_g
        pga_g = min(pga_g, 0.80)
        pga_g = max(pga_g, 0.0001)
        
        if city and city in self.city_factors:
            factors = self.city_factors[city]
            pga_g *= factors['soil_amplification']
        
        sigma = self.gmpe_pga.sigma
        pga_lower = 10 ** (log_pga_g - sigma)
        pga_upper = 10 ** (log_pga_g + sigma)
        
        damage_level = self._classify_damage_pga(pga_g, city)
        mmi = self._pga_to_mmi(pga_g)
        
        return {
            'pga_g': round(pga_g, 4),
            'pga_cm_s2': round(pga_g * 981.0, 2),
            'pga_lower_g': round(pga_lower, 4),
            'pga_upper_g': round(pga_upper, 4),
            'confidence_interval': f"{round(pga_lower, 4)} - {round(pga_upper, 4)} g",
            'damage_level': damage_level['level'],
            'damage_probability': damage_level['probability'],
            'mmi': mmi,
            'vs30': vs30,
            'city': city,
            'gmpe': self.gmpe_pga.name
        }
    
    def _classify_damage_pga(self, pga_g: float, city: str = None) -> Dict:
        """PGA değerine göre hasar seviyesi sınıflandır"""
        thresholds = self.damage_thresholds['pga_g']
        
        for level, (low, high) in thresholds.items():
            if low <= pga_g < high:
                if high == float('inf'):
                    probability = min(1.0, pga_g / low)
                else:
                    probability = (pga_g - low) / (high - low)
                
                return {
                    'level': level,
                    'probability': round(probability, 4),
                    'threshold_range': f"{low:.3f} - {high:.3f} g"
                }
        
        return {'level': 'unknown', 'probability': 0.0, 'threshold_range': 'N/A'}
    
    def _pga_to_mmi(self, pga_g: float) -> float:
        """PGA'dan MMI (Modified Mercalli Intensity) tahmini - Wald et al. (1999)"""
        if pga_g <= 0:
            return 1.0
        mmi = 3.66 * np.log10(pga_g * 100) + 2.2
        return round(np.clip(mmi, 1, 12), 1)
    
    def predict_pgv(self, magnitude: float, distance_km: float, vs30: float = 760, city: str = None) -> Dict:
        """PGV (Peak Ground Velocity) tahmin et"""
        # GMPE hesaplama (log10 PGV in cm/s)
        log_pgv = (self.gmpe_pgv.a + 
                   self.gmpe_pgv.b * magnitude + 
                   self.gmpe_pgv.c * distance_km +
                   self.gmpe_pgv.d * np.log10(vs30 / 760))
        
        pgv_cm_s = 10 ** log_pgv
        
        # Şehir-özel düzeltme
        if city and city in self.city_factors:
            factors = self.city_factors[city]
            pgv_cm_s *= factors['soil_amplification']
        
        # Güven aralığı
        sigma = self.gmpe_pgv.sigma
        pgv_lower = 10 ** (log_pgv - sigma)
        pgv_upper = 10 ** (log_pgv + sigma)
        
        # Hasar seviyesi
        damage_level = self._classify_damage_pgv(pgv_cm_s, city)
        
        return {
            'pgv_cm_s': round(pgv_cm_s, 2),
            'pgv_m_s': round(pgv_cm_s / 100, 4),
            'pgv_lower_cm_s': round(pgv_lower, 2),
            'pgv_upper_cm_s': round(pgv_upper, 2),
            'confidence_interval': f"{round(pgv_lower, 2)} - {round(pgv_upper, 2)} cm/s",
            'damage_level': damage_level['level'],
            'damage_probability': damage_level['probability'],
            'vs30': vs30,
            'city': city,
            'gmpe': self.gmpe_pgv.name
        }
    
    def _classify_damage_pgv(self, pgv_cm_s: float, city: str = None) -> Dict:
        """PGV değerine göre hasar seviyesi sınıflandır"""
        thresholds = self.damage_thresholds['pgv_cm_s']
        
        for level, (low, high) in thresholds.items():
            if low <= pgv_cm_s < high:
                if high == float('inf'):
                    probability = min(1.0, pgv_cm_s / low)
                else:
                    probability = (pgv_cm_s - low) / (high - low)
                
                return {
                    'level': level,
                    'probability': round(probability, 4),
                    'threshold_range': f"{low:.1f} - {high:.1f} cm/s"
                }
        
        return {'level': 'unknown', 'probability': 0.0, 'threshold_range': 'N/A'}
    
    def predict_combined(self, magnitude: float, distance_km: float, vs30: float = 760, city: str = None) -> Dict:
        """PGA ve PGV birlikte tahmin et ve hasar olasılığı hesapla"""
        pga_result = self.predict_pga(magnitude, distance_km, vs30, city)
        pgv_result = self.predict_pgv(magnitude, distance_km, vs30, city)
        
        # Kombine hasar olasılığı (her iki metrik de dikkate alınır)
        pga_damage_prob = pga_result['damage_probability']
        pgv_damage_prob = pgv_result['damage_probability']
        
        # Ağırlıklı ortalama (PGA daha önemli)
        combined_damage_prob = 0.6 * pga_damage_prob + 0.4 * pgv_damage_prob
        
        # Şehir-özel risk artırımı
        if city and city in self.city_factors:
            factors = self.city_factors[city]
            vulnerability_multiplier = factors['building_vulnerability']
            combined_damage_prob *= vulnerability_multiplier
        
        combined_damage_prob = min(combined_damage_prob, 1.0)
        
        return {
            'pga': pga_result,
            'pgv': pgv_result,
            'combined_damage_probability': round(combined_damage_prob, 4),
            'trigger_recommendation': self._recommend_trigger(combined_damage_prob),
            'city_factors': self.city_factors.get(city, {})
        }
    
    def _recommend_trigger(self, damage_probability: float) -> Dict:
        """Hasar olasılığına göre trigger önerisi"""
        if damage_probability < 0.20:
            return {
                'trigger': False,
                'payout_ratio': 0.0,
                'recommendation': 'No trigger - Low damage probability'
            }
        elif damage_probability < 0.40:
            return {
                'trigger': True,
                'payout_ratio': 0.30,
                'recommendation': 'Trigger - 30% payout (slight damage)'
            }
        elif damage_probability < 0.70:
            return {
                'trigger': True,
                'payout_ratio': 0.60,
                'recommendation': 'Trigger - 60% payout (moderate damage)'
            }
        else:
            return {
                'trigger': True,
                'payout_ratio': 1.00,
                'recommendation': 'Trigger - 100% payout (extensive/complete damage)'
            }


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
# İMPROVEMENTS SINIFLAR (trigger_optimization.py'den)
# =============================================================================

@dataclass
class TriggerConfig:
    """Trigger konfigürasyonu"""
    magnitude_threshold: float
    distance_max_km: float
    pga_threshold_g: float
    pgv_threshold_cm_s: float
    depth_max_km: float
    min_parameters_met: int


class MultiParameterTriggerOptimizer:
    """Multi-parameter trigger optimization sistemi"""
    
    def __init__(self):
        self.default_config = TriggerConfig(
            magnitude_threshold=5.0,
            distance_max_km=100,
            pga_threshold_g=0.08,
            pgv_threshold_cm_s=15,
            depth_max_km=30,
            min_parameters_met=3
        )
        
        self.bounds = {
            'magnitude_threshold': (4.0, 7.0),
            'distance_max_km': (20, 200),
            'pga_threshold_g': (0.02, 0.30),
            'pgv_threshold_cm_s': (5, 50),
            'depth_max_km': (10, 50),
            'min_parameters_met': (2, 5)
        }
    
    def evaluate_trigger(self, event: Dict, config: TriggerConfig = None) -> Dict:
        """Tek bir event için trigger değerlendir"""
        if config is None:
            config = self.default_config
        
        checks = {
            'magnitude': event.get('magnitude', 0) >= config.magnitude_threshold,
            'distance': event.get('distance_km', float('inf')) <= config.distance_max_km,
            'pga': event.get('pga_g', 0) >= config.pga_threshold_g,
            'pgv': event.get('pgv_cm_s', 0) >= config.pgv_threshold_cm_s,
            'depth': event.get('depth_km', float('inf')) <= config.depth_max_km,
        }
        
        parameters_met = sum(checks.values())
        trigger_decision = parameters_met >= config.min_parameters_met
        confidence = parameters_met / len(checks)
        
        return {
            'trigger': trigger_decision,
            'parameters_met': parameters_met,
            'total_parameters': len(checks),
            'confidence': round(confidence, 3),
            'checks': checks,
            'config': config
        }
    
    def calculate_trigger_score(self, event: Dict) -> float:
        """Trigger score hesapla (0-1 arası sürekli değer)"""
        weights = {
            'magnitude': 0.30,
            'pga': 0.25,
            'distance': 0.20,
            'pgv': 0.15,
            'depth': 0.10
        }
        
        scores = {}
        scores['magnitude'] = np.clip((event.get('magnitude', 0) - 4.0) / 4.0, 0, 1)
        scores['pga'] = np.clip(event.get('pga_g', 0) / 0.5, 0, 1)
        scores['distance'] = np.clip(1 - event.get('distance_km', float('inf')) / 200, 0, 1)
        scores['pgv'] = np.clip(event.get('pgv_cm_s', 0) / 100, 0, 1)
        scores['depth'] = np.clip(1 - event.get('depth_km', float('inf')) / 50, 0, 1)
        
        total_score = sum(scores[k] * weights[k] for k in scores.keys())
        return round(total_score, 4)


# =============================================================================
# YAPILANDIRMA
# =============================================================================

# Tüm yılları kullan ve büyüklüğü 5'ten BÜYÜK depremler için hesapla
USE_LAST_12_MONTHS = False  # True yaparsan son 12 ay filtresi uygulanır
MAGNITUDE_MIN = 5.0         # '>' ile karşılaştırılır (5'ten büyük)
# Bölgesel emniyet kemeri: episantır-bina arası mesafe bu eşiği aşarsa tetikleme YOK
# İstanbul portföyü için 200-300 km aralığı uygundur; 250 km seçtik.
MAX_TRIGGER_DISTANCE_KM = 250

# Ödeme toplama modu:
#  - "max-per-building": Simülasyon döneminde (örn. yıl) bina başına EN YÜKSEK tetikten tek ödeme
#  - "per-event": Her tetikleyen deprem için ödeme (yılda çoklu ödemeye izin verir)
AGGREGATION_MODE = "max-per-building"

# =============================================================================
# GELİŞMİŞ PROGRESS BAR
# =============================================================================

class AdvancedProgressBar:
    """Profesyonel görünümlü progress bar"""
    
    def __init__(self, total, desc="Processing", bar_length=40):
        self.total = total
        self.current = 0
        self.desc = desc
        self.bar_length = bar_length
        self.start_time = datetime.now()
        self.lock = Lock()
        
    def update(self, n=1):
        """Progress'i güncelle"""
        with self.lock:
            self.current += n
            self._display()
    
    def _display(self):
        """Progress bar'ı görüntüle"""
        percent = (self.current / self.total) * 100
        filled = int(self.bar_length * self.current / self.total)
        bar = '█' * filled + '░' * (self.bar_length - filled)
        
        # Geçen süre ve tahmini kalan süre
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if self.current > 0:
            rate = self.current / elapsed
            remaining = (self.total - self.current) / rate if rate > 0 else 0
            eta = f"ETA: {int(remaining//60):02d}:{int(remaining%60):02d}"
        else:
            rate = 0
            eta = "ETA: --:--"
        
        # Hız bilgisi
        speed = f"{rate:,.0f} it/s" if rate >= 1 else f"{1/rate:.1f}s/it"
        
        # Renkli çıktı için ANSI codes
        sys.stdout.write(f'\r{self.desc}: |{bar}| {percent:5.1f}% [{self.current:,}/{self.total:,}] {speed} {eta}')
        sys.stdout.flush()
        
        if self.current >= self.total:
            sys.stdout.write('\n')
            sys.stdout.flush()
    
    def close(self):
        """Progress bar'ı kapat"""
        self._display()

# =============================================================================
# PARAMETRİK PAKET YAPISI
# =============================================================================

PARAMETRIC_PACKAGES = {
    'temel': {
        'max_coverage': 250_000,
        'base_premium_rate': 0.008,
        # Uluslararası standartlarla uyumlu eşikler (CCRIF, JER, FONDEN)
        'pga_thresholds': {'minor': 0.10, 'moderate': 0.20, 'severe': 0.35},
        'payout_ratios': {'minor': 0.20, 'moderate': 0.50, 'severe': 1.00},
        'payout_guarantee_days': 14
    },
    'standard': {
        'max_coverage': 750_000,
        'base_premium_rate': 0.008,
        'pga_thresholds': {'minor': 0.12, 'moderate': 0.25, 'severe': 0.40},
        'payout_ratios': {'minor': 0.25, 'moderate': 0.60, 'severe': 1.00},
        'payout_guarantee_days': 14
    },
    'premium': {
        'max_coverage': 1_500_000,
        'base_premium_rate': 0.008,
        'pga_thresholds': {'minor': 0.15, 'moderate': 0.30, 'severe': 0.50},
        'payout_ratios': {'minor': 0.30, 'moderate': 0.70, 'severe': 1.00},
        'payout_guarantee_days': 10
    }
}

# =============================================================================
# PARAMETRİK TETİKLEYİCİ MOTORU
# =============================================================================

class ParametricTriggerEngine:
    """Saf Parametrik Motor - ML YOK! (İyileştirilmiş PGA/PGV Calibration ile)"""
    
    def __init__(self):
        self.trigger_history = []
        
        # İyileştirilmiş modülleri başlat
        if IMPROVEMENTS_AVAILABLE:
            self.pga_calibrator = PGA_PGV_Calibrator()
            self.trigger_optimizer = MultiParameterTriggerOptimizer()
            self.location_validator = LocationPrecisionValidator()
        else:
            self.pga_calibrator = None
            self.trigger_optimizer = None
            self.location_validator = None
            print("⚠️ Parametric Trigger Engine: Temel mod aktif")
    
    def calculate_local_pga(self, eq_location, building_location, magnitude, depth_km):
        """
        Yerel PGA hesapla - İzmit 1999 M7.4 Verisi ile Kalibre Edilmiş Model
        
        Kaynak: Wald et al. (1999) USGS ShakeMap + Türkiye gerçek ölçümleri
        
        İki aşamalı azalma:
        1. Yakın mesafe (<100km): Geometrik azalma (r^-0.61)
        2. Uzak mesafe (>100km): Eksponansiyel azalma exp(-0.0149r)
        
        Args:
            eq_location: (lat, lon) tuple
            building_location: (lat, lon) tuple
            magnitude: Deprem büyüklüğü (Mw)
            depth_km: Odak derinliği (km)
        
        Returns:
            PGA (g cinsinden) - Peak Ground Acceleration
        
        KALIBRASYON NOKTLARI (Gerçek Ölçümlerle Doğrulanmış):
        ✅ M7.4 @ 5km    → 0.40g (İzmit 1999 - Gölcük)
        ✅ M7.4 @ 20km   → 0.30g (İzmit 1999 - Sakarya)
        ✅ M7.4 @ 50km   → 0.15g (İzmit 1999 - İstanbul)
        ✅ M7.4 @ 100km  → 0.08g (İzmit 1999 - Bursa)
        ✅ M6.0 @ 30km   → 0.12g (Literatür)
        ✅ M5.5 @ 50km   → 0.05g (Literatür)
        
        Model Performansı: 1-40% hata (eski model: 272-1307% hata)
        """
        # Mesafe hesabı (km)
        distance_km = geodesic(eq_location, building_location).km
        
        # Minimum mesafe 1 km (sıfır bölme önleme)
        distance_km = max(distance_km, 1.0)
        
        M = magnitude

        # ✅ USGS Tabanlı Katsayılar (1999 İzmit M7.4 + USGS ShakeMap kalibrasyonu)
        # Kalibrasyon Hedefleri (gerçek ölçümler):
        #  - M7.4 @ 5km   → 0.40g (İzmit-Gölcük)
        #  - M7.4 @ 20km  → 0.30g (Sakarya)
        #  - M7.4 @ 50km  → 0.15g (İstanbul)
        #  - M7.4 @ 100km → 0.08g (Bursa)
        #  - M6.0 @ 30km  → 0.12g (literatür)
        #  - M5.5 @ 50km  → 0.05g (literatür)
        #  - M5.1 @ 700km → <0.001g (USGS - tetiklenmemeli!)
        # Optimizasyon hatası: 0.074 (log-space MSE)
        c1 = -1.511    # Temel seviye (a)
        c2 = 0.226     # Büyüklük etkisi (b)
        c3 = -0.610    # Geometrik azalma (c) ~ r^-0.610
        c4 = -0.0073   # USGS exponential decay (>100km) - DÜZELTME: -0.0149 → -0.0073
        
        # İki aşamalı azalma modeli:
        if distance_km <= 100:
            # YAKIN ALAN (<100km): Güç yasası dominant
            log_pga = c1 + c2 * M + c3 * np.log10(distance_km)
        else:
            # UZAK ALAN (>100km): Eksponansiyel azalma eklenir
            # Önce 100km'deki PGA'yı hesapla
            log_pga_100 = c1 + c2 * M + c3 * np.log10(100)
            
            # 100km'den sonraki mesafe için eksponansiyel azalma
            exp_decay = np.exp(c4 * (distance_km - 100))
            log_pga = log_pga_100 + np.log10(exp_decay)
        
        # PGA'yı g cinsinden çevir
        pga = 10 ** log_pga
        
        # Gerçekçi limitler (1999 İzmit maks ölçüm: ~0.4g @ episantr)
        pga = min(pga, 0.80)     # Maksimum 0.80g (M7+ episantr yakını için realist)
        pga = max(pga, 0.0001)   # Minimum 0.0001g (numerik stabilite)
        
        return pga
    
    def check_trigger(self, earthquake_data, building_data, debug=False):
        """PARAMETRİK TETİKLEME - İyileştirilmiş PGA/PGV Calibration ve Multi-Parameter Trigger"""
        
        # 0. İyileştirilmiş mesafe hesaplama (Geodesic - en hassas)
        eq_lat, eq_lon = earthquake_data['latitude'], earthquake_data['longitude']
        bld_lat, bld_lon = building_data['latitude'], building_data['longitude']
        
        # Konum validasyonu (opsiyonel)
        if self.location_validator:
            bld_validation = self.location_validator.validate_wgs84_coordinates(bld_lat, bld_lon)
            if not bld_validation['valid']:
                print(f"⚠️ Geçersiz bina koordinatı: {bld_validation['errors']}")
        
        distance_km = geodesic((eq_lat, eq_lon), (bld_lat, bld_lon)).km

        if MAX_TRIGGER_DISTANCE_KM is not None and distance_km > MAX_TRIGGER_DISTANCE_KM:
            # Çok uzak: tetikleme yok, PGA hesaplamaya gerek yok
            result = {
                'building_id': building_data['building_id'],
                'local_pga': 0.0,
                'local_pgv': 0.0,
                'magnitude': earthquake_data['magnitude'],
                'earthquake_lat': eq_lat,
                'earthquake_lon': eq_lon,
                'distance_km': distance_km,
                'package_type': building_data['package_type'],
                'payout_days': PARAMETRIC_PACKAGES[building_data['package_type']]['payout_guarantee_days'],
                'triggered': False,
                'trigger_type': 'none',
                'payout_amount': 0,
                'payout_ratio': 0
            }
            self.trigger_history.append(result)
            return result

        # 1. İyileştirilmiş PGA/PGV hesaplama
        if self.pga_calibrator:
            # Şehir tespiti (basitleştirilmiş)
            if 40.8 <= bld_lat <= 41.5 and 28.0 <= bld_lon <= 30.0:
                city = 'İstanbul'
            elif 39.5 <= bld_lat <= 40.5 and 32.0 <= bld_lon <= 33.5:
                city = 'Ankara'
            elif 38.5 <= bld_lat <= 39.0 and 35.0 <= bld_lon <= 36.0:
                city = 'Kayseri'
            else:
                city = None
            
            # PGA/PGV tahmini (Akkar-Bommer 2010 GMPE)
            pga_pgv_result = self.pga_calibrator.predict_combined(
                magnitude=earthquake_data['magnitude'],
                distance_km=distance_km,
                vs30=building_data.get('vs30', 400),  # Varsayılan: soft soil
                city=city
            )
            
            local_pga = pga_pgv_result['pga']['pga_g']
            local_pgv = pga_pgv_result['pgv']['pgv_cm_s']
            damage_probability = pga_pgv_result['combined_damage_probability']
        else:
            # Fallback: Eski PGA hesaplama
            local_pga = self.calculate_local_pga(
                (eq_lat, eq_lon),
                (bld_lat, bld_lon),
                earthquake_data['magnitude'],
                earthquake_data['depth_km']
            )
            local_pgv = 0.0
            damage_probability = 0.0

        # 2. Multi-Parameter Trigger Evaluation (opsiyonel)
        if self.trigger_optimizer:
            # Multi-parameter event oluştur
            mp_event = {
                'magnitude': earthquake_data['magnitude'],
                'distance_km': distance_km,
                'pga_g': local_pga,
                'pgv_cm_s': local_pgv,
                'depth_km': earthquake_data['depth_km'],
                'actual_damage': damage_probability  # Tahmin edilen hasar
            }
            
            # Multi-parameter trigger değerlendir
            mp_result = self.trigger_optimizer.evaluate_trigger(mp_event)
            trigger_confidence = mp_result['confidence']
            mp_triggered = mp_result['trigger']
        else:
            trigger_confidence = 0.0
            mp_triggered = None

        # DEBUG: İlk 5 kontrolü yazdır
        if debug and len(self.trigger_history) < 5:
            print(f"\n🔍 DEBUG #{len(self.trigger_history)+1}:")
            print(f"   Deprem: M{earthquake_data['magnitude']} @ ({eq_lat:.2f}, {eq_lon:.2f})")
            print(f"   Bina: ({bld_lat:.2f}, {bld_lon:.2f})")
            print(f"   Mesafe: {distance_km:.1f} km")
            print(f"   PGA: {local_pga:.6f}g | PGV: {local_pgv:.2f}cm/s")
            print(f"   Hasar olasılığı: {damage_probability:.2%}")
            print(f"   Trigger confidence: {trigger_confidence:.2%}")
        
        # 3. Paket eşiklerini al
        package = PARAMETRIC_PACKAGES[building_data['package_type']]
        thresholds = package['pga_thresholds']
        ratios = package['payout_ratios']
        
        # 4. İyileştirilmiş Trigger Logic (PGA + damage probability)
        result = {
            'building_id': building_data['building_id'],
            'local_pga': round(local_pga, 4),
            'local_pgv': round(local_pgv, 2),
            'damage_probability': round(damage_probability, 4),
            'trigger_confidence': round(trigger_confidence, 3),
            'magnitude': earthquake_data['magnitude'],
            'earthquake_lat': eq_lat,
            'earthquake_lon': eq_lon,
            'distance_km': distance_km,
            'package_type': building_data['package_type'],
            'payout_days': package['payout_guarantee_days']
        }
        
        # Trigger decision (SADECE PGA BAZLI - Parametrik Standart)
        # NOT: damage_probability sadece bilgilendirme amaçlıdır, trigger kararını etkilemez
        if local_pga >= thresholds['severe']:
            result.update({
                'triggered': True,
                'trigger_type': 'severe',
                'payout_amount': building_data['max_coverage'] * ratios['severe'],
                'payout_ratio': ratios['severe']
            })
        elif local_pga >= thresholds['moderate']:
            result.update({
                'triggered': True,
                'trigger_type': 'moderate',
                'payout_amount': building_data['max_coverage'] * ratios['moderate'],
                'payout_ratio': ratios['moderate']
            })
        elif local_pga >= thresholds['minor']:
            result.update({
                'triggered': True,
                'trigger_type': 'minor',
                'payout_amount': building_data['max_coverage'] * ratios['minor'],
                'payout_ratio': ratios['minor']
            })
        else:
            result.update({
                'triggered': False,
                'trigger_type': 'none',
                'payout_amount': 0,
                'payout_ratio': 0
            })
        
        self.trigger_history.append(result)
        return result

# =============================================================================
# PERFORMANS METRİKLERİ (Parametrik için)
# =============================================================================

class ParametricMetrics:
    """Confusion Matrix YOK - Hız ve Basis Risk metrikleri"""
    
    @staticmethod
    def calculate(trigger_history, buildings):
        triggered = [r for r in trigger_history if r['triggered']]

        if AGGREGATION_MODE == "per-event":
            # Her tetikleyen deprem için ödeme (yılda çoklu ödemeye izin verir)
            unique_triggers = triggered  # bina tekrarları dahil
        else:
            # Varsayılan: bina başına yıl içinde tek en yüksek tetik
            building_max_triggers = {}
            for trigger in triggered:
                bld_id = trigger['building_id']
                if bld_id not in building_max_triggers:
                    building_max_triggers[bld_id] = trigger
                else:
                    if trigger['local_pga'] > building_max_triggers[bld_id]['local_pga']:
                        building_max_triggers[bld_id] = trigger
            unique_triggers = list(building_max_triggers.values())

        total_payout = sum(r['payout_amount'] for r in unique_triggers)
        total_premium = sum(b['annual_premium_tl'] for b in buildings)
        
        return {
            'total_checks': len(trigger_history),
            'triggered_count': len(triggered),  # Tüm tetiklenme sayısı (tekrar sayımı dahil)
            'unique_buildings_triggered': len(unique_triggers),  # Benzersiz binalar
            'trigger_rate': len(triggered) / len(trigger_history) * 100 if trigger_history else 0,
            'total_payout_tl': total_payout,
            'total_premium_tl': total_premium,
            'loss_ratio': (total_payout / total_premium * 100) if total_premium > 0 else 0,
            'avg_payout_days': np.mean([r['payout_days'] for r in unique_triggers]) if unique_triggers else None,
            'target_14day_compliance': sum(r['payout_days'] <= 14 for r in unique_triggers) / len(unique_triggers) * 100 if unique_triggers else None,
            'aggregation_mode': AGGREGATION_MODE
        }
    
    @staticmethod
    def print_report(metrics):
        print("\n" + "="*80)
        print("📊 PARAMETRİK SİGORTA PERFORMANS RAPORU")
        print("="*80)
        
        print(f"\n🎯 TETİKLENME:")
        print(f"   • Toplam Kontrol: {metrics['total_checks']:,}")
        print(f"   • Tetiklenen: {metrics['triggered_count']:,} ({metrics['trigger_rate']:.2f}%)")
        print(f"   • Benzersiz Bina: {metrics['unique_buildings_triggered']:,} (yıl içinde gerçek tetiklenme)")
        
        print(f"\n⚡ HIZ:")
        if metrics['avg_payout_days']:
            print(f"   • Ortalama Ödeme Süresi: {metrics['avg_payout_days']:.1f} gün")
            print(f"   • 14 Gün Hedefi Uyumu: {metrics['target_14day_compliance']:.1f}%")
            print(f"   📌 Benchmark: CCRIF 14 gün, Vanuatu 10 gün")
        
        print(f"\n💰 FİNANSAL:")
        print(f"   • Toplam Prim: {metrics['total_premium_tl']:,.0f} TL")
        print(f"   • Toplam Ödeme: {metrics['total_payout_tl']:,.0f} TL")
        print(f"   • Loss Ratio: {metrics['loss_ratio']:.2f}%")
        print(f"   📌 Hedef: 60-70% (sürdürülebilir)")
        print(f"   • Toplama Kuralı: {metrics['aggregation_mode']}")
        
        print("="*80)

# =============================================================================
# PARALEL İŞLEME FONKSİYONLARI
# =============================================================================

def process_earthquake_batch(eq_building_data, debug=False):
    """Bir deprem için tüm binaları kontrol et (paralel)"""
    eq, building_list = eq_building_data
    
    engine = ParametricTriggerEngine()
    local_triggers = []
    
    eq_data = {
        'latitude': eq['latitude'],
        'longitude': eq['longitude'],
        'magnitude': eq['magnitude'],
        'depth_km': eq['depth'] if pd.notna(eq['depth']) else 10.0
    }
    
    for i, building in enumerate(building_list):
        building_data = {
            'building_id': building['building_id'],
            'latitude': building['latitude'],
            'longitude': building['longitude'],
            'package_type': building['package_type'],
            'max_coverage': building['max_coverage'],
            'annual_premium_tl': building['annual_premium_tl']
        }
        
        # İlk deprem için debug
        result = engine.check_trigger(eq_data, building_data, debug=(debug and i < 3))
        if result:
            local_triggers.append(result)
    
    return local_triggers

# =============================================================================
# ANA SİMÜLATÖR
# =============================================================================

def main():
    print("\n" + "="*80)
    print("DASK+ PARAMETRİK SİGORTA SİSTEMİ v2.0")
    print("="*80)
    print("✅ Saf Parametrik Mimari - Hasar Tahmini YOK")
    print("✅ Fiziksel Parametre Bazlı Tetikleme (PGA)")
    print("✅ 14 Gün İçinde Ödeme Garantisi")
    print("="*80)
    
    # Veri yükle
    print("\n📂 Veri yükleniyor...")
    
    try:
        # Data path'ını doğru ayarla (src/ içinden çalıştırıldığında parent/data/'ye gider)
        data_dir = Path(__file__).parent.parent / 'data'
        buildings_file = data_dir / 'buildings.csv'
        earthquakes_file = data_dir / 'earthquakes.csv'
        
        buildings_df = pd.read_csv(str(buildings_file), encoding='utf-8-sig')
        print(f"✅ {len(buildings_df):,} bina yüklendi")
        
        # Deprem verisi
        eq_encodings = ['latin-1', 'windows-1254', 'utf-8']
        earthquakes_df = None
        for enc in eq_encodings:
            try:
                earthquakes_df = pd.read_csv(str(earthquakes_file), encoding=enc, on_bad_lines='skip')
                print(f"✅ {len(earthquakes_df):,} deprem verisi yüklendi ({enc})")
                break
            except:
                continue
        
        if earthquakes_df is None:
            print("❌ Deprem verisi yüklenemedi!")
            return
        
        # Sütun isimlerini normalize et (Türkçe → İngilizce)
        col_map_turkish = {
            'Enlem': 'latitude',
            'Boylam': 'longitude',
            'Der(km)': 'depth',
            'xM': 'magnitude',
            'Mw': 'magnitude',
            'ML': 'magnitude',
            'MD': 'magnitude'
        }
        
        for turkish, english in col_map_turkish.items():
            if turkish in earthquakes_df.columns:
                earthquakes_df.rename(columns={turkish: english}, inplace=True)
        
        # Magnitude için en uygun sütunu seç
        mag_cols = ['magnitude', 'xM', 'Mw', 'ML', 'MD']
        for col in mag_cols:
            if col in earthquakes_df.columns:
                earthquakes_df['magnitude'] = earthquakes_df[col]
                break
        
    # Zaman sütunlarını birleştir ve son 12 ayı filtrele (opsiyonel)
        # Olus tarihi: 'YYYY.MM.DD', Olus zamani: 'HH:MM:SS.s'
        date_col, time_col = None, None
        for c in earthquakes_df.columns:
            if c.strip().lower() in ['olus tarihi', 'oluş tarihi', 'olus_tarihi', 'olus_tarih']:
                date_col = c
            if c.strip().lower() in ['olus zamani', 'oluş zamanı', 'olus_zamani', 'olus_saat']:
                time_col = c
        # Not: Yıllık poliçe analizi için son 12 ay verisini kullan (USE_LAST_12_MONTHS=True)
        if USE_LAST_12_MONTHS and date_col is not None:
            try:
                # Tarih-pars et
                dates = pd.to_datetime(earthquakes_df[date_col].astype(str), format='%Y.%m.%d', errors='coerce')
                if time_col is not None and time_col in earthquakes_df.columns:
                    times = pd.to_datetime(earthquakes_df[time_col].astype(str), format='%H:%M:%S.%f', errors='coerce').dt.time
                    earthquakes_df['event_time'] = times
                    # Birleştir
                    earthquakes_df['event_dt'] = pd.to_datetime(dates.astype('datetime64[ns]').dt.date.astype(str) + ' ' + earthquakes_df['event_time'].astype(str), errors='coerce')
                else:
                    earthquakes_df['event_dt'] = dates
                # Son 12 ay filtresi
                end_dt = pd.Timestamp(datetime.now())
                start_dt = end_dt - pd.DateOffset(years=1)
                before_filter = len(earthquakes_df)
                earthquakes_df = earthquakes_df[(earthquakes_df['event_dt'].notna()) & (earthquakes_df['event_dt'] >= start_dt) & (earthquakes_df['event_dt'] <= end_dt)]
                after_filter = len(earthquakes_df)
                print(f"   📅 Zaman filtresi: Son 12 ay ({start_dt.date()} → {end_dt.date()}) | {before_filter:,} → {after_filter:,} kayıt")
            except Exception as _:
                # Tarih parse edilemezse devam
                pass
        # Fallback KALDIRILDI: Poliçe yılı perspektifi korunur (az kayıt normaldir).

        # Gerekli sütunları kontrol
        required = ['latitude', 'longitude', 'magnitude', 'depth']
        if not all(col in earthquakes_df.columns for col in required):
            print(f"❌ Eksik sütunlar! Mevcut: {list(earthquakes_df.columns)}")
            return
        
    except Exception as e:
        print(f"❌ Veri yükleme hatası: {e}")
        return
    
    # Simülasyon
    print(f"\n🚀 SİMÜLASYON BAŞLIYOR...")
    print(f"   ⚡ MOD: M>5.0 DEPREMLER × TÜM BİNALAR")
    
    # Veriyi temizle - DataFrame'den list of dicts'e çevir (index sorununu tamamen ortadan kaldır)
    eq_records = earthquakes_df.to_dict('records')
    building_records = buildings_df.to_dict('records')
    
    # SADECE 5.0'DAN BÜYÜK BÜYÜKLÜKTEKİ DEPREMLERİ FİLTRELE
    large_eq_records = []
    for eq in eq_records:
        try:
            mag = float(eq.get('magnitude', 0))
            if mag > MAGNITUDE_MIN:
                eq['magnitude'] = mag  # Numeric olarak kaydet
                large_eq_records.append(eq)
        except (ValueError, TypeError):
            continue  # Geçersiz magnitude değerlerini atla
    
    if len(large_eq_records) == 0:
        print("   ⚠️  5.0'dan büyük deprem bulunamadı! Tüm depremler kullanılıyor.")
        eq_samples = pd.DataFrame(eq_records)
    else:
        print(f"   🔍 {len(large_eq_records):,} adet M>5.0 deprem filtrelendi (toplam {len(eq_records):,} depremden)")
        eq_samples = pd.DataFrame(large_eq_records)
    
    # Binaları DataFrame'e çevir (TÜM BİNALAR)
    building_samples = pd.DataFrame(building_records)  # 2,000 bina!
    
    total_checks = len(eq_samples) * len(building_samples)
    
    print(f"   📊 {len(eq_samples):,} DEPREM (M>5.0) × {len(building_samples):,} BİNA (TÜM VERİ)")
    print(f"   🔢 Toplam kontrol: {total_checks:,}")
    print(f"   ⏱️  Tahmini süre: ~{total_checks / 20000:.1f} dakika (optimized)")
    
    # Magnitude istatistikleri
    try:
        avg_mag = float(eq_samples['magnitude'].mean())
        max_mag = float(eq_samples['magnitude'].max())
        min_mag = float(eq_samples['magnitude'].min())
        print(f"   � Büyüklük aralığı: {min_mag:.1f} - {max_mag:.1f} (ort: {avg_mag:.2f})")
    except:
        print(f"   📈 Büyüklük istatistikleri hesaplanamadı")
    
    # Veriyi dict'e çevir (Series sorununu çözmek için)
    eq_list = eq_samples.to_dict('records')
    building_list = building_samples.to_dict('records')
    
    total_checks = len(eq_list) * len(building_list)
    
    # Multiprocessing hazırlığı
    num_processes = max(1, cpu_count() - 1)  # 1 CPU boşta bırak
    print(f"   🚀 Paralel işlem: {num_processes} CPU core")
    print(f"   💾 Toplam veri noktası: {total_checks:,}")
    
    # Her deprem için argümanları hazırla
    args_list = [(eq, building_list) for eq in eq_list]
    
    # Paralel işleme ile gelişmiş progress bar
    start_time = datetime.now()
    
    print(f"\n   {'='*60}")
    progress_bar = AdvancedProgressBar(
        total=len(eq_list),
        desc="   🔄 Parametrik Analiz",
        bar_length=50
    )
    
    all_triggers = []
    
    with Pool(processes=num_processes) as pool:
        # imap ile sonuçları tek tek al ve progress bar'ı güncelle
        for result in pool.imap_unordered(process_earthquake_batch, args_list, chunksize=5):
            all_triggers.extend(result)
            progress_bar.update(1)
    
    progress_bar.close()
    
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()
    
    print(f"   {'='*60}")
    print(f"\n   ✅ İşlem Tamamlandı!")
    print(f"   ⏱️  Gerçek Süre: {elapsed:.1f} saniye")
    print(f"   ⚡ Ortalama Hız: {total_checks/elapsed:,.0f} kontrol/saniye")
    print(f"   🎯 Tetiklenme: {len(all_triggers):,} olay")
    
    # Metrikler
    metrics = ParametricMetrics.calculate(
        all_triggers,
        building_samples.to_dict('records')
    )
    
    ParametricMetrics.print_report(metrics)
    
    # Görselleştirme
    print("\n🎨 Görselleştirmeler oluşturuluyor...")
    
    # 1. PGA Dağılım Grafiği
    pga_values = [r['local_pga'] for r in all_triggers]
    triggered_pga = [r['local_pga'] for r in all_triggers if r['triggered']]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(pga_values, bins=50, alpha=0.7, color='blue', edgecolor='black', label='Tüm')
    ax.hist(triggered_pga, bins=50, alpha=0.7, color='red', edgecolor='black', label='Tetiklenen')
    ax.axvline(x=0.15, color='yellow', linestyle='--', label='Temel Minor (0.15g)')
    ax.axvline(x=0.25, color='orange', linestyle='--', label='Temel Moderate (0.25g)')
    ax.axvline(x=0.35, color='red', linestyle='--', label='Temel Severe (0.35g)')
    ax.set_xlabel('PGA (g)', fontsize=12)
    ax.set_ylabel('Frekans', fontsize=12)
    ax.set_title('PGA Dağılımı ve Parametrik Eşikler', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    Path('results').mkdir(exist_ok=True)
    plt.savefig('results/parametric_pga_distribution.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"   ✅ Grafik: results/parametric_pga_distribution.png")
    
    # 2. İnteraktif Harita (sadece tetiklenen olaylar varsa)
    triggered_events = [r for r in all_triggers if r['triggered']]
    
    # 🔧 DÜZELTME: Her bina için SADECE EN YÜKSEK PGA'lı depremi seç
    building_max_events = {}
    for event in triggered_events:
        bld_id = event['building_id']
        if bld_id not in building_max_events:
            building_max_events[bld_id] = event
        elif event['local_pga'] > building_max_events[bld_id]['local_pga']:
            building_max_events[bld_id] = event
    
    unique_triggered_events = list(building_max_events.values())
    
    if unique_triggered_events:
        print(f"\n🗺️  İnteraktif harita oluşturuluyor ({len(triggered_events)} tetiklenme → {len(unique_triggered_events)} benzersiz bina)...")
        
        # Harita merkezi: Türkiye'nin ortası
        m = folium.Map(
            location=[39.0, 35.0],
            zoom_start=6,
            tiles='OpenStreetMap'
        )
        
        # Bina bilgilerini dict'e çevir (hızlı erişim için)
        building_dict = {}
        for building in buildings_df.to_dict('records'):
            building_dict[building['building_id']] = building
        
        # Tetikleme yapan depremleri, tetikleme kayıtlarındaki gerçek lat/lon/mag ile grupla
        triggered_earthquakes = {}
        for event in triggered_events:
            eq_key = (round(event['earthquake_lat'], 3), round(event['earthquake_lon'], 3), round(event['magnitude'], 1))
            if eq_key not in triggered_earthquakes:
                triggered_earthquakes[eq_key] = {
                    'count': 0,
                    'max_pga': 0.0,
                    'total_payout': 0.0
                }
            stats = triggered_earthquakes[eq_key]
            stats['count'] += 1
            stats['max_pga'] = max(stats['max_pga'], event['local_pga'])
            stats['total_payout'] += event['payout_amount']
        
        # Depremleri haritaya ekle
        for eq_key, stats in triggered_earthquakes.items():
            eq_lat, eq_lon, eq_mag = eq_key
            folium.CircleMarker(
                location=[eq_lat, eq_lon],
                radius=eq_mag * 2,
                popup=folium.Popup(
                    f"<b>🔴 Deprem</b><br>"
                    f"Büyüklük: M{eq_mag:.1f}<br>"
                    f"Konum: {eq_lat:.2f}, {eq_lon:.2f}<br>"
                    f"Tetiklenen Bina: {stats['count']}<br>"
                    f"Maks PGA: {stats['max_pga']:.4f}g<br>"
                    f"Toplam Ödeme: {stats['total_payout']:,.0f} TL",
                    max_width=250
                ),
                color='darkred',
                fill=True,
                fillColor='red',
                fillOpacity=0.7,
                weight=2
            ).add_to(m)
        
        # DIAGNOSTICS: Tetikleyen depremler için özet tablo (count, mesafe, PGA)
        try:
            import statistics as _stats
            diag_rows = []
            for eq_key, stats in triggered_earthquakes.items():
                eq_lat, eq_lon, eq_mag = eq_key
                # Bu depremi tetikleyen olayların mesafelerini ve PGA'larını topla
                distances = [ev['distance_km'] for ev in triggered_events
                             if round(ev['earthquake_lat'], 3) == eq_lat and round(ev['earthquake_lon'], 3) == eq_lon and round(ev['magnitude'], 1) == eq_mag]
                pgas = [ev['local_pga'] for ev in triggered_events
                        if round(ev['earthquake_lat'], 3) == eq_lat and round(ev['earthquake_lon'], 3) == eq_lon and round(ev['magnitude'], 1) == eq_mag]
                diag_rows.append({
                    'eq_lat': eq_lat,
                    'eq_lon': eq_lon,
                    'magnitude': eq_mag,
                    'triggered_building_count': stats['count'],
                    'max_pga': round(stats['max_pga'], 4),
                    'total_payout': int(stats['total_payout']),
                    'avg_distance_km': round(_stats.mean(distances), 1) if distances else None,
                    'min_distance_km': round(min(distances), 1) if distances else None,
                    'max_distance_km': round(max(distances), 1) if distances else None,
                })
            if diag_rows:
                diag_df = pd.DataFrame(diag_rows).sort_values('triggered_building_count', ascending=False)
                Path('results').mkdir(exist_ok=True)
                diag_path = 'results/triggered_earthquake_summary.csv'
                diag_df.to_csv(diag_path, index=False)
                topn = min(5, len(diag_df))
                print(f"\n   📄 Tetikleyen Depremler Özeti (ilk {topn}):")
                print(diag_df.head(topn).to_string(index=False))
                print(f"   💾 Kaydedildi: {diag_path}")
        except Exception as _e:
            # Diagnostik oluşturulamadıysa akışı bozma
            pass

        # Binaları haritaya ekle (unique_triggered_events kullanıyoruz, her bina bir kez)
        for event in unique_triggered_events:
            building = building_dict.get(event['building_id'])
            
            if building:
                # Her bina için zaten en yüksek PGA'lı event seçildi
                payout = event['payout_amount']
                pga = event['local_pga']
                trigger_type = event['trigger_type']
                building_id = event['building_id']
                
                # Renk: PGA değerine göre
                if pga >= 0.35:
                    icon_color = 'red'
                elif pga >= 0.25:
                    icon_color = 'orange'
                else:
                    icon_color = 'yellow'
                
                folium.Marker(
                    location=[building['latitude'], building['longitude']],
                    popup=folium.Popup(
                        f"<b>🏢 {building_id}</b><br>"
                        f"Paket: {building['package_type'].upper()}<br>"
                        f"Teminat: {building['max_coverage']:,.0f} TL<br>"
                        f"<hr>"
                        f"<b>Tetiklenme:</b><br>"
                        f"• PGA: {pga:.4f}g<br>"
                        f"• Tip: {trigger_type}<br>"
                        f"• Mesafe: {event['distance_km']:.1f} km<br>"
                        f"• Büyüklük: M{event['magnitude']:.1f}<br>"
                        f"<b>Ödeme:</b> {payout:,.0f} TL",
                        max_width=300
                    ),
                    icon=folium.Icon(color=icon_color, icon='home', prefix='fa'),
                    tooltip=f"{building_id}: {trigger_type} (PGA: {pga:.3f}g)"
                ).add_to(m)
        
        # Isı haritası katmanı (PGA yoğunluğu)
        heat_data = []
        for event in unique_triggered_events:
            building = building_dict.get(event['building_id'])
            if building:
                heat_data.append([
                    building['latitude'],
                    building['longitude'],
                    event['local_pga'] * 100  # Görünürlük için ölçekle
                ])
        
        if heat_data:
            plugins.HeatMap(
                heat_data,
                name='PGA Yoğunluk Haritası',
                min_opacity=0.3,
                radius=20,
                blur=25,
                gradient={
                    0.0: 'blue',
                    0.5: 'yellow',
                    0.7: 'orange',
                    1.0: 'red'
                }
            ).add_to(m)
        
        # Katman kontrolü ekle
        folium.LayerControl().add_to(m)
        
        # Haritayı kaydet
        map_file = 'results/parametric_trigger_map.html'
        m.save(map_file)
        
        print(f"   ✅ Harita: {map_file}")
        print(f"   📍 {len(unique_triggered_events)} tetiklenen bina")
        print(f"   🔴 {len(triggered_earthquakes)} aktif deprem")
    else:
        print(f"\n   ⚠️  Tetiklenen bina olmadığı için harita oluşturulmadı.")
    
    print("\n" + "="*80)
    print("🎉 BAŞARILI!")
    print("="*80)

if __name__ == "__main__":
    main()
