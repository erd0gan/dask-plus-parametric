# -*- coding: utf-8 -*-
"""
DASK+ Parametrik Sigorta - Flask Backend API
============================================
Tüm mevcut pricing_only.py, main.py ve data_generator.py özellikleri
UI-Latest ile entegre edilmiş Flask backend
"""

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
import os
from pathlib import Path
import warnings
import requests
import re
import logging
import random
from multiprocessing import Pool, cpu_count
from functools import partial
warnings.filterwarnings('ignore')

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths
SRC_DIR = Path(__file__).parent
ROOT_DIR = SRC_DIR.parent
STATIC_DIR = ROOT_DIR / 'static'
DATA_DIR = ROOT_DIR / 'data'

# Mevcut modüllerden import
import sys
sys.path.insert(0, str(SRC_DIR))

# Data generator için gerekli imports
from generator import RealisticDataGenerator

# Pricing için gerekli imports  
from pricing import (
    RealEarthquakeDataAnalyzer,
    BuildingDataLoader,
    AIRiskPricingModel,
    DASKPlusPricingSystem,
    FineGrainedPricingEngine,
    LocationPrecisionValidator
)

# Parametric trigger için gerekli imports
from trigger import (
    ParametricTriggerEngine,
    ParametricMetrics,
    PGA_PGV_Calibrator,
    MultiParameterTriggerOptimizer
)

# ✨ BLOCKCHAIN ENTEGRASYONU ✨
from blockchain_manager import BlockchainManager, SmartBlockchainFilter
from blockchain_service import BlockchainService

# Templates ve static dosyaları absolute path ile
app = Flask(__name__, 
            template_folder=str(STATIC_DIR),
            static_folder=str(STATIC_DIR),
            static_url_path='/static')
CORS(app)

# JSON Encoder - int64 ve numpy türlerini dönüştür
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
            return int(obj)
        elif isinstance(obj, (np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif pd.isna(obj):
            return None
        return super().default(obj)

app.json_encoder = NumpyEncoder

# Global değişkenler
pricing_system = None
earthquake_analyzer = None
building_loader = None
trigger_engine = None
kandilli_service = None

# ✨ BLOCKCHAIN MANAGER ✨
blockchain_manager = None
blockchain_service = None  # Yeni: Blockchain Service (Immutable, Hash-Chained)

# Cache değişkenleri
customers_cache = None
customers_cache_timestamp = None
CACHE_DURATION = 300  # 5 dakika cache süresi

# ============================================================================
# KANDILLI EARTHQUAKE SERVICE (backend/app.py'den entegre)
# ============================================================================

class KandilliEarthquakeService:
    """Kandilli Rasathanesi gerçek zamanlı deprem verisi servisi"""
    
    def __init__(self):
        self.url = "http://www.koeri.boun.edu.tr/scripts/lst0.asp"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def fetch_earthquakes(self, min_magnitude=2.0, limit=10):
        """Kandilli'den deprem verilerini çek"""
        try:
            response = requests.get(self.url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                response.encoding = response.apparent_encoding or 'iso-8859-9'
                
                try:
                    content = response.text
                except UnicodeDecodeError:
                    content = response.content.decode('iso-8859-9', errors='ignore')
                
                logger.info(f"Kandilli - Content encoding: {response.encoding}")
                return self.parse_earthquake_data(content, min_magnitude, limit)
            else:
                logger.error(f"Kandilli API hatası: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Kandilli bağlantı hatası: {str(e)}")
            return None
    
    def parse_earthquake_data(self, html_content, min_magnitude, limit):
        """HTML içeriğini parse et"""
        earthquakes = []
        
        try:
            lines = html_content.split('\n')
            in_data_section = False
            header_passed = False
            
            for line in lines:
                line = line.strip()
                
                if '<pre>' in line.lower():
                    in_data_section = True
                    header_passed = False
                    continue
                
                if '</pre>' in line.lower():
                    in_data_section = False
                    continue
                
                if in_data_section:
                    if not header_passed:
                        if any(keyword in line.upper() for keyword in ['DATE', 'TIME', 'LATITUDE', 'LONGITUDE', 'DEPTH', 'REGION']):
                            continue
                        if line.startswith('---') or len(line.strip()) < 50:
                            continue
                        header_passed = True
                    
                    if len(line) > 50 and not line.startswith('---'):
                        earthquake = self.parse_earthquake_line(line)
                        if earthquake and earthquake['magnitude'] >= min_magnitude:
                            earthquakes.append(earthquake)
                            
                            if len(earthquakes) >= limit:
                                break
            
            return earthquakes
            
        except Exception as e:
            logger.error(f"Veri parse hatası: {str(e)}")
            return []
    
    def parse_earthquake_line(self, line):
        """Tek bir deprem satırını parse et"""
        try:
            if len(line) < 50:
                return None
            
            datetime_part = line[:19].strip()
            remaining = line[19:].strip()
            
            if '.' not in datetime_part or ':' not in datetime_part:
                return None
            
            try:
                dt = datetime.strptime(datetime_part, "%Y.%m.%d %H:%M:%S")
                formatted_date = dt.strftime("%d.%m.%Y")
                formatted_time = dt.strftime("%H:%M:%S")
            except:
                return None
            
            parts = remaining.split()
            
            if len(parts) < 6:
                return None
            
            try:
                latitude = float(parts[0])
                longitude = float(parts[1])
                depth = float(parts[2])
                
                magnitude = 0.0
                
                # ML değeri
                if len(parts) > 4 and parts[4] != '-.-':
                    try:
                        magnitude = float(parts[4])
                    except:
                        pass
                
                # MD değeri
                if magnitude == 0.0 and len(parts) > 3 and parts[3] != '-.-':
                    try:
                        magnitude = float(parts[3])
                    except:
                        pass
                
                # MS değeri
                if magnitude == 0.0 and len(parts) > 5 and parts[5] != '-.-':
                    try:
                        magnitude = float(parts[5])
                    except:
                        pass
                
                # Location
                if len(parts) > 6:
                    location_parts = parts[6:]
                    location = ' '.join(location_parts)
                    location = self.fix_turkish_encoding(location)
                    location = location.replace(' İlksel', '').replace(' İLKSEL', '').strip()
                else:
                    location = self.get_approximate_location(latitude, longitude)
                
                return {
                    'date': formatted_date,
                    'time': formatted_time,
                    'latitude': latitude,
                    'longitude': longitude,
                    'depth': depth,
                    'magnitude': magnitude,
                    'location': location.strip(),
                    'datetime': datetime_part
                }
                
            except (ValueError, IndexError) as e:
                return None
        
        except Exception as e:
            return None
    
    def get_approximate_location(self, lat, lon):
        """Koordinatlara göre yaklaşık konum"""
        if 40.5 <= lat <= 42.0 and 26.0 <= lon <= 30.0:
            return "Marmara Bölgesi"
        elif 38.0 <= lat <= 40.5 and 26.0 <= lon <= 30.0:
            return "Ege Bölgesi"
        elif 35.0 <= lat <= 38.0 and 28.0 <= lon <= 36.0:
            return "Akdeniz Bölgesi"
        else:
            return f"Koordinat: {lat:.2f}, {lon:.2f}"
    
    def fix_turkish_encoding(self, text):
        """Turkish encoding düzelt"""
        if not text or len(text.strip()) < 2:
            return text
        
        replacements = {
            '�': '', 'Ã¼': 'ü', 'Ã‡': 'Ç', 'Ã¶': 'ö', 'Ã–': 'Ö',
            'Ã§': 'ç', 'Ä±': 'ı', 'Å�': 'ş', 'Ä�': 'ğ',
            'Ãœ': 'Ü', 'Ä°': 'İ', 'Åž': 'Ş', 'Ä': 'Ğ'
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        return ' '.join(text.split())

# ============================================================================
# INITIALIZATION
# ============================================================================

def _process_policy_batch(args):
    """
    Poliçe batch'ini işle (multiprocessing worker fonksiyonu)
    
    Args:
        args: (batch_data,) tuple
    
    Returns:
        (success_count, failed_count, policy_data_list)
    """
    batch_data = args
    
    success_count = 0
    failed_count = 0
    policy_data_list = []
    
    for building in batch_data:
        try:
            # Poliçe verilerini hazırla (blockchain'e eklenmek üzere)
            policy_data = {
                'type': 'policy',
                'customer_id': building['customer_id'],
                'coverage_tl': int(building['max_coverage']),
                'premium_tl': float(building['annual_premium_tl']),
                'latitude': float(building['latitude']),
                'longitude': float(building['longitude']),
                'package_type': building['package_type'],
                'building_id': building['building_id'],
                'policy_number': building.get('policy_number', 'N/A'),
                'owner_name': building.get('owner_name', 'N/A'),
                'city': building.get('city', 'N/A'),
                'district': building.get('district', 'N/A'),
                'created_at': datetime.now().isoformat()
            }
            
            policy_data_list.append(policy_data)
            success_count += 1
            
        except Exception as e:
            failed_count += 1
    
    return (success_count, failed_count, policy_data_list)


def load_policies_to_blockchain_service():
    """
    Aktif poliçeleri BlockchainService'e yükle (Hash-Chained Blockchain)
    - Mevcut blockchain'deki policy_number'ları kontrol eder
    - Sadece yeni poliçeleri ekler (tekrar önlenir)
    """
    global blockchain_service
    
    if not blockchain_service:
        logger.warning("⚠️ Blockchain service mevcut değil, poliçe yükleme atlanıyor")
        return
    
    try:
        # Buildings verilerini yükle
        buildings_file = DATA_DIR / 'buildings.csv'
        if not buildings_file.exists():
            logger.warning("⚠️ buildings.csv bulunamadı, poliçe yükleme atlanıyor")
            return
        
        buildings_df = pd.read_csv(buildings_file, encoding='utf-8-sig')
        
        # Aktif poliçeleri filtrele
        active_buildings = buildings_df[buildings_df['policy_status'] == 'Aktif'].copy()
        
        # Yüksek kapsamlı poliçeler (100K+)
        high_coverage_policies = active_buildings[
            active_buildings['max_coverage'] >= 100_000
        ].copy()
        
        logger.info(f"📊 Blockchain Service için {len(high_coverage_policies):,} yüksek kapsamlı poliçe bulundu")
        
        if len(high_coverage_policies) == 0:
            logger.info("ℹ️ BlockchainService'e yüklenecek poliçe yok")
            return
        
        # ✨ MEVCUT BLOCKCHAIN'DEKİ POLİÇE NUMARALARINI AL ✨
        existing_policy_numbers = set()
        for block in blockchain_service.blockchain.chain:
            if block.data.get('type') == 'policy':
                policy_num = block.data.get('policy_number')
                if policy_num:
                    existing_policy_numbers.add(policy_num)
        
        logger.info(f"📦 Blockchain'de mevcut {len(existing_policy_numbers):,} poliçe var")
        
        # Sadece yeni poliçeleri filtrele
        new_policies = high_coverage_policies[
            ~high_coverage_policies['policy_number'].isin(existing_policy_numbers)
        ].copy()
        
        if len(new_policies) == 0:
            logger.info("✅ Tüm poliçeler blockchain'de kayıtlı, yeni ekleme yapılmadı")
            return
        
        logger.info(f"📤 {len(new_policies):,} YENİ poliçe BlockchainService'e yükleniyor...")
        logger.info(f"🚀 Multiprocessing kullanılıyor: {cpu_count()} CPU core")
        
        # Multiprocessing için veriyi hazırla
        policies_list = new_policies.to_dict('records')
        
        # Batch'lere böl - daha büyük batch'ler (daha az overhead)
        num_workers = min(cpu_count(), 4)  # Maksimum 4 worker (daha büyük batch'ler)
        batch_size = len(policies_list) // num_workers
        if batch_size == 0:
            batch_size = len(policies_list)
        
        batches = []
        for i in range(0, len(policies_list), batch_size):
            batch = policies_list[i:i + batch_size]
            batches.append(batch)
        
        logger.info(f"📦 {len(batches)} batch oluşturuldu (batch size: ~{batch_size})")
        
        # Multiprocessing ile paralel işle
        success_count = 0
        failed_count = 0
        all_policy_data = []
        
        with Pool(processes=num_workers) as pool:
            # Progress bar ile batch'leri işle
            from tqdm import tqdm
            
            for result in tqdm(
                pool.imap(_process_policy_batch, batches),
                total=len(batches),
                desc="🔗 Blockchain Hazırlık (Parallel)",
                unit="batch",
                bar_format='{l_bar}{bar:40}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                colour='cyan',
                ncols=100
            ):
                batch_success, batch_failed, batch_policy_data = result
                success_count += batch_success
                failed_count += batch_failed
                all_policy_data.extend(batch_policy_data)
        
        print()  # Progress bar'dan sonra yeni satır
        
        # Tüm poliçe verilerini blockchain'e ekle (memory'de, diske yazmadan)
        logger.info(f"📤 {len(all_policy_data):,} poliçe blockchain'e kaydediliyor (memory)...")
        
        from tqdm import tqdm
        for policy_data in tqdm(
            all_policy_data,
            desc="💾 Blockchain Memory Kayıt",
            unit="block",
            bar_format='{l_bar}{bar:40}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
            colour='green',
            ncols=100
        ):
            try:
                # save_to_disk=False ile sadece memory'de tut
                blockchain_service.blockchain.add_block(policy_data, save_to_disk=False)
            except Exception as e:
                logger.error(f"Block ekleme hatası: {e}")
        
        print()  # Progress bar'dan sonra yeni satır
        
        logger.info(f"✅ BlockchainService'e {success_count:,} YENİ poliçe yüklendi (paralel)")
        logger.info(f"❌ {failed_count:,} hata")
        logger.info(f"🔗 Toplam Block: {len(blockchain_service.blockchain.chain)}")
        logger.info(f"✓ Chain Valid: {blockchain_service.blockchain.is_valid()}")
        
        # ⚡ SADECE EN SONDA DİSKE KAYDET (Tek seferde, hızlı!)
        logger.info(f"💾 Blockchain diske kaydediliyor...")
        import time
        start_time = time.time()
        blockchain_service.blockchain._save_chain()
        save_duration = time.time() - start_time
        logger.info(f"✅ Blockchain kaydedildi: {blockchain_service.blockchain.chain_file} ({save_duration:.2f} saniye)")
        
    except Exception as e:
        logger.error(f"❌ BlockchainService poliçe yükleme hatası: {e}")
        import traceback
        traceback.print_exc()


def load_active_policies_to_blockchain():
    """
    Aktif poliçeleri blockchain'e yükle
    data/blockchain_policies.json dosyasından kontrol ederek
    """
    global blockchain_manager
    
    if not blockchain_manager:
        logger.warning("⚠️ Blockchain manager mevcut değil, poliçe yükleme atlanıyor")
        return
    
    try:
        # Blockchain policy cache dosyası
        policy_cache_file = DATA_DIR / 'blockchain_policies.json'
        
        # Bina verilerini yükle
        buildings_file = DATA_DIR / 'buildings.csv'
        if not buildings_file.exists():
            logger.warning("⚠️ buildings.csv bulunamadı, poliçe yükleme atlanıyor")
            return
        
        buildings_df = pd.read_csv(buildings_file, encoding='utf-8-sig')
        
        # Aktif poliçeleri filtrele
        active_buildings = buildings_df[buildings_df['policy_status'] == 'Aktif'].copy()
        
        # Threshold kontrolü - sadece yüksek kapsamlı poliçeler
        high_coverage_policies = active_buildings[
            active_buildings['max_coverage'] >= 100_000
        ].copy()
        
        logger.info(f"📊 Toplam aktif poliçe: {len(active_buildings):,}")
        logger.info(f"📊 100K+ kapsamlı poliçe: {len(high_coverage_policies):,}")
        
        # Paket dağılımı
        if len(high_coverage_policies) > 0:
            package_dist = high_coverage_policies['package_type'].value_counts()
            logger.info(f"📦 Paket dağılımı:")
            for pkg, count in package_dist.items():
                logger.info(f"   {pkg}: {count:,} poliçe")
        
        if len(high_coverage_policies) == 0:
            logger.info("ℹ️ Blockchain'e yüklenecek yüksek kapsamlı poliçe yok")
            return
        
        # Cache'den önceki kayıtları yükle
        loaded_policies = set()
        if policy_cache_file.exists():
            try:
                with open(policy_cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    loaded_policies = set(cache_data.get('loaded_policy_numbers', []))
                    logger.info(f"📂 Cache'den {len(loaded_policies):,} yüklenmiş poliçe bulundu")
            except Exception as e:
                logger.warning(f"⚠️ Cache okuma hatası: {e}")
        
        # Yeni poliçeleri filtrele
        new_policies = high_coverage_policies[
            ~high_coverage_policies['policy_number'].isin(loaded_policies)
        ]
        
        if len(new_policies) == 0:
            logger.info("✅ Tüm aktif poliçeler blockchain'de kayıtlı")
            return
        
        logger.info(f"📤 {len(new_policies):,} yeni poliçe blockchain'e yükleniyor...")
        
        # İstatistikler
        success_count = 0
        failed_count = 0
        
        # Progress bar ile yükleme
        from tqdm import tqdm
        
        for idx, building in tqdm(
            new_policies.iterrows(),
            total=len(new_policies),
            desc="📦 Blockchain Yükleme",
            unit="poliçe",
            bar_format='{l_bar}{bar:40}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
            colour='green',
            ncols=100
        ):
            try:
                policy_data = {
                    'customer_id': building['customer_id'],
                    'building_id': building['building_id'],
                    'policy_number': building['policy_number'],
                    'policy_id': building['policy_number'],
                    'package_type': building['package_type'],
                    'max_coverage': int(building['max_coverage']),
                    'coverage_amount': int(building['max_coverage']),
                    'annual_premium_tl': float(building['annual_premium_tl']),
                    'latitude': float(building['latitude']),
                    'longitude': float(building['longitude']),
                    'start_date': building['policy_start_date'],
                    'owner_name': building['owner_name'],
                    'city': building['city'],
                    'district': building['district']
                }
                
                result = blockchain_manager.record_policy(policy_data)
                
                if result is not None:
                    if result > 0 or result == -1:
                        loaded_policies.add(building['policy_number'])
                        success_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                failed_count += 1
                # Progress bar ile uyumlu hata gösterimi (sadece kritik hataları göster)
                if failed_count <= 5:  # İlk 5 hatayı göster
                    tqdm.write(f"❌ Hata: {building.get('policy_number', 'N/A')}")
        
        print()  # Progress bar'dan sonra yeni satır
        
        # Cache'i güncelle
        cache_data = {
            'last_update': datetime.now().isoformat(),
            'total_loaded': len(loaded_policies),
            'loaded_policy_numbers': list(loaded_policies)
        }
        
        with open(policy_cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ Blockchain'e {success_count:,} poliçe yüklendi, {failed_count:,} hata")
        logger.info(f"💾 Cache güncellendi: {policy_cache_file}")
        
    except Exception as e:
        logger.error(f"❌ Poliçe yükleme hatası: {e}")
        import traceback
        traceback.print_exc()


def initialize_backend():
    """Backend sistemlerini başlat"""
    global pricing_system, earthquake_analyzer, building_loader, trigger_engine, kandilli_service, blockchain_manager, blockchain_service
    
    print("\n" + "="*80)
    print("DASK+ BACKEND BAŞLATILIYOR...")
    print("="*80)
    
    try:
        # ✨ BLOCKCHAIN SERVICE BAŞLAT (YENİ - Hash-Chained Blockchain) ✨
        print("\n🔗 Blockchain Service başlatılıyor...")
        blockchain_service = BlockchainService()
        print("✅ Blockchain Service hazır (Immutable Hash-Chained Blockchain)")
        print(f"   📦 Genesis Block: {blockchain_service.blockchain.chain[0].hash[:16]}...")
        print(f"   🔗 Toplam Block: {len(blockchain_service.blockchain.chain)}")
        print(f"   ✓ Chain Valid: {blockchain_service.blockchain.is_valid()}")
        
        # ✨ BLOCKCHAIN MANAGER BAŞLAT (ESKİ - Hibrit Sistem) ✨
        print("\n🔗 Blockchain Manager başlatılıyor...")
        blockchain_manager = BlockchainManager(
            enable_blockchain=True,  # Blockchain aktif
            async_mode=True,  # Asenkron mod (hız için)
            record_threshold={
                'policy_min_coverage': 100_000,  # 100K+ poliçeler (temel paket dahil)
                'earthquake_min_magnitude': 5.0,  # Sadece M5.0+ depremler
                'payout_min_amount': 0  # Tüm ödemeler
            }
        )
        print("✅ Blockchain Manager hazır (Hibrit Mod)")
        
        # Kandilli Service başlat
        kandilli_service = KandilliEarthquakeService()
        print("✅ Kandilli Service hazır")
        # Veri dizinini kontrol et - ROOT_DIR'e göre relatif path
        data_dir = ROOT_DIR / 'data'
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Veri dosyalarını kontrol et
        buildings_file = data_dir / 'buildings.csv'
        customers_file = data_dir / 'customers.csv'
        earthquakes_file = data_dir / 'earthquakes.csv'
        
        # Eğer buildings.csv yoksa oluştur
        if not buildings_file.exists():
            print("\n📊 Bina ve müşteri verisi oluşturuluyor...")
            generator = RealisticDataGenerator()
            buildings_df, customers_df = generator.generate_buildings(n_buildings=10000)
            buildings_df.to_csv(buildings_file, index=False, encoding='utf-8-sig')
            customers_df.to_csv(customers_file, index=False, encoding='utf-8-sig')
            print(f"✅ {len(buildings_df)} bina ve {len(customers_df)} müşteri verisi oluşturuldu")
        
        # Sistemleri başlat
        print("\n🚀 Sistemler başlatılıyor...")
        
        # 1. Pricing System
        pricing_system = DASKPlusPricingSystem()
        print("✅ Pricing System hazır")
        
        # 2. Earthquake Analyzer
        earthquake_analyzer = RealEarthquakeDataAnalyzer()
        earthquake_analyzer.load_real_earthquake_data()
        print("✅ Earthquake Analyzer hazır")
        
        # 3. Building Loader
        building_loader = BuildingDataLoader()
        print("✅ Building Loader hazır")
        
        # 4. Trigger Engine
        trigger_engine = ParametricTriggerEngine()
        print("✅ Trigger Engine hazır")
        
        # 5. MODEL EĞİTİMİ - İLK BAŞLATMADA
        print("\n🤖 AI Model Eğitimi kontrol ediliyor...")
        model_cache_file = data_dir / 'trained_model.pkl'
        
        if not model_cache_file.exists():
            print("⚠️ Eğitilmiş model bulunamadı. Model eğitimi başlatılıyor...")
            print("⏱️ Bu işlem 2-5 dakika sürebilir (ilk başlatmada bir kez)...")
            
            try:
                # Veriyi yükle
                buildings_df = pd.read_csv(buildings_file, encoding='utf-8-sig')
                
                # Feature extraction (prepare_features kullan)
                features_df = pricing_system.pricing_model.prepare_features(buildings_df)
                
                # Model eğitimi
                pricing_system.pricing_model.train_risk_model(features_df)
                
                # Model'i kaydet (cache için)
                import pickle
                with open(model_cache_file, 'wb') as f:
                    pickle.dump(pricing_system.pricing_model, f)
                
                print("✅ Model eğitimi tamamlandı ve kaydedildi!")
                
            except Exception as e:
                print(f"⚠️ Model eğitimi atlandı: {e}")
                print("💡 Sistem temel fiyatlandırma ile devam edecek")
        else:
            print("✅ Eğitilmiş model cache'den yüklendi")
            try:
                import pickle
                with open(model_cache_file, 'rb') as f:
                    cached_model = pickle.load(f)
                    pricing_system.pricing_model = cached_model
                print("✅ Model başarıyla yüklendi")
            except Exception as e:
                print(f"⚠️ Model yükleme hatası: {e}")
                print("💡 Sistem temel fiyatlandırma ile devam edecek")
        
        # Blockchain'e aktif poliçeleri yükle (ilk başlatmada)
        print("\n📦 Blockchain poliçe durumu kontrol ediliyor...")
        load_active_policies_to_blockchain()
        
        # Blockchain Service'e de poliçeleri yükle
        print("\n📦 Blockchain Service'e poliçeler yükleniyor...")
        load_policies_to_blockchain_service()
        
        print("\n" + "="*80)
        print("✅ BACKEND BAŞLATILDI!")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"❌ Backend başlatma hatası: {e}")
        import traceback
        traceback.print_exc()

# ============================================================================
# ROUTES - HTML PAGES
# ============================================================================

@app.route('/')
def index():
    """Ana sayfa"""
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Müşteri paneli"""
    return render_template('dashboard.html')

@app.route('/admin')
def admin():
    """Admin paneli"""
    return render_template('admin.html')

@app.route('/admin.html')
def admin_html():
    """Admin paneli (HTML uzantısı ile de erişilebilir)"""
    return render_template('admin.html')

@app.route('/test-css')
def test_css():
    """CSS test endpoint"""
    from flask import url_for
    return f"""
    <h1>CSS Test</h1>
    <p>Static folder: {app.static_folder}</p>
    <p>Template folder: {app.template_folder}</p>
    <p>CSS URL: {url_for('static', filename='styles.css')}</p>
    <p><a href="/">Ana Sayfa</a></p>
    <p><a href="/admin">Admin</a></p>
    <style>
        body {{ font-family: Arial; padding: 20px; }}
        h1 {{ color: #1e3a8a; }}
    </style>
    """

# ============================================================================
# API ROUTES - EARTHQUAKE DATA
# ============================================================================

@app.route('/api/earthquakes', methods=['GET'])
def get_earthquakes():
    """Deprem verilerini getir - Kandilli gerçek zamanlı veri"""
    try:
        min_magnitude = float(request.args.get('min_magnitude', 2.0))
        limit = int(request.args.get('limit', 10))
        
        # Önce Kandilli'den gerçek veri çekmeyi dene
        if kandilli_service:
            earthquakes = kandilli_service.fetch_earthquakes(min_magnitude, limit)
            
            if earthquakes and len(earthquakes) > 0:
                logger.info(f"✅ Kandilli'den {len(earthquakes)} deprem verisi alındı")
                
                # ✨ BLOCKCHAIN'E KAYDET (Asenkron - Manager) ✨
                if blockchain_manager and blockchain_manager.enabled:
                    for eq in earthquakes:
                        # Sadece büyük depremleri kaydet (filtreleme blockchain_manager içinde)
                        earthquake_data = {
                            'event_id': f"kandilli_{eq['datetime'].replace(' ', '_').replace('.', '_').replace(':', '_')}",
                            'magnitude': eq['magnitude'],
                            'latitude': eq['latitude'],
                            'longitude': eq['longitude'],
                            'depth_km': eq['depth'],
                            'timestamp': datetime.now()
                        }
                        blockchain_manager.record_earthquake(earthquake_data)
                
                # ✨ BLOCKCHAIN SERVICE'E KAYDET (Hash-Chained) ✨
                if blockchain_service:
                    for eq in earthquakes:
                        try:
                            # M5.0+ depremler için blockchain'e kaydet
                            if eq['magnitude'] >= 5.0:
                                blockchain_service.record_earthquake_on_chain(
                                    magnitude=eq['magnitude'],
                                    latitude=eq['latitude'],
                                    longitude=eq['longitude'],
                                    depth_km=eq['depth'],
                                    location=eq['location'],
                                    event_data={
                                        'event_id': f"kandilli_{eq['datetime'].replace(' ', '_').replace('.', '_').replace(':', '_')}",
                                        'date': eq['date'],
                                        'time': eq['time']
                                    }
                                )
                        except Exception as e:
                            logger.error(f"Blockchain deprem kayıt hatası: {e}")
                
                return jsonify({
                    'success': True,
                    'count': len(earthquakes),
                    'data': earthquakes,
                    'source': 'Kandilli Rasathanesi - Boğaziçi Üniversitesi',
                    'blockchain_recorded': blockchain_manager.enabled if blockchain_manager else False,
                    'blockchain_service_active': blockchain_service is not None,
                    'timestamp': datetime.now().isoformat()
                })
        
        # Kandilli başarısız olursa CSV'den veri yükle (fallback)
        logger.warning("⚠️ Kandilli verisi alınamadı, CSV fallback kullanılıyor")
        
        if earthquake_analyzer and earthquake_analyzer.earthquakes_df is not None:
            df = earthquake_analyzer.earthquakes_df
            
            # Filtrele
            filtered = df[df['magnitude'] >= min_magnitude]
            filtered = filtered.sort_values('date', ascending=False).head(limit)
            
            # JSON formatına çevir
            earthquakes = []
            for _, row in filtered.iterrows():
                earthquakes.append({
                    'location': row['location'],
                    'magnitude': float(row['magnitude']),
                    'depth': float(row['depth']) if pd.notna(row['depth']) else 10.0,
                    'date': row['date'].strftime('%d.%m.%Y') if hasattr(row['date'], 'strftime') else str(row['date']),
                    'time': row['time'].strftime('%H:%M:%S') if hasattr(row['time'], 'strftime') else str(row['time']),
                    'latitude': float(row['latitude']),
                    'longitude': float(row['longitude'])
                })
            
            return jsonify({
                'success': True,
                'count': len(earthquakes),
                'data': earthquakes,
                'source': 'CSV Fallback Data',
                'timestamp': datetime.now().isoformat()
            })
        
        # Her iki kaynak da başarısız - örnek veri
        return jsonify({
            'success': False,
            'message': 'Deprem verisi yüklenemedi',
            'data': get_fallback_earthquake_data(),
            'source': 'Example Data',
            'timestamp': datetime.now().isoformat()
        })
            
    except Exception as e:
        logger.error(f"❌ Deprem API hatası: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}',
            'data': get_fallback_earthquake_data()
        }), 500

def get_fallback_earthquake_data():
    """Fallback deprem verisi"""
    now = datetime.now()
    return [
        {
            'date': now.strftime('%d.%m.%Y'),
            'time': '14:30:45',
            'latitude': 38.4237,
            'longitude': 27.1428,
            'depth': 7.2,
            'magnitude': 3.2,
            'location': 'Ege Denizi',
            'datetime': f"{now.strftime('%Y.%m.%d')} 14:30:45"
        },
        {
            'date': now.strftime('%d.%m.%Y'),
            'time': '13:15:22',
            'latitude': 40.7589,
            'longitude': 29.4013,
            'depth': 12.5,
            'magnitude': 2.8,
            'location': 'Marmara Denizi',
            'datetime': f"{now.strftime('%Y.%m.%d')} 13:15:22"
        },
        {
            'date': now.strftime('%d.%m.%Y'),
            'time': '12:45:10',
            'latitude': 36.2048,
            'longitude': 32.4550,
            'depth': 15.3,
            'magnitude': 3.5,
            'location': 'Akdeniz',
            'datetime': f"{now.strftime('%Y.%m.%d')} 12:45:10"
        }
    ]

# ============================================================================
# API ROUTES - PRICING
# ============================================================================

@app.route('/api/calculate-premium', methods=['POST'])
def calculate_premium():
    """Prim hesapla"""
    try:
        data = request.get_json()
        
        il = data.get('il')
        ilce = data.get('ilce')
        mahalle = data.get('mahalle')
        package = data.get('package')  # 'temel' veya 'standard'
        
        if not all([il, ilce, mahalle, package]):
            return jsonify({
                'success': False,
                'message': 'Eksik parametre'
            }), 400
        
        # Simülasyon değerleri (gerçek sistemde veritabanından gelecek)
        risk_factors = {
            'İstanbul': 1.8,
            'İzmir': 1.5,
            'Ankara': 1.0,
            'Bursa': 1.3,
            'Tokat': 1.2
        }
        
        coverage_amounts = {
            'temel': 250000,
            'standard': 500000,
            'premium': 1000000
        }
        
        risk_factor = risk_factors.get(il, 1.0)
        coverage = coverage_amounts.get(package, 250000)
        
        # Basit prim hesaplama
        base_rate = 0.01  # %1
        premium = int(coverage * base_rate * risk_factor)
        
        return jsonify({
            'success': True,
            'data': {
                'premium': premium,
                'coverage': coverage,
                'location': f"{mahalle}, {ilce}, {il}",
                'risk_factor': risk_factor,
                'package': package
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500

@app.route('/api/simulate-trigger', methods=['POST'])
def simulate_trigger():
    """Parametrik tetikleme simülasyonu"""
    try:
        data = request.get_json()
        
        coverage = data.get('coverage', 250000)
        location = data.get('location', 'İstanbul')
        
        # Simüle edilmiş PGV değeri
        import random
        pgv_value = random.uniform(35, 50)
        
        # İşlem süresi simülasyonu
        processing_time = round(random.uniform(1.8, 2.5), 2)
        
        return jsonify({
            'success': True,
            'triggered': True,
            'data': {
                'payout_amount': coverage,
                'pgv_value': round(pgv_value, 1),
                'processing_time': processing_time,
                'location': location,
                'timestamp': datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500

# ============================================================================
# API ROUTES - ADMIN DASHBOARD (Removed - Using customer dashboard instead)
# ============================================================================

@app.route('/api/policies', methods=['GET'])
def get_policies():
    """Poliçe listesini getir - buildings.csv'den (pagination + filter destekli)"""
    try:
        # Query parametreleri
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '', type=str)
        status_filter = request.args.get('status', 'all', type=str)
        
        # per_page değeri sınırla
        if per_page not in [10, 20, 50, 100]:
            per_page = 20
        if page < 1:
            page = 1
        
        buildings_file = DATA_DIR / 'buildings.csv'
        
        if not buildings_file.exists():
            return jsonify({
                'success': False,
                'message': 'Poliçe verisi bulunamadı'
            }), 404
        
        # CSV'yi oku
        df = pd.read_csv(str(buildings_file), encoding='utf-8-sig')
        
        # Arama filtresi (poliçe no, müşteri adı, adres)
        if search:
            search_lower = search.lower()
            df = df[
                df['policy_number'].str.lower().str.contains(search_lower, na=False) |
                df['owner_name'].str.lower().str.contains(search_lower, na=False) |
                df['complete_address'].str.lower().str.contains(search_lower, na=False)
            ]
        
        # Durum filtresi
        if status_filter != 'all':
            df = df[df['policy_status'] == status_filter]
        
        total_policies = len(df)
        
        # Sayfalama
        total_pages = (total_policies + per_page - 1) // per_page
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        paginated_df = df.iloc[start_idx:end_idx]
        
        # Poliçe listesini hazırla
        policies = []
        for idx, row in paginated_df.iterrows():
            policies.append({
                'no': str(row['policy_number']),
                'musteri': str(row['owner_name']),
                'email': str(row['owner_email']),
                'tel': str(row['owner_phone']),
                'adres': f"{row['city']}/{row['district']}",
                'tam_adres': str(row['complete_address']),
                'teminat': f"{int(row['max_coverage']):,} TL",
                'prim': int(row['monthly_premium_tl']),
                'baslangic': str(row['policy_start_date']),
                'bitis': str(row['policy_end_date']),
                'durum': str(row['policy_status']),
                'paket': str(row['package_type']),
                'risk_skoru': round(float(row['risk_score']), 4),
                'building_id': str(row['building_id'])
            })
        
        return jsonify({
            'success': True,
            'data': policies,
            'total': total_policies,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        })
        
    except Exception as e:
        logger.error(f'Poliçe listesi hatası: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500

@app.route('/api/claims', methods=['GET'])
def get_claims():
    """Hasar taleplerini getir"""
    try:
        claims = [
            {
                'hasarNo': 'H25001',
                'policeNo': 'DP25001',
                'musteri': 'Ahmet Yılmaz',
                'depremTarih': '2025-10-08',
                'pgv': '35.2 cm/s',
                'tutar': '75,000 TL',
                'durum': 'Ödendi'
            },
            {
                'hasarNo': 'H25002',
                'policeNo': 'DP25003',
                'musteri': 'Mehmet Öztürk',
                'depremTarih': '2025-10-08',
                'pgv': '42.8 cm/s',
                'tutar': '25,000 TL',
                'durum': 'Beklemede'
            }
        ]
        
        return jsonify({
            'success': True,
            'data': claims,
            'total': len(claims)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500

@app.route('/api/customers', methods=['GET'])
def get_customers():
    """Müşteri listesini CSV'den getir (pagination + cache destekli) - Optimize edilmiş"""
    global customers_cache, customers_cache_timestamp
    
    try:
        # Query parametreleri
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '', type=str)
        
        # per_page değeri sınırla
        if per_page not in [20, 50, 100]:
            per_page = 20
        if page < 1:
            page = 1
        
        buildings_file = DATA_DIR / 'buildings.csv'
        
        if not buildings_file.exists():
            return jsonify({
                'success': False,
                'message': 'Müşteri verisi bulunamadı'
            }), 404
        
        # Cache kontrolü
        now = datetime.now()
        if (customers_cache is None or 
            customers_cache_timestamp is None or 
            (now - customers_cache_timestamp).total_seconds() > CACHE_DURATION):
            
            # CSV'yi oku (sadece cache oluşturuken)
            df = pd.read_csv(str(buildings_file), encoding='utf-8-sig')
            
            # Müşteri bilgilerini ayıkla - customer_id bazlı
            customers_dict = {}  # customer_id -> müşteri bilgisi
            
            for idx, row in df.iterrows():
                customer_id = row['customer_id']
                
                if customer_id not in customers_dict:
                    customers_dict[customer_id] = {
                        'id': row['building_id'],
                        'customer_id': customer_id,
                        'ad_soyad': row['owner_name'],
                        'email': row['owner_email'],
                        'telefon': row['owner_phone'],
                        'ilce': row['district'],
                        'semte': row['neighborhood'],
                        'kayit_tarihi': row['created_at'][:10],
                        'police_sayisi': 0,
                        'aktif_police': 0,
                        'risk_skoru': round(row['risk_score'], 3)
                    }
                
                # Poliçe sayılarını artır
                customers_dict[customer_id]['police_sayisi'] += 1
                if row['policy_status'] == 'Aktif':
                    customers_dict[customer_id]['aktif_police'] += 1
            
            customers_cache = list(customers_dict.values())
            customers_cache_timestamp = now
            logger.info(f'Müşteri cache güncellendi: {len(customers_cache)} müşteri')
        
        customers_list = customers_cache
        
        # Arama filtresi
        if search:
            search_lower = search.lower()
            customers_list = [
                c for c in customers_list 
                if (search_lower in c['ad_soyad'].lower() or 
                    search_lower in c['email'].lower() or
                    search_lower in c['ilce'].lower() or
                    search_lower in c['semte'].lower())
            ]
        
        total_customers = len(customers_list)
        
        # Sayfalama
        total_pages = (total_customers + per_page - 1) // per_page
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        paginated_customers = customers_list[start_idx:end_idx]
        
        return jsonify({
            'success': True,
            'data': paginated_customers,
            'total': total_customers,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1
        })
        
    except Exception as e:
        logger.error(f'Müşteri listesi hatası: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500

@app.route('/api/customers/<building_id>', methods=['GET'])
def get_customer_detail(building_id):
    """Müşteri detaylarını getir"""
    global customers_cache, customers_cache_timestamp
    
    try:
        buildings_file = DATA_DIR / 'buildings.csv'
        
        if not buildings_file.exists():
            return jsonify({
                'success': False,
                'message': 'Müşteri verisi bulunamadı'
            }), 404
        
        # CSV'yi oku
        df = pd.read_csv(str(buildings_file), encoding='utf-8-sig')
        
        # Building ID'ye göre verileri bul
        building = df[df['building_id'] == building_id]
        
        if building.empty:
            return jsonify({
                'success': False,
                'message': 'Müşteri bulunamadı'
            }), 404
        
        row = building.iloc[0]
        
        # Aynı customer_id'ye sahip tüm binaları bul
        customer_buildings = df[df['customer_id'] == row['customer_id']]
        
        # Detaylı müşteri bilgileri - .item() ile int64 dönüşümü
        customer_detail = {
            'id': str(row['building_id']),
            'customer_id': str(row['customer_id']),
            'ad_soyad': str(row['owner_name']),
            'email': str(row['owner_email']),
            'telefon': str(row['owner_phone']),
            'ilce': str(row['district']),
            'semte': str(row['neighborhood']),
            'tam_adres': str(row['complete_address']),
            
            # Bina bilgileri
            'yapı_tipi': str(row['structure_type']),
            'inşa_yili': int(row['construction_year'].item()),
            'bina_yasi': int(row['building_age'].item()),
            'kat_sayisi': int(row['floors'].item()),
            'daire_sayisi': int(row['apartment_count'].item()),
            'bina_alani_m2': float(round(float(row['building_area_m2']), 2)),
            'oturan_sayisi': int(row['residents'].item()),
            
            # Riskler
            'zemin_tipi': str(row['soil_type']),
            'zemin_amplifikasyonu': float(round(float(row['soil_amplification']), 2)),
            'likefaksiyon_riski': float(round(float(row['liquefaction_risk']), 2)),
            'en_yakin_fay': str(row['nearest_fault']),
            'faya_uzaklik_km': float(round(float(row['distance_to_fault_km']), 2)),
            'risk_skoru': float(round(float(row['risk_score']), 4)),
            'kalite_skoru': float(round(float(row['quality_score']), 2)),
            
            # Sigorta bilgileri
            'paket_tipi': str(row['package_type']),
            'max_teminat': int(row['max_coverage'].item()),
            'sigorta_degeri_tl': float(round(float(row['insurance_value_tl']), 2)),
            'yillik_prim_tl': float(round(float(row['annual_premium_tl']), 2)),
            'aylik_prim_tl': float(round(float(row['monthly_premium_tl']), 2)),
            'policy_status': str(row['policy_status']),
            'police_baslangic': str(row['policy_start_date']),
            'police_bitis': str(row['policy_end_date']),
            'kayit_tarihi': str(row['created_at'])[:10],
            
            # Müşteri istatistikleri
            'toplam_police': int(len(customer_buildings)),
            'aktif_police': int(len(customer_buildings[customer_buildings['policy_status'] == 'Aktif'])),
            'pasif_police': int(len(customer_buildings[customer_buildings['policy_status'] == 'Pasif'])),
            'toplam_teminat': int(customer_buildings['max_coverage'].sum().item()),
            'toplam_yillik_prim': float(round(float(customer_buildings['annual_premium_tl'].sum()), 2))
        }
        
        return jsonify({
            'success': True,
            'data': customer_detail
        })
        
    except Exception as e:
        logger.error(f'Müşteri detayı hatası: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500

@app.route('/api/pgv-monitor', methods=['GET'])
def get_pgv_monitor():
    """Canlı PGV monitör verisi"""
    try:
        import random
        
        locations = [
            {'name': 'İstanbul', 'threshold': 20},
            {'name': 'İzmir', 'threshold': 20},
            {'name': 'Bursa', 'threshold': 30},
            {'name': 'Ankara', 'threshold': 40},
            {'name': 'Tokat', 'threshold': 30}
        ]
        
        pgv_data = []
        for loc in locations:
            value = random.uniform(2, 15)
            pgv_data.append({
                'name': loc['name'],
                'value': round(value, 1),
                'threshold': loc['threshold'],
                'status': 'danger' if value > loc['threshold'] else 'warning' if value > loc['threshold'] * 0.8 else 'safe'
            })
        
        return jsonify({
            'success': True,
            'data': pgv_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500

# ============================================================================
# API ROUTES - REPORTS
# ============================================================================

@app.route('/api/reports/generate', methods=['POST'])
def generate_report():
    """Rapor oluştur"""
    try:
        data = request.get_json()
        report_type = data.get('type', 'policy')
        date_range = data.get('date_range', 'last_30_days')
        
        # Rapor oluşturma simülasyonu
        report = {
            'type': report_type,
            'date_range': date_range,
            'generated_at': datetime.now().isoformat(),
            'file_path': f'/reports/{report_type}_{date_range}.pdf',
            'status': 'ready'
        }
        
        return jsonify({
            'success': True,
            'data': report
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500

# ============================================================================
# API ROUTES - DEBUGGING (Kandilli)
# ============================================================================

@app.route('/api/earthquakes/debug', methods=['GET'])
def debug_earthquakes():
    """Kandilli debug endpoint - ham veri görüntüleme"""
    try:
        if not kandilli_service:
            return jsonify({'error': 'Kandilli service başlatılmamış'}), 500
        
        response = requests.get(kandilli_service.url, headers=kandilli_service.headers, timeout=10)
        
        return jsonify({
            'url': kandilli_service.url,
            'status_code': response.status_code,
            'encoding': response.encoding,
            'apparent_encoding': response.apparent_encoding,
            'content_type': response.headers.get('content-type'),
            'content_sample': response.text[:1000] if response.text else 'No content',
            'note': 'Kandilli ham veri örneği'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Sistem sağlık kontrolü"""
    
    # Blockchain stats (Manager)
    blockchain_stats = {}
    if blockchain_manager:
        blockchain_stats = blockchain_manager.get_stats()
    
    # Blockchain Service stats
    blockchain_service_stats = {}
    if blockchain_service:
        blockchain_service_stats = {
            'total_blocks': len(blockchain_service.blockchain.chain),
            'chain_valid': blockchain_service.blockchain.is_valid(),
            'genesis_hash': blockchain_service.blockchain.chain[0].hash[:16] + '...',
            'latest_hash': blockchain_service.blockchain.chain[-1].hash[:16] + '...' if len(blockchain_service.blockchain.chain) > 0 else None,
            'admin_count': len(blockchain_service.admins),
            'required_approvals': blockchain_service.REQUIRED_ADMIN_APPROVALS
        }
    
    return jsonify({
        'status': 'healthy',
        'service': 'DASK+ Parametrik Backend',
        'kandilli_service': 'active' if kandilli_service else 'inactive',
        'pricing_system': 'active' if pricing_system else 'inactive',
        'blockchain_manager': 'active' if blockchain_manager and blockchain_manager.enabled else 'inactive',
        'blockchain_service': 'active' if blockchain_service else 'inactive',
        'blockchain_manager_stats': blockchain_stats,
        'blockchain_service_stats': blockchain_service_stats,
        'timestamp': datetime.now().isoformat(),
        'version': '2.0.2-blockchain-full'
    })

# ============================================================================
# BLOCKCHAIN API ROUTES
# ============================================================================

@app.route('/api/blockchain/stats', methods=['GET'])
def get_blockchain_stats():
    """Blockchain istatistiklerini getir (hem Manager hem Service)"""
    try:
        stats = {}
        
        # Blockchain Manager stats (eski sistem)
        if blockchain_manager and blockchain_manager.enabled:
            manager_stats = blockchain_manager.get_stats()
            contract_stats = blockchain_manager.get_contract_stats()
            stats['manager'] = {
                'integration_stats': manager_stats,
                'contract_stats': contract_stats,
                'type': 'Hybrid Manager (Asenkron)'
            }
        
        # Blockchain Service stats (yeni sistem - hash-chained)
        if blockchain_service:
            service_stats = blockchain_service.get_blockchain_blocks()
            blockchain_data = blockchain_service.blockchain
            
            stats['service'] = {
                'total_blocks': len(blockchain_data.chain),
                'genesis_hash': blockchain_data.chain[0].hash,
                'latest_block_hash': blockchain_data.chain[-1].hash if len(blockchain_data.chain) > 0 else None,
                'chain_valid': blockchain_data.is_valid(),
                'policy_blocks': len([b for b in blockchain_data.chain if b.data.get('type') == 'policy']),
                'payout_blocks': len([b for b in blockchain_data.chain if b.data.get('type') == 'payout']),
                'earthquake_blocks': len([b for b in blockchain_data.chain if b.data.get('type') == 'earthquake']),
                'type': 'Immutable Hash-Chained Blockchain'
            }
            
            # Multi-admin bilgileri
            stats['service']['multi_admin'] = {
                'admin_count': len(blockchain_service.admins),
                'required_approvals': blockchain_service.REQUIRED_ADMIN_APPROVALS,
                'admins': list(blockchain_service.admins.keys())
            }
        
        return jsonify({
            'success': True,
            'blockchain_systems': stats,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500

@app.route('/api/blockchain/policy/<int:policy_id>', methods=['GET'])
def get_blockchain_policy(policy_id):
    """Blockchain'den poliçe sorgula"""
    try:
        if not blockchain_manager or not blockchain_manager.enabled:
            return jsonify({
                'success': False,
                'message': 'Blockchain devre dışı'
            }), 503
        
        policy = blockchain_manager.get_policy_from_blockchain(policy_id)
        
        if policy:
            return jsonify({
                'success': True,
                'policy': policy
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Poliçe bulunamadı'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500

@app.route('/api/blockchain/earthquake/<event_id>', methods=['GET'])
def get_blockchain_earthquake(event_id):
    """Blockchain'den deprem sorgula"""
    try:
        if not blockchain_manager or not blockchain_manager.enabled:
            return jsonify({
                'success': False,
                'message': 'Blockchain devre dışı'
            }), 503
        
        earthquake = blockchain_manager.get_earthquake_from_blockchain(event_id)
        
        if earthquake:
            return jsonify({
                'success': True,
                'earthquake': earthquake
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Deprem bulunamadı'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500

@app.route('/api/blockchain/bulk-sync', methods=['POST'])
def blockchain_bulk_sync():
    """Toplu blockchain senkronizasyonu (tüm poliçeler)"""
    try:
        if not blockchain_manager or not blockchain_manager.enabled:
            return jsonify({
                'success': False,
                'message': 'Blockchain devre dışı'
            }), 503
        
        data = request.get_json()
        limit = data.get('limit', 100)  # Varsayılan 100 poliçe
        
        result = blockchain_manager.bulk_record_policies(limit=limit)
        
        return jsonify({
            'success': True,
            'result': result,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500

@app.route('/api/blockchain/blocks', methods=['GET'])
def get_blockchain_blocks():
    """
    Blockchain'deki tüm blokları getir (BlockchainService)
    
    Query params:
        - type: 'policy', 'payout', 'earthquake' (opsiyonel)
        - limit: int (varsayılan 50)
    """
    try:
        if not blockchain_service:
            return jsonify({
                'success': False,
                'message': 'BlockchainService devre dışı'
            }), 503
        
        block_type = request.args.get('type', None)
        limit = int(request.args.get('limit', 50))
        
        blocks = blockchain_service.get_blockchain_blocks(block_type=block_type)
        
        # Limit uygula
        blocks = blocks[:limit]
        
        return jsonify({
            'success': True,
            'blocks': blocks,
            'total': len(blocks),
            'chain_valid': blockchain_service.blockchain.is_valid(),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500

@app.route('/api/blockchain/verify', methods=['GET'])
def verify_blockchain():
    """
    Blockchain integrity verification
    """
    try:
        if not blockchain_service:
            return jsonify({
                'success': False,
                'message': 'BlockchainService devre dışı'
            }), 503
        
        is_valid = blockchain_service.verify_blockchain_integrity()
        
        return jsonify({
            'success': True,
            'chain_valid': is_valid,
            'total_blocks': len(blockchain_service.blockchain.chain),
            'genesis_hash': blockchain_service.blockchain.chain[0].hash,
            'latest_hash': blockchain_service.blockchain.chain[-1].hash if len(blockchain_service.blockchain.chain) > 0 else None,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500

@app.route('/api/blockchain/create-policy', methods=['POST'])
def blockchain_create_policy():
    """
    Blockchain'e poliçe kaydet (BlockchainService)
    
    Body:
    {
        "customer_id": "CUST000123",
        "coverage_amount": 1000000,
        "latitude": 39.0,
        "longitude": 28.5,
        "premium": 30000,
        "package_type": "temel"
    }
    """
    try:
        if not blockchain_service:
            return jsonify({
                'success': False,
                'message': 'BlockchainService devre dışı'
            }), 503
        
        data = request.get_json()
        
        policy_id = blockchain_service.create_policy_on_chain(
            customer_id=data.get('customer_id'),
            coverage_amount=data.get('coverage_amount'),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            premium=data.get('premium'),
            package_type=data.get('package_type', 'temel'),
            verbose=True
        )
        
        return jsonify({
            'success': True,
            'policy_id': policy_id,
            'block_index': len(blockchain_service.blockchain.chain) - 1,
            'block_hash': blockchain_service.blockchain.chain[-1].hash,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500

@app.route('/api/blockchain/execute-payout', methods=['POST'])
def blockchain_execute_payout():
    """
    Blockchain'de ödeme gerçekleştir (multi-admin onayı ile)
    
    Body:
    {
        "payout_id": 0,
        "admin_approvals": ["admin1", "admin2"]  # 2-of-3 gerekli
    }
    """
    try:
        if not blockchain_service:
            return jsonify({
                'success': False,
                'message': 'BlockchainService devre dışı'
            }), 503
        
        data = request.get_json()
        payout_id = data.get('payout_id')
        admin_approvals = data.get('admin_approvals', [])
        
        if len(admin_approvals) < 2:
            return jsonify({
                'success': False,
                'message': 'En az 2 admin onayı gerekli (2-of-3)'
            }), 400
        
        # Ödeme gerçekleştir
        success = blockchain_service.execute_payout(
            payout_id=payout_id,
            admin_approvals=admin_approvals
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Ödeme başarıyla gerçekleştirildi',
                'payout_id': payout_id,
                'admin_approvals': admin_approvals,
                'block_index': len(blockchain_service.blockchain.chain) - 1,
                'block_hash': blockchain_service.blockchain.chain[-1].hash,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Ödeme gerçekleştirilemedi'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500

@app.route('/api/blockchain/customer/<customer_id>', methods=['GET'])
def get_blockchain_customer_data(customer_id):
    """
    Müşterinin blockchain'deki tüm kayıtlarını getir
    
    Args:
        customer_id: Müşteri ID (ör: CUST000123)
    
    Returns:
        - Müşteriye ait tüm poliçe blokları
        - Müşteriye yapılan tüm ödeme blokları
        - Müşteriyi etkileyen deprem blokları (konum bazlı)
    """
    try:
        if not blockchain_service:
            return jsonify({
                'success': False,
                'message': 'BlockchainService devre dışı'
            }), 503
        
        # Müşteriye ait tüm blokları bul
        customer_blocks = []
        
        for block in blockchain_service.blockchain.chain:
            block_data = block.data
            
            # Policy blokları
            if block_data.get('type') == 'policy' and block_data.get('customer_id') == customer_id:
                customer_blocks.append({
                    'block_index': block.index,
                    'block_hash': block.hash,
                    'timestamp': datetime.fromtimestamp(block.timestamp).isoformat(),
                    'type': 'policy',
                    'data': block_data
                })
            
            # Payout blokları
            elif block_data.get('type') == 'payout' and block_data.get('customer_id') == customer_id:
                customer_blocks.append({
                    'block_index': block.index,
                    'block_hash': block.hash,
                    'timestamp': datetime.fromtimestamp(block.timestamp).isoformat(),
                    'type': 'payout',
                    'data': block_data
                })
        
        # İstatistikler
        policy_count = len([b for b in customer_blocks if b['type'] == 'policy'])
        payout_count = len([b for b in customer_blocks if b['type'] == 'payout'])
        total_coverage = sum([b['data'].get('coverage_tl', 0) for b in customer_blocks if b['type'] == 'policy'])
        total_payouts = sum([b['data'].get('payout_amount', 0) for b in customer_blocks if b['type'] == 'payout'])
        
        return jsonify({
            'success': True,
            'customer_id': customer_id,
            'blocks': customer_blocks,
            'stats': {
                'total_blocks': len(customer_blocks),
                'policy_blocks': policy_count,
                'payout_blocks': payout_count,
                'total_coverage': total_coverage,
                'total_payouts': total_payouts
            },
            'blockchain_valid': blockchain_service.blockchain.is_valid(),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500

@app.route('/api/blockchain/search', methods=['POST'])
def blockchain_search():
    """
    Blockchain'de arama yap
    
    Body:
    {
        "query": "CUST000123",  # Customer ID, policy ID, vb.
        "type": "policy",  # policy, payout, earthquake (opsiyonel)
        "limit": 50
    }
    """
    try:
        if not blockchain_service:
            return jsonify({
                'success': False,
                'message': 'BlockchainService devre dışı'
            }), 503
        
        data = request.get_json()
        query = data.get('query', '')
        block_type = data.get('type', None)
        limit = data.get('limit', 50)
        
        # Arama yap
        results = []
        
        for block in blockchain_service.blockchain.chain:
            block_data = block.data
            
            # Tip filtresi
            if block_type and block_data.get('type') != block_type:
                continue
            
            # Query filtresi (customer_id, policy_id, vb.)
            block_str = json.dumps(block_data).lower()
            if query.lower() in block_str:
                results.append({
                    'block_index': block.index,
                    'block_hash': block.hash,
                    'timestamp': datetime.fromtimestamp(block.timestamp).isoformat(),
                    'type': block_data.get('type'),
                    'data': block_data
                })
            
            if len(results) >= limit:
                break
        
        return jsonify({
            'success': True,
            'query': query,
            'results': results,
            'total_found': len(results),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500

# ============================================================================
# AUTHENTICATION & DASHBOARD API ROUTES
# ============================================================================

@app.route('/api/login', methods=['POST'])
def login():
    """
    Kullanıcı giriş endpoint'i
    
    Request:
        {
            "email": "user@email.com",
            "password": "password123"
        }
    """
    try:
        from auth import PasswordManager, TokenManager
        
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email ve sifre gerekli'}), 400
        
        # Customers.csv'den müşteri verilerini oku
        customers_file = DATA_DIR / 'customers.csv'
        if not customers_file.exists():
            return jsonify({'error': 'Veri dosyalari bulunamadi'}), 404
        
        customers_df = pd.read_csv(customers_file)
        
        # Email ile müşteri bul (büyük/küçük harf duyarsız)
        customer_record = customers_df[customers_df['email'].str.lower() == email.lower()]
        if customer_record.empty:
            return jsonify({'error': 'E-mail veya sifre yanlis'}), 401
        
        customer_data = customer_record.iloc[0]
        
        # Basit password check (plain text - production'da hash ile)
        if password != "dask2024":
            return jsonify({'error': 'E-mail veya sifre yanlis'}), 401
        
        # Müşteri bilgilerini al
        customer_id = customer_data['customer_id']
        full_name = customer_data['full_name']
        avatar_url = customer_data['avatar_url']
        status = customer_data['status']
        
        # ✨ BLOCKCHAIN'E GİRİŞ KAYDI (İsteğe Bağlı - Audit Trail) ✨
        if blockchain_service:
            try:
                # Login event'i blockchain'e kaydet (diske yazmadan, hızlı)
                login_block_data = {
                    'type': 'customer_login',
                    'customer_id': customer_id,
                    'email': email,
                    'timestamp': datetime.now().isoformat(),
                    'ip_address': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent', 'Unknown')[:100]
                }
                blockchain_service.blockchain.add_block(login_block_data, save_to_disk=False)
                logger.info(f"🔗 Login kaydı blockchain'e eklendi: {customer_id}")
            except Exception as e:
                logger.error(f"Blockchain login kayıt hatası: {e}")
        
        # Token oluştur
        token = TokenManager.create_token(
            customer_id=customer_id,
            email=email,
            name=full_name
        )
        
        return jsonify({
            'success': True,
            'token': token,
            'customer': {
                'customer_id': customer_id,
                'email': email,
                'name': full_name,
                'full_name': full_name,
                'avatar_url': avatar_url,
                'status': status
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/customer/<customer_id>', methods=['GET'])
def get_customer(customer_id):
    """
    Müşteri bilgilerini getir (customers.csv'den)
    
    Args:
        customer_id: Müşteri ID (ör: CUST000000)
    """
    try:
        # Önce customers.csv'den bul
        customers_file = DATA_DIR / 'customers.csv'
        if not customers_file.exists():
            return jsonify({'error': 'Veri dosyalari bulunamadi'}), 404
        
        customers_df = pd.read_csv(customers_file)
        customer_data = customers_df[customers_df['customer_id'] == customer_id]
        
        if customer_data.empty:
            return jsonify({'error': 'Musteri bulunamadi'}), 404
        
        customer_info = customer_data.iloc[0]
        
        # Buildings.csv'den ilişkili binaları say
        buildings_file = DATA_DIR / 'buildings.csv'
        total_properties = 0
        if buildings_file.exists():
            buildings_df = pd.read_csv(buildings_file)
            total_properties = int(len(buildings_df[buildings_df['customer_id'] == customer_id]))
        
        # Müşteri bilgisini derle (int64 türlerini int'e çevir)
        response_data = {
            'success': True,
            'customer': {
                'customer_id': str(customer_info['customer_id']),
                'full_name': str(customer_info['full_name']),
                'first_name': str(customer_info['first_name']),
                'last_name': str(customer_info['last_name']),
                'email': str(customer_info['email']),
                'phone': str(customer_info['phone']),
                'tc_number': str(customer_info['tc_number']),
                'avatar_url': str(customer_info['avatar_url']),
                'status': str(customer_info['status']),
                'total_properties': total_properties,
                'registration_date': str(customer_info['registration_date']),
                'last_login': str(customer_info['last_login']),
                'customer_score': int(customer_info['customer_score'])
            }
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Get customer error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/policy-details/<customer_id>', methods=['GET'])
def get_policy_details(customer_id):
    """
    Müşterinin poliçe detaylarını getir - Dinamik
    buildings.csv'den customer_id'ye göre ilişkili binaları bulup
    poliçe detaylarını dön
    
    Args:
        customer_id: Müşteri ID
    """
    try:
        # Bina verilerini oku
        buildings_file = DATA_DIR / 'buildings.csv'
        if not buildings_file.exists():
            return jsonify({'error': 'Bina verileri bulunamadı'}), 404
        
        buildings_df = pd.read_csv(buildings_file)
        
        # Bu müşteriye ait binaları bul
        customer_buildings = buildings_df[buildings_df['customer_id'] == customer_id]
        
        if customer_buildings.empty:
            return jsonify({'error': 'Musteri icin polis bulunamadı'}), 404
        
        # İlk poliçeyi ayrıntılı şekilde dön (müşterinin aktif poliçesi)
        building = customer_buildings.iloc[0]
        
        policy_details = {
            'customer_id': str(customer_id),
            'total_policies': len(customer_buildings),
            'active_policy_index': 1,
            'policy_number': str(building['policy_number']),
            'package_type': str(building['package_type']),
            'policy_start_date': str(building['policy_start_date']),
            'policy_end_date': str(building['policy_end_date']),
            'policy_status': str(building['policy_status']),
            'max_coverage': int(building['max_coverage']),
            'monthly_premium_tl': round(float(building['monthly_premium_tl']), 2),
            'annual_premium_tl': round(float(building['annual_premium_tl']), 2),
            'building_info': {
                'building_id': str(building['building_id']),
                'address': str(building['complete_address']),
                'district': str(building['district']),
                'city': str(building['city']),
                'latitude': float(building['latitude']),
                'longitude': float(building['longitude']),
                'construction_year': int(building['construction_year']),
                'building_age': int(building['building_age']),
                'structure_type': str(building['structure_type']),
                'floors': int(building['floors']),
                'units': int(building['apartment_count']),
                'building_area_m2': int(building['building_area_m2']),
                'residents': int(building['residents']),
                'commercial_units': int(building['commercial_units'])
            },
            'risk_assessment': {
                'risk_score': round(float(building['risk_score']), 4),
                'quality_score': round(float(building['quality_score']), 2),
                'soil_type': str(building['soil_type']),
                'soil_amplification': round(float(building['soil_amplification']), 2),
                'liquefaction_risk': round(float(building['liquefaction_risk']), 2),
                'distance_to_fault_km': round(float(building['distance_to_fault_km']), 2),
                'nearest_fault': str(building['nearest_fault']),
                'risk_level': 'Yuksek' if float(building['risk_score']) > 0.7 else ('Orta' if float(building['risk_score']) > 0.4 else 'Dusuk')
            },
            'coverage': {
                'package': str(building['package_type']),
                'insurance_value_tl': int(building['insurance_value_tl']),
                'max_coverage_tl': int(building['max_coverage']),
                'deductible_tl': int(building['insurance_value_tl'] * 0.02),
                'annual_premium_tl': round(float(building['annual_premium_tl']), 2),
                'monthly_premium_tl': round(float(building['monthly_premium_tl']), 2)
            },
            'policy_dates': {
                'start_date': str(building['policy_start_date']),
                'end_date': str(building['policy_end_date']),
                'status': str(building['policy_status']),
                'renewal_date': (datetime.strptime(str(building['policy_end_date']), '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d')
            },
            'coverage_details': {
                'structural_damage': 'Tam Kapsama',
                'contents': 'Istegine Bagli',
                'additional_living': 'Istegine Bagli',
                'liability': 'Istegine Bagli',
                'parametric_trigger': '48 Saat'
            },
            'all_policies_summary': []
        }
        
        # Tüm poliçelerin özeti
        for idx, bld in customer_buildings.iterrows():
            policy_details['all_policies_summary'].append({
                'policy_number': str(bld['policy_number']),
                'address': str(bld['complete_address']),
                'status': str(bld['policy_status']),
                'coverage': int(bld['max_coverage']),
                'premium': round(float(bld['monthly_premium_tl']), 2)
            })
        
        return jsonify({
            'success': True,
            'policy': policy_details
        }), 200
        
    except Exception as e:
        logger.error(f"Get policy details error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/customer-policies/<customer_id>', methods=['GET'])
def get_customer_policies(customer_id):
    """
    Müşterinin TÜM poliçelerini listele
    
    Args:
        customer_id: Müşteri ID
    """
    try:
        buildings_file = DATA_DIR / 'buildings.csv'
        if not buildings_file.exists():
            return jsonify({'error': 'Bina verileri bulunamadı'}), 404
        
        buildings_df = pd.read_csv(buildings_file)
        
        # Müşteriye ait tüm binaları bul
        customer_buildings = buildings_df[buildings_df['customer_id'] == customer_id]
        
        if customer_buildings.empty:
            return jsonify({
                'success': True,
                'policies': [],
                'total': 0
            }), 200
        
        policies = []
        for idx, building in customer_buildings.iterrows():
            policies.append({
                'policy_number': building['policy_number'],
                'address': building['complete_address'],
                'status': building['policy_status'],
                'start_date': building['policy_start_date'],
                'end_date': building['policy_end_date'],
                'coverage': int(building['max_coverage']),
                'premium_monthly': round(float(building['monthly_premium_tl']), 2),
                'risk_score': round(float(building['risk_score']), 4),
                'building_id': building['building_id'],
                'package_type': str(building['package_type'])
            })
        
        return jsonify({
            'success': True,
            'policies': policies,
            'total': len(policies),
            'customer_id': customer_id
        }), 200
        
    except Exception as e:
        logger.error(f"Get customer policies error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/dashboard/stats/<customer_id>', methods=['GET'])
def get_dashboard_stats(customer_id):
    """
    Dashboard istatistikleri getir - Musteri odakli (buildings.csv'den)
    
    Args:
        customer_id: Musteri ID
    """
    try:
        buildings_file = DATA_DIR / 'buildings.csv'
        
        if not buildings_file.exists():
            return jsonify({'error': 'Veri dosyalari bulunamadi'}), 404
        
        buildings_df = pd.read_csv(buildings_file)
        
        # Müşteriye ait binaları bul
        customer_buildings = buildings_df[buildings_df['customer_id'] == customer_id]
        
        if customer_buildings.empty:
            return jsonify({'error': 'Musteri bulunamadi'}), 404
        
        # Aktif ve pasif poliçeleri say
        active_policies = int(len(customer_buildings[customer_buildings['policy_status'] == 'Aktif']))
        passive_policies = int(len(customer_buildings[customer_buildings['policy_status'] == 'Pasif']))
        
        # Toplam prim hesapla
        total_premiums = float(customer_buildings['monthly_premium_tl'].sum()) if len(customer_buildings) > 0 else 0.0
        
        # İlk kaydından müşteri puanını al
        first_record = customer_buildings.iloc[0]
        
        # Risk score ortalaması
        avg_risk = float(customer_buildings['risk_score'].mean()) if len(customer_buildings) > 0 else 0.0
        total_coverage = int(customer_buildings['max_coverage'].sum()) if len(customer_buildings) > 0 else 0
        
        # Dashboard istatistikleri
        stats = {
            'customer_id': str(customer_id),
            'customer_name': str(first_record['owner_name']),
            'total_policies': int(len(customer_buildings)),
            'active_policies': active_policies,
            'passive_policies': passive_policies,
            'total_coverage': total_coverage,
            'monthly_premium_total': round(total_premiums, 2),
            'next_payment_date': (datetime.now() + timedelta(days=23)).strftime('%Y-%m-%d'),
            'claims_history': 0,
            'claims_pending': 0,
            'referral_code': f"REF{customer_id[-6:]}",
            'referral_earnings': round(random.uniform(100, 2000), 2),
            'customer_score': 85,
            'member_since': '2024-01-15',
            'avg_risk_score': round(avg_risk, 4)
        }
        
        return jsonify({
            'success': True,
            'stats': stats
        }), 200
        
    except Exception as e:
        logger.error(f"Get dashboard stats error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/payment-history/<customer_id>', methods=['GET'])
def get_payment_history(customer_id):
    """
    Müşterinin ödeme geçmişini getir - buildings.csv'den
    
    Args:
        customer_id: Müşteri ID
    """
    try:
        buildings_file = DATA_DIR / 'buildings.csv'
        
        if not buildings_file.exists():
            return jsonify({'error': 'Veri dosyaları bulunamadı'}), 404
        
        buildings_df = pd.read_csv(buildings_file)
        
        # Müşteriye ait binaları bul
        customer_buildings = buildings_df[buildings_df['customer_id'] == customer_id]
        
        if customer_buildings.empty:
            return jsonify({
                'success': True,
                'payments': [],
                'total': 0
            }), 200
        
        # Ödeme geçmişi oluştur (son 6 ay)
        payments = []
        now = datetime.now()
        
        for building in customer_buildings.itertuples():
            # Her bina için son 6 ayın ödemelerini oluştur
            monthly_premium = float(building.monthly_premium_tl)
            policy_start = datetime.strptime(str(building.policy_start_date), '%Y-%m-%d')
            
            # Poliçe başlangıcından bugüne kadar kaç ay geçti
            months_diff = (now.year - policy_start.year) * 12 + (now.month - policy_start.month)
            
            # Son 6 ayın ödemelerini ekle (veya poliçe yaşı kadarını)
            for i in range(min(6, months_diff + 1)):
                payment_date = now - timedelta(days=30 * i)
                
                # Sadece poliçe başlangıcından sonraki ödemeleri ekle
                if payment_date >= policy_start:
                    payments.append({
                        'payment_id': f"PAY-{building.building_id[-4:]}-{i+1}",
                        'policy_number': str(building.policy_number),
                        'building_address': str(building.complete_address)[:50] + '...',
                        'amount': round(monthly_premium, 2),
                        'payment_date': payment_date.strftime('%Y-%m-%d'),
                        'status': 'Tamamlandı' if i > 0 else 'Beklemede',
                        'payment_method': 'Kredi Kartı'
                    })
        
        # Tarihe göre sırala (en yeni en başta)
        payments.sort(key=lambda x: x['payment_date'], reverse=True)
        
        # En fazla 20 ödeme göster
        payments = payments[:20]
        
        return jsonify({
            'success': True,
            'payments': payments,
            'total': len(payments),
            'total_amount': sum(p['amount'] for p in payments if p['status'] == 'Tamamlandı')
        }), 200
        
    except Exception as e:
        logger.error(f"Get payment history error: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ADMIN API ENDPOINTS
# ============================================================================

@app.route('/api/admin/retrain-model', methods=['POST'])
def retrain_model():
    """
    AI modelini yeniden eğit
    
    Returns:
        JSON: Eğitim sonuçları ve performans metrikleri
    """
    global pricing_system
    
    try:
        logger.info("Model yeniden eğitim başlatıldı (Admin isteği)")
        
        # Veriyi yükle
        buildings_file = DATA_DIR / 'buildings.csv'
        if not buildings_file.exists():
            return jsonify({
                'success': False,
                'error': 'Bina verisi bulunamadı'
            }), 404
        
        buildings_df = pd.read_csv(buildings_file, encoding='utf-8-sig')
        
        # Feature extraction
        logger.info("Feature extraction başladı...")
        pricing_system.pricing_model.extract_features(buildings_df)
        
        # Model eğitimi
        logger.info("Model eğitimi başladı...")
        start_time = datetime.now()
        
        pricing_system.pricing_model.train_risk_model(
            pricing_system.pricing_model.features_df
        )
        
        training_duration = (datetime.now() - start_time).total_seconds()
        
        # Model'i kaydet
        model_cache_file = DATA_DIR / 'trained_model.pkl'
        import pickle
        with open(model_cache_file, 'wb') as f:
            pickle.dump(pricing_system.pricing_model, f)
        
        # Performans metrikleri
        metrics = {
            'training_duration_seconds': round(training_duration, 2),
            'training_samples': len(pricing_system.pricing_model.features_df),
            'model_saved': str(model_cache_file),
            'timestamp': datetime.now().isoformat()
        }
        
        # Model performans bilgilerini al (varsa)
        if hasattr(pricing_system.pricing_model, 'model_metrics'):
            metrics.update(pricing_system.pricing_model.model_metrics)
        
        logger.info(f"Model eğitimi tamamlandı: {training_duration:.2f} saniye")
        
        return jsonify({
            'success': True,
            'message': 'Model başarıyla yeniden eğitildi',
            'metrics': metrics
        }), 200
        
    except Exception as e:
        logger.error(f"Model eğitim hatası: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/admin/model-info', methods=['GET'])
def get_model_info():
    """
    Mevcut model bilgilerini getir
    
    Returns:
        JSON: Model performans metrikleri ve bilgileri
    """
    try:
        model_cache_file = DATA_DIR / 'trained_model.pkl'
        
        info = {
            'model_exists': model_cache_file.exists(),
            'model_path': str(model_cache_file)
        }
        
        if model_cache_file.exists():
            import os
            from datetime import datetime
            
            # Dosya bilgileri
            stat = os.stat(model_cache_file)
            info['model_size_mb'] = round(stat.st_size / (1024 * 1024), 2)
            info['last_trained'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            
            # Model metrikleri (varsa)
            if pricing_system and hasattr(pricing_system.pricing_model, 'model_metrics'):
                info['performance'] = pricing_system.pricing_model.model_metrics
            
            # Training data info
            if pricing_system and hasattr(pricing_system.pricing_model, 'features_df'):
                info['training_samples'] = len(pricing_system.pricing_model.features_df)
        
        return jsonify({
            'success': True,
            'info': info
        }), 200
        
    except Exception as e:
        logger.error(f"Model info error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/admin/system-stats', methods=['GET'])
def get_system_stats():
    """
    Sistem istatistiklerini getir
    
    Returns:
        JSON: Sistem performans metrikleri
    """
    try:
        buildings_file = DATA_DIR / 'buildings.csv'
        customers_file = DATA_DIR / 'customers.csv'
        earthquakes_file = DATA_DIR / 'earthquakes.csv'
        
        stats = {
            'data_files': {
                'buildings': {
                    'exists': buildings_file.exists(),
                    'count': 0
                },
                'customers': {
                    'exists': customers_file.exists(),
                    'count': 0
                },
                'earthquakes': {
                    'exists': earthquakes_file.exists(),
                    'count': 0
                }
            },
            'services': {
                'pricing_system': pricing_system is not None,
                'earthquake_analyzer': earthquake_analyzer is not None,
                'building_loader': building_loader is not None,
                'trigger_engine': trigger_engine is not None,
                'blockchain_manager': blockchain_manager is not None
            }
        }
        
        # Veri sayılarını al
        if buildings_file.exists():
            buildings_df = pd.read_csv(buildings_file)
            stats['data_files']['buildings']['count'] = len(buildings_df)
            stats['data_files']['buildings']['total_premium'] = float(buildings_df['annual_premium_tl'].sum())
            stats['data_files']['buildings']['avg_premium'] = float(buildings_df['annual_premium_tl'].mean())
        
        if customers_file.exists():
            customers_df = pd.read_csv(customers_file)
            stats['data_files']['customers']['count'] = len(customers_df)
        
        if earthquakes_file.exists():
            earthquakes_df = pd.read_csv(earthquakes_file)
            stats['data_files']['earthquakes']['count'] = len(earthquakes_df)
        
        # Blockchain stats (basit)
        if blockchain_manager:
            stats['blockchain'] = {
                'policies_recorded': blockchain_manager.stats.get('policies_recorded', 0),
                'policies_skipped': blockchain_manager.stats.get('policies_skipped', 0),
                'earthquakes_recorded': blockchain_manager.stats.get('earthquakes_recorded', 0),
                'payouts_recorded': blockchain_manager.stats.get('payouts_recorded', 0),
                'queue_size': blockchain_manager.stats.get('queue_size', 0),
                'errors': blockchain_manager.stats.get('errors', 0)
            }
        
        return jsonify({
            'success': True,
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"System stats error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/admin/load-policies-to-blockchain', methods=['POST'])
def load_policies_to_blockchain():
    """
    Aktif poliçeleri blockchain'e yükle
    
    Returns:
        JSON: Yükleme sonuçları
    """
    global blockchain_manager
    
    try:
        logger.info("Aktif poliçeler blockchain'e yükleniyor (Admin isteği)")
        
        # Veri dosyalarını kontrol et
        buildings_file = DATA_DIR / 'buildings.csv'
        if not buildings_file.exists():
            return jsonify({
                'success': False,
                'error': 'Bina verisi bulunamadı'
            }), 404
        
        # Verileri yükle
        buildings_df = pd.read_csv(buildings_file, encoding='utf-8-sig')
        
        # Aktif poliçeleri filtrele
        active_buildings = buildings_df[buildings_df['policy_status'] == 'Aktif'].copy()
        
        if len(active_buildings) == 0:
            return jsonify({
                'success': False,
                'error': 'Aktif poliçe bulunamadı'
            }), 404
        
        # İstatistikler
        stats = {
            'total': len(active_buildings),
            'success': 0,
            'skipped': 0,
            'failed': 0
        }
        
        logger.info(f"{len(active_buildings):,} aktif poliçe bulundu")
        
        # Her aktif poliçeyi blockchain'e kaydet
        for idx, building in active_buildings.iterrows():
            try:
                # Poliçe verisi hazırla
                policy_data = {
                    'customer_id': building['customer_id'],
                    'building_id': building['building_id'],
                    'policy_number': building['policy_number'],
                    'policy_id': building['policy_number'],
                    'package_type': building['package_type'],
                    'max_coverage': int(building['max_coverage']),
                    'coverage_amount': int(building['max_coverage']),
                    'annual_premium_tl': float(building['annual_premium_tl']),
                    'latitude': float(building['latitude']),
                    'longitude': float(building['longitude']),
                    'start_date': building['policy_start_date'],
                    'owner_name': building['owner_name'],
                    'city': building['city'],
                    'district': building['district']
                }
                
                # Blockchain'e kaydet
                result = blockchain_manager.record_policy(policy_data)
                
                if result is not None:
                    if result > 0 or result == -1:  # Başarılı veya queue'ya eklendi
                        stats['success'] += 1
                    else:
                        stats['skipped'] += 1
                else:
                    stats['skipped'] += 1
                    
            except Exception as e:
                stats['failed'] += 1
                logger.error(f"Policy kayıt hatası ({building.get('policy_number', 'N/A')}): {e}")
        
        logger.info(f"Blockchain yükleme tamamlandı: {stats['success']:,} başarılı, {stats['skipped']:,} atlandı, {stats['failed']:,} hata")
        
        return jsonify({
            'success': True,
            'message': 'Poliçeler blockchain\'e yüklendi',
            'stats': stats
        }), 200
        
    except Exception as e:
        logger.error(f"Load policies to blockchain error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'message': 'Endpoint bulunamadı'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'message': 'Sunucu hatası'
    }), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    # Backend'i başlat
    initialize_backend()
    
    # Flask uygulamasını çalıştır
    print("\n" + "="*80)
    print("🌐 FLASK SERVER BAŞLATILIYOR...")
    print("="*80)
    print("\n📍 Ana Sayfa: http://localhost:5000")
    print("📍 Admin Panel: http://localhost:5000/admin")
    print("📍 Blockchain Stats: http://localhost:5000/api/blockchain/stats")
    print("\n💡 Çıkmak için: CTRL+C\n")
    
    try:
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=True,
            use_reloader=False  # Backend'in tekrar başlatılmasını önle
        )
    finally:
        # Uygulama kapanırken blockchain manager'ı kapat
        if blockchain_manager:
            print("\n🛑 Blockchain Manager kapatılıyor...")
            blockchain_manager.shutdown()
