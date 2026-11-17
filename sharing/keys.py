import base64, json
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import HKDF
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
from Crypto.Signature import pss


# ---------- RSA ----------
def generate_rsa_keypair(bits=2048):
    key = RSA.generate(bits)
    return key.publickey().export_key().decode(), key.export_key()   # (PEM publik, PEM privat)


def rsa_encrypt(public_pem, data: bytes) -> bytes:
    return PKCS1_OAEP.new(RSA.import_key(public_pem), hashAlgo=SHA256).encrypt(data)


def rsa_decrypt(private_pem, blob: bytes) -> bytes:
    return PKCS1_OAEP.new(RSA.import_key(private_pem), hashAlgo=SHA256).decrypt(blob)


def sign(private_pem, data: bytes) -> bytes:
    return pss.new(RSA.import_key(private_pem)).sign(SHA256.new(data))


def verify(public_pem, data: bytes, sig: bytes) -> bool:
    try:
        pss.new(RSA.import_key(public_pem)).verify(SHA256.new(data), sig)
        return True
    except (ValueError, TypeError):
        return False


# ---------- Pembungkus kunci (AES-GCM, kuncinya turunan data_key user) ----------
def _wrap_key(data_key: bytes) -> bytes:
    return HKDF(data_key, 32, b"sharing-v1", SHA256, context=b"wrap")


def wrap(data_key: bytes, plaintext: bytes, aad: bytes) -> bytes:
    nonce = get_random_bytes(12)
    c = AES.new(_wrap_key(data_key), AES.MODE_GCM, nonce=nonce)
    c.update(aad)
    ct, tag = c.encrypt_and_digest(plaintext)
    return nonce + tag + ct                       # 12 | 16 | n


def unwrap(data_key: bytes, blob: bytes, aad: bytes) -> bytes:
    nonce, tag, ct = blob[:12], blob[12:28], blob[28:]
    c = AES.new(_wrap_key(data_key), AES.MODE_GCM, nonce=nonce)
    c.update(aad)
    return c.decrypt_and_verify(ct, tag)          # ValueError jika kunci salah / data diubah


# ---------- Kunci simetris untuk berbagi ----------
def new_share_key() -> bytes:
    return get_random_bytes(32)                   # dipakai langsung sebagai data_key di vault.crypto


# ---------- Kode kunci (dikirim lewat WA/email) ----------
def build_token(owner_private_pem, requester_public_pem, req_id, owner_username, k: bytes) -> str:
    ek = rsa_encrypt(requester_public_pem, k)
    sig = sign(owner_private_pem, ek + str(req_id).encode())
    payload = {"v": 1, "req": req_id, "from": owner_username,
               "ek": base64.b64encode(ek).decode(), "sig": base64.b64encode(sig).decode()}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def open_token(token: str, requester_private_pem, owner_public_pem, expected_req_id) -> bytes:
    p = json.loads(base64.urlsafe_b64decode(token.strip().encode()))
    ek, sig = base64.b64decode(p["ek"]), base64.b64decode(p["sig"])
    if p["req"] != expected_req_id:
        raise ValueError("Kode ini untuk permintaan lain.")
    if not verify(owner_public_pem, ek + str(p["req"]).encode(), sig):
        raise ValueError("Tanda tangan tidak valid (kode dipalsukan/rusak).")
    return rsa_decrypt(requester_private_pem, ek)