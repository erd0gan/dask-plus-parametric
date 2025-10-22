# -*- coding: utf-8 -*-
"""
Kimlik Doğrulama ve Şifreleme Sistemi
=====================================
AES-256 şifreleme, password hashing, JWT tokens
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import json
import base64
import jwt
import logging

logger = logging.getLogger(__name__)

class PasswordManager:
    """Şifre yönetimi ve hashing"""
    
    @staticmethod
    def hash_password(password: str, algorithm='pbkdf2') -> dict:
        """
        Şifreyi hash'le (plain ve AES-256)
        
        Args:
            password: Plain text password
            algorithm: Hash algoritması (pbkdf2, bcrypt, argon2)
            
        Returns:
            dict: {
                'plain': şifre,
                'hash': pbkdf2 hash,
                'salt': salt değeri,
                'aes_encrypted': AES-256 encrypted
            }
        """
        try:
            # Plain text
            plain_password = password
            
            # PBKDF2 hashing
            salt = secrets.token_hex(32)
            hash_obj = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                bytes.fromhex(salt),
                100000  # iterations
            )
            hashed = hash_obj.hex()
            
            # AES-256 Encryption
            aes_encrypted = PasswordManager.aes_encrypt(password)
            
            return {
                'plain': plain_password,  # Development için (production'da kaldırılacak)
                'hash': hashed,
                'salt': salt,
                'aes_encrypted': aes_encrypted,
                'created_at': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Password hashing error: {e}")
            raise
    
    @staticmethod
    def verify_password(password: str, stored_hash: str, salt: str) -> bool:
        """
        Şifreyi doğrula
        
        Args:
            password: Plain text password to verify
            stored_hash: Depolanan hash
            salt: Depolanan salt
            
        Returns:
            bool: Şifre doğru mu?
        """
        try:
            hash_obj = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                bytes.fromhex(salt),
                100000
            )
            return hash_obj.hex() == stored_hash
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    @staticmethod
    def aes_encrypt(plaintext: str, key: str = None) -> str:
        """
        AES-256-CBC ile şifrele
        
        Args:
            plaintext: Şifrelenecek metin
            key: Şifreleme anahtarı (None ise default kullan)
            
        Returns:
            str: IV + Ciphertext (base64 encoded)
        """
        try:
            # Default key (production'da environment variable kullan)
            if key is None:
                key = os.environ.get('AES_KEY', 'DASK-PARAMETRIK-SIGORTA-AES256-KEY-2025!')
            
            # Key'i 32 bytes (256 bits) yapmamız lazım
            if len(key) < 32:
                key = (key * (32 // len(key) + 1))[:32]
            
            # IV oluştur (Initialization Vector)
            iv = get_random_bytes(16)
            
            # Cipher oluştur
            cipher = AES.new(key.encode('utf-8')[:32], AES.MODE_CBC, iv)
            
            # Plaintext'i PKCS7 padding ile doldur
            plaintext_bytes = plaintext.encode('utf-8')
            padding_length = 16 - (len(plaintext_bytes) % 16)
            plaintext_bytes += bytes([padding_length] * padding_length)
            
            # Şifrele
            ciphertext = cipher.encrypt(plaintext_bytes)
            
            # IV + Ciphertext'i base64 encode et
            encrypted_data = base64.b64encode(iv + ciphertext).decode('utf-8')
            
            return encrypted_data
        except Exception as e:
            logger.error(f"AES encryption error: {e}")
            raise
    
    @staticmethod
    def aes_decrypt(encrypted_data: str, key: str = None) -> str:
        """
        AES-256-CBC ile çöz
        
        Args:
            encrypted_data: Base64 encoded IV + Ciphertext
            key: Şifreleme anahtarı
            
        Returns:
            str: Orijinal plaintext
        """
        try:
            # Default key
            if key is None:
                key = os.environ.get('AES_KEY', 'DASK-PARAMETRIK-SIGORTA-AES256-KEY-2025!')
            
            if len(key) < 32:
                key = (key * (32 // len(key) + 1))[:32]
            
            # Base64 decode
            encrypted_bytes = base64.b64decode(encrypted_data)
            
            # IV ve Ciphertext'i ayır
            iv = encrypted_bytes[:16]
            ciphertext = encrypted_bytes[16:]
            
            # Cipher oluştur ve çöz
            cipher = AES.new(key.encode('utf-8')[:32], AES.MODE_CBC, iv)
            plaintext_bytes = cipher.decrypt(ciphertext)
            
            # Padding'i kaldır
            padding_length = plaintext_bytes[-1]
            plaintext_bytes = plaintext_bytes[:-padding_length]
            
            return plaintext_bytes.decode('utf-8')
        except Exception as e:
            logger.error(f"AES decryption error: {e}")
            raise


class TokenManager:
    """JWT Token yönetimi"""
    
    SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'DASK-PARAMETRIK-JWT-SECRET-2025!')
    ALGORITHM = 'HS256'
    EXPIRATION_HOURS = 24
    
    @classmethod
    def create_token(cls, customer_id: str, email: str, name: str = None) -> str:
        """
        JWT token oluştur
        
        Args:
            customer_id: Müşteri ID
            email: Müşteri email
            name: Müşteri adı
            
        Returns:
            str: JWT token
        """
        try:
            payload = {
                'customer_id': customer_id,
                'email': email,
                'name': name,
                'iat': datetime.utcnow(),
                'exp': datetime.utcnow() + timedelta(hours=cls.EXPIRATION_HOURS)
            }
            
            token = jwt.encode(payload, cls.SECRET_KEY, algorithm=cls.ALGORITHM)
            return token
        except Exception as e:
            logger.error(f"Token creation error: {e}")
            raise
    
    @classmethod
    def verify_token(cls, token: str) -> dict:
        """
        JWT token doğrula
        
        Args:
            token: JWT token
            
        Returns:
            dict: Token payload
        """
        try:
            payload = jwt.decode(token, cls.SECRET_KEY, algorithms=[cls.ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None


class AuthDecorator:
    """Flask route decorators için authentication"""
    
    @staticmethod
    def require_login(f):
        """Login gerekli olan route'lar için decorator"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import request
            
            # Header'dan token al
            auth_header = request.headers.get('Authorization')
            if not auth_header:
                return {'error': 'Missing authorization header'}, 401
            
            try:
                # Bearer token'ı al
                parts = auth_header.split()
                if len(parts) != 2 or parts[0].lower() != 'bearer':
                    return {'error': 'Invalid authorization header'}, 401
                
                token = parts[1]
                payload = TokenManager.verify_token(token)
                
                if not payload:
                    return {'error': 'Invalid or expired token'}, 401
                
                # Token'ı request'e ekle
                request.user = payload
                
            except Exception as e:
                logger.error(f"Auth decorator error: {e}")
                return {'error': 'Authentication failed'}, 401
            
            return f(*args, **kwargs)
        
        return decorated_function


# Test için kullanılabilecek helper functions
def generate_demo_customer_password():
    """Demo müşteri için şifre oluştur"""
    password = "dask2024demo"
    return PasswordManager.hash_password(password)


if __name__ == '__main__':
    # Test
    pwd_data = PasswordManager.hash_password("TestPassword123")
    print("Password Data:", json.dumps(pwd_data, indent=2, default=str))
    
    # Verify
    is_valid = PasswordManager.verify_password("TestPassword123", pwd_data['hash'], pwd_data['salt'])
    print("Password Valid:", is_valid)
    
    # AES Test
    encrypted = PasswordManager.aes_encrypt("TestPassword123")
    print("AES Encrypted:", encrypted)
    decrypted = PasswordManager.aes_decrypt(encrypted)
    print("AES Decrypted:", decrypted)
