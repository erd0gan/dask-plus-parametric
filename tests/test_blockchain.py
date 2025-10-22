"""
DASK+ Blockchain Entegrasyon Test
=================================
Blockchain sisteminin çalışıp çalışmadığını test eder.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from blockchain_manager import BlockchainManager
from datetime import datetime

print("\n" + "="*80)
print("DASK+ BLOCKCHAIN TEST")
print("="*80)

# Blockchain manager başlat
print("\n[1] Blockchain Manager başlatılıyor...")
blockchain = BlockchainManager(
    enable_blockchain=True,
    async_mode=True,
    record_threshold={
        'policy_min_coverage': 500_000,
        'earthquake_min_magnitude': 5.0,
        'payout_min_amount': 0
    }
)
print("✅ Blockchain Manager hazır")

# Test poliçesi
print("\n[2] Test poliçesi kaydediliyor...")
test_policy = {
    'customer_id': 'CUST000001',
    'building_id': 'BLD_TEST_001',
    'package_type': 'premium',
    'max_coverage': 1_500_000,
    'annual_premium_tl': 12_500.00,
    'latitude': 41.0181,
    'longitude': 28.9784,
    'policy_number': 'DP-TEST-001'
}

policy_id = blockchain.record_policy(test_policy)
if policy_id:
    print(f"✅ Poliçe kaydedildi: ID={policy_id}")
else:
    print("⚠️  Poliçe filtrelendi veya hata oluştu")

# Test depremi
print("\n[3] Test depremi kaydediliyor...")
test_earthquake = {
    'event_id': 'eq_test_001',
    'magnitude': 6.5,
    'latitude': 40.7589,
    'longitude': 29.9284,
    'depth_km': 10.0,
    'timestamp': datetime.now()
}

result = blockchain.record_earthquake(test_earthquake)
print(f"{'✅' if result else '⚠️ '} Deprem {'kaydedildi' if result else 'filtrelendi'}")

# İstatistikler
print("\n[4] İstatistikler:")
blockchain.print_stats()

# Kapatma
blockchain.shutdown()

print("\n" + "="*80)
print("✅ TEST TAMAMLANDI")
print("="*80 + "\n")
