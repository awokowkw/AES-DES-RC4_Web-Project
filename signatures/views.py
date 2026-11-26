from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from accounts import keystore
from accounts.decorators import vault_unlocked
from vault.models import StoredFile
from vault.services import open_stored_file, overwrite_encrypted_bytes, stored_filename
from .cert_utils import ensure_root_ca, ensure_user_signing_key
from .models import RootCA, UserSigningKey
from .pdf_signer import embed_signature_to_pdf_bytes, verify_pdf_signature


def _get_passphrase(request) -> bytes:
    """Ambil data_key asli (sama yang dipakai saat upload)."""
    dk = getattr(request, 'data_key', None)
    if isinstance(dk, bytes):
        return dk
    dk = keystore.get_key(request.session.session_key)
    if isinstance(dk, bytes):
        return dk
    return f"synk-key-{request.user.id}".encode('utf-8')


def _get_trust_certs() -> list[str]:
    """Ambil Root CA sebagai trust root beserta sertifikat user untuk kompatibilitas."""
    trust_certs = []
    root = RootCA.objects.first()
    if root:
        trust_certs.append(root.certificate_pem)
    trust_certs += list(UserSigningKey.objects.values_list('certificate_pem', flat=True))
    return trust_certs


@login_required
@require_GET
def key_status_endpoint(request):
    """Mengecek apakah user sudah memiliki RSA Signing Key Pair & Sertifikat."""
    key_obj = getattr(request.user, 'signing_key', None)
    if key_obj is None:
        return JsonResponse({'has_key': False})
    return JsonResponse({
        'has_key': True,
        'created_at': key_obj.created_at.strftime('%d %b %Y, %H:%M'),
        'public_key_preview': key_obj.public_key_pem.splitlines()[1][:36] + '...',
    })


@vault_unlocked
@require_POST
def generate_key_endpoint(request):
    """Membuatkan RSA Key Pair & X.509 Certificate jika user belum punya."""
    key_obj = ensure_user_signing_key(request.user, request.data_key)
    return JsonResponse({
        'has_key': True,
        'created_at': key_obj.created_at.strftime('%d %b %Y, %H:%M'),
        'public_key_preview': key_obj.public_key_pem.splitlines()[1][:36] + '...',
        'message': 'RSA Key Pair & X.509 Certificate berhasil dibuat!',
    })


@vault_unlocked
@require_POST
def regenerate_key_endpoint(request):
    """Hapus key lama (self-signed) & buat ulang cert yang ditandatangani Root CA."""
    UserSigningKey.objects.filter(user=request.user).delete()
    key_obj = ensure_user_signing_key(request.user, request.data_key)
    return JsonResponse({
        'has_key': True,
        'created_at': key_obj.created_at.strftime('%d %b %Y, %H:%M'),
        'public_key_preview': key_obj.public_key_pem.splitlines()[1][:36] + '...',
        'message': 'Key pair & sertifikat baru (ditandatangani Root CA SYNK) berhasil dibuat!',
    })


@login_required
@require_POST
def verify_pdf_endpoint(request):
    """Memverifikasi tanda tangan digital tertanam pada file PDF."""
    pdf_file = request.FILES.get('pdf_file')
    if not pdf_file or not pdf_file.name.lower().endswith('.pdf'):
        return JsonResponse({'signed': False, 'valid': False, 'message': 'Harap pilih file berformat .pdf.'}, status=400)

    pdf_bytes = pdf_file.read()
    result = verify_pdf_signature(pdf_bytes, _get_trust_certs())
    return JsonResponse(result)


@vault_unlocked
@require_GET
def download_root_ca(request):
    """Unduh Root CA SYNK (.crt) untuk di-install ke Trusted Root (Edge/Adobe)."""
    root = ensure_root_ca()
    resp = HttpResponse(root.certificate_pem, content_type='application/x-x509-ca-cert')
    resp['Content-Disposition'] = 'attachment; filename="SYNK_Root_CA.crt"'
    return resp


@vault_unlocked
@require_GET
def download_my_certificate(request):
    """Unduh sertifikat X.509 (.crt) untuk di-import ke Adobe Acrobat Reader."""
    key_obj = ensure_user_signing_key(request.user, request.data_key)
    resp = HttpResponse(key_obj.certificate_pem, content_type='application/x-x509-ca-cert')
    resp['Content-Disposition'] = f'attachment; filename="{request.user.username}_synk_cert.crt"'
    return resp


@vault_unlocked
@require_GET
def pdf_signature_status_endpoint(request, file_id):
    """Mengecek status digital signature file PDF di vault."""
    sf = get_object_or_404(StoredFile, id=file_id)
    data_key = request.data_key
    filename = stored_filename(sf, data_key)

    if not filename.lower().endswith('.pdf'):
        return JsonResponse({'is_pdf': False})

    with open_stored_file(sf, data_key, algo='aes') as f:
        pdf_bytes = f.read()

    result = verify_pdf_signature(pdf_bytes, _get_trust_certs())

    return JsonResponse({
        'is_pdf': True,
        'is_signed': result.get('signed', False),
        'valid': result.get('valid', False),
        'signer': result.get('signer', ''),
        'signed_at': result.get('signed_at', ''),
    })


@vault_unlocked
@require_POST
def sign_pdf_file_endpoint(request, file_id):
    """Menandatangani file PDF di vault secara opsional saat user klik Sign PDF di preview."""
    sf = get_object_or_404(StoredFile, id=file_id, owner=request.user)
    data_key = request.data_key
    filename = stored_filename(sf, data_key)

    if not filename.lower().endswith('.pdf'):
        return JsonResponse({'error': 'Hanya file PDF yang dapat ditandatangani.'}, status=400)

    key_obj = ensure_user_signing_key(request.user, data_key)

    with open_stored_file(sf, data_key, algo='aes') as f:
        raw_pdf = f.read()

    signed_pdf = embed_signature_to_pdf_bytes(
        pdf_bytes=raw_pdf,
        priv_pem=key_obj.private_key_pem,
        cert_pem=key_obj.certificate_pem,
        passphrase=data_key,
    )

    overwrite_encrypted_bytes(request.user, data_key, sf, signed_pdf)

    return JsonResponse({'ok': True, 'message': 'PDF berhasil ditandatangani secara digital!'})