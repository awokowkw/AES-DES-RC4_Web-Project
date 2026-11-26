import mimetypes
import binascii

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from vault import crypto
from vault.models import PrivateData, StoredFile
from . import keys
from .models import AccessRequest, SharedItem, SharedKey, UserKeyPair
from .services import ensure_keypair, get_data_key

S = AccessRequest.Status
User = get_user_model()
TRIPLE = ("aes", "rc4", "des")


def _triple(prefix, sealed: dict) -> dict:
    return {f"{prefix}_{a}": sealed[a] for a in TRIPLE}


# ---------------------------------------------------------------- B: meminta
@login_required
def request_access(request):
    dk = get_data_key(request)
    if dk is None:
        return redirect("login")
    context = {
        "active_nav": "sharing_request",
        "active_page": "sharing",
        "owner_username": request.GET.get("owner", ""),
        "message": "",
    }
    if request.method == "POST":
        username = request.POST.get("owner_username", "").strip()
        context["owner_username"] = request.POST.get("owner_username", "")
        context["message"] = request.POST.get("message", "")
        owner = User.objects.filter(username=username).first() if username else None
        if not username:
            context["error"] = "Masukkan username pemilik data."
        elif owner is None:
            context["error"] = "Username tidak ditemukan."
        elif owner == request.user:
            context["error"] = "Kamu tidak dapat meminta akses ke akun sendiri."
        elif AccessRequest.objects.filter(
                requester=request.user, owner=owner,
                status__in=[S.PENDING, S.APPROVED]).exists():
            context["error"] = "Masih ada permintaan aktif ke pengguna ini."

        if "error" in context:
            return render(request, "sharing/request.html", context)

        ensure_keypair(request.user, dk)      # B harus punya RSA publik sebelum disetujui
        AccessRequest.objects.create(requester=request.user, owner=owner,
                                     message=request.POST.get("message", ""))
        messages.success(request, "Permintaan terkirim.")
        return redirect("sharing_sent")
    return render(request, "sharing/request.html", context)


@login_required
def sent(request):
    reqs = AccessRequest.objects.filter(requester=request.user).select_related(
        "owner", "sharedkey").order_by("-created")
    return render(request, "sharing/sent.html", {
        "requests": reqs, "active_nav": "sharing_sent", "active_page": "sharing"})


# ---------------------------------------------------------------- A: menyetujui
@login_required
def incoming(request):
    reqs = AccessRequest.objects.filter(owner=request.user).select_related(
        "requester").order_by("-created")
    return render(request, "sharing/incoming.html", {
        "reqs": reqs, "active_nav": "sharing_incoming", "active_page": "sharing"})


@login_required
def approve(request, pk):
    req = get_object_or_404(AccessRequest, pk=pk, owner=request.user, status=S.PENDING)
    odk = get_data_key(request)
    if odk is None:
        return redirect("login")

    context = {
        "req": req,
        "active_nav": "sharing_incoming", "active_page": "sharing",
    }
    data_ids = request.POST.getlist("data") if request.method == "POST" else []
    file_ids = request.POST.getlist("files") if request.method == "POST" else []
    if request.method != "POST" or not (data_ids or file_ids):
        context.update({
            "data": PrivateData.objects.filter(user=request.user).order_by("field"),
            "files": [{"id": f.id, "kind": f.kind, "size": f.size,
                       "name": crypto.open_one(odk, "aes", f.name_aes).decode()}
                      for f in StoredFile.objects.filter(owner=request.user)],
        })
        if request.method == "POST":
            if context["data"].exists() or context["files"]:
                context["error"] = "Pilih setidaknya satu data atau file untuk dibagikan."
            else:
                context["error"] = "Tidak ada data atau file yang tersedia untuk dibagikan."
        return render(request, "sharing/approve.html", context)

    requester_kp = get_object_or_404(UserKeyPair, user=req.requester)
    owner_kp = ensure_keypair(request.user, odk)
    owner_priv = keys.unwrap(odk, bytes(owner_kp.private_key_wrapped),
                             aad=f"rsa-priv:{request.user.id}".encode())

    K = keys.new_share_key()
    timings, sk = {}, None
    try:
        with transaction.atomic():
            token = keys.build_token(owner_priv, requester_kp.public_key_pem,
                                     req.id, request.user.username, K)
            sk = SharedKey.objects.create(
                request=req, token=token,
                key_wrapped_owner=keys.wrap(odk, K, aad=f"share-owner:{req.id}".encode()))

            for d in PrivateData.objects.filter(user=request.user, pk__in=data_ids):
                plain = crypto.open_all(odk, d.blobs())            # dekripsi 3 versi, harus sama
                SharedItem.objects.create(
                    shared_key=sk, kind="data", size=len(plain),
                    **_triple("label", crypto.seal(K, d.field.encode())),
                    **_triple("data", crypto.seal(K, plain, timings)))

            for f in StoredFile.objects.filter(owner=request.user, pk__in=file_ids):
                name = crypto.open_one(odk, "aes", f.name_aes)
                item = SharedItem.objects.create(
                    shared_key=sk, kind=f.kind, size=f.size,
                    **_triple("label", crypto.seal(K, name)))
                rel = {a: f"shared/{sk.id}/{item.id}.{a}" for a in TRIPLE}
                outs = {a: default_storage.open(rel[a], "wb") for a in TRIPLE}
                try:
                    with default_storage.open(f.path_aes, "rb") as src:
                        crypto.encrypt_stream(K, crypto.decrypt_stream(odk, "aes", src), outs, timings)
                finally:
                    for o in outs.values():
                        o.close()
                item.path_aes, item.path_rc4, item.path_des = rel["aes"], rel["rc4"], rel["des"]
                item.save()

            req.status, req.decided_at = S.APPROVED, timezone.now()
            req.save()
    except Exception:
        if sk is not None:
            # Clean up orphaned shared files from storage
            for si in SharedItem.objects.filter(shared_key=sk):
                for p in [si.path_aes, si.path_rc4, si.path_des]:
                    if p:
                        default_storage.delete(p)
        raise
    return render(request, "sharing/approved.html", {
        "req": req, "token": token,
        "active_nav": "sharing_incoming", "active_page": "sharing"})


@login_required
def show_token(request, pk):                 # A bisa melihat kode lagi kalau pesan WA hilang
    req = get_object_or_404(AccessRequest, pk=pk, owner=request.user, status=S.APPROVED)
    return render(request, "sharing/approved.html", {
        "req": req, "token": req.sharedkey.token,
        "active_nav": "sharing_incoming", "active_page": "sharing"})


@login_required
def reject(request, pk):
    if request.method == "POST":
        req = get_object_or_404(AccessRequest, pk=pk, owner=request.user, status=S.PENDING)
        req.status, req.decided_at = S.REJECTED, timezone.now()
        req.save()
        messages.success(request, "Permintaan ditolak.")
    return redirect("sharing_incoming")


@login_required
def revoke(request, pk):
    if request.method == "POST":
        req = get_object_or_404(AccessRequest, pk=pk, owner=request.user, status=S.APPROVED)
        sk = req.sharedkey
        # Delete all shared ciphertext files from storage (local or S3)
        for si in sk.items.all():
            for p in [si.path_aes, si.path_rc4, si.path_des]:
                if p:
                    default_storage.delete(p)
        sk.delete()                          # SharedItem ikut terhapus (cascade)
        req.status, req.decided_at = S.REVOKED, timezone.now()
        req.save()
        messages.success(request, "Akses dicabut dan salinan data dihapus.")
    return redirect("sharing_incoming")


# ---------------------------------------------------------------- B: impor kunci
@login_required
def import_key(request, pk):
    req = get_object_or_404(AccessRequest, pk=pk, requester=request.user, status=S.APPROVED)
    dk = get_data_key(request)
    if dk is None:
        return redirect("login")
    if request.method == "POST":
        try:
            my_kp = UserKeyPair.objects.get(user=request.user)
            my_priv = keys.unwrap(dk, bytes(my_kp.private_key_wrapped),
                                  aad=f"rsa-priv:{request.user.id}".encode())
            owner_pub = UserKeyPair.objects.get(user=req.owner).public_key_pem
            K = keys.open_token(request.POST["token"], my_priv, owner_pub, req.id)
        except (ValueError, KeyError, TypeError, binascii.Error,
                UserKeyPair.DoesNotExist):
            return render(request, "sharing/import.html", {
                "req": req, "error": "Kode kunci tidak valid atau tidak cocok dengan permintaan ini.",
                "token": request.POST.get("token", ""),
                "active_nav": "sharing_sent", "active_page": "sharing",
            })
        sk = req.sharedkey
        sk.key_wrapped_requester = keys.wrap(dk, K, aad=f"share-req:{req.id}".encode())
        sk.imported_at = timezone.now()
        sk.save()
        messages.success(request, "Kunci berhasil diimpor.")
        return redirect("sharing_received", pk=pk)
    return render(request, "sharing/import.html", {
        "req": req, "active_nav": "sharing_sent", "active_page": "sharing"})


# ---------------------------------------------------------------- B: membuka data
def _open_share_key(request, sk):
    """Kembalikan K (atau None jika belum diimpor)."""
    if not sk.key_wrapped_requester:
        return None
    dk = get_data_key(request)
    return keys.unwrap(dk, bytes(sk.key_wrapped_requester),
                       aad=f"share-req:{sk.request_id}".encode())


def _plain_stream(K, algo, storage_path):
    """Buka file dari default_storage, verifikasi MAC DULU, lalu alirkan."""
    f = default_storage.open(storage_path, "rb")
    try:
        gen = crypto.decrypt_stream(K, algo, f)
        first = next(gen, b"")
    except Exception:
        f.close()
        raise

    def body():
        try:
            yield first
            yield from gen
        finally:
            f.close()
    return body()


@login_required
def received(request, pk):
    req = get_object_or_404(AccessRequest, pk=pk, requester=request.user, status=S.APPROVED)
    if get_data_key(request) is None:
        return redirect("login")
    K = _open_share_key(request, req.sharedkey)
    if K is None:
        messages.info(request, "Impor kode kunci terlebih dahulu untuk membuka data.")
        return redirect("sharing_import", pk=pk)
    items = [{"id": i.id, "kind": i.kind, "size": i.size,
              "label": crypto.open_one(K, "aes", i.label_aes).decode()}
             for i in req.sharedkey.items.all()]
    return render(request, "sharing/received.html", {
        "req": req, "items": items,
        "active_nav": "sharing_sent", "active_page": "sharing"})


@login_required
def read_item(request, item_pk, algo):
    if algo not in TRIPLE:
        raise Http404
    if get_data_key(request) is None:
        return redirect("login")
    item = get_object_or_404(
        SharedItem.objects.select_related("shared_key__request"), pk=item_pk,
        shared_key__request__requester=request.user,        # hanya peminta yang sah
        shared_key__request__status=S.APPROVED)             # dan hanya selama belum dicabut
    req = item.shared_key.request
    if req.expires_at and req.expires_at < timezone.now():
        raise Http404
    K = _open_share_key(request, item.shared_key)
    if K is None:
        return redirect("sharing_import", pk=req.id)

    try:
        if item.kind == "data":
            plain = crypto.open_one(K, algo, getattr(item, f"data_{algo}"))
            return HttpResponse(plain.decode(), content_type="text/plain; charset=utf-8")

        name = crypto.open_one(K, "aes", item.label_aes).decode()
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        stream = _plain_stream(K, algo, getattr(item, f"path_{algo}"))
    except crypto.IntegrityError as e:
        messages.error(request, f"Data gagal diverifikasi: {e}")
        return redirect("sharing_received", pk=req.id)

    resp = FileResponse(stream, as_attachment=not mime.startswith("image/"),
                        filename=name, content_type=mime)
    resp["Content-Length"] = item.size
    return resp