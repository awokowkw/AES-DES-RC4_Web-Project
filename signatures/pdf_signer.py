import io
from asn1crypto import keys as asn1_keys, pem, x509 as asn1_x509
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from django.core.files.uploadedfile import SimpleUploadedFile
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import fields, signers, validation
from pyhanko_certvalidator import ValidationContext
from .cert_utils import ensure_user_signing_key


def _build_pyhanko_signer(priv_pem: str, cert_pem: str, passphrase: bytes) -> signers.SimpleSigner:
    """Memuat Private Key & Certificate PEM dari memori ke objek SimpleSigner pyhanko."""
    # 1. Dekripsi private key menggunakan cryptography lalu ubah ke format PKCS#8 DER
    priv_obj = serialization.load_pem_private_key(
        priv_pem.encode('utf-8'),
        password=passphrase,
    )
    priv_der = priv_obj.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    signing_key = asn1_keys.PrivateKeyInfo.load(priv_der)

    # 2. Konversi sertifikat PEM ke objek asn1crypto Certificate
    _, _, cert_der = pem.unarmor(cert_pem.encode('utf-8'))
    signing_cert = asn1_x509.Certificate.load(cert_der)

    return signers.SimpleSigner(
        signing_cert=signing_cert,
        signing_key=signing_key,
        cert_registry=None,
    )


def embed_signature_to_pdf_bytes(pdf_bytes: bytes, priv_pem: str, cert_pem: str, passphrase: bytes) -> bytes:
    signer = _build_pyhanko_signer(priv_pem, cert_pem, passphrase)
    writer = IncrementalPdfFileWriter(io.BytesIO(pdf_bytes), strict=False)
    fields.append_signature_field(writer, sig_field_spec=fields.SigFieldSpec('SynkOwnerSignature'))

    meta = signers.PdfSignatureMetadata(
        field_name='SynkOwnerSignature',
        reason='Digitally signed by file owner via SYNK',
    )
    out_buf = io.BytesIO()
    signers.sign_pdf(writer, meta, signer=signer, output=out_buf)
    return out_buf.getvalue()


def sign_uploaded_pdf_if_needed(user, passphrase: bytes, uploaded_file):
    """Helper 1-baris untuk dipanggil di vault/views.py saat user mengunggah file."""
    if not uploaded_file.name.lower().endswith('.pdf'):
        return uploaded_file

    raw_pdf = uploaded_file.read()
    try:
        reader = PdfFileReader(io.BytesIO(raw_pdf), strict=False)
        if reader.embedded_signatures:
            uploaded_file.seek(0)
            return uploaded_file
    except Exception:
        # Jika gagal membaca struktur PDF untuk cek signature, lanjutkan ke alur signing
        # atau biarkan error ditangani di bawah.
        pass

    key_obj = ensure_user_signing_key(user, passphrase)
    signed_pdf = embed_signature_to_pdf_bytes(
        raw_pdf,
        key_obj.encrypted_private_key_pem,
        key_obj.certificate_pem,
        passphrase,
    )
    return SimpleUploadedFile(
        uploaded_file.name,
        signed_pdf,
        content_type='application/pdf',
    )


def verify_pdf_signature(pdf_bytes: bytes, trusted_certs_pem: list[str]) -> dict:
    try:
        reader = PdfFileReader(io.BytesIO(pdf_bytes), strict=False)
    except Exception:
        return {
            'signed': False,
            'valid': False,
            'signer': None,
            'message': 'File tidak terbaca sebagai PDF valid.',
        }

    if not reader.embedded_signatures:
        return {
            'signed': False,
            'valid': False,
            'signer': None,
            'message': 'File PDF ini tidak memiliki tanda tangan digital tertanam.',
        }

    try:
        sig = reader.embedded_signatures[0]
        trust_roots = []
        for c in trusted_certs_pem:
            if c:
                _, _, cert_der = pem.unarmor(c.encode('utf-8'))
                trust_roots.append(asn1_x509.Certificate.load(cert_der))

        vc = ValidationContext(
            trust_roots=trust_roots,
            allow_fetching=False,
            revocation_mode='soft-fail',
        ) if trust_roots else None

        status = validation.validate_pdf_signature(sig, signer_validation_context=vc)
        is_valid = bool(status.intact and status.valid)

        return {
            'signed': True,
            'valid': is_valid,
            'signer': sig.signer_cert.subject.human_friendly,
            'message': (
                'Valid: Tanda tangan digital asli & isi dokumen PDF masih utuh.'
                if is_valid
                else 'Invalid / Tampered: Tanda tangan tidak terpercaya atau isi PDF telah diubah!'
            ),
        }
    except Exception as exc:
        return {
            'signed': True,
            'valid': False,
            'signer': None,
            'message': f'Gagal memverifikasi tanda tangan: {exc}',
        }