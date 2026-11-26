from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import vault_unlocked
from vault.models import StoredFile
from vault.services import open_stored_file, overwrite_encrypted_bytes, stored_filename
from .cert_utils import ensure_user_signing_key
from .models import UserSigningKey
from .pdf_signer import embed_signature_to_pdf_bytes, verify_pdf_signature


@vault_unlocked
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
def verify_pdf_endpoint(request):
    """Memverifikasi tanda tangan digital tertanam pada file PDF."""
    pdf_file = request.FILES.get('pdf_file')
    if not pdf_file or not pdf_file.name.lower().endswith('.pdf'):
        return JsonResponse({'signed': False, 'valid': False, 'message': 'Harap pilih file berformat .pdf.'}, status=400)

    pdf_bytes = pdf_file.read()
    all_certs = list(UserSigningKey.objects.values_list('certificate_pem', flat=True))
    result = verify_pdf_signature(pdf_bytes, all_certs)
    return JsonResponse(result)


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

    all_certs = list(UserSigningKey.objects.values_list('certificate_pem', flat=True))
    result = verify_pdf_signature(pdf_bytes, all_certs)

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

    # 1. Baca PDF asli terdekripsi dari Supabase S3
    with open_stored_file(sf, data_key, algo='aes') as f:
        raw_pdf = f.read()

    # 2. Tanamkan signature PAdES ke dalam bytes PDF
    signed_pdf = embed_signature_to_pdf_bytes(
        pdf_bytes=raw_pdf,
        priv_pem=key_obj.private_key_pem,
        cert_pem=key_obj.certificate_pem,
        passphrase=data_key,
    )

    # 3. Enkripsi ulang (AES/RC4/DES) dan simpan kembali ke Supabase S3
    overwrite_encrypted_bytes(request.user, data_key, sf, signed_pdf)

    return JsonResponse({'ok': True, 'message': 'PDF berhasil ditandatangani secara digital!'})