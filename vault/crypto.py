"""
Modul kripto murni (tanpa Django).

Satu data disimpan dalam 3 versi ciphertext: AES, RC4, DES.
Format tiap blob / file:
    VERSION(1) | salt(16) | nonce(0/4/8) | ciphertext | HMAC-SHA256(32)

Hierarki kunci:
    password --scrypt(kek_salt)--> KEK --AES-GCM--> data_key (acak 32 byte, disimpan terbungkus)
    per record: HKDF(data_key, salt, label) -> kunci cipher dan kunci MAC terpisah
"""
from Crypto.Cipher import AES, ARC4, DES
from Crypto.Hash import HMAC, SHA256
from Crypto.Protocol.KDF import HKDF, scrypt
from Crypto.Random import get_random_bytes

ALGOS = ("aes", "rc4", "des")
VERSION = b"\x01"
SALT_LEN = 16
TAG_LEN = 32
CHUNK = 1 << 20  # 1 MB
RC4_DROP = 3072
NONCE_LEN = {"aes": 8, "des": 4, "rc4": 0}
KEY_LEN = {"aes": 32, "des": 8, "rc4": 32}


class IntegrityError(Exception):
    """Password salah, data rusak, atau data dimodifikasi."""


# ------------------------------------------------------------ manajemen kunci
def _scrypt(password: str, salt: bytes) -> bytes:
    return scrypt(password, salt, 32, N=2 ** 15, r=8, p=1)


def new_user_key(password: str):
    """Buat data_key baru. Return (kek_salt, wrapped_key, data_key)."""
    kek_salt = get_random_bytes(16)
    data_key = get_random_bytes(32)
    gcm = AES.new(_scrypt(password, kek_salt), AES.MODE_GCM)
    ct, tag = gcm.encrypt_and_digest(data_key)
    return kek_salt, gcm.nonce + tag + ct, data_key  # nonce(16) | tag(16) | ct(32)


def unwrap_key(password: str, kek_salt: bytes, wrapped_key: bytes) -> bytes:
    """Buka data_key. Password salah -> IntegrityError."""
    kek_salt, wrapped_key = bytes(kek_salt), bytes(wrapped_key)
    try:
        return AES.new(_scrypt(password, kek_salt), AES.MODE_GCM, nonce=wrapped_key[:16]) \
            .decrypt_and_verify(wrapped_key[32:], wrapped_key[16:32])
    except (ValueError, KeyError):
        raise IntegrityError("password salah atau kunci rusak")


def rewrap_key(old_password: str, new_password: str, kek_salt: bytes, wrapped_key: bytes):
    """Ganti password: data_key tetap, hanya pembungkusnya yang diganti.
    Return (kek_salt_baru, wrapped_key_baru)."""
    data_key = unwrap_key(old_password, kek_salt, wrapped_key)
    new_salt = get_random_bytes(16)
    gcm = AES.new(_scrypt(new_password, new_salt), AES.MODE_GCM)
    ct, tag = gcm.encrypt_and_digest(data_key)
    return new_salt, gcm.nonce + tag + ct


# --------------------------------------------------------------------- cipher
def _cipher(algo: str, data_key: bytes, salt: bytes, nonce: bytes):
    key = HKDF(data_key, KEY_LEN[algo], salt, SHA256, context=algo.encode())
    if algo == "aes":
        return AES.new(key, AES.MODE_CTR, nonce=nonce)
    if algo == "des":
        return DES.new(key, DES.MODE_CTR, nonce=nonce)
    c = ARC4.new(key)
    c.encrypt(bytes(RC4_DROP))  # buang keystream awal yang bias
    return c


def _mac(algo: str, data_key: bytes, salt: bytes, first: bytes = b""):
    key = HKDF(data_key, 32, salt, SHA256, context=b"mac-" + algo.encode())
    return HMAC.new(key, first, SHA256)


def _hdr_len(algo: str) -> int:
    return 1 + SALT_LEN + NONCE_LEN[algo]


# ---------------------------------------------------------- data kecil (teks)
def _seal_one(algo: str, data_key: bytes, plaintext: bytes) -> bytes:
    salt = get_random_bytes(SALT_LEN)
    nonce = get_random_bytes(NONCE_LEN[algo])
    ct = _cipher(algo, data_key, salt, nonce).encrypt(plaintext)
    body = VERSION + salt + nonce + ct
    return body + _mac(algo, data_key, salt, body).digest()


def seal(data_key: bytes, plaintext: bytes) -> dict:
    """Enkripsi data dengan ketiga algoritma. Return {'aes': blob, 'rc4': blob, 'des': blob}."""
    return {a: _seal_one(a, data_key, plaintext) for a in ALGOS}


def open_one(data_key: bytes, algo: str, blob: bytes) -> bytes:
    blob = bytes(blob)
    hl = _hdr_len(algo)
    if len(blob) < hl + TAG_LEN or blob[:1] != VERSION:
        raise IntegrityError("format blob tidak valid")
    body, tag = blob[:-TAG_LEN], blob[-TAG_LEN:]
    salt, nonce = body[1:1 + SALT_LEN], body[1 + SALT_LEN:hl]
    try:
        _mac(algo, data_key, salt, body).verify(tag)  # verifikasi SEBELUM dekripsi
    except ValueError:
        raise IntegrityError("MAC tidak cocok")
    return _cipher(algo, data_key, salt, nonce).decrypt(body[hl:])


def open_all(data_key: bytes, blobs: dict) -> bytes:
    """Dekripsi ketiganya dan pastikan hasilnya identik."""
    results = {a: open_one(data_key, a, blobs[a]) for a in ALGOS}
    if len(set(results.values())) != 1:
        raise IntegrityError("hasil dekripsi AES/RC4/DES tidak sama")
    return results["aes"]


# ------------------------------------------------------------ file (streaming)
def encrypt_stream(data_key: bytes, chunks, outs: dict) -> int:
    """
    chunks: iterable potongan bytes (mis. uploaded_file.chunks(CHUNK))
    outs:   {'aes': file_obj, 'rc4': file_obj, 'des': file_obj} (mode 'wb')
    File sumber dibaca sekali dan ditulis ke tiga output. Return ukuran plaintext.
    """
    state = {}
    for a in ALGOS:
        salt = get_random_bytes(SALT_LEN)
        nonce = get_random_bytes(NONCE_LEN[a])
        header = VERSION + salt + nonce
        outs[a].write(header)
        state[a] = (_cipher(a, data_key, salt, nonce), _mac(a, data_key, salt, header))
    size = 0
    for chunk in chunks:
        size += len(chunk)
        for a in ALGOS:
            cipher, mac = state[a]
            ct = cipher.encrypt(chunk)
            mac.update(ct)
            outs[a].write(ct)
    for a in ALGOS:
        outs[a].write(state[a][1].digest())
    return size


def _read_header(f, algo: str):
    hl = _hdr_len(algo)
    h = f.read(hl)
    if len(h) != hl or h[:1] != VERSION:
        raise IntegrityError("header file tidak valid")
    return h, h[1:1 + SALT_LEN], h[1 + SALT_LEN:]


def verify_stream(data_key: bytes, algo: str, f) -> None:
    """Cek MAC seluruh file (f harus bisa di-seek)."""
    f.seek(0, 2)
    total = f.tell()
    f.seek(0)
    h, salt, _ = _read_header(f, algo)
    remaining = total - len(h) - TAG_LEN
    if remaining < 0:
        raise IntegrityError("file terpotong")
    mac = _mac(algo, data_key, salt, h)
    while remaining > 0:
        chunk = f.read(min(CHUNK, remaining))
        if not chunk:
            raise IntegrityError("file terpotong")
        remaining -= len(chunk)
        mac.update(chunk)
    try:
        mac.verify(f.read(TAG_LEN))
    except ValueError:
        raise IntegrityError("MAC file tidak cocok")


def decrypt_stream(data_key: bytes, algo: str, f):
    """Generator: verifikasi MAC dulu, baru mengalirkan hasil dekripsi."""
    verify_stream(data_key, algo, f)
    f.seek(0, 2)
    total = f.tell()
    f.seek(0)
    h, salt, nonce = _read_header(f, algo)
    cipher = _cipher(algo, data_key, salt, nonce)
    remaining = total - len(h) - TAG_LEN
    while remaining > 0:
        chunk = f.read(min(CHUNK, remaining))
        remaining -= len(chunk)
        yield cipher.decrypt(chunk)