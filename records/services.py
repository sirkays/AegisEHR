import os
import hashlib
import base64
import json
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# System Master Key-Encryption-Key (KEK) for wrapping record keys
# In enterprise production, this resides in a Hardware Security Module (HSM) or HashiCorp Vault.
_MASTER_KEK = AESGCM.generate_key(bit_length=256)

class CryptoService:
    @staticmethod
    def generate_record_key():
        """Generates a unique 256-bit AES Data Encryption Key (DEK)."""
        return AESGCM.generate_key(bit_length=256)

    @staticmethod
    def wrap_key(dek_bytes):
        """Wraps (encrypts) the DEK using the master Key-Encryption-Key (KEK)."""
        aesgcm = AESGCM(_MASTER_KEK)
        nonce = os.urandom(12)
        wrapped = aesgcm.encrypt(nonce, dek_bytes, b"KEY_WRAP_AAD")
        return base64.b64encode(nonce + wrapped).decode('utf-8')

    @staticmethod
    def unwrap_key(wrapped_key_b64):
        """Unwraps (decrypts) the DEK using the master Key-Encryption-Key (KEK)."""
        raw = base64.b64decode(wrapped_key_b64.encode('utf-8'))
        nonce = raw[:12]
        wrapped = raw[12:]
        aesgcm = AESGCM(_MASTER_KEK)
        return aesgcm.decrypt(nonce, wrapped, b"KEY_WRAP_AAD")

    @classmethod
    def encrypt_medical_document(cls, plaintext_bytes, record_id_str, version_int):
        """
        Encrypts plaintext medical data with AES-256-GCM.
        Returns:
            ciphertext_bytes, nonce_hex, auth_tag_hex, wrapped_key_str, package_digest_hex, simulated_cid
        """
        dek = cls.generate_record_key()
        nonce = os.urandom(12)  # 96-bit fresh nonce
        aesgcm = AESGCM(dek)
        
        # Authenticated Associated Data (AAD) binds record ID and version to prevent replay
        aad = f"{record_id_str}:v{version_int}".encode('utf-8')
        
        # AESGCM.encrypt appends 16-byte auth tag at the end of ciphertext
        encrypted_data = aesgcm.encrypt(nonce, plaintext_bytes, aad)
        ciphertext = encrypted_data[:-16]
        auth_tag = encrypted_data[-16:]

        # Package format: Header (10 bytes) + Nonce (12 bytes) + Tag (16 bytes) + Ciphertext
        package_bytes = b"AEGIS_PKG1" + nonce + auth_tag + ciphertext
        
        # SHA-256 digest computed over the entire stored package
        package_digest = hashlib.sha256(package_bytes).hexdigest()
        
        # IPFS Content Identifier (CIDv0 representation: sha256 multihash with Qm prefix)
        h = hashlib.sha256(package_bytes).digest()
        # IPFS multihash prefix for sha2-256 (0x12) length 32 (0x20)
        multihash = b'\x12\x20' + h
        # Mock CID base58 representation
        cid_simulated = "Qm" + hashlib.sha256(multihash).hexdigest()[:44]
        
        wrapped_key = cls.wrap_key(dek)

        return {
            'package_bytes': package_bytes,
            'nonce_hex': nonce.hex(),
            'auth_tag_hex': auth_tag.hex(),
            'wrapped_key': wrapped_key,
            'package_digest': package_digest,
            'ipfs_cid': cid_simulated,
            'size_bytes': len(package_bytes)
        }

    @classmethod
    def decrypt_medical_document(cls, package_bytes, wrapped_key_str, record_id_str, version_int):
        """
        Decrypts an encrypted package with integrity checks.
        Validates AES-GCM authentication tag and AAD.
        """
        if not package_bytes.startswith(b"AEGIS_PKG1"):
            raise ValueError("Corrupt or invalid package header")

        nonce = package_bytes[10:22]
        auth_tag = package_bytes[22:38]
        ciphertext = package_bytes[38:]

        dek = cls.unwrap_key(wrapped_key_str)
        aesgcm = AESGCM(dek)
        aad = f"{record_id_str}:v{version_int}".encode('utf-8')

        # Recombine ciphertext and 16-byte auth tag for AESGCM verification
        combined = ciphertext + auth_tag
        plaintext = aesgcm.decrypt(nonce, combined, aad)
        return plaintext
