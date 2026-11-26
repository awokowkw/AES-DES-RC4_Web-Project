import datetime
import io
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import fields, signers, validation
from pyhanko_certvalidator import ValidationContext


def generate_user_cert_and_keys(username: str, passphrase: bytes):
    """Auto-generate RSA 2048-bit key pair + Self-Signed X.509 Cert jika user belum punya."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    enc_priv = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(passphrase),
    ).decode('utf-8')
    pub = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode('utf-8')

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, f"{username} - SYNK Verified Owner"),
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
    return pub, enc_priv, cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')


def embed_pdf_signature(pdf_bytes: bytes, priv_pem: str, cert_pem: str, passphrase: bytes) -> bytes:
    """Menyematkan tanda tangan digital ke dalam biner PDF menggunakan Private Key owner."""
    signer = signers.SimpleSigner.load_key_and_cert_from_pem(
        key_pem=priv_pem.encode('utf-8'),
        cert_pem=cert_pem.encode('utf-8'),
        key_passphrase=passphrase,
    )
    writer = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))
    fields.append_signature_field(writer, sig_field_spec=fields.SigFieldSpec('SynkOwnerSig'))
    meta = signers.PdfSignatureMetadata(field_name='SynkOwnerSig', reason='Signed by File Owner in SYNK')
    out_buf = io.BytesIO()
    signers.sign_pdf(writer, meta, signer=signer, output=out_buf)
    return out_buf.getvalue()


def verify_embedded_pdf_signature(pdf_bytes: bytes, trusted_cert_pem: str = None) -> dict:
    """Memeriksa keberadaan, identitas penanda tangan, dan integritas hash PDF."""
    reader = PdfFileReader(io.BytesIO(pdf_bytes))
    if not reader.embedded_signatures:
        return {'signed': False, 'valid': False, 'message': 'PDF ini tidak memiliki tanda tangan digital.'}

    sig = reader.embedded_signatures[0]
    trust_roots = [x509.load_pem_x509_certificate(trusted_cert_pem.encode('utf-8'))] if trusted_cert_pem else []
    vc = ValidationContext(trust_roots=trust_roots, allow_fetching=False) if trust_roots else None
    status = validation.validate_pdf_signature(sig, signer_validation_context=vc)

    return {
        'signed': True,
        'valid': status.intact,
        'signer': sig.signer_cert.subject.human_friendly,
        'message': 'Valid: Tanda tangan asli & isi PDF utuh.' if status.intact else 'Invalid: Isi PDF telah diubah setelah ditandatangani!',
    }