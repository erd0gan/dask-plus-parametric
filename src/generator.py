"""
DASK+ Parametrik Sigorta - Veri Üretici (Kısaltılmış)
======================================================
Gerçekçi bina verisi üretir. Deprem verisi için gerçek AFAD/Kandilli 
kayıtlarını kullanır (../data/earthquakes.csv).
Müşteri verileri, şifreler ve autentikasyon bilgileri ekler.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from geopy.distance import geodesic
import random
from pathlib import Path
import sys
import json
from multiprocessing import Pool, cpu_count
import sqlite3
import warnings
warnings.filterwarnings('ignore')

# Auth module'ü import et
sys.path.insert(0, str(Path(__file__).parent))
try:
    from auth import PasswordManager
except ImportError:
    print("Auth modülü bulunamadı. Şifreler kaydedilmeyecek.")
    PasswordManager = None


class RealisticDataGenerator:
    """Gerçekçi ve tutarlı bina veri üretici"""
    
    def __init__(self, seed=42):
        np.random.seed(seed)
        random.seed(seed)
        self.seed = seed
        self.current_year = 2025
        
        # Data dizini - UI-Latest klasöründe (../data)
        self.data_dir = Path(__file__).parent.parent / 'data'
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # SQLite veritabanı yolu
        self.db_path = self.data_dir / 'dask_plus.db'
        
        self.quality_stats = {
            'total_generated': 0,
            'duplicates_prevented': 0,
            'outliers_prevented': 0,
            'inconsistencies_fixed': 0,
            'validation_passed': 0
        }
        
        self.used_building_ids = set()
        self.used_policy_numbers = set()
        self.used_tc_numbers = set()
        
        self.valid_ranges = {
            'building_age': (0, 80),
            'construction_year': (1945, 2025),
            'floors': (1, 40),
            'building_area_m2': (30, 2000),
            'residents': (1, 200),
            'commercial_units': (0, 20),
            'insurance_value_tl': (100_000, 20_000_000),
            'annual_premium_tl': (200, 200_000),
            'risk_score': (0.0, 1.0),
            'quality_score': (1.0, 10.0),
            'soil_amplification': (1.0, 2.5),
            'liquefaction_risk': (0.0, 0.8),
            'distance_to_fault_km': (0, 500)
        }
        
        self.turkish_names = [
            "Ahmet", "Mehmet", "Mustafa", "Ali", "Hasan", "Hüseyin", "İbrahim", "Yusuf",
            "Ayşe", "Fatma", "Emine", "Hatice", "Zeynep", "Elif", "Merve", "Büşra",
        ]
        
        self.turkish_surnames = [
            "Yılmaz", "Kaya", "Demir", "Şahin", "Çelik", "Yıldız", "Yıldırım", "Öztürk",
            "Aydın", "Özdemir", "Arslan", "Doğan", "Kılıç", "Aslan", "Çetin", "Kara",
        ]
        
        self.fault_lines = {
            'KAF': {'lat': 40.5, 'lon': 30.0, 'name': 'Kuzey Anadolu Fayı'},
            'DAF': {'lat': 38.0, 'lon': 37.0, 'name': 'Doğu Anadolu Fayı'},
            'BZBF': {'lat': 38.5, 'lon': 26.5, 'name': 'Batı Anadolu Fay Bölgesi'},
        }
        
        self.locations = {
            'İstanbul': {
                'risk_factor': 1.8,
                'districts': {
                    'Fatih': {'lat': 41.0186, 'lon': 28.9498, 'neighborhoods': ['Sultanahmet', 'Aksaray', 'Çapa']},
                    'Beyoğlu': {'lat': 41.0368, 'lon': 28.9770, 'neighborhoods': ['Taksim', 'Galata', 'Cihangir']},
                    'Kadıköy': {'lat': 40.9892, 'lon': 29.0341, 'neighborhoods': ['Fenerbahçe', 'Göztepe', 'Moda']},
                    'Üsküdar': {'lat': 41.0246, 'lon': 29.0169, 'neighborhoods': ['Altunizade', 'Bağlarbaşı', 'Çengelköy']},
                }
            }
        }
        
        self.street_names = ['Atatürk', 'İstiklal', 'Cumhuriyet', 'İnönü', 'Barbaros']
        self.apartment_names = ['Çınar', 'Palmiye', 'Yaprak', 'Ağaç', 'Güneş']
        
        self.structure_types = {
            'betonarme_cok_yeni': {
                'damage_factor': 0.2,
                'prob': 0.30,
                'description': 'Betonarme Çok Yeni (2015-2025)',
                'base_quality': 9.5,
                'year_range': (2015, 2025)
            },
            'betonarme_yeni': {
                'damage_factor': 0.35,
                'prob': 0.25,
                'description': 'Betonarme Yeni (2001-2014)',
                'base_quality': 8.5,
                'year_range': (2001, 2014)
            },
            'betonarme_orta': {
                'damage_factor': 0.6,
                'prob': 0.32,
                'description': 'Betonarme Orta (1981-2000)',
                'base_quality': 6,
                'year_range': (1981, 2000)
            },
            'betonarme_eski': {
                'damage_factor': 0.9,
                'prob': 0.08,
                'description': 'Betonarme Eski (1960-1980)',
                'base_quality': 4,
                'year_range': (1960, 1980)
            },
            'yigma': {
                'damage_factor': 1.3,
                'prob': 0.03,
                'description': 'Yığma (1960 öncesi)',
                'base_quality': 2.5,
                'year_range': (1945, 1959)
            },
            'celik': {
                'damage_factor': 0.15,
                'prob': 0.02,
                'description': 'Çelik Karkas (2010+)',
                'base_quality': 10,
                'year_range': (2010, 2025)
            }
        }
        
        self.soil_types = {
            'A': {'amplification': 1.0, 'liquefaction_risk': 0.0, 'description': 'Sağlam kaya', 'quality_modifier': 1.2},
            'B': {'amplification': 1.2, 'liquefaction_risk': 0.1, 'description': 'Kaya', 'quality_modifier': 1.1},
            'C': {'amplification': 1.5, 'liquefaction_risk': 0.3, 'description': 'Sert zemin', 'quality_modifier': 1.0},
            'D': {'amplification': 2.0, 'liquefaction_risk': 0.5, 'description': 'Yumuşak zemin', 'quality_modifier': 0.85},
            'E': {'amplification': 2.5, 'liquefaction_risk': 0.8, 'description': 'Çok yumuşak zemin', 'quality_modifier': 0.7}
        }
    
    def generate_full_name(self):
        return f"{random.choice(self.turkish_names)} {random.choice(self.turkish_surnames)}"
    
    def generate_phone(self):
        prefix = random.choice(['532', '533', '534', '535', '536'])
        return f"0{prefix}{''.join([str(random.randint(0, 9)) for _ in range(7)])}"
    
    def normalize_turkish_chars(self, text):
        """Türkçe karakterleri email-safe karakterlere dönüştürür"""
        replacements = {
            'ı': 'i', 'İ': 'i',
            'ğ': 'g', 'Ğ': 'g',
            'ü': 'u', 'Ü': 'u',
            'ş': 's', 'Ş': 's',
            'ö': 'o', 'Ö': 'o',
            'ç': 'c', 'Ç': 'c'
        }
        for turkish_char, latin_char in replacements.items():
            text = text.replace(turkish_char, latin_char)
        return text
    
    def generate_email(self, name):
        name_part = self.normalize_turkish_chars(name.lower()).replace(' ', '.')
        return f"{name_part}{random.randint(1, 999)}@gmail.com"
    
    def generate_policy_number(self, index):
        policy_num = f"DP-{self.current_year}-{index:08d}"
        self.used_policy_numbers.add(policy_num)
        return policy_num
    
    def generate_tc_no(self):
        tc_no = f"{random.randint(1, 9)}{''.join([str(random.randint(0, 9)) for _ in range(10)])}"
        self.used_tc_numbers.add(tc_no)
        return tc_no
    
    def validate_value_range(self, value, field_name):
        if field_name not in self.valid_ranges:
            return value
        
        min_val, max_val = self.valid_ranges[field_name]
        
        if value < min_val:
            self.quality_stats['outliers_prevented'] += 1
            return min_val
        elif value > max_val:
            self.quality_stats['outliers_prevented'] += 1
            return max_val
        
        return value
    
    def validate_consistency(self, building_data):
        fixed = False
        
        expected_age = self.current_year - building_data['construction_year']
        if abs(building_data['building_age'] - expected_age) > 1:
            building_data['building_age'] = expected_age
            fixed = True
        
        if building_data['insurance_value_tl'] > 0:
            prem_ratio = building_data['annual_premium_tl'] / building_data['insurance_value_tl']
            if prem_ratio < 0.003 or prem_ratio > 0.02:
                building_data['annual_premium_tl'] = building_data['insurance_value_tl'] * 0.008 * (0.5 + building_data['risk_score'])
                building_data['monthly_premium_tl'] = building_data['annual_premium_tl'] / 12
                fixed = True
        
        if fixed:
            self.quality_stats['inconsistencies_fixed'] += 1
        
        return building_data
    
    def generate_address(self, neighborhood):
        street_name = random.choice(self.street_names)
        apartment_name = random.choice(self.apartment_names)
        street_no = random.randint(1, 250)
        floor = random.randint(1, 20)
        apartment_no = random.randint(1, 50)
        
        return {
            'street': f"{street_name} Sokak",
            'street_no': street_no,
            'apartment_name': f"{apartment_name} Apartmanı",
            'floor': floor,
            'apartment_no': apartment_no,
            'complete_address': f"{apartment_name} Apartmanı, Kat: {floor}, Daire: {apartment_no}, {street_name} Sokak No: {street_no}, {neighborhood}"
        }
    
    def calculate_risk_score(self, building_age, distance_to_fault, soil_amp, liq_risk, damage_factor):
        fault_risk = 1.0 / (1 + distance_to_fault / 30)
        soil_risk = (soil_amp - 1.0) / 1.5 + liq_risk * 0.5
        age_risk = min(building_age / 60, 1.0)
        structure_risk = damage_factor / 1.5
        
        risk_score = (
            fault_risk * 0.40 +
            soil_risk * 0.25 +
            age_risk * 0.20 +
            structure_risk * 0.15
        )
        
        return min(max(risk_score, 0.0), 1.0)
    
    def calculate_quality_score(self, struct_quality, soil_modifier, building_age):
        quality_with_soil = struct_quality * soil_modifier
        age_degradation = 1.0 - (building_age / 100) * 0.5
        final_quality = quality_with_soil * age_degradation
        
        return min(max(final_quality, 1.0), 10.0)
    
    def generate_single_building(self, args):
        """Tek bir binayı oluştur - multiprocessing için"""
        i, customer_list, city_data = args
        
        try:
            # Müşteri seç (döngüsel)
            customer = customer_list[i % len(customer_list)]
            customer_id = customer['customer_id']
            city = 'İstanbul'
            
            # Bina oluştur
            district = random.choice(list(city_data['districts'].keys()))
            district_data = city_data['districts'][district]
            neighborhood = random.choice(district_data['neighborhoods'])
            lat = district_data['lat'] + np.random.normal(0, 0.01)
            lon = district_data['lon'] + np.random.normal(0, 0.01)
            address_info = self.generate_address(neighborhood)
            
            struct_probs = [v['prob'] for v in self.structure_types.values()]
            struct_type = np.random.choice(list(self.structure_types.keys()), p=struct_probs)
            struct_info = self.structure_types[struct_type]
            
            year_min, year_max = struct_info['year_range']
            construction_year = np.random.randint(year_min, year_max + 1)
            construction_year = int(self.validate_value_range(construction_year, 'construction_year'))
            
            building_age = self.current_year - construction_year
            building_age = int(self.validate_value_range(building_age, 'building_age'))
            
            soil_type = np.random.choice(list(self.soil_types.keys()), p=[0.1, 0.2, 0.3, 0.3, 0.1])
            soil_info = self.soil_types[soil_type]
            
            floors = np.random.choice([1,2,3,4,5,6,7,8,10], p=[0.05,0.1,0.15,0.2,0.15,0.1,0.08,0.1,0.07])
            floors = int(self.validate_value_range(floors, 'floors'))
            
            apartment_count = floors if floors <= 2 else floors * random.randint(2, 8)
            building_area_m2 = np.random.gamma(5, 20) + 50
            building_area_m2 = self.validate_value_range(building_area_m2, 'building_area_m2')
            
            residents = np.random.randint(1, apartment_count * 4)
            residents = int(self.validate_value_range(residents, 'residents'))
            
            commercial_units = np.random.choice([0, 1, 2], p=[0.7, 0.2, 0.1])
            
            min_dist = float('inf')
            nearest_fault = None
            for fault_name, fault_info in self.fault_lines.items():
                dist = geodesic((lat, lon), (fault_info['lat'], fault_info['lon'])).km
                if dist < min_dist:
                    min_dist = dist
                    nearest_fault = fault_info['name']
            
            base_value_per_m2 = 15000
            year_depreciation = min(building_age * 0.01, 0.30)
            insurance_value_tl = building_area_m2 * base_value_per_m2 * (1 - year_depreciation)
            
            quality_score = self.calculate_quality_score(
                struct_info['base_quality'],
                soil_info['quality_modifier'],
                building_age
            )
            
            risk_score = self.calculate_risk_score(
                building_age,
                min_dist,
                soil_info['amplification'],
                soil_info['liquefaction_risk'],
                struct_info['damage_factor']
            )
            
            if (insurance_value_tl > 3_200_000 and risk_score < 0.30) or (quality_score > 9.2 and building_age < 4):
                package_type = 'premium'
                max_coverage = 1_500_000
                base_rate = 0.012
            elif (insurance_value_tl >= 1_500_000 and insurance_value_tl <= 3_200_000 and
                  risk_score >= 0.25 and risk_score <= 0.60):
                package_type = 'standard'
                max_coverage = 750_000
                base_rate = 0.008
            else:
                package_type = 'temel'
                max_coverage = 250_000
                base_rate = 0.005
            
            risk_multiplier = 1.0 + (risk_score - 0.5)
            annual_premium = max_coverage * base_rate * max(risk_multiplier, 0.5)
            monthly_premium = annual_premium / 12
            
            policy_status = random.choices(['Aktif', 'Pasif'], weights=[95, 5], k=1)[0]
            policy_start_date = datetime.now() - timedelta(days=random.randint(0, 365))
            policy_end_date = policy_start_date + timedelta(days=365)
            
            building = {
                'building_id': f'BLD_{i:06d}',
                'customer_id': customer_id,
                'owner_name': customer['full_name'],
                'owner_email': customer['email'],
                'owner_phone': customer['phone'],
                'policy_number': self.generate_policy_number(i),
                'city': city,
                'district': district,
                'neighborhood': neighborhood,
                'complete_address': address_info['complete_address'],
                'latitude': lat,
                'longitude': lon,
                'structure_type': struct_type,
                'construction_year': construction_year,
                'building_age': building_age,
                'floors': floors,
                'apartment_count': apartment_count,
                'building_area_m2': building_area_m2,
                'residents': residents,
                'commercial_units': commercial_units,
                'soil_type': soil_type,
                'soil_amplification': soil_info['amplification'],
                'liquefaction_risk': soil_info['liquefaction_risk'],
                'distance_to_fault_km': min_dist,
                'nearest_fault': nearest_fault,
                'quality_score': round(quality_score, 2),
                'risk_score': round(risk_score, 4),
                'package_type': package_type,
                'max_coverage': max_coverage,
                'insurance_value_tl': int(insurance_value_tl),
                'annual_premium_tl': round(annual_premium, 2),
                'monthly_premium_tl': round(monthly_premium, 2),
                'policy_status': policy_status,
                'policy_start_date': policy_start_date.strftime('%Y-%m-%d'),
                'policy_end_date': policy_end_date.strftime('%Y-%m-%d'),
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return building
        except Exception as e:
            print(f"Hata building {i}: {e}")
            return None
    
    def generate_buildings(self, n_buildings=10000):
        """
        Binaları oluştur - her binaya customer bilgisi ekle
        10.000 bina oluştur, 8.000-9.500 müşteri arası
        Her müşteri maksimum 2 poliçe alabilir (bazıları 1, bazıları 2)
        """
        print(f"\n[BINA] {n_buildings} adet bina olusturuluyor...")
        
        buildings = []
        self.quality_stats['total_generated'] = n_buildings
        city = 'İstanbul'
        city_data = self.locations[city]
        
        # Müşteri sayısı: 8.000 ile 9.500 arasında rastgele
        n_customers = random.randint(8000, 9500)
        customer_list = []
        
        print(f"   [OK] {n_customers} musteri olusturulacak...")
        
        for cust_idx in range(n_customers):
            first_name = random.choice(self.turkish_names)
            last_name = random.choice(self.turkish_surnames)
            customer_id = f"CUST{cust_idx:06d}"
            email = f"{self.normalize_turkish_chars(first_name.lower())}.{self.normalize_turkish_chars(last_name.lower())}{cust_idx}@email.com"
            phone = f"+90 {random.randint(500, 599)} {random.randint(100, 999)} {random.randint(10, 99)} {random.randint(10, 99)}"
            tc_number = f"{random.randint(10000000000, 99999999999)}"
            
            # Şifre - demo için basit
            password = "dask2024"
            password_hash = "demo_hash_dask2024"
            password_salt = "demo_salt"
            password_aes = "demo_aes_dask2024"
            
            avatar_url = f"https://ui-avatars.com/api/?name={first_name}+{last_name}&background=random&color=fff&size=400"
            
            customer_list.append({
                'customer_id': customer_id,
                'first_name': first_name,
                'last_name': last_name,
                'full_name': f"{first_name} {last_name}",
                'email': email,
                'phone': phone,
                'tc_number': tc_number,
                'password': password,
                'password_hash': password_hash,
                'password_salt': password_salt,
                'password_aes_encrypted': password_aes,
                'avatar_url': avatar_url,
                'status': random.choice(['Aktif', 'Aktif', 'Aktif', 'Pasif']),
                'registration_date': (datetime.now() - timedelta(days=random.randint(0, 365))).strftime('%Y-%m-%d'),
                'last_login': (datetime.now() - timedelta(days=random.randint(0, 30))).strftime('%Y-%m-%d %H:%M:%S'),
                'customer_score': random.randint(70, 100)
            })
        
        print(f"   [OK] {len(customer_list)} musteri olusturuldu")
        
        # Müşteri başına poliçe sayısı belirleme
        # %70 müşteri 1 poliçe, %30 müşteri 2 poliçe alacak
        buildings_per_customer = []
        
        for customer in customer_list:
            # %91 ihtimalle 1 poliçe, %9 ihtimalle 2 poliçe
            policies_count = random.choices([1, 2], weights=[91, 9], k=1)[0]
            
            # Her müşteri için belirlenen sayıda bina ata
            for _ in range(policies_count):
                buildings_per_customer.append(customer)
        
        # Total atadığımız bina sayısı
        total_assigned = len(buildings_per_customer)
        
        # Eğer n_buildings'ten az ise, fazla binaları rastgele müşterilere ata (max 2 poliçe)
        if total_assigned < n_buildings:
            extra_count = n_buildings - total_assigned
            
            for _ in range(extra_count):
                # Şu an 1 poliçesi olan müşteri bul
                customers_with_one = [c for c in customer_list 
                                     if buildings_per_customer.count(c) == 1]
                
                if customers_with_one:
                    customer = random.choice(customers_with_one)
                    buildings_per_customer.append(customer)
                else:
                    # Herkese 2 verilmişse, 1'i rastgele seç
                    customer = random.choice(customer_list)
                    buildings_per_customer.append(customer)
        
        # Fazla bina varsa kırp (max n_buildings)
        buildings_per_customer = buildings_per_customer[:n_buildings]
        
        print(f"   [MP] Toplam {len(buildings_per_customer)} bina dağıtıldı")
        print(f"   [MP] {cpu_count()} CPU core kullanılıyor...")
        
        # Binaları müşterilere ata (shuffled order)
        random.shuffle(buildings_per_customer)
        customer_assignment = []
        
        for i in range(len(buildings_per_customer)):
            customer = buildings_per_customer[i]
            customer_assignment.append((i, [customer], city_data))
        
        # Multiprocessing Pool kullan
        with Pool(processes=cpu_count()) as pool:
            buildings_list = []
            for idx, building in enumerate(pool.imap_unordered(self.generate_single_building, customer_assignment, chunksize=500)):
                if building is not None:
                    buildings_list.append(building)
                    self.quality_stats['validation_passed'] += 1
                
                if (idx + 1) % 5000 == 0:
                    print(f"   [OK] {idx + 1}/{n_buildings} bina olusturuldu")
        
        print(f"   [OK] {len(buildings_list)}/{n_buildings} bina olusturuldu")
        
        buildings_df = pd.DataFrame(buildings_list)
        
        # Müşteri DataFrame'ini de döndür
        customers_df = pd.DataFrame(customer_list)
        
        return buildings_df, customers_df
    
    def print_quality_report(self):
        print("\n" + "="*70)
        print("[REPORT] VERİ KALİTE RAPORU")
        print("="*70)
        
        total = self.quality_stats['total_generated']
        passed = self.quality_stats['validation_passed']
        
        print(f"\n[STATS] GENEL:")
        print(f"   * Toplam: {total:,}")
        print(f"   * Validasyon Gecen: {passed:,} ({passed/total*100:.2f}%)")
        print("="*70 + "\n")
    
    def create_database(self):
        """
        SQLite veritabanı oluştur ve tabloları tanımla
        """
        print(f"\n[DB] SQLite veritabanı oluşturuluyor: {self.db_path}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Customers tablosu
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            tc_number TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            password_aes_encrypted TEXT NOT NULL,
            avatar_url TEXT,
            status TEXT DEFAULT 'Aktif',
            registration_date DATE,
            last_login DATETIME,
            customer_score INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Buildings tablosu
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS buildings (
            building_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            owner_name TEXT NOT NULL,
            owner_email TEXT NOT NULL,
            owner_phone TEXT NOT NULL,
            policy_number TEXT UNIQUE NOT NULL,
            city TEXT NOT NULL,
            district TEXT NOT NULL,
            neighborhood TEXT NOT NULL,
            complete_address TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            structure_type TEXT NOT NULL,
            construction_year INTEGER NOT NULL,
            building_age INTEGER NOT NULL,
            floors INTEGER NOT NULL,
            apartment_count INTEGER NOT NULL,
            building_area_m2 REAL NOT NULL,
            residents INTEGER NOT NULL,
            commercial_units INTEGER DEFAULT 0,
            soil_type TEXT NOT NULL,
            soil_amplification REAL NOT NULL,
            liquefaction_risk REAL NOT NULL,
            distance_to_fault_km REAL NOT NULL,
            nearest_fault TEXT NOT NULL,
            quality_score REAL NOT NULL,
            risk_score REAL NOT NULL,
            package_type TEXT NOT NULL,
            max_coverage INTEGER NOT NULL,
            insurance_value_tl INTEGER NOT NULL,
            annual_premium_tl REAL NOT NULL,
            monthly_premium_tl REAL NOT NULL,
            policy_status TEXT DEFAULT 'Aktif',
            policy_start_date DATE,
            policy_end_date DATE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
        )
        ''')
        
        # Earthquakes tablosu
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS earthquakes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            no TEXT,
            earthquake_code TEXT,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            depth_km REAL,
            xM REAL,
            MD REAL,
            ML REAL,
            Mw REAL,
            Ms REAL,
            Mb REAL,
            type TEXT,
            location TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Blockchain Records tablosu (blockchain kayıtları için)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS blockchain_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            block_index INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            data_type TEXT NOT NULL,
            data_json TEXT NOT NULL,
            previous_hash TEXT,
            block_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Indexes oluştur
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_customer_email ON customers(email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_customer_status ON customers(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_building_customer ON buildings(customer_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_building_location ON buildings(latitude, longitude)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_building_policy ON buildings(policy_number)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_building_status ON buildings(policy_status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_earthquake_location ON earthquakes(latitude, longitude)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_earthquake_date ON earthquakes(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_blockchain_type ON blockchain_records(data_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_blockchain_hash ON blockchain_records(block_hash)')
        
        conn.commit()
        conn.close()
        
        print(f"   [OK] Veritabanı oluşturuldu: {self.db_path}")
        print(f"   [OK] Tablolar: customers, buildings, earthquakes, blockchain_records")
        print(f"   [OK] Indexler oluşturuldu")
    
    def save_to_database(self, customers_df, buildings_df):
        """
        DataFrame'leri SQLite veritabanına kaydet
        """
        print(f"\n[DB] Veriler SQLite'a kaydediliyor...")
        
        conn = sqlite3.connect(self.db_path)
        
        # Customers tablosunu kaydet
        print(f"   [DB] Customers tablosu kaydediliyor ({len(customers_df)} kayıt)...")
        customers_df.to_sql('customers', conn, if_exists='replace', index=False)
        print(f"   [OK] {len(customers_df)} müşteri kaydedildi")
        
        # Buildings tablosunu kaydet
        print(f"   [DB] Buildings tablosu kaydediliyor ({len(buildings_df)} kayıt)...")
        buildings_df.to_sql('buildings', conn, if_exists='replace', index=False)
        print(f"   [OK] {len(buildings_df)} bina kaydedildi")
        
        # Earthquakes CSV'sini yükle ve kaydet
        earthquakes_csv = self.data_dir / 'earthquakes.csv'
        if earthquakes_csv.exists():
            print(f"   [DB] Earthquakes CSV'si yükleniyor...")
            earthquakes_df = pd.read_csv(earthquakes_csv, encoding='utf-8-sig')
            
            # Sütun adlarını düzenle
            earthquakes_df.columns = [
                'no', 'earthquake_code', 'date', 'time', 'latitude', 'longitude',
                'depth_km', 'xM', 'MD', 'ML', 'Mw', 'Ms', 'Mb', 'type', 'location'
            ]
            
            print(f"   [DB] Earthquakes tablosu kaydediliyor ({len(earthquakes_df)} kayıt)...")
            earthquakes_df.to_sql('earthquakes', conn, if_exists='replace', index=False)
            print(f"   [OK] {len(earthquakes_df)} deprem kaydedildi")
        else:
            print(f"   [WARN] earthquakes.csv bulunamadı, atlanıyor...")
        
        # Blockchain records JSON'ını yükle ve kaydet (varsa)
        blockchain_json = self.data_dir / 'blockchain_policies.json'
        if blockchain_json.exists():
            print(f"   [DB] Blockchain records JSON'ı yükleniyor...")
            try:
                with open(blockchain_json, 'r', encoding='utf-8') as f:
                    blockchain_data = json.load(f)
                
                # JSON'dan DataFrame oluştur
                if isinstance(blockchain_data, list) and len(blockchain_data) > 0:
                    records = []
                    for block in blockchain_data:
                        records.append({
                            'block_index': block.get('index', 0),
                            'timestamp': block.get('timestamp', ''),
                            'data_type': block.get('data', {}).get('type', 'unknown'),
                            'data_json': json.dumps(block.get('data', {})),
                            'previous_hash': block.get('previous_hash', ''),
                            'block_hash': block.get('hash', '')
                        })
                    
                    blockchain_df = pd.DataFrame(records)
                    print(f"   [DB] Blockchain records tablosu kaydediliyor ({len(blockchain_df)} kayıt)...")
                    blockchain_df.to_sql('blockchain_records', conn, if_exists='replace', index=False)
                    print(f"   [OK] {len(blockchain_df)} blockchain kaydı kaydedildi")
                else:
                    print(f"   [WARN] Blockchain JSON boş, atlanıyor...")
            except Exception as e:
                print(f"   [ERROR] Blockchain JSON yüklenemedi: {e}")
        else:
            print(f"   [INFO] blockchain_policies.json bulunamadı, atlanıyor...")
        
        conn.close()
        
        print(f"   [OK] Tüm veriler SQLite'a kaydedildi: {self.db_path}")
        
        # Veritabanı istatistikleri
        self.print_database_stats()
    
    def print_database_stats(self):
        """
        Veritabanı istatistiklerini göster
        """
        print(f"\n[DB] Veritabanı İstatistikleri:")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Customer sayısı
        cursor.execute("SELECT COUNT(*) FROM customers")
        customer_count = cursor.fetchone()[0]
        
        # Aktif müşteri sayısı
        cursor.execute("SELECT COUNT(*) FROM customers WHERE status='Aktif'")
        active_customers = cursor.fetchone()[0]
        
        # Building sayısı
        cursor.execute("SELECT COUNT(*) FROM buildings")
        building_count = cursor.fetchone()[0]
        
        # Aktif poliçe sayısı
        cursor.execute("SELECT COUNT(*) FROM buildings WHERE policy_status='Aktif'")
        active_policies = cursor.fetchone()[0]
        
        # Toplam teminat
        cursor.execute("SELECT SUM(max_coverage) FROM buildings WHERE policy_status='Aktif'")
        total_coverage = cursor.fetchone()[0] or 0
        
        # Toplam prim
        cursor.execute("SELECT SUM(annual_premium_tl) FROM buildings WHERE policy_status='Aktif'")
        total_premium = cursor.fetchone()[0] or 0
        
        # Paket dağılımı
        cursor.execute("SELECT package_type, COUNT(*) FROM buildings GROUP BY package_type")
        package_dist = cursor.fetchall()
        
        # Earthquake sayısı
        try:
            cursor.execute("SELECT COUNT(*) FROM earthquakes")
            earthquake_count = cursor.fetchone()[0]
        except:
            earthquake_count = 0
        
        # Blockchain records sayısı
        try:
            cursor.execute("SELECT COUNT(*) FROM blockchain_records")
            blockchain_count = cursor.fetchone()[0]
        except:
            blockchain_count = 0
        
        conn.close()
        
        print(f"   • Toplam Müşteri: {customer_count:,}")
        print(f"   • Aktif Müşteri: {active_customers:,} (%{active_customers/customer_count*100:.1f})")
        print(f"   • Toplam Bina: {building_count:,}")
        print(f"   • Aktif Poliçe: {active_policies:,} (%{active_policies/building_count*100:.1f})")
        print(f"   • Toplam Teminat: {total_coverage:,} TL")
        print(f"   • Toplam Yıllık Prim: {total_premium:,.2f} TL")
        
        if earthquake_count > 0:
            print(f"   • Toplam Deprem Kaydı: {earthquake_count:,}")
        
        if blockchain_count > 0:
            print(f"   • Toplam Blockchain Kaydı: {blockchain_count:,}")
        
        print(f"\n   Paket Dağılımı:")
        for package, count in package_dist:
            print(f"      - {package}: {count:,} (%{count/building_count*100:.1f})")
        print("="*70 + "\n")


def main():
    print("="*70)
    print("DASK+ - VERİ ÜRETİCİ")
    print("="*70)
    
    generator = RealisticDataGenerator()
    
    # SQLite veritabanını oluştur
    generator.create_database()
    
    # Binaları ve müşterileri üret
    buildings_df, customers_df = generator.generate_buildings(n_buildings=10000)
    
    # DEBUG: customer_id var mı kontrol et
    print(f"\n[DEBUG] Buildings DF shape: {buildings_df.shape}")
    print(f"[DEBUG] Buildings columns: {list(buildings_df.columns)[:5]}...")
    print(f"[DEBUG] 'customer_id' in columns: {'customer_id' in buildings_df.columns}")
    
    # CSV'ye kaydet (backward compatibility)
    buildings_df.to_csv(generator.data_dir / 'buildings.csv', index=False, encoding='utf-8-sig')
    print(f"\n[OK] Bina CSV'si kaydedildi: {len(buildings_df)} kayıt")
    
    customers_df.to_csv(generator.data_dir / 'customers.csv', index=False, encoding='utf-8-sig')
    print(f"[OK] Müşteri CSV'si kaydedildi: {len(customers_df)} kayıt")
    
    # SQLite veritabanına kaydet
    generator.save_to_database(customers_df, buildings_df)
    
    # Kalite raporu
    generator.print_quality_report()
    
    # Test verisi
    print("\n[TEST] İlk müşteri:")
    if len(customers_df) > 0:
        test_cust = customers_df.iloc[0]
        print(f"   Email: {test_cust['email']}")
        print(f"   Şifre: {test_cust['password']}")
        print(f"   Customer ID: {test_cust['customer_id']}")
        
        # Bu müşterinin kaç binası var?
        cust_buildings = buildings_df[buildings_df['customer_id'] == test_cust['customer_id']]
        print(f"   Bina sayısı: {len(cust_buildings)}")
    
    print(f"\n[OK] Tamamlandı!")
    print("="*70 + "\n")


def generate_customers(self, n_customers=100):
    """
    Müşteri verilerini oluştur - şifre ve autentikasyon dahil
    
    Args:
        n_customers: Kaç müşteri oluşturulacak
        
    Returns:
        pd.DataFrame: Müşteri verileri
    """
    customers = []
    
    print(f"\n[MUSTERI] {n_customers} müşteri verisi oluşturuluyor...")
    
    for i in range(n_customers):
        first_name = random.choice(self.turkish_names)
        last_name = random.choice(self.turkish_surnames)
        
        # TC Kimlik Numarası (fake)
        tc_number = f"{random.randint(10000000000, 99999999999)}"
        
        # Email ve iletişim
        email = f"{self.normalize_turkish_chars(first_name.lower())}.{self.normalize_turkish_chars(last_name.lower())}{i}@email.com"
        phone = f"+90 {random.randint(500, 599)} {random.randint(100, 999)} {random.randint(10, 99)} {random.randint(10, 99)}"
        
        # Şifre (aynı şifreler - demo için)
        password = "dask2024"
        
        # Password hashing ve encryption
        if PasswordManager:
            pwd_data = PasswordManager.hash_password(password)
            password_hash = pwd_data['hash']
            password_salt = pwd_data['salt']
            password_aes_encrypted = pwd_data['aes_encrypted']
        else:
            password_hash = "demo_hash"
            password_salt = "demo_salt"
            password_aes_encrypted = "demo_encrypted"
        
        # Profil fotosu URL'i (anonim avatar)
        avatar_url = f"https://ui-avatars.com/api/?name={first_name}+{last_name}&background=random&color=fff&size=400"
        
        # Müşteri durumu
        customer_status = random.choice(['Aktif', 'Aktif', 'Aktif', 'Aktif', 'Aktif', 'Aktif', 'Pasif'])
        
        # Müşteri oluşturma tarihi
        registration_date = datetime.now() - timedelta(days=random.randint(0, 365))
        
        # Müşteri başarı puanı
        customer_score = random.randint(70, 100)
        
        # Son giriş
        last_login = datetime.now() - timedelta(days=random.randint(0, 30))
        
        customer = {
            'customer_id': f"CUST{i+1:06d}",
            'tc_number': tc_number,
            'first_name': first_name,
            'last_name': last_name,
            'full_name': f"{first_name} {last_name}",
            'email': email,
            'phone': phone,
            'password': password,  # Plain (demo için - production'da silinecek)
            'password_hash': password_hash,
            'password_salt': password_salt,
            'password_aes_encrypted': password_aes_encrypted,
            'avatar_url': avatar_url,
            'status': customer_status,
            'registration_date': registration_date.strftime('%Y-%m-%d'),
            'last_login': last_login.strftime('%Y-%m-%d %H:%M:%S'),
            'customer_score': customer_score,
            'active_policies': random.randint(1, 3),
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        customers.append(customer)
        
        if (i + 1) % 20 == 0:
            print(f"   [OK] {i + 1}/{n_customers} musteri olusturuldu")
    
    print(f"   [OK] {n_customers} musteri basarıyla olusturuldu")
    return pd.DataFrame(customers)


# Generator class'ına generate_customers metodunu ekle
RealisticDataGenerator.generate_customers = generate_customers


if __name__ == "__main__":
    main()
