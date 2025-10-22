#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DASK+ Parametrik Sigorta Sistemi - Python Implementation
Solidity smart contract'ının Python simülasyonu
Test ve analiz için tasarlanmıştır.
"""

import hashlib
import time
import json
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
import math
from datetime import datetime, timedelta

class Role(Enum):
    """Kullanıcı rolleri"""
    ADMIN = "ADMIN_ROLE"
    ORACLE = "ORACLE_ROLE"
    EMERGENCY = "EMERGENCY_ROLE"
    DEFAULT_ADMIN = "DEFAULT_ADMIN_ROLE"

@dataclass
class Policy:
    """Sigorta poliçesi"""
    holder: str
    coverage_amount: int  # Wei cinsinden (1 TL = 1e18 wei)
    premium: int
    latitude: int         # 1e8 precision (39.0 derece = 390000000)
    longitude: int        # 1e8 precision (28.5 derece = 285000000)
    activation_time: int  # Unix timestamp
    is_active: bool = True
    last_claim_time: int = 0

@dataclass
class EarthquakeEvent:
    """Deprem olayı"""
    magnitude: int        # 1e1 precision (7.5 büyüklük = 75)
    latitude: int
    longitude: int
    timestamp: int
    confirmations: int = 0
    verified: bool = False
    oracle_confirmed: Dict[str, bool] = field(default_factory=dict)

@dataclass
class PayoutRequest:
    """Ödeme talebi"""
    policy_id: int
    amount: int
    request_time: int
    confirmations: int = 0
    executed: bool = False
    admin_approved: Dict[str, bool] = field(default_factory=dict)

class DASKPlusParametric:
    """DASK+ Parametrik Sigorta Smart Contract Python Implementation"""
    
    # Güvenlik Parametreleri
    MAX_PAYOUT_PER_POLICY = 5_000_000 * 10**18  # 5M TL
    MAX_DAILY_PAYOUTS = 50_000_000 * 10**18     # 50M TL/gün
    MIN_ORACLE_CONFIRMATIONS = 3
    PAYOUT_DELAY = 3600  # 1 saat (saniye)
    
    def __init__(self, deployer_address: str):
        """Contract initialization"""
        self.deployer = deployer_address
        self.paused = False
        
        # Role assignments
        self.roles: Dict[Role, List[str]] = {
            Role.DEFAULT_ADMIN: [deployer_address],
            Role.ADMIN: [deployer_address],
            Role.ORACLE: [],
            Role.EMERGENCY: [deployer_address]
        }
        
        # State variables
        self.policies: Dict[int, Policy] = {}
        self.earthquake_events: Dict[str, EarthquakeEvent] = {}
        self.payout_requests: Dict[int, PayoutRequest] = {}
        self.blacklisted_policies: set = set()
        
        # Counters
        self.policy_counter = 0
        self.payout_counter = 0
        
        # Financial tracking
        self.total_locked = 0
        self.daily_payout_total = 0
        self.last_reset_day = int(time.time()) // 86400  # Günlük reset için
        self.contract_balance = 0
        
        # Events log
        self.events: List[Dict] = []
        
        print(f"✅ DASK+ Contract deployed by {deployer_address}")
        print(f"📅 Deployment time: {datetime.now()}")
    
    def has_role(self, role: Role, address: str) -> bool:
        """Role kontrolü"""
        return address in self.roles.get(role, [])
    
    def grant_role(self, role: Role, address: str, caller: str):
        """Role verme"""
        if not self.has_role(Role.DEFAULT_ADMIN, caller):
            raise PermissionError(f"❌ {caller} doesn't have admin rights")
        
        if address not in self.roles[role]:
            self.roles[role].append(address)
            print(f"✅ Role {role.value} granted to {address}")
    
    def renounce_role(self, role: Role, address: str, caller: str):
        """Role'dan çıkma"""
        if caller != address:
            raise PermissionError("❌ Can only renounce own roles")
        
        if address in self.roles[role]:
            self.roles[role].remove(address)
            print(f"🚫 Role {role.value} renounced by {address}")
    
    def pause(self, caller: str):
        """Contract'ı durdurma"""
        if not self.has_role(Role.EMERGENCY, caller):
            raise PermissionError("❌ Not authorized for emergency stop")
        
        self.paused = True
        self._emit_event("EmergencyStop", {"admin": caller, "reason": "Emergency stop"})
        print(f"⏸️ Contract paused by {caller}")
    
    def unpause(self, caller: str):
        """Contract'ı devam ettirme"""
        if not self.has_role(Role.ADMIN, caller):
            raise PermissionError("❌ Not authorized to unpause")
        
        self.paused = False
        print(f"▶️ Contract unpaused by {caller}")
    
    def _reset_daily_limit_if_needed(self):
        """Günlük limit sıfırlama"""
        current_day = int(time.time()) // 86400
        if current_day > self.last_reset_day:
            self.daily_payout_total = 0
            self.last_reset_day = current_day
            print(f"🔄 Daily payout limit reset")
    
    def _calculate_premium(self, coverage_amount: int) -> int:
        """
        Prim hesaplama - TAM ESNEKLEŞTIRILDI
        Ana sistemdeki pricing zaten doğru hesaplanmış olarak geliyor,
        çok düşük kontrol yapıyoruz, gerçek risk bazlı primleri kabul etmek için
        """
        # Minimum %0.01 prim (sadece 0 değeri engellemek için)
        # Gerçek risk bazlı primler her zaman bu değerin üzerinde olacaktır
        minimum_premium = (coverage_amount * 1) // 10000  # %0.01
        return minimum_premium
    
    def create_policy(self, coverage_amount: int, latitude: int, longitude: int, 
                     caller: str, payment: int) -> int:
        """Yeni poliçe oluşturma"""
        if self.paused:
            raise RuntimeError("❌ Contract is paused")
        
        # Validations
        if coverage_amount <= 0 or coverage_amount > self.MAX_PAYOUT_PER_POLICY:
            raise ValueError(f"❌ Invalid coverage amount: {coverage_amount}")
        
        # Minimum prim kontrolü (ana sistemden gelen prim zaten doğru hesaplanmış)
        minimum_premium = self._calculate_premium(coverage_amount)
        if payment < minimum_premium:
            raise ValueError(f"❌ Insufficient premium. Minimum required: {minimum_premium} ({minimum_premium/1e18:.0f} TL), Got: {payment} ({payment/1e18:.0f} TL)")
        
        # Türkiye koordinat kontrolü (1e8 precision: 36°-42° enlem, 26°-45° boylam)
        if not (3_600_000_000 <= latitude <= 4_200_000_000):
            raise ValueError(f"❌ Invalid latitude for Turkey: {latitude} (expected 3.6e9 - 4.2e9)")
        if not (2_600_000_000 <= longitude <= 4_500_000_000):
            raise ValueError(f"❌ Invalid longitude for Turkey: {longitude} (expected 2.6e9 - 4.5e9)")
        
        # Policy oluşturma
        policy_id = self.policy_counter
        self.policy_counter += 1
        
        activation_time = int(time.time()) + 48 * 3600  # 48 saat gecikme
        
        self.policies[policy_id] = Policy(
            holder=caller,
            coverage_amount=coverage_amount,
            premium=payment,
            latitude=latitude,
            longitude=longitude,
            activation_time=activation_time,
            is_active=True,
            last_claim_time=0
        )
        
        self.total_locked += coverage_amount
        self.contract_balance += payment
        
        self._emit_event("PolicyCreated", {
            "policy_id": policy_id,
            "holder": caller,
            "coverage_amount": coverage_amount,
            "activation_time": datetime.fromtimestamp(activation_time)
        })
        
        # Verbose loglar kaldırıldı (toplu yükleme için)
        # print(f"🆕 Policy {policy_id} created for {caller}")
        # print(f"💰 Coverage: {coverage_amount/1e18:.2f} TL")
        # print(f"⏰ Activation: {datetime.fromtimestamp(activation_time)}")
        
        return policy_id
    
    def report_earthquake(self, magnitude: int, latitude: int, longitude: int,
                         event_id: str, caller: str) -> bool:
        """Deprem bildirimi (Oracle'lar tarafından)"""
        if self.paused:
            raise RuntimeError("❌ Contract is paused")
        
        if not self.has_role(Role.ORACLE, caller):
            raise PermissionError(f"❌ {caller} is not authorized oracle")
        
        # Magnitude validation
        if not (40 <= magnitude <= 90):  # 4.0 - 9.0 arası
            raise ValueError(f"❌ Invalid magnitude: {magnitude}")
        
        # Event oluştur veya güncelle
        if event_id not in self.earthquake_events:
            self.earthquake_events[event_id] = EarthquakeEvent(
                magnitude=magnitude,
                latitude=latitude,
                longitude=longitude,
                timestamp=int(time.time())
            )
        
        earthquake = self.earthquake_events[event_id]
        
        # Oracle confirmation
        if caller not in earthquake.oracle_confirmed:
            earthquake.oracle_confirmed[caller] = True
            earthquake.confirmations += 1
            
            print(f"📡 Earthquake {event_id} confirmed by oracle {caller}")
            print(f"   Confirmations: {earthquake.confirmations}/{self.MIN_ORACLE_CONFIRMATIONS}")
            
            if earthquake.confirmations >= self.MIN_ORACLE_CONFIRMATIONS:
                earthquake.verified = True
                print(f"✅ Earthquake {event_id} VERIFIED!")
        
        self._emit_event("EarthquakeReported", {
            "event_id": event_id,
            "magnitude": magnitude/10,
            "latitude": latitude/1e8,
            "longitude": longitude/1e8,
            "oracle": caller,
            "verified": earthquake.verified
        })
        
        return earthquake.verified
    
    def request_payout(self, policy_id: int, event_id: str, caller: str) -> int:
        """Ödeme talebi"""
        if self.paused:
            raise RuntimeError("❌ Contract is paused")
        
        # Policy validations
        if policy_id not in self.policies:
            raise ValueError(f"❌ Invalid policy ID: {policy_id}")
        
        policy = self.policies[policy_id]
        
        if not policy.is_active:
            raise ValueError(f"❌ Policy {policy_id} is not active")
        
        if policy_id in self.blacklisted_policies:
            raise ValueError(f"❌ Policy {policy_id} is blacklisted")
        
        if caller != policy.holder:
            raise PermissionError(f"❌ {caller} is not the policy holder")
        
        # Activation time check
        if time.time() < policy.activation_time:
            raise ValueError(f"❌ Policy not activated yet. Wait until {datetime.fromtimestamp(policy.activation_time)}")
        
        # Rate limiting
        if policy.last_claim_time > 0 and time.time() < policy.last_claim_time + 86400:
            raise ValueError(f"❌ Rate limit: Wait 24h between claims")
        
        # Earthquake validation
        if event_id not in self.earthquake_events:
            raise ValueError(f"❌ Earthquake event {event_id} not found")
        
        earthquake = self.earthquake_events[event_id]
        if not earthquake.verified:
            raise ValueError(f"❌ Earthquake {event_id} not verified")
        
        # Time window check (72 saat)
        if time.time() > earthquake.timestamp + 72 * 3600:
            raise ValueError(f"❌ Claim period expired (72 hours)")
        
        # Distance calculation
        distance = self._calculate_distance(
            policy.latitude, policy.longitude,
            earthquake.latitude, earthquake.longitude
        )
        
        if distance > 100000:  # 100km
            raise ValueError(f"❌ Too far from epicenter: {distance/1000:.1f} km")
        
        # Payout calculation
        payout_amount = self._calculate_payout(
            policy.coverage_amount, earthquake.magnitude, distance
        )
        
        if payout_amount <= 0:
            raise ValueError(f"❌ No payout calculated for this event")
        
        # Create payout request
        payout_id = self.payout_counter
        self.payout_counter += 1
        
        self.payout_requests[payout_id] = PayoutRequest(
            policy_id=policy_id,
            amount=payout_amount,
            request_time=int(time.time())
        )
        
        policy.last_claim_time = int(time.time())
        
        self._emit_event("PayoutRequested", {
            "payout_id": payout_id,
            "policy_id": policy_id,
            "amount": payout_amount/1e18,
            "distance_km": distance/1000,
            "magnitude": earthquake.magnitude/10
        })
        
        print(f"💰 Payout requested: {payout_amount/1e18:.2f} TL")
        print(f"📍 Distance: {distance/1000:.1f} km")
        print(f"📊 Magnitude: {earthquake.magnitude/10}")
        
        return payout_id
    
    def execute_payout(self, payout_id: int, caller: str) -> bool:
        """Ödeme gerçekleştirme"""
        if self.paused:
            raise RuntimeError("❌ Contract is paused")
        
        if not self.has_role(Role.ADMIN, caller):
            raise PermissionError(f"❌ {caller} is not authorized admin")
        
        if payout_id not in self.payout_requests:
            raise ValueError(f"❌ Invalid payout ID: {payout_id}")
        
        payout = self.payout_requests[payout_id]
        
        if payout.executed:
            raise ValueError(f"❌ Payout {payout_id} already executed")
        
        # Delay check
        if time.time() < payout.request_time + self.PAYOUT_DELAY:
            raise ValueError(f"❌ Payout delay not met. Wait until {datetime.fromtimestamp(payout.request_time + self.PAYOUT_DELAY)}")
        
        # Daily limit check
        self._reset_daily_limit_if_needed()
        if self.daily_payout_total + payout.amount > self.MAX_DAILY_PAYOUTS:
            raise ValueError(f"❌ Daily payout limit exceeded")
        
        # Multi-signature check
        if caller not in payout.admin_approved:
            payout.admin_approved[caller] = True
            payout.confirmations += 1
            print(f"✅ Admin {caller} approved payout {payout_id} ({payout.confirmations}/2)")
        
        if payout.confirmations < 2:
            raise ValueError(f"❌ Need at least 2 admin approvals (current: {payout.confirmations})")
        
        # Balance check
        if self.contract_balance < payout.amount:
            raise ValueError(f"❌ Insufficient contract balance")
        
        # Execute payout
        policy = self.policies[payout.policy_id]
        payout.executed = True
        self.daily_payout_total += payout.amount
        self.contract_balance -= payout.amount
        
        self._emit_event("PayoutExecuted", {
            "payout_id": payout_id,
            "recipient": policy.holder,
            "amount": payout.amount/1e18,
            "executed_by": caller
        })
        
        print(f"💸 Payout executed: {payout.amount/1e18:.2f} TL to {policy.holder}")
        
        return True
    
    def blacklist_policy(self, policy_id: int, reason: str, caller: str):
        """Poliçeyi kara listeye alma"""
        if not self.has_role(Role.ADMIN, caller):
            raise PermissionError(f"❌ {caller} is not authorized admin")
        
        self.blacklisted_policies.add(policy_id)
        
        self._emit_event("SecurityAlert", {
            "type": "POLICY_BLACKLISTED",
            "policy_id": policy_id,
            "reason": reason,
            "admin": caller
        })
        
        print(f"🚫 Policy {policy_id} blacklisted: {reason}")
    
    def _calculate_distance(self, lat1: int, lon1: int, lat2: int, lon2: int) -> int:
        """İki nokta arası mesafe (metre)"""
        # Basitleştirilmiş hesaplama
        lat_diff = abs(lat1 - lat2) / 1e8
        lon_diff = abs(lon1 - lon2) / 1e8
        
        # Yaklaşık mesafe (km cinsinden)
        distance_km = math.sqrt(lat_diff**2 + lon_diff**2) * 111
        return int(distance_km * 1000)  # metre
    
    def _calculate_payout(self, coverage_amount: int, magnitude: int, distance: int) -> int:
        """Ödeme miktarı hesaplama"""
        if magnitude < 50 or distance > 50000:  # 5.0 altı veya 50km üzeri
            return 0
        
        magnitude_factor = (magnitude - 40) * 25  # %25 per 0.1 magnitude
        distance_factor = (50000 - distance) * 100 // 50000  # Mesafe faktörü
        
        payout_percentage = (magnitude_factor * distance_factor) // 100
        if payout_percentage > 100:
            payout_percentage = 100
        
        return (coverage_amount * payout_percentage) // 100
    
    def _emit_event(self, event_name: str, data: Dict):
        """Event logging"""
        event = {
            "name": event_name,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        self.events.append(event)
    
    def get_policy_details(self, policy_id: int) -> Optional[Dict]:
        """Poliçe detaylarını getir"""
        if policy_id not in self.policies:
            return None
        
        policy = self.policies[policy_id]
        return {
            "holder": policy.holder,
            "coverage_amount_tl": policy.coverage_amount / 1e18,
            "premium_tl": policy.premium / 1e18,
            "location": {
                "latitude": policy.latitude / 1e8,
                "longitude": policy.longitude / 1e8
            },
            "is_active": policy.is_active,
            "activation_time": datetime.fromtimestamp(policy.activation_time),
            "last_claim": datetime.fromtimestamp(policy.last_claim_time) if policy.last_claim_time else None
        }
    
    def get_contract_stats(self) -> Dict:
        """Contract istatistikleri"""
        return {
            "total_policies": len(self.policies),
            "active_policies": sum(1 for p in self.policies.values() if p.is_active),
            "total_locked_tl": self.total_locked / 1e18,
            "contract_balance_tl": self.contract_balance / 1e18,
            "total_events": len(self.earthquake_events),
            "verified_events": sum(1 for e in self.earthquake_events.values() if e.verified),
            "total_payouts": len(self.payout_requests),
            "executed_payouts": sum(1 for p in self.payout_requests.values() if p.executed),
            "daily_payout_total_tl": self.daily_payout_total / 1e18,
            "blacklisted_policies": len(self.blacklisted_policies),
            "is_paused": self.paused
        }
    
    def get_recent_events(self, limit: int = 10) -> List[Dict]:
        """Son events'leri getir"""
        return self.events[-limit:] if self.events else []


def main():
    """Test fonksiyonu"""
    print("🚀 DASK+ Parametrik Sigorta Sistemi - Python Test")
    print("=" * 60)
    
    # Contract deploy
    deployer = "0x1234567890123456789012345678901234567890"
    contract = DASKPlusParametric(deployer)
    
    # Oracle'lar ekle
    oracle1 = "0xAFAD111111111111111111111111111111111111"
    oracle2 = "0xKOERI22222222222222222222222222222222222"
    oracle3 = "0xUSGS333333333333333333333333333333333333"
    
    contract.grant_role(Role.ORACLE, oracle1, deployer)
    contract.grant_role(Role.ORACLE, oracle2, deployer)
    contract.grant_role(Role.ORACLE, oracle3, deployer)
    
    # Admin ekle
    admin2 = "0xADMIN22222222222222222222222222222222222"
    contract.grant_role(Role.ADMIN, admin2, deployer)
    
    # Test kullanıcısı
    user = "0xUSER1111111111111111111111111111111111111"
    
    print("\n📋 Test Senaryoları:")
    print("-" * 30)
    
    try:
        # 1. Poliçe oluşturma
        print("\n1️⃣ Poliçe Oluşturma...")
        coverage = 1_000_000 * 10**18  # 1M TL
        premium = contract._calculate_premium(coverage)
        
        policy_id = contract.create_policy(
            coverage_amount=coverage,
            latitude=390000000,  # İstanbul
            longitude=285000000,
            caller=user,
            payment=premium
        )
        
        # 2. Deprem bildirimi
        print("\n2️⃣ Deprem Bildirimi...")
        event_id = "earthquake_2025_001"
        magnitude = 72  # 7.2 büyüklük
        
        contract.report_earthquake(magnitude, 391000000, 284000000, event_id, oracle1)
        contract.report_earthquake(magnitude, 391000000, 284000000, event_id, oracle2)
        verified = contract.report_earthquake(magnitude, 391000000, 284000000, event_id, oracle3)
        
        if verified:
            print("✅ Deprem 3 oracle tarafından doğrulandı!")
        
        # 3. Activation time'ı simüle et (normalde 48 saat)
        print("\n3️⃣ Policy Activation (simulated)...")
        contract.policies[policy_id].activation_time = int(time.time()) - 1
        
        # 4. Payout talebi
        print("\n4️⃣ Payout Talebi...")
        payout_id = contract.request_payout(policy_id, event_id, user)
        
        # 5. Payout delay'i simüle et
        print("\n5️⃣ Payout Execution (simulated delay)...")
        contract.payout_requests[payout_id].request_time = int(time.time()) - 3601  # 1 saat önce
        
        # 6. Admin onayları
        print("📝 İlk admin onayı...")
        try:
            contract.execute_payout(payout_id, deployer)
        except ValueError as e:
            if "2 admin approvals" in str(e):
                print(f"✅ İlk admin onayladı, ikinci admin bekleniyor...")
        
        print("📝 İkinci admin onayı...")
        contract.execute_payout(payout_id, admin2)  # 2. admin onayı
        print("✅ Ödeme başarıyla gerçekleştirildi!")
        
        print("\n📊 Contract İstatistikleri:")
        stats = contract.get_contract_stats()
        for key, value in stats.items():
            print(f"   {key}: {value}")
        
        print("\n📝 Son Events:")
        events = contract.get_recent_events(5)
        for event in events:
            print(f"   {event['name']}: {event['data']}")
        
        print("\n✅ Tüm testler başarılı!")
        
    except Exception as e:
        print(f"\n❌ Test hatası: {e}")
    
    print("\n" + "="*60)
    print("🎯 Python simülasyonu tamamlandı!")

if __name__ == "__main__":
    main()