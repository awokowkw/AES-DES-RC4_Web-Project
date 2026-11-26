import datetime
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from .models import RootCA, UserSigningKey


def _name(cn: str, org: str = "SYNK Secure Vault") -> x509.Name:
    return x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, cn),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, org),
    ])


def generate_root_ca():
    """Buat pasangan kunci + sertifikat Root CA (dipakai sekali per sistem).
    Return (encrypted_private_key_pem, certificate_pem)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    enc_priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode('utf-8')

    subject = issuer = _name("SYNK Root CA")
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=False,
                key_encipherment=False, data_encipherment=False,
                key_agreement=False, key_cert_sign=True, crl_sign=True,
                encipher_only=False, decipher_only=False),
            critical=True)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
            critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(private_key.public_key()),
            critical=False)
        .sign(private_key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')
    return enc_priv_pem, cert_pem


def ensure_root_ca() -> RootCA:
    """Ambil Root CA sistem; buat otomatis jika belum ada (singleton)."""
    obj = RootCA.objects.first()
    if obj is None:
        enc_priv, cert = generate_root_ca()
        obj = RootCA.objects.create(private_key_pem=enc_priv, certificate_pem=cert)
    return obj


def generate_keypair_and_cert(username: str, passphrase: bytes, root_ca: RootCA):
    """Key pair milik user + sertifikat yang DITANDATANGANI oleh Root CA
    (bukan self-signed lagi). Return (pub_pem, enc_priv_pem, cert_pem)."""
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

    ca_key = serialization.load_pem_private_key(
        root_ca.private_key_pem.encode('utf-8'), password=None)
    ca_cert = x509.load_pem_x509_certificate(root_ca.certificate_pem.encode('utf-8'))

    subject = _name(f"{username} (SYNK Verified Owner)")
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=True,
                key_encipherment=False, data_encipherment=False,
                key_agreement=False, key_cert_sign=False, crl_sign=False,
                encipher_only=False, decipher_only=False),
            critical=True)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
            critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')

    return pub_pem, enc_priv_pem, cert_pem


def ensure_user_signing_key(user, passphrase: bytes) -> UserSigningKey:
    """Memastikan user memiliki key pair & sertifikat; buat otomatis jika belum ada."""
    obj = getattr(user, 'signing_key', None)
    if obj is None:
        root_ca = ensure_root_ca()
        pub, enc_priv, cert = generate_keypair_and_cert(user.username, passphrase, root_ca)
        obj = UserSigningKey.objects.create(
            user=user,
            public_key_pem=pub,
            encrypted_private_key_pem=enc_priv,
            certificate_pem=cert,
        )
    return obj