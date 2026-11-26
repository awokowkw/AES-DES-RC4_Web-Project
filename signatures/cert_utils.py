import datetime
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from .models import UserSigningKey


def generate_keypair_and_cert(username: str, passphrase: bytes):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    enc_priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(passphrase),
    ).decode('utf-8')

    pub_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode('utf-8')

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, f"{username} (SYNK Verified Owner)"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SYNK Secure Vault"),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
        .sign(private_key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')

    return pub_pem, enc_priv_pem, cert_pem


def ensure_user_signing_key(user, passphrase: bytes) -> UserSigningKey:
    """Memastikan user memiliki key pair & sertifikat; buat otomatis jika belum ada."""
    obj = getattr(user, 'signing_key', None)
    if obj is None:
        pub, enc_priv, cert = generate_keypair_and_cert(user.username, passphrase)
        obj = UserSigningKey.objects.create(
            user=user,
            public_key_pem=pub,
            encrypted_private_key_pem=enc_priv,
            certificate_pem=cert,
        )
    return obj