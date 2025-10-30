# -*- coding: utf-8 -*-
"""
DASK+ Blockchain Hibrit Entegrasyon Yöneticisi
==============================================

Bu modül, mevcut DASK+ sistemine blockchain katmanını ekler.
✅ Ana sistemdeki hiçbir fonksiyon değiştirilmez
✅ Blockchain kayıtları arka planda asenkron çalışır
✅ Blockchain hatası ana sistemi DURDURMAZ

KULLANIM:
    from blockchain_manager import BlockchainManager
    
    blockchain = BlockchainManager()
    
    # Poliçe oluşturulduğunda
    blockchain.record_policy(policy_data)
    
    # Deprem algılandığında
    blockchain.record_earthquake(earthquake_data)
    
    # Ödeme yapıldığında
    blockchain.record_payout(payout_data)
"""

import sys
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import logging
from threading import Thread, Lock
from queue import Queue, Empty
import json
from typing import Dict, Optional, List

# Blockchain service'i import et (artık src/ klasöründe)
try:
    from blockchain_service import BlockchainService
except ImportError:
    BlockchainService = None
    logging.warning("⚠️ blockchain_service modülü yüklenemedi. Blockchain devre dışı olacak.")

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# BLOCKCHAIN YÖNETIM KATMANI
# =============================================================================

class BlockchainManager:
    """
    Blockchain Hibrit Entegrasyon Yöneticisi
    
    ÖZELLİKLER:
    1. Asenkron işlem (ana sistemi yavaşlatmaz)
    2. Hata toleransı (blockchain hatası = sistem devam eder)
    3. Önbellekleme (yoğun zamanlarda kuyruk)
    4. Seçici kayıt (sadece önemli olaylar)
    5. İstatistik toplama
    """
    
    def __init__(self, 
                 enable_blockchain=True,
                 async_mode=True,
                 record_threshold=None,
                 data_dir=None,
                 skip_existing=True):
        """
        Args:
            enable_blockchain: Blockchain'i aktifleştir/devre dışı bırak
            async_mode: Asenkron mod (arka planda kayıt)
            record_threshold: Hangi olayları kaydet (None=hepsi, dict=filtreleme)
            data_dir: Veri dizini (buildings.csv için)
            skip_existing: Zaten kaydedilmiş poliçeleri atla
        """
        self.enabled = enable_blockchain
        self.async_mode = async_mode
        self.data_dir = data_dir or str(Path(__file__).parent.parent / 'data')
        self.skip_existing = skip_existing
        
        # Zaten kaydedilmiş poliçeleri yükle
        self.recorded_policies = set()
        if self.skip_existing:
            self._load_recorded_policies()
        
        # Blockchain servisini başlat
        if self.enabled and BlockchainService is not None:
            try:
                self.blockchain = BlockchainService()
                logger.info("✅ Blockchain servisi başlatıldı")
            except Exception as e:
                logger.error(f"❌ Blockchain servisi başlatılamadı: {e}")
                self.enabled = False
                self.blockchain = None
        else:
            self.blockchain = None
            if BlockchainService is None:
                logger.warning("⚠️ BlockchainService modülü bulunamadı, blockchain devre dışı")
            else:
                logger.info("⚠️ Blockchain servisi devre dışı")
        
        # Filtreleme eşikleri
        if record_threshold is None:
            self.threshold = {
                'policy_min_coverage': 0,  # Tüm poliçeler
                'earthquake_min_magnitude': 5.0,  # M5.0+
                'payout_min_amount': 0  # Tüm ödemeler
            }
        else:
            self.threshold = record_threshold
        
        # Asenkron işlem için kuyruk
        if self.async_mode and self.enabled:
            self.queue = Queue(maxsize=10000)
            self.worker_thread = Thread(target=self._process_queue, daemon=True)
            self.worker_thread.start()
            logger.info("✅ Asenkron blockchain worker başlatıldı")
        else:
            self.queue = None
            self.worker_thread = None
        
        # İstatistikler
        self.stats = {
            'policies_recorded': 0,
            'policies_skipped': 0,
            'earthquakes_recorded': 0,
            'earthquakes_skipped': 0,
            'payouts_recorded': 0,
            'payouts_skipped': 0,
            'errors': 0,
            'queue_size': 0
        }
        self.stats_lock = Lock()
    
    # =========================================================================
    # KAYITLI POLİÇELERİ YÜKLEME
    # =========================================================================
    
    def _load_recorded_policies(self):
        """Daha önce blockchain'e kaydedilmiş poliçeleri yükle"""
        try:
            records_file = Path(self.data_dir) / 'blockchain_records.csv'
            if records_file.exists():
                df = pd.read_csv(records_file)
                # RECORDED ve SUCCESS durumundaki poliçeleri kaydet
                recorded = df[df['status'].isin(['RECORDED', 'SUCCESS'])]['policy_id'].unique()
                self.recorded_policies = set(recorded)
                logger.info(f"✅ {len(self.recorded_policies)} kayıtlı poliçe yüklendi (tekrar kaydedilmeyecek)")
            else:
                logger.info("ℹ️ Daha önce kaydedilmiş poliçe bulunamadı")
        except Exception as e:
            logger.warning(f"⚠️ Kayıtlı poliçeler yüklenemedi: {e}")
            self.recorded_policies = set()
    
    # =========================================================================
    # POLİÇE KAYDI
    # =========================================================================
    
    def record_policy(self, policy_data: Dict) -> Optional[int]:
        """
        Poliçeyi blockchain'e kaydet
        
        Args:
            policy_data: Poliçe bilgileri dict
                {
                    'customer_id': str,
                    'building_id': str,
                    'package_type': str,
                    'max_coverage': int,
                    'annual_premium_tl': float,
                    'latitude': float,
                    'longitude': float,
                    'policy_number': str (opsiyonel),
                    'policy_id': str (opsiyonel),
                    'start_date': str (opsiyonel)
                }
        
        Returns:
            Policy ID (blockchain) or None
        """
        if not self.enabled:
            return None
        
        # Duplicate kontrolü - zaten kaydedilmiş mi?
        policy_id = policy_data.get('policy_id') or policy_data.get('policy_number')
        if self.skip_existing and policy_id and policy_id in self.recorded_policies:
            with self.stats_lock:
                self.stats['policies_skipped'] += 1
            return None
        
        # Filtreleme (hem max_coverage hem coverage_amount destekle)
        coverage = policy_data.get('max_coverage') or policy_data.get('coverage_amount', 0)
        if coverage < self.threshold['policy_min_coverage']:
            with self.stats_lock:
                self.stats['policies_skipped'] += 1
            return None
        
        # Asenkron mod
        if self.async_mode:
            try:
                self.queue.put(('policy', policy_data), block=False)
                with self.stats_lock:
                    self.stats['queue_size'] = self.queue.qsize()
                return -1  # Placeholder (gerçek ID kuyruktan sonra)
            except:
                logger.warning("⚠️ Blockchain kuyruğu dolu, policy kaydedilemiyor")
                with self.stats_lock:
                    self.stats['policies_skipped'] += 1
                return None
        
        # Senkron mod
        return self._record_policy_sync(policy_data)
    
    def _record_policy_sync(self, policy_data: Dict) -> Optional[int]:
        """Poliçeyi senkron kaydet"""
        try:
            # Veri doğrulama - None değerleri kontrol et
            coverage = policy_data.get('max_coverage') or policy_data.get('coverage_amount')
            latitude = policy_data.get('latitude')
            longitude = policy_data.get('longitude')
            premium = policy_data.get('annual_premium_tl') or policy_data.get('annual_premium', 0)
            
            # Gerekli alanların None olup olmadığını kontrol et
            if coverage is None or latitude is None or longitude is None:
                logger.warning(f"⚠️ Eksik veri, policy atlandı: coverage={coverage}, lat={latitude}, lon={longitude}")
                with self.stats_lock:
                    self.stats['policies_skipped'] += 1
                return None
            
            # Coverage ve premium'u int/float'a çevir
            coverage = int(float(coverage))
            premium = int(float(premium))
            latitude = float(latitude)
            longitude = float(longitude)
            
            policy_id = self.blockchain.create_policy_on_chain(
                customer_id=policy_data.get('customer_id'),
                coverage_amount=coverage,
                latitude=latitude,
                longitude=longitude,
                premium=premium,
                package_type=policy_data.get('package_type', 'Standart'),
                verbose=False  # Toplu yüklemede verbose kapalı
            )
            
            with self.stats_lock:
                self.stats['policies_recorded'] += 1
            
            # Sadece hata durumunda log
            # logger.info(f"✅ Policy {policy_id} blockchain'e kaydedildi")
            return policy_id
            
        except Exception as e:
            logger.error(f"❌ Policy blockchain kaydı hatası: {e}")
            with self.stats_lock:
                self.stats['errors'] += 1
            return None
    
    # =========================================================================
    # DEPREM KAYDI
    # =========================================================================
    
    def record_earthquake(self, earthquake_data: Dict) -> bool:
        """
        Depremi blockchain'e kaydet
        
        Args:
            earthquake_data: Deprem bilgileri
                {
                    'event_id': str,
                    'magnitude': float,
                    'latitude': float,
                    'longitude': float,
                    'depth_km': float,
                    'timestamp': datetime or str
                }
        
        Returns:
            True/False (başarı)
        """
        if not self.enabled:
            return False
        
        # Filtreleme
        if earthquake_data.get('magnitude', 0) < self.threshold['earthquake_min_magnitude']:
            with self.stats_lock:
                self.stats['earthquakes_skipped'] += 1
            return False
        
        # Asenkron mod
        if self.async_mode:
            try:
                self.queue.put(('earthquake', earthquake_data), block=False)
                with self.stats_lock:
                    self.stats['queue_size'] = self.queue.qsize()
                return True
            except:
                logger.warning("⚠️ Blockchain kuyruğu dolu, earthquake kaydedilemiyor")
                with self.stats_lock:
                    self.stats['earthquakes_skipped'] += 1
                return False
        
        # Senkron mod
        return self._record_earthquake_sync(earthquake_data)
    
    def _record_earthquake_sync(self, earthquake_data: Dict) -> bool:
        """Depremi senkron kaydet"""
        try:
            # Event ID yoksa oluştur
            if 'event_id' not in earthquake_data:
                earthquake_data['event_id'] = f"eq_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Koordinatları blockchain formatına çevir (1e8 precision)
            lat_blockchain = int(earthquake_data['latitude'] * 1e8)
            lon_blockchain = int(earthquake_data['longitude'] * 1e8)
            mag_blockchain = int(earthquake_data['magnitude'] * 10)  # M6.5 -> 65
            
            # Blockchain'e kaydet (timestamp blockchain tarafından otomatik eklenir)
            self.blockchain.report_earthquake_all_oracles(
                event_id=earthquake_data['event_id'],
                magnitude=mag_blockchain,
                latitude=lat_blockchain,
                longitude=lon_blockchain
            )
            
            with self.stats_lock:
                self.stats['earthquakes_recorded'] += 1
            
            logger.info(f"✅ Earthquake {earthquake_data['event_id']} blockchain'e kaydedildi")
            return True
            
        except Exception as e:
            logger.error(f"❌ Earthquake blockchain kaydı hatası: {e}")
            with self.stats_lock:
                self.stats['errors'] += 1
            return False
    
    # =========================================================================
    # ÖDEME KAYDI
    # =========================================================================
    
    def record_payout(self, payout_data: Dict) -> bool:
        """
        Ödemeyi blockchain'e kaydet
        
        Args:
            payout_data: Ödeme bilgileri
                {
                    'policy_id': int (blockchain),
                    'event_id': str,
                    'amount': float,
                    'trigger_type': str,
                    'payout_date': datetime or str
                }
        
        Returns:
            True/False (başarı)
        """
        if not self.enabled:
            return False
        
        # Filtreleme
        if payout_data.get('amount', 0) < self.threshold['payout_min_amount']:
            with self.stats_lock:
                self.stats['payouts_skipped'] += 1
            return False
        
        # Asenkron mod
        if self.async_mode:
            try:
                self.queue.put(('payout', payout_data), block=False)
                with self.stats_lock:
                    self.stats['queue_size'] = self.queue.qsize()
                return True
            except:
                logger.warning("⚠️ Blockchain kuyruğu dolu, payout kaydedilemiyor")
                with self.stats_lock:
                    self.stats['payouts_skipped'] += 1
                return False
        
        # Senkron mod
        return self._record_payout_sync(payout_data)
    
    def _record_payout_sync(self, payout_data: Dict) -> bool:
        """Ödemeyi senkron kaydet"""
        try:
            # Request payout
            tx_id = self.blockchain.request_payout(
                policy_id=payout_data['policy_id'],
                earthquake_id=payout_data['event_id']
            )
            
            # Execute payout
            result = self.blockchain.execute_payout(tx_id)
            
            if result:
                with self.stats_lock:
                    self.stats['payouts_recorded'] += 1
                
                logger.info(f"✅ Payout {tx_id} blockchain'e kaydedildi")
                return True
            else:
                logger.warning(f"⚠️ Payout {tx_id} execute edilemedi")
                with self.stats_lock:
                    self.stats['payouts_skipped'] += 1
                return False
            
        except Exception as e:
            logger.error(f"❌ Payout blockchain kaydı hatası: {e}")
            with self.stats_lock:
                self.stats['errors'] += 1
            return False
    
    # =========================================================================
    # TOPLU KAYIT (CSV'DEN)
    # =========================================================================
    
    def bulk_record_policies(self, limit: int = None) -> Dict:
        """
        buildings.csv'den toplu poliçe kaydı
        
        Args:
            limit: Kaç poliçe kaydedilecek (None=hepsi)
        
        Returns:
            İstatistik dict
        """
        if not self.enabled:
            logger.warning("⚠️ Blockchain devre dışı, toplu kayıt yapılamıyor")
            return {'success': False, 'message': 'Blockchain devre dışı'}
        
        buildings_file = Path(self.data_dir) / 'buildings.csv'
        
        if not buildings_file.exists():
            logger.error(f"❌ Bina verisi bulunamadı: {buildings_file}")
            return {'success': False, 'message': 'Veri dosyası bulunamadı'}
        
        try:
            df = pd.read_csv(buildings_file, encoding='utf-8-sig')
            
            if limit:
                df = df.head(limit)
            
            logger.info(f"📂 {len(df)} poliçe yüklendi, blockchain'e kaydediliyor...")
            
            recorded = 0
            skipped = 0
            errors = 0
            
            for idx, row in df.iterrows():
                try:
                    # None değerleri kontrol et ve filtrele
                    if pd.isna(row.get('latitude')) or pd.isna(row.get('longitude')):
                        skipped += 1
                        continue
                    
                    if pd.isna(row.get('max_coverage')) or pd.isna(row.get('insurance_value_tl')):
                        skipped += 1
                        continue
                    
                    policy_data = {
                        'customer_id': str(row['customer_id']),
                        'building_id': str(row['building_id']),
                        'package_type': str(row.get('package_type', 'Standart')),
                        'max_coverage': int(float(row.get('insurance_value_tl', row.get('max_coverage', 0)))),
                        'annual_premium_tl': float(row.get('annual_premium_tl', 0)),
                        'latitude': float(row['latitude']),
                        'longitude': float(row['longitude']),
                        'policy_number': str(row.get('policy_number', f"DP-{row['building_id']}"))
                    }
                    
                    result = self.record_policy(policy_data)
                    
                    if result is not None and result >= 0:
                        recorded += 1
                    elif result == -1:
                        recorded += 1  # Kuyruğa eklendi
                    else:
                        skipped += 1
                    
                except Exception as e:
                    logger.warning(f"⚠️ Satır {idx} işlenirken hata: {e}")
                    errors += 1
                    skipped += 1
                
                # İlerleme göstergesi
                if (idx + 1) % 100 == 0:
                    logger.info(f"   📊 İlerleme: {idx + 1}/{len(df)}")
            
            logger.info(f"✅ Toplu kayıt tamamlandı: {recorded} kaydedildi, {skipped} atlandı")
            
            return {
                'success': True,
                'total': len(df),
                'recorded': recorded,
                'skipped': skipped,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"❌ Toplu kayıt hatası: {e}")
            return {'success': False, 'message': str(e)}
    
    def bulk_sync_with_logging(self, batch_size: int = 100) -> Dict:
        """
        Detaylı loglama ile toplu blockchain senkronizasyonu
        
        Args:
            batch_size: Batch işleme boyutu
        
        Returns:
            İstatistik dict
        """
        from datetime import datetime
        import time
        
        if not self.enabled:
            logger.warning("⚠️ Blockchain devre dışı")
            return {'success': False, 'message': 'Blockchain devre dışı'}
        
        buildings_file = Path(self.data_dir) / 'buildings.csv'
        
        if not buildings_file.exists():
            logger.error(f"❌ Veri dosyası bulunamadı: {buildings_file}")
            return {'success': False, 'message': 'Veri dosyası bulunamadı'}
        
        try:
            # CSV yükle
            df = pd.read_csv(buildings_file, encoding='utf-8-sig')
            df = df.dropna(subset=['latitude', 'longitude'])
            
            logger.info(f"✅ {len(df)} geçerli poliçe yüklendi")
            
            # Log dosyaları
            blockchain_records_file = Path(self.data_dir) / 'blockchain_records.csv'
            operations_log_file = Path(self.data_dir) / 'blockchain_operations.log'
            
            # Log başlat
            with open(operations_log_file, 'w', encoding='utf-8') as f:
                f.write("="*80 + "\n")
                f.write("DASK+ BLOCKCHAIN TOPLU SENKRONİZASYON LOG\n")
                f.write("="*80 + "\n")
                f.write(f"Başlangıç: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Toplam Poliçe: {len(df)}\n")
                f.write("="*80 + "\n\n")
            
            # Kayıt listesi
            blockchain_records = []
            
            # İstatistikler
            stats = {
                'total': len(df),
                'recorded': 0,
                'skipped': 0,
                'high_value': 0,
                'medium_value': 0,
                'low_value': 0,
                'start_time': datetime.now(),
                'errors': 0
            }
            
            logger.info("🚀 Toplu kayıt başlıyor...")
            
            # Batch işleme
            total_batches = (len(df) + batch_size - 1) // batch_size
            
            for batch_num in range(total_batches):
                start_idx = batch_num * batch_size
                end_idx = min(start_idx + batch_size, len(df))
                batch_df = df.iloc[start_idx:end_idx]
                
                for idx, row in batch_df.iterrows():
                    try:
                        if pd.isna(row.get('latitude')) or pd.isna(row.get('longitude')):
                            stats['skipped'] += 1
                            continue
                        
                        if pd.isna(row.get('insurance_value_tl')):
                            stats['skipped'] += 1
                            continue
                        
                        # Poliçe verisi
                        policy_data = {
                            'policy_id': f"DP-{row['building_id']}",
                            'customer_id': str(row['customer_id']),
                            'building_id': str(row['building_id']),
                            'coverage_amount': float(row.get('insurance_value_tl')),
                            'annual_premium': float(row.get('annual_premium_tl', 0)),
                            'latitude': float(row['latitude']),
                            'longitude': float(row['longitude']),
                            'package_type': str(row.get('package_type', 'Standart'))
                        }
                        
                        # Kategori
                        coverage = policy_data['coverage_amount']
                        if coverage >= 1500000:
                            category = 'high'
                            stats['high_value'] += 1
                        elif coverage >= 750000:
                            category = 'medium'
                            stats['medium_value'] += 1
                        else:
                            category = 'low'
                            stats['low_value'] += 1
                        
                        # Blockchain'e kaydet
                        success = self.record_policy(policy_data)
                        
                        if success:
                            stats['recorded'] += 1
                            status = 'RECORDED'
                        else:
                            stats['skipped'] += 1
                            status = 'SKIPPED'
                        
                        # Log kaydı
                        blockchain_records.append({
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'policy_id': policy_data['policy_id'],
                            'customer_id': policy_data['customer_id'],
                            'coverage': coverage,
                            'category': category,
                            'status': status
                        })
                        
                    except Exception as e:
                        stats['errors'] += 1
                        with open(operations_log_file, 'a', encoding='utf-8') as f:
                            f.write(f"❌ HATA: {str(e)}\n")
                
                # İlerleme
                progress = (end_idx / len(df)) * 100
                logger.info(f"📊 İlerleme: {end_idx}/{len(df)} ({progress:.1f}%)")
            
            logger.info("⏳ İşlemler tamamlanıyor...")
            time.sleep(5)
            
            # İstatistikler
            stats['end_time'] = datetime.now()
            stats['duration'] = (stats['end_time'] - stats['start_time']).total_seconds()
            
            # Kayıtları CSV'ye yaz
            logger.info("💾 Kayıtlar kaydediliyor...")
            records_df = pd.DataFrame(blockchain_records)
            records_df.to_csv(blockchain_records_file, index=False, encoding='utf-8')
            
            # Detaylı log yaz
            with open(operations_log_file, 'a', encoding='utf-8') as f:
                f.write("\n" + "="*80 + "\n")
                f.write("SONUÇ\n")
                f.write("="*80 + "\n")
                f.write(f"Bitiş: {stats['end_time'].strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Süre: {stats['duration']:.2f} saniye\n")
                f.write(f"Kaydedilen: {stats['recorded']}\n")
                f.write(f"Atlanan: {stats['skipped']}\n")
                f.write(f"Hatalar: {stats['errors']}\n")
                f.write(f"Yüksek Değerli: {stats['high_value']}\n")
                f.write(f"Orta Değerli: {stats['medium_value']}\n")
                f.write(f"Düşük Değerli: {stats['low_value']}\n")
            
            logger.info(f"✅ Toplu senkronizasyon tamamlandı")
            logger.info(f"   Süre: {stats['duration']:.2f} saniye")
            logger.info(f"   Kaydedilen: {stats['recorded']}/{stats['total']}")
            logger.info(f"   📁 {blockchain_records_file}")
            logger.info(f"   📁 {operations_log_file}")
            
            return {
                'success': True,
                'total': stats['total'],
                'recorded': stats['recorded'],
                'skipped': stats['skipped'],
                'errors': stats['errors'],
                'duration': stats['duration'],
                'files': {
                    'records': str(blockchain_records_file),
                    'log': str(operations_log_file)
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Toplu senkronizasyon hatası: {e}")
            return {'success': False, 'message': str(e)}
    
    # =========================================================================
    # ASENKRON KUYRUK İŞLEMCİSİ
    # =========================================================================
    
    def _process_queue(self):
        """Arka planda kuyruktan işlem çeker"""
        logger.info("🔄 Blockchain worker thread başladı")
        
        while True:
            try:
                # Kuyruktan al (1 saniye timeout)
                item = self.queue.get(timeout=1.0)
                
                if item is None:
                    break  # Poison pill
                
                event_type, data = item
                
                # İşlemi yap
                if event_type == 'policy':
                    self._record_policy_sync(data)
                elif event_type == 'earthquake':
                    self._record_earthquake_sync(data)
                elif event_type == 'payout':
                    self._record_payout_sync(data)
                
                # Kuyruk boyutunu güncelle
                with self.stats_lock:
                    self.stats['queue_size'] = self.queue.qsize()
                
            except Empty:
                # Kuyruk boş, devam et
                continue
            except Exception as e:
                logger.error(f"❌ Worker thread hatası: {e}")
                with self.stats_lock:
                    self.stats['errors'] += 1
    
    # =========================================================================
    # İSTATİSTİKLER
    # =========================================================================
    
    def get_stats(self) -> Dict:
        """Blockchain istatistiklerini getir"""
        with self.stats_lock:
            return self.stats.copy()
    
    def print_stats(self):
        """İstatistikleri yazdır"""
        stats = self.get_stats()
        
        print("\n" + "="*60)
        print("📊 BLOCKCHAIN ENTEGRASYON İSTATİSTİKLERİ")
        print("="*60)
        
        print(f"\n✅ POLİÇELER:")
        print(f"   Kaydedilen: {stats['policies_recorded']:,}")
        print(f"   Atlanan: {stats['policies_skipped']:,}")
        
        print(f"\n🌍 DEPREMLER:")
        print(f"   Kaydedilen: {stats['earthquakes_recorded']:,}")
        print(f"   Atlanan: {stats['earthquakes_skipped']:,}")
        
        print(f"\n💰 ÖDEMELER:")
        print(f"   Kaydedilen: {stats['payouts_recorded']:,}")
        print(f"   Atlanan: {stats['payouts_skipped']:,}")
        
        print(f"\n⚠️ HATALAR: {stats['errors']:,}")
        
        if self.async_mode:
            print(f"\n📦 KUYRUK BOYUTU: {stats['queue_size']:,}")
        
        print("="*60 + "\n")
    
    # =========================================================================
    # BLOCKCHAIN SORGULAMA
    # =========================================================================
    
    def get_policy_from_blockchain(self, policy_id: int) -> Optional[Dict]:
        """Blockchain'den poliçe sorgula"""
        if not self.enabled or not self.blockchain:
            return None
        
        try:
            policy = self.blockchain.get_policy_details(policy_id)
            return policy
        except Exception as e:
            logger.error(f"❌ Policy sorgulama hatası: {e}")
            return None
    
    def get_earthquake_from_blockchain(self, event_id: str) -> Optional[Dict]:
        """Blockchain'den deprem sorgula"""
        if not self.enabled or not self.blockchain:
            return None
        
        try:
            # Not implemented in blockchain_service yet
            # earthquake = self.blockchain.get_earthquake(event_id)
            logger.warning(f"⚠️ Earthquake query not yet implemented")
            return None
        except Exception as e:
            logger.error(f"❌ Earthquake sorgulama hatası: {e}")
            return None
    
    def get_contract_stats(self) -> Dict:
        """Smart contract istatistiklerini getir"""
        if not self.enabled or not self.blockchain:
            return {}
        
        try:
            stats = self.blockchain.get_contract_stats()
            return stats
        except Exception as e:
            logger.error(f"❌ Contract stats hatası: {e}")
            return {}
    
    # =========================================================================
    # KAPATMA
    # =========================================================================
    
    def shutdown(self):
        """Blockchain manager'ı kapat"""
        logger.info("🛑 Blockchain manager kapatılıyor...")
        
        if self.async_mode and self.worker_thread:
            # Poison pill gönder
            self.queue.put(None)
            
            # Thread'in bitmesini bekle (max 5 saniye)
            self.worker_thread.join(timeout=5.0)
            
            if self.worker_thread.is_alive():
                logger.warning("⚠️ Worker thread hala çalışıyor")
        
        self.print_stats()
        logger.info("✅ Blockchain manager kapatıldı")


# =============================================================================
# GELİŞMİŞ ÖZELLIKLER: AKILLI FİLTRELEME
# =============================================================================

class SmartBlockchainFilter:
    """
    Akıllı blockchain filtreleme stratejisi
    
    Sadece kritik olayları blockchain'e kaydet:
    - Yüksek değerli poliçeler
    - Büyük depremler
    - Önemli ödemeler
    """
    
    @staticmethod
    def should_record_policy(policy_data: Dict) -> bool:
        """Bu poliçe blockchain'e kaydedilmeli mi?"""
        
        # Strateji 1: Yüksek teminat (>500K)
        if policy_data.get('max_coverage', 0) > 500_000:
            return True
        
        # Strateji 2: Premium paket
        if policy_data.get('package_type') == 'premium':
            return True
        
        # Strateji 3: Yüksek risk skoru (>0.7)
        if policy_data.get('risk_score', 0) > 0.7:
            return True
        
        # Strateji 4: Rastgele %10 örnekleme (audit trail için)
        import random
        if random.random() < 0.10:
            return True
        
        return False
    
    @staticmethod
    def should_record_earthquake(earthquake_data: Dict) -> bool:
        """Bu deprem blockchain'e kaydedilmeli mi?"""
        
        # Sadece M5.0+ depremler
        if earthquake_data.get('magnitude', 0) >= 5.0:
            return True
        
        return False
    
    @staticmethod
    def should_record_payout(payout_data: Dict) -> bool:
        """Bu ödeme blockchain'e kaydedilmeli mi?"""
        
        # Tüm ödemeler blockchain'e (audit trail)
        return True


# =============================================================================
# ÖRNEK KULLANIM
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("BLOCKCHAIN MANAGER TEST")
    print("="*60)
    
    # Blockchain manager'ı başlat
    blockchain = BlockchainManager(
        enable_blockchain=True,
        async_mode=True
    )
    
    # Test 1: Tek poliçe kaydet
    print("\n1️⃣ Tek poliçe testi...")
    test_policy = {
        'customer_id': 'CUST000001',
        'building_id': 'BLD_000001',
        'package_type': 'Standart',
        'max_coverage': 750_000,
        'annual_premium_tl': 5_132.47,
        'latitude': 41.0181,
        'longitude': 28.9784
    }
    
    policy_id = blockchain.record_policy(test_policy)
    print(f"   ✅ Policy ID: {policy_id}")
    
    # Test 2: Deprem kaydet
    print("\n2️⃣ Deprem testi...")
    test_earthquake = {
        'event_id': 'eq_test_001',
        'magnitude': 6.5,
        'latitude': 40.7589,
        'longitude': 29.9284,
        'depth_km': 10.0,
        'timestamp': datetime.now()
    }
    
    result = blockchain.record_earthquake(test_earthquake)
    print(f"   ✅ Earthquake kaydedildi: {result}")
    
    # Test 3: Toplu kayıt (ilk 10 poliçe)
    print("\n3️⃣ Toplu kayıt testi (ilk 10 poliçe)...")
    bulk_result = blockchain.bulk_record_policies(limit=10)
    print(f"   ✅ Toplu kayıt: {bulk_result}")
    
    # Test 4: Detaylı loglama ile toplu senkronizasyon (ilk 20 poliçe)
    print("\n4️⃣ Detaylı loglama ile senkronizasyon testi...")
    sync_result = blockchain.bulk_sync_with_logging(batch_size=10)
    if sync_result['success']:
        print(f"   ✅ Senkronizasyon tamamlandı:")
        print(f"      - Toplam: {sync_result['total']}")
        print(f"      - Kaydedilen: {sync_result['recorded']}")
        print(f"      - Süre: {sync_result['duration']:.2f}s")
        print(f"      - Log: {sync_result['files']['log']}")
    
    # İstatistikler
    blockchain.print_stats()
    
    # Kapatma
    blockchain.shutdown()
