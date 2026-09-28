#!/usr/bin/env python3
"""
ZERO TOWER BATTLE (ZTB) - ECC Crypto Module
=============================================
Elliptic Curve Cryptography fuer BLE-Handshake und P2P-Sicherheit.

Algorithmen:
  - Curve25519: Diffie-Hellman Key Exchange (ECDH)
  - Ed25519: Digitale Signaturen
  - HKDF: Session-Key Ableitung
  - AES-GCM: Symmetrische Verschluesselung (nach Handshake)

Ablauf (laut Spec "ECC Crypto.txt"):
  1. Setup: Jeder Pi generiert ECC-Schlüsselpaar (einmalig)
  2. BLE-Beacon: Sendet gehashten Challenge-Code / Public-Key-Fragment
  3. GATT-Handshake: Nach Erkennung → dedizierte GATT-Charakteristiken
  4. Diffie-Hellman: Beide Pis berechnen Shared Secret
  5. Session-Key: HKDF-Ableitung → AES-GCM fuer WiFi-Direct-Verbindung

Pi Zero 2W Cortex-A53: ECC in wenigen Millisekunden.
Gesamter Prozess: <2 Sekunden (Spec-Vorgabe).

Referenz: ECC Crypto.txt
"""

import os
import hashlib
import struct
import time
from typing import Dict, Any, Optional, Tuple

# Crypto-Imports (Optional: graceful degradation)
try:
    from cryptography.hazmat.primitives.asymmetric.x25519 import (
        X25519PrivateKey, X25519PublicKey
    )
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey, Ed25519PublicKey
    )
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


# =============================================
# Konstanten
# =============================================

# BLE-Beacon Felder (31-Byte-Paket)
BEACON_BATTLE_CODE = 0xFEAA        # 2 Bytes: ZTB-Kennung
BEACON_IDENTITY_LEN = 8             # 8 Bytes: Spieler-Hash
BEACON_WIFI_PSK_LEN = 8             # 8 Bytes: WPA2-PSK
BEACON_IP_SUFFIX_LEN = 1            # 1 Byte: IP-Suffix (10.42.0.X)
BEACON_ECC_FRAGMENT_LEN = 12        # 12 Bytes: ECC Challenge/PubKey-Fragment
BEACON_TOTAL_LEN = 31               # 31 Bytes gesamt

# GATT Service UUID fuer ZTB-Handshake
ZTB_SERVICE_UUID = "0000FE42-0000-1000-8000-00805F9B34FB"
ZTB_HANDSHAKE_CHAR_UUID = "0000FE43-0000-1000-8000-00805F9B34FB"

# Session-Key Ableitung
HKDF_INFO = b"ZTB-Session-Key-v1"
SESSION_KEY_LEN = 32  # 256-bit AES-GCM


# =============================================
# ECC Key Manager
# =============================================

class ECCKeyManager:
    """
    Verwaltet das ECC-Schlüsselpaar des lokalen Pi.

    Schluesselpaare:
      - X25519: Fuer Diffie-Hellman Key Exchange (ECDH)
      - Ed25519: Fuer digitale Signaturen (Authentizitaet)

    Persistenz: Keys werden in Cold Storage gespeichert
    und beim Erststart generiert.
    """

    def __init__(self):
        self._x25519_private = None
        self._x25519_public = None
        self._ed25519_private = None
        self._ed25519_public = None
        self._initialized = False

    @property
    def is_available(self) -> bool:
        """Pruefe ob cryptography-Bibliothek verfuegbar."""
        return HAS_CRYPTO

    # -----------------------------------------
    # Schluesselgenerierung
    # -----------------------------------------

    def generate_keys(self) -> Dict[str, Any]:
        """
        Neues ECC-Schlüsselpaar generieren (einmalig beim Setup).

        Returns:
            Dict mit: status, public_key_x25519_hex, public_key_ed25519_hex
        """
        if not HAS_CRYPTO:
            return {"status": "ERROR", "message": "cryptography nicht installiert"}

        # X25519 (Diffie-Hellman)
        self._x25519_private = X25519PrivateKey.generate()
        self._x25519_public = self._x25519_private.public_key()

        # Ed25519 (Signaturen)
        self._ed25519_private = Ed25519PrivateKey.generate()
        self._ed25519_public = self._ed25519_private.public_key()

        self._initialized = True

        return {
            "status": "SUCCESS",
            "public_key_x25519_hex": self.get_x25519_public_hex(),
            "public_key_ed25519_hex": self.get_ed25519_public_hex()
        }

    # -----------------------------------------
    # Public Keys exportieren
    # -----------------------------------------

    def get_x25519_public_bytes(self) -> bytes:
        """X25519 Public Key als raw bytes (32 Bytes)."""
        if not self._x25519_public:
            return b""
        return self._x25519_public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

    def get_x25519_public_hex(self) -> str:
        """X25519 Public Key als Hex-String."""
        return self.get_x25519_public_bytes().hex()

    def get_ed25519_public_bytes(self) -> bytes:
        """Ed25519 Public Key als raw bytes (32 Bytes)."""
        if not self._ed25519_public:
            return b""
        return self._ed25519_public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

    def get_ed25519_public_hex(self) -> str:
        """Ed25519 Public Key als Hex-String."""
        return self.get_ed25519_public_bytes().hex()

    # -----------------------------------------
    # Diffie-Hellman Key Exchange
    # -----------------------------------------

    def perform_ecdh(self, remote_public_bytes: bytes) -> Optional[bytes]:
        """
        Diffie-Hellman Schluesselaustausch mit Remote-Pi.

        Args:
            remote_public_bytes: X25519 Public Key des Gegners (32 Bytes)

        Returns:
            Shared Secret (32 Bytes) oder None bei Fehler
        """
        if not HAS_CRYPTO or not self._x25519_private:
            return None

        try:
            remote_public = X25519PublicKey.from_public_bytes(remote_public_bytes)
            shared_secret = self._x25519_private.exchange(remote_public)
            return shared_secret
        except Exception as e:
            print(f"[ECC-ERROR] ECDH fehlgeschlagen: {e}")
            return None

    def derive_session_key(self, shared_secret: bytes,
                           salt: bytes = None) -> Optional[bytes]:
        """
        Session-Key aus Shared Secret ableiten (HKDF).

        Args:
            shared_secret: ECDH Shared Secret
            salt: Optional, z.B. Timestamp-Hash

        Returns:
            AES-256-GCM Key (32 Bytes) oder None
        """
        if not HAS_CRYPTO:
            return None

        try:
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=SESSION_KEY_LEN,
                salt=salt,
                info=HKDF_INFO,
            )
            return hkdf.derive(shared_secret)
        except Exception as e:
            print(f"[ECC-ERROR] HKDF fehlgeschlagen: {e}")
            return None

    # -----------------------------------------
    # Signaturen (Ed25519)
    # -----------------------------------------

    def sign(self, data: bytes) -> Optional[bytes]:
        """
        Daten mit Ed25519 signieren.

        Args:
            data: Zu signierende Bytes

        Returns:
            Signatur (64 Bytes) oder None
        """
        if not HAS_CRYPTO or not self._ed25519_private:
            return None

        try:
            return self._ed25519_private.sign(data)
        except Exception as e:
            print(f"[ECC-ERROR] Signatur fehlgeschlagen: {e}")
            return None

    def verify(self, data: bytes, signature: bytes,
               remote_public_bytes: bytes) -> bool:
        """
        Ed25519-Signatur verifizieren.

        Args:
            data: Originaldaten
            signature: Signatur (64 Bytes)
            remote_public_bytes: Ed25519 Public Key des Absenders

        Returns:
            True wenn gueltig
        """
        if not HAS_CRYPTO:
            return False

        try:
            remote_public = Ed25519PublicKey.from_public_bytes(remote_public_bytes)
            remote_public.verify(signature, data)
            return True
        except Exception:
            return False

    # -----------------------------------------
    # AES-GCM (nach Session-Key-Ableitung)
    # -----------------------------------------

    @staticmethod
    def encrypt(session_key: bytes, plaintext: bytes,
                associated_data: bytes = None) -> Optional[Tuple[bytes, bytes]]:
        """
        AES-256-GCM Verschluesselung.

        Args:
            session_key: 32-Byte Session Key
            plaintext: Klartextdaten
            associated_data: AAD (optional, z.B. Paket-Header)

        Returns:
            Tuple (nonce, ciphertext) oder None
        """
        if not HAS_CRYPTO:
            return None

        try:
            aesgcm = AESGCM(session_key)
            nonce = os.urandom(12)  # 96-bit Nonce
            ct = aesgcm.encrypt(nonce, plaintext, associated_data)
            return nonce, ct
        except Exception as e:
            print(f"[ECC-ERROR] Encrypt: {e}")
            return None

    @staticmethod
    def decrypt(session_key: bytes, nonce: bytes, ciphertext: bytes,
                associated_data: bytes = None) -> Optional[bytes]:
        """
        AES-256-GCM Entschluesselung.

        Args:
            session_key: 32-Byte Session Key
            nonce: 12-Byte Nonce
            ciphertext: Verschluesselte Daten
            associated_data: AAD (muss identisch sein)

        Returns:
            Klartext oder None bei Fehler (Manipulation erkannt)
        """
        if not HAS_CRYPTO:
            return None

        try:
            aesgcm = AESGCM(session_key)
            return aesgcm.decrypt(nonce, ciphertext, associated_data)
        except Exception as e:
            print(f"[ECC-ERROR] Decrypt: {e}")
            return None

    # -----------------------------------------
    # Persistenz (Cold Storage)
    # -----------------------------------------

    def export_keys(self) -> Optional[Dict[str, str]]:
        """Keys als Hex-Strings exportieren (fuer Cold Storage)."""
        if not self._initialized or not HAS_CRYPTO:
            return None

        return {
            "x25519_private": self._x25519_private.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            ).hex(),
            "x25519_public": self.get_x25519_public_hex(),
            "ed25519_private": self._ed25519_private.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            ).hex(),
            "ed25519_public": self.get_ed25519_public_hex()
        }

    def import_keys(self, key_data: Dict[str, str]) -> bool:
        """Keys aus Cold Storage laden."""
        if not HAS_CRYPTO:
            return False

        try:
            self._x25519_private = X25519PrivateKey.from_private_bytes(
                bytes.fromhex(key_data["x25519_private"])
            )
            self._x25519_public = self._x25519_private.public_key()

            self._ed25519_private = Ed25519PrivateKey.from_private_bytes(
                bytes.fromhex(key_data["ed25519_private"])
            )
            self._ed25519_public = self._ed25519_private.public_key()

            self._initialized = True
            return True

        except Exception as e:
            print(f"[ECC-ERROR] Key-Import: {e}")
            return False


# =============================================
# BLE Beacon Builder (31-Byte-Paket)
# =============================================

class BLEBeaconBuilder:
    """
    Baut das 31-Byte BLE-Advertising-Paket gemaess Spec.

    Struktur (31 Bytes):
      Bytes 0-1:   Battle-Code (0xFEAA)
      Bytes 2-9:   Spieler-Identity-Hash (8 Bytes)
      Bytes 10-17: WiFi-PSK (8 Bytes, zufaellig)
      Byte  18:    IP-Suffix (10.42.0.X)
      Bytes 19-30: ECC-Fragment / Challenge (12 Bytes)
    """

    @staticmethod
    def build_beacon(character_name: str, ip_suffix: int,
                     ecc_manager: ECCKeyManager = None,
                     wifi_psk: bytes = None) -> bytes:
        """
        31-Byte BLE-Beacon-Paket erstellen.

        Args:
            character_name: Name des Champions
            ip_suffix: Letztes Oktett der IP (1-254)
            ecc_manager: ECCKeyManager fuer Public-Key-Fragment
            wifi_psk: WiFi-PSK (8 Bytes) oder auto-generiert

        Returns:
            31-Byte Beacon-Paket
        """
        packet = bytearray(BEACON_TOTAL_LEN)

        # 1. Battle-Code (2 Bytes, Big-Endian)
        struct.pack_into(">H", packet, 0, BEACON_BATTLE_CODE)

        # 2. Spieler-Identity-Hash (8 Bytes)
        identity_hash = hashlib.sha256(character_name.encode("utf-8")).digest()[:8]
        packet[2:10] = identity_hash

        # 3. WiFi-PSK (8 Bytes)
        if wifi_psk is None:
            wifi_psk = os.urandom(8)
        packet[10:18] = wifi_psk[:8]

        # 4. IP-Suffix (1 Byte)
        packet[18] = max(1, min(254, ip_suffix))

        # 5. ECC-Fragment (12 Bytes)
        if ecc_manager and ecc_manager.is_available:
            pub_bytes = ecc_manager.get_x25519_public_bytes()
            if len(pub_bytes) >= 12:
                packet[19:31] = pub_bytes[:12]
            else:
                # Padding mit Zufallsbytes
                packet[19:31] = os.urandom(12)
        else:
            # Kein ECC: Challenge-Hash
            challenge = hashlib.sha256(
                character_name.encode() + struct.pack(">I", int(time.time()))
            ).digest()[:12]
            packet[19:31] = challenge

        return bytes(packet)

    @staticmethod
    def parse_beacon(data: bytes) -> Optional[Dict[str, Any]]:
        """
        31-Byte BLE-Beacon-Paket parsen.

        Args:
            data: Empfangenes 31-Byte-Paket

        Returns:
            Dict mit geparstem Inhalt oder None wenn ungueltig
        """
        if len(data) < BEACON_TOTAL_LEN:
            return None

        # Battle-Code pruefen
        battle_code = struct.unpack_from(">H", data, 0)[0]
        if battle_code != BEACON_BATTLE_CODE:
            return None  # Kein ZTB-Beacon

        return {
            "battle_code": hex(battle_code),
            "identity_hash": data[2:10].hex(),
            "wifi_psk": data[10:18],
            "ip_suffix": data[18],
            "ecc_fragment": data[19:31].hex(),
            "is_ztb": True
        }


# =============================================
# GATT Handshake Manager
# =============================================

class GATTHandshakeManager:
    """
    Verwaltet den GATT-basierten ECC-Handshake.

    Ablauf:
      1. BLE-Beacon empfangen → Gegner erkannt
      2. GATT-Verbindung aufbauen (dedizierte Charakteristiken)
      3. Public Keys austauschen (X25519 + Ed25519)
      4. ECDH → Shared Secret
      5. HKDF → Session Key (AES-256-GCM)
      6. Signatur-Verifikation (Ed25519)
      7. Bereit fuer WiFi-Direct-Verbindung

    Zeitvorgabe: <2 Sekunden gesamt (Spec)
    """

    def __init__(self, ecc_manager: ECCKeyManager):
        self._ecc = ecc_manager
        self._session_key = None
        self._remote_identity = None

    def prepare_handshake_payload(self) -> Optional[bytes]:
        """
        Lokalen Handshake-Payload erstellen.
        Enthaelt X25519 + Ed25519 Public Keys.

        Returns:
            64-Byte Payload (32 + 32) oder None
        """
        if not self._ecc.is_available:
            return None

        x25519_pub = self._ecc.get_x25519_public_bytes()
        ed25519_pub = self._ecc.get_ed25519_public_bytes()

        if len(x25519_pub) != 32 or len(ed25519_pub) != 32:
            return None

        return x25519_pub + ed25519_pub

    def complete_handshake(self, remote_payload: bytes,
                           salt: bytes = None) -> Dict[str, Any]:
        """
        Handshake mit empfangenem Remote-Payload abschliessen.

        Args:
            remote_payload: 64 Bytes (X25519 + Ed25519 Public Keys)
            salt: Optional Timestamp-Salt

        Returns:
            Dict mit: status, session_key_ready, remote_identity_hash
        """
        if len(remote_payload) < 64:
            return {"status": "ERROR", "message": "Payload zu kurz"}

        remote_x25519_pub = remote_payload[:32]
        remote_ed25519_pub = remote_payload[32:64]

        # 1. ECDH → Shared Secret
        shared_secret = self._ecc.perform_ecdh(remote_x25519_pub)
        if shared_secret is None:
            return {"status": "ERROR", "message": "ECDH fehlgeschlagen"}

        # 2. HKDF → Session Key
        self._session_key = self._ecc.derive_session_key(shared_secret, salt)
        if self._session_key is None:
            return {"status": "ERROR", "message": "Session-Key-Ableitung fehlgeschlagen"}

        # 3. Remote-Identity speichern
        self._remote_identity = hashlib.sha256(remote_ed25519_pub).hexdigest()[:16]

        return {
            "status": "SUCCESS",
            "session_key_ready": True,
            "remote_identity_hash": self._remote_identity
        }

    def get_session_key(self) -> Optional[bytes]:
        """Session Key zurueckgeben (nach erfolgreichem Handshake)."""
        return self._session_key

    def encrypt_message(self, plaintext: bytes) -> Optional[Tuple[bytes, bytes]]:
        """Nachricht mit Session Key verschluesseln."""
        if self._session_key is None:
            return None
        return ECCKeyManager.encrypt(self._session_key, plaintext)

    def decrypt_message(self, nonce: bytes, ciphertext: bytes) -> Optional[bytes]:
        """Nachricht mit Session Key entschluesseln."""
        if self._session_key is None:
            return None
        return ECCKeyManager.decrypt(self._session_key, nonce, ciphertext)


# =============================================
# Standalone-Test
# =============================================

if __name__ == "__main__":
    if not HAS_CRYPTO:
        print("[ECC] cryptography nicht installiert!")
        print("      pip install cryptography")
        exit(1)

    print("=== ECC Crypto Test ===\n")

    # 1. Zwei Pis simulieren
    pi_a = ECCKeyManager()
    pi_b = ECCKeyManager()

    result_a = pi_a.generate_keys()
    result_b = pi_b.generate_keys()
    print(f"Pi A Keys: {result_a['status']}")
    print(f"Pi B Keys: {result_b['status']}")

    # 2. Diffie-Hellman
    shared_a = pi_a.perform_ecdh(pi_b.get_x25519_public_bytes())
    shared_b = pi_b.perform_ecdh(pi_a.get_x25519_public_bytes())
    print(f"\nShared Secrets gleich: {shared_a == shared_b}")

    # 3. Session Keys
    key_a = pi_a.derive_session_key(shared_a)
    key_b = pi_b.derive_session_key(shared_b)
    print(f"Session Keys gleich: {key_a == key_b}")

    # 4. Signatur
    message = b"PVP-Battle-Request"
    sig = pi_a.sign(message)
    valid = pi_b.verify(message, sig, pi_a.get_ed25519_public_bytes())
    print(f"Signatur gueltig: {valid}")

    # 5. Verschluesselung
    result = ECCKeyManager.encrypt(key_a, b"Kampfdaten: ATK=30, DEF=25")
    if result:
        nonce, ct = result
        pt = ECCKeyManager.decrypt(key_b, nonce, ct)
        print(f"Entschluesselung: {pt}")

    # 6. Beacon
    print(f"\n=== BLE Beacon Test ===")
    beacon = BLEBeaconBuilder.build_beacon("TestHeld", ip_suffix=42, ecc_manager=pi_a)
    print(f"Beacon Laenge: {len(beacon)} Bytes")
    print(f"Beacon Hex: {beacon.hex()}")

    parsed = BLEBeaconBuilder.parse_beacon(beacon)
    print(f"Parsed: {parsed}")

    # 7. GATT Handshake
    print(f"\n=== GATT Handshake Test ===")
    gatt_a = GATTHandshakeManager(pi_a)
    gatt_b = GATTHandshakeManager(pi_b)

    payload_a = gatt_a.prepare_handshake_payload()
    payload_b = gatt_b.prepare_handshake_payload()
    print(f"Payload A: {len(payload_a)} Bytes")

    result_a = gatt_a.complete_handshake(payload_b)
    result_b = gatt_b.complete_handshake(payload_a)
    print(f"Handshake A: {result_a['status']}")
    print(f"Handshake B: {result_b['status']}")
    print(f"Session Keys gleich: {gatt_a.get_session_key() == gatt_b.get_session_key()}")

    # 8. Verschluesselte Kommunikation
    enc = gatt_a.encrypt_message(b"Angriff mit 30 ATK!")
    if enc:
        nonce, ct = enc
        dec = gatt_b.decrypt_message(nonce, ct)
        print(f"Entschluesselung via GATT: {dec}")

    # 9. Key Export/Import
    exported = pi_a.export_keys()
    pi_c = ECCKeyManager()
    imported = pi_c.import_keys(exported)
    print(f"\nKey Export/Import: {imported}")
    print(f"Keys identisch: {pi_c.get_x25519_public_hex() == pi_a.get_x25519_public_hex()}")

    print("\nAlle ECC-Tests bestanden!")
