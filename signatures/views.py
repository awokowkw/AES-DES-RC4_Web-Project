from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from accounts import keystore

from .cert_utils import ensure_root_ca, ensure_user_signing_key
from .models import RootCA, UserSigningKey
from .pdf_signer import verify_pdf_signature


def _get_passphrase(request) -> bytes:
    """Ambil data_key asli (sama yang dipakai saat upload). Endpoint signature
    tidak memakai @vault_unlocked, jadi data_key diambil dari keystore cache.
    Fallback lama hanya dipakai bila kunci benar-benar tidak tersedia."""
    dk = getattr(request, 'data_key', None)
    if isinstance(dk, bytes):
        return dk
    dk = keystore.get_key(request.session.session_key)
    if isinstance(dk, bytes):
        return dk
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
def regenerate_key_endpoint(request):
    """Hapus key lama (self-signed) & buat ulang cert yang ditandatangani Root CA.
    Diperlukan agar PDF lama yang ditandatangani cert self-signed jadi terverifikasi."""
    UserSigningKey.objects.filter(user=request.user).delete()
    key_obj = ensure_user_signing_key(request.user, _get_passphrase(request))
    return JsonResponse({
        'has_key': True,
        'created_at': key_obj.created_at.strftime('%d %b %Y, %H:%M'),
        'public_key_preview': key_obj.public_key_pem.splitlines()[1][:36] + '...',
        'message': 'Key pair & sertifikat baru (ditandatangani Root CA SYNK) berhasil dibuat! Unggah ulang PDF untuk menandatangani ulang.',
    })


@login_required
@require_POST
def verify_pdf_endpoint(request):
    """Memverifikasi tanda tangan digital tertanam pada file PDF."""
    pdf_file = request.FILES.get('pdf_file')
    if not pdf_file or not pdf_file.name.lower().endswith('.pdf'):
        return JsonResponse({'signed': False, 'valid': False, 'message': 'Harap pilih file berformat .pdf.'}, status=400)

    pdf_bytes = pdf_file.read()
    # Root CA sebagai trust root (cert user ditandatangani root). Sertifikat
    # user lama (self-signed) tetap dimasukkan agar kompatibel ke belakang.
    trust_certs = []
    root = RootCA.objects.first()
    if root:
        trust_certs.append(root.certificate_pem)
    trust_certs += list(UserSigningKey.objects.values_list('certificate_pem', flat=True))
    result = verify_pdf_signature(pdf_bytes, trust_certs)
    return JsonResponse(result)


@login_required
@require_GET
def download_root_ca(request):
    """Unduh Root CA SYNK (.crt). Install SEKALI ke Trusted Root (Edge/Adobe)
    agar SEMUA tanda tangan user otomatis terverifikasi."""
    root = ensure_root_ca()
    resp = HttpResponse(root.certificate_pem, content_type='application/x-x509-ca-cert')
    resp['Content-Disposition'] = 'attachment; filename="SYNK_Root_CA.crt"'
    return resp


@login_required
@require_GET
def download_my_certificate(request):
    """Unduh sertifikat X.509 (.crt) untuk di-import ke Adobe Acrobat Reader."""
    key_obj = ensure_user_signing_key(request.user, _get_passphrase(request))
    resp = HttpResponse(key_obj.certificate_pem, content_type='application/x-x509-ca-cert')
    resp['Content-Disposition'] = f'attachment; filename="{request.user.username}_synk_cert.crt"'
    return resp