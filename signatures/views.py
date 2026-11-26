from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from .cert_utils import ensure_user_signing_key
from .models import UserSigningKey
from .pdf_signer import verify_pdf_signature


def _get_passphrase(request) -> bytes:
    """Mengambil data_key dari request (middleware) atau fallback aman."""
    dk = getattr(request, 'data_key', None)
    if isinstance(dk, bytes):
        return dk
    if isinstance(dk, str):
        return dk.encode('utf-8')
    return f"synk-key-{request.user.id}".encode('utf-8')


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


@login_required
@require_POST
def generate_key_endpoint(request):
    """Membuatkan RSA Key Pair & X.509 Certificate jika user belum punya."""
    key_obj = ensure_user_signing_key(request.user, _get_passphrase(request))
    return JsonResponse({
        'has_key': True,
        'created_at': key_obj.created_at.strftime('%d %b %Y, %H:%M'),
        'public_key_preview': key_obj.public_key_pem.splitlines()[1][:36] + '...',
        'message': 'RSA Key Pair & X.509 Certificate berhasil dibuat!',
    })


@login_required
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


@login_required
@require_GET
def download_my_certificate(request):
    """Unduh sertifikat X.509 (.crt) untuk di-import ke Adobe Acrobat Reader."""
    key_obj = ensure_user_signing_key(request.user, _get_passphrase(request))
    resp = HttpResponse(key_obj.certificate_pem, content_type='application/x-x509-ca-cert')
    resp['Content-Disposition'] = f'attachment; filename="{request.user.username}_synk_cert.crt"'
    return resp