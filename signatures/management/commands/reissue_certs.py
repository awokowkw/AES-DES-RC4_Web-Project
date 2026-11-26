"""Re-issue Root CA + semua sertifikat user dengan SKI/AKI (kunci tidak berubah).

Diperlukan agar viewer ketat (Adobe/Edge) bisa membangun jalur kepercayaan.
Private key user tidak berubah, jadi file terenkripsi lama tetap bisa dibuka.
"""
import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.oid import NameOID
from django.core.management.base import BaseCommand

from signatures.models import RootCA, UserSigningKey


def _name(cn, org="SYNK Secure Vault"):
    return x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, cn),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, org),
    ])


class Command(BaseCommand):
    help = "Terbitkan ulang Root CA & cert user dengan SKI/AKI (kunci tetap)."

    def handle(self, *args, **options):
        root = RootCA.objects.first()
        if root is None:
            self.stdout.write("Tidak ada RootCA. Jalankan ensure_root_ca() dulu.")
            return

        root_key = serialization.load_pem_private_key(
            root.private_key_pem.encode("utf-8"), password=None)
        now = datetime.datetime.now(datetime.timezone.utc)

        # 1. Terbitkan ulang root cert (kunci sama, tambah SKI/AKI)
        root_cert = (
            x509.CertificateBuilder()
            .subject_name(_name("SYNK Root CA"))
            .issuer_name(_name("SYNK Root CA"))
            .public_key(root_key.public_key())
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
                x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()),
                critical=False)
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()),
                critical=False)
            .sign(root_key, hashes.SHA256())
        )
        root.certificate_pem = root_cert.public_bytes(
            serialization.Encoding.PEM).decode("utf-8")
        root.save(update_fields=["certificate_pem"])
        self.stdout.write(self.style.SUCCESS("Root CA diterbitkan ulang (SKI/AKI)."))

        # 2. Terbitkan ulang tiap cert user (public key sama, tambah SKI/AKI)
        count = 0
        for k in UserSigningKey.objects.all():
            old = x509.load_pem_x509_certificate(k.certificate_pem.encode("utf-8"))
            pub = serialization.load_pem_public_key(k.public_key_pem.encode("utf-8"))
            cert = (
                x509.CertificateBuilder()
                .subject_name(old.subject)
                .issuer_name(root_cert.subject)
                .public_key(pub)
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
                    x509.SubjectKeyIdentifier.from_public_key(pub), critical=False)
                .add_extension(
                    x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()),
                    critical=False)
                .sign(root_key, hashes.SHA256())
            )
            k.certificate_pem = cert.public_bytes(
                serialization.Encoding.PEM).decode("utf-8")
            k.save(update_fields=["certificate_pem"])
            count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Selesai. {count} sertifikat user diterbitkan ulang."))