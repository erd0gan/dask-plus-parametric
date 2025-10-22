#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API Test Script
===============
Tüm endpoints'i test et
"""
import requests
import json

BASE_URL = "http://localhost:5000"

# Demo Account
DEMO_EMAIL = "ali.yılmaz0@email.com"
DEMO_PASSWORD = "dask2024"

def test_customer_endpoint():
    """Müşteri bilgilerini getir"""
    print("\n" + "="*70)
    print("[TEST 1] GET /api/customer/<customer_id>")
    print("="*70)
    
    try:
        response = requests.get(f"{BASE_URL}/api/customer/CUST000001")
        data = response.json()
        
        if data.get('success'):
            customer = data['customer']
            print(f"✓ Status: {response.status_code}")
            print(f"✓ Müşteri: {customer['full_name']}")
            print(f"✓ Email: {customer['email']}")
            print(f"✓ Avatar: {customer['avatar_url'][:50]}...")
            print(f"✓ Poliçe Sayısı: {customer['total_properties']}")
        else:
            print(f"✗ Hata: {data.get('error')}")
    except Exception as e:
        print(f"✗ Bağlantı hatası: {e}")


def test_policy_details():
    """Poliçe detaylarını getir"""
    print("\n" + "="*70)
    print("[TEST 2] GET /api/policy-details/<customer_id>")
    print("="*70)
    
    try:
        response = requests.get(f"{BASE_URL}/api/policy-details/CUST000001")
        data = response.json()
        
        if data.get('success'):
            policy = data['policy']
            print(f"✓ Status: {response.status_code}")
            print(f"✓ Toplam Poliçe: {policy['total_policies']}")
            print(f"✓ Poliçe Numarası: {policy['policy_number']}")
            print(f"✓ Adres: {policy['building_info']['address'][:50]}...")
            print(f"✓ Risk Skoru: {policy['risk_assessment']['risk_score']}")
            print(f"✓ Aylık Prim: ₺{policy['coverage']['monthly_premium_tl']}")
        else:
            print(f"✗ Hata: {data.get('error')}")
    except Exception as e:
        print(f"✗ Bağlantı hatası: {e}")


def test_customer_policies():
    """Tüm poliçeleri listele"""
    print("\n" + "="*70)
    print("[TEST 3] GET /api/customer-policies/<customer_id>")
    print("="*70)
    
    try:
        response = requests.get(f"{BASE_URL}/api/customer-policies/CUST000001")
        data = response.json()
        
        if data.get('success'):
            print(f"✓ Status: {response.status_code}")
            print(f"✓ Toplam Poliçe: {data['total']}")
            
            for i, policy in enumerate(data['policies'][:3], 1):
                print(f"\n  Poliçe {i}:")
                print(f"    • Numarası: {policy['policy_number']}")
                print(f"    • Durum: {policy['status']}")
                print(f"    • Teminat: ₺{policy['coverage']:,}")
        else:
            print(f"✗ Hata: {data.get('error')}")
    except Exception as e:
        print(f"✗ Bağlantı hatası: {e}")


def test_dashboard_stats():
    """Dashboard istatistiklerini getir"""
    print("\n" + "="*70)
    print("[TEST 4] GET /api/dashboard/stats/<customer_id>")
    print("="*70)
    
    try:
        response = requests.get(f"{BASE_URL}/api/dashboard/stats/CUST000001")
        data = response.json()
        
        if data.get('success'):
            stats = data['stats']
            print(f"✓ Status: {response.status_code}")
            print(f"✓ Toplam Poliçe: {stats['total_policies']}")
            print(f"✓ Aktif Poliçe: {stats['active_policies']}")
            print(f"✓ Toplam Teminat: ₺{stats['total_coverage']:,}")
        else:
            print(f"✗ Hata: {data.get('error')}")
    except Exception as e:
        print(f"✗ Bağlantı hatası: {e}")


def test_login():
    """Giriş yap ve token al"""
    print("\n" + "="*70)
    print("[TEST 5] POST /api/login")
    print("="*70)
    
    try:
        payload = {
            "email": DEMO_EMAIL,
            "password": DEMO_PASSWORD
        }
        response = requests.post(
            f"{BASE_URL}/api/login",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        data = response.json()
        
        if data.get('success'):
            print(f"✓ Status: {response.status_code}")
            print(f"✓ Müşteri: {data['customer']['name']}")
            print(f"✓ Token alındı")
        else:
            print(f"✗ Hata: {data.get('error')}")
    except Exception as e:
        print(f"✗ Bağlantı hatası: {e}")


def main():
    print("\n" + "#"*70)
    print("# DASK+ API TEST SUITE")
    print("#"*70)
    print(f"\nBase URL: {BASE_URL}")
    print("Test Müşteri ID: CUST000001")
    
    test_customer_endpoint()
    test_policy_details()
    test_customer_policies()
    test_dashboard_stats()
    test_login()
    
    print("\n" + "="*70)
    print("[SONUC] Tüm testler tamamlandı!")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()
