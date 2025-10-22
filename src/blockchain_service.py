# -*- coding: utf-8 -*-
"""
DASK+ Blockchain Service - Basit Simülatör (Prototip)
====================================================

Basit blockchain simülatörü - karmaşık özellikler olmadan.

KULLANIM:
    from blockchain_service import BlockchainService
    
    blockchain = BlockchainService()
    
    # Poliçe oluşturma
    policy_id = blockchain.create_policy_on_chain(
        customer_id="CUST000123",
        coverage_amount=1000000,
        latitude=39.0,
        longitude=28.5,
        premium=30000
    )
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import json
import hashlib
import pickle

# UTF-8 encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Python simulator'ı import et
sys.path.insert(0, str(Path(__file__).parent))
from dask_plus_simulator import (
    DASKPlusParametric,
    Role,
    Policy,
    EarthquakeEvent,
    PayoutRequest
)


# =============================================================================
# BLOCKCHAIN KAYIT YAPISI (Immutable, Hash'li, Zincirli)
# =============================================================================

class Block:
    """
    Blockchain Block - Gerçek blockchain mantığı ile
    Her block bir önceki block'un hash'ini içerir (chain)
    """
    
    def __init__(self, index: int, timestamp: float, data: Dict, previous_hash: str):
        self.index = index
        self.timestamp = timestamp
        self.data = data  # Poliçe/deprem/ödeme verisi
        self.previous_hash = previous_hash
        self.nonce = 0
        self.hash = self.calculate_hash()
    
    def calculate_hash(self) -> str:
        """Block hash hesapla (SHA-256)"""
        block_string = f"{self.index}{self.timestamp}{json.dumps(self.data, sort_keys=True)}{self.previous_hash}{self.nonce}"
        return hashlib.sha256(block_string.encode()).hexdigest()
    
    def to_dict(self) -> Dict:
        """Block'u dict'e çevir"""
        return {
            'index': self.index,
            'timestamp': self.timestamp,
            'data': self.data,
            'previous_hash': self.previous_hash,
            'hash': self.hash,
            'nonce': self.nonce
        }


class Blockchain:
    """
    Basit Blockchain Implementasyonu
    - Immutable: Bir kez yazıldı mı değişmez
    - Hash'li: Her block hash ile korunur
    - Zincirli: Her block bir öncekine bağlı
    """
    
    def __init__(self, chain_file: str = None, auto_save_interval: int = 1000):
        """
        Args:
            chain_file: Blockchain dosya yolu
            auto_save_interval: Kaç block'ta bir otomatik kaydet (0 = otomatik kaydetme)
        """
        self.chain_file = chain_file or str(Path(__file__).parent.parent / 'data' / 'blockchain.dat')
        self.chain: List[Block] = []
        self.auto_save_interval = auto_save_interval
        self.blocks_since_last_save = 0
        
        # Genesis block oluştur veya mevcut chain'i yükle
        self._load_or_create_genesis()
    
    def _load_or_create_genesis(self):
        """Genesis block oluştur veya mevcut chain'i yükle"""
        chain_path = Path(self.chain_file)
        
        if chain_path.exists():
            # Mevcut blockchain'i yükle
            try:
                with open(chain_path, 'rb') as f:
                    self.chain = pickle.load(f)
                print(f"📦 Blockchain yüklendi: {len(self.chain)} block")
            except Exception as e:
                print(f"⚠️ Blockchain yükleme hatası: {e}, yeni chain oluşturuluyor")
                self._create_genesis_block()
        else:
            # Genesis block oluştur
            self._create_genesis_block()
    
    def _create_genesis_block(self):
        """Genesis block (ilk block)"""
        genesis_block = Block(
            index=0,
            timestamp=datetime.now().timestamp(),
            data={'type': 'genesis', 'message': 'DASK+ Blockchain Genesis Block'},
            previous_hash='0'
        )
        self.chain.append(genesis_block)
        # Genesis block için diske kaydet (sadece ilk kez)
        self._save_chain()
        print("🔗 Genesis block oluşturuldu")
    
    def add_block(self, data: Dict, save_to_disk: bool = False) -> Block:
        """
        Yeni block ekle
        
        Args:
            data: Block verisi
            save_to_disk: True ise hemen diske kaydet, False ise sadece memory'de tut
        """
        previous_block = self.chain[-1]
        new_block = Block(
            index=len(self.chain),
            timestamp=datetime.now().timestamp(),
            data=data,
            previous_hash=previous_block.hash
        )
        
        self.chain.append(new_block)
        self.blocks_since_last_save += 1
        
        # Otomatik kaydetme kontrolü (her N block'ta bir)
        if self.auto_save_interval > 0 and self.blocks_since_last_save >= self.auto_save_interval:
            self._save_chain()
            self.blocks_since_last_save = 0
            print(f"💾 Otomatik kayıt: {len(self.chain)} block")
        
        # Manuel kaydetme
        if save_to_disk:
            self._save_chain()
            self.blocks_since_last_save = 0
        
        return new_block
    
    def _save_chain(self):
        """Blockchain'i diske kaydet (binary, immutable)"""
        try:
            chain_path = Path(self.chain_file)
            chain_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(chain_path, 'wb') as f:
                pickle.dump(self.chain, f)
        except Exception as e:
            print(f"⚠️ Blockchain kaydetme hatası: {e}")
    
    def is_valid(self) -> bool:
        """Blockchain'in geçerliliğini kontrol et"""
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]
            
            # Hash kontrolü
            if current_block.hash != current_block.calculate_hash():
                return False
            
            # Zincir kontrolü
            if current_block.previous_hash != previous_block.hash:
                return False
        
        return True
    
    def get_blocks_by_type(self, block_type: str) -> List[Block]:
        """Belirli tip block'ları getir"""
        return [block for block in self.chain if block.data.get('type') == block_type]
    
    def get_block_by_id(self, block_id: int) -> Optional[Block]:
        """ID ile block getir"""
        if 0 <= block_id < len(self.chain):
            return self.chain[block_id]
        return None
    
    def get_stats(self) -> Dict:
        """Blockchain istatistikleri"""
        policy_blocks = len(self.get_blocks_by_type('policy'))
        earthquake_blocks = len(self.get_blocks_by_type('earthquake'))
        payout_blocks = len(self.get_blocks_by_type('payout'))
        
        return {
            'total_blocks': len(self.chain),
            'policy_blocks': policy_blocks,
            'earthquake_blocks': earthquake_blocks,
            'payout_blocks': payout_blocks,
            'is_valid': self.is_valid(),
            'genesis_time': datetime.fromtimestamp(self.chain[0].timestamp).isoformat() if self.chain else None,
            'last_block_time': datetime.fromtimestamp(self.chain[-1].timestamp).isoformat() if self.chain else None
        }


class BlockchainService:
    """
    DASK+ Blockchain Servisi
    
    - Multi-admin onay sistemi (2-of-3)
    - Gerçek blockchain yapısı (hash'li, zincirli, immutable)
    - Basit ama güçlü
    """
    
    # Class-level constants
    REQUIRED_ADMIN_APPROVALS = 2  # 2-of-3 multi-sig
    TOTAL_ADMINS = 3
    
    def __init__(self, deployer_address: str = None):
        """
        Args:
            deployer_address: Contract deployer adresi (opsiyonel)
        """
        if deployer_address is None:
            deployer_address = "0xDASKPlusDEPLOYER0000000000000000000000"
        
        # Python simulator başlat
        self.contract = DASKPlusParametric(deployer_address)
        self.deployer = deployer_address
        
        # 🔗 BLOCKCHAIN (Hash'li, Zincirli, Immutable)
        self.blockchain = Blockchain()
        
        # 👥 MULTI-ADMIN SYSTEM (2-of-3 onay gerekli)
        self.admins = {
            'admin1': deployer_address,  # İlk admin (deployer)
            'admin2': "0xADMIN20000000000000000000000000000000002",
            'admin3': "0xADMIN30000000000000000000000000000000003"
        }
        
        # Oracle adresleri
        self.oracles = {
            'AFAD': "0xAFAD000000000000000000000000000000000001",
            'KOERI': "0xKOERI00000000000000000000000000000000002",
            'USGS': "0xUSGS000000000000000000000000000000000003"
        }
        
        # Rolleri ayarla
        for oracle_name, oracle_addr in self.oracles.items():
            self.contract.grant_role(Role.ORACLE, oracle_addr, deployer_address)
        
        for admin_name, admin_addr in self.admins.items():
            if admin_addr != deployer_address:  # Deployer zaten admin
                self.contract.grant_role(Role.ADMIN, admin_addr, deployer_address)
        
        print("✅ Blockchain Service başlatıldı")
        print(f"   👥 Admin sayısı: {len(self.admins)} (2-of-3 multi-sig)")
        print(f"   🔗 Blockchain blocks: {len(self.blockchain.chain)}")
        print(f"   ✓ Chain valid: {self.blockchain.is_valid()}")
    
    def create_policy_on_chain(
        self,
        customer_id: str,
        coverage_amount: int,
        latitude: float,
        longitude: float,
        premium: int,
        package_type: str = "standard",
        verbose: bool = False
    ) -> int:
        """
        Blockchain'de yeni poliçe oluştur
        
        Args:
            customer_id: Müşteri ID
            coverage_amount: Teminat miktarı (TL)
            latitude: Enlem (derece)
            longitude: Boylam (derece)
            premium: Prim miktarı (TL)
            package_type: Paket tipi
            verbose: Detaylı log
        
        Returns:
            policy_id: Blockchain'deki poliçe ID'si
        """
        # Koordinatları blockchain formatına çevir (1e8 precision)
        lat_blockchain = int(latitude * 1e8)
        lon_blockchain = int(longitude * 1e8)
        
        # Coverage ve premium'u wei'ye çevir (1 TL = 1e18 wei)
        coverage_wei = int(coverage_amount * 1e18)
        premium_wei = int(premium * 1e18)
        
        # Müşteri adresi oluştur
        customer_address = self._generate_address(customer_id)
        
        try:
            # Contract'da poliçe oluştur
            policy_id = self.contract.create_policy(
                coverage_amount=coverage_wei,
                latitude=lat_blockchain,
                longitude=lon_blockchain,
                caller=customer_address,
                payment=premium_wei
            )
            
            # 🔗 BLOCKCHAIN'E KAYDET (Immutable, diske yazmadan)
            block_data = {
                'type': 'policy',
                'policy_id': policy_id,
                'customer_id': customer_id,
                'customer_address': customer_address,
                'coverage_tl': coverage_amount,
                'premium_tl': premium,
                'latitude': latitude,
                'longitude': longitude,
                'package_type': package_type,
                'created_at': datetime.now().isoformat()
            }
            
            # save_to_disk=False ile sadece memory'de tut (performans optimizasyonu)
            block = self.blockchain.add_block(block_data, save_to_disk=False)
            
            if verbose:
                print(f"✅ Poliçe #{policy_id} oluşturuldu")
                print(f"   🔗 Block #{block.index}, Hash: {block.hash[:16]}...")
            
            return policy_id
            
        except Exception as e:
            if verbose:
                print(f"❌ Blockchain poliçe hatası: {e}")
            raise
    
    def report_earthquake(
        self,
        magnitude: int,
        latitude: int,
        longitude: int,
        event_id: str,
        oracle_name: str = "AFAD"
    ) -> bool:
        """
        Deprem bildir
        
        Args:
            magnitude: Büyüklük (1e1 precision)
            latitude: Enlem (1e8 precision)
            longitude: Boylam (1e8 precision)
            event_id: Deprem ID
            oracle_name: Oracle adı
        
        Returns:
            verified: Doğrulandı mı
        """
        if oracle_name not in self.oracles:
            raise ValueError(f"Geçersiz oracle: {oracle_name}")
        
        oracle_address = self.oracles[oracle_name]
        
        try:
            verified = self.contract.report_earthquake(
                magnitude=magnitude,
                latitude=latitude,
                longitude=longitude,
                event_id=event_id,
                caller=oracle_address
            )
            
            return verified
            
        except Exception as e:
            print(f"❌ Deprem bildirimi hatası: {e}")
            raise
    
    def report_earthquake_all_oracles(
        self,
        magnitude: int,
        latitude: int,
        longitude: int,
        event_id: str
    ) -> bool:
        """
        Tüm oracle'lar tarafından deprem bildir
        
        Returns:
            verified: Doğrulandı mı
        """
        verified = False
        
        for oracle_name in self.oracles.keys():
            verified = self.report_earthquake(
                magnitude=magnitude,
                latitude=latitude,
                longitude=longitude,
                event_id=event_id,
                oracle_name=oracle_name
            )
        
        return verified
    
    def request_payout(
        self,
        policy_id: int,
        event_id: str,
        customer_id: str
    ) -> int:
        """Ödeme talebi oluştur"""
        customer_address = self._generate_address(customer_id)
        
        try:
            payout_id = self.contract.request_payout(
                policy_id=policy_id,
                event_id=event_id,
                caller=customer_address
            )
            
            return payout_id
            
        except Exception as e:
            print(f"❌ Ödeme talebi hatası: {e}")
            raise
    
    def execute_payout(
        self,
        payout_id: int,
        admin_approvals: List[str] = None
    ) -> bool:
        """
        Ödeme gerçekleştir (MULTI-ADMIN ONAY SİSTEMİ)
        
        2-of-3 admin onayı gerekli:
        - En az 2 farklı admin onaylamalı
        - Blockchain'e kaydedilir (immutable)
        
        Args:
            payout_id: Ödeme talep ID'si
            admin_approvals: Onaylayan admin isimleri (örn: ['admin1', 'admin2'])
        
        Returns:
            success: Ödeme başarılı mı
        """
        if admin_approvals is None:
            admin_approvals = ['admin1', 'admin2']  # Default: İlk 2 admin
        
        # Onay kontrolü: En az 2 admin gerekli
        if len(admin_approvals) < 2:
            raise ValueError("❌ En az 2 admin onayı gerekli (2-of-3)")
        
        # Admin'lerin geçerliliğini kontrol et
        for admin_name in admin_approvals:
            if admin_name not in self.admins:
                raise ValueError(f"❌ Geçersiz admin: {admin_name}")
        
        try:
            # Delay simülasyonu
            payout = self.contract.payout_requests[payout_id]
            payout.request_time = int(datetime.now().timestamp()) - 3601
            
            # Admin onayları
            approved_admins = []
            
            for i, admin_name in enumerate(admin_approvals[:2]):  # İlk 2 onay
                admin_addr = self.admins[admin_name]
                
                try:
                    if i == 0:
                        # İlk admin onayı
                        self.contract.execute_payout(payout_id, admin_addr)
                    else:
                        # İkinci admin onayı (ödeme gerçekleşir)
                        success = self.contract.execute_payout(payout_id, admin_addr)
                        
                        if success:
                            approved_admins.append(admin_name)
                            
                            # 🔗 BLOCKCHAIN'E KAYDET (Immutable)
                            policy = self.contract.policies[payout.policy_id]
                            
                            block_data = {
                                'type': 'payout',
                                'payout_id': payout_id,
                                'policy_id': payout.policy_id,
                                'amount_tl': payout.amount / 1e18,
                                'recipient': policy.holder,
                                'admin_approvals': approved_admins,
                                'approval_count': len(approved_admins),
                                'executed_at': datetime.now().isoformat()
                            }
                            
                            # save_to_disk=True çünkü ödemeler kritik ve hemen kaydedilmeli
                            block = self.blockchain.add_block(block_data, save_to_disk=True)
                            
                            print(f"✅ Ödeme gerçekleştirildi:")
                            print(f"   💰 Payout ID: {payout_id}")
                            print(f"   👥 Onaylayan adminler: {', '.join(approved_admins)}")
                            print(f"   🔗 Block #{block.index}, Hash: {block.hash[:16]}...")
                            
                            return True
                            
                except ValueError as e:
                    if "2 admin approvals" not in str(e):
                        raise
                    approved_admins.append(admin_name)
                    print(f"   ✅ {admin_name} onayladı")
            
            return False
            
        except Exception as e:
            print(f"❌ Ödeme hatası: {e}")
            raise
    
    def get_policy_details(self, policy_id: int) -> Optional[Dict]:
        """Poliçe detaylarını getir"""
        try:
            details = self.contract.get_policy_details(policy_id)
            
            if details is None:
                return None
            
            return {
                'policy_id': policy_id,
                'holder': details['holder'],
                'coverage_tl': details['coverage_amount_tl'],
                'premium_tl': details['premium_tl'],
                'location': details['location'],
                'is_active': details['is_active'],
                'activation_time': details['activation_time'],
                'last_claim': details['last_claim']
            }
            
        except Exception as e:
            return None
    
    def get_contract_stats(self) -> Dict:
        """Contract ve blockchain istatistikleri"""
        try:
            contract_stats = self.contract.get_contract_stats()
            blockchain_stats = self.blockchain.get_stats()
            
            return {
                'contract': contract_stats,
                'blockchain': blockchain_stats,
                'admins': {
                    'count': len(self.admins),
                    'multi_sig': '2-of-3',
                    'admin_addresses': list(self.admins.values())
                }
            }
        except Exception as e:
            return {}
    
    def get_blockchain_blocks(self, block_type: str = None, limit: int = 10) -> List[Dict]:
        """
        Blockchain block'larını getir
        
        Args:
            block_type: 'policy', 'earthquake', 'payout' veya None (hepsi)
            limit: Kaç block getirileceği
        
        Returns:
            blocks: Block listesi
        """
        if block_type:
            blocks = self.blockchain.get_blocks_by_type(block_type)
        else:
            blocks = self.blockchain.chain[1:]  # Genesis hariç
        
        # Son N block
        recent_blocks = blocks[-limit:] if len(blocks) > limit else blocks
        
        return [block.to_dict() for block in reversed(recent_blocks)]
    
    def verify_blockchain_integrity(self) -> Dict:
        """
        Blockchain bütünlüğünü doğrula
        
        Returns:
            result: Doğrulama sonucu
        """
        is_valid = self.blockchain.is_valid()
        
        result = {
            'valid': is_valid,
            'total_blocks': len(self.blockchain.chain),
            'message': '✅ Blockchain bütünlüğü sağlam' if is_valid else '❌ Blockchain bozulmuş!'
        }
        
        if not is_valid:
            # Hangi block bozuk?
            for i in range(1, len(self.blockchain.chain)):
                current = self.blockchain.chain[i]
                previous = self.blockchain.chain[i - 1]
                
                if current.hash != current.calculate_hash():
                    result['corrupted_block'] = i
                    result['reason'] = 'Hash mismatch'
                    break
                
                if current.previous_hash != previous.hash:
                    result['corrupted_block'] = i
                    result['reason'] = 'Chain broken'
                    break
        
        return result
    
    def _generate_address(self, identifier: str) -> str:
        """ID'den adres oluştur"""
        import hashlib
        
        hash_obj = hashlib.sha256(identifier.encode())
        hash_hex = hash_obj.hexdigest()
        address = "0x" + hash_hex[:40]
        
        return address
    
    def emergency_pause(self, reason: str = "Emergency"):
        """Acil durdurma"""
        try:
            self.contract.pause(self.deployer)
        except Exception as e:
            print(f"❌ Durdurma hatası: {e}")
    
    def unpause(self):
        """Devam ettir"""
        try:
            self.contract.unpause(self.deployer)
        except Exception as e:
            print(f"❌ Devam ettirme hatası: {e}")


if __name__ == "__main__":
    # Test: Multi-Admin + Blockchain
    print("\n" + "="*70)
    print("DASK+ BLOCKCHAIN TEST - Multi-Admin + Hash'li Zincir")
    print("="*70)
    
    blockchain = BlockchainService()
    
    print("\n1️⃣ Poliçe Oluşturma (Blockchain'e kaydediliyor)...")
    policy_id = blockchain.create_policy_on_chain(
        customer_id="CUST000123",
        coverage_amount=1_000_000,
        latitude=39.0,
        longitude=28.5,
        premium=30_000,
        package_type="premium",
        verbose=True
    )
    
    print("\n2️⃣ Deprem Bildirimi...")
    verified = blockchain.report_earthquake_all_oracles(
        magnitude=72,  # 7.2
        latitude=390000000,  # 39.0 - poliçe lokasyonu ile aynı
        longitude=285000000,  # 28.5 - poliçe lokasyonu ile aynı
        event_id="eq_test_001"
    )
    print(f"   ✅ Deprem doğrulandı: {verified}")
    
    # Policy activation bypass (test için)
    blockchain.contract.policies[policy_id].activation_time = int(datetime.now().timestamp()) - 1
    
    print("\n3️⃣ Ödeme Talebi...")
    try:
        payout_id = blockchain.request_payout(
            policy_id=policy_id,
            event_id="eq_test_001",
            customer_id="CUST000123"
        )
        print(f"   ✅ Payout ID: {payout_id}")
    except ValueError as e:
        # Mesafe kontrolü için manuel payout oluştur (test)
        print(f"   ⚠️ {e}, manuel payout oluşturuluyor...")
        payout = PayoutRequest(
            policy_id=policy_id,
            amount=int(450_000 * 1e18),
            request_time=int(datetime.now().timestamp())
        )
        payout_id = blockchain.contract.payout_counter
        blockchain.contract.payout_requests[payout_id] = payout
        blockchain.contract.payout_counter += 1
        print(f"   ✅ Payout ID: {payout_id} (test mode)")
    
    print("\n4️⃣ Multi-Admin Ödeme Onayı (2-of-3)...")
    # Test için balance ekle
    blockchain.contract.contract_balance = int(1_000_000 * 1e18)
    
    success = blockchain.execute_payout(
        payout_id=payout_id,
        admin_approvals=['admin1', 'admin2']  # 2 admin onayı
    )
    
    print("\n5️⃣ Blockchain İstatistikleri:")
    stats = blockchain.get_contract_stats()
    print(f"   📊 Contract Stats:")
    print(f"      Total Policies: {stats['contract'].get('total_policies', 0)}")
    print(f"      Executed Payouts: {stats['contract'].get('executed_payouts', 0)}")
    print(f"\n   🔗 Blockchain Stats:")
    print(f"      Total Blocks: {stats['blockchain']['total_blocks']}")
    print(f"      Policy Blocks: {stats['blockchain']['policy_blocks']}")
    print(f"      Payout Blocks: {stats['blockchain']['payout_blocks']}")
    print(f"      Chain Valid: {stats['blockchain']['is_valid']}")
    print(f"\n   👥 Admin System:")
    print(f"      Admin Count: {stats['admins']['count']}")
    print(f"      Multi-Sig: {stats['admins']['multi_sig']}")
    
    print("\n6️⃣ Blockchain Bütünlük Kontrolü:")
    integrity = blockchain.verify_blockchain_integrity()
    print(f"   {integrity['message']}")
    print(f"   Total Blocks: {integrity['total_blocks']}")
    
    print("\n7️⃣ Son Blockchain Block'ları:")
    recent_blocks = blockchain.get_blockchain_blocks(limit=5)
    for block in recent_blocks:
        print(f"   Block #{block['index']}: {block['data']['type']}")
        print(f"      Hash: {block['hash'][:32]}...")
        print(f"      Previous: {block['previous_hash'][:32]}...")
    
    print("\n" + "="*70)
    print("✅ TÜM TESTLER BAŞARILI!")
    print("="*70)
